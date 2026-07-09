const HTTP_API = "/astrbot_plugin_llm_identify/page";
const PAGE_ENDPOINT_PREFIX = "page";
const LANGUAGE_KEY = "llmIdentifyLanguage";
const LANGUAGE_MANUAL_KEY = "llmIdentifyLanguageManual";
const LANGUAGES = ["en-US", "zh-CN", "ja-JP"];
const PAGE_TEXT = {
  "en-US": {
    unknown: "unknown", idle: "idle", running: "running", none: "none", pass: "pass", fail: "fail", warning: "warning",
    response_not_json: "Response is not JSON",
    bridge_unavailable: "AstrBot page bridge is unavailable. Open this page from the AstrBot plugin extension page.",
    request_failed: "Request failed",
    confidence: "Confidence",
    no_findings: "No major findings.",
    score_protocol: "Protocol",
    score_token_truth: "Token Truth",
    score_fingerprint: "Fingerprint",
    score_spoofing: "Spoofing",
    score_proxy: "Proxy",
    score_mixture: "Mixture",
    provider_probability: "Provider probability",
    fingerprint_candidate: "Fingerprint candidate",
    fingerprint_database: "Fingerprint database",
    cross_method_evidence: "cross-method evidence",
    records: "records",
    sample: "Sample",
    direct_required: "Direct API mode requires Base URL, API Key, and Model.",
    running_full: "Running full audit with token-accounting and fingerprint probes.",
    running_quick: "Running quick protocol audit.",
    audit_complete: "Audit complete.",
    audit_failed: "Audit failed.",
    refresh_failed: "Refresh failed.",
    init_failed: "Page initialization failed.",
    eyebrow: "LLM IDENTIFY",
    heading: "Endpoint Audit",
    refresh: "Refresh",
    provider: "Provider",
    claimed_model: "Claimed Model",
    family_guess: "Family Guess",
    state: "State",
    risk: "Risk",
    run_audit: "Run Audit",
    run_hint: "Quick mode checks protocol behavior. Full mode adds token-accounting and fingerprint evidence.",
    run: "Run",
    audit_mode: "Audit mode",
    mode_astrbot: "AstrBot Provider - Quick",
    mode_astrbot_full: "AstrBot Provider - Full Fingerprint",
    mode_direct: "Direct OpenAI-compatible - Full Fingerprint",
    astrbot_provider: "AstrBot model",
    no_models: "No AstrBot models available",
    base_url: "Base URL",
    api_key: "API Key",
    model: "Model",
    audit_result: "Audit Result",
    primary_findings: "Primary Findings",
    text_report: "Text report",
    audit_tab: "Audit",
    settings_tab: "Settings",
    assistant_settings: "LLM-assisted Detection Model",
    assistant_settings_hint: "Choose an auxiliary judge model for deep fingerprint matching.",
    save_settings: "Save",
    settings_saved: "Settings saved.",
    settings_failed: "Settings save failed.",
    enable_auxiliary_judge: "Enable auxiliary LLM judge",
    assistant_source: "Assistant model source",
    source_astrbot: "AstrBot connected model",
    source_openai: "OpenAI-compatible API",
    assistant_astrbot_model: "AstrBot auxiliary model",
    api_key_saved: "An API key is already saved. Leave the field blank to keep it.",
    aux_direct_required: "OpenAI-compatible auxiliary mode requires Base URL, API Key, and Model.",
    assistant_weights: "Auxiliary detection items and weights",
    contribution_title: "Voluntary official fingerprint contribution",
    contribution_hint: "A sanitized candidate package is available for this official endpoint audit.",
    push_contribution: "Submit",
    not_now: "Not now",
    contribution_pushed: "Contribution page opened.",
    contribution_unavailable: "Run a full direct audit against an official API before contributing."
  },
  "zh-CN": {
    unknown: "未知", idle: "空闲", running: "运行中", none: "无", pass: "通过", fail: "失败", warning: "警告",
    response_not_json: "响应不是 JSON",
    bridge_unavailable: "AstrBot 页面桥不可用。请从 AstrBot 插件扩展页打开此页面。",
    request_failed: "请求失败",
    confidence: "置信度",
    no_findings: "未发现主要问题。",
    score_protocol: "协议",
    score_token_truth: "Token 真实性",
    score_fingerprint: "指纹",
    score_spoofing: "伪装",
    score_proxy: "代理",
    score_mixture: "混合",
    provider_probability: "提供商概率",
    fingerprint_candidate: "指纹候选",
    fingerprint_database: "指纹数据库",
    cross_method_evidence: "跨方法证据",
    records: "条记录",
    sample: "样例",
    direct_required: "直连 API 模式需要 Base URL、API Key 和模型。",
    running_full: "正在运行完整审计，包含 Token 计量和指纹探测。",
    running_quick: "正在运行快速协议审计。",
    audit_complete: "审计完成。",
    audit_failed: "审计失败。",
    refresh_failed: "刷新失败。",
    init_failed: "页面初始化失败。",
    eyebrow: "LLM 识别",
    heading: "端点审计",
    refresh: "刷新",
    provider: "提供商",
    claimed_model: "声明模型",
    family_guess: "家族推断",
    state: "状态",
    risk: "风险",
    run_audit: "运行审计",
    run_hint: "快速模式检查协议行为；完整模式会加入 Token 计量和指纹证据。",
    run: "运行",
    audit_mode: "审计模式",
    mode_astrbot: "AstrBot 提供商 - 快速",
    mode_astrbot_full: "AstrBot 提供商 - 完整指纹",
    mode_direct: "直连 OpenAI 兼容端点 - 完整指纹",
    astrbot_provider: "AstrBot 模型",
    no_models: "没有可用的 AstrBot 模型",
    base_url: "Base URL",
    api_key: "API Key",
    model: "模型",
    audit_result: "审计结果",
    primary_findings: "主要发现",
    text_report: "文本报告",
    audit_tab: "检测",
    settings_tab: "设置",
    assistant_settings: "LLM 辅助检测模型",
    assistant_settings_hint: "选择用于深度指纹匹配的辅助判断模型。",
    save_settings: "保存",
    settings_saved: "设置已保存。",
    settings_failed: "设置保存失败。",
    enable_auxiliary_judge: "启用辅助 LLM 判断",
    assistant_source: "辅助模型来源",
    source_astrbot: "AstrBot 已接入模型",
    source_openai: "OpenAI 兼容协议 API",
    assistant_astrbot_model: "AstrBot 辅助模型",
    api_key_saved: "已保存 API Key。留空将继续使用已保存的 Key。",
    aux_direct_required: "OpenAI 兼容辅助模式需要填写 Base URL、API Key 和模型。",
    assistant_weights: "辅助检测项目和权重",
    contribution_title: "志愿上报官方模型指纹",
    contribution_hint: "检测到官方 API，本次检测已生成脱敏模型指纹候选包。是否一键提交到志愿库？",
    push_contribution: "一键上报",
    not_now: "暂不",
    contribution_pushed: "已打开上报页面。",
    contribution_unavailable: "请先对官方 API 运行完整直连检测。"
  },
  "ja-JP": {
    unknown: "不明", idle: "待機中", running: "実行中", none: "なし", pass: "合格", fail: "失敗", warning: "警告",
    response_not_json: "応答は JSON ではありません",
    bridge_unavailable: "AstrBot ページブリッジを利用できません。AstrBot プラグイン拡張ページから開いてください。",
    request_failed: "リクエストに失敗しました",
    confidence: "信頼度",
    no_findings: "主要な検出事項はありません。",
    score_protocol: "プロトコル",
    score_token_truth: "Token 真実性",
    score_fingerprint: "指紋",
    score_spoofing: "偽装",
    score_proxy: "プロキシ",
    score_mixture: "混在",
    provider_probability: "プロバイダー確率",
    fingerprint_candidate: "指紋候補",
    fingerprint_database: "指紋データベース",
    cross_method_evidence: "手法横断の証拠",
    records: "件",
    sample: "サンプル",
    direct_required: "直接 API モードには Base URL、API Key、モデルが必要です。",
    running_full: "Token 計量と指紋プローブを含む完全監査を実行中です。",
    running_quick: "簡易プロトコル監査を実行中です。",
    audit_complete: "監査が完了しました。",
    audit_failed: "監査に失敗しました。",
    refresh_failed: "更新に失敗しました。",
    init_failed: "ページ初期化に失敗しました。",
    eyebrow: "LLM IDENTIFY",
    heading: "エンドポイント監査",
    refresh: "更新",
    provider: "プロバイダー",
    claimed_model: "主張モデル",
    family_guess: "ファミリー推定",
    state: "状態",
    risk: "リスク",
    run_audit: "監査を実行",
    run_hint: "簡易モードはプロトコル挙動を確認します。完全モードは Token 計量と指紋証拠を追加します。",
    run: "実行",
    audit_mode: "監査モード",
    mode_astrbot: "AstrBot プロバイダー - 簡易",
    mode_astrbot_full: "AstrBot プロバイダー - 完全指紋",
    mode_direct: "直接 OpenAI 互換 - 完全指紋",
    astrbot_provider: "AstrBot モデル",
    no_models: "利用可能な AstrBot モデルがありません",
    base_url: "Base URL",
    api_key: "API Key",
    model: "モデル",
    audit_result: "監査結果",
    primary_findings: "主要な検出事項",
    text_report: "テキストレポート",
    audit_tab: "監査",
    settings_tab: "設定",
    assistant_settings: "LLM 補助検出モデル",
    assistant_settings_hint: "詳細なフィンガープリント照合に使う補助判定モデルを選択します。",
    save_settings: "保存",
    settings_saved: "設定を保存しました。",
    settings_failed: "設定の保存に失敗しました。",
    enable_auxiliary_judge: "補助 LLM 判定を有効にする",
    assistant_source: "補助モデルのソース",
    source_astrbot: "AstrBot 接続済みモデル",
    source_openai: "OpenAI 互換 API",
    assistant_astrbot_model: "AstrBot 補助モデル",
    api_key_saved: "API Key は保存済みです。空欄のままにすると保存済みの Key を使用します。",
    aux_direct_required: "OpenAI 互換の補助モードでは Base URL、API Key、Model が必要です。",
    assistant_weights: "補助検出項目と重み",
    contribution_title: "公式モデル指紋の任意提供",
    contribution_hint: "公式 API が検出され、この監査からサニタイズ済みモデル指紋候補パッケージを生成しました。任意リポジトリへ送信しますか。",
    push_contribution: "ワンクリック送信",
    not_now: "後で",
    contribution_pushed: "送信ページを開きました。",
    contribution_unavailable: "提供前に公式 API への完全な直接監査を実行してください。"
  }
};
let bridgeReadyPromise = null;
let languageManuallySelected = readLanguageManualFlag();
let currentLanguage = normalizeLanguage(readStoredLanguage() || document.documentElement.lang || "en-US");
let lastStatusData = null;
let currentContribution = null;

