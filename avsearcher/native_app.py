import csv
import math
import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List

try:
    import webbrowser
except ImportError:
    webbrowser = None

# Android detection — p4a sets ANDROID_ARGUMENT env var
_ON_ANDROID = "ANDROID_ARGUMENT" in os.environ

# 注册中文字体（必须在导入其他 kivy 模块之前）
try:
    from kivy.core.text import LabelBase

    if _ON_ANDROID:
        _FONT_PATHS = [
            "/system/fonts/NotoSansCJK-Regular.ttc",
            "/system/fonts/NotoSansSC-Regular.otf",
            "/system/fonts/DroidSansFallback.ttf",
        ]
    else:
        _FONT_PATHS = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        ]

    for _fp in _FONT_PATHS:
        try:
            if os.path.exists(_fp):
                LabelBase.register(name="Roboto", fn_regular=_fp)
                break
        except Exception:
            pass
except Exception:
    pass

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle

from .search import SearchService, fetch_article_content, set_cache_dir


BG_COLOR = (0.96, 0.93, 0.88, 1)
CARD_COLOR = (0.99, 0.98, 0.96, 0.98)
ACCENT_COLOR = (0.62, 0.18, 0.12, 1)
ACCENT_SOFT = (0.86, 0.47, 0.31, 1)
INK_COLOR = (0.13, 0.09, 0.07, 1)
MUTED_COLOR = (0.42, 0.35, 0.31, 1)
PILL_COLOR = (0.97, 0.93, 0.88, 1)


def bind_text_width(label: Label) -> Label:
    label.bind(size=lambda instance, value: setattr(instance, "text_size", (value[0], None)))
    return label


def bind_auto_height(label: Label, min_height=20) -> Label:
    bind_text_width(label)
    label.size_hint_y = None
    label.bind(texture_size=lambda instance, value: setattr(instance, "height", max(dp(min_height), value[1] + dp(6))))
    return label


