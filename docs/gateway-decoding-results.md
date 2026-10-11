# Gateway-trained MoE: dev-rejected strict decoding (diagnostic)

Contract v3: **loss**. Contract v2: **loss**.

Dev selection was infeasible. This is the prospectively amended strict-rule diagnostic,
not a feasible selection or a contract win; see [the amendment](gateway-decoding-diagnostic.md)
and [all dev results](gateway-decoding-dev-results.md).

Remaining seed-1 inference used two local CPU workers on disjoint configs, four threads each;
earlier inference was sequential. Model, batches, windows and decoding stayed fixed.
This scheduling change supplies no latency or SLO evidence.

Seed 2 extends the same frozen strict diagnostic by replaying verified default CPU receipts.
No decoder selection or new inference was performed for this extension; its registration is
recorded in the comparison JSON under `execution.seed2_extension`.

76 comparator receipt paths had moved during scratch archiving. Exact original SHA-256
matches were verified in the archive or preserved copies; scores were unchanged. The comparison
JSON records both original and resolved evidence paths.

Training seeds: [0, 1, 2]; seed count 3. CPU fp32, saved 512-token window, no threshold tuning.
Leak CIs are 95% Wilson; F1 and utility CIs are 2,000-cluster bootstrap, RNG seed 100.
Paired candidate-minus-comparator CIs and both verdicts: `analysis/gateway-decoding-comparison.json`.

