# Gateway full-PII dev results — RES-126

Synthetic, unreviewed `gateway-traffic-v1`, data revision 4. Each row scores 1,000
conversations and 4,506 identifier subjects (4,266 DIRECT, 240 QUASI; UNSPECIFIED
has no support). Each KP checkpoint: training seed 0 only; each baseline: one inference run.
95% Wilson intervals below are descriptive subject intervals. Paired conversation
cluster intervals (2,000 resamples, seed 126) are in `baselines/gateway-comparisons.json`.
Negative utility deltas favor the candidate. Character retention is a proxy, not semantic utility.

| Engine | Language | Leak % [95% Wilson] | Non-PII removed % [95% cluster CI] |
|---|---|---:|---:|
| 560m-legal | de | 63.52 [62.10, 64.91] | 2.34 [2.13, 2.54] |
| 560m-legal | en | 51.71 [50.25, 53.17] | 1.43 [1.30, 1.57] |
| 560m-legal | es | 52.42 [50.96, 53.87] | 1.98 [1.81, 2.16] |
| 560m-legal | fr | 59.88 [58.44, 61.30] | 1.79 [1.64, 1.95] |
| 560m-legal | it | 73.70 [72.40, 74.97] | 1.94 [1.76, 2.12] |
| 560m-legal | nl | 69.91 [68.55, 71.23] | 1.79 [1.63, 1.96] |
| 560m-legal | pl | 94.76 [94.07, 95.38] | 3.33 [3.02, 3.64] |
| 560m-legal | ro | 71.68 [70.35, 72.98] | 3.58 [3.26, 3.89] |
| 560m-tab | de | 57.35 [55.90, 58.78] | 0.38 [0.27, 0.51] |
| 560m-tab | en | 52.37 [50.91, 53.83] | 0.38 [0.29, 0.49] |
| 560m-tab | es | 52.95 [51.49, 54.41] | 0.47 [0.37, 0.59] |
| 560m-tab | fr | 59.65 [58.21, 61.08] | 0.38 [0.28, 0.50] |
| 560m-tab | it | 59.52 [58.08, 60.95] | 0.40 [0.30, 0.52] |
| 560m-tab | nl | 55.57 [54.12, 57.02] | 0.43 [0.32, 0.55] |
| 560m-tab | pl | 65.02 [63.62, 66.40] | 0.54 [0.44, 0.65] |
| 560m-tab | ro | 60.92 [59.49, 62.33] | 0.62 [0.52, 0.74] |
| kp-280m | de | 34.02 [32.65, 35.42] | 20.09 [18.16, 21.83] |
| kp-280m | en | 36.93 [35.53, 38.35] | 21.63 [19.48, 23.57] |
| kp-280m | es | 35.97 [34.59, 37.39] | 22.39 [20.26, 24.31] |
| kp-280m | fr | 34.62 [33.25, 36.02] | 22.88 [20.65, 24.96] |
| kp-280m | it | 35.06 [33.68, 36.47] | 21.16 [19.19, 22.94] |
| kp-280m | nl | 35.04 [33.66, 36.45] | 20.59 [18.69, 22.32] |
| kp-280m | pl | 31.49 [30.15, 32.86] | 18.68 [17.01, 20.24] |
| kp-280m | ro | 33.40 [32.04, 34.79] | 23.34 [21.00, 25.43] |
| presidio | de | 53.33 [51.87, 54.78] | 28.87 [27.83, 29.94] |
| presidio | en | 54.24 [52.78, 55.69] | 8.25 [7.56, 8.91] |
| presidio | es | 53.53 [52.07, 54.98] | 22.20 [21.13, 23.36] |
| presidio | fr | 59.65 [58.21, 61.08] | 14.35 [13.66, 15.03] |
| presidio | it | 53.11 [51.65, 54.56] | 20.95 [20.15, 21.69] |
| presidio | nl | 56.28 [54.83, 57.72] | 16.79 [16.11, 17.49] |
| presidio | pl | 53.84 [52.38, 55.29] | 25.37 [24.38, 26.36] |
| presidio | ro | 61.16 [59.73, 62.58] | 17.32 [16.75, 17.92] |
| shield | de | 44.81 [43.36, 46.26] | 24.76 [23.77, 25.74] |
| shield | en | 54.19 [52.74, 55.64] | 7.19 [6.30, 8.04] |
| shield | es | 44.83 [43.38, 46.28] | 25.54 [24.55, 26.49] |
| shield | fr | 44.01 [42.56, 45.46] | 17.50 [16.56, 18.41] |
| shield | it | 44.14 [42.70, 45.60] | 26.29 [25.26, 27.29] |
| shield | nl | 44.81 [43.36, 46.26] | 14.98 [13.54, 16.40] |
| shield | pl | 44.50 [43.05, 45.95] | 35.56 [34.36, 36.80] |
| shield | ro | 45.61 [44.16, 47.06] | 27.03 [26.30, 27.76] |

