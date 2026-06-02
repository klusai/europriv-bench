# McNemar significance — per-subject CNP detection (`ro-realskeleton-v1`)

Item-paired McNemar on **per-subject CNP detection** (was each distinct gold CNP subject `(doc, country, normalized value)` redacted or leaked) — the same per-subject unit as the re-identification leak-rate. Exact two-sided binomial p-value on the discordant pairs (valid for small discordant counts). Source dump: `analysis/predictions_ro_realskeleton.json` (timestamp 2026-06-02T10:38:13.997432+00:00).

Discordant counts: **b** = kp-deid protects / other leaks; **c** = other protects / kp-deid leaks.

| Contrast | Model A (kp-deid) vs B | shared CNP subjects | A leaked | B leaked | b | c | McNemar p (exact) | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---|
| f1_leader_max_leak | kp-model vs gliner | 1123 | 0 | 339 | 339 | 0 | 1.79e-102 | **significant** |
| next_best_protector | kp-model vs presidio | 1123 | 0 | 0 | 0 | 0 | 1 | not significant |
| next_leaking_protector | kp-model vs privacy-filter | 1123 | 0 | 16 | 16 | 0 | 3.05e-05 | **significant** |

## Verdicts

- **kp-deid vs gliner** (f1_leader_max_leak): SIGNIFICANT (p=1.79e-102 < 0.05): kp-model protects per-subject CNPs that gliner leaks far more often than the reverse (b=339, c=0). The dissociation is real.
- **kp-deid vs presidio** (next_best_protector): NOT significant (p=1 >= 0.05): no detectable difference in per-subject CNP protection between kp-model and presidio (b=0, c=0).
- **kp-deid vs privacy-filter** (next_leaking_protector): SIGNIFICANT (p=3.05e-05 < 0.05): kp-model protects per-subject CNPs that privacy-filter leaks far more often than the reverse (b=16, c=0). The dissociation is real.

Figure: `pareto_dissociation_ro_realskeleton.svg` (+ `.png`). Regenerate with `analysis/pareto_dissociation.py`.