const els = {
  languageSelect: document.getElementById("languageSelect"),
  auditTabBtn: document.getElementById("auditTabBtn"),
  settingsTabBtn: document.getElementById("settingsTabBtn"),
  auditView: document.getElementById("auditView"),
  settingsView: document.getElementById("settingsView"),
  astrbotProviderField: document.getElementById("astrbotProviderField"),
  astrbotProvider: document.getElementById("astrbotProvider"),
  auxEnabled: document.getElementById("auxEnabled"),
  auxMode: document.getElementById("auxMode"),
  auxProvider: document.getElementById("auxProvider"),
  auxAstrbotField: document.getElementById("auxAstrbotField"),
  auxOpenaiFields: document.getElementById("auxOpenaiFields"),
  auxBaseUrl: document.getElementById("auxBaseUrl"),
  auxApiKey: document.getElementById("auxApiKey"),
  auxModel: document.getElementById("auxModel"),
  saveSettingsBtn: document.getElementById("saveSettingsBtn"),
  settingsSavedKey: document.getElementById("settingsSavedKey"),
  auxWeightList: document.getElementById("auxWeightList"),
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
  contributionModal: document.getElementById("contributionModal"),
  contributionText: document.getElementById("contributionText"),
  dismissContributionBtn: document.getElementById("dismissContributionBtn"),
  pushContributionBtn: document.getElementById("pushContributionBtn"),
  probeList: document.getElementById("probeList"),
  rawReport: document.getElementById("rawReport"),
};

