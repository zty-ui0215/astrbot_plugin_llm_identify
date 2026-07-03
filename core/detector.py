from __future__ import annotations

import json
import re
import time
from collections.abc import Awaitable, Callable

from .models import DetectionReport, ModelCandidate, ModelReply, ProbeResult


GenerateFn = Callable[..., Awaitable[ModelReply]]


class LLMDetector:
    def __init__(
        self,
        generate: GenerateFn,
        *,
        provider_id: str,
        claimed_model: str = "unknown",
        enable_protocol_probe: bool = True,
        enable_token_probe: bool = True,
        enable_fingerprint_probe: bool = True,
        strict_mode: bool = False,
    ) -> None:
        self.generate = generate
        self.provider_id = provider_id or "unknown"
        self.claimed_model = claimed_model or "unknown"
        self.model_family = _detect_model_family(self.claimed_model, self.provider_id)
        self.protocol_profile = _protocol_profile_for_family(self.model_family)
        self.enable_protocol_probe = enable_protocol_probe
        self.enable_token_probe = enable_token_probe
        self.enable_fingerprint_probe = enable_fingerprint_probe
        self.strict_mode = strict_mode

    async def run(self) -> DetectionReport:
        results: list[ProbeResult] = []
        if self.enable_protocol_probe:
            results.extend(await self._run_protocol_probes())
        if self.enable_token_probe:
            results.extend(await self._run_token_probes())
        if self.enable_fingerprint_probe:
            results.extend(await self._run_fingerprint_probes())
        return self._build_report(results)

    async def _run_protocol_probes(self) -> list[ProbeResult]:
        if self.model_family == "claude":
            return await self._run_claude_protocol_probes()
        if self.model_family == "openai":
            return await self._run_openai_protocol_probes()
        if self.model_family == "gemini":
            return await self._run_gemini_protocol_probes()

        results: list[ProbeResult] = []

        marker_a = await self.generate("Reply with exactly this marker and nothing else: LLMID_PROTOCOL_A")
        marker_b = await self.generate("Reply with exactly this marker and nothing else: LLMID_PROTOCOL_B")
        marker_a_ok = marker_a.text.strip() == "LLMID_PROTOCOL_A"
        marker_b_ok = marker_b.text.strip() == "LLMID_PROTOCOL_B"
        results.append(
            ProbeResult(
                category="protocol",
                name="minimal_completion_contract",
                score=_score_bool_pair(marker_a_ok, marker_b_ok, partial=0.55),
                status=_status(_score_bool_pair(marker_a_ok, marker_b_ok, partial=0.55)),
                detail=(
                    "Provider follows two independent exact-output minimal completion probes."
                    if marker_a_ok and marker_b_ok
                    else "Provider failed at least one exact-output minimal completion probe."
                ),
                sample=_shorten(f"A={marker_a.text!r}; B={marker_b.text!r}"),
                evidence={"first": _reply_evidence(marker_a), "second": _reply_evidence(marker_b)},
            )
        )

        json_reply = await self.generate('Return JSON only, no markdown: {"answer":410,"ok":true,"items":[1,2,3]}')
        parsed = _try_parse_json_object(json_reply.text)
        json_exact = json_reply.text.strip().startswith("{") and json_reply.text.strip().endswith("}")
        json_ok = bool(parsed and parsed.get("answer") == 410 and parsed.get("ok") is True and parsed.get("items") == [1, 2, 3])
        results.append(
            ProbeResult(
                category="protocol",
                name="json_mode_compatibility",
                score=1.0 if json_ok and json_exact else (0.45 if json_ok else 0.2),
                status=_status(1.0 if json_ok and json_exact else (0.45 if json_ok else 0.2)),
                detail=(
                    "Provider can return strict parseable JSON without wrapper text."
                    if json_ok and json_exact
                    else "Provider returned wrapper text or malformed/mismatched JSON."
                ),
                sample=_shorten(json_reply.text),
                evidence={**_reply_evidence(json_reply), "parsed_json": parsed or None},
            )
        )

        shape_score, shape_detail, shape_evidence = _response_shape_score(marker_a, self.claimed_model)
        results.append(
            ProbeResult(
                category="protocol",
                name="raw_response_shape",
                score=shape_score,
                status=_status(shape_score),
                detail=shape_detail,
                evidence=shape_evidence,
            )
        )

        usage_score, usage_detail, usage_evidence = _protocol_usage_score(marker_a, json_reply)
        results.append(
            ProbeResult(
                category="protocol",
                name="usage_contract",
                score=usage_score,
                status=_status(usage_score),
                detail=usage_detail,
                evidence=usage_evidence,
            )
        )

        parameter_result = await self._run_parameter_control_probe()
        results.append(parameter_result)

        consistency_score, consistency_detail, consistency_evidence = _protocol_consistency_score(marker_a, marker_b)
        results.append(
            ProbeResult(
                category="protocol",
                name="multi_call_consistency",
                score=consistency_score,
                status=_status(consistency_score),
                detail=consistency_detail,
                evidence=consistency_evidence,
            )
        )
        return results

    async def _run_claude_protocol_probes(self, seed_probe: ModelReply | None = None, seed_expected: str | None = None) -> list[ProbeResult]:
        results: list[ProbeResult] = []
        expected = seed_expected or "LLMID_CLAUDE_PROTOCOL"
        marker = seed_probe or await self.generate(f"Reply with exactly this marker and nothing else: {expected}")
        marker_ok = marker.text.strip() == expected
        marker_score = 1.0 if marker_ok else 0.35
        results.append(
            ProbeResult(
                category="protocol",
                name="claude_minimal_message_contract",
                score=marker_score,
                status=_status(marker_score),
                detail="Claude message call follows exact-output contract." if marker_ok else "Claude message call failed exact-output contract.",
                sample=_shorten(marker.text),
                evidence=_reply_evidence(marker),
            )
        )
        results.append(await self._run_claude_thinking_signature_probe())
        shape_score, shape_detail, shape_evidence = _claude_response_shape_score(marker, self.claimed_model)
        results.append(
            ProbeResult(
                category="protocol",
                name="claude_message_shape",
                score=shape_score,
                status=_status(shape_score),
                detail=shape_detail,
                evidence=shape_evidence,
            )
        )
        usage_score, usage_detail, usage_evidence = _claude_usage_baseline_score(marker)
        results.append(
            ProbeResult(
                category="protocol",
                name="claude_usage_baseline",
                score=usage_score,
                status=_status(usage_score),
                detail=usage_detail,
                evidence=usage_evidence,
            )
        )
        results.append(_claude_tool_use_id_surface(marker))
        results.append(_claude_stream_surface(marker))
        return results

    async def _run_openai_protocol_probes(self, seed_probe: ModelReply | None = None, seed_expected: str | None = None) -> list[ProbeResult]:
        results: list[ProbeResult] = []

        marker_a_expected = seed_expected or "LLMID_OPENAI_PROTOCOL_A"
        marker_a = seed_probe or await self.generate(f"Reply with exactly this marker and nothing else: {marker_a_expected}")
        marker_b = await self.generate("Reply with exactly this marker and nothing else: LLMID_OPENAI_PROTOCOL_B")
        marker_a_ok = marker_a.text.strip() == marker_a_expected
        marker_b_ok = marker_b.text.strip() == "LLMID_OPENAI_PROTOCOL_B"
        marker_score = _score_bool_pair(marker_a_ok, marker_b_ok, partial=0.55)
        results.append(
            ProbeResult(
                category="protocol",
                name="openai_minimal_chat_contract",
                score=marker_score,
                status=_status(marker_score),
                detail="OpenAI chat completion follows independent exact-output probes." if marker_a_ok and marker_b_ok else "OpenAI chat completion failed at least one exact-output probe.",
                sample=_shorten(f"A={marker_a.text!r}; B={marker_b.text!r}"),
                evidence={"first": _reply_evidence(marker_a), "second": _reply_evidence(marker_b)},
            )
        )

        shape_score, shape_detail, shape_evidence = _openai_response_shape_score(marker_a, self.claimed_model)
        results.append(
            ProbeResult(
                category="protocol",
                name="openai_chat_completion_shape",
                score=shape_score,
                status=_status(shape_score),
                detail=shape_detail,
                sample=_openai_shape_sample(shape_evidence),
                evidence=shape_evidence,
            )
        )

        usage_score, usage_detail, usage_evidence = _openai_usage_baseline_score(marker_a, marker_b)
        results.append(
            ProbeResult(
                category="protocol",
                name="openai_usage_shape",
                score=usage_score,
                status=_status(usage_score),
                detail=usage_detail,
                evidence=usage_evidence,
            )
        )

        results.append(await self._run_openai_json_schema_probe())
        results.append(await self._run_openai_tool_call_probe())
        results.append(await self._run_openai_stream_consistency_probe(marker_a))
        return results

    async def _run_gemini_protocol_probes(self, seed_probe: ModelReply | None = None, seed_expected: str | None = None) -> list[ProbeResult]:
        results: list[ProbeResult] = []

        marker_a_expected = seed_expected or "LLMID_GEMINI_PROTOCOL_A"
        marker_a = seed_probe or await self.generate(f"Reply with exactly this marker and nothing else: {marker_a_expected}")
        marker_b = await self.generate("Reply with exactly this marker and nothing else: LLMID_GEMINI_PROTOCOL_B")
        marker_a_ok = marker_a.text.strip() == marker_a_expected
        marker_b_ok = marker_b.text.strip() == "LLMID_GEMINI_PROTOCOL_B"
        marker_score = _score_bool_pair(marker_a_ok, marker_b_ok, partial=0.55)
        results.append(
            ProbeResult(
                category="protocol",
                name="gemini_minimal_generate_content_contract",
                score=marker_score,
                status=_status(marker_score),
                detail="Gemini generateContent follows independent exact-output probes." if marker_a_ok and marker_b_ok else "Gemini generateContent failed at least one exact-output probe.",
                sample=_shorten(f"A={marker_a.text!r}; B={marker_b.text!r}"),
                evidence={"first": _reply_evidence(marker_a), "second": _reply_evidence(marker_b)},
            )
        )

        shape_score, shape_detail, shape_evidence = _gemini_response_shape_score(marker_a, self.claimed_model)
        results.append(
            ProbeResult(
                category="protocol",
                name="gemini_generate_content_shape",
                score=shape_score,
                status=_status(shape_score),
                detail=shape_detail,
                sample=_gemini_shape_sample(shape_evidence),
                evidence=shape_evidence,
            )
        )

        usage_score, usage_detail, usage_evidence = _gemini_usage_baseline_score(marker_a, marker_b)
        results.append(
            ProbeResult(
                category="protocol",
                name="gemini_usage_metadata",
                score=usage_score,
                status=_status(usage_score),
                detail=usage_detail,
                evidence=usage_evidence,
            )
        )

        results.append(await self._run_gemini_structured_output_probe())
        results.append(await self._run_gemini_function_call_probe())
        results.append(await self._run_gemini_stream_surface_probe(marker_a))
        return results

    async def _run_gemini_structured_output_probe(self) -> ProbeResult:
        prompt = "Return JSON only with answer=410, ok=true, and items=[1,2,3]."
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "integer"},
                "ok": {"type": "boolean"},
                "items": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["answer", "ok", "items"],
        }
        try:
            reply = await self.generate(prompt, generation_config={"responseMimeType": "application/json", "responseSchema": schema})
        except TypeError:
            reply = await self.generate(prompt)
            parsed = _try_parse_json_object(reply.text)
            score = 0.45 if _openai_schema_payload_ok(parsed) else 0.2
            return ProbeResult(
                category="protocol",
                name="gemini_structured_output_contract",
                score=score,
                status=_status(score),
                detail="Adapter rejected Gemini generationConfig response schema; fallback JSON text is not a strict structured-output contract.",
                sample=_shorten(reply.text),
                evidence={**_reply_evidence(reply), "parsed_json": parsed or None, "parameter_supported": False},
            )
        except Exception as exc:
            return ProbeResult(
                category="protocol",
                name="gemini_structured_output_contract",
                score=0.2,
                status="异常",
                detail=f"Gemini structured-output request failed: {type(exc).__name__}: {exc}",
                evidence={"error_type": type(exc).__name__, "error": str(exc), "parameter_supported": False},
            )

        parsed = _try_parse_json_object(reply.text)
        payload_ok = _openai_schema_payload_ok(parsed)
        exact_json = reply.text.strip().startswith("{") and reply.text.strip().endswith("}")
        score = 1.0 if payload_ok and exact_json else (0.55 if payload_ok else 0.25)
        return ProbeResult(
            category="protocol",
            name="gemini_structured_output_contract",
            score=score,
            status=_status(score),
            detail="Gemini structured output returns strict parseable JSON." if score >= 0.8 else "Gemini structured-output probe returned wrapper text, mismatched payload, or ignored schema controls.",
            sample=_shorten(reply.text),
            evidence={**_reply_evidence(reply), "parsed_json": parsed or None, "parameter_supported": True},
        )

    async def _run_gemini_function_call_probe(self) -> ProbeResult:
        function_declaration = {
            "name": "llmid_report_probe",
            "description": "Return the probe marker through a function call.",
            "parameters": {
                "type": "object",
                "properties": {"marker": {"type": "string"}},
                "required": ["marker"],
            },
        }
        try:
            reply = await self.generate(
                "Call llmid_report_probe with marker exactly LLMID_GEMINI_FUNCTION_OK. Do not answer in plain text.",
                tools=[{"functionDeclarations": [function_declaration]}],
                tool_config={"functionCallingConfig": {"mode": "ANY", "allowedFunctionNames": ["llmid_report_probe"]}},
            )
        except TypeError:
            return ProbeResult(
                category="protocol",
                name="gemini_function_call_contract",
                score=0.25,
                status="异常",
                detail="Adapter rejected Gemini tools/toolConfig parameters; likely simplified text interface or incomplete compatibility layer.",
                evidence={"parameter_supported": False},
            )
        except Exception as exc:
            return ProbeResult(
                category="protocol",
                name="gemini_function_call_contract",
                score=0.2,
                status="异常",
                detail=f"Gemini function-call request failed: {type(exc).__name__}: {exc}",
                evidence={"error_type": type(exc).__name__, "error": str(exc), "parameter_supported": False},
            )

        meta = reply.meta or {}
        function_names = [str(item) for item in (meta.get("function_call_names") or []) if item]
        part_types = [str(item) for item in (meta.get("part_types") or []) if item]
        checks = {
            "has_function_call_part": "functionCall" in part_types,
            "function_name_matches": "llmid_report_probe" in function_names,
            "not_plain_text_marker": "LLMID_GEMINI_FUNCTION_OK" not in reply.text,
        }
        score = sum(1 for ok in checks.values() if ok) / len(checks)
        detail = "Gemini function calling exposes functionCall part with expected function name." if score >= 0.8 else "Gemini function calling surface is missing, normalized, or returned as plain text."
        return ProbeResult(
            category="protocol",
            name="gemini_function_call_contract",
            score=round(score, 4),
            status=_status(score),
            detail=detail,
            sample=_shorten(reply.text),
            evidence={**_reply_evidence(reply), "checks": checks},
        )

    async def _run_gemini_stream_surface_probe(self, baseline: ModelReply) -> ProbeResult:
        try:
            stream_reply = await self.generate("Reply with exactly this marker and nothing else: LLMID_GEMINI_STREAM", stream=True)
        except TypeError:
            return ProbeResult(
                category="protocol",
                name="gemini_stream_generate_content_surface",
                score=0.45,
                status="异常",
                detail="Adapter rejected stream=True; streamGenerateContent baseline is not observable and may be hidden by a wrapper layer.",
                evidence={"parameter_supported": False, "baseline": _reply_evidence(baseline)},
            )
        except Exception as exc:
            return ProbeResult(
                category="protocol",
                name="gemini_stream_generate_content_surface",
                score=0.35,
                status="异常",
                detail=f"Gemini stream request failed: {type(exc).__name__}: {exc}",
                evidence={"error_type": type(exc).__name__, "error": str(exc), "parameter_supported": False},
            )

        baseline_meta = baseline.meta or {}
        stream_meta = stream_reply.meta or {}
        checks = {
            "stream_text_matches": stream_reply.text.strip() == "LLMID_GEMINI_STREAM",
            "same_model_version_or_model": bool((baseline_meta.get("modelVersion") or baseline_meta.get("model")) and (baseline_meta.get("modelVersion") or baseline_meta.get("model")) == (stream_meta.get("modelVersion") or stream_meta.get("model"))),
            "stream_has_candidates": int(stream_meta.get("candidates_count") or 0) > 0,
            "stream_usage_visible_or_deferred": bool(stream_reply.usage or stream_meta.get("raw_usage")),
        }
        score = sum(1 for ok in checks.values() if ok) / len(checks)
        detail = "Gemini stream and non-stream calls expose consistent generateContent metadata." if score >= 0.8 else "Gemini stream/non-stream metadata is incomplete or hidden by the adapter."
        return ProbeResult(
            category="protocol",
            name="gemini_stream_generate_content_surface",
            score=round(score, 4),
            status=_status(score),
            detail=detail,
            sample=_shorten(stream_reply.text),
            evidence={"checks": checks, "baseline": _reply_evidence(baseline), "stream": _reply_evidence(stream_reply)},
        )

    async def _run_openai_json_schema_probe(self) -> ProbeResult:
        prompt = "Return a JSON object with answer=410, ok=true, and items=[1,2,3]. Do not add prose."
        schema = {
            "name": "llmid_schema_probe",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "answer": {"type": "integer"},
                    "ok": {"type": "boolean"},
                    "items": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["answer", "ok", "items"],
            },
        }
        try:
            reply = await self.generate(prompt, response_format={"type": "json_schema", "json_schema": schema})
        except TypeError:
            reply = await self.generate(prompt)
            parsed = _try_parse_json_object(reply.text)
            score = 0.45 if _openai_schema_payload_ok(parsed) else 0.2
            return ProbeResult(
                category="protocol",
                name="openai_json_schema_contract",
                score=score,
                status=_status(score),
                detail="Adapter rejected OpenAI json_schema parameter; fallback JSON text is not a strict schema contract.",
                sample=_shorten(reply.text),
                evidence={**_reply_evidence(reply), "parsed_json": parsed or None, "parameter_supported": False},
            )
        except Exception as exc:
            return ProbeResult(
                category="protocol",
                name="openai_json_schema_contract",
                score=0.2,
                status="异常",
                detail=f"OpenAI json_schema request failed: {type(exc).__name__}: {exc}",
                evidence={"error_type": type(exc).__name__, "error": str(exc), "parameter_supported": False},
            )

        parsed = _try_parse_json_object(reply.text)
        payload_ok = _openai_schema_payload_ok(parsed)
        exact_json = reply.text.strip().startswith("{") and reply.text.strip().endswith("}")
        score = 1.0 if payload_ok and exact_json else (0.55 if payload_ok else 0.25)
        return ProbeResult(
            category="protocol",
            name="openai_json_schema_contract",
            score=score,
            status=_status(score),
            detail="OpenAI json_schema response is strict parseable JSON." if score >= 0.8 else "JSON schema probe returned wrapper text, mismatched payload, or ignored schema controls.",
            sample=_shorten(reply.text),
            evidence={**_reply_evidence(reply), "parsed_json": parsed or None, "parameter_supported": True},
        )

    async def _run_openai_tool_call_probe(self) -> ProbeResult:
        tool = {
            "type": "function",
            "function": {
                "name": "llmid_report_probe",
                "description": "Return the probe marker through a tool call.",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"marker": {"type": "string"}},
                    "required": ["marker"],
                },
            },
        }
        try:
            reply = await self.generate(
                "Call the llmid_report_probe tool with marker exactly LLMID_TOOLCALL_OK. Do not answer in plain text.",
                tools=[tool],
                tool_choice={"type": "function", "function": {"name": "llmid_report_probe"}},
            )
        except TypeError:
            return ProbeResult(
                category="protocol",
                name="openai_tool_call_contract",
                score=0.25,
                status="异常",
                detail="Adapter rejected OpenAI tools/tool_choice parameters; likely simplified text interface or incomplete compatibility layer.",
                evidence={"parameter_supported": False},
            )
        except Exception as exc:
            return ProbeResult(
                category="protocol",
                name="openai_tool_call_contract",
                score=0.2,
                status="异常",
                detail=f"OpenAI tool-call request failed: {type(exc).__name__}: {exc}",
                evidence={"error_type": type(exc).__name__, "error": str(exc), "parameter_supported": False},
            )

        meta = reply.meta or {}
        tool_call_count = int(meta.get("tool_call_count") or 0)
        tool_call_ids = [str(item) for item in (meta.get("tool_call_ids") or []) if item]
        tool_call_types = [str(item) for item in (meta.get("tool_call_types") or []) if item]
        tool_function_names = [str(item) for item in (meta.get("tool_function_names") or []) if item]
        finish_reason = str(meta.get("finish_reason") or "")
        checks = {
            "has_tool_call": tool_call_count > 0,
            "has_tool_id": bool(tool_call_ids),
            "tool_type_function": bool(tool_call_types) and all(item == "function" for item in tool_call_types),
            "function_name_matches": "llmid_report_probe" in tool_function_names,
            "finish_reason_tool_calls": finish_reason == "tool_calls",
        }
        score = sum(1 for ok in checks.values() if ok) / len(checks)
        if not checks["has_tool_call"] and "LLMID_TOOLCALL_OK" in reply.text:
            score = min(score, 0.35)
        detail = "OpenAI tool call surface exposes tool ids, function type, function name, and tool_calls finish_reason." if score >= 0.8 else "Tool call surface is missing, normalized, or returned as plain text."
        return ProbeResult(
            category="protocol",
            name="openai_tool_call_contract",
            score=round(score, 4),
            status=_status(score),
            detail=detail,
            sample=_shorten(reply.text),
            evidence={**_reply_evidence(reply), "checks": checks},
        )

    async def _run_openai_stream_consistency_probe(self, baseline: ModelReply) -> ProbeResult:
        try:
            stream_reply = await self.generate("Reply with exactly this marker and nothing else: LLMID_OPENAI_STREAM", stream=True)
        except TypeError:
            return ProbeResult(
                category="protocol",
                name="openai_stream_nonstream_consistency",
                score=0.45,
                status="异常",
                detail="Adapter rejected stream=True; stream/non-stream baseline is not observable and may be hidden by a wrapper layer.",
                evidence={"parameter_supported": False, "baseline": _reply_evidence(baseline)},
            )
        except Exception as exc:
            return ProbeResult(
                category="protocol",
                name="openai_stream_nonstream_consistency",
                score=0.35,
                status="异常",
                detail=f"OpenAI stream request failed: {type(exc).__name__}: {exc}",
                evidence={"error_type": type(exc).__name__, "error": str(exc), "parameter_supported": False},
            )

        events = [str(item) for item in ((stream_reply.meta or {}).get("sse_event_types") or []) if item]
        baseline_meta = baseline.meta or {}
        stream_meta = stream_reply.meta or {}
        checks = {
            "stream_text_matches": stream_reply.text.strip() == "LLMID_OPENAI_STREAM",
            "same_model_field": bool(baseline_meta.get("model") and baseline_meta.get("model") == stream_meta.get("model")),
            "stream_has_response_id": bool(stream_reply.response_id or stream_meta.get("id")),
            "stream_usage_visible_or_deferred": bool(stream_reply.usage or stream_meta.get("raw_usage") or events),
        }
        score = sum(1 for ok in checks.values() if ok) / len(checks)
        if not events:
            score = min(score, 0.72)
        detail = "OpenAI stream and non-stream calls expose consistent metadata." if score >= 0.8 else "Stream/non-stream metadata is incomplete or hidden by the adapter."
        return ProbeResult(
            category="protocol",
            name="openai_stream_nonstream_consistency",
            score=round(score, 4),
            status=_status(score),
            detail=detail,
            sample=_shorten(stream_reply.text),
            evidence={"checks": checks, "sse_event_types": events, "baseline": _reply_evidence(baseline), "stream": _reply_evidence(stream_reply)},
        )

    async def _run_claude_thinking_signature_probe(self) -> ProbeResult:
        prompt = (
            "Use extended thinking if available, then answer exactly: LLMID_CLAUDE_THINKING_OK. "
            "Do not add any other visible text."
        )
        try:
            reply = await self.generate(prompt, thinking={"type": "enabled", "budget_tokens": 1024})
        except Exception as exc:
            return ProbeResult(
                category="protocol",
                name="claude_thinking_signature",
                score=0.25,
                status="异常",
                detail=f"Thinking request failed or was rejected: {type(exc).__name__}: {exc}",
                evidence={"error_type": type(exc).__name__, "error": str(exc)},
            )

        signatures = _claude_signatures(reply)
        answer_ok = "LLMID_CLAUDE_THINKING_OK" in reply.text.strip()
        if signatures and answer_ok:
            score = 1.0
            detail = "Claude thinking block exposes server-encrypted signature."
        elif signatures:
            score = 0.85
            detail = "Claude thinking signature exists, but visible answer did not strictly match probe."
        elif answer_ok:
            score = 0.45
            detail = "Visible answer succeeded, but no thinking signature was exposed through AstrBot/provider."
        else:
            score = 0.25
            detail = "No Claude thinking signature and visible answer did not match probe."

        evidence = _reply_evidence(reply)
        evidence["signatures"] = signatures
        return ProbeResult(
            category="protocol",
            name="claude_thinking_signature",
            score=score,
            status=_status(score),
            detail=detail,
            sample=_shorten(reply.text),
            evidence=evidence,
        )

    async def _run_parameter_control_probe(self) -> ProbeResult:
        prompt = "Output exactly: LLMID_PARAM_ALPHA_STOP_BETA"
        try:
            reply = await self.generate(prompt, stop=["_STOP_"])
        except TypeError:
            reply = await self.generate(prompt)
            return ProbeResult(
                category="protocol",
                name="parameter_control",
                score=0.35,
                status="异常",
                detail="Provider adapter rejected stop parameter, so API parameter compatibility is weak.",
                sample=_shorten(reply.text),
                evidence=_reply_evidence(reply),
            )
        except Exception as exc:
            return ProbeResult(
                category="protocol",
                name="parameter_control",
                score=0.2,
                status="异常",
                detail=f"Provider failed when stop parameter was supplied: {type(exc).__name__}: {exc}",
                evidence={"error_type": type(exc).__name__, "error": str(exc)},
            )

        text = reply.text.strip()
        stopped = text == "LLMID_PARAM_ALPHA"
        ignored_but_valid = text == "LLMID_PARAM_ALPHA_STOP_BETA"
        stop_policy = self.protocol_profile["stop_policy"]
        if stopped:
            score = 1.0
            detail = "Provider honored stop sequence parameter."
        elif ignored_but_valid and stop_policy == "optional":
            score = 0.82
            detail = "Provider ignored stop sequence, acceptable for this model family's compatibility profile."
        elif ignored_but_valid and stop_policy == "soft":
            score = 0.62
            detail = "Provider ignored stop sequence; this is a soft compatibility warning for this model family."
        elif ignored_but_valid:
            score = 0.35
            detail = "Provider appears to ignore stop sequence parameter."
        else:
            score = 0.2
            detail = "Provider output did not match stop-parameter probe."
        return ProbeResult(
            category="protocol",
            name="parameter_control",
            score=score,
            status=_status(score),
            detail=detail,
            sample=_shorten(text),
            evidence={
                **_reply_evidence(reply),
                "expected_stopped_text": "LLMID_PARAM_ALPHA",
                "model_family": self.model_family,
                "stop_policy": stop_policy,
            },
        )

    async def _run_token_probes(self) -> list[ProbeResult]:
        cases = [
            ("ascii_short", "Reply OK only. Text: The quick brown fox jumps over 13 lazy dogs."),
            ("cjk_mixed", "只回复 OK。文本：模型真实性检测需要比较中文、English、数字123和标点。"),
            ("unicode_edge", "Reply OK only. Text: emoji 😊🚀, math ∑≈√, spaces     and\nnew lines."),
            ("long_repeat", "Reply OK only. Text: " + ("alpha beta gamma delta " * 80)),
        ]

        observations: list[tuple[str, str, ModelReply, int]] = []
        results: list[ProbeResult] = []
        for name, prompt in cases:
            reply = await self.generate(prompt)
            observations.append((name, prompt, reply, _rough_token_estimate(prompt)))

        usage_inputs = [reply.usage.input for _, _, reply, _ in observations if reply.usage and reply.usage.input]
        has_usage = len(usage_inputs) >= 3
        if not has_usage:
            results.append(
                ProbeResult(
                    category="token",
                    name="token usage 存在性",
                    score=0.2,
                    status="异常",
                    detail="多数 token 探测没有返回 input usage，无法验证计量真实性。",
                    evidence={"observed_inputs": usage_inputs},
                )
            )
            return results

        estimate_pairs = [
            {"case": name, "estimated": estimated, "reported": reply.usage.input}
            for name, _, reply, estimated in observations
            if reply.usage and reply.usage.input is not None
        ]
        ratios = [
            (item["reported"] / max(item["estimated"], 1))
            for item in estimate_pairs
            if item["reported"] is not None
        ]
        ratio_spread = max(ratios) - min(ratios) if ratios else 99.0
        plausible_ratio = all(0.35 <= ratio <= 3.5 for ratio in ratios)
        monotonic_ok = _reported(observations, "long_repeat") > max(
            _reported(observations, "ascii_short"),
            _reported(observations, "cjk_mixed"),
            _reported(observations, "unicode_edge"),
        )
        identical_bad = len(set(usage_inputs)) <= 1

        score = 1.0
        if not plausible_ratio:
            score -= 0.35
        if not monotonic_ok:
            score -= 0.3
        if identical_bad:
            score -= 0.35
        if ratio_spread > 2.0:
            score -= 0.15
        score = max(0.0, score)

        results.append(
            ProbeResult(
                category="token",
                name="token 计量真实性",
                score=score,
                status="通过" if score >= 0.75 else ("可疑" if score >= 0.45 else "异常"),
                detail=_token_detail(score, monotonic_ok, plausible_ratio, identical_bad),
                evidence={"cases": estimate_pairs, "ratio_spread": round(ratio_spread, 4)},
            )
        )
        return results

    async def _run_fingerprint_probes(self) -> list[ProbeResult]:
        results: list[ProbeResult] = []

        math_reply = await self.generate("请只输出 17*23+19 的阿拉伯数字结果，不要解释。")
        math_ok = "410" in re.findall(r"-?\d+", math_reply.text.strip())
        results.append(
            ProbeResult(
                category="fingerprint",
                name="基础推理稳定性",
                score=1.0 if math_ok else 0.45,
                status="通过" if math_ok else "异常",
                detail="基础算术探测通过。" if math_ok else "基础算术结果与预期不一致。",
                sample=_shorten(math_reply.text),
                evidence=_reply_evidence(math_reply),
            )
        )

        diff_reply = await self.generate(
            "下面有一个 Python bug。只输出 unified diff，不要解释。\n"
            "def add_one(x):\n"
            "    return x - 1\n"
            "期望：add_one(2) == 3"
        )
        diff_text = diff_reply.text.strip()
        diff_ok = "---" in diff_text and "+++" in diff_text and ("+    return x + 1" in diff_text or "+    return x+1" in diff_text)
        results.append(
            ProbeResult(
                category="fingerprint",
                name="代码修复格式服从",
                score=1.0 if diff_ok else 0.5,
                status="通过" if diff_ok else "可疑",
                detail="代码修复可按 unified diff 输出。" if diff_ok else "代码修复格式或补丁内容不够稳定。",
                sample=_shorten(diff_text),
                evidence=_reply_evidence(diff_reply),
            )
        )

        ambiguity_reply = await self.generate(
            "用两条编号短句解释“我看见她拿着望远镜”这句话的两种含义，不要添加第三条。"
        )
        ambiguity_text = ambiguity_reply.text.strip()
        numbered = len(re.findall(r"(^|\n)\s*(1[.、]|一[.、]|①)", ambiguity_text)) >= 1 and len(
            re.findall(r"(^|\n)\s*(2[.、]|二[.、]|②)", ambiguity_text)
        ) >= 1
        telescope = "望远镜" in ambiguity_text
        results.append(
            ProbeResult(
                category="fingerprint",
                name="中文歧义理解",
                score=1.0 if numbered and telescope else 0.55,
                status="通过" if numbered and telescope else "可疑",
                detail="中文歧义任务输出结构和语义均符合要求。" if numbered and telescope else "中文歧义解释不完整或格式不稳定。",
                sample=_shorten(ambiguity_text),
                evidence=_reply_evidence(ambiguity_reply),
            )
        )
        return results

    def _build_report(self, results: list[ProbeResult]) -> DetectionReport:
        category_scores: dict[str, float] = {}
        for category in ("protocol", "token", "fingerprint"):
            items = [item for item in results if item.category == category]
            if items:
                category_scores[category] = round(_category_score(category, items, self.protocol_profile), 4)

        weights = _category_weights_for_family(self.model_family)
        present_weight = sum(weights[key] for key in category_scores)
        total = sum(category_scores[key] * weights[key] for key in category_scores) / max(present_weight, 0.01)
        if set(category_scores) == {"protocol"} and _is_open_model_family(self.model_family):
            total = min(total, 0.60)
        if self.strict_mode:
            total = max(0.0, total - 0.05 * sum(1 for item in results if item.status in {"异常", "失败"}))
        total = round(total, 4)

        protocol_only = set(category_scores) == {"protocol"}
        if protocol_only and _is_open_model_family(self.model_family):
            certainty = "较低"
            risk = "中"
            base_model = "开源模型族协议证据权重较低，需要后续指纹识别确认底模"
        elif protocol_only and total < 0.8:
            certainty = "较低"
            risk = "中高" if total < 0.65 else "中"
            base_model = "接口兼容性存在缺陷，无法仅凭协议确认声明模型"
        elif total >= 0.82:
            certainty = "中等偏高"
            risk = "低"
            base_model = "声明模型或高度兼容底模"
        elif total >= 0.62:
            certainty = "中等"
            risk = "中"
            base_model = "兼容模型 / 可能存在包装、路由或能力降级"
        elif total >= 0.42:
            certainty = "较低"
            risk = "中高"
            base_model = "小模型、蒸馏模型或未知兼容模型"
        else:
            certainty = "低"
            risk = "高"
            base_model = "未知模型 / 接口或计量明显异常"

        candidates = self._build_candidates(total, category_scores, results)
        return DetectionReport(
            provider_id=self.provider_id,
            claimed_model=self.claimed_model,
            model_family=self.model_family,
            protocol_profile=str(self.protocol_profile["name"]),
            base_model_guess=base_model,
            certainty_label=certainty,
            certainty_score=total,
            risk_level=risk,
            category_scores=category_scores,
            candidates=candidates,
            results=results,
            created_at=int(time.time()),
        )

    def _build_candidates(
        self,
        total: float,
        category_scores: dict[str, float],
        results: list[ProbeResult],
    ) -> list[ModelCandidate]:
        protocol = category_scores.get("protocol", 0.0)
        token = category_scores.get("token")
        fingerprint = category_scores.get("fingerprint")
        usage_anomaly = any(item.category == "token" and item.score < 0.45 for item in results)
        protocol_only = set(category_scores) == {"protocol"}
        json_issue = any(item.category == "protocol" and item.name == "json_mode_compatibility" and item.score < 0.8 for item in results)
        stop_policy = str(self.protocol_profile.get("stop_policy") or "strict")
        openai_adapter_issue = any(
            item.category == "protocol"
            and item.name in {
                "openai_chat_completion_shape",
                "openai_json_schema_contract",
                "openai_tool_call_contract",
                "openai_stream_nonstream_consistency",
            }
            and item.score < 0.8
            for item in results
        )
        claude_signature_missing = any(
            item.category == "protocol"
            and item.name == "claude_thinking_signature"
            and item.score < 0.8
            for item in results
        )
        parameter_issue = any(item.category == "protocol" and item.name == "parameter_control" and item.score < (0.5 if stop_policy == "optional" else 0.8) for item in results)
        parameter_soft_issue = any(item.category == "protocol" and item.name == "parameter_control" and item.score < 0.8 for item in results)

        if protocol_only:
            if self.model_family == "claude":
                wrapper_confidence = min(0.92, max(0.12, (1.0 - protocol) * 1.15 + (0.42 if claude_signature_missing else 0.0)))
                declared_confidence = min(0.9, max(0.05, protocol * (0.48 if claude_signature_missing else 0.9)))
                candidates = [
                    ModelCandidate(
                        name="Claude 兼容层 / 疑似非官方 Anthropic 响应",
                        confidence=round(wrapper_confidence, 4),
                        basis=["缺失 Claude thinking signature 是强异常"] if claude_signature_missing else ["Anthropic 专用字段基本匹配"],
                    ),
                    ModelCandidate(
                        name=f"{self.claimed_model} / 声明 Claude 底模",
                        confidence=round(declared_confidence, 4),
                        basis=[f"按 {self.protocol_profile['name']} 协议 profile 评估"],
                    ),
                    ModelCandidate(
                        name="未知 Claude-compatible 模型",
                        confidence=round(max(0.08, min(0.58, 1.0 - protocol + (0.18 if claude_signature_missing else 0.0))), 4),
                        basis=["需要官方 Anthropic signature / stream baseline 进一步确认"],
                    ),
                ]
                candidates.sort(key=lambda item: item.confidence, reverse=True)
                return candidates

            if self.model_family == "openai":
                wrapper_confidence = min(0.92, max(0.1, (1.0 - protocol) * 1.15 + (0.25 if openai_adapter_issue else 0.0)))
                declared_confidence = min(0.9, max(0.05, protocol * (0.62 if openai_adapter_issue else 0.9)))
                candidates = [
                    ModelCandidate(
                        name="OpenAI 协议包装层 / 简化文本适配层",
                        confidence=round(wrapper_confidence, 4),
                        basis=["chat.completion、tool call、JSON schema、stream 或 usage 字段存在适配异常"] if openai_adapter_issue else ["OpenAI strict chat completions 字段基本匹配"],
                    ),
                    ModelCandidate(
                        name=f"{self.claimed_model} / 声明 GPT 底模",
                        confidence=round(declared_confidence, 4),
                        basis=[f"按 {self.protocol_profile['name']} 协议 profile 评估"],
                    ),
                    ModelCandidate(
                        name="未知 OpenAI-compatible 模型",
                        confidence=round(max(0.08, min(0.58, 1.0 - protocol + (0.12 if openai_adapter_issue else 0.0))), 4),
                        basis=["需要 token、指纹与官方 API baseline 进一步确认"],
                    ),
                ]
                candidates.sort(key=lambda item: item.confidence, reverse=True)
                return candidates

            if _is_open_model_family(self.model_family):
                protocol_issue = json_issue or parameter_issue or parameter_soft_issue or protocol < 0.8
                declared_confidence = min(0.62, max(0.05, protocol * 0.45))
                wrapper_confidence = min(
                    0.75,
                    max(
                        0.12,
                        (1.0 - protocol) * 0.75
                        + (0.12 if json_issue else 0.0)
                        + (0.12 if parameter_issue else 0.0)
                        + (0.05 if parameter_soft_issue else 0.0),
                    ),
                )
                candidates = [
                    ModelCandidate(
                        name=f"{self.claimed_model} / 声明开源模型兼容底模",
                        confidence=round(declared_confidence, 4),
                        basis=["Qwen/GLM/DeepSeek 等开源模型族仅凭协议合法性不能强确认底模"],
                    ),
                    ModelCandidate(
                        name="同族开源兼容模型 / 蒸馏或微调模型",
                        confidence=round(max(0.18, min(0.68, 0.55 - protocol * 0.18)), 4),
                        basis=["需要后续行为指纹、token 与多轮稳定性区分"],
                    ),
                    ModelCandidate(
                        name="中转站包装 / OpenAI-compatible 适配层",
                        confidence=round(wrapper_confidence, 4),
                        basis=["接口兼容性存在异常"] if protocol_issue else ["协议层仅作为低权重辅助证据"],
                    ),
                ]
                candidates.sort(key=lambda item: item.confidence, reverse=True)
                return candidates

            wrapper_confidence = min(
                0.9,
                max(
                    0.1,
                    (1.0 - protocol) * 1.1
                    + (0.18 if json_issue else 0.0)
                    + (0.22 if parameter_issue else 0.0)
                    + (0.06 if parameter_soft_issue and stop_policy != "optional" else 0.0),
                ),
            )
            declared_multiplier = 0.75 if json_issue or parameter_issue else (0.86 if parameter_soft_issue else 0.9)
            declared_confidence = min(0.9, max(0.05, protocol * declared_multiplier))
            candidates = [
                ModelCandidate(
                    name="中转站包装 / OpenAI-compatible 适配层",
                    confidence=round(wrapper_confidence, 4),
                    basis=["JSON-only 或关键参数行为与该模型族协议 profile 不一致"] if json_issue or parameter_issue else ["仅存在模型族允许的软兼容差异"],
                ),
                ModelCandidate(
                    name=f"{self.claimed_model} / 声明模型兼容底模",
                    confidence=round(declared_confidence, 4),
                    basis=[f"按 {self.protocol_profile['name']} 协议 profile 评估"],
                ),
                ModelCandidate(
                    name="未知兼容模型",
                    confidence=round(max(0.08, min(0.55, 1.0 - protocol)), 4),
                    basis=["需要 token 与行为指纹进一步区分"],
                ),
            ]
            candidates.sort(key=lambda item: item.confidence, reverse=True)
            return candidates

        token_score = token if token is not None else 0.65
        fingerprint_score = fingerprint if fingerprint is not None else 0.65

        candidates = [
            ModelCandidate(
                name=f"{self.claimed_model} / 声明模型兼容底模",
                confidence=round(min(0.92, max(0.05, total)), 4),
                basis=["协议、token 与行为指纹综合匹配"] if total >= 0.7 else ["仍需更多证据确认声明模型"],
            ),
            ModelCandidate(
                name="小模型或蒸馏兼容模型",
                confidence=round(max(0.05, min(0.75, 0.75 - fingerprint_score * 0.45 + max(0.0, 0.65 - token_score) * 0.25)), 4),
                basis=["行为指纹或 token 计量弱于声明模型时提升该候选"],
            ),
            ModelCandidate(
                name="中转站包装/动态路由模型",
                confidence=round(max(0.05, min(0.85, (1.0 - protocol) * 0.35 + (1.0 - token_score) * 0.35 + (0.25 if usage_anomaly else 0.0))), 4),
                basis=["接口字段、usage 或多轮表现异常时提升该候选"],
            ),
        ]
        candidates.sort(key=lambda item: item.confidence, reverse=True)
        return candidates


