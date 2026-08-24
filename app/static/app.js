const state = { apps: [], activeApp: null, activeProduct: null };
const $ = (id) => document.getElementById(id);

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

function adminHeaders() {
  const token = sessionStorage.getItem("adminToken");
  return token ? { "X-Admin-Token": token } : {};
}

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...adminHeaders(), ...(options.headers || {}) } });
  if (!response.ok) {
    let message = `请求失败 (${response.status})`;
    try { message = (await response.json()).detail || message; } catch (_) { /* noop */ }
    throw new Error(message);
  }
  return response.json();
}

let toastTimer;
function toast(message, error = false) {
  const node = $("toast");
  node.textContent = message;
  node.className = `toast show${error ? " error" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.className = "toast"; }, 3600);
}

function formatDate(value) {
  if (!value) return "尚未采集";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function periodLabel(value) {
  return ({ P1W: "周付", P1M: "月付", P2M: "双月付", P3M: "季付", P6M: "半年付", P1Y: "年付", ONCE: "一次性" })[value] || value;
}

function appIcon(app, className = "") {
  if (app.icon_url) return `<img class="${className}" src="${escapeHtml(app.icon_url)}" alt="" loading="lazy">`;
  return `<span class="app-fallback ${className}">${escapeHtml((app.name || "A")[0])}</span>`;
}

async function loadStats() {
  const data = await api("/api/stats");
  $("stat-apps").textContent = data.apps;
  $("stat-products").textContent = data.products;
  $("stat-prices").textContent = data.current_prices;
  $("stat-regions").textContent = data.storefronts;
}

async function loadApps() {
  state.apps = await api("/api/apps");
  $("app-count").textContent = state.apps.length;
  $("app-list").innerHTML = state.apps.map((app) => `
    <button class="app-item${state.activeApp?.id === app.id ? " active" : ""}" data-app-id="${app.id}" type="button">
      ${appIcon(app)}
      <span><strong>${escapeHtml(app.name)}</strong><small>${app.last_refresh_status === "ok" ? "已采集" : "等待采集"} · ${escapeHtml(app.apple_id)}</small></span>
    </button>`).join("");
  document.querySelectorAll("[data-app-id]").forEach((button) => button.addEventListener("click", () => openApp(Number(button.dataset.appId))));
}

async function openApp(id) {
  try {
    state.activeApp = await api(`/api/apps/${id}`);
    state.activeProduct = state.activeApp.products.find((product) => product.is_subscription) || state.activeApp.products[0] || null;
    $("welcome").hidden = true;
    $("detail").hidden = false;
    renderDetail();
    await loadApps();
  } catch (error) { toast(error.message, true); }
}

function renderDetail() {
  const app = state.activeApp;
  $("detail-name").textContent = app.name;
  $("detail-developer").textContent = app.developer || `Apple ID ${app.apple_id}`;
  $("detail-updated").textContent = `最后刷新：${formatDate(app.last_refresh_at)}`;
  $("detail-status").textContent = ({ ok: "采集正常", failed: "采集失败", pending: "等待采集" })[app.last_refresh_status] || app.last_refresh_status;
  $("detail-status").className = `status ${app.last_refresh_status}`;
  $("detail-icon").innerHTML = app.icon_url ? `<img src="${escapeHtml(app.icon_url)}" alt="">` : escapeHtml(app.name[0] || "A");

  const select = $("product-select");
  select.innerHTML = app.products.map((product) => `<option value="${product.id}">${escapeHtml(product.canonical_name)} · ${periodLabel(product.period)}</option>`).join("");
  if (state.activeProduct) select.value = state.activeProduct.id;
  const hasProducts = app.products.length > 0;
  $("empty-product").hidden = hasProducts;
  $("price-view").hidden = !hasProducts;
  $("toolbar").querySelectorAll("select, input").forEach((element) => { element.disabled = !hasProducts; });
  if (hasProducts) renderProduct();
}

function renderProduct() {
  const product = state.activeProduct;
  if (!product) return;
  const query = $("price-filter").value.trim().toLowerCase();
  const prices = product.prices.filter((price) => !query || `${price.storefront} ${price.storefront_name} ${price.currency}`.toLowerCase().includes(query));
  const comparable = product.prices.filter((price) => Number(price.amount_cny) > 0);
  const lowest = comparable[0];
  const highest = comparable[comparable.length - 1];
  $("lowest-price").textContent = lowest ? `¥${Number(lowest.amount_cny).toFixed(2)}` : "—";
  $("lowest-region").textContent = lowest ? lowest.storefront_name : "数据缺失";
  $("highest-price").textContent = highest ? `¥${Number(highest.amount_cny).toFixed(2)}` : "—";
  $("highest-region").textContent = highest ? highest.storefront_name : "数据缺失";
  $("available-regions").textContent = product.prices.length;
  const spread = lowest && highest ? ((Number(highest.amount_cny) / Number(lowest.amount_cny) - 1) * 100) : null;
  $("price-spread").textContent = spread === null ? "—" : `${spread.toFixed(1)}%`;
  $("product-period").textContent = periodLabel(product.period);
  $("price-table").innerHTML = prices.map((price, index) => {
    const delta = Number(price.versus_lowest_percent || 0);
    return `<tr class="${price.is_lowest ? "rank-one" : ""}">
      <td>${index + 1}</td>
      <td><span class="price-primary">${escapeHtml(price.storefront_name)}</span> <small>${escapeHtml(price.storefront)}</small></td>
      <td>${escapeHtml(price.price_formatted || `${price.amount} ${price.currency}`)}</td>
      <td class="price-primary">${price.amount_cny == null ? "数据缺失" : `¥${Number(price.amount_cny).toFixed(2)}`}</td>
      <td>${price.amount_usd == null ? "—" : `$${Number(price.amount_usd).toFixed(2)}`}</td>
      <td class="delta${delta > 50 ? " high" : ""}">${price.is_lowest ? "最低" : `+${delta.toFixed(1)}%`}</td>
      <td>${formatDate(price.fetched_at)}</td>
    </tr>`;
  }).join("") || `<tr><td colspan="7">没有匹配的地区</td></tr>`;
}

async function refreshActiveApp() {
  if (!state.activeApp) return;
  const button = $("refresh-button");
  button.disabled = true;
  button.classList.add("loading");
  button.querySelector("span").textContent = "正在采集 30 区";
  try {
    const result = await api(`/api/apps/${state.activeApp.id}/refresh`, { method: "POST" });
    toast(`刷新完成：${result.storefront_success}/${result.storefront_total} 个地区成功`);
    await Promise.all([openApp(state.activeApp.id), loadStats()]);
  } catch (error) {
    toast(error.message, true);
    if (error.message.includes("令牌")) promptToken();
  } finally {
    button.disabled = false;
    button.classList.remove("loading");
    button.querySelector("span").textContent = "刷新价格";
  }
}

function promptToken() {
  const current = sessionStorage.getItem("adminToken") || "";
  const token = window.prompt("请输入服务器 ADMIN_TOKEN；仅保存在当前浏览器会话。", current);
  if (token !== null) {
    sessionStorage.setItem("adminToken", token.trim());
    toast(token.trim() ? "管理令牌已保存" : "管理令牌已清除");
  }
}

$("search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = $("search-input").value.trim();
  if (!query) return;
  const results = $("search-results");
  results.hidden = false;
  results.innerHTML = `<div class="search-result">正在搜索…</div>`;
  try {
    const apps = await api(`/api/search?q=${encodeURIComponent(query)}`);
    results.innerHTML = apps.length ? apps.map((app) => `<button class="search-result" type="button" data-add-id="${app.apple_id}">
      ${appIcon(app)}<span><strong>${escapeHtml(app.name)}</strong><small>${escapeHtml(app.developer)}</small></span>
    </button>`).join("") : `<div class="search-result">没有找到应用</div>`;
    document.querySelectorAll("[data-add-id]").forEach((button) => button.addEventListener("click", async () => {
      const found = apps.find((item) => item.apple_id === button.dataset.addId);
      try {
        const created = await api("/api/apps", { method: "POST", body: JSON.stringify(found) });
        results.hidden = true;
        $("search-input").value = "";
        await Promise.all([loadApps(), loadStats()]);
        await openApp(created.id);
        toast(`${created.name} 已加入监测`);
      } catch (error) {
        toast(error.message, true);
        if (error.message.includes("令牌")) promptToken();
      }
    }));
  } catch (error) { results.innerHTML = `<div class="search-result">${escapeHtml(error.message)}</div>`; }
});

$("product-select").addEventListener("change", (event) => {
  state.activeProduct = state.activeApp.products.find((product) => product.id === Number(event.target.value));
  renderProduct();
});
$("price-filter").addEventListener("input", renderProduct);
$("refresh-button").addEventListener("click", refreshActiveApp);
$("token-button").addEventListener("click", promptToken);

Promise.all([loadApps(), loadStats()]).catch((error) => toast(error.message, true));
