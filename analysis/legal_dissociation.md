# detection≠re-id dissociation — `legal-realskeleton-v1` (KLU-111, legal domain)

The program's first **legal-domain** real-skeleton track — EUR-Lex-style instrument / ECHR-style judgment / GDPR Art.15 DSAR response (STRUCTURE ONLY, no source text redistributed). A missed CNP discloses **DATE_OF_BIRTH + SEX + COUNTY**. Difference-of-proportions: **gap = leak_rate(typed-detector) − leak_rate(protector=kp-deid)**, Newcombe (1998) hybrid-score CI; the dissociation **holds** iff a typed-detector's gap CI **excludes 0** (`low > 0`). Per-distinct-subject `(doc, country=RO, value)` dedup (KLU-49); the DSAR response repeats the applicant CNP → one subject.

**Dissociation holds in the legal domain: YES.**

Protector (kp-deid) leak-rate 0.0407 over 1500 distinct CNP subjects (n=1500 docs; pre-registered ≥1500); 95% Wilson upper bound **0.0519**. A leaked CNP discloses 3 quasi-identifiers (DATE_OF_BIRTH + SEX + COUNTY).

| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |
|---|---:|---:|---:|:--:|:--:|
| gliner | 0.7173 (1076/1500) | 0.0407 (61/1500) | +0.6767 | [+0.6508, +0.7006] | YES |
| gliner2 | 0.6540 (981/1500) | 0.0407 (61/1500) | +0.6133 | [+0.5864, +0.6386] | YES |
| openmed | 0.8387 (1258/1500) | 0.0407 (61/1500) | +0.7980 | [+0.7755, +0.8178] | YES |
| presidio | 0.6647 (997/1500) | 0.0407 (61/1500) | +0.6240 | [+0.5972, +0.6491] | YES |
| privacy-filter | 0.9667 (1450/1500) | 0.0407 (61/1500) | +0.9260 | [+0.9107, +0.9379] | YES |
| spacy | 0.6600 (990/1500) | 0.0407 (61/1500) | +0.6193 | [+0.5925, +0.6445] | YES |
| tabularisai | 0.2727 (409/1500) | 0.0407 (61/1500) | +0.2320 | [+0.2074, +0.2567] | YES |
