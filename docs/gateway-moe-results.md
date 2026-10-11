# Gateway-trained MoE: default operating point

Contract v3: **loss**. Contract v2: **loss**.

Training seeds: [0]; seed count 1. CPU fp32, saved 512-token window, no threshold tuning.
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

RO/PL legacy zero floors: PASS. All legacy metrics and their Wilson/bootstrap intervals remain in the aggregate artifact.
Worst gateway language by all-identifier leakage: {'0': 'gateway-ro'}.

Gateway synthetic test stays dev; its overlapping/token-colliding annotations do not support legacy F1/
leakage, so those metrics are unavailable. OpenPII retains validation split. Italian/legal real-skeleton
are unavailable at the frozen source revision. No gold is dropped or relabelled to manufacture scores.

Comparators retain original runtime, truncation and operators. RES-100 seed0 uses its raw default
predictions before calibration. The TAB comparator is res104-tab-seed0, not 560m-legal.
Base/RES-100 use 256-token windows; candidate uses its saved default of 512. Shield is distinct from Presidio.

No overall win is established. Unverified: three independent seeds; native review and source/subject/scenario-family/translation disjointness; reviewed held-out challenge; service deployment equivalence and CPU load/SLO; semantic utility; empirical attacker re-identification.

## Paired anchor and worst-language comparisons

All deltas below are candidate minus comparator in percentage points (95% cluster bootstrap).
TAB uses its separately registered DIRECT endpoint; other rows use all identifier subjects.
The worst gateway language is descriptive, not a selected replacement for the eight-language matrix.
Numerical pass counts are not contract wins; the seed/review/disjointness requirements remain.

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
