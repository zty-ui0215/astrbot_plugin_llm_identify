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
    enable_data_reporting: "Allow optional data reporting",
    data_reporting_settings: "Optional Data Reporting",
    data_reporting_hint: "Choose whether to show a voluntary prompt for sharing sanitized official-model fingerprint data after an eligible audit.",
    assistant_source: "Assistant model source",
    source_astrbot: "AstrBot connected model",
    source_openai: "OpenAI-compatible API",
    assistant_astrbot_model: "AstrBot auxiliary model",
    api_key_saved: "An API key is already saved. Leave the field blank to keep it.",
    api_key_placeholder: "Leave blank to keep saved key",
    close: "Close",
    aux_direct_required: "OpenAI-compatible auxiliary mode requires Base URL, API Key, and Model.",
    assistant_weights: "Auxiliary detection items and weights",
    aux_behavioral_style: "General answer style, hedging, verbosity, and formatting habits.",
    aux_reasoning_structure: "Reasoning organization, correction behavior, and final-answer discipline.",
    aux_knowledge_boundary_honesty: "Handling of uncertain or non-public facts without fabrication.",
    aux_safety_refusal_policy: "Benign-versus-risky boundaries and safe alternative style.",
    aux_format_instruction_following: "Compliance with JSON, CSV, length, and exact-output requirements.",
    aux_unicode_tokenization_artifacts: "Unicode, escaping, Markdown, and tokenizer-adjacent behavior.",
    aux_sampling_randomness_stability: "Repeated-output variability and deterministic constraints.",
    aux_scientific_probe_quality: "Quality of controlled, standards-aligned audit questions.",
    aux_routing_sidechannel_consistency: "Streaming, route stability, and inference-stack consistency.",
    aux_public_model_docs_match: "Fit with public model documentation and capability disclosures.",
    aux_label_behavioral_style: "Behavioral style", aux_label_reasoning_structure: "Reasoning structure",
    aux_label_knowledge_boundary_honesty: "Knowledge-boundary honesty", aux_label_safety_refusal_policy: "Safety refusal policy",
    aux_label_format_instruction_following: "Format instruction following", aux_label_unicode_tokenization_artifacts: "Unicode/tokenization artifacts",
    aux_label_sampling_randomness_stability: "Sampling stability", aux_label_scientific_probe_quality: "Scientific probe quality",
    aux_label_routing_sidechannel_consistency: "Routing consistency", aux_label_public_model_docs_match: "Public documentation match",
    contribution_title: "Voluntary official fingerprint contribution",
    contribution_hint: "We found that you are testing a model provided directly by an official platform. Would you like to share a sanitized data package to help us build a more complete official model fingerprint library?",
    push_contribution: "OK",
    not_now: "No, thanks",
    contribution_pushed: "Contribution page opened.",
    contribution_unavailable: "Run a full audit with an official API provider before contributing.",
    audit_running_elapsed: "Audit in progress, elapsed {seconds} seconds",
    stop_audit: "Stop",
    stop_confirm_title: "Stop the audit?",
    stop_confirm_hint: "All active audits will be terminated and unfinished data will be cleared.",
    cancel: "Cancel",
    confirm_stop: "Confirm stop",
    audit_stopped: "Audit stopped. Unfinished data was cleared.",
    stop_failed: "Failed to stop the audit."
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
    enable_data_reporting: "同意可选的数据上报",
    data_reporting_settings: "可选数据上报",
    data_reporting_hint: "选择是否在符合条件的检测完成后显示志愿分享脱敏官方模型指纹数据的提示。",
    assistant_source: "辅助模型来源",
    source_astrbot: "AstrBot 已接入模型",
    source_openai: "OpenAI 兼容协议 API",
    assistant_astrbot_model: "AstrBot 辅助模型",
    api_key_saved: "已保存 API Key。留空将继续使用已保存的 Key。",
    api_key_placeholder: "留空以继续使用已保存的 Key",
    close: "关闭",
    aux_direct_required: "OpenAI 兼容辅助模式需要填写 Base URL、API Key 和模型。",
    assistant_weights: "辅助检测项目和权重",
    aux_behavioral_style: "整体回答风格、保留措辞、详略程度和格式习惯。",
    aux_reasoning_structure: "推理组织、纠错行为和最终答案规范。",
    aux_knowledge_boundary_honesty: "对不确定或非公开事实的诚实处理，避免编造。",
    aux_safety_refusal_policy: "安全与风险边界的处理及安全替代方案风格。",
    aux_format_instruction_following: "对 JSON、CSV、长度和精确输出要求的遵循程度。",
    aux_unicode_tokenization_artifacts: "Unicode、转义、Markdown 及分词器相关行为。",
    aux_sampling_randomness_stability: "重复输出的变化程度和确定性约束表现。",
    aux_scientific_probe_quality: "生成受控、符合标准且有审计价值的问题的能力。",
    aux_routing_sidechannel_consistency: "流式输出、路由稳定性和推理栈一致性信号。",
    aux_public_model_docs_match: "与公开模型文档及能力说明的匹配程度。",
    aux_label_behavioral_style: "回答风格", aux_label_reasoning_structure: "推理结构",
    aux_label_knowledge_boundary_honesty: "知识边界诚实性", aux_label_safety_refusal_policy: "安全拒答策略",
    aux_label_format_instruction_following: "格式指令遵循", aux_label_unicode_tokenization_artifacts: "Unicode 与分词特征",
    aux_label_sampling_randomness_stability: "采样稳定性", aux_label_scientific_probe_quality: "科学探测质量",
    aux_label_routing_sidechannel_consistency: "路由一致性", aux_label_public_model_docs_match: "公开文档匹配度",
    contribution_title: "志愿上报官方模型指纹",
    contribution_hint: "我们发现您检测的是官方平台直接提供的模型。您是否愿意分享脱敏后的数据包，帮助我们建立更加完善的官方模型指纹库？",
    push_contribution: "好的",
    not_now: "不，谢谢",
    contribution_pushed: "已打开上报页面。",
    contribution_unavailable: "请先使用官方 API 提供商运行完整检测。",
    audit_running_elapsed: "审计正在进行，已持续 {seconds} 秒",
    stop_audit: "停止",
    stop_confirm_title: "是否停止运行",
    stop_confirm_hint: "确认后将强制停止所有审计并清除未完成的所有数据。",
    cancel: "取消",
    confirm_stop: "确认停止",
    audit_stopped: "审计已停止，未完成的数据已清除。",
    stop_failed: "停止审计失败。"
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
    enable_data_reporting: "任意のデータ提供に同意する",
    data_reporting_settings: "任意のデータ提供",
    data_reporting_hint: "対象となる監査の完了後に、サニタイズ済み公式モデル指紋データの任意提供を案内するかどうかを選択します。",
    assistant_source: "補助モデルのソース",
    source_astrbot: "AstrBot 接続済みモデル",
    source_openai: "OpenAI 互換 API",
    assistant_astrbot_model: "AstrBot 補助モデル",
    api_key_saved: "API Key は保存済みです。空欄のままにすると保存済みの Key を使用します。",
    api_key_placeholder: "空欄の場合は保存済みの Key を使用",
    close: "閉じる",
    aux_direct_required: "OpenAI 互換の補助モードでは Base URL、API Key、Model が必要です。",
    assistant_weights: "補助検出項目と重み",
    aux_behavioral_style: "回答全体のスタイル、留保表現、詳しさ、書式の傾向。",
    aux_reasoning_structure: "推論の構成、訂正動作、最終回答の規律。",
    aux_knowledge_boundary_honesty: "不確実または非公開の事実を捏造せずに扱う姿勢。",
    aux_safety_refusal_policy: "安全・危険の境界判断と安全な代替案の提示スタイル。",
    aux_format_instruction_following: "JSON、CSV、長さ、完全一致出力の指示への準拠。",
    aux_unicode_tokenization_artifacts: "Unicode、エスケープ、Markdown、トークナイザー関連の挙動。",
    aux_sampling_randomness_stability: "反復出力の変動性と決定的制約への対応。",
    aux_scientific_probe_quality: "統制され、標準に沿った監査質問を生成する能力。",
    aux_routing_sidechannel_consistency: "ストリーミング、経路安定性、推論スタックの一貫性。",
    aux_public_model_docs_match: "公開モデル文書および能力開示との一致度。",
    aux_label_behavioral_style: "回答スタイル", aux_label_reasoning_structure: "推論構造",
    aux_label_knowledge_boundary_honesty: "知識境界の誠実性", aux_label_safety_refusal_policy: "安全拒否ポリシー",
    aux_label_format_instruction_following: "書式指示への準拠", aux_label_unicode_tokenization_artifacts: "Unicode・トークン化特性",
    aux_label_sampling_randomness_stability: "サンプリング安定性", aux_label_scientific_probe_quality: "科学的プローブ品質",
    aux_label_routing_sidechannel_consistency: "ルーティング一貫性", aux_label_public_model_docs_match: "公開文書との一致度",
    contribution_title: "公式モデル指紋の任意提供",
    contribution_hint: "公式プラットフォームから直接提供されているモデルを検出していることが分かりました。公式モデル指紋ライブラリをより充実させるため、サニタイズ済みデータパッケージを共有しますか。",
    push_contribution: "はい",
    not_now: "いいえ、結構です",
    contribution_pushed: "送信ページを開きました。",
    contribution_unavailable: "提供前に公式 API プロバイダーで完全監査を実行してください。",
    audit_running_elapsed: "監査を実行中です。経過時間: {seconds} 秒",
    stop_audit: "停止",
    stop_confirm_title: "監査を停止しますか",
    stop_confirm_hint: "確認すると、実行中のすべての監査を強制終了し、未完了のデータを消去します。",
    cancel: "キャンセル",
    confirm_stop: "停止を確認",
    audit_stopped: "監査を停止し、未完了のデータを消去しました。",
    stop_failed: "監査を停止できませんでした。"
  }
};
let bridgeReadyPromise = null;
let languageManuallySelected = readLanguageManualFlag();
let currentLanguage = normalizeLanguage(readStoredLanguage() || document.documentElement.lang || "en-US");
let lastStatusData = null;
let currentContribution = null;
let auditStartedAt = null;
let auditElapsedTimer = null;
let auditStatusPoller = null;
let auditStatusPollBusy = false;
let auditStopRequested = false;

