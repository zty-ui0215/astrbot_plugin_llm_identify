from __future__ import annotations

import unittest
from types import SimpleNamespace

from llm_identify.adapters.astrbot import reply_from_astrbot_response
from llm_identify.adapters.direct_openai import _reply_from_chat_completion
from llm_identify.adapters.trace_normalization import normalize_headers, normalize_sse_events, normalize_usage


class ProviderTraceAdapterTests(unittest.TestCase):
    def test_openai_chat_completion_normalizes_usage_headers_and_cache_details(self) -> None:
        reply = _reply_from_chat_completion(
            {
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "model": "gpt-test",
                "choices": [{"message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 14,
                    "completion_tokens": 2,
                    "total_tokens": 16,
                    "prompt_tokens_details": {"cached_tokens": 8},
                    "completion_tokens_details": {"reasoning_tokens": 1},
                },
            },
            raw_type="OpenAIChatCompletionDirect",
            transport_meta={"headers": {"x-request-id": "req-1", "authorization": "Bearer secret", "x-ratelimit-limit-requests": "100"}},
        )
        self.assertEqual(reply.text, "OK")
        self.assertEqual(reply.usage.input, 14)
        self.assertEqual(reply.usage.output, 2)
        self.assertEqual(reply.meta["normalized_usage"]["provider_shape"], "openai_chat")
        self.assertEqual(reply.meta["normalized_usage"]["details"]["input_cached_tokens"], 8)
        self.assertEqual(reply.meta["normalized_headers"]["signals"]["request_id"], "req-1")
        self.assertNotIn("authorization", {key.lower() for key in reply.meta["normalized_headers"]["safe"]})

    def test_openai_response_object_normalizes_input_output_tokens(self) -> None:
        reply = _reply_from_chat_completion(
            {
                "id": "resp-1",
                "object": "response",
                "model": "gpt-response",
                "status": "completed",
                "output": [{"type": "message", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": "done"}]}],
                "usage": {"input_tokens": 21, "output_tokens": 3, "total_tokens": 24, "output_token_details": {"reasoning_tokens": 2}},
            },
            raw_type="OpenAIChatCompletionDirect",
            transport_meta={"headers": {"request-id": "resp-request"}},
        )
        self.assertEqual(reply.raw_type, "OpenAIResponseDirect")
        self.assertEqual(reply.text, "done")
        self.assertEqual(reply.usage.total, 24)
        self.assertEqual(reply.meta["provider_trace"]["usage_shape"], "openai_responses_or_anthropic")
        self.assertEqual(reply.meta["normalized_usage"]["details"]["output_reasoning_tokens"], 2)

    def test_gemini_usage_and_sse_events_are_normalized(self) -> None:
        usage, meta = normalize_usage({"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15, "cachedContentTokenCount": 4})
        self.assertEqual(usage.input, 10)
        self.assertEqual(meta["provider_shape"], "gemini")
        self.assertEqual(meta["details"]["cachedContentTokenCount"], 4)
        sse = normalize_sse_events(["message_start", "content_block_delta", "usage_delta", "[DONE]", "malformed"])
        self.assertTrue(sse["done_seen"])
        self.assertTrue(sse["usage_event_seen"])
        self.assertEqual(sse["malformed_count"], 1)

    def test_header_normalization_redacts_sensitive_values_and_extracts_provider_hints(self) -> None:
        headers = normalize_headers({"Authorization": "Bearer secret", "x-goog-request-id": "g-1", "content-type": "application/json"})
        self.assertTrue(headers["present"])
        self.assertNotIn("Authorization", headers["safe"])
        self.assertEqual(headers["signals"]["request_id"], "g-1")
        self.assertEqual(headers["signals"]["provider_hint"], "google_like")

    def test_astrbot_response_normalizes_raw_usage_metadata(self) -> None:
        raw = SimpleNamespace(
            id="raw-1",
            modelVersion="gemini-test",
            usageMetadata={"promptTokenCount": 18, "candidatesTokenCount": 6, "totalTokenCount": 24},
            finish_reason="STOP",
        )
        response = SimpleNamespace(completion_text="OK", raw_completion=raw)
        reply = reply_from_astrbot_response(response)
        self.assertEqual(reply.text, "OK")
        self.assertEqual(reply.usage.input, 18)
        self.assertEqual(reply.meta["normalized_usage"]["provider_shape"], "gemini")
        self.assertEqual(reply.meta["provider_trace"]["model"], "gemini-test")


if __name__ == "__main__":
    unittest.main()