def _reply_evidence(reply: ModelReply) -> dict[str, object]:
    return {
        "response_id": reply.response_id,
        "usage": vars(reply.usage) if reply.usage else None,
        "has_reasoning_content": bool(reply.reasoning_content),
        "raw_type": reply.raw_type,
        "meta": reply.meta,
    }


def _claude_signatures(reply: ModelReply) -> list[str]:
    signatures: list[str] = []
    if reply.reasoning_signature:
        signatures.append(reply.reasoning_signature)
    meta = reply.meta or {}
    raw_signature = meta.get("reasoning_signature")
    if raw_signature:
        signatures.append(str(raw_signature))
    for signature in meta.get("thinking_signatures", []) or []:
        signatures.append(str(signature))
    seen: set[str] = set()
    unique: list[str] = []
    for signature in signatures:
        if not signature or signature in seen:
            continue
        seen.add(signature)
        unique.append(signature)
    return unique


def _claude_response_shape_score(reply: ModelReply, claimed_model: str) -> tuple[float, str, dict[str, object]]:
    meta = reply.meta or {}
    checks = {
        "has_message_id": str(reply.response_id or meta.get("id") or "").startswith("msg_"),
        "type_is_message": str(meta.get("type") or "").lower() == "message",
        "role_is_assistant": str(meta.get("role") or "").lower() == "assistant",
        "has_model_field": bool(meta.get("model")),
        "model_matches_claim": _model_names_compatible(str(meta.get("model") or ""), claimed_model) if meta.get("model") else False,
        "has_stop_reason": bool(meta.get("stop_reason") or meta.get("finish_reason")),
    }
    score = sum(1 for ok in checks.values() if ok) / len(checks)
    missing = [name for name, ok in checks.items() if not ok]
    detail = (
        "Claude raw message metadata matches Anthropic message shape."
        if score >= 0.8
        else "Claude message metadata is incomplete or inconsistent: " + ", ".join(missing)
    )
    return round(score, 4), detail, {"checks": checks, "meta": meta}


