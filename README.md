# LLM Identify

LLM Identify is an AstrBot plugin for probabilistic black-box audits of LLM endpoints. It is designed for relay, proxy, wrapper, and OpenAI-compatible endpoint checks. The plugin reports evidence, not proof: model identity can be spoofed, routed, cached, or wrapped by the provider.

## Current Architecture

The plugin uses an engine-first layout:

- `llm_identify/adapters`: AstrBot and direct OpenAI-compatible adapters.
- `llm_identify/probes`: protocol, token, and fingerprint probe packs.
- `llm_identify/capture`: trace capture and summary helpers.
- `llm_identify/features`: token and fingerprint feature extraction.
- `llm_identify/evidence.py`: external evidence adapters for public fingerprint sources, trusted reference corpora, and LLM judges.
- `llm_identify/corpus.py`: embedded/local/remote trusted corpus loading with cache fallback and source attribution.
- `llm_identify/scoring`: evidence fusion, fingerprint fusion, and report formatting.
- `llm_identify/storage.py`: SQLite task/report/trace persistence with redaction.
- `llm_identify/tasks.py`: audit task and SSE event models.
- `llm_identify/branches.py`: branch-level evidence outputs for statistics, timing, context, tools, and prompt-injection signals.
- `llm_identify/cli.py`: standalone `python -m llm_identify.cli` automation entrypoint.
- `main.py`: AstrBot integration layer and task-backed plugin APIs.

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

## Trusted Reference Corpus

Full fingerprint audits load a compact embedded trusted reference corpus by default. The embedded corpus stays small and contains only stable provider-family aliases, protocol traits, trust-tier metadata, and source attribution. It is used as probabilistic evidence through `trusted_corpus:*` methods, not as an absolute identity authority.

Extended corpus data can be supplied through `trusted_corpus_sources` as local JSON files or HTTPS URLs, including GitHub raw URLs. Remote corpora are cached in `public_cache_dir`; if a remote source is unavailable, the cached copy is used and the report records a degraded mode. Reports include corpus version, schema version, probe-pack version, release, trust-tier counts, and source attribution.

See `docs/requirement_gap_analysis.md` for the requirement mapping and remaining implementation roadmap.

## External Evidence

The engine treats external resources as evidence providers, not authorities. Full fingerprint audits can now include:

- Multiple configured AstrBot judge providers via `auxiliary_judge_provider_ids`.
- A backward-compatible single judge via `auxiliary_judge_provider_id`.
- Public fingerprint/model datasets from local JSON files or HTTPS URLs via `public_fingerprint_sources`.

External judge calls must return structured JSON where possible. Each invocation is logged in the report with model, prompt, response, timestamp, execution status, and error details when available. Public URL datasets are downloaded into `public_cache_dir`; if a URL cannot be reached, the engine falls back to the cached copy. If no cache exists, the source is marked degraded and the audit continues with remaining evidence.


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
GET  /astrbot_plugin_llm_identify/page/health
GET  /astrbot_plugin_llm_identify/page/audits
POST /astrbot_plugin_llm_identify/page/audits
GET  /astrbot_plugin_llm_identify/page/audits/<task_id>
GET  /astrbot_plugin_llm_identify/page/audits/<task_id>/report
GET  /astrbot_plugin_llm_identify/page/audits/<task_id>/events
POST /astrbot_plugin_llm_identify/page/baselines/refresh
GET  /astrbot_plugin_llm_identify/page/drift/<target_id>
POST /astrbot_plugin_llm_identify/page/export/<task_id>
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
- `identity_posterior`
- `authenticity_posterior`
- `security_posterior`
- `prompt_injection_risk`
- `drift_risk`
- `branch_evidence`
- `thresholds`
- `risk_analysis`
- `evidence_summary`
- `findings`
- `probe_results`
- `evidence_sources`
- `judge_invocations`
- `degraded_modes`
- `execution_trace`
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
- `randomize_fingerprint_probes`: randomly select redundant probes per method.
- `fingerprint_probes_per_method`: number of probes sampled per method.
- `fingerprint_probe_seed`: optional deterministic seed for reproducible randomized probe selection.
- `local_fingerprint_libraries`: bundled and optional Python fingerprint libraries to check/install for local operation. `bundled:llmmap` is included by default and requires no user installation.
- `enable_auxiliary_llm_judge`: enable external LLM judging over extracted fingerprint summaries.
- `auxiliary_judge_provider_id`: optional single AstrBot provider ID used for auxiliary judging.
- `auxiliary_judge_provider_ids`: comma-separated AstrBot provider IDs used as independent judge evidence providers.
- `public_fingerprint_sources`: comma-separated local JSON paths or HTTPS URLs for public fingerprint/model datasets.
- `enable_embedded_trusted_corpus`: load the compact embedded trusted reference corpus for offline operation.
- `trusted_corpus_sources`: comma-separated local JSON paths or HTTPS URLs for extended trusted reference corpus data; remote URLs are cached and degrade offline.
- `public_cache_dir`: local cache directory for downloaded public fingerprint resources.
- `enable_context_probe`: reserved for future context sentinel probes.
- `strict_mode`: apply a more conservative penalty for failed probes.

