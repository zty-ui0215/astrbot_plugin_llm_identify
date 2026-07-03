from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..models import ModelReply, TokenSnapshot


class DirectOpenAICompatibleAdapter:
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout: int = 60) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def generate(self, prompt: str, **kwargs: Any) -> ModelReply:
        return await asyncio.to_thread(self._generate_sync, prompt, kwargs)

    def _generate_sync(self, prompt: str, kwargs: dict[str, Any]) -> ModelReply:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0),
        }
        for key in ("stop", "response_format", "tools", "tool_choice", "max_tokens"):
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]
        if kwargs.get("stream"):
            payload["stream"] = True
            payload["stream_options"] = {"include_usage": True}
            return self._request_stream(payload)
        data, meta = self._request_json(payload)
        return _reply_from_chat_completion(data, raw_type="OpenAIChatCompletionDirect", transport_meta=meta)

    def _request_json(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self._chat_completions_url(),
            data=body,
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                transport_meta = {
                    "http_status": response.status,
                    "headers": _safe_headers(response.headers.items()),
                }
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Direct OpenAI-compatible request failed: HTTP {exc.code}: {_shorten(detail)}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Direct OpenAI-compatible request failed: {exc.reason}") from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Direct OpenAI-compatible response is not JSON: {_shorten(raw)}") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Direct OpenAI-compatible response JSON is not an object")
        return parsed, transport_meta

    def _request_stream(self, payload: dict[str, Any]) -> ModelReply:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self._chat_completions_url(),
            data=body,
            headers={**self._headers(), "Accept": "text/event-stream"},
            method="POST",
        )
        chunks: list[dict[str, Any]] = []
        event_types: list[str] = []
        text_parts: list[str] = []
        usage: dict[str, Any] | None = None
        first_id = None
        first_model = None
        first_object = None
        finish_reason = None
        headers: dict[str, str] = {}
        http_status = None
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                http_status = response.status
                headers = _safe_headers(response.headers.items())
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if line.startswith("event:"):
                        event_types.append(line.split(":", 1)[1].strip())
                        continue
                    if not line.startswith("data:"):
                        continue
                    data_line = line.split(":", 1)[1].strip()
                    if data_line == "[DONE]":
                        event_types.append("[DONE]")
                        break
                    try:
                        chunk = json.loads(data_line)
                    except json.JSONDecodeError:
                        event_types.append("malformed")
                        continue
                    if not isinstance(chunk, dict):
                        continue
                    chunks.append(chunk)
                    event_types.append(str(chunk.get("object") or "chat.completion.chunk"))
                    first_id = first_id or chunk.get("id")
                    first_model = first_model or chunk.get("model")
                    first_object = first_object or chunk.get("object")
                    if isinstance(chunk.get("usage"), dict):
                        usage = chunk["usage"]
                    choices = chunk.get("choices")
                    if isinstance(choices, list) and choices:
                        choice = choices[0]
                        if isinstance(choice, dict):
                            finish_reason = choice.get("finish_reason") or finish_reason
                            delta = choice.get("delta")
                            if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                                text_parts.append(delta["content"])
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Direct OpenAI-compatible stream failed: HTTP {exc.code}: {_shorten(detail)}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Direct OpenAI-compatible stream failed: {exc.reason}") from exc
        meta: dict[str, Any] = {
            "response_type": "direct_openai_stream",
            "raw_type": "OpenAIChatCompletionStreamDirect",
            "id": str(first_id) if first_id else "",
            "model": str(first_model) if first_model else self.model,
            "object": str(first_object) if first_object else "chat.completion.chunk",
            "sse_event_types": event_types,
            "stream_chunk_count": len(chunks),
            "http_status": http_status,
            "headers": headers,
        }
        if finish_reason is not None:
            meta["finish_reason"] = str(finish_reason)
        if usage:
            meta["raw_usage"] = usage
            meta["raw_usage_type"] = "dict"
        return ModelReply(
            text="".join(text_parts),
            usage=_usage_from_raw(usage),
            response_id=str(first_id) if first_id else None,
            raw_type="OpenAIChatCompletionStreamDirect",
            meta=meta,
        )

    def _chat_completions_url(self) -> str:
        return urllib.parse.urljoin(self.base_url.rstrip("/") + "/", "chat/completions")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "astrbot-plugin-llm-identify/0.4",
        }


def _reply_from_chat_completion(data: dict[str, Any], *, raw_type: str, transport_meta: dict[str, Any]) -> ModelReply:
    choices = data.get("choices")
    first_choice = choices[0] if isinstance(choices, list) and choices else {}
    message = first_choice.get("message") if isinstance(first_choice, dict) else {}
    if not isinstance(message, dict):
        message = {}
    text = message.get("content") if isinstance(message.get("content"), str) else ""
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
    meta = _meta_from_chat_completion(data)
    meta.update(transport_meta)
    return ModelReply(
        text=text,
        usage=_usage_from_raw(usage),
        response_id=str(data.get("id")) if data.get("id") else None,
        raw_type=raw_type,
        meta=meta,
    )


def _meta_from_chat_completion(data: dict[str, Any]) -> dict[str, Any]:
    meta: dict[str, Any] = {"response_type": "direct_openai", "raw_type": "OpenAIChatCompletionDirect"}
    for key in ("id", "model", "object", "created"):
        if data.get(key) is not None:
            meta[key] = str(data[key])
    choices = data.get("choices")
    if isinstance(choices, list):
        meta["choices_count"] = len(choices)
        if choices and isinstance(choices[0], dict) and choices[0].get("finish_reason") is not None:
            meta["finish_reason"] = str(choices[0]["finish_reason"])
    usage = data.get("usage")
    if isinstance(usage, dict):
        meta["raw_usage"] = usage
        meta["raw_usage_type"] = "dict"
    return meta


def _usage_from_raw(raw_usage: dict[str, Any] | None) -> TokenSnapshot | None:
    if not raw_usage:
        return None

    def read(*names: str) -> int | None:
        for name in names:
            value = raw_usage.get(name)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        return None

    input_tokens = read("prompt_tokens", "input_tokens", "promptTokenCount")
    output_tokens = read("completion_tokens", "output_tokens", "candidatesTokenCount")
    total_tokens = read("total_tokens", "totalTokenCount")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return TokenSnapshot(input=input_tokens, output=output_tokens, total=total_tokens)


def _normalize_base_url(value: str) -> str:
    url = value.strip()
    if not url:
        raise ValueError("Direct API base_url is required")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    return url


def _safe_headers(items: Any) -> dict[str, str]:
    safe: dict[str, str] = {}
    for key, value in items:
        lowered = str(key).lower()
        if lowered in {"authorization", "cookie", "set-cookie"}:
            continue
        safe[str(key)] = str(value)
    return safe


def _shorten(value: str, limit: int = 500) -> str:
    text = value.strip()
    return text if len(text) <= limit else text[:limit] + "..."
