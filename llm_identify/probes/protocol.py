from __future__ import annotations

from ..adapters.base import GenerateAdapter
from ..models import ProbeResult
from ..utils import status_for_score, try_parse_json_object


class ProtocolProbePack:
    category = "protocol"

    async def run(self, adapter: GenerateAdapter) -> list[ProbeResult]:
        results: list[ProbeResult] = []
        marker_a = await adapter.generate(
            "Reply with exactly this marker and nothing else: LLMID_PROTOCOL_A",
            probe_id="protocol_marker_a",
            category=self.category,
        )
        marker_b = await adapter.generate(
            "Reply with exactly this marker and nothing else: LLMID_PROTOCOL_B",
            probe_id="protocol_marker_b",
            category=self.category,
        )
        exact_a = marker_a.text.strip() == "LLMID_PROTOCOL_A"
        exact_b = marker_b.text.strip() == "LLMID_PROTOCOL_B"
        exact_score = 1.0 if exact_a and exact_b else (0.55 if exact_a or exact_b else 0.2)
        results.append(
            ProbeResult(
                category=self.category,
                name="minimal_completion_contract",
                score=exact_score,
                status=status_for_score(exact_score),
                detail="The endpoint followed independent exact-output probes." if exact_score >= 0.8 else "The endpoint failed or wrapped at least one exact-output probe.",
                sample=f"A={marker_a.text.strip()!r}; B={marker_b.text.strip()!r}",
                evidence={
                    "first_raw_type": marker_a.raw_type,
                    "second_raw_type": marker_b.raw_type,
                    "first_meta_keys": sorted(marker_a.meta.keys()),
                    "second_meta_keys": sorted(marker_b.meta.keys()),
                },
            )
        )

        json_reply = await adapter.generate(
            'Return JSON only, no markdown: {"answer":410,"ok":true,"items":[1,2,3]}',
            probe_id="protocol_json",
            category=self.category,
        )
        parsed = try_parse_json_object(json_reply.text)
        strict = json_reply.text.strip().startswith("{") and json_reply.text.strip().endswith("}")
        payload_ok = bool(parsed and parsed.get("answer") == 410 and parsed.get("ok") is True and parsed.get("items") == [1, 2, 3])
        json_score = 1.0 if strict and payload_ok else (0.55 if payload_ok else 0.25)
        results.append(
            ProbeResult(
                category=self.category,
                name="json_contract",
                score=json_score,
                status=status_for_score(json_score),
                detail="The endpoint returned strict parseable JSON." if json_score >= 0.8 else "The endpoint wrapped, malformed, or changed the requested JSON payload.",
                sample=json_reply.text,
                evidence={"parsed": parsed, "strict_object": strict, "raw_type": json_reply.raw_type},
            )
        )

        usage_present = any(reply.usage is not None for reply in (marker_a, marker_b, json_reply))
        usage_score = 0.85 if usage_present else 0.35
        results.append(
            ProbeResult(
                category=self.category,
                name="usage_surface",
                score=usage_score,
                status=status_for_score(usage_score),
                detail="At least one protocol probe exposed token usage metadata." if usage_present else "Protocol probes did not expose usage metadata through the current adapter.",
                evidence={
                    "marker_a_usage": marker_a.usage is not None,
                    "marker_b_usage": marker_b.usage is not None,
                    "json_usage": json_reply.usage is not None,
                },
            )
        )
        return results
