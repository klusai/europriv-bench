# detection≠re-id dissociation — `lt-realskeleton-v1` (RES-84, asmens kodas)

A decode-bearing identifier + language extending the headline beyond RO/PL/IT/SE/CZ/DK/FI. A missed asmens kodas discloses **SEX + DATE_OF_BIRTH (full date; century from the 1st digit)**. Difference-of-proportions: **gap = leak_rate(typed-detector) − leak_rate(protector=kp-deid)**, Newcombe (1998) hybrid-score CI; the dissociation **holds** iff a typed-detector's gap CI **excludes 0** (`low > 0`). Per-distinct-subject `(doc, country=LT, value)` dedup (KLU-49); the discharge note repeats the patient id → one subject. A **null is still a finding**.

**Dissociation holds on LT: YES.**

Protector (kp-deid) leak-rate 0.0000 over 227 distinct asmens kodas subjects (n=300 docs; pre-registered ≥300); 95% Wilson upper bound **0.0166** (target ≤ 0.02). kp-deid is RO-trained and has never seen lt — this is a **zero-shot** transfer result.

| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |
|---|---:|---:|---:|:--:|:--:|
| gliner | 0.9736 (221/227) | 0.0000 (0/227) | +0.9736 | [+0.9392, +0.9878] | YES |
| gliner2 | 0.0617 (14/227) | 0.0000 (0/227) | +0.0617 | [+0.0320, +0.1008] | YES |
| presidio | 0.0000 (0/227) | 0.0000 (0/227) | +0.0000 | [-0.0166, +0.0166] | no |
| spacy | 0.6784 (154/227) | 0.0000 (0/227) | +0.6784 | [+0.6130, +0.7358] | YES |
