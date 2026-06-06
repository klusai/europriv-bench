# detection≠re-id dissociation — `se-realskeleton-v1` (RES-80, personnummer)

A decode-bearing identifier + language extending the headline beyond RO/PL/IT. A missed personnummer discloses **SEX + DATE_OF_BIRTH (birth month + day)**. Difference-of-proportions: **gap = leak_rate(typed-detector) − leak_rate(protector=kp-deid)**, Newcombe (1998) hybrid-score CI; the dissociation **holds** iff a typed-detector's gap CI **excludes 0** (`low > 0`). Per-distinct-subject `(doc, country=SE, value)` dedup (KLU-49); the discharge note repeats the patient id → one subject. A **null is still a finding**.

**Dissociation holds on SE: YES.**

Protector (kp-deid) leak-rate 0.0000 over 232 distinct personnummer subjects (n=300 docs; pre-registered ≥300); 95% Wilson upper bound **0.0163** (target ≤ 0.02). kp-deid is RO-trained and has never seen sv — this is a **zero-shot** transfer result.

| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |
|---|---:|---:|---:|:--:|:--:|
| gliner | 1.0000 (232/232) | 0.0000 (0/232) | +1.0000 | [+0.9770, +1.0000] | YES |
| gliner2 | 0.4871 (113/232) | 0.0000 (0/232) | +0.4871 | [+0.4214, +0.5511] | YES |
| privacy-filter | 0.0000 (0/232) | 0.0000 (0/232) | +0.0000 | [-0.0163, +0.0163] | no |
| tabularisai | 0.3190 (74/232) | 0.0000 (0/232) | +0.3190 | [+0.2601, +0.3815] | YES |