const els = {
  normalPanel: document.getElementById("normalPanel"),
  auditRunningView: document.getElementById("auditRunningView"),
  auditElapsedText: document.getElementById("auditElapsedText"),
  stopAuditBtn: document.getElementById("stopAuditBtn"),
  stopConfirmModal: document.getElementById("stopConfirmModal"),
  closeStopConfirmBtn: document.getElementById("closeStopConfirmBtn"),
  cancelStopBtn: document.getElementById("cancelStopBtn"),
  confirmStopBtn: document.getElementById("confirmStopBtn"),
  languageSelect: document.getElementById("languageSelect"),
  auditTabBtn: document.getElementById("auditTabBtn"),
  settingsTabBtn: document.getElementById("settingsTabBtn"),
  auditView: document.getElementById("auditView"),
  settingsView: document.getElementById("settingsView"),
  astrbotProviderField: document.getElementById("astrbotProviderField"),
  astrbotProvider: document.getElementById("astrbotProvider"),
  auxEnabled: document.getElementById("auxEnabled"),
  dataReportConsent: document.getElementById("dataReportConsent"),
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
  closeContributionBtn: document.getElementById("closeContributionBtn"),
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
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = text(node.dataset.i18nPlaceholder, node.placeholder);
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => {
    node.setAttribute("aria-label", text(node.dataset.i18nAriaLabel, node.getAttribute("aria-label") || ""));
  });
  if (els.languageSelect) els.languageSelect.value = currentLanguage;
  updateAuditElapsedText();
}