def _claude_usage_baseline_score(reply: ModelReply) -> tuple[float, str, dict[str, object]]:
    meta = reply.meta or {}
    raw_usage = meta.get("raw_usage") if isinstance(meta.get("raw_usage"), dict) else {}
    checks = {
        "has_usage": bool(reply.usage or raw_usage),
        "has_input_tokens": bool((reply.usage and reply.usage.input is not None) or raw_usage.get("input_tokens")),
        "has_output_tokens": bool((reply.usage and reply.usage.output is not None) or raw_usage.get("output_tokens")),
        "uses_anthropic_names": bool(raw_usage.get("input_tokens") is not None and raw_usage.get("output_tokens") is not None),
    }
    score = sum(1 for ok in checks.values() if ok) / len(checks)
    if checks["has_input_tokens"] and checks["has_output_tokens"] and not checks["uses_anthropic_names"]:
        score = min(score, 0.72)
    detail = (
        "Usage fields expose Anthropic-style input_tokens/output_tokens baseline."
        if score >= 0.8
        else "Usage fields are missing or normalized away from Anthropic baseline."
    )
    return round(score, 4), detail, {"checks": checks, "usage": vars(reply.usage) if reply.usage else None, "raw_usage": raw_usage}


def _claude_tool_use_id_surface(reply: ModelReply) -> ProbeResult:
    meta = reply.meta or {}
    tool_use_ids = [str(item) for item in (meta.get("tool_use_ids") or []) if item]
    if tool_use_ids:
        valid = all(item.startswith("toolu_") for item in tool_use_ids)
        score = 1.0 if valid else 0.45
        detail = "Claude tool_use ids are exposed and use Anthropic toolu_ shape." if valid else "Tool use ids are exposed but do not match Anthropic toolu_ shape."
    else:
        score = 0.62
        detail = "Tool-use id baseline not observable through current AstrBot call; run a tool-enabled Claude probe for 1:1 comparison."
    return ProbeResult(
        category="protocol",
        name="claude_tool_use_id_surface",
        score=score,
        status=_status(score),
        detail=detail,
        evidence={"tool_use_ids": tool_use_ids, "meta": meta},
    )


