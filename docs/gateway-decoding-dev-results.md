# Gateway boundary decoding: dev selection

Frozen selection: **no feasible candidate**. Training seed: **0**; seed count **1**.
All three registered rules were scored on all 1,600 gateway DEV conversations (200 per language)
and 126 TAB dev documents. Selection uses no test results. Wilson intervals describe identifier
subjects; utility and paired delta intervals use 2,000 whole-document/conversation bootstrap draws, RNG 100.
TAB's selection replay uses the v2 path; its clusters are documents, despite the generic replay
helper's `bootstrap_unit=conversation` metadata in the dev grid. No rows or counts are changed.
TAB also inherits generic `clean_held_out`/`dev` replay markers in that frozen grid. The correct
interpretation is unknown model contamination and real-external-gold on the dev split. These
markers were not selection inputs; `metadata_corrections` records this without changing the frozen grid.

| Rule | Feasible configs / 9 | Macro all-subject leak % | Macro non-PII removed % |
|---|---:|---:|---:|
| strict | 4 | 71.49 | 1.18 |
| inward | 3 | 71.45 | 1.71 |
| anchored | 3 | 22.77 | 2.40 |

Macro rates are the registered equal-config selection objective, not pooled independent n or a win claim.
A single failing config/comparator excludes a candidate; the v3 utility upper-CI margin is +1.0 point.
V2 reference requires upper CI <=0. Full per-comparator deltas and all subject slices are retained in
[the aggregate dev grid](../analysis/gateway-decoding-dev.json). There are no three-seed/held-out verdicts.

| Rule | Config | Clusters | Subjects | V2 leak % [95% Wilson CI] | Non-PII removed % [95% bootstrap CI] | V3 utility | V2 utility |
|---|---|---:|---:|---:|---:|---|---|
| strict | tab-echr-legal-en-v1 | 126 | 4053 | 90.94 [90.02, 91.79] | 0.61 [0.45, 0.81] | pass | fail |
| strict | gateway-ro | 200 | 900 | 86.00 [83.58, 88.11] | 1.62 [1.07, 2.12] | fail | fail |
| strict | gateway-en | 200 | 900 | 50.33 [47.07, 53.59] | 0.52 [0.32, 0.72] | pass | fail |
| strict | gateway-de | 200 | 900 | 51.44 [48.18, 54.70] | 1.17 [0.82, 1.50] | fail | fail |
| strict | gateway-fr | 200 | 900 | 63.44 [60.25, 66.53] | 0.52 [0.33, 0.71] | pass | fail |
| strict | gateway-es | 200 | 900 | 52.44 [49.18, 55.69] | 0.93 [0.60, 1.24] | fail | fail |
| strict | gateway-it | 200 | 900 | 67.11 [63.97, 70.10] | 0.67 [0.42, 0.91] | pass | fail |
| strict | gateway-nl | 200 | 900 | 84.67 [82.17, 86.87] | 1.78 [1.20, 2.31] | fail | fail |
| strict | gateway-pl | 200 | 900 | 97.00 [95.67, 97.93] | 2.76 [1.88, 3.55] | fail | fail |
| inward | tab-echr-legal-en-v1 | 126 | 4053 | 90.87 [89.95, 91.72] | 0.73 [0.55, 0.95] | pass | fail |
| inward | gateway-ro | 200 | 900 | 86.00 [83.58, 88.11] | 2.31 [1.50, 3.03] | fail | fail |
| inward | gateway-en | 200 | 900 | 50.33 [47.07, 53.59] | 0.59 [0.37, 0.82] | pass | fail |
| inward | gateway-de | 200 | 900 | 51.44 [48.18, 54.70] | 1.37 [0.95, 1.78] | fail | fail |
| inward | gateway-fr | 200 | 900 | 63.44 [60.25, 66.53] | 0.59 [0.37, 0.82] | pass | fail |
| inward | gateway-es | 200 | 900 | 52.44 [49.18, 55.69] | 1.07 [0.66, 1.46] | fail | fail |
| inward | gateway-it | 200 | 900 | 66.89 [63.75, 69.89] | 0.98 [0.66, 1.29] | fail | fail |
| inward | gateway-nl | 200 | 900 | 84.67 [82.17, 86.87] | 2.05 [1.38, 2.66] | fail | fail |
| inward | gateway-pl | 200 | 900 | 97.00 [95.67, 97.93] | 5.67 [3.96, 7.18] | fail | fail |
| anchored | tab-echr-legal-en-v1 | 126 | 4053 | 34.20 [32.75, 35.67] | 0.80 [0.61, 1.03] | pass | fail |
| anchored | gateway-ro | 200 | 900 | 22.78 [20.16, 25.63] | 3.20 [2.03, 4.24] | fail | fail |
| anchored | gateway-en | 200 | 900 | 22.22 [19.63, 25.05] | 0.69 [0.43, 0.94] | pass | fail |
| anchored | gateway-de | 200 | 900 | 22.22 [19.63, 25.05] | 1.88 [1.25, 2.47] | fail | fail |
| anchored | gateway-fr | 200 | 900 | 19.89 [17.41, 22.62] | 0.70 [0.42, 0.99] | pass | fail |
| anchored | gateway-es | 200 | 900 | 23.56 [20.90, 26.44] | 1.25 [0.75, 1.74] | fail | fail |
| anchored | gateway-it | 200 | 900 | 20.11 [17.62, 22.85] | 1.40 [0.94, 1.85] | fail | fail |
| anchored | gateway-nl | 200 | 900 | 19.89 [17.41, 22.62] | 2.53 [1.67, 3.34] | fail | fail |
| anchored | gateway-pl | 200 | 900 | 20.11 [17.62, 22.85] | 9.17 [6.46, 11.64] | fail | fail |

