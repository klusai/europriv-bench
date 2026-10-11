# Gateway-trained MoE: default operating point

Contract v3: **loss**. Contract v2: **loss**.

76 comparator receipt paths had moved during scratch archiving. Exact original SHA-256
matches were verified in the archive or preserved copies; scores were unchanged. The comparison
JSON records both original and resolved evidence paths.

Training seeds: [0, 1, 2]; seed count 3. CPU fp32, saved 512-token window, no threshold tuning.
Leak CIs are 95% Wilson; F1 and utility CIs are 2,000-cluster bootstrap, RNG seed 100.
Paired candidate-minus-comparator CIs and both verdicts: `analysis/gateway-moe-comparison.json`.

| Config | Seed | Clusters | Subjects | F1 % [95% CI] | V2 leak % [95% CI] | Non-PII removed % [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
| tab-echr-legal-en-v1 | 0 | 127 | 3965 | 75.31 [73.06, 77.55] | 17.83 [16.67, 19.05] | 1.05 [0.80, 1.35] |
| ro-realskeleton-v1 | 0 | 1500 | 13751 | 61.89 [61.45, 62.34] | 14.82 [14.24, 15.42] | 4.78 [4.62, 4.95] |
| pl-realskeleton-v1 | 0 | 1500 | 13885 | 63.42 [62.93, 63.92] | 14.54 [13.96, 15.14] | 12.46 [12.24, 12.70] |
| ai4privacy-openpii-cs-v1 | 0 | 399 | 2526 | 41.75 [39.83, 43.64] | 22.17 [20.59, 23.83] | 2.38 [2.09, 2.70] |
| ai4privacy-openpii-de-v1 | 0 | 399 | 2555 | 46.14 [44.15, 48.05] | 10.96 [9.81, 12.23] | 1.87 [1.60, 2.15] |
| ai4privacy-openpii-el-v1 | 0 | 397 | 2434 | 41.71 [39.79, 43.63] | 32.83 [30.99, 34.72] | 0.94 [0.76, 1.14] |
| ai4privacy-openpii-fi-v1 | 0 | 399 | 2639 | 39.52 [37.57, 41.44] | 17.81 [16.40, 19.32] | 4.85 [4.31, 5.43] |
| ai4privacy-openpii-fr-v1 | 0 | 398 | 2679 | 48.32 [46.67, 49.93] | 9.07 [8.04, 10.22] | 2.96 [2.58, 3.40] |
| ai4privacy-openpii-hu-v1 | 0 | 400 | 2752 | 38.37 [36.84, 39.92] | 25.87 [24.27, 27.54] | 3.49 [3.08, 3.95] |
| ai4privacy-openpii-nl-v1 | 0 | 399 | 2623 | 49.09 [47.19, 50.92] | 10.83 [9.69, 12.07] | 2.21 [1.93, 2.50] |
| ai4privacy-openpii-pl-v1 | 0 | 397 | 2788 | 42.04 [40.35, 43.82] | 20.70 [19.23, 22.24] | 2.39 [2.09, 2.71] |
| ai4privacy-openpii-ro-v1 | 0 | 400 | 2732 | 42.58 [40.88, 44.22] | 16.58 [15.23, 18.02] | 2.13 [1.87, 2.41] |
| ai4privacy-openpii-sv-v1 | 0 | 397 | 2748 | 46.56 [44.75, 48.24] | 15.98 [14.65, 17.39] | 1.83 [1.57, 2.11] |
| de | 0 | 1500 | 3161 | 48.47 [46.45, 50.45] | 29.99 [28.42, 31.61] | 1.57 [1.32, 1.83] |
| en | 0 | 1500 | 3619 | 45.00 [43.11, 46.95] | 24.26 [22.89, 25.68] | 1.92 [1.64, 2.21] |
| es | 0 | 1500 | 3197 | 46.48 [44.52, 48.46] | 29.34 [27.79, 30.94] | 1.12 [0.93, 1.33] |
| fr | 0 | 1500 | 3285 | 46.36 [44.41, 48.34] | 27.37 [25.87, 28.92] | 1.55 [1.33, 1.78] |
| gateway-de | 0 | 1000 | 4506 | unavailable | 14.09 [13.11, 15.14] | 5.13 [4.55, 5.74] |
| gateway-en | 0 | 1000 | 4506 | unavailable | 13.34 [12.38, 14.36] | 1.33 [1.16, 1.52] |
| gateway-es | 0 | 1000 | 4506 | unavailable | 13.89 [12.91, 14.93] | 2.44 [2.15, 2.74] |
| gateway-fr | 0 | 1000 | 4506 | unavailable | 11.45 [10.55, 12.41] | 1.49 [1.30, 1.70] |
| gateway-it | 0 | 1000 | 4506 | unavailable | 11.70 [10.79, 12.67] | 3.28 [2.93, 3.66] |
| gateway-nl | 0 | 1000 | 4506 | unavailable | 13.20 [12.25, 14.22] | 3.71 [3.30, 4.15] |
| gateway-pl | 0 | 1000 | 4506 | unavailable | 9.76 [8.93, 10.67] | 11.58 [10.38, 12.82] |
| gateway-ro | 0 | 1000 | 4506 | unavailable | 14.96 [13.95, 16.03] | 4.26 [3.77, 4.78] |
| it | 0 | 1500 | 3244 | 44.29 [42.26, 46.28] | 24.14 [22.70, 25.64] | 1.32 [1.14, 1.53] |
| nl | 0 | 1500 | 3125 | 45.86 [43.95, 47.79] | 28.03 [26.48, 29.63] | 2.09 [1.81, 2.37] |
| ro-synthetic-v1 | 0 | 1500 | 6488 | 96.65 [96.17, 97.09] | 0.03 [0.01, 0.11] | 0.72 [0.62, 0.83] |
| tab-echr-legal-en-v1 | 1 | 127 | 3965 | 75.78 [73.51, 78.05] | 17.65 [16.50, 18.87] | 1.05 [0.80, 1.32] |
| ro-realskeleton-v1 | 1 | 1500 | 13751 | 59.97 [59.49, 60.44] | 14.70 [14.12, 15.30] | 8.15 [7.92, 8.41] |
| pl-realskeleton-v1 | 1 | 1500 | 13885 | 64.19 [63.75, 64.63] | 18.99 [18.35, 19.65] | 14.10 [13.67, 14.52] |
| ai4privacy-openpii-cs-v1 | 1 | 399 | 2526 | 43.45 [41.61, 45.28] | 22.49 [20.90, 24.16] | 2.37 [2.06, 2.70] |
| ai4privacy-openpii-de-v1 | 1 | 399 | 2555 | 45.40 [43.53, 47.38] | 14.40 [13.10, 15.82] | 1.97 [1.68, 2.26] |
| ai4privacy-openpii-el-v1 | 1 | 397 | 2434 | 40.87 [38.99, 42.84] | 32.21 [30.38, 34.09] | 1.21 [1.02, 1.42] |
| ai4privacy-openpii-fi-v1 | 1 | 399 | 2639 | 38.21 [36.33, 40.16] | 17.28 [15.88, 18.77] | 4.96 [4.30, 5.76] |
| ai4privacy-openpii-fr-v1 | 1 | 398 | 2679 | 47.94 [46.03, 49.68] | 10.86 [9.74, 12.10] | 2.64 [2.32, 2.98] |
| ai4privacy-openpii-hu-v1 | 1 | 400 | 2752 | 38.28 [36.61, 39.94] | 29.58 [27.90, 31.31] | 3.05 [2.64, 3.49] |
| ai4privacy-openpii-nl-v1 | 1 | 399 | 2623 | 49.51 [47.57, 51.61] | 11.28 [10.13, 12.55] | 2.42 [2.15, 2.71] |
| ai4privacy-openpii-pl-v1 | 1 | 397 | 2788 | 40.43 [38.52, 42.28] | 21.38 [19.90, 22.94] | 2.54 [2.21, 2.87] |
| ai4privacy-openpii-ro-v1 | 1 | 400 | 2732 | 42.58 [40.85, 44.23] | 17.86 [16.47, 19.34] | 2.00 [1.77, 2.26] |
| ai4privacy-openpii-sv-v1 | 1 | 397 | 2748 | 45.71 [43.97, 47.45] | 17.07 [15.71, 18.52] | 1.79 [1.56, 2.06] |
| de | 1 | 1500 | 3161 | 47.43 [45.39, 49.50] | 33.19 [31.57, 34.85] | 1.34 [1.14, 1.55] |
| en | 1 | 1500 | 3619 | 46.11 [44.31, 48.13] | 27.11 [25.68, 28.58] | 2.04 [1.74, 2.35] |
| es | 1 | 1500 | 3197 | 45.81 [43.87, 47.84] | 30.06 [28.49, 31.67] | 1.18 [1.00, 1.37] |
| fr | 1 | 1500 | 3285 | 44.04 [42.12, 45.98] | 31.32 [29.76, 32.93] | 1.44 [1.22, 1.65] |
| gateway-de | 1 | 1000 | 4506 | unavailable | 13.09 [12.14, 14.11] | 2.11 [1.84, 2.40] |
| gateway-en | 1 | 1000 | 4506 | unavailable | 13.40 [12.44, 14.43] | 2.55 [2.23, 2.86] |
| gateway-es | 1 | 1000 | 4506 | unavailable | 10.99 [10.11, 11.93] | 2.86 [2.53, 3.19] |
| gateway-fr | 1 | 1000 | 4506 | unavailable | 10.41 [9.55, 11.33] | 1.73 [1.51, 1.96] |
| gateway-it | 1 | 1000 | 4506 | unavailable | 10.03 [9.19, 10.94] | 2.26 [2.02, 2.51] |
| gateway-nl | 1 | 1000 | 4506 | unavailable | 12.34 [11.41, 13.33] | 2.17 [1.89, 2.48] |
| gateway-pl | 1 | 1000 | 4506 | unavailable | 9.37 [8.55, 10.25] | 9.53 [8.48, 10.57] |
| gateway-ro | 1 | 1000 | 4506 | unavailable | 12.94 [11.99, 13.95] | 3.04 [2.67, 3.40] |
| it | 1 | 1500 | 3244 | 44.79 [42.70, 46.82] | 26.76 [25.26, 28.31] | 1.26 [1.09, 1.44] |
| nl | 1 | 1500 | 3125 | 47.63 [45.68, 49.50] | 29.22 [27.65, 30.84] | 2.08 [1.83, 2.33] |
| ro-synthetic-v1 | 1 | 1500 | 6488 | 99.44 [99.27, 99.60] | 1.25 [1.01, 1.55] | 0.12 [0.08, 0.17] |
| tab-echr-legal-en-v1 | 2 | 127 | 3965 | 75.61 [73.37, 77.86] | 17.43 [16.28, 18.64] | 1.15 [0.87, 1.47] |
| ro-realskeleton-v1 | 2 | 1500 | 13751 | 51.00 [50.42, 51.63] | 16.36 [15.75, 16.99] | 10.53 [10.22, 10.87] |
| pl-realskeleton-v1 | 2 | 1500 | 13885 | 48.87 [48.22, 49.49] | 17.61 [16.98, 18.25] | 13.98 [13.70, 14.26] |
| ai4privacy-openpii-cs-v1 | 2 | 399 | 2526 | 42.77 [40.86, 44.77] | 21.93 [20.36, 23.59] | 2.19 [1.89, 2.52] |
| ai4privacy-openpii-de-v1 | 2 | 399 | 2555 | 45.28 [43.35, 47.26] | 14.87 [13.55, 16.31] | 1.87 [1.61, 2.14] |
| ai4privacy-openpii-el-v1 | 2 | 397 | 2434 | 40.91 [39.00, 42.79] | 30.40 [28.61, 32.26] | 1.59 [1.31, 1.88] |
| ai4privacy-openpii-fi-v1 | 2 | 399 | 2639 | 35.91 [33.95, 37.86] | 20.80 [19.30, 22.39] | 6.12 [5.36, 7.02] |
| ai4privacy-openpii-fr-v1 | 2 | 398 | 2679 | 46.06 [44.15, 47.89] | 13.44 [12.20, 14.78] | 2.57 [2.26, 2.90] |
| ai4privacy-openpii-hu-v1 | 2 | 400 | 2752 | 38.57 [36.79, 40.38] | 31.03 [29.33, 32.79] | 3.35 [2.90, 3.80] |
| ai4privacy-openpii-nl-v1 | 2 | 399 | 2623 | 46.79 [44.77, 48.97] | 14.87 [13.56, 16.28] | 2.10 [1.83, 2.38] |
| ai4privacy-openpii-pl-v1 | 2 | 397 | 2788 | 40.32 [38.62, 42.08] | 22.70 [21.19, 24.30] | 2.57 [2.24, 2.93] |
| ai4privacy-openpii-ro-v1 | 2 | 400 | 2732 | 40.74 [38.99, 42.57] | 18.63 [17.22, 20.13] | 2.19 [1.93, 2.48] |
| ai4privacy-openpii-sv-v1 | 2 | 397 | 2748 | 44.90 [43.07, 46.64] | 17.72 [16.34, 19.19] | 1.94 [1.67, 2.23] |
| de | 2 | 1500 | 3161 | 49.33 [47.38, 51.33] | 34.74 [33.10, 36.41] | 1.35 [1.13, 1.59] |
| en | 2 | 1500 | 3619 | 46.11 [44.22, 48.09] | 25.01 [23.62, 26.44] | 1.99 [1.71, 2.28] |
| es | 2 | 1500 | 3197 | 45.93 [43.94, 48.04] | 31.69 [30.10, 33.32] | 0.97 [0.80, 1.15] |
| fr | 2 | 1500 | 3285 | 45.18 [43.13, 47.23] | 32.09 [30.51, 33.70] | 1.18 [0.99, 1.37] |
| gateway-de | 2 | 1000 | 4506 | unavailable | 14.62 [13.62, 15.69] | 1.26 [1.04, 1.52] |
| gateway-en | 2 | 1000 | 4506 | unavailable | 14.25 [13.26, 15.30] | 0.57 [0.45, 0.70] |
| gateway-es | 2 | 1000 | 4506 | unavailable | 11.19 [10.30, 12.14] | 0.93 [0.79, 1.11] |
| gateway-fr | 2 | 1000 | 4506 | unavailable | 11.50 [10.60, 12.46] | 0.56 [0.44, 0.70] |
| gateway-it | 2 | 1000 | 4506 | unavailable | 10.96 [10.08, 11.91] | 0.74 [0.60, 0.91] |
| gateway-nl | 2 | 1000 | 4506 | unavailable | 13.09 [12.14, 14.11] | 1.05 [0.81, 1.32] |
| gateway-pl | 2 | 1000 | 4506 | unavailable | 9.57 [8.74, 10.46] | 3.66 [3.30, 4.02] |
| gateway-ro | 2 | 1000 | 4506 | unavailable | 14.38 [13.39, 15.44] | 0.75 [0.58, 0.94] |
| it | 2 | 1500 | 3244 | 42.72 [40.64, 44.76] | 30.46 [28.90, 32.06] | 0.91 [0.78, 1.05] |
| nl | 2 | 1500 | 3125 | 46.82 [44.82, 48.75] | 32.26 [30.64, 33.92] | 1.78 [1.53, 2.05] |
| ro-synthetic-v1 | 2 | 1500 | 6488 | 99.73 [99.62, 99.82] | 0.02 [0.00, 0.09] | 0.23 [0.18, 0.28] |

RO/PL legacy zero floors: FAIL. All legacy metrics and their Wilson/bootstrap intervals remain in the aggregate artifact.
Worst gateway language by all-identifier leakage: {'0': 'gateway-ro', '1': 'gateway-en', '2': 'gateway-de'}.

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
| ro-realskeleton-v1 | 0 | 1123 | 0 | 0.00 [0.00, 0.34] | PASS |
| pl-realskeleton-v1 | 0 | 1096 | 0 | 0.00 [0.00, 0.35] | PASS |
| ro-realskeleton-v1 | 1 | 1123 | 0 | 0.00 [0.00, 0.34] | PASS |
| pl-realskeleton-v1 | 1 | 1096 | 0 | 0.00 [0.00, 0.35] | PASS |
| ro-realskeleton-v1 | 2 | 1123 | 0 | 0.00 [0.00, 0.34] | PASS |
| pl-realskeleton-v1 | 2 | 1096 | 6 | 0.55 [0.25, 1.19] | FAIL |

## TAB DIRECT endpoint

The separately registered DIRECT endpoint uses the same documents and its own subject denominator.

| Seed | Documents | DIRECT subjects | V2 DIRECT leak % [95% Wilson CI] |
|---|---:|---:|---:|
| 0 | 127 | 264 | 1.52 [0.59, 3.83] |
| 1 | 127 | 264 | 1.52 [0.59, 3.83] |
| 2 | 127 | 264 | 1.89 [0.81, 4.36] |

## Training-seed spread

Min–max of per-seed point estimates, in percent; these ranges are not confidence intervals.
The per-seed CIs and denominators are above. Repeated gold is never pooled across seeds.

| Config | Seeds | F1 % range | V2 all leak % range | Non-PII removed % range |
|---|---:|---:|---:|---:|
| tab-echr-legal-en-v1 | 3 | 75.31–75.78 | 17.43–17.83 | 1.05–1.15 |
| ro-realskeleton-v1 | 3 | 51.00–61.89 | 14.70–16.36 | 4.78–10.53 |
| pl-realskeleton-v1 | 3 | 48.87–64.19 | 14.54–18.99 | 12.46–14.10 |
| ai4privacy-openpii-cs-v1 | 3 | 41.75–43.45 | 21.93–22.49 | 2.19–2.38 |
| ai4privacy-openpii-de-v1 | 3 | 45.28–46.14 | 10.96–14.87 | 1.87–1.97 |
| ai4privacy-openpii-el-v1 | 3 | 40.87–41.71 | 30.40–32.83 | 0.94–1.59 |
| ai4privacy-openpii-fi-v1 | 3 | 35.91–39.52 | 17.28–20.80 | 4.85–6.12 |
| ai4privacy-openpii-fr-v1 | 3 | 46.06–48.32 | 9.07–13.44 | 2.57–2.96 |
| ai4privacy-openpii-hu-v1 | 3 | 38.28–38.57 | 25.87–31.03 | 3.05–3.49 |
| ai4privacy-openpii-nl-v1 | 3 | 46.79–49.51 | 10.83–14.87 | 2.10–2.42 |
| ai4privacy-openpii-pl-v1 | 3 | 40.32–42.04 | 20.70–22.70 | 2.39–2.57 |
| ai4privacy-openpii-ro-v1 | 3 | 40.74–42.58 | 16.58–18.63 | 2.00–2.19 |
| ai4privacy-openpii-sv-v1 | 3 | 44.90–46.56 | 15.98–17.72 | 1.79–1.94 |
| de | 3 | 47.43–49.33 | 29.99–34.74 | 1.34–1.57 |
| en | 3 | 45.00–46.11 | 24.26–27.11 | 1.92–2.04 |
| es | 3 | 45.81–46.48 | 29.34–31.69 | 0.97–1.18 |
| fr | 3 | 44.04–46.36 | 27.37–32.09 | 1.18–1.55 |
| gateway-de | 3 | unavailable | 13.09–14.62 | 1.26–5.13 |
| gateway-en | 3 | unavailable | 13.34–14.25 | 0.57–2.55 |
| gateway-es | 3 | unavailable | 10.99–13.89 | 0.93–2.86 |
| gateway-fr | 3 | unavailable | 10.41–11.50 | 0.56–1.73 |
| gateway-it | 3 | unavailable | 10.03–11.70 | 0.74–3.28 |
| gateway-nl | 3 | unavailable | 12.34–13.20 | 1.05–3.71 |
| gateway-pl | 3 | unavailable | 9.37–9.76 | 3.66–11.58 |
| gateway-ro | 3 | unavailable | 12.94–14.96 | 0.75–4.26 |
| it | 3 | 42.72–44.79 | 24.14–30.46 | 0.91–1.32 |
| nl | 3 | 45.86–47.63 | 28.03–32.26 | 1.78–2.09 |
| ro-synthetic-v1 | 3 | 96.65–99.73 | 0.02–1.25 | 0.12–0.72 |

## Three-seed numerical gate

Seed-count requirement: met (3 training seeds).
Each listed comparator passes disjoint Wilson privacy, paired privacy and utility gates on
the same endpoint for every seed. An empty cell is shown as none; this is not a contract win.
Legacy zero floors are reported above; native review and held-out disjointness remain unverified.

| Config / endpoint | V2 passing comparators (all seeds) | V3 passing comparators (all seeds) |
|---|---|---|
| ai4privacy-openpii-cs-v1/all | presidio, shield | presidio, shield |
| ai4privacy-openpii-de-v1/all | presidio, shield | presidio, shield |
| ai4privacy-openpii-el-v1/all | presidio | presidio |
| ai4privacy-openpii-fi-v1/all | presidio, shield | presidio, shield |
| ai4privacy-openpii-fr-v1/all | presidio, shield | presidio, shield |
| ai4privacy-openpii-hu-v1/all | presidio, shield | presidio, shield |
| ai4privacy-openpii-nl-v1/all | presidio, shield | presidio, shield |
| ai4privacy-openpii-pl-v1/all | presidio, shield | presidio, shield |
| ai4privacy-openpii-ro-v1/all | presidio, shield | presidio, shield |
| ai4privacy-openpii-sv-v1/all | presidio, shield | presidio, shield |
| de/all | none | none |
| en/all | shield | presidio, shield |
| es/all | presidio | 560m-tab, presidio |
| fr/all | presidio | presidio |
| gateway-de/all | kp-280m, presidio, shield | kp-280m, presidio, shield |
| gateway-en/all | kp-280m, presidio, shield | kp-280m, presidio, shield |
| gateway-es/all | kp-280m, presidio, shield | res100-seed0, kp-280m, presidio, shield |
| gateway-fr/all | res100-seed0, kp-280m, presidio, shield | res100-seed0, kp-280m, presidio, shield |
| gateway-it/all | kp-280m, presidio, shield | res100-seed0, kp-280m, presidio, shield |
| gateway-nl/all | kp-280m, presidio, shield | kp-280m, presidio, shield |
| gateway-pl/all | kp-280m, presidio, shield | kp-280m, presidio, shield |
| gateway-ro/all | kp-280m, presidio, shield | kp-280m, presidio, shield |
| it/all | presidio | presidio |
| nl/all | none | none |
| pl-realskeleton-v1/all | presidio, shield | presidio, shield |
| ro-realskeleton-v1/all | shield | shield |
| ro-synthetic-v1/all | base, kp-280m, presidio, shield | base, kp-280m, 560m-tab, presidio, shield |
| tab-echr-legal-en-v1/all | kp-280m, presidio, shield | kp-280m, 560m-tab, presidio, shield |
| tab-echr-legal-en-v1/DIRECT | kp-280m, presidio, shield | kp-280m, 560m-tab, presidio, shield |

## Paired anchor and worst-language comparisons

All deltas below are candidate minus comparator in percentage points (95% cluster bootstrap).
TAB uses its separately registered DIRECT endpoint; other rows use all identifier subjects.
The worst gateway language is descriptive, not a selected replacement for the eight-language matrix.
Numerical pass counts are not contract wins; review/disjointness requirements remain.

| Config / endpoint | Seed | Comparator | Leak delta [95% CI] | Utility delta [95% CI] | V2 numerical pass | V3 numerical pass |
|---|---:|---|---:|---:|---|---|
| tab-echr-legal-en-v1/DIRECT | 0 | base | -64.77 [-68.80, -60.54] | 0.81 [0.57, 1.10] | False | False |
| tab-echr-legal-en-v1/DIRECT | 0 | res100-seed0 | -0.38 [-1.86, 0.77] | -0.03 [-0.10, 0.04] | False | False |
| tab-echr-legal-en-v1/DIRECT | 0 | kp-280m | -14.77 [-18.92, -10.69] | -1.46 [-1.78, -1.17] | True | True |
| tab-echr-legal-en-v1/DIRECT | 0 | 560m-tab | -31.44 [-36.54, -26.47] | 0.47 [0.32, 0.64] | False | True |
| tab-echr-legal-en-v1/DIRECT | 0 | presidio | -92.05 [-94.98, -89.14] | -1.39 [-1.68, -1.09] | True | True |
| tab-echr-legal-en-v1/DIRECT | 0 | shield | -92.05 [-94.96, -89.14] | -8.11 [-8.75, -7.48] | True | True |
| ro-realskeleton-v1/all | 0 | base | -13.19 [-13.92, -12.46] | 1.36 [1.12, 1.61] | False | False |
| ro-realskeleton-v1/all | 0 | res100-seed0 | -1.51 [-1.94, -1.08] | -0.22 [-0.51, 0.06] | False | True |
| ro-realskeleton-v1/all | 0 | kp-280m | 6.68 [5.80, 7.51] | 0.99 [0.79, 1.19] | False | False |
| ro-realskeleton-v1/all | 0 | 560m-tab | -58.00 [-58.62, -57.37] | 4.71 [4.54, 4.87] | False | False |
| ro-realskeleton-v1/all | 0 | presidio | -24.34 [-24.97, -23.76] | -2.50 [-2.83, -2.17] | True | True |
| ro-realskeleton-v1/all | 0 | shield | -32.83 [-33.34, -32.31] | -17.38 [-17.89, -16.86] | True | True |
| pl-realskeleton-v1/all | 0 | base | -8.28 [-8.91, -7.64] | 4.47 [3.95, 4.98] | False | False |
| pl-realskeleton-v1/all | 0 | res100-seed0 | -1.91 [-2.26, -1.55] | 2.55 [2.30, 2.81] | False | False |
| pl-realskeleton-v1/all | 0 | kp-280m | 5.64 [5.06, 6.19] | 8.96 [8.77, 9.17] | False | False |
| pl-realskeleton-v1/all | 0 | 560m-tab | -60.62 [-61.35, -59.90] | 12.45 [12.23, 12.69] | False | False |
| pl-realskeleton-v1/all | 0 | presidio | -17.05 [-17.51, -16.64] | -11.24 [-11.73, -10.71] | True | True |
| pl-realskeleton-v1/all | 0 | shield | -34.89 [-35.45, -34.35] | -16.78 [-17.53, -16.03] | True | True |
| gateway-ro/all | 0 | base | -13.72 [-15.28, -12.14] | 3.66 [3.15, 4.17] | False | False |
| gateway-ro/all | 0 | res100-seed0 | -18.38 [-20.03, -16.72] | 1.32 [0.97, 1.70] | False | False |
| gateway-ro/all | 0 | kp-280m | -18.44 [-20.60, -16.17] | -19.08 [-20.92, -17.27] | True | True |
| gateway-ro/all | 0 | 560m-tab | -45.96 [-47.98, -44.06] | 3.64 [3.15, 4.14] | False | False |
| gateway-ro/all | 0 | presidio | -46.21 [-47.75, -44.64] | -13.06 [-13.79, -12.36] | True | True |
| gateway-ro/all | 0 | shield | -30.65 [-32.64, -28.61] | -22.77 [-23.52, -22.03] | True | True |
| tab-echr-legal-en-v1/DIRECT | 1 | base | -64.77 [-68.90, -60.74] | 0.80 [0.57, 1.07] | False | False |
| tab-echr-legal-en-v1/DIRECT | 1 | res100-seed0 | -0.38 [-1.16, 0.00] | -0.04 [-0.14, 0.05] | False | False |
| tab-echr-legal-en-v1/DIRECT | 1 | kp-280m | -14.77 [-19.17, -10.34] | -1.47 [-1.77, -1.18] | True | True |
| tab-echr-legal-en-v1/DIRECT | 1 | 560m-tab | -31.44 [-36.54, -26.34] | 0.46 [0.32, 0.62] | False | True |
| tab-echr-legal-en-v1/DIRECT | 1 | presidio | -92.05 [-94.94, -89.22] | -1.40 [-1.67, -1.12] | True | True |
| tab-echr-legal-en-v1/DIRECT | 1 | shield | -92.05 [-95.02, -89.01] | -8.12 [-8.77, -7.51] | True | True |
| ro-realskeleton-v1/all | 1 | base | -13.32 [-14.08, -12.56] | 4.72 [4.39, 5.08] | False | False |
| ro-realskeleton-v1/all | 1 | res100-seed0 | -1.63 [-2.15, -1.14] | 3.15 [2.95, 3.36] | False | False |
| ro-realskeleton-v1/all | 1 | kp-280m | 6.56 [5.63, 7.45] | 4.36 [4.21, 4.50] | False | False |
| ro-realskeleton-v1/all | 1 | 560m-tab | -58.12 [-58.80, -57.43] | 8.07 [7.84, 8.32] | False | False |
| ro-realskeleton-v1/all | 1 | presidio | -24.46 [-25.12, -23.83] | 0.87 [0.62, 1.11] | False | False |
| ro-realskeleton-v1/all | 1 | shield | -32.95 [-33.52, -32.39] | -14.01 [-14.57, -13.41] | True | True |
| pl-realskeleton-v1/all | 1 | base | -3.82 [-4.50, -3.18] | 6.10 [5.39, 6.81] | False | False |
| pl-realskeleton-v1/all | 1 | res100-seed0 | 2.54 [2.07, 3.01] | 4.18 [3.82, 4.56] | False | False |
| pl-realskeleton-v1/all | 1 | kp-280m | 10.09 [9.56, 10.59] | 10.60 [10.26, 10.92] | False | False |
| pl-realskeleton-v1/all | 1 | 560m-tab | -56.17 [-56.79, -55.57] | 14.09 [13.66, 14.51] | False | False |
| pl-realskeleton-v1/all | 1 | presidio | -12.60 [-13.07, -12.16] | -9.60 [-10.00, -9.17] | True | True |
| pl-realskeleton-v1/all | 1 | shield | -30.44 [-30.95, -29.92] | -15.15 [-15.65, -14.63] | True | True |
| gateway-en/all | 1 | base | -6.10 [-7.34, -4.92] | 2.28 [1.98, 2.60] | False | False |
| gateway-en/all | 1 | res100-seed0 | -16.73 [-18.50, -14.99] | 1.66 [1.35, 1.97] | False | False |
| gateway-en/all | 1 | kp-280m | -23.52 [-25.18, -21.89] | -19.08 [-20.93, -17.26] | True | True |
| gateway-en/all | 1 | 560m-tab | -38.97 [-40.66, -37.26] | 2.17 [1.85, 2.50] | False | False |
| gateway-en/all | 1 | presidio | -40.83 [-42.09, -39.61] | -5.70 [-6.27, -5.10] | True | True |
| gateway-en/all | 1 | shield | -40.79 [-42.19, -39.36] | -4.64 [-5.37, -3.97] | True | True |
| tab-echr-legal-en-v1/DIRECT | 2 | base | -64.39 [-68.48, -60.23] | 0.91 [0.66, 1.21] | False | False |
| tab-echr-legal-en-v1/DIRECT | 2 | res100-seed0 | 0.00 [-1.12, 1.13] | 0.07 [-0.02, 0.16] | False | False |
| tab-echr-legal-en-v1/DIRECT | 2 | kp-280m | -14.39 [-18.63, -10.24] | -1.36 [-1.69, -1.05] | True | True |
| tab-echr-legal-en-v1/DIRECT | 2 | 560m-tab | -31.06 [-36.06, -26.15] | 0.57 [0.40, 0.76] | False | True |
| tab-echr-legal-en-v1/DIRECT | 2 | presidio | -91.67 [-94.62, -88.68] | -1.29 [-1.58, -0.98] | True | True |
| tab-echr-legal-en-v1/DIRECT | 2 | shield | -91.67 [-94.68, -88.55] | -8.02 [-8.64, -7.40] | True | True |
| ro-realskeleton-v1/all | 2 | base | -11.65 [-12.39, -10.88] | 7.10 [6.68, 7.54] | False | False |
| ro-realskeleton-v1/all | 2 | res100-seed0 | 0.04 [-0.56, 0.64] | 5.52 [5.29, 5.76] | False | False |
| ro-realskeleton-v1/all | 2 | kp-280m | 8.22 [7.45, 8.96] | 6.73 [6.54, 6.93] | False | False |
| ro-realskeleton-v1/all | 2 | 560m-tab | -56.45 [-57.04, -55.84] | 10.45 [10.15, 10.78] | False | False |
| ro-realskeleton-v1/all | 2 | presidio | -22.80 [-23.41, -22.21] | 3.25 [3.00, 3.48] | False | False |
| ro-realskeleton-v1/all | 2 | shield | -31.28 [-31.93, -30.65] | -11.64 [-12.26, -10.94] | True | True |
| pl-realskeleton-v1/all | 2 | base | -5.21 [-5.88, -4.58] | 5.98 [5.44, 6.52] | False | False |
| pl-realskeleton-v1/all | 2 | res100-seed0 | 1.16 [0.61, 1.72] | 4.07 [3.81, 4.32] | False | False |
| pl-realskeleton-v1/all | 2 | kp-280m | 8.71 [8.06, 9.26] | 10.48 [10.28, 10.67] | False | False |
| pl-realskeleton-v1/all | 2 | 560m-tab | -57.55 [-58.18, -56.94] | 13.97 [13.70, 14.25] | False | False |
| pl-realskeleton-v1/all | 2 | presidio | -13.99 [-14.58, -13.43] | -9.72 [-10.14, -9.28] | True | True |
| pl-realskeleton-v1/all | 2 | shield | -31.83 [-32.42, -31.23] | -15.26 [-15.91, -14.62] | True | True |
| gateway-de/all | 2 | base | -6.75 [-8.33, -5.24] | 0.30 [0.17, 0.43] | False | True |
| gateway-de/all | 2 | res100-seed0 | -14.23 [-16.18, -12.25] | -1.47 [-1.65, -1.28] | True | True |
| gateway-de/all | 2 | kp-280m | -19.40 [-21.36, -17.43] | -18.83 [-20.68, -16.99] | True | True |
| gateway-de/all | 2 | 560m-tab | -42.72 [-44.63, -40.83] | 0.88 [0.67, 1.11] | False | False |
| gateway-de/all | 2 | presidio | -38.70 [-40.20, -37.23] | -27.61 [-28.70, -26.55] | True | True |
| gateway-de/all | 2 | shield | -30.18 [-32.30, -28.06] | -23.50 [-24.49, -22.46] | True | True |

## Frozen strict diagnostic

The same three training seeds are also reported under the merged frozen strict rule in
[the decoding results](gateway-decoding-results.md). DEV selection was infeasible; this remains
a dev-rejected diagnostic, with separate leaderboard rows and no test-based rule selection.
Seed 2 uses SHA-verified replay of the default receipts; the original decoded seeds 0 and 1 are preserved.