function readStoredLanguage() {
  try {
    return window.localStorage?.getItem(LANGUAGE_KEY);
  } catch (error) {
    return "";
  }
}

function readLanguageManualFlag() {
  try {
    return window.localStorage?.getItem(LANGUAGE_MANUAL_KEY) === "1";
  } catch (error) {
    return false;
  }
}

function writeStoredLanguage(language) {
  try {
    window.localStorage?.setItem(LANGUAGE_KEY, language);
  } catch (error) {
    // Storage may be unavailable in embedded plugin iframes.
  }
}

function writeLanguageManualFlag(value) {
  try {
    if (value) window.localStorage?.setItem(LANGUAGE_MANUAL_KEY, "1");
    else window.localStorage?.removeItem(LANGUAGE_MANUAL_KEY);
  } catch (error) {
    // Storage may be unavailable in embedded plugin iframes.
  }
}

function normalizeLanguage(value) {
  const normalized = String(value || "").trim().toLowerCase().replace("_", "-");
  if (["zh", "zh-cn", "zh-hans", "cn", "chinese", "中文"].includes(normalized)) return "zh-CN";
  if (["ja", "ja-jp", "jp", "japanese", "日本語"].includes(normalized)) return "ja-JP";
  return "en-US";
}

function text(key, fallback = "") {
  return PAGE_TEXT[currentLanguage]?.[key] || PAGE_TEXT["en-US"][key] || fallback || key;
}