## Limits

This plugin uses observable behavior and metadata to estimate risk. It cannot prove the true underlying model. Relays can rewrite usage, cache responses, change system prompts, spoof model style, or route traffic dynamically, so repeat audits and provider-side logs remain important.


## Task Storage And Privacy

Audits now run through task records and are persisted to SQLite plus local object files. The storage layer writes raw traces, feature summaries, and report artifacts separately. Redaction runs before trace persistence and masks common emails, phone-like values, API-key-like tokens, selected JSON secret fields, and deterministic hashes. Ordinary logs should only refer to task IDs and trace/report IDs.

Traffic modes are `probe_only`, `mixed`, and `real_traffic`. The default is `mixed`; `real_traffic` is downgraded to `mixed` unless `allow_real_traffic` is enabled.

## CLI And Experiment Utilities

Use the standalone entrypoint with Python:

```text
python -m llm_identify.cli scan --target-id relay-default --base-url https://example.com/v1 --api-key sk-... --model gpt-test --output reports/run-001
python -m llm_identify.cli baselines refresh --providers openai anthropic gemini
python -m llm_identify.cli report export --task-id aud_... --format json --data-dir reports/run-001
python -m llm_identify.cli report plot --out reports/run-001/figures
```

`llm_identify.rest.create_app()` exposes the optional FastAPI app for local automation when FastAPI is installed. The plugin APIs remain AstrBot `register_web_api` routes.

## Drift And Release Notes

`llm_identify.drift` provides a lightweight drift event model and p-value approximation suitable for scheduled jobs. Large datasets and downloaded public baselines should live under the configured data/cache directory and are not vendored into the plugin package.


## Bundled Fingerprint Packs

The plugin now bundles a lightweight, source-attributed LLMmap pack under `llm_identify/data/bundled_fingerprint_packs.json`. This packages behavioral probe strategies, output-format probes, source metadata, and supported-model metadata hooks directly into the plugin so users get local fingerprint coverage without running `pip install` or cloning upstream repositories. Heavy upstream assets such as trained classifiers, generated datasets, model weights, and CUDA/PyTorch stacks are intentionally not vendored; they remain optional external sources to keep the AstrBot plugin small and portable.

## Trusted Reference Contribution

Trusted-reference contribution is disabled by default with `enable_reference_contribution: false`. When enabled, the Page shows a non-intrusive prompt only after a completed direct audit whose configured base URL matches an allowlisted official HTTPS endpoint such as `https://api.openai.com/v1`, `https://api.anthropic.com`, or `https://generativelanguage.googleapis.com`. Proxy, mirror, custom, HTTP, and unknown domains are not treated as trusted references unless explicitly configured in `official_endpoint_allowlist`.

The plugin never uploads automatically. Each contribution requires explicit user action. Users can preview the schema-versioned `trusted_reference_candidate` package, export JSON/JSONL locally, prepare a GitHub issue URL, or decline future prompts for the current official endpoint. Sanitized packages exclude API keys, raw prompts, raw completions, full base URLs, IP addresses, account identifiers, authorization headers, cookies, and private business data. They include only aggregate metadata, protocol/timing/token statistics, probe IDs, capability scores, plugin/probe-pack versions, claimed official model name, coarse timestamp buckets, and anonymous dynamic fingerprint vectors.

## Dynamic Fingerprint Database

Every completed audit stores an anonymous high-dimensional fingerprint vector in the local data directory. The vector is not treated as a model-name label; it captures protocol scores, timing summaries, token cadence, capability/probe scores, posterior distributions, and fingerprint method scores. Future audits compare vectors with cosine similarity to identify likely same-backend behavior, related model families, routing changes, and response rewriting even when the true model name is unknown. Full audits target `dynamic_fingerprint_probe_budget` probes, defaulting to 120 and capped by the configured repeat safety limit.
## Active Goal Features

- Local fingerprint-library status is exposed through `GET /astrbot_plugin_llm_identify/page/fingerprint-library/status`. The plugin includes the no-install `bundled:llmmap` lightweight pack by default. Optional external install attempts can still be triggered through `POST /astrbot_plugin_llm_identify/page/fingerprint-library/install` with `{"module": "name"}`; external libraries are installed into the configured data directory target when possible.
- Fingerprint probes now use a redundant probe library per detection method. Standard and light profiles randomly sample `fingerprint_probes_per_method` probes per method; exhaustive mode still runs all probes. Set `fingerprint_probe_seed` for reproducible sampling.
- Complete inspection records can be exported as `json`, `csv`, `md`, `txt`, or `pdf`. TXT and PDF exports include the report, feature summary, trace references, and redacted trace records.
- Page-triggered audits run as background tasks. Leaving and reopening the Page shows persisted task status and previously completed reports from SQLite storage.
- The result UI and report expose `identity_posterior`, so the current best model family and similarity probabilities for other model families are visible together.

