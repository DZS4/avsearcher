import hashlib
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote, urlsplit, urlunsplit

import requests


SHANGHAI_TZ = timezone(timedelta(hours=8))
HTTP_TIMEOUT = 12.0
ARTICLE_TIMEOUT = 15.0
DEFAULT_LIMIT = 30
CACHE_TTL = 300
GENERIC_REVIEW_TERMS = ("测评", "评测", "飞机杯", "名器", "倒模", "推荐")
GENERIC_CATEGORY_PATTERNS = (
    r"^\d(?:\.\d)?星$",
    r"^\d-\d星$",
    r"^\d(?:\.\d)?星推荐$",
    r"^¥\d",
    r"^\d{1,3}\s*[~-]\s*\d{1,3}$",
    r"^\d{1,2}-\d{1,2}cm$",
    r"^\d+-\d+cm$",
    r"^\d+星$",
)
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
RATING_RE = re.compile(r"(\d(?:\.\d)?)星")
PRICE_RE = re.compile(r"(¥\s*\d+(?:-\d+)?)|(\d+\s*[~-]\s*\d+)|参考(?:价|價格)[:：]?\s*￥?\s*(\d+)")
SEP_RE = re.compile(r"[|｜]")
IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\'\s>]+)["\']', re.IGNORECASE)

CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
MEDIA_NS = "http://search.yahoo.com/mrss/"
CONTENT_PREVIEW_LEN = 600


# ---------------------------------------------------------------------------
#  磁盘缓存 — RSS 列表和文章全文都持久化，下次打开秒开
# ---------------------------------------------------------------------------

_disk_cache: Optional["DiskCache"] = None


def set_cache_dir(cache_dir: str) -> None:
    global _disk_cache
    _disk_cache = DiskCache(cache_dir)


def get_disk_cache() -> Optional["DiskCache"]:
    return _disk_cache


class DiskCache:
    """简单的 JSON 文件持久化缓存。"""

    def __init__(self, cache_dir: str):
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, namespace: str, key: str) -> Path:
        safe = hashlib.sha256(key.encode()).hexdigest()[:24]
        ns_dir = self._dir / namespace
        ns_dir.mkdir(parents=True, exist_ok=True)
        return ns_dir / (safe + ".json")

    def get(self, namespace: str, key: str):
        path = self._key_path(namespace, key)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def put(self, namespace: str, key: str, value) -> None:
        path = self._key_path(namespace, key)
        try:
            path.write_text(json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8")
        except OSError:
            pass

    def has(self, namespace: str, key: str) -> bool:
        return self._key_path(namespace, key).exists()


@dataclass
class SourceConfig:
    key: str
    label: str
    site_url: str
    latest_feed: str
    search_feed_template: str
    default_enabled: bool = True
    review_terms: List[str] = field(default_factory=list)
    generic_categories: List[str] = field(default_factory=list)


@dataclass
class ReviewItem:
    source_key: str
    source_label: str
    title: str
    url: str
    summary: str
    author: str
    published_at: Optional[datetime]
    categories: List[str]
    rating: Optional[str]
    price_band: Optional[str]
    product_guess: Optional[str]
    matched_terms: List[str]
    relevance_score: float
    freshness_days: Optional[int]
    thumbnail_url: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["published_at"] = self.published_at.astimezone(SHANGHAI_TZ).isoformat() if self.published_at else None
        payload["published_label"] = format_datetime(self.published_at)
        payload["freshness_days"] = self.freshness_days
        payload["relevance_score"] = round(self.relevance_score, 2)
        return payload


def format_datetime(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.astimezone(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M UTC+08")


def load_source_configs() -> List[SourceConfig]:
    source_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(source_dir, "sources.json")
    with open(path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)
    return [SourceConfig(**item) for item in raw_items]


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = "https" if parts.scheme in ("http", "https") else parts.scheme
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, parts.netloc.lower(), path, "", ""))


def compact_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value.replace("\xa0", " ")).strip()


def strip_html(value: str) -> str:
    return compact_text(html.unescape(HTML_TAG_RE.sub(" ", value or "")))


def split_query_terms(query: str) -> List[str]:
    normalized = compact_text(query.lower())
    if not normalized:
        return []
    tokens = [token for token in re.split(r"[\s,/]+", normalized) if token]
    if normalized not in tokens:
        tokens.insert(0, normalized)
    seen = []
    for token in tokens:
        if token not in seen:
            seen.append(token)
    return seen