def _claude_stream_surface(reply: ModelReply) -> ProbeResult:
    meta = reply.meta or {}
    events = [str(item) for item in (meta.get("sse_event_types") or []) if item]
    if events:
        required = {"message_start", "content_block_start", "content_block_delta", "content_block_stop", "message_delta", "message_stop"}
        seen = set(events)
        score = len(required & seen) / len(required)
        detail = "SSE event sequence is exposed for Claude stream baseline." if score >= 0.8 else "SSE event sequence is incomplete for Claude stream baseline."
    else:
        score = 0.62
        detail = "SSE stream/non-stream baseline is not observable through current AstrBot non-stream call."
    return ProbeResult(
        category="protocol",
        name="claude_stream_event_surface",
        score=round(score, 4),
        status=_status(score),
        detail=detail,
        evidence={"sse_event_types": events},
    )


def _gemini_response_shape_score(reply: ModelReply, claimed_model: str) -> tuple[float, str, dict[str, object]]:
    meta = reply.meta or {}
    model_value = str(meta.get("modelVersion") or meta.get("model") or "")
    checks = {
        "has_candidates": int(meta.get("candidates_count") or 0) > 0,
        "role_is_model": str(meta.get("role") or "").lower() in {"model", ""},
        "has_text_part": "text" in [str(item) for item in (meta.get("part_types") or [])],
        "has_finish_reason": bool(meta.get("finish_reason")),
        "has_model_version_or_model": bool(model_value),
    }
    if model_value and claimed_model and claimed_model != "unknown":
        checks["model_matches_claim"] = _model_names_compatible(model_value, claimed_model)
    score = sum(1 for ok in checks.values() if ok) / len(checks)
    missing = [name for name, ok in checks.items() if not ok]
    observed = {
        "response_id": meta.get("responseId") or meta.get("id"),
        "model": meta.get("model"),
        "modelVersion": meta.get("modelVersion"),
        "candidates_count": meta.get("candidates_count"),
        "role": meta.get("role"),
        "part_types": meta.get("part_types"),
        "finish_reason": meta.get("finish_reason"),
    }
    detail = (
        "Raw response matches Gemini GenerateContentResponse structure: candidates, model role, parts, finishReason, modelVersion/model."
        if score >= 0.8
        else "Gemini GenerateContentResponse metadata is incomplete or normalized: " + ", ".join(missing)
    )
    return round(score, 4), detail, {"checks": checks, "missing": missing, "observed": observed, "meta": meta}


