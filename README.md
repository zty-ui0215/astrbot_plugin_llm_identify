# LLM Identify

LLM Identify is an AstrBot plugin for probabilistic black-box audits of LLM endpoints. It is designed for relay, proxy, wrapper, and OpenAI-compatible endpoint checks. The plugin reports evidence, not proof: model identity can be spoofed, routed, cached, or wrapped by the provider.

## Current Architecture

The plugin uses an engine-first layout:

- `llm_identify/adapters`: AstrBot and direct OpenAI-compatible adapters.
- `llm_identify/probes`: protocol, token, and fingerprint probe packs.
- `llm_identify/capture`: trace capture and summary helpers.
- `llm_identify/features`: token and fingerprint feature extraction.
- `llm_identify/scoring`: evidence fusion, fingerprint fusion, and report formatting.
- `main.py`: thin AstrBot integration layer.

Legacy files under `core/` are no longer used by the new entrypoint.

## Commands

```text
/llmid
/llmid full
/llmid help
```

- `/llmid` runs a quick protocol audit.
- `/llmid full` runs protocol, token-accounting, and fingerprint audits.
- The web panel also supports direct OpenAI-compatible endpoint audits.

## Token Audit

Full mode runs a dedicated token audit with synthetic prompts only. It checks usage availability, input-token monotonicity, slope plausibility, constant-count anomalies, repeated-prefix cache signals, Unicode behavior, and output-token consistency.

## Fingerprint Audit

Full mode also runs cross-validated fingerprint detection. The default path is deterministic and dependency-light. When `enable_auxiliary_llm_judge` is enabled, AstrBot can call a configured auxiliary provider for bounded deep matching over extracted feature summaries.

Fingerprint methods currently include:

- LLMmap-style active behavioral probes.
- knowledge-boundary and uncertainty probes.
- visible reasoning-structure probes that do not request hidden chain-of-thought.
- refusal and alignment-style probes.
- tokenizer/Unicode behavior probes.
- stream/timing surface evidence when adapters expose it.
- optional auxiliary-LLM judging over extracted method summaries.

The fusion layer requires cross-method agreement before raising confidence. Disagreement increases `spoofing_risk` instead of forcing a single winner.


## Rule And Database Files

Fingerprint probes and executable scoring markers are loaded from `llm_identify/data/fingerprint_rules.json`. The current rule file covers all documented detection method families: LLMmap-style behavior, prompt probes, refusal style, embedding fingerprint placeholders, knowledge boundary, reasoning structure, tokenizer/Unicode, sampling distribution, API sidechannel, mixed routing, context truth, adversarial robustness, and inference stack signals.

Rule and database matching is executable: feature extractors load these files at runtime, and the fusion layer uses `fingerprint_database.json` to promote exact public model candidates under matching family clusters. Optional user-populated databases live under `llm_identify/data/`:

- `fingerprint_database.json`
- `knowledge_boundary_database.json`
- `embedding_fingerprint_database.json`
- `drift_database.json`
- `static_scan_database.json`
- `inference_stack_database.json`
- `adversarial_database.json`

`fingerprint_database.json` is seeded with public LLMmap supported-model identifiers and external corpus references. The other databases are intentionally valid but mostly empty so project-specific baselines can be added later without changing code.
## Page API

```text
GET  /astrbot_plugin_llm_identify/page/status
POST /astrbot_plugin_llm_identify/page/detect
```

The report shape includes:

- `provider_id`
- `claimed_model`
- `adapter_type`
- `model_family_guess`
- `provider_probabilities`
- `protocol_score`
- `token_truth_score`
- `context_truth_score`
- `fingerprint_score`
- `fingerprint_confidence`
- `fingerprint_candidates`
- `fingerprint_method_scores`
- `fingerprint_disagreement`
- `spoofing_risk`
- `proxy_probability`
- `mixture_probability`
- `confidence`
- `findings`
- `probe_results`
- `trace_summary`
- `created_at`

## Configuration

- `default_timeout`: timeout in seconds for each probe request.
- `page_provider_id`: provider ID used by the web panel.
- `enable_protocol_probe`: enable protocol behavior probes.
- `enable_token_probe`: enable token probes by default; full mode always enables them.
- `enable_fingerprint_probe`: enable fingerprint probes by default; full mode always enables them.
- `fingerprint_profile`: `light`, `standard`, or `exhaustive`.
- `fingerprint_repeats`: repeat count for each fingerprint probe.
- `enable_auxiliary_llm_judge`: enable optional auxiliary-LLM judging over extracted fingerprint summaries.
- `auxiliary_judge_provider_id`: optional AstrBot provider ID used for auxiliary judging.
- `enable_context_probe`: reserved for future context sentinel probes.
- `strict_mode`: apply a more conservative penalty for failed probes.

## Limits

This plugin uses observable behavior and metadata to estimate risk. It cannot prove the true underlying model. Relays can rewrite usage, cache responses, change system prompts, spoof model style, or route traffic dynamically, so repeat audits and provider-side logs remain important.