function setLanguage(language, options = {}) {
  currentLanguage = normalizeLanguage(language);
  if (options.manual) {
    languageManuallySelected = true;
    writeLanguageManualFlag(true);
    writeStoredLanguage(currentLanguage);
  } else if (!languageManuallySelected) {
    writeStoredLanguage(currentLanguage);
  }
  document.documentElement.lang = currentLanguage;
  renderStaticText();
  if (currentContribution && els.contributionModal && !els.contributionModal.hidden) updateContributionModalText(currentContribution);
  if (lastStatusData) renderStatus(lastStatusData);
  if (!options.skipReload) loadStatus().catch((error) => setMessage(error.message || text("refresh_failed"), "error"));
}

function renderStaticText() {
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.dataset.i18n;
    node.textContent = text(key, node.textContent);
  });
  if (els.languageSelect) els.languageSelect.value = currentLanguage;
}

async function initHostLanguage() {
  const bridge = await waitForBridge().catch(() => getBridge());
  if (bridge && typeof bridge.ready === "function") {
    try {
      await bridge.ready();
    } catch (error) {
      // Continue with the best available bridge context.
    }
  }
  if (!languageManuallySelected) {
    const hostLanguage = detectHostLanguage(bridge);
    setLanguage(hostLanguage, { skipReload: true });
  }
  if (bridge && typeof bridge.onContext === "function") {
    try {
      bridge.onContext(() => {
        if (!languageManuallySelected) setLanguage(detectHostLanguage(bridge), { skipReload: false });
        else renderStaticText();
      });
    } catch (error) {
      // Older AstrBot builds may not expose context callbacks.
    }
  }
}

function detectHostLanguage(bridge) {
  const context = readBridgeContext(bridge);
  const candidates = [
    context?.locale,
    context?.language,
    context?.lang,
    context?.i18n?.locale,
    context?.webui?.locale,
    document.documentElement.lang,
  ];
  for (const candidate of candidates) {
    const normalized = normalizeLanguage(candidate);
    if (normalized !== "en-US" || String(candidate || "").toLowerCase().startsWith("en")) return normalized;
  }
  if (bridge && typeof bridge.t === "function") {
    try {
      const translated = bridge.t("pages.模型检测面板.language", "Language");
      if (translated === "语言") return "zh-CN";
      if (translated === "言語") return "ja-JP";
    } catch (error) {
      return "en-US";
    }
  }
  return "en-US";
}

function readBridgeContext(bridge) {
  if (!bridge) return null;
  for (const key of ["context", "ctx", "pluginContext"]) {
    const value = bridge[key];
    if (value && typeof value === "object") return value;
  }
  for (const key of ["getContext", "getCurrentContext"]) {
    if (typeof bridge[key] === "function") {
      try {
        const value = bridge[key]();
        if (value && typeof value === "object" && typeof value.then !== "function") return value;
      } catch (error) {
        return null;
      }
    }
  }
  return null;
}

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
    const responseText = await response.text();
    try {
      payload = responseText ? JSON.parse(responseText) : {};
    } catch (error) {
      throw new Error(response.ok ? text("response_not_json") : `HTTP ${response.status}: ${responseText.slice(0, 160)}`);
    }
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  } else {
    throw new Error(text("bridge_unavailable"));
  }
  payload = normalizeResponse(payload);
  if (!payload.success) throw new Error(payload.error || text("request_failed"));
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
  lastStatusData = data;
  els.providerId.textContent = data.provider_id || text("unknown");
  els.claimedModel.textContent = data.claimed_model || text("unknown");
  els.modelFamily.textContent = data.model_family_guess || text("unknown");
  els.runningState.textContent = data.running ? text("running") : text("idle");
  renderProviderOptions(data.providers || [], data.provider_id);
  renderSettings(data.config || {}, data.providers || []);
  renderReport(data.last_report);
}

