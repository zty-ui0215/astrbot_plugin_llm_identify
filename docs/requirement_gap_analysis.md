# Requirement Gap Analysis

Source documents reviewed:

- `Community-Driven Trusted Reference Corpus for LLM Fingerprinting on GitHub`
- `Reliable Detection and Measurement of LLM Token Counting and Context Claims`
- `Technical Specification for an Upgraded LLM Fingerprinting and Auditing System for an AstrBot Plugin`
- `Verifying Real-World LLM Context Windows and Detecting Backend Substitution`

Current detailed completion evidence is in `docs/spec_completion_audit.md`.

## Implemented Requirements

- AstrBot-compatible plugin entrypoint remains in `main.py` with command mode, page APIs, direct OpenAI-compatible audits, task storage, and report export.
- Host-agnostic audit core exists under `llm_identify/` with adapters, probes, trace capture, feature extraction, branch evidence, scoring, storage, CLI support, and degraded-mode handling.
- Reports are probabilistic and include ranked fingerprint candidates, confidence, provider probabilities, proxy probability, mixture probability, token/context authenticity signals, spoofing risk, drift risk, branch evidence, findings, evidence summaries, judge invocations, degraded modes, execution traces, corpus metadata, calibration diagnostics, and mixture signals.
- Provider-native trace normalization is implemented for safe headers, request IDs, provider hints, SSE event summaries, usage shapes, cache/reasoning token details, OpenAI chat completions, OpenAI Responses-style objects, Gemini-style usage metadata, and AstrBot raw completions.
- Provider-native token count verification is supported through an optional `GenerateAdapter.count_tokens_fn`; direct OpenAI-compatible scans can call `/responses/input_tokens`, and failures degrade into trace metadata without failing the audit.
- Token authenticity checks cover usage availability, monotonic length gradients, slope plausibility, constant-count anomalies, cache signals, Unicode stability, output-length consistency, and native count agreement.
- Context-window verification has real context probes with short, multi-position, and boundary-pressure sentinels; branch scoring records sentinel recall, JSON response rate, position coverage, refusals, truncation, and per-probe evidence.
- Fingerprint fusion uses calibrated tempered log-opinion pooling with method reliability priors, temperature scaling, unknown mixing, entropy, margin, weighted agreement, calibration penalties, and diagnostics.
- Mixture/provider-switching detection has a dedicated detector using repeated-response clusters, provider trace shifts, usage-shape switches, latency modes, probe status pressure, and fusion disagreement.
- Trusted corpus support includes embedded/local/remote sources, cache fallback, optional SHA-256 integrity, runtime schema/governance validation, corpus scoring as probabilistic evidence, report provenance, and schema/governance artifacts under `schemas/`, `docs/`, `.github/`, and `CODEOWNERS`.
- Contribution workflows include official endpoint detection, consent state, sanitization, evidence package generation, browser-based GitHub issue URL preparation, candidate review states, duplicate/contradiction checks, quarantine/reject/promote decisions, and schema artifacts.
- Benchmark/regression harness supports JSON/JSONL/CSV cases, default regression classes, top-1 accuracy, macro-F1, macro-AUROC, Brier score, ECE, reliability bins, threshold curves, scenario metrics, and temperature calibration artifacts.
- Privacy-safe defaults redact sensitive trace values, avoid raw prompt/completion upload in contribution packages, bucket timestamps, and keep external judges optional and disabled by default.
- Tests cover reliability-critical behavior across corpus validation, schema artifacts, contribution review, token features, native token count, provider traces, context windows, calibrated fusion, mixture detection, benchmark harness, storage/privacy/CLI, evidence source degradation, and AstrBot engine modes.

## Verification

Latest verification command:

```powershell
C:\Users\Zhang\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest discover -s tests
C:\Users\Zhang\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m compileall -q llm_identify main.py
```

Observed result on 2026-07-09:

- `Ran 70 tests in 0.690s` with `OK`.
- `compileall` exited successfully.

## Residual Operational Notes

- Live provider calls are not executed in the test suite because they require user-supplied credentials and may incur cost.
- The public trusted-corpus repository is represented by committed schemas, governance docs, CODEOWNERS, issue form, and validation workflow skeleton; deploying a separate public repository is operational follow-through, not plugin code.
- Benchmark temperature calibration is implemented for supplied validation rows; no private held-out provider dataset is bundled.
- Package size was intentionally not optimized because the requested priority was correctness, observability, privacy safety, and robustness under degraded dependencies.

## Status

No remaining objective requirement is known to be missing from the current plugin implementation.