class Card(BoxLayout):
    def __init__(self, bg_color=CARD_COLOR, radius=22, padding_dp=16, spacing_dp=10, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", dp(padding_dp))
        kwargs.setdefault("spacing", dp(spacing_dp))
        super().__init__(**kwargs)
        self._bg_color = bg_color
        self._radius = radius
        with self.canvas.before:
            self._color = Color(*self._bg_color)
            self._rect = RoundedRectangle(radius=[dp(self._radius)] * 4, pos=self.pos, size=self.size)
        self.bind(pos=self._sync_rect, size=self._sync_rect)

    def _sync_rect(self, *_args):
        self._rect.pos = self.pos
        self._rect.size = self.size


class AutoCard(GridLayout):
    """GridLayout(cols=1) 卡片，支持 minimum_height 自动高度，不会重叠。"""

    def __init__(self, bg_color=CARD_COLOR, radius=22, padding_dp=16, spacing_dp=10, **kwargs):
        kwargs.setdefault("cols", 1)
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("spacing", dp(spacing_dp))
        super().__init__(**kwargs)
        self.padding = [dp(padding_dp)] * 4
        self.bind(minimum_height=self.setter("height"))
        with self.canvas.before:
            self._color = Color(*bg_color)
            self._rect = RoundedRectangle(radius=[dp(radius)] * 4, pos=self.pos, size=self.size)
        self.bind(pos=self._sync_rect, size=self._sync_rect)

    def _sync_rect(self, *_args):
        self._rect.pos = self.pos
        self._rect.size = self.size


class SourceToggle(BoxLayout):
    def __init__(self, key: str, label: str, active: bool, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(38))
        kwargs.setdefault("spacing", dp(8))
        super().__init__(**kwargs)
        self.key = key
        self.checkbox = CheckBox(active=active, size_hint=(None, None), size=(dp(28), dp(28)))
        self.label = bind_text_width(
            Label(
                text=label,
                color=INK_COLOR,
                halign="left",
                valign="middle",
            )
        )
        self.add_widget(self.checkbox)
        self.add_widget(self.label)

    @property
    def active(self) -> bool:
        return bool(self.checkbox.active)


class MetaPill(Label):
    def __init__(self, text: str, color=PILL_COLOR, text_color=MUTED_COLOR, **kwargs):
        kwargs.setdefault("size_hint", (None, None))
        kwargs.setdefault("height", dp(28))
        kwargs.setdefault("padding", (dp(10), dp(6)))
        kwargs.setdefault("color", text_color)
        kwargs.setdefault("text", text)
        super().__init__(**kwargs)
        self.texture_update()
        self.width = max(dp(90), self.texture_size[0] + dp(18))
        with self.canvas.before:
            self._color = Color(*color)
            self._rect = RoundedRectangle(radius=[dp(14)] * 4, pos=self.pos, size=self.size)
        self.bind(pos=self._sync_rect, size=self._sync_rect, texture_size=self._sync_width)

    def _sync_rect(self, *_args):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _sync_width(self, *_args):
        self.width = max(dp(90), self.texture_size[0] + dp(18))


class AVSearcherNativeApp(App):
    title = "AVSearcher"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = SearchService()
        self.source_widgets: List[SourceToggle] = []
        self.result_cards: List[Widget] = []
        self.last_items: List[Dict[str, object]] = []
        self.query_input = None
        self.days_spinner = None
        self.sort_spinner = None
        self.limit_spinner = None
        self.status_label = None
        self.meta_label = None
        self.results_box = None
        self.search_button = None
        self.latest_button = None
        self.export_button = None
        self._current_page = 1
        self._current_params = {}
        self._load_more_btn = None
        self._preload_running = False

    def build(self):
        if Window:
            Window.clearcolor = BG_COLOR
            if not _ON_ANDROID:
                try:
                    Window.minimum_width = 980
                    Window.minimum_height = 720
                except Exception:
                    pass

        root = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(14))

        hero = Card(size_hint_y=None, height=dp(150), padding_dp=22, spacing_dp=8)
        eyebrow = Label(
            text="AVSearcher",
            size_hint_y=None,
            height=dp(20),
            color=ACCENT_COLOR,
            halign="left",
            valign="middle",
        )
        bind_text_width(eyebrow)
        title = Label(
            text="飞机杯评测原生查询台",
            size_hint_y=None,
            height=dp(44),
            font_size="26sp",
            bold=True,
            color=INK_COLOR,
            halign="left",
            valign="middle",
        )
        bind_text_width(title)
        subtitle = bind_text_width(
            Label(
                text="不走浏览器。直接聚合评测源，适合发给同事、客户和采购人员做选品检索。",
                color=MUTED_COLOR,
                halign="left",
                valign="top",
            )
        )
        bind_auto_height(subtitle, 34)
        hero.add_widget(eyebrow)
        hero.add_widget(title)
        hero.add_widget(subtitle)

        all_sources = self.service.list_sources()
        n_sources = len(all_sources)
        SOURCE_COLS = 3
        n_source_rows = math.ceil(n_sources / SOURCE_COLS)
        source_row_h = dp(38) * n_source_rows + dp(6) * max(0, n_source_rows - 1)
        source_card_h = dp(14 * 2 + 18 + 8) + source_row_h
        controls_h = dp(20 * 2 + 44 + 12 + 44 + 12 + 12 + 44) + source_card_h

        controls = Card(size_hint_y=None, height=controls_h, padding_dp=20, spacing_dp=12)

        self.query_input = TextInput(
            hint_text="输入品牌、女优、型号或关键词，例如 GXP / 慢玩 / 中川美铃",
            multiline=False,
            size_hint_y=None,
            height=dp(44),
            background_normal="",
            background_active="",
            background_color=(1, 1, 1, 0.92),
            foreground_color=INK_COLOR,
            cursor_color=ACCENT_COLOR,
            padding=(dp(14), dp(12)),
        )
        self.query_input.bind(on_text_validate=lambda *_args: self.start_search(use_latest=False))

        control_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        self.days_spinner = Spinner(text="近 365 天", values=("近 30 天", "近 90 天", "近 180 天", "近 365 天", "全部"))
        self.sort_spinner = Spinner(text="按最新", values=("按最新", "按相关度"))
        self.limit_spinner = Spinner(text="50 条", values=("30 条", "50 条", "100 条", "200 条", "不限"))
        for spinner in (self.days_spinner, self.sort_spinner, self.limit_spinner):
            spinner.background_normal = ""
            spinner.background_color = (1, 1, 1, 0.92)
            spinner.color = INK_COLOR
            control_row.add_widget(spinner)

        source_card = Card(size_hint_y=None, height=source_card_h, padding_dp=14, spacing_dp=8, bg_color=(1, 1, 1, 0.64))
        source_title = Label(
            text="来源（勾选启用，未能连接的来源不影响其他来源）",
            size_hint_y=None,
            height=dp(18),
            color=MUTED_COLOR,
            halign="left",
            valign="middle",
        )
        bind_text_width(source_title)
        source_row = GridLayout(cols=SOURCE_COLS, size_hint_y=None, height=source_row_h, spacing=dp(6))
        for item in all_sources:
            widget = SourceToggle(item["key"], item["label"], item["default_enabled"])
            self.source_widgets.append(widget)
            source_row.add_widget(widget)
        source_card.add_widget(source_title)
        source_card.add_widget(source_row)

        action_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        self.search_button = Button(text="查询", background_normal="", background_color=ACCENT_COLOR, color=(1, 1, 1, 1))
        self.latest_button = Button(text="看最新", background_normal="", background_color=ACCENT_SOFT, color=(1, 1, 1, 1))
        self.export_button = Button(text="导出 CSV", background_normal="", background_color=(1, 1, 1, 0.92), color=INK_COLOR)
        self.search_button.bind(on_press=lambda *_args: self.start_search(use_latest=False))
        self.latest_button.bind(on_press=lambda *_args: self.start_search(use_latest=True))
        self.export_button.bind(on_press=self.export_csv)
        action_row.add_widget(self.search_button)
        action_row.add_widget(self.latest_button)
        action_row.add_widget(self.export_button)

        controls.add_widget(self.query_input)
        controls.add_widget(control_row)
        controls.add_widget(source_card)
        controls.add_widget(action_row)

        status = Card(size_hint_y=None, height=dp(80), padding_dp=16, spacing_dp=4, bg_color=(1, 1, 1, 0.72))
        self.status_label = Label(text="正在准备默认查询…", color=INK_COLOR, halign="left", valign="middle", size_hint_y=None, height=dp(24))
        self.meta_label = Label(text="", color=MUTED_COLOR, halign="left", valign="middle")
        bind_text_width(self.status_label)
        bind_text_width(self.meta_label)
        status.add_widget(self.status_label)
        status.add_widget(self.meta_label)

        results_scroll = ScrollView(do_scroll_x=False, bar_width=dp(8))
        self.results_box = GridLayout(cols=1, size_hint_y=None, spacing=dp(12), padding=(0, 0, 0, dp(12)))
        self.results_box.bind(minimum_height=self.results_box.setter("height"))
        results_scroll.add_widget(self.results_box)

        root.add_widget(hero)
        root.add_widget(controls)
        root.add_widget(status)
        root.add_widget(results_scroll)

        # 初始化磁盘缓存
        cache_dir = os.path.join(self.user_data_dir, "cache")
        set_cache_dir(cache_dir)

        Clock.schedule_once(lambda _dt: self.start_search(use_latest=True), 0.2)
        # 启动后台预加载
        Clock.schedule_once(lambda _dt: self._start_preload(), 1.5)
        return root

    def _selected_sources(self) -> List[str]:
        return [widget.key for widget in self.source_widgets if widget.active]

    def _days_value(self) -> int:
        mapping = {
            "近 30 天": 30,
            "近 90 天": 90,
            "近 180 天": 180,
            "近 365 天": 365,
            "全部": 3650,
        }
        return mapping.get(self.days_spinner.text, 365)

    def _limit_value(self) -> int:
        if self.limit_spinner.text == "不限":
            return 9999
        return int(self.limit_spinner.text.split()[0])

    def _sort_value(self) -> str:
        return "relevance" if self.sort_spinner.text == "按相关度" else "latest"

    def set_busy(self, busy: bool):
        self.search_button.disabled = busy
        self.latest_button.disabled = busy
        self.export_button.disabled = busy

    def set_status(self, text: str, meta: str = ""):
        self.status_label.text = text
        self.meta_label.text = meta

    def start_search(self, use_latest: bool):
        self._current_page = 1
        self.set_busy(True)
        self.set_status("正在拉取数据…", "查询中")
        query = "" if use_latest else self.query_input.text.strip()
        self._current_params = {
            "query": query,
            "selected_sources": self._selected_sources(),
            "limit": self._limit_value(),
            "days": self._days_value(),
            "sort": self._sort_value(),
            "page": 1,
        }
        thread = threading.Thread(target=self._search_worker, args=(dict(self._current_params),), daemon=True)
        thread.start()

    def load_more(self):
        self._current_page += 1
        params = dict(self._current_params)
        params["page"] = self._current_page
        self.set_busy(True)
        self.set_status("正在加载更多…", "第 %d 页" % self._current_page)
        threading.Thread(target=self._search_worker, args=(params, True), daemon=True).start()

    def _start_preload(self):
        if self._preload_running:
            return
        self._preload_running = True
        threading.Thread(target=self._preload_worker, daemon=True).start()

    def _preload_worker(self):
        """后台持续预加载所有页面的 RSS + 文章全文，缓存到磁盘。"""
        try:
            max_pages = 10
            for page in range(1, max_pages + 1):
                try:
                    payload = self.service.search(
                        query="",
                        limit=50,
                        days=3650,
                        sort="latest",
                        page=page,
                    )
                except Exception:
                    break
                items = payload.get("items", [])
                if not items:
                    break
                # 预抓取每篇文章全文（fetch_article_content 内部会缓存）
                for item in items:
                    url = item.get("url", "")
                    if url:
                        try:
                            fetch_article_content(url)
                        except Exception:
                            pass
                msg = "后台缓存中… 第%d/%d页 (%d篇)" % (page, max_pages, len(items))
                Clock.schedule_once(lambda _dt, m=msg: self._update_preload_status(m), 0)
            Clock.schedule_once(lambda _dt: self._update_preload_status("缓存完成"), 0)
        finally:
            self._preload_running = False

    def _update_preload_status(self, msg: str):
        if self.meta_label and not self.search_button.disabled:
            self.meta_label.text = msg

    def _search_worker(self, params: Dict[str, object], append: bool = False):
        try:
            payload = self.service.search(**params)
        except Exception as exc:
            Clock.schedule_once(lambda _dt: self._apply_error(str(exc)), 0)
            return
        Clock.schedule_once(lambda _dt, p=payload, a=append: self._apply_results(p, append=a), 0)

    def _apply_error(self, message: str):
        self.set_busy(False)
        self.set_status("查询失败", message)

    def _clear_results(self):
        self.results_box.clear_widgets()
        self.result_cards = []

    def _add_result_card(self, item: Dict[str, object]):
        card = AutoCard(padding_dp=18, spacing_dp=8, bg_color=(1, 1, 1, 0.94))

        # ---- 缩略图 ----
        thumb_url = item.get("thumbnail_url")
        if thumb_url:
            img = AsyncImage(
                source=thumb_url,
                size_hint_y=None,
                height=dp(180),
                nocache=False,
                fit_mode="contain",
            )
            card.add_widget(img)

        # ---- 标题 ----
        title_lbl = bind_auto_height(Label(
            text=item.get("title") or "未命名结果",
            color=ACCENT_COLOR,
            halign="left",
            valign="middle",
            bold=True,
            font_size="15sp",
        ), min_height=36)
        card.add_widget(title_lbl)

        # ---- 元信息标签行 ----
        meta_row = GridLayout(cols=4, size_hint_y=None, height=dp(34), spacing=dp(6))
        meta_row.add_widget(MetaPill(item.get("source_label") or "未知", color=(0.95, 0.88, 0.84, 1), text_color=ACCENT_COLOR))
        meta_row.add_widget(MetaPill(item.get("published_label") or "日期未知"))
        meta_row.add_widget(MetaPill(item.get("rating") or "未提评级"))
        meta_row.add_widget(MetaPill(item.get("price_band") or "未提价格"))
        card.add_widget(meta_row)

        # ---- 产品识别 ----
        product_guess = item.get("product_guess")
        if product_guess:
            product = bind_auto_height(Label(
                text="▶ %s" % product_guess,
                color=INK_COLOR,
                halign="left",
                valign="middle",
                bold=True,
                font_size="13sp",
            ))
            card.add_widget(product)

        # ---- 内容摘要 ----
        summary_text = item.get("summary") or "暂无摘要"
        summary = bind_auto_height(Label(
            text=summary_text,
            color=MUTED_COLOR,
            halign="left",
            valign="top",
            font_size="13sp",
        ))
        card.add_widget(summary)

        # ---- 分类标签 ----
        cats = item.get("categories") or []
        if cats:
            categories = bind_auto_height(Label(
                text="标签：%s" % "  /  ".join(cats[:10]),
                color=MUTED_COLOR,
                halign="left",
                valign="middle",
                font_size="12sp",
            ))
            card.add_widget(categories)

        # ---- 底部按钮行 ----
        btn_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(10))
        detail_btn = Button(
            text="软件内阅读全文",
            size_hint_x=0.5,
            background_normal="",
            background_color=ACCENT_COLOR,
            color=(1, 1, 1, 1),
            bold=True,
            font_size="13sp",
        )
        detail_btn.bind(on_press=lambda *_args, it=item: self.show_detail(it))
        open_btn = Button(
            text="浏览器打开原文 →",
            size_hint_x=0.5,
            background_normal="",
            background_color=(0, 0, 0, 0),
            color=ACCENT_SOFT,
            bold=True,
            font_size="13sp",
        )
        open_btn.bind(on_press=lambda *_args, url=item.get("url"): self.open_link(url))
        btn_row.add_widget(detail_btn)
        btn_row.add_widget(open_btn)
        card.add_widget(btn_row)

        self.results_box.add_widget(card)
        self.result_cards.append(card)

    def _apply_results(self, payload: Dict[str, object], append: bool = False):
        self.set_busy(False)
        new_items = payload.get("items", [])

        if append:
            self.last_items.extend(new_items)
            if self._load_more_btn and self._load_more_btn.parent:
                self.results_box.remove_widget(self._load_more_btn)
        else:
            self.last_items = new_items
            self._clear_results()

        if not new_items and not append:
            empty = Card(size_hint_y=None, height=dp(88), padding_dp=18, spacing_dp=8)
            empty_text = bind_auto_height(
                Label(
                    text="没有命中结果。可以改搜品牌名、系列名、女优名，或者把时间范围放宽。",
                    color=MUTED_COLOR,
                    halign="left",
                    valign="middle",
                )
            )
            empty.add_widget(empty_text)
            self.results_box.add_widget(empty)
        else:
            for item in new_items:
                self._add_result_card(item)

        if new_items and payload.get("has_more", False):
            self._load_more_btn = Button(
                text="加载更多结果（第 %d 页）" % (self._current_page + 1),
                size_hint_y=None,
                height=dp(50),
                background_normal="",
                background_color=ACCENT_SOFT,
                color=(1, 1, 1, 1),
                bold=True,
                font_size="14sp",
            )
            self._load_more_btn.bind(on_press=lambda *_args: self.load_more())
            self.results_box.add_widget(self._load_more_btn)

        sources = "、".join(payload.get("sources_used", []))
        errors = payload.get("errors", [])
        error_summary = "（%d 个来源连接失败）" % len(errors) if errors else ""
        meta_parts = [p for p in (sources, payload.get("generated_at"), error_summary) if p]
        self.set_status("共 %s 条结果" % len(self.last_items), " | ".join(meta_parts))

    def show_detail(self, item: Dict[str, object]):
        """in-app 全文阅读弹窗，含图片。"""
        popup_layout = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))

        # 标题
        head_lbl = Label(
            text=item.get("title") or "",
            size_hint_y=None,
            height=dp(48),
            color=INK_COLOR,
            bold=True,
            halign="left",
            valign="middle",
            font_size="15sp",
        )
        bind_text_width(head_lbl)
        head_lbl.bind(texture_size=lambda i, v: setattr(i, "height", min(v[1] + dp(10), dp(80))))
        popup_layout.add_widget(head_lbl)

        # 滚动内容区
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(8))
        content_box = GridLayout(cols=1, size_hint_y=None, spacing=dp(10), padding=(0, 0, 0, dp(16)))
        content_box.bind(minimum_height=content_box.setter("height"))
        loading = Label(
            text="正在加载全文内容，请稍候…",
            size_hint_y=None,
            height=dp(60),
            color=MUTED_COLOR,
            halign="center",
            valign="middle",
        )
        content_box.add_widget(loading)
        scroll.add_widget(content_box)
        popup_layout.add_widget(scroll)

        close_btn = Button(
            text="关  闭",
            size_hint_y=None,
            height=dp(46),
            background_normal="",
            background_color=ACCENT_COLOR,
            color=(1, 1, 1, 1),
            bold=True,
            font_size="14sp",
        )
        popup_layout.add_widget(close_btn)

        popup = Popup(
            title="",
            content=popup_layout,
            size_hint=(0.93, 0.93),
            separator_height=0,
            background_color=(0, 0, 0, 0.6),
        )
        close_btn.bind(on_press=popup.dismiss)
        popup.open()

        def _populate(blocks: List[Dict[str, str]]):
            content_box.clear_widgets()
            if not blocks:
                content_box.add_widget(Label(
                    text="未能提取到文章内容",
                    size_hint_y=None, height=dp(50),
                    color=MUTED_COLOR, halign="center",
                ))
                return
            for block in blocks:
                btype = block["type"]
                if btype == "heading":
                    lbl = Label(
                        text=block["content"],
                        size_hint_y=None,
                        height=dp(20),
                        color=ACCENT_COLOR,
                        halign="left",
                        valign="middle",
                        bold=True,
                        font_size="17sp",
                    )
                    bind_text_width(lbl)
                    lbl.bind(texture_size=lambda i, v: setattr(i, "height", v[1] + dp(14)))
                    content_box.add_widget(lbl)
                elif btype == "text":
                    lbl = Label(
                        text=block["content"],
                        size_hint_y=None,
                        height=dp(20),
                        color=INK_COLOR,
                        halign="left",
                        valign="top",
                        font_size="14sp",
                    )
                    bind_text_width(lbl)
                    lbl.bind(texture_size=lambda i, v: setattr(i, "height", v[1] + dp(8)))
                    content_box.add_widget(lbl)
                elif btype == "image":
                    img = AsyncImage(
                        source=block["content"],
                        size_hint_y=None,
                        height=dp(350),
                        fit_mode="contain",
                    )
                    content_box.add_widget(img)

        def _fetch():
            blocks = fetch_article_content(item.get("url", ""))
            Clock.schedule_once(lambda _dt: _populate(blocks), 0)

        threading.Thread(target=_fetch, daemon=True).start()

    def open_link(self, url: str):
        if not url:
            return
        if _ON_ANDROID:
            try:
                from jnius import autoclass
                Intent = autoclass("android.content.Intent")
                Uri = autoclass("android.net.Uri")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                PythonActivity.mActivity.startActivity(intent)
            except Exception:
                pass
        elif webbrowser:
            webbrowser.open(url)

    def export_csv(self, *_args):
        if not self.last_items:
            self.set_status("当前没有可导出的结果")
            return

        export_dir = self.user_data_dir
        if not _ON_ANDROID:
            try:
                dl = os.path.join(os.path.expanduser("~"), "Downloads")
                if os.path.isdir(dl):
                    export_dir = dl
            except Exception:
                pass
        os.makedirs(export_dir, exist_ok=True)
        output_path = os.path.join(export_dir, "avsearcher-%s.csv" % int(time.time()))

        with open(output_path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["来源", "发布时间", "标题", "链接", "产品识别", "评级", "价格带", "分类", "摘要"])
            for item in self.last_items:
                writer.writerow(
                    [
                        item.get("source_label", ""),
                        item.get("published_label", ""),
                        item.get("title", ""),
                        item.get("url", ""),
                        item.get("product_guess", ""),
                        item.get("rating", ""),
                        item.get("price_band", ""),
                        " / ".join(item.get("categories", [])),
                        item.get("summary", ""),
                    ]
                )

        self.set_status("导出成功", str(output_path))


def run():
    AVSearcherNativeApp().run()
