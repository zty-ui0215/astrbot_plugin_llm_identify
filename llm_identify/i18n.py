from __future__ import annotations

from typing import Any

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en-US": {
        "token.usage_availability.ok": "Usage metadata is available on most token probes.",
        "token.usage_availability.bad": "Usage metadata is missing on most token probes.",
        "token.input_monotonicity.ok": "Reported input tokens increase with controlled prompt length.",
        "token.input_monotonicity.bad": "Reported input tokens do not increase with controlled prompt length.",
        "token.slope_plausibility.ok": "Reported input token slope broadly tracks local estimates.",
        "token.slope_plausibility.bad": "Reported input token slope is implausible relative to local estimates.",
        "token.constant_count_anomaly.ok": "Reported input token counts vary across varied prompts.",
        "token.constant_count_anomaly.bad": "Reported input token counts are constant or nearly constant.",
        "token.unicode_count_stability.ok": "Unicode edge prompts produce plausible token counts.",
        "token.unicode_count_stability.bad": "Unicode edge prompts produce missing or implausible token counts.",
        "token.output_length_consistency.ok": "Output token counts track short versus long responses when exposed.",
        "token.output_length_consistency.bad": "Output token counts do not track short versus long responses.",
        "token.cache_signal_consistency.neutral": "Cache metadata was not exposed; repeated-prefix counts are treated as neutral.",
        "token.cache_signal_consistency.ok": "Repeated-prefix cache/token signal is plausible.",
        "token.cache_signal_consistency.bad": "Repeated-prefix cache/token signal is inconsistent.",
        "token.token_truth_score.detail": "Token audit score synthesized from usage availability, monotonicity, slope, cache, Unicode, and output-length evidence.",
        "protocol.minimal_completion_contract.ok": "The endpoint followed independent exact-output probes.",
        "protocol.minimal_completion_contract.bad": "The endpoint failed or wrapped at least one exact-output probe.",
        "protocol.json_contract.ok": "The endpoint returned strict parseable JSON.",
        "protocol.json_contract.bad": "The endpoint wrapped, malformed, or changed the requested JSON payload.",
        "protocol.usage_surface.ok": "At least one protocol probe exposed token usage metadata.",
        "protocol.usage_surface.bad": "Protocol probes did not expose usage metadata through the current adapter.",
        "branch.output_statistics": "output_statistics branch score {score:.0%} with missingness {missingness:.0%}.",
        "branch.context_truth": "context_truth branch score {score:.0%} with missingness {missingness:.0%}.",
        "branch.timing": "timing branch score {score:.0%} with missingness {missingness:.0%}.",
        "branch.prompt_injection": "prompt_injection branch score {score:.0%} with missingness {missingness:.0%}.",
        "branch.tool_calling": "tool_calling branch score {score:.0%} with missingness {missingness:.0%}.",
        "branch.token_authenticity": "token_authenticity branch score {score:.0%} with missingness {missingness:.0%}.",
        "fingerprint.cross_validate.ok": "Fingerprint methods cross-validate around {family}.",
        "fingerprint.cross_validate.bad": "Fingerprint methods do not cross-validate strongly enough for a high-confidence identity claim.",
        "fingerprint.disagreement.bad": "Fingerprint disagreement suggests possible wrapping, mixed routing, or spoofing.",
        "fingerprint.trusted_corpus.ok": "Trusted reference corpus contributed {count} attributed model or family records.",
        "fingerprint.public_database.ok": "Public fingerprint baseline database contributed {count} model candidates.",
        "fingerprint.empty_database.bad": "One or more optional fingerprint databases are empty; rule-only scoring was used for those methods.",
        "fingerprint.openai_like": "OpenAI-like behavior cluster",
        "fingerprint.anthropic_like": "Anthropic-like behavior cluster",
        "fingerprint.google_like": "Google/Gemini-like behavior cluster",
        "fingerprint.open_source_or_relay": "Open-source or relay-shaped cluster",
        "fingerprint.unknown": "Unknown behavior cluster",
    },
    "zh-CN": {
        "token.usage_availability.ok": "大多数 Token 探测暴露了可用的元数据。",
        "token.usage_availability.bad": "大多数 Token 探测未暴露可用的元数据。",
        "token.input_monotonicity.ok": "报告的输入 Token 数会随受控提示长度增加。",
        "token.input_monotonicity.bad": "报告的输入 Token 数未随受控提示长度增加。",
        "token.slope_plausibility.ok": "报告的输入 Token 斜率大体符合本地估计。",
        "token.slope_plausibility.bad": "报告的输入 Token 斜率相对于本地估计不合理。",
        "token.constant_count_anomaly.ok": "不同提示下报告的输入 Token 数存在变化。",
        "token.constant_count_anomaly.bad": "报告的输入 Token 数保持恒定或近似恒定。",
        "token.unicode_count_stability.ok": "Unicode 边界提示给出合理的 Token 数。",
        "token.unicode_count_stability.bad": "Unicode 边界提示返回缺失或不合理的 Token 数。",
        "token.output_length_consistency.ok": "在暴露输出 Token 时，短长响应的计数会对应变化。",
        "token.output_length_consistency.bad": "输出 Token 数不会随短长响应变化。",
        "token.cache_signal_consistency.neutral": "未暴露缓存元数据；重复前缀计数视为中性。",
        "token.cache_signal_consistency.ok": "重复前缀的缓存/Token 信号看起来合理。",
        "token.cache_signal_consistency.bad": "重复前缀的缓存/Token 信号不一致。",
        "token.token_truth_score.detail": "Token 审计得分综合了元数据可用性、单调性、斜率、缓存、Unicode 和输出长度证据。",
        "protocol.minimal_completion_contract.ok": "端点通过了独立的精确输出探测。",
        "protocol.minimal_completion_contract.bad": "端点未通过至少一个精确输出探测，或对其进行了包装。",
        "protocol.json_contract.ok": "端点返回了可严格解析的 JSON。",
        "protocol.json_contract.bad": "端点包装、损坏或修改了请求的 JSON 载荷。",
        "protocol.usage_surface.ok": "至少一个协议探测暴露了 Token 使用元数据。",
        "protocol.usage_surface.bad": "当前适配器下的协议探测未暴露使用元数据。",
        "branch.output_statistics": "output_statistics 分支得分 {score:.0%}，缺失率 {missingness:.0%}。",
        "branch.context_truth": "context_truth 分支得分 {score:.0%}，缺失率 {missingness:.0%}。",
        "branch.timing": "timing 分支得分 {score:.0%}，缺失率 {missingness:.0%}。",
        "branch.prompt_injection": "prompt_injection 分支得分 {score:.0%}，缺失率 {missingness:.0%}。",
        "branch.tool_calling": "tool_calling 分支得分 {score:.0%}，缺失率 {missingness:.0%}。",
        "branch.token_authenticity": "token_authenticity 分支得分 {score:.0%}，缺失率 {missingness:.0%}。",
        "fingerprint.cross_validate.ok": "指纹方法围绕 {family} 形成交叉验证。",
        "fingerprint.cross_validate.bad": "指纹方法的交叉验证强度不足，无法支持高置信度身份判断。",
        "fingerprint.disagreement.bad": "指纹分歧暗示可能存在包装、混合路由或伪装。",
        "fingerprint.trusted_corpus.ok": "可信参考语料贡献了 {count} 条带归属的模型或家族记录。",
        "fingerprint.public_database.ok": "公共指纹基线数据库贡献了 {count} 个模型候选。",
        "fingerprint.empty_database.bad": "一个或多个可选指纹数据库为空；这些方法仅使用规则得分。",
        "fingerprint.openai_like": "OpenAI 风格行为簇",
        "fingerprint.anthropic_like": "Anthropic 风格行为簇",
        "fingerprint.google_like": "Google/Gemini 风格行为簇",
        "fingerprint.open_source_or_relay": "开源或中转形态簇",
        "fingerprint.unknown": "未知行为簇",
    },
}


def _normalize(language: str | None) -> str:
    value = str(language or "").strip().lower().replace("_", "-")
    return "zh-CN" if value in {"zh", "zh-cn", "zh-hans", "cn", "chinese"} else "en-US"


def t(key: str, language: str | None = None, **kwargs: Any) -> str:
    lang = _normalize(language)
    value = _TRANSLATIONS.get(lang, {}).get(key) or _TRANSLATIONS["en-US"].get(key) or key
    if kwargs:
        try:
            return value.format(**kwargs)
        except Exception:
            return value
    return value
