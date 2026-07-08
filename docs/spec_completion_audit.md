# Specification Completion Audit

Audit date: 2026-07-09

Authoritative sources reviewed:

- `D:\astrbot_llm_identify\Technical Specification for an Upgraded LLM Fing..pdf`
- `D:\astrbot_llm_identify\Reliable Detection and Measurement of LLM Token ..pdf`
- `D:\astrbot_llm_identify\Verifying Real-World LLM Context Windows and Det..pdf`
- `D:\astrbot_llm_identify\Community-Driven Trusted Reference Corpus for LL..pdf`

PDF text extracts used for local audit are under `tmp/spec_text/`.

## Requirement Evidence Matrix

| Requirement | Current evidence |
| --- | --- |
| Keep existing AstrBot APIs working | `main.py`, `_conf_schema.json`, page assets under `pages/`, and full test discovery pass. |
| Production-grade context-window verification | `llm_identify/probes/context.py`, `llm_identify/branches.py`, `llm_identify/engine.py`, `tests/test_context_window.py`. Evidence includes multi-position sentinels, boundary pressure, JSON compliance, recall, truncation/refusal signals, and degraded scoring. |
| Provider-native token/counting adapters | `llm_identify/adapters/base.py`, `llm_identify/adapters/direct_openai.py`, `llm_identify/features/token.py`, `main.py`, `llm_identify/cli.py`, `tests/test_native_token_count.py`. Direct OpenAI-compatible scans can call `/responses/input_tokens`; failures degrade into trace metadata. |
| Provider-native trace adapters | `llm_identify/adapters/trace_normalization.py`, `llm_identify/adapters/direct_openai.py`, `llm_identify/adapters/astrbot.py`, `tests/test_provider_trace_adapters.py`. Evidence includes safe headers, provider hints, request IDs, SSE summaries, usage shapes, cache/reasoning details, and Responses-style object parsing. |
| Calibrated evidence fusion | `llm_identify/scoring/fingerprint.py`, `tests/test_calibrated_fusion.py`. Fusion uses tempered log-opinion pooling, reliability priors, unknown mixing, entropy, margin, weighted agreement, and diagnostics. |
| Stronger mixture/provider-switching detection | `llm_identify/mixture.py`, `llm_identify/scoring/report.py`, `tests/test_mixture_detection.py`. Signals include response clusters, provider trace shifts, usage-shape switches, latency modes, probe status pressure, and calibrated fusion disagreement. |
| Trusted-corpus schema/governance validation | `llm_identify/corpus_validation.py`, `llm_identify/corpus.py`, `schemas/*.schema.json`, `docs/trusted_corpus_governance.md`, `CODEOWNERS`, `.github/ISSUE_TEMPLATE/trusted-reference-candidate.yml`, `.github/workflows/validate-trusted-corpus.yml`, `tests/test_corpus_validation_review.py`, `tests/test_schema_artifacts.py`. |
| Contribution review workflows | `llm_identify/contribution/evidence_schema.py`, `llm_identify/contribution/review.py`, `llm_identify/contribution/sanitizer.py`, `llm_identify/contribution/github_issue_submitter.py`, `tests/test_contribution_dynamic.py`, `tests/test_corpus_validation_review.py`. |
| Benchmark/regression harness | `llm_identify/benchmark.py`, `llm_identify/exporting.py`, `llm_identify/cli.py`, `tests/test_benchmark_harness.py`. Metrics include top-1 accuracy, macro-F1, macro-AUROC, Brier, ECE, reliability bins, threshold curves, scenario metrics, and temperature calibration artifacts. |
| Privacy safety | `llm_identify/privacy.py`, `llm_identify/contribution/sanitizer.py`, contribution schemas, trace storage redaction, and tests `test_task_storage_privacy_cli.py`, `test_contribution_dynamic.py`, `test_schema_artifacts.py`. |
| Robust degraded behavior | External evidence, trusted corpus, native token count, and public source paths record degraded modes instead of failing audits; covered by `test_evidence_sources.py`, `test_trusted_corpus.py`, `test_native_token_count.py`, `test_corpus_validation_review.py`. |
| Observable reports | `llm_identify/scoring/report.py`, `llm_identify/storage.py`, `llm_identify/pdf_export.py`, `llm_identify/capture/trace.py`. Reports expose risk analysis, mixture signals, calibration metadata, branch evidence, corpus metadata, degraded modes, evidence sources, traces, and exports. |

## Verification

Commands run on 2026-07-09:

```powershell
C:\Users\Zhang\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest discover -s tests
C:\Users\Zhang\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m compileall -q llm_identify main.py
```

Observed results:

- `Ran 70 tests in 0.690s` with `OK`.
- `compileall` exited successfully.

## Residual Notes

- Live provider verification requires user-supplied credentials and is intentionally not run in tests.
- External public corpus hosting is represented by repository-ready schemas, issue form, workflow, CODEOWNERS, and governance artifacts; deployment of a separate public repository is operational work outside this plugin workspace.
- Package size has not been optimized, matching the instruction to prioritize audit correctness, observability, privacy, and degraded-mode robustness first.

No remaining objective requirement is unsupported by current repository evidence.
