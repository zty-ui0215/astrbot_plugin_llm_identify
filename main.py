from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from typing import Any, Awaitable, Callable

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

try:
    from quart import request as quart_request
except Exception:  # pragma: no cover - AstrBot runtime provides quart for page APIs.
    quart_request = None

try:
    from .llm_identify.adapters.base import GenerateAdapter
    from .llm_identify.adapters.astrbot import reply_from_astrbot_response
    from .llm_identify.adapters.direct_openai import DirectOpenAICompatibleAdapter
    from .llm_identify.capture import TraceStore
    from .llm_identify.engine import AuditEngine, AuditOptions
    from .llm_identify.models import AuditReport, ModelReply
    from .llm_identify.scoring import format_text_report
    from .llm_identify.utils import detect_model_family
except ImportError:
    from llm_identify.adapters.base import GenerateAdapter
    from llm_identify.adapters.astrbot import reply_from_astrbot_response
    from llm_identify.adapters.direct_openai import DirectOpenAICompatibleAdapter
    from llm_identify.capture import TraceStore
    from llm_identify.engine import AuditEngine, AuditOptions
    from llm_identify.models import AuditReport, ModelReply
    from llm_identify.scoring import format_text_report
    from llm_identify.utils import detect_model_family


PLUGIN_NAME = "astrbot_plugin_llm_identify"
PAGE_API_PREFIX = f"/{PLUGIN_NAME}/page"


