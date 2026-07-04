# Requirement Gap Analysis

Source documents reviewed:

- `Community-Driven Trusted Reference Corpus for LLM Fingerprinting on GitHub`
- `Technical Specification for an Upgraded LLM Fingerprinting and Auditing System for an AstrBot Plugin`

## Implemented Requirements

- AstrBot-compatible plugin entrypoint remains in `main.py` with page APIs, command fallback, task storage, report export, and direct OpenAI-compatible audits.
- Host-agnostic core exists under `llm_identify/` with adapters, probes, trace capture, feature extraction, branch evidence, scoring, storage, and CLI support.
- Reports are probabilistic and include ranked fingerprint candidates, confidence, provider probabilities, proxy probability, mixture probability, token/context authenticity signals, spoofing risk, drift risk, branch evidence, findings, supporting evidence, contradicting evidence, unknown evidence, judge invocations, degraded modes, and execution traces.
- External LLM judges are configurable as one or more evidence providers. Judge calls are optional, timeout-bound, logged, parsed as structured JSON where possible, and fused as non-authoritative evidence.
- Public external fingerprint sources can be local files or HTTPS URLs. Remote sources use local cache fallback and degrade without failing the audit.
- Contribution features are optional and disabled by default. The existing contribution module includes official endpoint detection, consent state, sanitization, export, and GitHub issue URL preparation.
- Probe families cover protocol behavior, token accounting, knowledge-boundary behavior, refusal style, tokenizer/Unicode behavior, timing/stream surfaces, mixed routing, context truth, adversarial robustness, and inference-stack signals.
- Dynamic probe selection and repeat budgeting are implemented through fingerprint randomization, per-method probe limits, seeds, and dynamic full-audit budget expansion.
- Storage and export paths redact sensitive trace values and support JSON, Markdown, text, CSV, and PDF export.

## Newly Implemented In This Upgrade

- Added `llm_identify/corpus.py`, a trusted reference corpus subsystem with embedded, local-file, and remote URL sources.
- Added compact embedded corpus data at `llm_identify/data/trusted_reference_corpus.json`; it contains only high-value stable provider-family aliases, protocol traits, source attribution, version metadata, and seed reference records.
- Added local caching and offline fallback for remote trusted corpus URLs.
- Added optional SHA-256 integrity checking for trusted corpus sources.
- Added corpus version, schema version, probe-pack version, release, trust-tier counts, and source attribution to report metadata.
- Added `trusted_corpus:*` evidence methods so corpus matches participate in probabilistic fingerprint fusion instead of acting as deterministic authority.
- Added report and text-output sections for trusted corpus provenance.
- Added AstrBot config keys for `enable_embedded_trusted_corpus` and `trusted_corpus_sources`.
- Added tests for embedded corpus loading and remote corpus cache degradation.

## Partially Implemented Requirements

- Full trace capture exists, but direct provider-specific header/event normalization is still limited by what adapters expose in `ModelReply.meta`.
- Corpus schema is represented in compact JSON and loader code, but not yet as a separate published JSON Schema package.
- Mixture detection is implemented as heuristic repeated-response instability and disagreement scoring, not HDBSCAN/Gaussian-mixture clustering.
- Fusion is quality-aware and cross-method weighted, but it is not yet a full calibrated log-opinion pool with isotonic or temperature calibration trained on held-out datasets.
- Context authenticity has report fields and branch hooks, but deep long-context sentinel probing remains limited.
- Evaluation harness artifacts exist as placeholders and tests cover core behavior, but full AUROC/ECE/Brier/reliability reporting is not implemented.
- Page-panel APIs exist, but the browser UI can still be expanded for corpus browsing, branch-score inspection, and contribution review workflows.

## Missing Requirements

- Native adapters for provider-specific reference baselines beyond the OpenAI-compatible execution path.
- Published external GitHub corpus repository layout, CI validators, CODEOWNERS, issue forms, release workflows, and governance documents.
- Human review workflow state for trusted-reference promotion beyond local contribution export/consent primitives.
- Advanced semantic deduplication, contradiction detection, and poisoning-resistance validation for contributed corpus rows.
- Full benchmark harness with reference classes for official endpoints, compatibility layers, relays, wrappers, summarization gateways, mixed routing, and spoofed endpoints.
- Learned calibration from validation data and explicit reliability curve generation from real benchmark results.
- Private-intake/quarantine lane implementation for richer evidence packages.

## Risky Or Unclear Requirements

- Exact AstrBot page-panel conventions may vary by host version; current implementation uses project-local APIs and defensive registration.
- External LLM judges can leak metadata or incur cost if misconfigured; they remain disabled by default and should not receive raw prompts or secrets.
- Provider documentation and endpoint behavior change over time; corpus entries need versioning, refresh, stale marking, and trust-tier downgrades.
- Remote GitHub data availability is not guaranteed; cache fallback is required and now implemented, but first-run offline remote-only setups still degrade.
- Larger corpus datasets should not be embedded; the embedded corpus must stay compact and stable.

## Affected Files And Modules

- `llm_identify/corpus.py`: trusted corpus loading, caching, integrity checks, metadata extraction, and corpus scoring.
- `llm_identify/data/trusted_reference_corpus.json`: compact embedded reference corpus.
- `llm_identify/evidence.py`: corpus evidence integration and degraded-mode reporting.
- `llm_identify/engine.py`: corpus source options.
- `llm_identify/scoring/fingerprint.py`: corpus-attributed candidate evidence and findings.
- `llm_identify/scoring/report.py`: corpus metadata in report shape, text output, and evidence summary.
- `llm_identify/models.py`: report metadata field.
- `main.py`: AstrBot configuration and status plumbing.
- `_conf_schema.json`: new corpus configuration keys.
- `tests/test_trusted_corpus.py` and `tests/test_evidence_sources.py`: coverage for corpus behavior and existing evidence source compatibility.

## Recommended Implementation Order

1. Keep AstrBot compatibility and core tests green.
2. Expand adapter trace capture for headers, SSE events, unsupported-field behavior, request IDs, and provider usage fields.
3. Publish a formal corpus JSON Schema and validator for the local and remote corpus formats.
4. Build corpus contribution review states, dedupe checks, and contradiction checks.
5. Improve mixture detection with repeated-probe clustering once enough baseline data exists.
6. Add benchmark classes and calibration metrics before tightening default thresholds.
7. Expand the page panel for corpus browsing, branch-score inspection, contribution review, and report comparison.