def has_review_signal(title: str, summary: str, categories: Sequence[str], review_terms: Sequence[str]) -> bool:
    haystack = " ".join([title, summary] + list(categories))
    terms = list(review_terms) or list(GENERIC_REVIEW_TERMS)
    return any(term.lower() in haystack.lower() for term in terms)


def parse_pub_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def extract_rating(categories: Sequence[str], summary: str) -> Optional[str]:
    pool = list(categories) + [summary]
    for chunk in pool:
        match = RATING_RE.search(chunk)
        if match:
            return match.group(1) + "星"
    return None


def extract_price_band(categories: Sequence[str], summary: str) -> Optional[str]:
    pool = list(categories) + [summary]
    for chunk in pool:
        match = PRICE_RE.search(chunk)
        if not match:
            continue
        if match.group(1):
            return compact_text(match.group(1))
        if match.group(2):
            return compact_text(match.group(2))
        if match.group(3):
            return "参考价 %s" % match.group(3)
    return None


def extract_thumbnail(node: ET.Element, content_html: str) -> Optional[str]:
    """从 RSS item 中提取封面图片 URL。"""
    # 尝试 media:content
    for el in node.findall("{%s}content" % MEDIA_NS):
        url = el.get("url", "").strip()
        if url and el.get("medium", "image") in ("image", ""):
            return url
    # 尝试 media:thumbnail
    for el in node.findall("{%s}thumbnail" % MEDIA_NS):
        url = el.get("url", "").strip()
        if url:
            return url
    # 尝试 enclosure
    enc = node.find("enclosure")
    if enc is not None and enc.get("type", "").startswith("image/"):
        url = enc.get("url", "").strip()
        if url:
            return url
    # 从 HTML 内容中提取第一张图片
    match = IMG_SRC_RE.search(content_html)
    if match:
        u = match.group(1).strip()
        if u.startswith(("http://", "https://")):
            return u
    return None


def is_generic_category(category: str, config: SourceConfig) -> bool:
    if category in config.generic_categories:
        return True
    return any(re.match(pattern, category) for pattern in GENERIC_CATEGORY_PATTERNS)


def guess_product_name(title: str, categories: Sequence[str], config: SourceConfig) -> Optional[str]:
    primary = compact_text(SEP_RE.split(title)[0])
    if "——" in primary:
        primary = compact_text(primary.split("——", 1)[0])
    if primary and len(primary) <= 48:
        return primary
    for category in categories:
        if not is_generic_category(category, config):
            return category
    return None