@register(
    "llm_identify",
    "Codex",
    "Probabilistic LLM endpoint audit for protocol behavior, token accounting, fingerprinting, and relay risk.",
    "0.5.0",
)
class LLMIdentifyPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config or {}
        self.timeout = self._cfg_int("default_timeout", 60, 5, 300)
        self.page_provider_id = str(self.config.get("page_provider_id", "") or "").strip()
        self.enable_protocol_probe = self._cfg_bool("enable_protocol_probe", True)
        self.enable_token_probe = self._cfg_bool("enable_token_probe", False)
        self.enable_context_probe = self._cfg_bool("enable_context_probe", False)
        self.enable_fingerprint_probe = self._cfg_bool("enable_fingerprint_probe", False)
        self.fingerprint_profile = str(self.config.get("fingerprint_profile", "standard") or "standard").strip().lower()
        self.fingerprint_repeats = self._cfg_int("fingerprint_repeats", 3, 1, 8)
        self.enable_auxiliary_llm_judge = self._cfg_bool("enable_auxiliary_llm_judge", False)
        self.auxiliary_judge_provider_id = str(self.config.get("auxiliary_judge_provider_id", "") or "").strip()
        self.strict_mode = self._cfg_bool("strict_mode", False)
        self.last_report: AuditReport | None = None
        self._running = False

    async def initialize(self):
        self._register_page_api_if_available()
        logger.info("[LLMIdentify] plugin initialized")

    @filter.command("llmid")
    async def llmid(self, event: AstrMessageEvent):
        """Audit the current conversation provider. Usage: /llmid, /llmid full, /llmid help"""
        mode = self._parse_mode(event.message_str or "")
        if mode == "help":
            yield event.plain_result(
                "LLM Identify commands:\n"
                "- /llmid: run a quick protocol audit for the current provider\n"
                "- /llmid full: run protocol, token-accounting, and fingerprint audits\n"
                "- /llmid help: show this help\n\n"
                "Open the LLM Identify panel from the AstrBot plugin extension page for the web UI."
            )
            return

        yield event.plain_result("Starting LLM endpoint audit. Quick mode usually takes 15-45 seconds; full mode runs token and fingerprint probes and can take longer.")
        report = await self.run_detection(event, full=mode == "full")
        yield event.plain_result(format_text_report(report))

    async def run_detection(self, event: AstrMessageEvent | None = None, *, full: bool = False) -> AuditReport:
        if self._running:
            raise RuntimeError("An audit is already running. Try again after it completes.")
        self._running = True
        try:
            provider_id = await self._get_provider_id(event)
            if not provider_id:
                raise RuntimeError("No usable provider was found. Use /llmid in a chat or set page_provider_id in plugin config.")
            claimed_model = await self._get_claimed_model(provider_id)

            async def generate(prompt: str, **kwargs: Any) -> ModelReply:
                return await asyncio.wait_for(self._ask_current_model(provider_id, prompt, **kwargs), timeout=self.timeout)

            adapter = GenerateAdapter(
                adapter_type="astrbot",
                provider_id=provider_id,
                claimed_model=claimed_model,
                generate_fn=generate,
                trace_store=TraceStore(),
            )
            report = await AuditEngine(adapter, self._audit_options(full=full)).run()
            self.last_report = report
            return report
        finally:
            self._running = False

    async def run_direct_openai_detection(self, payload: dict[str, Any]) -> AuditReport:
        if self._running:
            raise RuntimeError("An audit is already running. Try again after it completes.")
        base_url = str(payload.get("base_url") or "").strip()
        api_key = str(payload.get("api_key") or "").strip()
        model = str(payload.get("model") or "").strip()
        if not base_url:
            raise RuntimeError("Direct API Base URL is required.")
        if not api_key:
            raise RuntimeError("Direct API Key is required.")
        if not model:
            raise RuntimeError("Direct API Model is required.")
        self._running = True
        try:
            client = DirectOpenAICompatibleAdapter(base_url=base_url, api_key=api_key, model=model, timeout=self.timeout)

            async def generate(prompt: str, **kwargs: Any) -> ModelReply:
                return await asyncio.wait_for(client.generate(prompt, **kwargs), timeout=self.timeout)

            adapter = GenerateAdapter(
                adapter_type="direct_openai_compatible",
                provider_id=f"direct-openai-compatible:{self._safe_endpoint_label(base_url)}",
                claimed_model=model,
                generate_fn=generate,
                trace_store=TraceStore(),
            )
            report = await AuditEngine(adapter, self._audit_options(full=bool(payload.get("full", True)))).run()
            self.last_report = report
            return report
        finally:
            self._running = False

    async def _ask_current_model(self, provider_id: str, prompt: str, **kwargs: Any) -> ModelReply:
        llm_generate = getattr(self.context, "llm_generate", None)
        if not callable(llm_generate):
            raise RuntimeError("The current AstrBot context does not support llm_generate.")
        response = await llm_generate(prompt=prompt, chat_provider_id=provider_id, **kwargs)
        return reply_from_astrbot_response(response)

    def _audit_options(self, *, full: bool) -> AuditOptions:
        return AuditOptions(
            enable_protocol_probe=self.enable_protocol_probe,
            enable_token_probe=full or self.enable_token_probe,
            enable_context_probe=self.enable_context_probe,
            enable_fingerprint_probe=full or self.enable_fingerprint_probe,
            fingerprint_profile=self.fingerprint_profile,
            fingerprint_repeats=self.fingerprint_repeats,
            enable_auxiliary_llm_judge=self.enable_auxiliary_llm_judge,
            auxiliary_judge_fn=self._auxiliary_judge if self.enable_auxiliary_llm_judge else None,
            strict_mode=self.strict_mode,
        )

    async def _auxiliary_judge(self, prompt: str) -> str:
        provider_id = self.auxiliary_judge_provider_id or self.page_provider_id or await self._get_provider_id(None)
        if not provider_id:
            raise RuntimeError("No auxiliary judge provider is configured or discoverable.")
        reply = await self._ask_current_model(provider_id, prompt, temperature=0.0)
        return reply.text

    async def _get_provider_id(self, event: AstrMessageEvent | None = None) -> str | None:
        provider_getter = getattr(self.context, "get_current_chat_provider_id", None)
        umo = getattr(event, "unified_msg_origin", None) if event is not None else None
        if umo and callable(provider_getter):
            for args, kwargs in [([], {"umo": umo}), ([umo], {})]:
                try:
                    value = provider_getter(*args, **kwargs)
                    if hasattr(value, "__await__"):
                        value = await value
                    if value:
                        return str(value)
                except TypeError:
                    continue
                except Exception:
                    logger.exception("[LLMIdentify] failed to get current chat provider id")
                    return None
        if self.page_provider_id:
            return self.page_provider_id
        using_provider = getattr(self.context, "get_using_provider", None)
        if callable(using_provider):
            for args in ([umo], []):
                try:
                    provider = using_provider(*args)
                    if hasattr(provider, "__await__"):
                        provider = await provider
                    provider_id = self._extract_provider_id(provider)
                    if provider_id:
                        return provider_id
                except TypeError:
                    continue
                except Exception:
                    logger.debug("[LLMIdentify] get_using_provider fallback failed", exc_info=True)
                    break
        all_providers = getattr(self.context, "get_all_providers", None)
        if callable(all_providers):
            try:
                providers = all_providers()
                if hasattr(providers, "__await__"):
                    providers = await providers
                for provider in providers or []:
                    provider_id = self._extract_provider_id(provider)
                    if provider_id:
                        return provider_id
            except Exception:
                logger.debug("[LLMIdentify] get_all_providers fallback failed", exc_info=True)
        return None

    async def _get_claimed_model(self, provider_id: str) -> str:
        provider = None
        getter = getattr(self.context, "get_provider_by_id", None)
        if callable(getter):
            try:
                provider = getter(provider_id)
                if hasattr(provider, "__await__"):
                    provider = await provider
            except Exception:
                provider = None
        return self._extract_provider_model(provider) or provider_id or "unknown"

    def _register_page_api_if_available(self) -> None:
        register_web_api = getattr(self.context, "register_web_api", None)
        if not callable(register_web_api):
            logger.info("[LLMIdentify] current AstrBot version does not expose register_web_api")
            return
        routes: list[tuple[str, Callable[..., Awaitable[dict[str, Any]]], list[str], str]] = [
            ("/status", self.page_status, ["GET"], "LLM Identify page status"),
            ("/detect", self.page_detect, ["POST"], "LLM Identify run detection"),
        ]
        for path, handler, methods, desc in routes:
            register_web_api(f"{PAGE_API_PREFIX}{path}", handler, methods, desc)
        logger.info("[LLMIdentify] page api registered at %s", PAGE_API_PREFIX)

    async def page_status(self) -> dict[str, Any]:
        provider_id = await self._get_provider_id(None)
        claimed_model = await self._get_claimed_model(provider_id) if provider_id else "unknown"
        return self._ok(
            {
                "running": self._running,
                "provider_id": provider_id or "unknown",
                "claimed_model": claimed_model,
                "model_family_guess": detect_model_family(claimed_model, provider_id or ""),
                "config": {
                    "timeout": self.timeout,
                    "page_provider_id": self.page_provider_id,
                    "enable_protocol_probe": self.enable_protocol_probe,
                    "enable_token_probe": self.enable_token_probe,
                    "enable_context_probe": self.enable_context_probe,
                    "enable_fingerprint_probe": self.enable_fingerprint_probe,
                    "fingerprint_profile": self.fingerprint_profile,
                    "fingerprint_repeats": self.fingerprint_repeats,
                    "enable_auxiliary_llm_judge": self.enable_auxiliary_llm_judge,
                    "auxiliary_judge_provider_id": self.auxiliary_judge_provider_id,
                    "strict_mode": self.strict_mode,
                },
                "last_report": self._report_payload(self.last_report),
            }
        )

    async def page_detect(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            payload = await self._extract_page_payload(*args, **kwargs)
            mode = str(payload.get("mode") or "astrbot").strip().lower()
            full = bool(payload.get("full", mode.endswith("_full")))
            if mode.startswith("direct_openai"):
                payload["full"] = full
                report = await self.run_direct_openai_detection(payload)
            else:
                report = await self.run_detection(None, full=full)
            return self._ok({"report": self._report_payload(report)})
        except Exception as exc:
            logger.warning("[LLMIdentify] page detect failed: %s", exc, exc_info=True)
            return self._error(str(exc))

    def _report_payload(self, report: AuditReport | None) -> dict[str, Any] | None:
        if report is None:
            return None
        payload = asdict(report)
        payload["text"] = format_text_report(report)
        return payload

    @staticmethod
    def _ok(data: Any = None) -> dict[str, Any]:
        return {"success": True, "data": data, "ts": int(time.time())}

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {"success": False, "error": str(message), "ts": int(time.time())}

    async def _extract_page_payload(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if quart_request is not None:
            try:
                payload = await quart_request.get_json(silent=True)
                if isinstance(payload, dict):
                    return payload
            except Exception:
                pass
        candidates = list(args) + list(kwargs.values())
        for candidate in candidates:
            data = await self._payload_from_candidate(candidate)
            if data is not None:
                return data
        return dict(kwargs) if kwargs else {}

    async def _payload_from_candidate(self, candidate: Any) -> dict[str, Any] | None:
        if candidate is None:
            return None
        if isinstance(candidate, dict):
            return candidate
        json_getter = getattr(candidate, "json", None)
        if callable(json_getter):
            try:
                value = json_getter()
                if hasattr(value, "__await__"):
                    value = await value
                if isinstance(value, dict):
                    return value
            except Exception:
                pass
        body = getattr(candidate, "body", None)
        if body is not None:
            if hasattr(body, "__await__"):
                body = await body
            if isinstance(body, bytes):
                body = body.decode("utf-8", errors="replace")
            if isinstance(body, str) and body.strip():
                try:
                    parsed = __import__("json").loads(body)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    return None
        return None

    @staticmethod
    def _safe_endpoint_label(base_url: str) -> str:
        value = base_url.strip().replace("https://", "").replace("http://", "")
        return value.split("/", 1)[0] or "custom-endpoint"

    @staticmethod
    def _extract_provider_id(provider: Any) -> str | None:
        if provider is None:
            return None
        if isinstance(provider, str):
            return provider
        for attr in ("id", "provider_id", "name"):
            value = getattr(provider, attr, None)
            if value:
                return str(value)
        config = getattr(provider, "provider_config", None)
        if isinstance(config, dict):
            value = config.get("id") or config.get("name")
            if value:
                return str(value)
        meta = getattr(provider, "meta", None)
        if callable(meta):
            try:
                value = getattr(meta(), "id", None)
                if value:
                    return str(value)
            except Exception:
                return None
        return None

    @staticmethod
    def _extract_provider_model(provider: Any) -> str | None:
        if provider is None:
            return None
        get_model = getattr(provider, "get_model", None)
        if callable(get_model):
            try:
                model = get_model()
                if model:
                    return str(model)
            except Exception:
                pass
        for attr in ("model", "model_name"):
            value = getattr(provider, attr, None)
            if value:
                return str(value)
        config = getattr(provider, "provider_config", None)
        if isinstance(config, dict):
            for key in ("model", "model_name", "model_config"):
                value = config.get(key)
                if isinstance(value, str) and value:
                    return value
        return None

    def _cfg_bool(self, key: str, default: bool) -> bool:
        value = self.config.get(key, default)
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "on", "enable", "enabled"}
        return bool(value)

    def _cfg_int(self, key: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(self.config.get(key, default))
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(maximum, value))

    @staticmethod
    def _parse_mode(text: str) -> str:
        normalized = text.lower().strip()
        if normalized in {"/llmid help", "llmid help", "help"}:
            return "help"
        if normalized in {"/llmid full", "llmid full", "full"}:
            return "full"
        return "quick"

    async def terminate(self):
        logger.info("[LLMIdentify] plugin terminated")