function renderProviderOptions(providers, selectedProviderId, selectEl = els.astrbotProvider) {
  if (!selectEl) return;
  const selected = selectEl.value || selectedProviderId || "";
  const items = Array.isArray(providers) ? providers : [];
  if (!items.length) {
    selectEl.innerHTML = `<option value="">${escapeHtml(text("no_models"))}</option>`;
    selectEl.disabled = true;
    return;
  }
  selectEl.disabled = false;
  selectEl.innerHTML = items.map((item) => {
    const id = String(item.id || "");
    const label = String(item.label || item.model || id || text("unknown"));
    return `<option value="${escapeHtml(id)}">${escapeHtml(label)}</option>`;
  }).join("");
  selectEl.value = items.some((item) => String(item.id || "") === selected) ? selected : String(items[0].id || "");
}

function renderSettings(config, providers) {
  if (!els.auxMode) return;
  els.auxEnabled.checked = Boolean(config.enable_auxiliary_llm_judge);
  els.auxMode.value = config.auxiliary_judge_mode || "astrbot";
  renderProviderOptions(providers, config.auxiliary_judge_provider_id || config.page_provider_id || "", els.auxProvider);
  els.auxBaseUrl.value = config.auxiliary_judge_base_url || "";
  els.auxModel.value = config.auxiliary_judge_model || "";
  els.auxApiKey.value = "";
  if (els.settingsSavedKey) els.settingsSavedKey.hidden = !config.auxiliary_judge_has_api_key;
  renderAuxWeights(config.auxiliary_judge_items || []);
  syncAuxModeFields();
}

function renderAuxWeights(items) {
  if (!els.auxWeightList) return;
  const list = Array.isArray(items) ? items : [];
  els.auxWeightList.innerHTML = list.map((item) => {
    const weight = Math.round(Number(item.weight || 0) * 100);
    return `
      <article class="weight-item">
        <strong>${escapeHtml(item.id || text("unknown"))}<span>${weight}%</span></strong>
        <p>${escapeHtml(item.description || "")}</p>
      </article>
    `;
  }).join("");
}

function renderReport(report) {
  if (!report) {
    els.reportPanel.hidden = true;
    els.riskLevel.textContent = text("none");
    return;
  }
  els.reportPanel.hidden = false;
  els.riskLevel.textContent = localizeValue(report.risk_level || "unknown");
  els.claimedModel.textContent = report.claimed_model || text("unknown");
  els.modelFamily.textContent = report.model_family_guess || text("unknown");
  els.confidenceBadge.textContent = `${text("confidence")} ${Math.round(Number(report.confidence || 0) * 100)}%`;
  els.findingsSummary.textContent = (report.findings || [text("no_findings")]).slice(0, 2).join(" ");
  els.reportTime.textContent = report.created_at ? new Date(report.created_at * 1000).toLocaleString() : "";
  els.rawReport.textContent = report.text || "";
  renderScores(report);
  renderProbabilities(report.provider_probabilities || {}, report.fingerprint_candidates || [], report.fingerprint_database_status || {});
  const results = Array.isArray(report.probe_results) ? report.probe_results : [];
  els.probeList.innerHTML = results.map(renderProbe).join("");
}

