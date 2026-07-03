const HTTP_API = "/astrbot_plugin_llm_identify/page";
const PAGE_ENDPOINT_PREFIX = "page";
let bridgeReadyPromise = null;

const els = {
  providerId: document.getElementById("providerId"),
  claimedModel: document.getElementById("claimedModel"),
  modelFamily: document.getElementById("modelFamily"),
  runningState: document.getElementById("runningState"),
  riskLevel: document.getElementById("riskLevel"),
  refreshBtn: document.getElementById("refreshBtn"),
  detectBtn: document.getElementById("detectBtn"),
  detectMode: document.getElementById("detectMode"),
  directFields: document.getElementById("directFields"),
  directBaseUrl: document.getElementById("directBaseUrl"),
  directApiKey: document.getElementById("directApiKey"),
  directModel: document.getElementById("directModel"),
  message: document.getElementById("message"),
  reportPanel: document.getElementById("reportPanel"),
  reportTime: document.getElementById("reportTime"),
  confidenceBadge: document.getElementById("confidenceBadge"),
  findingsSummary: document.getElementById("findingsSummary"),
  scoreGrid: document.getElementById("scoreGrid"),
  probabilityList: document.getElementById("probabilityList"),
  probeList: document.getElementById("probeList"),
  rawReport: document.getElementById("rawReport"),
};

function setMessage(text, kind = "info") {
  if (!text) {
    els.message.hidden = true;
    els.message.textContent = "";
    return;
  }
  els.message.hidden = false;
  els.message.textContent = text;
  els.message.dataset.kind = kind;
}

async function fetchJson(path, options = {}) {
  const debugHttp = new URLSearchParams(window.location.search).get("debug_http") === "1";
  const bridge = debugHttp ? getBridge() : await waitForBridge();
  const method = (options.method || "GET").toUpperCase();
  let payload;
  if (isReadyBridge(bridge)) {
    payload = await bridgeRequest(bridge, path, method, options.body);
  } else if (debugHttp) {
    const response = await fetch(`${HTTP_API}${path}`, {
      cache: "no-store",
      headers: options.body ? { "Content-Type": "application/json" } : undefined,
      ...options,
    });
    const text = await response.text();
    try {
      payload = text ? JSON.parse(text) : {};
    } catch (error) {
      throw new Error(response.ok ? "Response is not JSON" : `HTTP ${response.status}: ${text.slice(0, 160)}`);
    }
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  } else {
    throw new Error("AstrBot page bridge is unavailable. Open this page from the AstrBot plugin extension page.");
  }
  payload = normalizeResponse(payload);
  if (!payload.success) throw new Error(payload.error || "Request failed");
  return payload.data;
}

function getBridge() {
  if (window.AstrBotPluginPage) return window.AstrBotPluginPage;
  try {
    if (window.parent && window.parent !== window && window.parent.AstrBotPluginPage) return window.parent.AstrBotPluginPage;
  } catch (error) {
    return null;
  }
  return null;
}

function isReadyBridge(bridge) {
  return Boolean(bridge && typeof bridge.apiGet === "function" && typeof bridge.apiPost === "function");
}

async function waitForBridge(timeoutMs = 1500) {
  const bridge = getBridge();
  if (isReadyBridge(bridge)) return bridge;
  if (!bridgeReadyPromise) {
    bridgeReadyPromise = waitForBridgeReady(timeoutMs).finally(() => {
      if (!isReadyBridge(getBridge())) bridgeReadyPromise = null;
    });
  }
  return bridgeReadyPromise;
}

async function waitForBridgeReady(timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const bridge = getBridge();
    if (isReadyBridge(bridge)) return bridge;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  return getBridge();
}

async function bridgeRequest(bridge, path, method, body) {
  const url = new URL(path, "https://astrbot-plugin-page.local/");
  const endpoint = `${PAGE_ENDPOINT_PREFIX}/${url.pathname.replace(/^\/+/, "")}`.replace(/\/+/g, "/");
  if (method === "GET") {
    const params = Object.fromEntries(url.searchParams.entries());
    return bridge.apiGet(endpoint, Object.keys(params).length ? params : undefined);
  }
  let payload = body || {};
  if (typeof payload === "string") {
    try {
      payload = JSON.parse(payload);
    } catch (error) {
      payload = {};
    }
  }
  return bridge.apiPost(endpoint, payload);
}

function normalizeResponse(payload) {
  if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "success")) return payload;
  return { success: true, data: payload };
}

function renderStatus(data) {
  els.providerId.textContent = data.provider_id || "unknown";
  els.claimedModel.textContent = data.claimed_model || "unknown";
  els.modelFamily.textContent = data.model_family_guess || "unknown";
  els.runningState.textContent = data.running ? "running" : "idle";
  renderReport(data.last_report);
}