def _gemini_usage_baseline_score(first: ModelReply, second: ModelReply) -> tuple[float, str, dict[str, object]]:
    replies = [first, second]
    raw_usages = [(reply.meta or {}).get("raw_usage") if isinstance((reply.meta or {}).get("raw_usage"), dict) else {} for reply in replies]
    usages = [reply.usage for reply in replies]
    checks = {
        "has_usage_both": all(usage is not None or raw_usage for usage, raw_usage in zip(usages, raw_usages)),
        "has_prompt_token_count": all((usage and usage.input is not None) or raw_usage.get("promptTokenCount") is not None for usage, raw_usage in zip(usages, raw_usages)),
        "has_candidates_token_count": all((usage and usage.output is not None) or raw_usage.get("candidatesTokenCount") is not None for usage, raw_usage in zip(usages, raw_usages)),
        "has_total_token_count": all((usage and usage.total is not None) or raw_usage.get("totalTokenCount") is not None for usage, raw_usage in zip(usages, raw_usages)),
        "uses_gemini_names": all(raw_usage.get("promptTokenCount") is not None and raw_usage.get("candidatesTokenCount") is not None for raw_usage in raw_usages),
        "usage_varies": len({(usage.input if usage else None, usage.output if usage else None, usage.total if usage else None) for usage in usages}) > 1,
    }
    score = sum(1 for ok in checks.values() if ok) / len(checks)
    if checks["has_usage_both"] and not checks["uses_gemini_names"]:
        score = min(score, 0.68)
    detail = (
        "Usage metadata exposes Gemini promptTokenCount/candidatesTokenCount/totalTokenCount and varies across calls."
        if score >= 0.8
        else "Gemini usageMetadata fields are missing, renamed, static, or normalized away."
    )
    return round(score, 4), detail, {"checks": checks, "usages": [vars(usage) if usage else None for usage in usages], "raw_usages": raw_usages}