| Rule | Config | Binding comparator (largest upper CI) | Utility delta pp [95% bootstrap CI] |
|---|---|---|---:|
| strict | gateway-ro | base | 1.39 [0.83, 1.90] |
| strict | gateway-de | 560m-tab | 1.08 [0.70, 1.42] |
| strict | gateway-es | 560m-tab | 0.77 [0.43, 1.10] |
| strict | gateway-nl | 560m-tab | 1.59 [1.02, 2.13] |
| strict | gateway-pl | 560m-tab | 2.38 [1.56, 3.14] |
| inward | gateway-ro | base | 2.08 [1.27, 2.80] |
| inward | gateway-de | 560m-tab | 1.28 [0.84, 1.70] |
| inward | gateway-es | 560m-tab | 0.92 [0.50, 1.31] |
| inward | gateway-it | 560m-tab | 0.81 [0.48, 1.13] |
| inward | gateway-nl | 560m-tab | 1.87 [1.21, 2.49] |
| inward | gateway-pl | 560m-tab | 5.30 [3.66, 6.75] |
| anchored | gateway-ro | base | 2.97 [1.81, 3.98] |
| anchored | gateway-de | 560m-tab | 1.79 [1.15, 2.39] |
| anchored | gateway-es | 560m-tab | 1.09 [0.59, 1.60] |
| anchored | gateway-it | 560m-tab | 1.24 [0.78, 1.69] |
| anchored | gateway-nl | 560m-tab | 2.35 [1.49, 3.15] |
| anchored | gateway-pl | 560m-tab | 8.80 [6.15, 11.20] |

The main sync before inference added the referenced DEV audit at `763604c`; the preregistration's
absence observation refers specifically to the earlier first-check commit `4f5203f`.
The fixed rules contain no learned merchant/status lists and no gold-derived country metadata.
The optional national-ID country validator is covered by controls but is inactive for this evaluation:
no independent deployment country context is available. IBAN/phone checks and Unicode boundaries are active.

DEV receipt inspection exposes a limitation: simple aggregation can emit adjacent native spans with
different BIOES prefixes. Normalizing their labels does not merge their intervals. This registered
filter requires a complete word within each individual span, so it can discard pieces whose union
previously protected a complete identifier. The whole-word-name unit control does not establish
preservation for a name emitted as several fragments. No coalescing rule was added after test access.

Unverified: independent native review; source/subject/scenario-family/translation disjointness;
three independent seeds; deployment equivalence; semantic utility; CPU load/SLO; attacker re-identification.

The original preregistered test path stopped because the constrained objective has no feasible solution.
A disclosed [prospective diagnostic amendment](gateway-decoding-diagnostic.md), written after these
dev outcomes and before test scoring, separately registers strict for the requested two-seed test matrix.
That diagnostic does not change this infeasible selection or the original default-decoding results.

## Reproduction

Use Python 3.13 with the pinned local MoE environment from gateway-moe-scoring.md.
Raw receipts/gold stay in estate/scratch/decode-fix; no downloads or training are required.
The diagnostic command requires the committed amendment and a completed immutable dev selection.
The dev command resumes interrupted inference; after selection is frozen, use the report command
rather than regenerating the grid (timestamps are part of its hash).
RES-125 inputs were subsequently moved to codespace-archive/2026-10-11/res125. A fresh dev capture
requires making the original pinned inputs available at the documented paths; the already-frozen
selection and test run resume from their verified local copies. Comparator receipt relocations are
recorded in the diagnostic comparison JSON with both paths and unchanged SHA-256 hashes.

```bash
export PYTHONPATH=src:. HF_HUB_OFFLINE=1
python -u analysis/score_gateway_decoding.py dev
python -m analysis.report_gateway_decoding_dev
python -u analysis/score_gateway_decoding_diagnostic.py --seeds 0 1 --splice
```

The adapter option is `Res100MoEAdapter(model_id, decoding_rule='strict', country=None)`.
The historical adapter retains its 256-token default; the registered gateway scoring commands
explicitly use the saved 512-token checkpoint pipeline. No default decoder behavior is changed.