| Candidate vs comparator | Disjoint Wilson languages / 8 | Paired privacy pass / 8 | Utility pass / 8 |
|---|---:|---:|---:|
| 560m-legal vs presidio | 0 | 1 | 8 |
| 560m-legal vs shield | 0 | 1 | 8 |
| 560m-tab vs presidio | 0 | 1 | 8 |
| 560m-tab vs shield | 0 | 1 | 8 |
| kp-280m vs presidio | 8 | 8 | 2 |
| kp-280m vs shield | 8 | 8 | 5 |

| Contract line | Verdict and evidence |
|---|---|
| §1 full-conversation v2 coverage | Implemented and tested; gold-defined identifier subjects, cross-turn IDs, exact Unicode intervals. |
| §1 Wilson/support/sensitivity slices | Reported for all eight languages; UNSPECIFIED unavailable, never a measured zero. |
| §2 operators and replay | KP/Presidio local deletion receipts; Shield pinned service replace receipts. KP deployment equivalence unverified. |
| §2 corruption controls | No-mask, full-mask, label permutation, shuffled positions on full test; masked-input diagnostic n=32/language/engine. |
| §3.1 disjoint Wilson | Per-language checks above; insufficient alone for acceptance. |
| §3.1 three independent training seeds | Not established: one seed per KP checkpoint. |
| §3.2 paired conversation bootstrap | Reported for all/sensitivity slices and utility, 2,000 resamples, seed 126. |
| §3.3 no-worse over-redaction | Per-language checks above; no pooled-average substitute. |
| §3.3 RO/PL zero floors; TAB anchor | Historical specifications and all existing board rows retained byte-for-byte as canonical JSON; new operators not rescored on anchors. |
| §3.4 all eight languages and worst language | Full 5×8 dev matrix; no gateway-wide acceptance. |
| §3.4 reviewed gold and disjointness | Not established: native review and semantic family/subject/translation review pending. |
| §4 p95 and CI <=250 ms | Not measured. No service/load trial in this quality run. |
| §4 >=15 successful req/s at 16 offered | Not measured. |
| §4 errors/timeouts/refusals <=0.1% | Not measured under load. Quality inference failures fail closed. |
| §4 1,000 ms deadline/cancel | Not measured. |
| §4 zero bypass/truncation | Full-input overflow operator implemented; deployed gateway behavior unverified. |
| §4 three trials and time-block CIs | Not run. |
| §4 long lane, interference, fallback | Not verified. |

No scoped privacy win or production acceptance is established. Dataset publication, native review,
three-seed verification, current-operator anchor scoring, semantic utility and deployment/load testing remain open.

| Engine | Worst-language residual leak |
|---|---|
| 560m-legal | pl: 94.76% [94.07, 95.38], n=4,506 |
| 560m-tab | pl: 65.02% [63.62, 66.40], n=4,506 |
| kp-280m | en: 36.93% [35.53, 38.35], n=4,506 |
| presidio | ro: 61.16% [59.73, 62.58], n=4,506 |
| shield | en: 54.19% [52.74, 55.64], n=4,506 |
