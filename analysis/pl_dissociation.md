# detection≠re-id dissociation — `pl-realskeleton-v1` (RES-87, PESEL)

A decode-bearing identifier + language extending the headline beyond RO. A missed PESEL discloses **SEX + DATE_OF_BIRTH (full date; century encoded in the month field)**. Difference-of-proportions: **gap = leak_rate(typed-detector) − leak_rate(protector=kp-deid)**, Newcombe (1998) hybrid-score CI; the dissociation **holds** iff a typed-detector's gap CI **excludes 0** (`low > 0`). Per-distinct-subject `(doc, country=PL, value)` dedup (KLU-49); the discharge note repeats the patient id → one subject. A **null is still a finding**.

**Dissociation holds on PL: YES.**

Protector (kp-deid) leak-rate 0.0000 over 1096 distinct PESEL subjects (n=1500 docs; pre-registered ≥300); 95% Wilson upper bound **0.0035** (target ≤ 0.02). kp-deid is RO-trained and has never seen pl — this is a **zero-shot** transfer result.

| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |
|---|---:|---:|---:|:--:|:--:|
| gliner | 0.5785 (634/1096) | 0.0000 (0/1096) | +0.5785 | [+0.5488, +0.6074] | YES |
| gliner2 | 0.3376 (370/1096) | 0.0000 (0/1096) | +0.3376 | [+0.3100, +0.3661] | YES |
| openmed | 0.0374 (41/1096) | 0.0000 (0/1096) | +0.0374 | [+0.0271, +0.0504] | YES |
| presidio | 0.0000 (0/1096) | 0.0000 (0/1096) | +0.0000 | [-0.0035, +0.0035] | no |
| privacy-filter | 0.0009 (1/1096) | 0.0000 (0/1096) | +0.0009 | [-0.0027, +0.0052] | no |
| spacy | 0.4471 (490/1096) | 0.0000 (0/1096) | +0.4471 | [+0.4177, +0.4766] | YES |
| tabularisai | 0.3066 (336/1096) | 0.0000 (0/1096) | +0.3066 | [+0.2798, +0.3345] | YES |