def compute_freshness_days(published_at: Optional[datetime]) -> Optional[int]:
    if not published_at:
        return None
    delta = datetime.now(timezone.utc) - published_at.astimezone(timezone.utc)
    return max(int(delta.total_seconds() // 86400), 0)


def compute_relevance(item: ReviewItem, query_terms: Sequence[str]) -> float:
    title = item.title.lower()
    summary = item.summary.lower()
    categories = " ".join(item.categories).lower()
    score = 0.0

    if not query_terms:
        if item.published_at:
            freshness_bonus = max(0.0, 14.0 - min(item.freshness_days or 999, 14))
            return 10.0 + freshness_bonus
        return 10.0

    for term in query_terms:
        if term in title:
            score += 8.0
        if term in categories:
            score += 4.0
        if term in summary:
            score += 2.0

    if item.rating:
        score += 0.5
    if item.freshness_days is not None:
        score += max(0.0, 30.0 - min(item.freshness_days, 30)) / 10.0
    return score


def merge_categories(first: Sequence[str], second: Sequence[str]) -> List[str]:
    merged: List[str] = []
    for category in list(first) + list(second):
        if category and category not in merged:
            merged.append(category)
    return merged


class WordpressFeedSource:
    def __init__(self, config: SourceConfig):
        self.config = config

    def fetch(self, query: str, limit: int, page: int = 1) -> Tuple[List[ReviewItem], Optional[str]]:
        url = self._build_url(query, page)
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "AVSearcher/1.0 (+https://localhost)"},
                allow_redirects=True,
                timeout=HTTP_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return [], "%s 抓取失败: %s" % (self.config.label, exc)
        try:
            items = self._parse_feed(response.text, query)
        except ET.ParseError as exc:
            return [], "%s RSS 解析失败: %s" % (self.config.label, exc)
        return items[:limit], None

    def _build_url(self, query: str, page: int = 1) -> str:
        normalized = compact_text(query)
        if not normalized:
            base = self.config.latest_feed
        else:
            base = self.config.search_feed_template.format(query=quote(normalized))
        if page > 1:
            sep = "&" if "?" in base else "?"
            base += "%spaged=%d" % (sep, page)
        return base

    def _parse_feed(self, xml_text: str, query: str) -> List[ReviewItem]:
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return []

        items: List[ReviewItem] = []
        query_terms = split_query_terms(query)
        for node in channel.findall("item"):
            title = compact_text(node.findtext("title", default=""))
            url = compact_text(node.findtext("link", default=""))
            description_html = node.findtext("description", default="")
            content_encoded = node.findtext("{%s}encoded" % CONTENT_NS, default="")
            full_html = content_encoded or description_html
            # 优先从 content:encoded 取更长摘要
            if content_encoded:
                long_text = strip_html(content_encoded)
                short_text = strip_html(description_html)
                summary = long_text if len(long_text) > len(short_text) else short_text
                if len(summary) > CONTENT_PREVIEW_LEN:
                    summary = summary[:CONTENT_PREVIEW_LEN].rstrip() + "…"
            else:
                summary = strip_html(description_html)
            author = compact_text(node.findtext("{http://purl.org/dc/elements/1.1/}creator", default=""))
            categories = [compact_text(child.text or "") for child in node.findall("category")]
            categories = [category for category in categories if category]
            if not title or not url:
                continue
            if not query and not has_review_signal(title, summary, categories, self.config.review_terms):
                continue

            published_at = parse_pub_date(node.findtext("pubDate"))
            thumbnail_url = extract_thumbnail(node, full_html)
            item = ReviewItem(
                source_key=self.config.key,
                source_label=self.config.label,
                title=title,
                url=canonicalize_url(url),
                summary=summary,
                author=author or self.config.label,
                published_at=published_at,
                categories=categories,
                rating=extract_rating(categories, summary),
                price_band=extract_price_band(categories, summary),
                product_guess=guess_product_name(title, categories, self.config),
                matched_terms=[],
                relevance_score=0.0,
                freshness_days=compute_freshness_days(published_at),
                thumbnail_url=thumbnail_url,
            )
            item.matched_terms = [term for term in query_terms if term in (title + " " + summary + " " + " ".join(categories)).lower()]
            item.relevance_score = compute_relevance(item, query_terms)
            items.append(item)
        return items


class SearchService:
    def __init__(self, sources: Optional[Sequence[SourceConfig]] = None):
        configs = list(sources or load_source_configs())
        self.configs = {config.key: config for config in configs}
        self.sources = {config.key: WordpressFeedSource(config) for config in configs}
        self._cache: Dict[Tuple[str, str, int, int, str], Tuple[float, Dict[str, object]]] = {}

    def list_sources(self) -> List[Dict[str, object]]:
        return [
            {
                "key": config.key,
                "label": config.label,
                "site_url": config.site_url,
                "default_enabled": config.default_enabled,
            }
            for config in self.configs.values()
        ]

    def search(
        self,
        query: str = "",
        selected_sources: Optional[Sequence[str]] = None,
        limit: int = DEFAULT_LIMIT,
        days: int = 3650,
        sort: str = "latest",
        page: int = 1,
    ) -> Dict[str, object]:
        normalized_query = compact_text(query)
        requested = [key for key in (selected_sources or self.configs.keys()) if key in self.sources]
        if not requested:
            requested = [key for key, config in self.configs.items() if config.default_enabled]

        limit = max(1, limit)
        days = max(1, days)
        sort = sort if sort in ("latest", "relevance") else "latest"
        cache_key = (normalized_query, ",".join(sorted(requested)), limit, days, sort, page)

        now = datetime.now(timezone.utc).timestamp()
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] < CACHE_TTL:
            return cached[1]

        # 检查磁盘缓存（离线可用）
        disk = get_disk_cache()
        disk_key = "%s|%s|%d|%d|%s|%d" % cache_key

        per_source_limit = max(limit, 20)
        try:
            with ThreadPoolExecutor(max_workers=max(len(requested), 1)) as executor:
                futures = {
                    executor.submit(self.sources[key].fetch, normalized_query, per_source_limit, page): key
                    for key in requested
                }
                results = [future.result() for future in as_completed(futures)]
        except Exception:
            # 网络全挂 → 从磁盘缓存返回
            if disk:
                disk_cached = disk.get("search", disk_key)
                if disk_cached:
                    return disk_cached
            raise

        merged: Dict[str, ReviewItem] = {}
        errors: List[str] = []
        for items, error in results:
            if error:
                errors.append(error)
            for item in items:
                if item.freshness_days is not None and item.freshness_days > days:
                    continue
                existing = merged.get(item.url)
                if existing:
                    existing.categories = merge_categories(existing.categories, item.categories)
                    existing.summary = existing.summary if len(existing.summary) >= len(item.summary) else item.summary
                    existing.rating = existing.rating or item.rating
                    existing.price_band = existing.price_band or item.price_band
                    existing.relevance_score = max(existing.relevance_score, item.relevance_score)
                    existing.matched_terms = merge_categories(existing.matched_terms, item.matched_terms)
                    continue
                merged[item.url] = item

        items = list(merged.values())
        if sort == "relevance" and normalized_query:
            items.sort(key=lambda item: (item.relevance_score, item.published_at or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
        else:
            items.sort(key=lambda item: (item.published_at or datetime.min.replace(tzinfo=timezone.utc), item.relevance_score), reverse=True)

        items = items[:limit]
        payload = {
            "query": normalized_query,
            "total": len(items),
            "page": page,
            "has_more": len(merged) >= 3,
            "generated_at": format_datetime(datetime.now(timezone.utc)),
            "sources_used": [self.configs[key].label for key in requested if key in self.configs],
            "errors": errors,
            "items": [item.to_dict() for item in items],
        }
        self._cache[cache_key] = (now, payload)
        if disk:
            disk.put("search", disk_key, payload)
        return payload


class ArticleParser(HTMLParser):
    """从文章页面 HTML 中提取正文段落、标题和图片 URL，保留排版结构。"""

    BLOCK_TAGS = frozenset({"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "figcaption"})
    HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
    SKIP_TAGS = frozenset({"script", "style", "nav", "header", "footer", "aside", "noscript", "form"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: List[Dict[str, str]] = []
        self._skip_depth = 0
        self._block_depth = 0
        self._buf: List[str] = []
        self._seen_imgs: set = set()
        self._block_tag: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attrs_dict = dict(attrs)
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        if tag == "img":
            src = (
                attrs_dict.get("data-src")
                or attrs_dict.get("data-lazy-src")
                or attrs_dict.get("data-original")
                or attrs_dict.get("src")
                or ""
            ).strip()
            if (
                src
                and src.startswith(("http://", "https://"))
                and src not in self._seen_imgs
                and "emoji" not in src
                and "icon" not in src.lower()
                and "logo" not in src.lower()
            ):
                self._seen_imgs.add(src)
                self._flush()
                self.blocks.append({"type": "image", "content": src})
        if tag in self.BLOCK_TAGS:
            if self._block_depth == 0:
                self._block_tag = tag
            self._block_depth += 1
            if tag == "li":
                self._buf.append("  \u2022 ")
        if tag == "br" and self._block_depth > 0:
            self._buf.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth > 0:
            return
        if tag in self.BLOCK_TAGS:
            self._block_depth = max(0, self._block_depth - 1)
            if self._block_depth == 0:
                bt = "heading" if self._block_tag in self.HEADING_TAGS else "text"
                self._flush(bt)
                self._block_tag = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._block_depth > 0:
            self._buf.append(data)

    def _flush(self, block_type: str = "text") -> None:
        raw = "".join(self._buf)
        lines = raw.split("\n")
        cleaned = [WHITESPACE_RE.sub(" ", ln).strip() for ln in lines]
        text = "\n".join(ln for ln in cleaned if ln)
        self._buf = []
        if text and len(text) >= 3:
            self.blocks.append({"type": block_type, "content": text})


def fetch_article_content(url: str) -> List[Dict[str, str]]:
    """抓取文章页面，提取正文段落与图片，返回 block 列表。带磁盘缓存。"""
    cache = get_disk_cache()
    if cache:
        cached = cache.get("article", url)
        if cached is not None:
            return cached
    try:
        sess = requests.Session()
        sess.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        })
        sess.trust_env = False
        try:
            resp = sess.get(url, timeout=ARTICLE_TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            # 修正常见中文页面编码误判
            if resp.encoding and resp.encoding.lower() in ("iso-8859-1", "latin-1"):
                resp.encoding = "utf-8"
        finally:
            sess.close()
        parser = ArticleParser()
        parser.feed(resp.text)
        result = [b for b in parser.blocks if b["type"] in ("image", "heading") or len(b["content"]) >= 5]
        result = result[:300]
        if cache:
            cache.put("article", url, result)
        return result
    except Exception as exc:
        return [{"type": "text", "content": "加载失败：%s" % exc}]
