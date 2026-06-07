# detection≠re-id dissociation — `ee-realskeleton-v1` (RES-84, isikukood)

A decode-bearing identifier + language extending the headline beyond RO/PL/IT/SE/CZ/DK/FI. A missed isikukood discloses **SEX + DATE_OF_BIRTH (full date; century from the 1st digit)**. Difference-of-proportions: **gap = leak_rate(typed-detector) − leak_rate(protector=kp-deid)**, Newcombe (1998) hybrid-score CI; the dissociation **holds** iff a typed-detector's gap CI **excludes 0** (`low > 0`). Per-distinct-subject `(doc, country=EE, value)` dedup (KLU-49); the discharge note repeats the patient id → one subject. A **null is still a finding**.

**Dissociation holds on EE: YES.**

Protector (kp-deid) leak-rate 0.0000 over 229 distinct isikukood subjects (n=300 docs; pre-registered ≥300); 95% Wilson upper bound **0.0165** (target ≤ 0.02). kp-deid is RO-trained and has never seen et — this is a **zero-shot** transfer result.

| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |
|---|---:|---:|---:|:--:|:--:|
| gliner | 0.7817 (179/229) | 0.0000 (0/229) | +0.7817 | [+0.7214, +0.8303] | YES |
| gliner2 | 0.3581 (82/229) | 0.0000 (0/229) | +0.3581 | [+0.2965, +0.4220] | YES |
| openmed | 0.2183 (50/229) | 0.0000 (0/229) | +0.2183 | [+0.1670, +0.2763] | YES |
| presidio | 0.0000 (0/229) | 0.0000 (0/229) | +0.0000 | [-0.0165, +0.0165] | no |
| privacy-filter | 0.0524 (12/229) | 0.0000 (0/229) | +0.0524 | [+0.0248, +0.0893] | YES |
| spacy | 0.7642 (175/229) | 0.0000 (0/229) | +0.7642 | [+0.7029, +0.8145] | YES |
| tabularisai | 0.3057 (70/229) | 0.0000 (0/229) | +0.3057 | [+0.2472, +0.3681] | YES |
