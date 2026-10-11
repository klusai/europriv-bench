# Prospective diagnostic test amendment

The original dev selection in [gateway-decoding.md](gateway-decoding.md) is
**infeasible**: none of strict/inward/anchored passes the v3 utility constraint
on every gateway DEV language and TAB dev comparator. That result is frozen in
`analysis/gateway-decoding-dev.json`; no criterion, grid score or selected-rule
field is changed. No decoder test score has been computed at this amendment.

To complete the coordinator's explicitly requested seed-0/seed-1 test matrix,
amend the original no-feasible/test-stop clause with this diagnostic exception:
evaluate **strict**, the first registered candidate, as **dev-rejected**. It is
chosen for the targeted fragment-rejection mechanism, not as a feasible optimum.
It rejects every partial word, including the mixed `ota zgodna` example. Do not
try another rule based on test results. This amendment is after dev outcomes and
before decoder test access/scoring; it must not be portrayed as an untouched
original protocol or a successful constrained selection.

Run the complete 28-config suite for seed 0 and seed 1 with the same fixed rule.
Keep the original frozen checkpoint/runtime/gold/comparator and bootstrap policy.
Preserve national-ID country-validation limitations and actual data split names.
Original default seed-0 predictions may be replayed only after receipt/checkpoint/
ordered-gold hash verification. Seed 1 requires a complete checksum/training manifest.
No test-based thresholds, minimums, boundary rules, seeds or endpoints may change.

Report all n and per-seed CIs, v3 verdicts and v2 references. Rows and comparison
artifacts must explicitly record infeasible dev selection, diagnostic status,
strict rule, this amendment hash and its committed registration. No resulting
numerical pass rescues the failed dev constraint or establishes a contract win.
Keep original default-decoding leaderboard entries unchanged. Splice diagnostic
rows under the separate decoded adapter/model keys; never pool the two seeds.
