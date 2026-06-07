# detection≠re-id dissociation — `fi-realskeleton-v1` (RES-83, henkilötunnus)

A decode-bearing identifier + language extending the headline beyond RO/PL/IT/SE/CZ. A missed henkilötunnus discloses **SEX + DATE_OF_BIRTH (full date; century from the marker)**. Difference-of-proportions: **gap = leak_rate(typed-detector) − leak_rate(protector=kp-deid)**, Newcombe (1998) hybrid-score CI; the dissociation **holds** iff a typed-detector's gap CI **excludes 0** (`low > 0`). Per-distinct-subject `(doc, country=FI, value)` dedup (KLU-49); the discharge note repeats the patient id → one subject. A **null is still a finding**.

**Dissociation holds on FI: YES.**

Protector (kp-deid) leak-rate 0.0000 over 228 distinct henkilötunnus subjects (n=300 docs; pre-registered ≥300); 95% Wilson upper bound **0.0166** (target ≤ 0.02). kp-deid is RO-trained and has never seen fi — this is a **zero-shot** transfer result.

| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |
|---|---:|---:|---:|:--:|:--:|
| gliner | 0.8772 (200/228) | 0.0000 (0/228) | +0.8772 | [+0.8255, +0.9137] | YES |
| gliner2 | 0.4035 (92/228) | 0.0000 (0/228) | +0.4035 | [+0.3397, +0.4683] | YES |
| presidio | 0.1754 (40/228) | 0.0000 (0/228) | +0.1754 | [+0.1285, +0.2301] | YES |
| spacy | 0.6096 (139/228) | 0.0000 (0/228) | +0.6096 | [+0.5429, +0.6707] | YES |
| tabularisai | 0.3026 (69/228) | 0.0000 (0/228) | +0.3026 | [+0.2443, +0.3651] | YES |
