# detection≠re-id dissociation — `si-realskeleton-v1` (RES-85, EMŠO)

A decode-bearing identifier + language extending the headline beyond RO/PL/IT/SE/CZ/DK/FI/EE/LT. A missed EMŠO discloses **SEX + DATE_OF_BIRTH + REGION_OF_BIRTH (full date; ex-YU century convention)**. Difference-of-proportions: **gap = leak_rate(typed-detector) − leak_rate(protector=kp-deid)**, Newcombe (1998) hybrid-score CI; the dissociation **holds** iff a typed-detector's gap CI **excludes 0** (`low > 0`). Per-distinct-subject `(doc, country=SI, value)` dedup (KLU-49); the discharge note repeats the patient id → one subject. A **null is still a finding**.

**Dissociation holds on SI: YES.**

Protector (kp-deid) leak-rate 0.0000 over 220 distinct EMŠO subjects (n=300 docs; pre-registered ≥300); 95% Wilson upper bound **0.0172** (target ≤ 0.02). kp-deid is RO-trained and has never seen sl — this is a **zero-shot** transfer result.

| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |
|---|---:|---:|---:|:--:|:--:|
| gliner | 0.3636 (80/220) | 0.0000 (0/220) | +0.3636 | [+0.3005, +0.4290] | YES |
| gliner2 | 0.2591 (57/220) | 0.0000 (0/220) | +0.2591 | [+0.2030, +0.3208] | YES |
| presidio | 0.0000 (0/220) | 0.0000 (0/220) | +0.0000 | [-0.0172, +0.0172] | no |
| spacy | 0.7909 (174/220) | 0.0000 (0/220) | +0.7909 | [+0.7299, +0.8394] | YES |