def _gemini_shape_sample(evidence: dict[str, object]) -> str:
    observed = evidence.get("observed") if isinstance(evidence, dict) else None
    if not isinstance(observed, dict):
        return ""
    parts = [
        f"{key}={observed.get(key)!r}"
        for key in ("response_id", "model", "modelVersion", "candidates_count", "role", "part_types", "finish_reason")
        if observed.get(key) is not None and observed.get(key) != ""
    ]
    missing = evidence.get("missing")
    if isinstance(missing, list) and missing:
        parts.append("missing=" + ",".join(str(item) for item in missing[:8]))
    return _shorten("; ".join(parts), 500)


def _openai_response_shape_score(reply: ModelReply, claimed_model: str) -> tuple[float, str, dict[str, object]]:
    meta = reply.meta or {}
    object_value = str(meta.get("object") or "").lower()
    response_id = str(reply.response_id or meta.get("id") or "")
    id_scheme = _openai_response_id_scheme(response_id)
    object_is_chat = object_value == "chat.completion"
    object_is_response = object_value == "response"
    checks = {
        "has_response_id": bool(response_id),
        "object_is_official_openai": object_is_chat or object_is_response,
        "output_or_choices_present": int(meta.get("choices_count") or 0) > 0 or int(meta.get("output_count") or 0) > 0,
        "role_is_assistant": str(meta.get("role") or "").lower() == "assistant",
        "finish_reason_or_status_present": bool(meta.get("finish_reason") or meta.get("status")),
        "has_model_field": bool(meta.get("model")),
    }
    if meta.get("model") and claimed_model and claimed_model != "unknown":
        checks["model_field_matches_claim"] = _model_names_compatible(str(meta.get("model") or ""), claimed_model)
    score = sum(1 for ok in checks.values() if ok) / len(checks)
    if object_value and not (object_is_chat or object_is_response):
        score = min(score, 0.76)
    missing = [name for name, ok in checks.items() if not ok]
    warnings = []
    if response_id and id_scheme == "unknown":
        warnings.append("unknown_response_id_scheme")
    detail = (
        "Raw response matches official OpenAI response structure: response id, output/choices, status/finish_reason, usage-ready metadata."
        if score >= 0.8 and not warnings
        else "Raw response matches official OpenAI response structure with compatibility warnings: " + ", ".join(warnings)
        if score >= 0.8
        else "OpenAI response metadata is incomplete or normalized: " + ", ".join(missing)
    )
    observed = {
        "response_id": response_id,
        "id_scheme": id_scheme,
        "object": meta.get("object"),
        "model": meta.get("model"),
        "choices_count": meta.get("choices_count"),
        "output_count": meta.get("output_count"),
        "role": meta.get("role"),
        "finish_reason": meta.get("finish_reason"),
        "status": meta.get("status"),
    }
    return round(score, 4), detail, {"checks": checks, "missing": missing, "warnings": warnings, "observed": observed, "meta": meta}