function renderReport(report) {
  if (!report) {
    els.reportPanel.hidden = true;
    els.riskLevel.textContent = "none";
    return;
  }
  els.reportPanel.hidden = false;
  els.riskLevel.textContent = report.risk_level || "unknown";
  els.claimedModel.textContent = report.claimed_model || "unknown";
  els.modelFamily.textContent = report.model_family_guess || "unknown";
  els.confidenceBadge.textContent = `Confidence ${Math.round(Number(report.confidence || 0) * 100)}%`;
  els.findingsSummary.textContent = (report.findings || ["No major findings."]).slice(0, 2).join(" ");
  els.reportTime.textContent = report.created_at ? new Date(report.created_at * 1000).toLocaleString() : "";
  els.rawReport.textContent = report.text || "";
  renderScores(report);
  renderProbabilities(report.provider_probabilities || {}, report.fingerprint_candidates || [], report.fingerprint_database_status || {});
  const results = Array.isArray(report.probe_results) ? report.probe_results : [];
  els.probeList.innerHTML = results.map(renderProbe).join("");
}

function renderScores(report) {
  const items = [
    ["Protocol", report.protocol_score],
    ["Token Truth", report.token_truth_score],
    ["Fingerprint", report.fingerprint_confidence],
    ["Spoofing", report.spoofing_risk],
    ["Proxy", report.proxy_probability],
    ["Mixture", report.mixture_probability],
  ].filter(([, value]) => value !== null && value !== undefined);
  els.scoreGrid.innerHTML = items.map(([label, value]) => `
    <article class="score-card">
      <span>${escapeHtml(label)}</span>
      <strong>${Math.round(Number(value || 0) * 100)}%</strong>
    </article>
  `).join("");
}

function renderProbabilities(probabilities, fingerprintCandidates, databaseStatus) {
  const entries = Object.entries(probabilities).sort((a, b) => Number(b[1]) - Number(a[1]));
  const providerHtml = entries.map(([name, value]) => `
    <article class="candidate">
      <span>Provider probability</span>
      <strong>${escapeHtml(name)}</strong>
      <p>${Math.round(Number(value || 0) * 100)}%</p>
    </article>
  `).join("");
  const fingerprintHtml = (fingerprintCandidates || []).map((item) => `
    <article class="candidate">
      <span>Fingerprint candidate</span>
      <strong>${escapeHtml(item.name || item.family || "unknown")}</strong>
      <p>${Math.round(Number(item.confidence || 0) * 100)}% - ${escapeHtml((item.methods || []).join(", ") || "cross-method evidence")}</p>
    </article>
  `).join("");
  const databaseHtml = Object.entries(databaseStatus || {}).map(([name, count]) => `
    <article class="candidate">
      <span>Fingerprint database</span>
      <strong>${escapeHtml(name)}</strong>
      <p>${Number(count || 0)} records</p>
    </article>
  `).join("");
  els.probabilityList.innerHTML = providerHtml + fingerprintHtml + databaseHtml;
}

function renderProbe(item) {
  const status = String(item.status || "");
  const cls = status === "pass" ? "status-ok" : status === "fail" ? "status-danger" : "status-warn";
  const sample = item.sample ? `<div class="probe-sample">Sample: ${escapeHtml(item.sample)}</div>` : "";
  return `
    <article class="probe">
      <div class="probe-head">
        <strong>${escapeHtml(item.category || "probe")} / ${escapeHtml(item.name || "probe")}</strong>
        <span class="probe-status ${cls}">${escapeHtml(status || "unknown")}</span>
      </div>
      <p>${escapeHtml(item.detail || "")}</p>
      ${sample}
    </article>
  `;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function loadStatus() {
  setMessage("");
  const data = await fetchJson("/status");
  renderStatus(data);
}

function buildDetectBody() {
  const mode = els.detectMode?.value || "astrbot";
  const direct = mode.startsWith("direct_openai");
  const full = mode.endsWith("_full") || direct;
  const body = { mode, full, fingerprint: full };
  if (!direct) return body;
  const baseUrl = els.directBaseUrl.value.trim();
  const apiKey = els.directApiKey.value.trim();
  const model = els.directModel.value.trim();
  if (!baseUrl || !apiKey || !model) {
    setMessage("Direct API mode requires Base URL, API Key, and Model.", "error");
    return null;
  }
  return { ...body, base_url: baseUrl, api_key: apiKey, model };
}

async function runDetection() {
  const body = buildDetectBody();
  if (!body) return;
  els.detectBtn.disabled = true;
  els.refreshBtn.disabled = true;
  setMessage(body.full ? "Running full audit with token-accounting and fingerprint probes." : "Running quick protocol audit.");
  try {
    const data = await fetchJson("/detect", { method: "POST", body: JSON.stringify(body) });
    renderReport(data.report);
    setMessage("Audit complete.");
  } catch (error) {
    setMessage(error.message || "Audit failed.", "error");
  } finally {
    els.detectBtn.disabled = false;
    els.refreshBtn.disabled = false;
    await loadStatus().catch(() => {});
  }
}

function syncModeFields() {
  const direct = (els.detectMode?.value || "astrbot").startsWith("direct_openai");
  if (els.directFields) els.directFields.hidden = !direct;
}

els.refreshBtn.addEventListener("click", () => loadStatus().catch((error) => setMessage(error.message || "Refresh failed.", "error")));
els.detectBtn.addEventListener("click", () => runDetection());
els.detectMode?.addEventListener("change", () => {
  syncModeFields();
  setMessage("");
});

syncModeFields();
loadStatus().catch((error) => setMessage(error.message || "Page initialization failed.", "error"));

