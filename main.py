from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from pathlib import Path
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
    from .llm_identify.contribution.evidence_schema import build_evidence_package
    from .llm_identify.contribution.exporter import ContributionExporter
    from .llm_identify.contribution.github_issue_submitter import DEFAULT_ISSUE_URL, build_github_issue_url
    from .llm_identify.contribution.official_endpoint_detector import OfficialEndpoint, detect_official_endpoint, detect_official_provider_endpoint
    from .llm_identify.dynamic_fingerprint import build_feature_vector
    from .llm_identify.engine import AuditEngine, AuditOptions
    from .llm_identify.evidence import AUXILIARY_JUDGE_ITEMS
    from .llm_identify.i18n import normalize_language, t
    from .llm_identify.models import AuditReport, ModelReply
    from .llm_identify.scoring import format_text_report
    from .llm_identify.utils import detect_model_family
except ImportError:
    from llm_identify.adapters.base import GenerateAdapter
    from llm_identify.adapters.astrbot import reply_from_astrbot_response
    from llm_identify.adapters.direct_openai import DirectOpenAICompatibleAdapter
    from llm_identify.capture import TraceStore
    from llm_identify.contribution.evidence_schema import build_evidence_package
    from llm_identify.contribution.exporter import ContributionExporter
    from llm_identify.contribution.github_issue_submitter import DEFAULT_ISSUE_URL, build_github_issue_url
    from llm_identify.contribution.official_endpoint_detector import OfficialEndpoint, detect_official_endpoint, detect_official_provider_endpoint
    from llm_identify.dynamic_fingerprint import build_feature_vector
    from llm_identify.engine import AuditEngine, AuditOptions
    from llm_identify.evidence import AUXILIARY_JUDGE_ITEMS
    from llm_identify.i18n import normalize_language, t
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
        self.auxiliary_judge_mode = self._cfg_choice("auxiliary_judge_mode", "astrbot", {"astrbot", "openai_compatible"})
        self.auxiliary_judge_provider_id = str(self.config.get("auxiliary_judge_provider_id", "") or "").strip()
        self.auxiliary_judge_base_url = str(self.config.get("auxiliary_judge_base_url", "") or "").strip()
        self.auxiliary_judge_api_key = str(self.config.get("auxiliary_judge_api_key", "") or "").strip()
        self.auxiliary_judge_model = str(self.config.get("auxiliary_judge_model", "") or "").strip()
        self.enable_voluntary_data_reporting = self._cfg_bool("enable_voluntary_data_reporting", False)
        self.contribution_export_dir = str(self.config.get("contribution_export_dir", "tmp/contributions") or "tmp/contributions").strip()
        self.contribution_issue_url = str(self.config.get("contribution_issue_url", DEFAULT_ISSUE_URL) or DEFAULT_ISSUE_URL).strip()
        if self.contribution_issue_url.rstrip("/") == "https://github.com/zty-ui0215/llm-identify-trusted-references/issues/new":
            self.contribution_issue_url = DEFAULT_ISSUE_URL
        self.strict_mode = self._cfg_bool("strict_mode", False)
        self.default_language = normalize_language(self.config.get("language") or self.config.get("locale"))
        self.last_report: AuditReport | None = None
        self.last_official_endpoint: OfficialEndpoint | None = None
        self.last_contribution_package: dict[str, Any] | None = None
        self.last_contribution_report_created_at: int | None = None
        self._running = False
        self._audit_started_at: int | None = None
        self._active_audit_task: asyncio.Task[Any] | None = None
        self._active_trace_store: TraceStore | None = None
        self._auxiliary_direct_client: DirectOpenAICompatibleAdapter | None = None

    async def initialize(self):
        self._register_page_api_if_available()
        logger.info("[LLMIdentify] plugin initialized")

    @filter.command("llmid")
    async def llmid(self, event: AstrMessageEvent):
        """Audit the current conversation provider. Usage: /llmid, /llmid full, /llmid help"""
        mode, language = self._parse_mode(event.message_str or "")
        if mode == "help":
            yield event.plain_result(t("cmd.help", language))
            return

        yield event.plain_result(t("cmd.start", language))
        report = await self.run_detection(event, full=mode == "full", language=language)
        yield event.plain_result(format_text_report(report, language))

    async def run_detection(self, event: AstrMessageEvent | None = None, *, full: bool = False, language: str | None = None, provider_id: str | None = None) -> AuditReport:
        if self._running:
            raise RuntimeError(t("error.audit_running", language or self.default_language))
        self._running = True
        self._audit_started_at = int(time.time())
        active_task = asyncio.current_task()
        self._active_audit_task = active_task
        self._clear_contribution_candidate()
        try:
            provider_id = str(provider_id or "").strip() or await self._get_provider_id(event)
            if not provider_id:
                raise RuntimeError(t("error.no_provider", language or self.default_language))
            provider = await self._get_provider_by_id(provider_id)
            claimed_model = self._extract_provider_model(provider) or provider_id or "unknown"

            async def generate(prompt: str, **kwargs: Any) -> ModelReply:
                return await asyncio.wait_for(self._ask_current_model(provider_id, prompt, **kwargs), timeout=self.timeout)

            trace_store = TraceStore()
            self._active_trace_store = trace_store
            adapter = GenerateAdapter(
                adapter_type="astrbot",
                provider_id=provider_id,
                claimed_model=claimed_model,
                generate_fn=generate,
                trace_store=trace_store,
            )
            report = await AuditEngine(adapter, self._audit_options(full=full, language=language)).run()
            self.last_report = report
            if full:
                self._prepare_contribution_candidate(
                    official_endpoint=detect_official_provider_endpoint(provider),
                    report=report,
                    traces=trace_store.traces,
                )
            return report
        finally:
            self._finish_active_audit(active_task)

    async def run_direct_openai_detection(self, payload: dict[str, Any], *, language: str | None = None) -> AuditReport:
        if self._running:
            raise RuntimeError(t("error.audit_running", language or self.default_language))
        base_url = str(payload.get("base_url") or "").strip()
        api_key = str(payload.get("api_key") or "").strip()
        model = str(payload.get("model") or "").strip()
        if not base_url:
            raise RuntimeError(t("error.base_url_required", language or self.default_language))
        if not api_key:
            raise RuntimeError(t("error.api_key_required", language or self.default_language))
        if not model:
            raise RuntimeError(t("error.model_required", language or self.default_language))
        self._running = True
        self._audit_started_at = int(time.time())
        active_task = asyncio.current_task()
        self._active_audit_task = active_task
        self._clear_contribution_candidate()
        try:
            client = DirectOpenAICompatibleAdapter(base_url=base_url, api_key=api_key, model=model, timeout=self.timeout)

            async def generate(prompt: str, **kwargs: Any) -> ModelReply:
                return await asyncio.wait_for(client.generate(prompt, **kwargs), timeout=self.timeout)

            trace_store = TraceStore()
            self._active_trace_store = trace_store
            adapter = GenerateAdapter(
                adapter_type="direct_openai_compatible",
                provider_id=f"direct-openai-compatible:{self._safe_endpoint_label(base_url)}",
                claimed_model=model,
                generate_fn=generate,
                trace_store=trace_store,
                count_tokens_fn=client.count_tokens,
            )
            report = await AuditEngine(adapter, self._audit_options(full=bool(payload.get("full", True)), language=language)).run()
            self.last_report = report
            if bool(payload.get("full", True)):
                self._prepare_contribution_candidate(base_url=base_url, report=report, traces=trace_store.traces)
            return report
        finally:
            self._finish_active_audit(active_task)

    async def _ask_current_model(self, provider_id: str, prompt: str, **kwargs: Any) -> ModelReply:
        llm_generate = getattr(self.context, "llm_generate", None)
        if not callable(llm_generate):
            raise RuntimeError(t("error.context_generate", self.default_language))
        response = await llm_generate(prompt=prompt, chat_provider_id=provider_id, **kwargs)
        return reply_from_astrbot_response(response)

    def _audit_options(self, *, full: bool, language: str | None = None) -> AuditOptions:
        return AuditOptions(
            enable_protocol_probe=self.enable_protocol_probe,
            enable_token_probe=full or self.enable_token_probe,
            enable_context_probe=self.enable_context_probe,
            enable_fingerprint_probe=full or self.enable_fingerprint_probe,
            fingerprint_profile=self.fingerprint_profile,
            fingerprint_repeats=self.fingerprint_repeats,
            enable_auxiliary_llm_judge=self.enable_auxiliary_llm_judge,
            auxiliary_judge_fn=self._auxiliary_judge if self.enable_auxiliary_llm_judge else None,
            auxiliary_judge_model=self._auxiliary_judge_label(),
            strict_mode=self.strict_mode,
            language=normalize_language(language or self.default_language),
        )

    async def _auxiliary_judge(self, prompt: str) -> str:
        if self.auxiliary_judge_mode == "openai_compatible":
            client = self._get_auxiliary_direct_client()
            reply = await client.generate(prompt, temperature=0.0)
            return reply.text
        provider_id = self.auxiliary_judge_provider_id or self.page_provider_id or await self._get_provider_id(None)
        if not provider_id:
            raise RuntimeError(t("error.no_aux_judge", self.default_language))
        reply = await self._ask_current_model(provider_id, prompt, temperature=0.0)
        return reply.text

    def _get_auxiliary_direct_client(self) -> DirectOpenAICompatibleAdapter:
        if not self.auxiliary_judge_base_url:
            raise RuntimeError(t("error.base_url_required", self.default_language))
        if not self.auxiliary_judge_api_key:
            raise RuntimeError(t("error.api_key_required", self.default_language))
        if not self.auxiliary_judge_model:
            raise RuntimeError(t("error.model_required", self.default_language))
        if self._auxiliary_direct_client is None:
            self._auxiliary_direct_client = DirectOpenAICompatibleAdapter(
                base_url=self.auxiliary_judge_base_url,
                api_key=self.auxiliary_judge_api_key,
                model=self.auxiliary_judge_model,
                timeout=self.timeout,
            )
        return self._auxiliary_direct_client

    def _auxiliary_judge_label(self) -> str:
        if self.auxiliary_judge_mode == "openai_compatible":
            return self.auxiliary_judge_model or "openai-compatible"
        return self.auxiliary_judge_provider_id or self.page_provider_id or "astrbot-provider"

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
        provider = await self._get_provider_by_id(provider_id)
        return self._extract_provider_model(provider) or provider_id or "unknown"

    async def _get_provider_by_id(self, provider_id: str) -> Any:
        provider = None
        getter = getattr(self.context, "get_provider_by_id", None)
        if callable(getter):
            try:
                provider = getter(provider_id)
                if hasattr(provider, "__await__"):
                    provider = await provider
            except Exception:
                provider = None
        if provider is not None:
            return provider
        for candidate in await self._get_all_providers():
            if self._extract_provider_id(candidate) == provider_id:
                return candidate
        return None

    def _register_page_api_if_available(self) -> None:
        register_web_api = getattr(self.context, "register_web_api", None)
        if not callable(register_web_api):
            logger.info("[LLMIdentify] current AstrBot version does not expose register_web_api")
            return
        routes: list[tuple[str, Callable[..., Awaitable[dict[str, Any]]], list[str], str]] = [
            ("/status", self.page_status, ["GET"], "LLM Identify page status"),
            ("/detect", self.page_detect, ["POST"], "LLM Identify run detection"),
            ("/stop", self.page_stop, ["POST"], "LLM Identify stop active detection"),
            ("/settings", self.page_settings, ["POST"], "LLM Identify page settings"),
            ("/contribution", self.page_contribution, ["POST"], "LLM Identify voluntary contribution export"),
        ]
        for path, handler, methods, desc in routes:
            register_web_api(f"{PAGE_API_PREFIX}{path}", handler, methods, desc)
        logger.info("[LLMIdentify] page api registered at %s", PAGE_API_PREFIX)

    async def page_status(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = await self._extract_page_payload(*args, **kwargs)
        language = normalize_language(payload.get("language") or self.default_language)
        requested_provider_id = str(payload.get("provider_id") or "").strip()
        provider_id = requested_provider_id or await self._get_provider_id(None)
        claimed_model = await self._get_claimed_model(provider_id) if provider_id else "unknown"
        providers = await self._get_provider_options(selected_provider_id=provider_id)
        return self._ok(
            {
                "running": self._running,
                "audit_started_at": self._audit_started_at,
                "provider_id": provider_id or "unknown",
                "claimed_model": claimed_model,
                "model_family_guess": detect_model_family(claimed_model, provider_id or ""),
                "providers": providers,
                "config": self._public_config(),
                "contribution": self._contribution_status(),
                "last_report": self._report_payload(self.last_report, language),
            }
        )

    async def page_detect(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            payload = await self._extract_page_payload(*args, **kwargs)
            language = normalize_language(payload.get("language") or self.default_language)
            mode = str(payload.get("mode") or "astrbot").strip().lower()
            full = bool(payload.get("full", mode.endswith("_full")))
            if mode.startswith("direct_openai"):
                payload["full"] = full
                report = await self.run_direct_openai_detection(payload, language=language)
            else:
                provider_id = str(payload.get("provider_id") or "").strip() or None
                report = await self.run_detection(None, full=full, language=language, provider_id=provider_id)
            return self._ok(
                {
                    "report": self._report_payload(report, language),
                    "contribution": self._contribution_status(),
                }
            )
        except asyncio.CancelledError:
            return self._error("Audit stopped.")
        except Exception as exc:
            logger.warning("[LLMIdentify] page detect failed: %s", exc, exc_info=True)
            return self._error(str(exc))

    async def page_stop(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        task = self._active_audit_task
        stopped = bool(task is not None and not task.done())
        if stopped:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.debug("[LLMIdentify] active audit finished with an error while stopping", exc_info=True)
        self._clear_unfinished_audit_data()
        return self._ok({"stopped": stopped, "running": self._running})

    async def page_contribution(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            payload = await self._extract_page_payload(*args, **kwargs)
            action = str(payload.get("action") or "status").strip().lower()
            if action == "status":
                return self._ok(self._contribution_status())
            if not self.enable_voluntary_data_reporting:
                return self._error("Voluntary data reporting is disabled in plugin page settings.")
            if self.last_contribution_package is None:
                return self._error("No official-endpoint contribution candidate is available. Run a full audit with an official API provider first.")
            if action == "issue_url":
                return self._ok({"issue_url": build_github_issue_url(self.last_contribution_package, self.contribution_issue_url)})
            if action == "export":
                task_id = self.last_contribution_package.get("task_ref") or f"page-{int(time.time())}"
                path = ContributionExporter(self._contribution_export_root()).export_json(str(task_id), self.last_contribution_package)
                return self._ok({"path": str(path), "package": self.last_contribution_package})
            if action == "push":
                task_id = self.last_contribution_package.get("task_ref") or f"page-{int(time.time())}"
                path = ContributionExporter(self._contribution_export_root()).export_json(str(task_id), self.last_contribution_package)
                return self._ok({"path": str(path), "issue_url": build_github_issue_url(self.last_contribution_package, self.contribution_issue_url)})
            if action == "package":
                return self._ok({"package": self.last_contribution_package})
            return self._error(f"Unsupported contribution action: {action}")
        except Exception as exc:
            logger.warning("[LLMIdentify] contribution action failed: %s", exc, exc_info=True)
            return self._error(str(exc))

    async def page_settings(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            payload = await self._extract_page_payload(*args, **kwargs)
            settings = self._sanitize_page_settings(payload)
            self._apply_page_settings(settings)
            await self._persist_config_best_effort()
            return self._ok({"config": self._public_config()})
        except Exception as exc:
            logger.warning("[LLMIdentify] page settings update failed: %s", exc, exc_info=True)
            return self._error(str(exc))

    def _sanitize_page_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        mode = self._choice_value(payload.get("auxiliary_judge_mode"), self.auxiliary_judge_mode, {"astrbot", "openai_compatible"})
        settings: dict[str, Any] = {
            "enable_auxiliary_llm_judge": self._bool_value(payload.get("enable_auxiliary_llm_judge"), self.enable_auxiliary_llm_judge),
            "enable_voluntary_data_reporting": self._bool_value(payload.get("enable_voluntary_data_reporting"), self.enable_voluntary_data_reporting),
            "auxiliary_judge_mode": mode,
            "auxiliary_judge_provider_id": str(payload.get("auxiliary_judge_provider_id") or "").strip(),
            "auxiliary_judge_base_url": str(payload.get("auxiliary_judge_base_url") or "").strip(),
            "auxiliary_judge_model": str(payload.get("auxiliary_judge_model") or "").strip(),
        }
        api_key = str(payload.get("auxiliary_judge_api_key") or "").strip()
        if api_key:
            settings["auxiliary_judge_api_key"] = api_key
        if settings["enable_auxiliary_llm_judge"]:
            if mode == "astrbot" and not settings["auxiliary_judge_provider_id"] and not self.page_provider_id:
                raise RuntimeError(t("error.no_aux_judge", self.default_language))
            if mode == "openai_compatible":
                if not settings["auxiliary_judge_base_url"]:
                    raise RuntimeError(t("error.base_url_required", self.default_language))
                if not settings["auxiliary_judge_model"]:
                    raise RuntimeError(t("error.model_required", self.default_language))
                if not api_key and not self.auxiliary_judge_api_key:
                    raise RuntimeError(t("error.api_key_required", self.default_language))
        return settings

    def _apply_page_settings(self, settings: dict[str, Any]) -> None:
        self.enable_auxiliary_llm_judge = bool(settings["enable_auxiliary_llm_judge"])
        self.enable_voluntary_data_reporting = bool(settings["enable_voluntary_data_reporting"])
        self.auxiliary_judge_mode = str(settings["auxiliary_judge_mode"])
        self.auxiliary_judge_provider_id = str(settings["auxiliary_judge_provider_id"])
        self.auxiliary_judge_base_url = str(settings["auxiliary_judge_base_url"])
        self.auxiliary_judge_model = str(settings["auxiliary_judge_model"])
        if "auxiliary_judge_api_key" in settings:
            self.auxiliary_judge_api_key = str(settings["auxiliary_judge_api_key"])
        if not self.enable_voluntary_data_reporting:
            self._clear_contribution_candidate()
        self._auxiliary_direct_client = None
        for key, value in settings.items():
            self.config[key] = value

    def _public_config(self) -> dict[str, Any]:
        return {
            "timeout": self.timeout,
            "page_provider_id": self.page_provider_id,
            "enable_protocol_probe": self.enable_protocol_probe,
            "enable_token_probe": self.enable_token_probe,
            "enable_context_probe": self.enable_context_probe,
            "enable_fingerprint_probe": self.enable_fingerprint_probe,
            "fingerprint_profile": self.fingerprint_profile,
            "fingerprint_repeats": self.fingerprint_repeats,
            "enable_auxiliary_llm_judge": self.enable_auxiliary_llm_judge,
            "auxiliary_judge_mode": self.auxiliary_judge_mode,
            "auxiliary_judge_provider_id": self.auxiliary_judge_provider_id,
            "auxiliary_judge_base_url": self.auxiliary_judge_base_url,
            "auxiliary_judge_model": self.auxiliary_judge_model,
            "auxiliary_judge_has_api_key": bool(self.auxiliary_judge_api_key),
            "auxiliary_judge_items": list(AUXILIARY_JUDGE_ITEMS),
            "enable_voluntary_data_reporting": self.enable_voluntary_data_reporting,
            "contribution_export_dir": self.contribution_export_dir,
            "contribution_issue_url": self.contribution_issue_url,
            "strict_mode": self.strict_mode,
        }

    def _prepare_contribution_candidate(
        self,
        *,
        report: AuditReport,
        traces: list[Any],
        base_url: str | None = None,
        official_endpoint: OfficialEndpoint | None = None,
    ) -> None:
        if not self.enable_voluntary_data_reporting:
            self._clear_contribution_candidate()
            return
        endpoint = official_endpoint or detect_official_endpoint(base_url or "")
        if endpoint is None:
            self._clear_contribution_candidate()
            return
        task_id = f"page-{int(report.created_at or time.time())}-{endpoint.provider}-{report.claimed_model}"
        self.last_official_endpoint = endpoint
        self.last_contribution_package = build_evidence_package(
            task_id=task_id,
            report=asdict(report),
            feature_vector=build_feature_vector(report, traces),
            official_endpoint=endpoint,
            plugin_version="0.5.0",
        )
        self.last_contribution_report_created_at = int(report.created_at or 0)

    def _clear_contribution_candidate(self) -> None:
        self.last_official_endpoint = None
        self.last_contribution_package = None
        self.last_contribution_report_created_at = None

    def _finish_active_audit(self, task: asyncio.Task[Any] | None) -> None:
        if self._active_audit_task is not task:
            return
        self._active_audit_task = None
        self._active_trace_store = None
        self._audit_started_at = None
        self._running = False

    def _clear_unfinished_audit_data(self) -> None:
        if self._active_trace_store is not None:
            self._active_trace_store.traces.clear()
        self._active_trace_store = None
        self._active_audit_task = None
        self._audit_started_at = None
        self._running = False
        self._clear_contribution_candidate()

    def _contribution_status(self) -> dict[str, Any]:
        endpoint = self.last_official_endpoint
        available = self.enable_voluntary_data_reporting and self.last_contribution_package is not None
        return {
            "enabled": self.enable_voluntary_data_reporting,
            "available": available,
            "endpoint": asdict(endpoint) if endpoint else None,
            "report_created_at": self.last_contribution_report_created_at,
            "issue_url": build_github_issue_url(self.last_contribution_package, self.contribution_issue_url) if available else "",
            "export_dir": str(self._contribution_export_root()),
            "privacy": "Voluntary export only. Sanitized aggregate evidence excludes raw prompts, completions, API keys, headers, account identifiers, IPs, and private content.",
        }

    def _contribution_export_root(self) -> Path:
        path = Path(self.contribution_export_dir)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
        return path

    async def _persist_config_best_effort(self) -> None:
        for owner in (self.config, self.context):
            for method_name in ("save", "save_config", "update_config"):
                method = getattr(owner, method_name, None)
                if not callable(method):
                    continue
                try:
                    result = method(self.config) if method_name == "update_config" else method()
                    if hasattr(result, "__await__"):
                        await result
                    return
                except TypeError:
                    try:
                        result = method()
                        if hasattr(result, "__await__"):
                            await result
                        return
                    except Exception:
                        continue
                except Exception:
                    logger.debug("[LLMIdentify] config persistence hook %s failed", method_name, exc_info=True)
                    continue

    def _report_payload(self, report: AuditReport | None, language: str | None = None) -> dict[str, Any] | None:
        if report is None:
            return None
        payload = asdict(report)
        payload["text"] = format_text_report(report, language or self.default_language)
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
                query_args = getattr(quart_request, "args", None)
                if query_args:
                    return dict(query_args)
            except Exception:
                pass
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
        if isinstance(provider, tuple) and len(provider) == 2:
            key, provider_obj = provider
            return LLMIdentifyPlugin._extract_provider_id(provider_obj) or (str(key) if key else None)
        if isinstance(provider, dict):
            value = provider.get("id") or provider.get("provider_id") or provider.get("name")
            if value:
                return str(value)
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

    async def _get_all_providers(self) -> list[Any]:
        all_providers = getattr(self.context, "get_all_providers", None)
        if not callable(all_providers):
            return []
        try:
            providers = all_providers()
            if hasattr(providers, "__await__"):
                providers = await providers
            if isinstance(providers, dict):
                return list(providers.items())
            return list(providers or [])
        except Exception:
            logger.debug("[LLMIdentify] get_all_providers failed", exc_info=True)
            return []

    async def _get_provider_options(self, *, selected_provider_id: str | None = None) -> list[dict[str, str]]:
        options: list[dict[str, str]] = []
        seen: set[str] = set()
        for provider in await self._get_all_providers():
            provider_id = self._extract_provider_id(provider)
            if not provider_id or provider_id in seen:
                continue
            seen.add(provider_id)
            model = self._extract_provider_model(provider) or provider_id
            options.append(
                {
                    "id": provider_id,
                    "model": model,
                    "label": self._provider_label(provider_id, model),
                }
            )
        selected = str(selected_provider_id or "").strip()
        if selected and selected not in seen:
            model = await self._get_claimed_model(selected)
            options.insert(0, {"id": selected, "model": model, "label": self._provider_label(selected, model)})
        return options

    @staticmethod
    def _provider_label(provider_id: str, model: str) -> str:
        if model and model != provider_id:
            return f"{provider_id} ({model})"
        return provider_id or model or "unknown"

    @staticmethod
    def _extract_provider_model(provider: Any) -> str | None:
        if provider is None:
            return None
        if isinstance(provider, tuple) and len(provider) == 2:
            provider = provider[1]
        if isinstance(provider, dict):
            for key in ("model", "model_name", "model_config"):
                value = provider.get(key)
                if isinstance(value, str) and value:
                    return value
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
        return self._bool_value(value, default)

    def _cfg_int(self, key: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(self.config.get(key, default))
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(maximum, value))

    def _cfg_choice(self, key: str, default: str, allowed: set[str]) -> str:
        return self._choice_value(self.config.get(key), default, allowed)

    @staticmethod
    def _bool_value(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "on", "enable", "enabled"}
        return bool(value)

    @staticmethod
    def _choice_value(value: Any, default: str, allowed: set[str]) -> str:
        candidate = str(value or default).strip().lower()
        return candidate if candidate in allowed else default

    def _parse_mode(self, text: str) -> tuple[str, str]:
        normalized = text.lower().strip()
        parts = [part for part in normalized.replace("/llmid", " ").replace("llmid", " ").split() if part]
        language = next((part for part in parts if part in {"zh", "zh-cn", "cn", "ja", "ja-jp", "jp", "en", "en-us"}), self.default_language)
        if "help" in parts:
            return "help", language
        if "full" in parts:
            return "full", language
        return "quick", language

    async def terminate(self):
        logger.info("[LLMIdentify] plugin terminated")