function renderScores(report) {
  const items = [
    [text("score_protocol"), report.protocol_score],
    [text("score_token_truth"), report.token_truth_score],
    [text("score_fingerprint"), report.fingerprint_confidence],
    [text("score_spoofing"), report.spoofing_risk],
    [text("score_proxy"), report.proxy_probability],
    [text("score_mixture"), report.mixture_probability],
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
      <span>${escapeHtml(text("provider_probability"))}</span>
      <strong>${escapeHtml(name)}</strong>
      <p>${Math.round(Number(value || 0) * 100)}%</p>
    </article>
  `).join("");
  const fingerprintHtml = (fingerprintCandidates || []).map((item) => `
    <article class="candidate">
      <span>${escapeHtml(text("fingerprint_candidate"))}</span>
      <strong>${escapeHtml(item.name || item.family || text("unknown"))}</strong>
      <p>${Math.round(Number(item.confidence || 0) * 100)}% - ${escapeHtml((item.methods || []).join(", ") || text("cross_method_evidence"))}</p>
    </article>
  `).join("");
  const databaseHtml = Object.entries(databaseStatus || {}).map(([name, count]) => `
    <article class="candidate">
      <span>${escapeHtml(text("fingerprint_database"))}</span>
      <strong>${escapeHtml(name)}</strong>
      <p>${Number(count || 0)} ${escapeHtml(text("records"))}</p>
    </article>
  `).join("");
  els.probabilityList.innerHTML = providerHtml + fingerprintHtml + databaseHtml;
}

function renderProbe(item) {
  const status = String(item.status || "");
  const cls = status === "pass" ? "status-ok" : status === "fail" ? "status-danger" : "status-warn";
  const sample = item.sample ? `<div class="probe-sample">${escapeHtml(text("sample"))}: ${escapeHtml(item.sample)}</div>` : "";
  return `
    <article class="probe">
      <div class="probe-head">
        <strong>${escapeHtml(item.category || "probe")} / ${escapeHtml(item.name || "probe")}</strong>
        <span class="probe-status ${cls}">${escapeHtml(localizeValue(status || "unknown"))}</span>
      </div>
      <p>${escapeHtml(item.detail || "")}</p>
      ${sample}
    </article>
  `;
}

function showContributionModal(contribution) {
  if (!els.contributionModal || !contribution?.available) return;
  currentContribution = contribution;
  updateContributionModalText(contribution);
  els.contributionModal.hidden = false;
}

function updateContributionModalText(contribution) {
  if (!els.contributionText) return;
  const endpoint = contribution.endpoint || {};
  const provider = endpoint.provider || text("unknown");
  const host = endpoint.host || "";
  els.contributionText.textContent = `${text("contribution_hint")} ${provider} ${host}`.trim();
  if (els.pushContributionBtn) els.pushContributionBtn.dataset.issueUrl = contribution.issue_url || "";
}

function hideContributionModal() {
  if (els.contributionModal) els.contributionModal.hidden = true;
}

function localizeValue(value) {
  return text(String(value || "").toLowerCase(), value);
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
  const providerId = els.astrbotProvider?.value || "";
  const query = new URLSearchParams({ language: currentLanguage });
  if (providerId) query.set("provider_id", providerId);
  const data = await fetchJson(`/status?${query.toString()}`);
  renderStatus(data);
  return data;
}

function buildDetectBody() {
  const mode = els.detectMode?.value || "astrbot";
  const direct = mode.startsWith("direct_openai");
  const full = mode.endsWith("_full") || direct;
  const body = { mode, full, fingerprint: full };
  if (!direct) return { ...body, provider_id: els.astrbotProvider?.value || "" };
  const baseUrl = els.directBaseUrl.value.trim();
  const apiKey = els.directApiKey.value.trim();
  const model = els.directModel.value.trim();
  if (!baseUrl || !apiKey || !model) {
    setMessage(text("direct_required"), "error");
    return null;
  }
  return { ...body, base_url: baseUrl, api_key: apiKey, model, language: currentLanguage };
}

async function runDetection() {
  const body = buildDetectBody();
  if (!body) return;
  hideContributionModal();
  els.detectBtn.disabled = true;
  els.refreshBtn.disabled = true;
  body.language = currentLanguage;
  let completed = false;
  setMessage(body.full ? text("running_full") : text("running_quick"));
  try {
    const data = await fetchJson("/detect", { method: "POST", body: JSON.stringify(body) });
    renderReport(data.report);
    completed = true;
    setMessage(text("audit_complete"));
  } catch (error) {
    setMessage(error.message || text("audit_failed"), "error");
  } finally {
    els.detectBtn.disabled = false;
    els.refreshBtn.disabled = false;
    const status = await loadStatus().catch(() => null);
    if (completed && status?.contribution?.available) showContributionModal(status.contribution);
  }
}

function syncModeFields() {
  const direct = (els.detectMode?.value || "astrbot").startsWith("direct_openai");
  if (els.directFields) els.directFields.hidden = !direct;
  if (els.astrbotProviderField) els.astrbotProviderField.hidden = direct;
}

function syncAuxModeFields() {
  const direct = (els.auxMode?.value || "astrbot") === "openai_compatible";
  if (els.auxOpenaiFields) els.auxOpenaiFields.hidden = !direct;
  if (els.auxAstrbotField) els.auxAstrbotField.hidden = direct;
}

function switchView(view) {
  const settings = view === "settings";
  if (els.auditView) els.auditView.hidden = settings;
  if (els.settingsView) els.settingsView.hidden = !settings;
  els.auditTabBtn?.classList.toggle("active", !settings);
  els.settingsTabBtn?.classList.toggle("active", settings);
}

function buildSettingsBody() {
  const mode = els.auxMode?.value || "astrbot";
  const body = {
    enable_auxiliary_llm_judge: Boolean(els.auxEnabled?.checked),
    auxiliary_judge_mode: mode,
    auxiliary_judge_provider_id: els.auxProvider?.value || "",
    auxiliary_judge_base_url: els.auxBaseUrl?.value.trim() || "",
    auxiliary_judge_api_key: els.auxApiKey?.value.trim() || "",
    auxiliary_judge_model: els.auxModel?.value.trim() || "",
  };
  if (body.enable_auxiliary_llm_judge && mode === "openai_compatible") {
    const hasSavedKey = lastStatusData?.config?.auxiliary_judge_has_api_key;
    if (!body.auxiliary_judge_base_url || (!body.auxiliary_judge_api_key && !hasSavedKey) || !body.auxiliary_judge_model) {
      setMessage(text("aux_direct_required"), "error");
      return null;
    }
  }
  return body;
}

async function saveSettings() {
  const body = buildSettingsBody();
  if (!body) return;
  els.saveSettingsBtn.disabled = true;
  setMessage("");
  try {
    await fetchJson("/settings", { method: "POST", body: JSON.stringify(body) });
    await loadStatus();
    setMessage(text("settings_saved"));
  } catch (error) {
    setMessage(error.message || text("settings_failed"), "error");
  } finally {
    els.saveSettingsBtn.disabled = false;
  }
}

async function pushContribution() {
  const popup = window.open("about:blank", "_blank");
  if (popup) popup.opener = null;
  try {
    const data = await fetchJson("/contribution", { method: "POST", body: JSON.stringify({ action: "push" }) });
    const url = data.issue_url || els.pushContributionBtn?.dataset.issueUrl || currentContribution?.issue_url || "";
    if (!url) throw new Error(text("contribution_unavailable"));
    if (popup) popup.location.href = url;
    else window.open(url, "_blank", "noopener,noreferrer");
    hideContributionModal();
    setMessage(text("contribution_pushed"));
  } catch (error) {
    try {
      popup?.close();
    } catch (closeError) {
      // Ignore popup cleanup failures.
    }
    setMessage(error.message || text("contribution_unavailable"), "error");
  }
}

els.languageSelect?.addEventListener("change", () => setLanguage(els.languageSelect.value, { manual: true }));
els.auditTabBtn?.addEventListener("click", () => switchView("audit"));
els.settingsTabBtn?.addEventListener("click", () => switchView("settings"));
els.astrbotProvider?.addEventListener("change", () => loadStatus().catch((error) => setMessage(error.message || text("refresh_failed"), "error")));
els.refreshBtn.addEventListener("click", () => loadStatus().catch((error) => setMessage(error.message || text("refresh_failed"), "error")));
els.detectBtn.addEventListener("click", () => runDetection());
els.saveSettingsBtn?.addEventListener("click", () => saveSettings());
els.dismissContributionBtn?.addEventListener("click", () => hideContributionModal());
els.pushContributionBtn?.addEventListener("click", () => pushContribution());
els.auxMode?.addEventListener("change", () => syncAuxModeFields());
els.detectMode?.addEventListener("change", () => {
  syncModeFields();
  setMessage("");
});

initHostLanguage().finally(() => {
  renderStaticText();
  syncModeFields();
  syncAuxModeFields();
  loadStatus().catch((error) => setMessage(error.message || text("init_failed"), "error"));
});

