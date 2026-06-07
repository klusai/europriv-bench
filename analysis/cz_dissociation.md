# detection≠re-id dissociation — `cz-realskeleton-v1` (RES-80, rodné číslo)

A decode-bearing identifier + language extending the headline beyond RO/PL/IT. A missed rodné číslo discloses **SEX + DATE_OF_BIRTH (full date, modern 10-digit form)**. Difference-of-proportions: **gap = leak_rate(typed-detector) − leak_rate(protector=kp-deid)**, Newcombe (1998) hybrid-score CI; the dissociation **holds** iff a typed-detector's gap CI **excludes 0** (`low > 0`). Per-distinct-subject `(doc, country=CZ, value)` dedup (KLU-49); the discharge note repeats the patient id → one subject. A **null is still a finding**.

**Dissociation holds on CZ: YES.**

Protector (kp-deid) leak-rate 0.0000 over 221 distinct rodné číslo subjects (n=300 docs; pre-registered ≥300); 95% Wilson upper bound **0.0171** (target ≤ 0.02). kp-deid is RO-trained and has never seen cs — this is a **zero-shot** transfer result.

| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |
|---|---:|---:|---:|:--:|:--:|
| gliner | 0.6742 (149/221) | 0.0000 (0/221) | +0.6742 | [+0.6077, +0.7326] | YES |
| gliner2 | 0.4661 (103/221) | 0.0000 (0/221) | +0.4661 | [+0.3992, +0.5319] | YES |
| openmed | 0.6833 (151/221) | 0.0000 (0/221) | +0.6833 | [+0.6170, +0.7410] | YES |
| presidio | 0.0000 (0/221) | 0.0000 (0/221) | +0.0000 | [-0.0171, +0.0171] | no |
| privacy-filter | 0.0136 (3/221) | 0.0000 (0/221) | +0.0136 | [-0.0057, +0.0391] | no |
| spacy | 0.4480 (99/221) | 0.0000 (0/221) | +0.4480 | [+0.3816, +0.5139] | YES |
| tabularisai | 0.3529 (78/221) | 0.0000 (0/221) | +0.3529 | [+0.2906, +0.4180] | YES |