function updateAuditElapsedText() {
  if (!els.auditElapsedText) return;
  const startedAt = Number(auditStartedAt || Date.now() / 1000);
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - startedAt));
  els.auditElapsedText.textContent = text("audit_running_elapsed").replace("{seconds}", String(seconds));
}

function setAuditRunning(running, startedAt = null) {
  const active = Boolean(running);
  if (els.normalPanel) els.normalPanel.hidden = active;
  if (els.auditRunningView) els.auditRunningView.hidden = !active;
  if (active) {
    const serverStartedAt = Number(startedAt || 0);
    if (serverStartedAt > 0) auditStartedAt = serverStartedAt;
    else if (!auditStartedAt) auditStartedAt = Math.floor(Date.now() / 1000);
    updateAuditElapsedText();
    if (!auditElapsedTimer) auditElapsedTimer = window.setInterval(updateAuditElapsedText, 1000);
    if (!auditStatusPoller) auditStatusPoller = window.setInterval(pollAuditStatus, 2000);
    return;
  }
  auditStartedAt = null;
  if (auditElapsedTimer) window.clearInterval(auditElapsedTimer);
  if (auditStatusPoller) window.clearInterval(auditStatusPoller);
  auditElapsedTimer = null;
  auditStatusPoller = null;
}

async function pollAuditStatus() {
  if (auditStatusPollBusy) return;
  auditStatusPollBusy = true;
  try {
    await loadStatus({ preserveMessage: true });
  } catch (error) {
    // A transient status failure must not replace the running screen.
  } finally {
    auditStatusPollBusy = false;
  }
}