| Config | Seed | Clusters | Subjects | F1 % [95% CI] | V2 leak % [95% CI] | Non-PII removed % [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
| tab-echr-legal-en-v1 | 0 | 127 | 3965 | 22.68 [20.15, 25.25] | 91.32 [90.41, 92.16] | 0.71 [0.50, 0.96] |
| ro-realskeleton-v1 | 0 | 1500 | 13751 | 23.45 [22.55, 24.31] | 81.32 [80.66, 81.97] | 0.75 [0.67, 0.82] |
| pl-realskeleton-v1 | 0 | 1500 | 13885 | 17.74 [17.14, 18.35] | 86.17 [85.59, 86.74] | 0.62 [0.55, 0.70] |
| ai4privacy-openpii-cs-v1 | 0 | 399 | 2526 | 10.57 [9.12, 12.08] | 89.03 [87.76, 90.19] | 0.51 [0.39, 0.65] |
| ai4privacy-openpii-de-v1 | 0 | 399 | 2555 | 11.25 [9.85, 12.60] | 87.28 [85.93, 88.52] | 0.41 [0.31, 0.51] |
| ai4privacy-openpii-el-v1 | 0 | 397 | 2434 | 9.19 [7.70, 10.70] | 92.65 [91.54, 93.62] | 0.22 [0.15, 0.30] |
| ai4privacy-openpii-fi-v1 | 0 | 399 | 2639 | 11.54 [10.14, 13.01] | 89.58 [88.36, 90.69] | 0.61 [0.46, 0.78] |
| ai4privacy-openpii-fr-v1 | 0 | 398 | 2679 | 10.88 [9.33, 12.45] | 86.56 [85.22, 87.80] | 0.74 [0.58, 0.92] |
| ai4privacy-openpii-hu-v1 | 0 | 400 | 2752 | 11.03 [9.57, 12.52] | 89.57 [88.37, 90.66] | 0.51 [0.37, 0.67] |
| ai4privacy-openpii-nl-v1 | 0 | 399 | 2623 | 10.79 [9.33, 12.28] | 88.11 [86.81, 89.29] | 0.54 [0.40, 0.70] |
| ai4privacy-openpii-pl-v1 | 0 | 397 | 2788 | 10.90 [9.53, 12.31] | 88.92 [87.70, 90.03] | 0.43 [0.32, 0.55] |
| ai4privacy-openpii-ro-v1 | 0 | 400 | 2732 | 9.59 [8.20, 10.94] | 90.52 [89.36, 91.56] | 0.58 [0.48, 0.69] |
| ai4privacy-openpii-sv-v1 | 0 | 397 | 2748 | 9.24 [7.83, 10.67] | 90.72 [89.58, 91.75] | 0.37 [0.25, 0.52] |
| de | 0 | 1500 | 3161 | 8.29 [7.03, 9.59] | 92.88 [91.93, 93.73] | 0.53 [0.41, 0.67] |
| en | 0 | 1500 | 3619 | 9.10 [7.90, 10.35] | 90.16 [89.15, 91.09] | 1.06 [0.86, 1.29] |
| es | 0 | 1500 | 3197 | 7.48 [6.28, 8.81] | 91.55 [90.54, 92.47] | 0.35 [0.26, 0.44] |
| fr | 0 | 1500 | 3285 | 7.83 [6.64, 9.09] | 91.20 [90.19, 92.12] | 0.49 [0.38, 0.61] |
| gateway-de | 0 | 1000 | 4506 | unavailable | 53.08 [51.63, 54.54] | 0.99 [0.87, 1.12] |
| gateway-en | 0 | 1000 | 4506 | unavailable | 51.26 [49.81, 52.72] | 0.39 [0.32, 0.45] |
| gateway-es | 0 | 1000 | 4506 | unavailable | 53.37 [51.91, 54.83] | 0.80 [0.68, 0.92] |
| gateway-fr | 0 | 1000 | 4506 | unavailable | 64.00 [62.59, 65.39] | 0.48 [0.40, 0.56] |
| gateway-it | 0 | 1000 | 4506 | unavailable | 69.44 [68.08, 70.77] | 1.07 [0.93, 1.23] |
| gateway-nl | 0 | 1000 | 4506 | unavailable | 86.82 [85.80, 87.77] | 1.36 [1.19, 1.55] |
| gateway-pl | 0 | 1000 | 4506 | unavailable | 98.87 [98.52, 99.14] | 2.44 [2.13, 2.75] |
| gateway-ro | 0 | 1000 | 4506 | unavailable | 88.95 [88.00, 89.83] | 0.91 [0.79, 1.03] |
| it | 0 | 1500 | 3244 | 8.24 [7.03, 9.53] | 91.99 [91.00, 92.87] | 0.33 [0.25, 0.43] |
| nl | 0 | 1500 | 3125 | 6.82 [5.67, 8.02] | 92.45 [91.47, 93.32] | 0.66 [0.51, 0.83] |
| ro-synthetic-v1 | 0 | 1500 | 6488 | 10.23 [9.40, 11.09] | 93.97 [93.37, 94.53] | 0.08 [0.04, 0.12] |
| tab-echr-legal-en-v1 | 1 | 127 | 3965 | 22.24 [19.59, 24.83] | 91.30 [90.38, 92.14] | 0.71 [0.52, 0.92] |
| ro-realskeleton-v1 | 1 | 1500 | 13751 | 16.00 [15.34, 16.69] | 86.03 [85.44, 86.60] | 0.89 [0.81, 0.97] |
| pl-realskeleton-v1 | 1 | 1500 | 13885 | 12.32 [11.73, 12.94] | 91.16 [90.68, 91.62] | 1.33 [1.19, 1.48] |
| ai4privacy-openpii-cs-v1 | 1 | 399 | 2526 | 10.93 [9.52, 12.37] | 88.88 [87.59, 90.04] | 0.52 [0.37, 0.70] |
| ai4privacy-openpii-de-v1 | 1 | 399 | 2555 | 10.76 [9.42, 12.12] | 87.36 [86.01, 88.59] | 0.50 [0.36, 0.65] |
| ai4privacy-openpii-el-v1 | 1 | 397 | 2434 | 9.19 [7.71, 10.66] | 92.11 [90.97, 93.12] | 0.20 [0.12, 0.29] |
| ai4privacy-openpii-fi-v1 | 1 | 399 | 2639 | 10.52 [9.16, 11.97] | 89.84 [88.63, 90.94] | 0.78 [0.60, 0.97] |
| ai4privacy-openpii-fr-v1 | 1 | 398 | 2679 | 10.26 [8.72, 11.85] | 87.20 [85.88, 88.41] | 0.63 [0.48, 0.80] |
| ai4privacy-openpii-hu-v1 | 1 | 400 | 2752 | 10.44 [9.06, 11.79] | 90.04 [88.87, 91.11] | 0.45 [0.32, 0.60] |
| ai4privacy-openpii-nl-v1 | 1 | 399 | 2623 | 11.54 [10.19, 13.06] | 88.33 [87.05, 89.51] | 0.60 [0.44, 0.77] |
| ai4privacy-openpii-pl-v1 | 1 | 397 | 2788 | 11.40 [9.96, 12.93] | 90.21 [89.05, 91.26] | 0.46 [0.34, 0.59] |
| ai4privacy-openpii-ro-v1 | 1 | 400 | 2732 | 9.08 [7.76, 10.46] | 90.92 [89.79, 91.94] | 0.47 [0.36, 0.59] |
| ai4privacy-openpii-sv-v1 | 1 | 397 | 2748 | 10.11 [8.55, 11.76] | 89.81 [88.62, 90.89] | 0.31 [0.20, 0.43] |
| de | 1 | 1500 | 3161 | 7.49 [6.33, 8.72] | 93.04 [92.10, 93.88] | 0.48 [0.37, 0.61] |
| en | 1 | 1500 | 3619 | 9.62 [8.35, 10.88] | 91.21 [90.25, 92.09] | 1.17 [0.94, 1.41] |
| es | 1 | 1500 | 3197 | 6.87 [5.76, 8.06] | 92.71 [91.76, 93.56] | 0.47 [0.35, 0.59] |
| fr | 1 | 1500 | 3285 | 7.45 [6.28, 8.65] | 92.18 [91.21, 93.05] | 0.45 [0.35, 0.57] |
| gateway-de | 1 | 1000 | 4506 | unavailable | 52.73 [51.27, 54.18] | 0.84 [0.73, 0.95] |
| gateway-en | 1 | 1000 | 4506 | unavailable | 48.31 [46.86, 49.77] | 1.35 [1.14, 1.56] |
| gateway-es | 1 | 1000 | 4506 | unavailable | 51.22 [49.76, 52.68] | 1.37 [1.18, 1.56] |
| gateway-fr | 1 | 1000 | 4506 | unavailable | 63.20 [61.79, 64.60] | 0.89 [0.75, 1.03] |
| gateway-it | 1 | 1000 | 4506 | unavailable | 69.51 [68.15, 70.83] | 0.94 [0.81, 1.08] |
| gateway-nl | 1 | 1000 | 4506 | unavailable | 87.19 [86.19, 88.14] | 0.86 [0.74, 0.99] |
| gateway-pl | 1 | 1000 | 4506 | unavailable | 98.80 [98.44, 99.08] | 1.89 [1.65, 2.14] |
| gateway-ro | 1 | 1000 | 4506 | unavailable | 88.46 [87.49, 89.36] | 1.01 [0.88, 1.14] |
| it | 1 | 1500 | 3244 | 8.51 [7.26, 9.76] | 92.85 [91.91, 93.69] | 0.38 [0.28, 0.49] |
| nl | 1 | 1500 | 3125 | 7.18 [5.99, 8.40] | 92.86 [91.91, 93.71] | 0.68 [0.52, 0.84] |
| ro-synthetic-v1 | 1 | 1500 | 6488 | 10.25 [9.41, 11.12] | 93.97 [93.37, 94.53] | 0.03 [0.01, 0.06] |
| tab-echr-legal-en-v1 | 2 | 127 | 3965 | 22.63 [20.13, 25.06] | 91.45 [90.54, 92.28] | 0.75 [0.53, 0.99] |
| ro-realskeleton-v1 | 2 | 1500 | 13751 | 23.96 [23.11, 24.79] | 79.62 [78.93, 80.28] | 0.91 [0.83, 0.99] |
| pl-realskeleton-v1 | 2 | 1500 | 13885 | 26.29 [25.33, 27.26] | 80.07 [79.40, 80.73] | 1.04 [0.93, 1.15] |
| ai4privacy-openpii-cs-v1 | 2 | 399 | 2526 | 10.32 [8.95, 11.87] | 88.76 [87.47, 89.93] | 0.44 [0.32, 0.58] |
| ai4privacy-openpii-de-v1 | 2 | 399 | 2555 | 10.33 [8.94, 11.72] | 88.14 [86.83, 89.34] | 0.39 [0.28, 0.53] |
| ai4privacy-openpii-el-v1 | 2 | 397 | 2434 | 9.44 [8.09, 10.78] | 92.77 [91.67, 93.73] | 0.37 [0.25, 0.49] |
| ai4privacy-openpii-fi-v1 | 2 | 399 | 2639 | 10.42 [9.15, 11.86] | 91.28 [90.15, 92.30] | 0.90 [0.71, 1.12] |
| ai4privacy-openpii-fr-v1 | 2 | 398 | 2679 | 10.08 [8.54, 11.68] | 87.91 [86.62, 89.09] | 0.57 [0.45, 0.70] |
| ai4privacy-openpii-hu-v1 | 2 | 400 | 2752 | 9.57 [8.23, 10.94] | 91.86 [90.78, 92.82] | 0.54 [0.40, 0.69] |
| ai4privacy-openpii-nl-v1 | 2 | 399 | 2623 | 9.64 [8.18, 11.13] | 90.13 [88.92, 91.21] | 0.47 [0.36, 0.60] |
| ai4privacy-openpii-pl-v1 | 2 | 397 | 2788 | 10.27 [9.03, 11.60] | 90.39 [89.24, 91.43] | 0.44 [0.34, 0.56] |
| ai4privacy-openpii-ro-v1 | 2 | 400 | 2732 | 8.95 [7.60, 10.30] | 91.00 [89.86, 92.01] | 0.52 [0.41, 0.64] |
| ai4privacy-openpii-sv-v1 | 2 | 397 | 2748 | 9.09 [7.68, 10.56] | 90.79 [89.65, 91.82] | 0.36 [0.27, 0.45] |
| de | 2 | 1500 | 3161 | 6.66 [5.55, 7.89] | 93.83 [92.94, 94.62] | 0.43 [0.32, 0.55] |
| en | 2 | 1500 | 3619 | 7.80 [6.61, 8.95] | 90.36 [89.35, 91.28] | 1.12 [0.91, 1.34] |
| es | 2 | 1500 | 3197 | 6.55 [5.30, 7.82] | 92.46 [91.49, 93.33] | 0.31 [0.22, 0.41] |
| fr | 2 | 1500 | 3285 | 6.42 [5.22, 7.60] | 91.72 [90.73, 92.61] | 0.36 [0.26, 0.47] |
| gateway-de | 2 | 1000 | 4506 | unavailable | 53.73 [52.27, 55.18] | 0.20 [0.17, 0.24] |
| gateway-en | 2 | 1000 | 4506 | unavailable | 52.44 [50.98, 53.90] | 0.06 [0.04, 0.08] |
| gateway-es | 2 | 1000 | 4506 | unavailable | 52.09 [50.63, 53.54] | 0.29 [0.23, 0.35] |
| gateway-fr | 2 | 1000 | 4506 | unavailable | 63.89 [62.48, 65.28] | 0.06 [0.05, 0.08] |
| gateway-it | 2 | 1000 | 4506 | unavailable | 69.62 [68.26, 70.94] | 0.13 [0.10, 0.16] |
| gateway-nl | 2 | 1000 | 4506 | unavailable | 86.95 [85.94, 87.90] | 0.18 [0.14, 0.22] |
| gateway-pl | 2 | 1000 | 4506 | unavailable | 99.13 [98.82, 99.37] | 0.16 [0.13, 0.20] |
| gateway-ro | 2 | 1000 | 4506 | unavailable | 89.08 [88.14, 89.96] | 0.04 [0.03, 0.05] |
| it | 2 | 1500 | 3244 | 6.85 [5.68, 8.03] | 93.96 [93.09, 94.73] | 0.19 [0.13, 0.26] |
| nl | 2 | 1500 | 3125 | 5.93 [4.81, 7.06] | 93.41 [92.48, 94.23] | 0.44 [0.32, 0.57] |
| ro-synthetic-v1 | 2 | 1500 | 6488 | 10.25 [9.41, 11.12] | 93.97 [93.37, 94.53] | 0.09 [0.06, 0.13] |

RO/PL legacy zero floors: FAIL. All legacy metrics and their Wilson/bootstrap intervals remain in the aggregate artifact.
Worst gateway language by all-identifier leakage: {'0': 'gateway-pl', '1': 'gateway-pl', '2': 'gateway-pl'}.

Gateway synthetic test stays dev; its overlapping/token-colliding annotations do not support legacy F1/
leakage, so those metrics are unavailable. OpenPII retains validation split. Italian/legal real-skeleton
are unavailable at the frozen source revision. No gold is dropped or relabelled to manufacture scores.

Comparators retain original runtime, truncation and operators. RES-100 seed0 uses its raw default
predictions before calibration. The TAB comparator is res104-tab-seed0, not 560m-legal.
Base/RES-100 use 256-token windows; candidate uses its saved default of 512. Shield is distinct from Presidio.

No overall win is established. Unverified: independent training lineage audit; native review and source/subject/scenario-family/translation disjointness; reviewed held-out challenge; service deployment equivalence and CPU load/SLO; semantic utility; empirical attacker re-identification.

## Legacy national-ID zero floors

Any observed leak fails the frozen anchor under both contracts. Document counts are listed above.

| Config | Seed | ID subjects | Missed | Legacy leak % [95% Wilson CI] | Zero-floor gate |
|---|---:|---:|---:|---:|---|
| ro-realskeleton-v1 | 0 | 1123 | 1123 | 100.00 [99.66, 100.00] | FAIL |
| pl-realskeleton-v1 | 0 | 1096 | 1094 | 99.82 [99.34, 99.95] | FAIL |
| ro-realskeleton-v1 | 1 | 1123 | 1123 | 100.00 [99.66, 100.00] | FAIL |
| pl-realskeleton-v1 | 1 | 1096 | 1095 | 99.91 [99.48, 99.98] | FAIL |
| ro-realskeleton-v1 | 2 | 1123 | 1059 | 94.30 [92.79, 95.51] | FAIL |
| pl-realskeleton-v1 | 2 | 1096 | 835 | 76.19 [73.58, 78.61] | FAIL |

## TAB DIRECT endpoint

The separately registered DIRECT endpoint uses the same documents and its own subject denominator.

| Seed | Documents | DIRECT subjects | V2 DIRECT leak % [95% Wilson CI] |
|---|---:|---:|---:|
| 0 | 127 | 264 | 92.42 [88.59, 95.04] |
| 1 | 127 | 264 | 92.42 [88.59, 95.04] |
| 2 | 127 | 264 | 92.80 [89.03, 95.34] |

## Training-seed spread

Min–max of per-seed point estimates, in percent; these ranges are not confidence intervals.
The per-seed CIs and denominators are above. Repeated gold is never pooled across seeds.

| Config | Seeds | F1 % range | V2 all leak % range | Non-PII removed % range |
|---|---:|---:|---:|---:|
| tab-echr-legal-en-v1 | 3 | 22.24–22.68 | 91.30–91.45 | 0.71–0.75 |
| ro-realskeleton-v1 | 3 | 16.00–23.96 | 79.62–86.03 | 0.75–0.91 |
| pl-realskeleton-v1 | 3 | 12.32–26.29 | 80.07–91.16 | 0.62–1.33 |
| ai4privacy-openpii-cs-v1 | 3 | 10.32–10.93 | 88.76–89.03 | 0.44–0.52 |
| ai4privacy-openpii-de-v1 | 3 | 10.33–11.25 | 87.28–88.14 | 0.39–0.50 |
| ai4privacy-openpii-el-v1 | 3 | 9.19–9.44 | 92.11–92.77 | 0.20–0.37 |
| ai4privacy-openpii-fi-v1 | 3 | 10.42–11.54 | 89.58–91.28 | 0.61–0.90 |
| ai4privacy-openpii-fr-v1 | 3 | 10.08–10.88 | 86.56–87.91 | 0.57–0.74 |
| ai4privacy-openpii-hu-v1 | 3 | 9.57–11.03 | 89.57–91.86 | 0.45–0.54 |
| ai4privacy-openpii-nl-v1 | 3 | 9.64–11.54 | 88.11–90.13 | 0.47–0.60 |
| ai4privacy-openpii-pl-v1 | 3 | 10.27–11.40 | 88.92–90.39 | 0.43–0.46 |
| ai4privacy-openpii-ro-v1 | 3 | 8.95–9.59 | 90.52–91.00 | 0.47–0.58 |
| ai4privacy-openpii-sv-v1 | 3 | 9.09–10.11 | 89.81–90.79 | 0.31–0.37 |
| de | 3 | 6.66–8.29 | 92.88–93.83 | 0.43–0.53 |
| en | 3 | 7.80–9.62 | 90.16–91.21 | 1.06–1.17 |
| es | 3 | 6.55–7.48 | 91.55–92.71 | 0.31–0.47 |
| fr | 3 | 6.42–7.83 | 91.20–92.18 | 0.36–0.49 |
| gateway-de | 3 | unavailable | 52.73–53.73 | 0.20–0.99 |
| gateway-en | 3 | unavailable | 48.31–52.44 | 0.06–1.35 |
| gateway-es | 3 | unavailable | 51.22–53.37 | 0.29–1.37 |
| gateway-fr | 3 | unavailable | 63.20–64.00 | 0.06–0.89 |
| gateway-it | 3 | unavailable | 69.44–69.62 | 0.13–1.07 |
| gateway-nl | 3 | unavailable | 86.82–87.19 | 0.18–1.36 |
| gateway-pl | 3 | unavailable | 98.80–99.13 | 0.16–2.44 |
| gateway-ro | 3 | unavailable | 88.46–89.08 | 0.04–1.01 |
| it | 3 | 6.85–8.51 | 91.99–93.96 | 0.19–0.38 |
| nl | 3 | 5.93–7.18 | 92.45–93.41 | 0.44–0.68 |
| ro-synthetic-v1 | 3 | 10.23–10.25 | 93.97–93.97 | 0.03–0.09 |

## Three-seed numerical gate

Seed-count requirement: met (3 training seeds).
Each listed comparator passes disjoint Wilson privacy, paired privacy and utility gates on
the same endpoint for every seed. An empty cell is shown as none; this is not a contract win.
Legacy zero floors are reported above; native review and held-out disjointness remain unverified.

| Config / endpoint | V2 passing comparators (all seeds) | V3 passing comparators (all seeds) |
|---|---|---|
| ai4privacy-openpii-cs-v1/all | none | none |
| ai4privacy-openpii-de-v1/all | none | none |
| ai4privacy-openpii-el-v1/all | none | none |
| ai4privacy-openpii-fi-v1/all | none | none |
| ai4privacy-openpii-fr-v1/all | none | none |
| ai4privacy-openpii-hu-v1/all | none | none |
| ai4privacy-openpii-nl-v1/all | none | none |
| ai4privacy-openpii-pl-v1/all | none | none |
| ai4privacy-openpii-ro-v1/all | none | none |
| ai4privacy-openpii-sv-v1/all | none | none |
| de/all | none | none |
| en/all | none | none |
| es/all | none | none |
| fr/all | none | none |
| gateway-de/all | none | 560m-tab |
| gateway-en/all | none | none |
| gateway-es/all | none | none |
| gateway-fr/all | none | none |
| gateway-it/all | none | none |
| gateway-nl/all | none | none |
| gateway-pl/all | none | none |
| gateway-ro/all | none | none |
| it/all | none | none |
| nl/all | none | none |
| pl-realskeleton-v1/all | none | none |
| ro-realskeleton-v1/all | none | none |
| ro-synthetic-v1/all | none | none |
| tab-echr-legal-en-v1/all | none | none |
| tab-echr-legal-en-v1/DIRECT | none | none |

## Paired anchor and worst-language comparisons

All deltas below are candidate minus comparator in percentage points (95% cluster bootstrap).
TAB uses its separately registered DIRECT endpoint; other rows use all identifier subjects.
The worst gateway language is descriptive, not a selected replacement for the eight-language matrix.
Numerical pass counts are not contract wins; review/disjointness requirements remain.

| Config / endpoint | Seed | Comparator | Leak delta [95% CI] | Utility delta [95% CI] | V2 numerical pass | V3 numerical pass |
|---|---:|---|---:|---:|---|---|
| tab-echr-legal-en-v1/DIRECT | 0 | base | 26.14 [21.15, 30.83] | 0.47 [0.26, 0.72] | False | False |
| tab-echr-legal-en-v1/DIRECT | 0 | res100-seed0 | 90.53 [86.84, 93.73] | -0.37 [-0.47, -0.28] | False | False |
| tab-echr-legal-en-v1/DIRECT | 0 | kp-280m | 76.14 [70.83, 81.58] | -1.81 [-2.12, -1.53] | False | False |
| tab-echr-legal-en-v1/DIRECT | 0 | 560m-tab | 59.47 [53.23, 65.37] | 0.13 [-0.00, 0.26] | False | False |
| tab-echr-legal-en-v1/DIRECT | 0 | presidio | -1.14 [-5.41, 2.94] | -1.73 [-2.02, -1.45] | False | False |
| tab-echr-legal-en-v1/DIRECT | 0 | shield | -1.14 [-5.38, 2.96] | -8.46 [-9.09, -7.83] | False | False |
| ro-realskeleton-v1/all | 0 | base | 53.31 [52.40, 54.24] | -2.68 [-2.86, -2.48] | False | False |
| ro-realskeleton-v1/all | 0 | res100-seed0 | 65.00 [64.32, 65.66] | -4.26 [-4.49, -4.02] | False | False |
| ro-realskeleton-v1/all | 0 | kp-280m | 73.19 [72.24, 74.19] | -3.05 [-3.24, -2.85] | False | False |
| ro-realskeleton-v1/all | 0 | 560m-tab | 8.51 [7.64, 9.43] | 0.67 [0.59, 0.75] | False | False |
| ro-realskeleton-v1/all | 0 | presidio | 42.16 [41.40, 42.89] | -6.53 [-6.88, -6.21] | False | False |
| ro-realskeleton-v1/all | 0 | shield | 33.68 [32.98, 34.36] | -21.42 [-21.83, -20.99] | False | False |
| pl-realskeleton-v1/all | 0 | base | 63.36 [62.60, 64.09] | -7.37 [-7.71, -7.04] | False | False |
| pl-realskeleton-v1/all | 0 | res100-seed0 | 69.72 [69.26, 70.16] | -9.29 [-9.53, -9.06] | False | False |
| pl-realskeleton-v1/all | 0 | kp-280m | 77.27 [76.57, 77.96] | -2.88 [-3.09, -2.67] | False | False |
| pl-realskeleton-v1/all | 0 | 560m-tab | 11.01 [10.04, 11.93] | 0.61 [0.54, 0.69] | False | False |
| pl-realskeleton-v1/all | 0 | presidio | 54.58 [54.11, 55.04] | -23.08 [-23.55, -22.59] | False | False |
| pl-realskeleton-v1/all | 0 | shield | 36.74 [36.08, 37.37] | -28.62 [-29.49, -27.75] | False | False |
| gateway-pl/all | 0 | base | 80.47 [78.55, 82.29] | -1.68 [-1.97, -1.37] | False | False |
| gateway-pl/all | 0 | res100-seed0 | 77.12 [75.27, 79.02] | -2.50 [-2.76, -2.24] | False | False |
| gateway-pl/all | 0 | kp-280m | 67.38 [66.06, 68.76] | -16.24 [-17.69, -14.83] | False | False |
| gateway-pl/all | 0 | 560m-tab | 33.84 [32.45, 35.14] | 1.90 [1.57, 2.24] | False | False |
| gateway-pl/all | 0 | presidio | 45.03 [43.77, 46.31] | -22.93 [-23.75, -22.09] | False | False |
| gateway-pl/all | 0 | shield | 54.37 [53.36, 55.42] | -33.12 [-34.21, -32.05] | False | False |
| tab-echr-legal-en-v1/DIRECT | 1 | base | 26.14 [21.07, 30.77] | 0.47 [0.28, 0.69] | False | False |
| tab-echr-legal-en-v1/DIRECT | 1 | res100-seed0 | 90.53 [86.94, 93.73] | -0.37 [-0.50, -0.26] | False | False |
| tab-echr-legal-en-v1/DIRECT | 1 | kp-280m | 76.14 [70.54, 81.61] | -1.80 [-2.11, -1.54] | False | False |
| tab-echr-legal-en-v1/DIRECT | 1 | 560m-tab | 59.47 [53.31, 65.49] | 0.13 [0.01, 0.26] | False | False |
| tab-echr-legal-en-v1/DIRECT | 1 | presidio | -1.14 [-5.38, 2.96] | -1.73 [-2.00, -1.47] | False | False |
| tab-echr-legal-en-v1/DIRECT | 1 | shield | -1.14 [-5.54, 3.05] | -8.46 [-9.09, -7.85] | False | False |
| ro-realskeleton-v1/all | 1 | base | 58.02 [57.21, 58.80] | -2.54 [-2.72, -2.35] | False | False |
| ro-realskeleton-v1/all | 1 | res100-seed0 | 69.70 [69.11, 70.27] | -4.12 [-4.37, -3.88] | False | False |
| ro-realskeleton-v1/all | 1 | kp-280m | 77.89 [77.01, 78.74] | -2.91 [-3.10, -2.73] | False | False |
| ro-realskeleton-v1/all | 1 | 560m-tab | 13.21 [12.46, 13.94] | 0.81 [0.73, 0.89] | False | False |
| ro-realskeleton-v1/all | 1 | presidio | 46.87 [46.15, 47.56] | -6.40 [-6.74, -6.07] | False | False |
| ro-realskeleton-v1/all | 1 | shield | 38.38 [37.68, 39.05] | -21.28 [-21.71, -20.84] | False | False |
| pl-realskeleton-v1/all | 1 | base | 68.35 [67.61, 69.06] | -6.66 [-7.09, -6.24] | False | False |
| pl-realskeleton-v1/all | 1 | res100-seed0 | 74.71 [74.20, 75.21] | -8.58 [-8.81, -8.35] | False | False |
| pl-realskeleton-v1/all | 1 | kp-280m | 82.26 [81.70, 82.82] | -2.17 [-2.34, -2.00] | False | False |
| pl-realskeleton-v1/all | 1 | 560m-tab | 16.00 [15.13, 16.83] | 1.32 [1.18, 1.47] | False | False |
| pl-realskeleton-v1/all | 1 | presidio | 59.57 [59.15, 59.98] | -22.37 [-22.79, -21.94] | False | False |
| pl-realskeleton-v1/all | 1 | shield | 41.73 [41.05, 42.40] | -27.91 [-28.68, -27.13] | False | False |
| gateway-pl/all | 1 | base | 80.40 [78.54, 82.25] | -2.23 [-2.57, -1.90] | False | False |
| gateway-pl/all | 1 | res100-seed0 | 77.05 [75.21, 78.90] | -3.04 [-3.30, -2.78] | False | False |
| gateway-pl/all | 1 | kp-280m | 67.31 [65.98, 68.70] | -16.79 [-18.29, -15.32] | False | False |
| gateway-pl/all | 1 | 560m-tab | 33.78 [32.42, 35.02] | 1.36 [1.09, 1.62] | False | False |
| gateway-pl/all | 1 | presidio | 44.96 [43.67, 46.24] | -23.47 [-24.33, -22.62] | False | False |
| gateway-pl/all | 1 | shield | 54.31 [53.30, 55.37] | -33.66 [-34.76, -32.58] | False | False |
| tab-echr-legal-en-v1/DIRECT | 2 | base | 26.52 [21.51, 31.06] | 0.51 [0.30, 0.74] | False | False |
| tab-echr-legal-en-v1/DIRECT | 2 | res100-seed0 | 90.91 [87.55, 93.89] | -0.34 [-0.46, -0.22] | False | False |
| tab-echr-legal-en-v1/DIRECT | 2 | kp-280m | 76.52 [71.22, 81.82] | -1.77 [-2.10, -1.49] | False | False |
| tab-echr-legal-en-v1/DIRECT | 2 | 560m-tab | 59.85 [53.64, 65.79] | 0.16 [0.02, 0.31] | False | False |
| tab-echr-legal-en-v1/DIRECT | 2 | presidio | -0.76 [-4.98, 3.08] | -1.70 [-1.98, -1.42] | False | False |
| tab-echr-legal-en-v1/DIRECT | 2 | shield | -0.76 [-5.15, 3.42] | -8.42 [-9.05, -7.79] | False | False |
| ro-realskeleton-v1/all | 2 | base | 51.60 [50.74, 52.50] | -2.52 [-2.71, -2.33] | False | False |
| ro-realskeleton-v1/all | 2 | res100-seed0 | 63.29 [62.54, 64.06] | -4.10 [-4.34, -3.89] | False | False |
| ro-realskeleton-v1/all | 2 | kp-280m | 71.48 [70.64, 72.30] | -2.89 [-3.08, -2.70] | False | False |
| ro-realskeleton-v1/all | 2 | 560m-tab | 6.80 [5.89, 7.75] | 0.83 [0.75, 0.91] | False | False |
| ro-realskeleton-v1/all | 2 | presidio | 40.46 [39.68, 41.23] | -6.37 [-6.71, -6.05] | False | False |
| ro-realskeleton-v1/all | 2 | shield | 31.97 [31.05, 32.93] | -21.26 [-21.68, -20.82] | False | False |
| pl-realskeleton-v1/all | 2 | base | 57.26 [56.42, 58.09] | -6.96 [-7.32, -6.62] | False | False |
| pl-realskeleton-v1/all | 2 | res100-seed0 | 63.62 [62.88, 64.37] | -8.88 [-9.12, -8.67] | False | False |
| pl-realskeleton-v1/all | 2 | kp-280m | 71.17 [70.34, 72.00] | -2.47 [-2.68, -2.25] | False | False |
| pl-realskeleton-v1/all | 2 | 560m-tab | 4.91 [3.83, 6.03] | 1.03 [0.92, 1.14] | False | False |
| pl-realskeleton-v1/all | 2 | presidio | 48.48 [47.79, 49.13] | -22.67 [-23.13, -22.20] | False | False |
| pl-realskeleton-v1/all | 2 | shield | 30.64 [29.73, 31.58] | -28.21 [-29.06, -27.36] | False | False |
| gateway-pl/all | 2 | base | 80.74 [78.84, 82.58] | -3.96 [-4.41, -3.50] | False | False |
| gateway-pl/all | 2 | res100-seed0 | 77.39 [75.54, 79.28] | -4.78 [-5.21, -4.34] | False | False |
| gateway-pl/all | 2 | kp-280m | 67.64 [66.31, 68.99] | -18.52 [-20.19, -16.87] | False | False |
| gateway-pl/all | 2 | 560m-tab | 34.11 [32.75, 35.36] | -0.38 [-0.49, -0.27] | False | False |
| gateway-pl/all | 2 | presidio | 45.30 [44.02, 46.60] | -25.21 [-26.18, -24.25] | False | False |
| gateway-pl/all | 2 | shield | 54.64 [53.64, 55.68] | -35.40 [-36.63, -34.20] | False | False |