def _openai_response_id_scheme(response_id: str) -> str:
    if response_id.startswith("chatcmpl-"):
        return "chat_completion"
    if response_id.startswith("resp_"):
        return "responses"
    if response_id:
        return "unknown"
    return "missing"


def _openai_usage_baseline_score(first: ModelReply, second: ModelReply) -> tuple[float, str, dict[str, object]]:
    replies = [first, second]
    raw_usages = [(reply.meta or {}).get("raw_usage") if isinstance((reply.meta or {}).get("raw_usage"), dict) else {} for reply in replies]
    usages = [reply.usage for reply in replies]
    checks = {
        "has_usage_both": all(usage is not None or raw_usage for usage, raw_usage in zip(usages, raw_usages)),
        "has_input_token_count": all((usage and usage.input is not None) or raw_usage.get("prompt_tokens") is not None or raw_usage.get("input_tokens") is not None for usage, raw_usage in zip(usages, raw_usages)),
        "has_output_token_count": all((usage and usage.output is not None) or raw_usage.get("completion_tokens") is not None or raw_usage.get("output_tokens") is not None for usage, raw_usage in zip(usages, raw_usages)),
        "has_total_tokens": all((usage and usage.total is not None) or raw_usage.get("total_tokens") is not None for usage, raw_usage in zip(usages, raw_usages)),
        "uses_official_names": all(
            (
                raw_usage.get("prompt_tokens") is not None
                and raw_usage.get("completion_tokens") is not None
            )
            or (
                raw_usage.get("input_tokens") is not None
                and raw_usage.get("output_tokens") is not None
            )
            for raw_usage in raw_usages
        ),
        "usage_varies": len({(usage.input if usage else None, usage.output if usage else None, usage.total if usage else None) for usage in usages}) > 1,
    }
    score = sum(1 for ok in checks.values() if ok) / len(checks)
    if checks["has_usage_both"] and not checks["uses_official_names"]:
        score = min(score, 0.68)
    detail = (
        "Usage fields expose official OpenAI token structure and vary across calls."
        if score >= 0.8
        else "Usage fields are missing, renamed, static, or normalized away from OpenAI baseline."
    )
    return round(score, 4), detail, {"checks": checks, "usages": [vars(usage) if usage else None for usage in usages], "raw_usages": raw_usages}


def _openai_shape_sample(evidence: dict[str, object]) -> str:
    observed = evidence.get("observed") if isinstance(evidence, dict) else None
    if not isinstance(observed, dict):
        return ""
    parts = [
        f"{key}={observed.get(key)!r}"
        for key in ("response_id", "id_scheme", "object", "model", "choices_count", "output_count", "role", "finish_reason", "status")
        if observed.get(key) is not None and observed.get(key) != ""
    ]
    missing = evidence.get("missing")
    if isinstance(missing, list) and missing:
        parts.append("missing=" + ",".join(str(item) for item in missing[:8]))
    return _shorten("; ".join(parts), 500)


def _openai_schema_payload_ok(parsed: object) -> bool:
    return bool(
        isinstance(parsed, dict)
        and parsed.get("answer") == 410
        and parsed.get("ok") is True
        and parsed.get("items") == [1, 2, 3]
    )


def _category_score(category: str, items: list[ProbeResult], protocol_profile: dict[str, object]) -> float:
    if category != "protocol":
        return sum(item.score for item in items) / max(len(items), 1)

    by_name = {item.name: item for item in items}
    profile_name = str(protocol_profile.get("name") or "")
    if profile_name == "anthropic_messages_compatible":
        return _claude_category_score(by_name)
    if profile_name == "openai_strict_chat_completions":
        return _openai_category_score(by_name)
    if profile_name == "gemini_generate_content_compatible":
        return _gemini_category_score(by_name)

    weights = {
        "minimal_completion_contract": 0.10,
        "json_mode_compatibility": 0.25,
        "raw_response_shape": 0.18,
        "usage_contract": 0.14,
        "parameter_control": 0.23,
        "multi_call_consistency": 0.10,
    }
    weighted = 0.0
    present_weight = 0.0
    for name, weight in weights.items():
        item = by_name.get(name)
        if item is None:
            continue
        weighted += item.score * weight
        present_weight += weight
    score = weighted / max(present_weight, 0.01)

    json_score = by_name.get("json_mode_compatibility").score if by_name.get("json_mode_compatibility") else 1.0
    parameter_score = by_name.get("parameter_control").score if by_name.get("parameter_control") else 1.0
    shape_score = by_name.get("raw_response_shape").score if by_name.get("raw_response_shape") else 1.0
    stop_policy = str(protocol_profile.get("stop_policy") or "strict")

    caps: list[float] = []
    if json_score < 0.8:
        caps.append(0.72)
    parameter_cap_threshold = 0.5 if stop_policy == "optional" else 0.8
    if parameter_score < parameter_cap_threshold:
        caps.append(0.70)
    if shape_score < 0.8:
        caps.append(0.76)
    if json_score < 0.8 and parameter_score < parameter_cap_threshold:
        caps.append(0.58)
    if caps:
        score = min(score, min(caps))
    return max(0.0, min(1.0, score))


def _openai_category_score(by_name: dict[str, ProbeResult]) -> float:
    weights = {
        "openai_minimal_chat_contract": 0.10,
        "openai_chat_completion_shape": 0.26,
        "openai_usage_shape": 0.18,
        "openai_json_schema_contract": 0.20,
        "openai_tool_call_contract": 0.18,
        "openai_stream_nonstream_consistency": 0.08,
    }
    weighted = 0.0
    present_weight = 0.0
    for name, weight in weights.items():
        item = by_name.get(name)
        if item is None:
            continue
        weighted += item.score * weight
        present_weight += weight
    score = weighted / max(present_weight, 0.01)

    shape_score = by_name.get("openai_chat_completion_shape").score if by_name.get("openai_chat_completion_shape") else 1.0
    usage_score = by_name.get("openai_usage_shape").score if by_name.get("openai_usage_shape") else 1.0
    schema_score = by_name.get("openai_json_schema_contract").score if by_name.get("openai_json_schema_contract") else 1.0
    tool_score = by_name.get("openai_tool_call_contract").score if by_name.get("openai_tool_call_contract") else 1.0
    stream_score = by_name.get("openai_stream_nonstream_consistency").score if by_name.get("openai_stream_nonstream_consistency") else 1.0

    caps: list[float] = []
    if shape_score < 0.8:
        caps.append(0.68)
    if usage_score < 0.8:
        caps.append(0.78)
    if schema_score < 0.8:
        caps.append(0.72)
    if tool_score < 0.8:
        caps.append(0.70)
    if schema_score < 0.5 and tool_score < 0.5:
        caps.append(0.52)
    if shape_score < 0.8 and (schema_score < 0.8 or tool_score < 0.8):
        caps.append(0.58)
    if stream_score < 0.5 and shape_score < 0.8:
        caps.append(0.62)
    if caps:
        score = min(score, min(caps))
    return max(0.0, min(1.0, score))


def _gemini_category_score(by_name: dict[str, ProbeResult]) -> float:
    weights = {
        "gemini_minimal_generate_content_contract": 0.10,
        "gemini_generate_content_shape": 0.28,
        "gemini_usage_metadata": 0.18,
        "gemini_structured_output_contract": 0.18,
        "gemini_function_call_contract": 0.18,
        "gemini_stream_generate_content_surface": 0.08,
    }
    weighted = 0.0
    present_weight = 0.0
    for name, weight in weights.items():
        item = by_name.get(name)
        if item is None:
            continue
        weighted += item.score * weight
        present_weight += weight
    score = weighted / max(present_weight, 0.01)

    shape_score = by_name.get("gemini_generate_content_shape").score if by_name.get("gemini_generate_content_shape") else 1.0
    usage_score = by_name.get("gemini_usage_metadata").score if by_name.get("gemini_usage_metadata") else 1.0
    structured_score = by_name.get("gemini_structured_output_contract").score if by_name.get("gemini_structured_output_contract") else 1.0
    function_score = by_name.get("gemini_function_call_contract").score if by_name.get("gemini_function_call_contract") else 1.0
    stream_score = by_name.get("gemini_stream_generate_content_surface").score if by_name.get("gemini_stream_generate_content_surface") else 1.0

    caps: list[float] = []
    if shape_score < 0.8:
        caps.append(0.66)
    if usage_score < 0.8:
        caps.append(0.78)
    if structured_score < 0.8:
        caps.append(0.74)
    if function_score < 0.8:
        caps.append(0.72)
    if structured_score < 0.5 and function_score < 0.5:
        caps.append(0.54)
    if stream_score < 0.5 and shape_score < 0.8:
        caps.append(0.62)
    if caps:
        score = min(score, min(caps))
    return max(0.0, min(1.0, score))