function showStopConfirmModal() {
  if (els.stopConfirmModal) els.stopConfirmModal.hidden = false;
}

function hideStopConfirmModal() {
  if (els.stopConfirmModal) els.stopConfirmModal.hidden = true;
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
  setAuditRunning(data.running, data.audit_started_at);
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
  if (els.dataReportConsent) els.dataReportConsent.checked = Boolean(config.enable_voluntary_data_reporting);
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
    const itemId = String(item.id || "");
    const itemLabel = text(`aux_label_${itemId}`, itemId || text("unknown"));
    const description = text(`aux_${itemId}`, item.description || "");
    return `
      <article class="weight-item">
        <strong>${escapeHtml(itemLabel)}<span>${weight}%</span></strong>
        <p>${escapeHtml(description)}</p>
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
  els.contributionText.textContent = text("contribution_hint");
  if (els.pushContributionBtn) els.pushContributionBtn.dataset.issueUrl = contribution.issue_url || "";
}

function hideContributionModal() {
  if (els.contributionModal) els.contributionModal.hidden = true;
}

window.hideContributionModal = hideContributionModal;

function handleContributionModalClick(event) {
  const target = event.target;
  if (!(target instanceof Element)) return;
  if (target.closest("#closeContributionBtn") || target.closest("#dismissContributionBtn")) {
    event.preventDefault();
    event.stopPropagation();
    hideContributionModal();
    return;
  }
  if (target.closest("#pushContributionBtn")) {
    event.preventDefault();
    event.stopPropagation();
    pushContribution();
  }
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

async function loadStatus(options = {}) {
  if (!options.preserveMessage) setMessage("");
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
  hideStopConfirmModal();
  auditStopRequested = false;
  setAuditRunning(true, Math.floor(Date.now() / 1000));
  els.detectBtn.disabled = true;
  els.refreshBtn.disabled = true;
  body.language = currentLanguage;
  let completed = false;
  let reportCreatedAt = null;
  let detectedContribution = null;
  setMessage(body.full ? text("running_full") : text("running_quick"));
  try {
    const data = await fetchJson("/detect", { method: "POST", body: JSON.stringify(body) });
    renderReport(data.report);
    reportCreatedAt = data.report?.created_at || null;
    detectedContribution = data.contribution || null;
    completed = true;
    setMessage(text("audit_complete"));
  } catch (error) {
    if (!auditStopRequested) setMessage(error.message || text("audit_failed"), "error");
  } finally {
    els.detectBtn.disabled = false;
    els.refreshBtn.disabled = false;
    const status = await loadStatus({ preserveMessage: auditStopRequested }).catch(() => null);
    if (completed && shouldShowContributionModal(detectedContribution, reportCreatedAt, { trustCurrentResponse: true })) {
      showContributionModal(detectedContribution);
    } else if (completed && shouldShowContributionModal(status?.contribution, reportCreatedAt)) {
      showContributionModal(status.contribution);
    }
  }
}

async function stopAudit() {
  auditStopRequested = true;
  if (els.stopAuditBtn) els.stopAuditBtn.disabled = true;
  if (els.confirmStopBtn) els.confirmStopBtn.disabled = true;
  try {
    await fetchJson("/stop", { method: "POST", body: JSON.stringify({}) });
    hideStopConfirmModal();
    setAuditRunning(false);
    await loadStatus({ preserveMessage: true }).catch(() => null);
    setMessage(text("audit_stopped"));
  } catch (error) {
    auditStopRequested = false;
    hideStopConfirmModal();
    setMessage(error.message || text("stop_failed"), "error");
    await loadStatus({ preserveMessage: true }).catch(() => null);
  } finally {
    if (els.stopAuditBtn) els.stopAuditBtn.disabled = false;
    if (els.confirmStopBtn) els.confirmStopBtn.disabled = false;
  }
}

function shouldShowContributionModal(contribution, reportCreatedAt, options = {}) {
  if (!contribution?.available || !contribution?.enabled) return false;
  if (options.trustCurrentResponse) return true;
  if (!reportCreatedAt) return false;
  const contributionCreatedAt = Number(contribution.report_created_at || 0);
  const detectedCreatedAt = Number(reportCreatedAt || 0);
  if (!contributionCreatedAt || !detectedCreatedAt) return false;
  return Math.abs(contributionCreatedAt - detectedCreatedAt) <= 1;
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
    enable_voluntary_data_reporting: Boolean(els.dataReportConsent?.checked),
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

window.pushContribution = pushContribution;

els.languageSelect?.addEventListener("change", () => setLanguage(els.languageSelect.value, { manual: true }));
els.auditTabBtn?.addEventListener("click", () => switchView("audit"));
els.settingsTabBtn?.addEventListener("click", () => switchView("settings"));
els.astrbotProvider?.addEventListener("change", () => loadStatus().catch((error) => setMessage(error.message || text("refresh_failed"), "error")));
els.refreshBtn.addEventListener("click", () => loadStatus().catch((error) => setMessage(error.message || text("refresh_failed"), "error")));
els.detectBtn.addEventListener("click", () => runDetection());
els.saveSettingsBtn?.addEventListener("click", () => saveSettings());
els.stopAuditBtn?.addEventListener("click", () => showStopConfirmModal());
els.closeStopConfirmBtn?.addEventListener("click", () => hideStopConfirmModal());
els.cancelStopBtn?.addEventListener("click", () => hideStopConfirmModal());
els.confirmStopBtn?.addEventListener("click", () => stopAudit());
els.dismissContributionBtn?.addEventListener("click", (event) => {
  event.stopPropagation();
  hideContributionModal();
});
els.closeContributionBtn?.addEventListener("click", (event) => {
  event.stopPropagation();
  hideContributionModal();
});
els.pushContributionBtn?.addEventListener("click", (event) => {
  event.stopPropagation();
  pushContribution();
});
els.contributionModal?.addEventListener("click", (event) => handleContributionModalClick(event));
document.addEventListener("click", (event) => {
  if (!els.contributionModal || els.contributionModal.hidden) return;
  handleContributionModalClick(event);
}, true);
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

