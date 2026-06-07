# detection≠re-id dissociation — `dk-realskeleton-v1` (RES-83, CPR-nummer)

A decode-bearing identifier + language extending the headline beyond RO/PL/IT/SE/CZ. A missed CPR-nummer discloses **SEX + DATE_OF_BIRTH (full date; century from the 7th-digit/YY table)**. Difference-of-proportions: **gap = leak_rate(typed-detector) − leak_rate(protector=kp-deid)**, Newcombe (1998) hybrid-score CI; the dissociation **holds** iff a typed-detector's gap CI **excludes 0** (`low > 0`). Per-distinct-subject `(doc, country=DK, value)` dedup (KLU-49); the discharge note repeats the patient id → one subject. A **null is still a finding**.

**Dissociation holds on DK: YES.**

Protector (kp-deid) leak-rate 0.0000 over 226 distinct CPR-nummer subjects (n=300 docs; pre-registered ≥300); 95% Wilson upper bound **0.0167** (target ≤ 0.02). kp-deid is RO-trained and has never seen da — this is a **zero-shot** transfer result.

| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |
|---|---:|---:|---:|:--:|:--:|
| gliner | 0.8540 (193/226) | 0.0000 (0/226) | +0.8540 | [+0.7994, +0.8941] | YES |
| gliner2 | 0.8319 (188/226) | 0.0000 (0/226) | +0.8319 | [+0.7751, +0.8750] | YES |
| openmed | 0.3053 (69/226) | 0.0000 (0/226) | +0.3053 | [+0.2465, +0.3682] | YES |
| presidio | 0.0000 (0/226) | 0.0000 (0/226) | +0.0000 | [-0.0167, +0.0167] | no |
| privacy-filter | 0.0442 (10/226) | 0.0000 (0/226) | +0.0442 | [+0.0182, +0.0795] | YES |
| spacy | 0.3628 (82/226) | 0.0000 (0/226) | +0.3628 | [+0.3006, +0.4273] | YES |
| tabularisai | 0.3496 (79/226) | 0.0000 (0/226) | +0.3496 | [+0.2881, +0.4138] | YES |