def _claude_category_score(by_name: dict[str, ProbeResult]) -> float:
    weights = {
        "claude_minimal_message_contract": 0.10,
        "claude_thinking_signature": 0.50,
        "claude_message_shape": 0.18,
        "claude_usage_baseline": 0.16,
        "claude_tool_use_id_surface": 0.08,
        "claude_stream_event_surface": 0.08,
    }
    weighted = 0.0
    present_weight = 0.0
    for name, weight in weights.items():
        item = by_name.get(name)
        if item is None:
            continue
        weighted += item.score * weight
        present_weight += weight
    score = weighted / max(present_weight, 0.01)

    thinking_score = by_name.get("claude_thinking_signature").score if by_name.get("claude_thinking_signature") else 1.0
    shape_score = by_name.get("claude_message_shape").score if by_name.get("claude_message_shape") else 1.0
    usage_score = by_name.get("claude_usage_baseline").score if by_name.get("claude_usage_baseline") else 1.0
    caps: list[float] = []
    if thinking_score < 0.8:
        caps.append(0.60)
    if thinking_score < 0.5:
        caps.append(0.42)
    if shape_score < 0.8:
        caps.append(0.76)
    if usage_score < 0.8:
        caps.append(0.82)
    if caps:
        score = min(score, min(caps))
    return max(0.0, min(1.0, score))


def _detect_model_family(claimed_model: str, provider_id: str) -> str:
    text = f"{claimed_model} {provider_id}".lower()
    if any(token in text for token in ("claude", "anthropic")):
        return "claude"
    if any(token in text for token in ("gemini", "google")):
        return "gemini"
    if any(token in text for token in ("qwen", "qwq", "qvq", "dashscope", "bailian", "百炼", "阿里")):
        return "qwen"
    if "deepseek" in text:
        return "deepseek"
    if any(token in text for token in ("glm", "zhipu", "智谱")):
        return "glm"
    if any(token in text for token in ("gpt", "openai", "o1", "o3", "o4")):
        return "openai"
    return "generic"


def _is_open_model_family(model_family: str) -> bool:
    return model_family in {"qwen", "glm", "deepseek"}


def _category_weights_for_family(model_family: str) -> dict[str, float]:
    if _is_open_model_family(model_family):
        return {"protocol": 0.12, "token": 0.18, "fingerprint": 0.70}
    if model_family == "generic":
        return {"protocol": 0.20, "token": 0.25, "fingerprint": 0.55}
    return {"protocol": 0.30, "token": 0.30, "fingerprint": 0.40}


def _protocol_profile_for_family(model_family: str) -> dict[str, object]:
    profiles: dict[str, dict[str, object]] = {
        "openai": {
            "name": "openai_strict_chat_completions",
            "stop_policy": "strict",
        },
        "qwen": {
            "name": "qwen_dashscope_openai_compatible",
            "stop_policy": "optional",
        },
        "deepseek": {
            "name": "deepseek_openai_compatible",
            "stop_policy": "soft",
        },
        "glm": {
            "name": "glm_openai_compatible",
            "stop_policy": "soft",
        },
        "claude": {
            "name": "anthropic_messages_compatible",
            "stop_policy": "soft",
        },
        "gemini": {
            "name": "gemini_generate_content_compatible",
            "stop_policy": "soft",
        },
        "generic": {
            "name": "generic_chat_compatible",
            "stop_policy": "soft",
        },
    }
    return profiles.get(model_family, profiles["generic"])


def _score_bool_pair(first: bool, second: bool, *, partial: float) -> float:
    if first and second:
        return 1.0
    if first or second:
        return partial
    return 0.2


def _status(score: float) -> str:
    if score >= 0.8:
        return "通过"
    if score >= 0.5:
        return "可疑"
    return "异常"


def _response_shape_score(reply: ModelReply, claimed_model: str) -> tuple[float, str, dict[str, object]]:
    meta = reply.meta or {}
    checks: dict[str, bool] = {
        "has_response_id": bool(reply.response_id or meta.get("id")),
        "has_raw_completion": bool(reply.raw_type and reply.raw_type not in {"", "NoneType"}),
        "has_model_field": bool(meta.get("model")),
        "role_is_assistant": str(meta.get("role") or "").lower() in {"assistant", "model", ""},
        "finish_reason_present": bool(meta.get("finish_reason")),
    }
    model_field = str(meta.get("model") or "")
    claimed = str(claimed_model or "")
    if model_field and claimed and claimed != "unknown":
        checks["model_field_matches_claim"] = _model_names_compatible(model_field, claimed)

    score = sum(1 for ok in checks.values() if ok) / max(len(checks), 1)
    missing = [name for name, ok in checks.items() if not ok]
    detail = (
        "Raw response exposes expected OpenAI-compatible metadata."
        if score >= 0.8
        else "Raw response metadata is incomplete or inconsistent: " + ", ".join(missing)
    )
    return round(score, 4), detail, {"checks": checks, "meta": meta}


def _protocol_usage_score(first: ModelReply, second: ModelReply) -> tuple[float, str, dict[str, object]]:
    usages = [reply.usage for reply in (first, second) if reply.usage is not None]
    if len(usages) < 2:
        return 0.25, "Usage is absent or only present on one response.", {"first": _reply_evidence(first), "second": _reply_evidence(second)}

    checks = {
        "input_positive": all((usage.input or 0) > 0 for usage in usages),
        "output_positive": all((usage.output or 0) > 0 for usage in usages),
        "total_consistent": all((usage.total or 0) >= (usage.input or 0) + (usage.output or 0) for usage in usages),
        "not_identical_for_different_prompts": len({(usage.input, usage.output, usage.total) for usage in usages}) > 1,
    }
    score = sum(1 for ok in checks.values() if ok) / len(checks)
    detail = (
        "Usage fields are present, positive, internally consistent, and vary across prompts."
        if score >= 0.8
        else "Usage contract is weak: " + ", ".join(name for name, ok in checks.items() if not ok)
    )
    return round(score, 4), detail, {"checks": checks, "usages": [vars(usage) for usage in usages]}


def _protocol_consistency_score(first: ModelReply, second: ModelReply) -> tuple[float, str, dict[str, object]]:
    first_meta = first.meta or {}
    second_meta = second.meta or {}
    checks = {
        "different_response_ids": bool((first.response_id or first_meta.get("id")) and (second.response_id or second_meta.get("id")) and (first.response_id or first_meta.get("id")) != (second.response_id or second_meta.get("id"))),
        "same_raw_type": bool(first.raw_type and first.raw_type == second.raw_type),
        "same_model_field": bool(first_meta.get("model") and first_meta.get("model") == second_meta.get("model")),
        "same_role": str(first_meta.get("role") or "") == str(second_meta.get("role") or ""),
    }
    score = sum(1 for ok in checks.values() if ok) / len(checks)
    detail = (
        "Multiple calls expose stable metadata and unique response ids."
        if score >= 0.8
        else "Multiple calls expose inconsistent or missing protocol metadata: " + ", ".join(name for name, ok in checks.items() if not ok)
    )
    return round(score, 4), detail, {"checks": checks, "first_meta": first_meta, "second_meta": second_meta}


def _model_names_compatible(raw_model: str, claimed_model: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    raw = normalize(raw_model)
    claimed = normalize(claimed_model)
    if not raw or not claimed:
        return False
    return raw in claimed or claimed in raw


def _try_parse_json_object(text: str) -> dict[str, object] | None:
    candidates = [text.strip()]
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _rough_token_estimate(text: str) -> int:
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    non_ascii_chars = len(text) - ascii_chars
    return max(1, int(ascii_chars / 4.0 + non_ascii_chars * 0.9))


def _reported(observations: list[tuple[str, str, ModelReply, int]], case_name: str) -> int:
    for name, _, reply, _ in observations:
        if name == case_name and reply.usage and reply.usage.input is not None:
            return reply.usage.input
    return 0


def _token_detail(score: float, monotonic_ok: bool, plausible_ratio: bool, identical_bad: bool) -> str:
    if score >= 0.75:
        return "usage 与输入长度变化基本一致，计量可信度较高。"
    problems: list[str] = []
    if not monotonic_ok:
        problems.append("长输入未体现更高 input tokens")
    if not plausible_ratio:
        problems.append("reported/estimated 比例偏离常见范围")
    if identical_bad:
        problems.append("多组输入返回相同 token 数")
    return "token 计量可疑：" + "；".join(problems or ["证据不足"])


def _shorten(text: str, limit: int = 180) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."
