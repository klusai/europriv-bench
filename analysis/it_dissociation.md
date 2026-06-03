# detection≠re-id dissociation — `it-realskeleton-v1` (KLU-105, codice fiscale)

The THIRD decode-bearing identifier + language (after RO/CNP and PL/PESEL). A missed codice fiscale discloses **DATE_OF_BIRTH + SEX + PLACE_OF_BIRTH** (Belfiore comune/country, omocodia reversed) — the richest of the three. Difference-of-proportions: **gap = leak_rate(typed-detector) − leak_rate(protector=kp-deid)**, Newcombe (1998) hybrid-score CI; the dissociation **holds** iff a typed-detector's gap CI **excludes 0** (`low > 0`). Per-distinct-subject `(doc, country=IT, value)` dedup (KLU-49); the discharge letter repeats the patient CF → one subject.

**Dissociation holds on IT: YES.**

Protector (kp-deid) leak-rate 0.0000 over 224 distinct codice-fiscale subjects (n=300 docs; pre-registered ≥300); 95% Wilson upper bound **0.0169** (pre-registered target ≤ 0.02). Place-of-birth is counted in the disclosed quasi-identifiers (3 QIs per leaked CF: DOB + SEX + PLACE_OF_BIRTH).

| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |
|---|---:|---:|---:|:--:|:--:|
| gliner | 0.3973 (89/224) | 0.0000 (0/224) | +0.3973 | [+0.3332, +0.4626] | YES |
| gliner2 | 0.3527 (79/224) | 0.0000 (0/224) | +0.3527 | [+0.2907, +0.4173] | YES |
| openmed | 0.3795 (85/224) | 0.0000 (0/224) | +0.3795 | [+0.3162, +0.4445] | YES |
| presidio | 0.9643 (216/224) | 0.0000 (0/224) | +0.9643 | [+0.9271, +0.9818] | YES |
| privacy-filter | 0.0045 (1/224) | 0.0000 (0/224) | +0.0045 | [-0.0128, +0.0248] | no |
| spacy | 0.3929 (88/224) | 0.0000 (0/224) | +0.3929 | [+0.3290, +0.4581] | YES |
| tabularisai | 0.3214 (72/224) | 0.0000 (0/224) | +0.3214 | [+0.2613, +0.3852] | YES |
