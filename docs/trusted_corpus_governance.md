# Trusted Corpus Governance

This plugin treats trusted reference submissions as de-identified telemetry, not chat transcripts.

## Review States

- `intake`: evidence package received through browser-based issue flow or local export.
- `needs-sanitization-proof`: sanitizer report is missing or incomplete.
- `schema-failed`: package or corpus row does not validate against the active schema.
- `needs-review`: automated gates passed and maintainer review is required.
- `quarantine`: contradiction, privacy risk, or suspicious endpoint evidence needs private handling.
- `accepted`: maintainer-approved corpus row for the next release snapshot.
- `rejected`: rejected with a reason that does not expose sensitive evidence.
- `stale`: previously accepted evidence is version-skewed or no longer reproducible.

## Trust Tiers

- `T0`: first-party official endpoint, maintainer reproduced, schema-valid, no forbidden fields.
- `T1`: first-party official endpoint, independently reproduced by a trusted verifier.
- `T2`: public documentation or compact seed reference used as probabilistic evidence only.
- `T3`: adversarial, relay, spoofing, or negative-control evidence.

## Automated Gates

Before human promotion, a candidate must pass:

- active evidence-package schema validation;
- forbidden-field and secret scan;
- exact official endpoint host/path-family allowlist;
- supported probe-pack and sanitizer versions;
- duplicate and contradiction checks against the active corpus;
- evidence-strength floor for protocol, token, context, and fingerprint scores.

## Privacy Rules

Never publish API keys, bearer tokens, cookies, Authorization headers, raw prompts, raw completions,
account identifiers, dashboard screenshots, private URLs, IP addresses, or user content.
Use stable salted hashes, timestamp buckets, token-length buckets, and aggregate trace features.

## Release And Refresh

Schema, probe pack, sanitizer, and corpus snapshot versions are tracked separately. Accepted rows carry
`schema_version`, `probe_pack_version`, `sanitizer_version`, and `accepted_in_release`. Rows that become
version-skewed, unreproducible, or contradicted by newer official behavior are downgraded or retired.
