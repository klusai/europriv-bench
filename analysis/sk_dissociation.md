# detection≠re-id dissociation — `sk-realskeleton-v1` (RES-85, rodné číslo)

A decode-bearing identifier + language extending the headline beyond RO/PL/IT/SE/CZ/DK/FI/EE/LT. A missed rodné číslo discloses **SEX + DATE_OF_BIRTH (full date, modern 10-digit form; same algorithm as CZ)**. Difference-of-proportions: **gap = leak_rate(typed-detector) − leak_rate(protector=kp-deid)**, Newcombe (1998) hybrid-score CI; the dissociation **holds** iff a typed-detector's gap CI **excludes 0** (`low > 0`). Per-distinct-subject `(doc, country=SK, value)` dedup (KLU-49); the discharge note repeats the patient id → one subject. A **null is still a finding**.

**Dissociation holds on SK: YES.**

Protector (kp-deid) leak-rate 0.0000 over 236 distinct rodné číslo subjects (n=300 docs; pre-registered ≥300); 95% Wilson upper bound **0.0160** (target ≤ 0.02). kp-deid is RO-trained and has never seen sk — this is a **zero-shot** transfer result.

| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |
|---|---:|---:|---:|:--:|:--:|
| gliner | 0.9958 (235/236) | 0.0000 (0/236) | +0.9958 | [+0.9706, +0.9993] | YES |
| gliner2 | 0.3814 (90/236) | 0.0000 (0/236) | +0.3814 | [+0.3196, +0.4448] | YES |
| presidio | 0.0000 (0/236) | 0.0000 (0/236) | +0.0000 | [-0.0160, +0.0160] | no |
| spacy | 0.3390 (80/236) | 0.0000 (0/236) | +0.3390 | [+0.2794, +0.4015] | YES |
