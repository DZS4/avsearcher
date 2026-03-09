const state = {
  sources: [],
  items: [],
};

const sourceList = document.getElementById("source-list");
const results = document.getElementById("results");
const resultTemplate = document.getElementById("result-template");
const queryInput = document.getElementById("query-input");
const daysSelect = document.getElementById("days-select");
const sortSelect = document.getElementById("sort-select");
const limitSelect = document.getElementById("limit-select");
const statusText = document.getElementById("status-text");
const statusMeta = document.getElementById("status-meta");
const errorBox = document.getElementById("error-box");

function setStatus(text, meta = "") {
  statusText.textContent = text;
  statusMeta.textContent = meta;
}

function getSelectedSources() {
  return Array.from(sourceList.querySelectorAll("input[type=checkbox]:checked")).map((input) => input.value);
}

function renderSources(items) {
  sourceList.innerHTML = "";
  items.forEach((item) => {
    const label = document.createElement("label");
    label.className = "source-chip";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = item.key;
    input.checked = item.default_enabled;

    const span = document.createElement("span");
    span.textContent = item.label;

    label.append(input, span);
    sourceList.append(label);
  });
  document.getElementById("stat-sources").textContent = String(items.length);
}

function createCategoryPill(text) {
  const span = document.createElement("span");
  span.className = "category-pill";
  span.textContent = text;
  return span;
}

function renderResults(items) {
  state.items = items;
  results.innerHTML = "";
  document.getElementById("stat-total").textContent = String(items.length);
  document.getElementById("stat-fresh").textContent = items[0]?.published_label?.slice(0, 16) || "-";

  if (!items.length) {
    const empty = document.createElement("article");
    empty.className = "empty-state panel";
    empty.textContent = "没有命中结果。可以试试品牌名、女优名、型号缩写，或者把时间范围放宽。";
    results.append(empty);
    return;
  }

  items.forEach((item) => {
    const node = resultTemplate.content.firstElementChild.cloneNode(true);
    node.querySelector("[data-field=source]").textContent = item.source_label;
    node.querySelector("[data-field=published]").textContent = item.published_label || "日期未知";
    node.querySelector("[data-field=rating]").textContent = item.rating || "未提评级";
    node.querySelector("[data-field=price]").textContent = item.price_band || "未提价格";
    const link = node.querySelector("[data-field=link]");
    link.href = item.url;
    link.textContent = item.title;
    node.querySelector("[data-field=product]").textContent = item.product_guess ? `产品识别：${item.product_guess}` : "产品识别：未提取";
    node.querySelector("[data-field=summary]").textContent = item.summary || "暂无摘要";

    const categories = node.querySelector("[data-field=categories]");
    (item.categories || []).slice(0, 8).forEach((category) => {
      categories.append(createCategoryPill(category));
    });
    results.append(node);
  });
}

function renderErrors(errors) {
  errorBox.textContent = (errors || []).join(" | ");
}

async function fetchSources() {
  const response = await fetch("/api/sources");
  const payload = await response.json();
  state.sources = payload.items || [];
  renderSources(state.sources);
}

function buildSearchParams(useLatest = false) {
  const params = new URLSearchParams();
  if (!useLatest && queryInput.value.trim()) {
    params.set("q", queryInput.value.trim());
  }
  params.set("days", daysSelect.value);
  params.set("sort", sortSelect.value);
  params.set("limit", limitSelect.value);
  getSelectedSources().forEach((source) => params.append("sources", source));
  return params;
}

async function search(useLatest = false) {
  setStatus(useLatest ? "正在拉取最新评测…" : "正在查询评测数据…");
  renderErrors([]);
  const params = buildSearchParams(useLatest);
  const response = await fetch(`/api/search?${params.toString()}`);
  const payload = await response.json();
  renderResults(payload.items || []);
  renderErrors(payload.errors || []);
  const meta = `${payload.sources_used?.join("、") || ""} | ${payload.generated_at || ""}`;
  setStatus(`共找到 ${payload.total || 0} 条结果`, meta);
}

function exportCsv() {
  if (!state.items.length) {
    setStatus("当前没有可导出的结果");
    return;
  }

  const header = ["来源", "发布时间", "标题", "链接", "产品识别", "评级", "价格带", "分类", "摘要"];
  const rows = state.items.map((item) => [
    item.source_label || "",
    item.published_label || "",
    item.title || "",
    item.url || "",
    item.product_guess || "",
    item.rating || "",
    item.price_band || "",
    (item.categories || []).join(" / "),
    item.summary || "",
  ]);

  const csv = [header, ...rows]
    .map((row) =>
      row
        .map((value) => `"${String(value).replace(/"/g, '""')}"`)
        .join(","),
    )
    .join("\n");

  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `avsearcher-${Date.now()}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

document.getElementById("search-button").addEventListener("click", () => search(false));
document.getElementById("latest-button").addEventListener("click", () => search(true));
document.getElementById("export-button").addEventListener("click", exportCsv);
document.getElementById("toggle-sources").addEventListener("click", () => {
  const inputs = Array.from(sourceList.querySelectorAll("input[type=checkbox]"));
  const allChecked = inputs.every((input) => input.checked);
  inputs.forEach((input) => {
    input.checked = !allChecked;
  });
});
queryInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    search(false);
  }
});

async function bootstrap() {
  try {
    await fetchSources();
    await search(true);
  } catch (error) {
    setStatus("初始化失败");
    renderErrors([String(error)]);
  }
}

bootstrap();

