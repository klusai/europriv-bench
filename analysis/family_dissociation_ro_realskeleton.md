# Per-family detection≠re-id dissociation — `ro-realskeleton-v1` (KLU-101)

Difference-of-proportions per family: **gap = leak_rate(typed-detector) − leak_rate(protector=kp-deid)**, with a Newcombe (1998) hybrid-score CI on the difference. The dissociation **holds** for a family iff a typed-detector's gap CI **excludes 0** (`low > 0`). Per-distinct-subject `(doc, country, value)` dedup (KLU-49).

**Dissociation holds across BOTH families: YES.**

## Family A — official correspondence (clinical / legal / administrative)  (n=250 docs)

Protector (kp-deid) leak-rate 0.0000 over 190 distinct CNP subjects; 95% Wilson upper bound **0.0198** (pre-registered target ≤ 0.02). Dissociation holds in this family: **YES**.

| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |
|---|---:|---:|---:|:--:|:--:|
| gliner | 0.2789 (53/190) | 0.0000 (0/190) | +0.2789 | [+0.2168, +0.3466] | YES |
| gliner2 | 0.2842 (54/190) | 0.0000 (0/190) | +0.2842 | [+0.2216, +0.3521] | YES |
| openmed | 0.2526 (48/190) | 0.0000 (0/190) | +0.2526 | [+0.1928, +0.3189] | YES |
| presidio | 0.0000 (0/190) | 0.0000 (0/190) | +0.0000 | [-0.0198, +0.0198] | no |
| privacy-filter | 0.0053 (1/190) | 0.0000 (0/190) | +0.0053 | [-0.0150, +0.0292] | no |
| spacy | 0.9211 (175/190) | 0.0000 (0/190) | +0.9211 | [+0.8699, +0.9516] | YES |
| tabularisai | 0.3684 (70/190) | 0.0000 (0/190) | +0.3684 | [+0.3001, +0.4390] | YES |

## Family B — academic registry (higher-education student records)  (n=250 docs)

Protector (kp-deid) leak-rate 0.0000 over 250 distinct CNP subjects; 95% Wilson upper bound **0.0151** (pre-registered target ≤ 0.02). Dissociation holds in this family: **YES**.

| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |
|---|---:|---:|---:|:--:|:--:|
| gliner | 1.0000 (250/250) | 0.0000 (0/250) | +1.0000 | [+0.9786, +1.0000] | YES |
| gliner2 | 0.9000 (225/250) | 0.0000 (0/250) | +0.9000 | [+0.8540, +0.9313] | YES |
| openmed | 0.6680 (167/250) | 0.0000 (0/250) | +0.6680 | [+0.6056, +0.7234] | YES |
| presidio | 0.9000 (225/250) | 0.0000 (0/250) | +0.9000 | [+0.8540, +0.9313] | YES |
| privacy-filter | 0.9840 (246/250) | 0.0000 (0/250) | +0.9840 | [+0.9553, +0.9938] | YES |
| spacy | 0.8920 (223/250) | 0.0000 (0/250) | +0.8920 | [+0.8449, +0.9247] | YES |
| tabularisai | 0.0120 (3/250) | 0.0000 (0/250) | +0.0120 | [-0.0051, +0.0347] | no |
