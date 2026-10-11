# ro-realskeleton-v2: independent round-2 report

Status: **dev**. External panel incomplete; no promotion.

[Frozen protocol](round2-protocol.md) · [Reproduction and spend ledger summary](round2-runbook.md).

Source: klusai/klusai-datasets commit `79c7a91c47be20c8d214b05b09c2850fe8049037`, CC-BY-4.0.
Frozen reserved sample: 300 documents, 75/type, seed 7712; population 1,500.
One generation seed/language; one sampling seed; no repeated inference seeds.
CIs: 2,000 stratified document bootstrap draws, seed 7701; proportions use Wilson 95%.

## Required external panel

Mistral upstream shared-pool HTTP 429s exhausted six attempts on RO batch 2.
Same-model provider fallback was enabled. No model substitution. Stage B did not run.
Valid A documents: mistralai/mistral-large-2512: 5/300, google/gemini-2.5-flash: 5/300, qwen/qwen3-235b-a22b-2507: 5/300.
Partial statistics below describe only the returned cases, not the full config.

| External statistic | n | Estimate [95% CI] |
|---|---:|---|
| Alpha: panel | 5 | 0.8298 [0.8298, 0.8298] |
| Alpha: mistralai/mistral-large-2512 | 5 | 1.0000 [1.0000, 1.0000] |
| Alpha: google/gemini-2.5-flash | 5 | 0.8719 [0.8719, 0.8719] |
| Alpha: qwen/qwen3-235b-a22b-2507 | 5 | 0.7475 [0.7475, 0.7475] |
| mistralai/mistral-large-2512: fluency | 5 | 5.0000 [5.0000, 5.0000] |
| mistralai/mistral-large-2512: naturalness | 5 | 5.0000 [5.0000, 5.0000] |
| google/gemini-2.5-flash: fluency | 5 | 5.0000 [5.0000, 5.0000] |
| google/gemini-2.5-flash: naturalness | 5 | 5.0000 [5.0000, 5.0000] |
| qwen/qwen3-235b-a22b-2507: fluency | 5 | 5.0000 [5.0000, 5.0000] |
| qwen/qwen3-235b-a22b-2507: naturalness | 5 | 5.0000 [5.0000, 5.0000] |
| Majority artifacts | 5 | 0/5; [2.7755575615628914e-17, 0.43448146575265334] |

Gate diagnostics (partial-case passes do not override failed completeness): sample=pass, complete=fail/unverified, agreement=fail/unverified, ratings=pass, artifacts=pass, decode=pass, gold_errors=fail/unverified.

| Document type | Complete external n / 75 |
|---|---:|
| contract | 0 |
| clinical | 0 |
| admin | 5 |
| declaration | 0 |

## Supplemental blind Codex review

The author self-review was not read and does not count. Codex annotations/ratings were
frozen before gold comparison or reading external judgments. Review used raw prose
variants plus all 600 document slot rows, with code transcribing selected spans.
This is one shared session with template-assisted transcription, not isolated per-document judgments.

| Type | n | Codex–gold alpha [95% CI] | Fluency median [95% CI] | Naturalness median [95% CI] | Artifact docs [Wilson CI] |
|---|---:|---|---|---|---|
| overall | 300 | 0.9117 [0.9117, 0.9117] | 5.0000 [5.0000, 5.0000] | 5.0000 [5.0000, 5.0000] | 75/300 [0.2043699748164734, 0.3019514854180529] |
| contract | 75 | 1.0000 [1.0000, 1.0000] | 5.0000 [5.0000, 5.0000] | 5.0000 [5.0000, 5.0000] | 0/75 [0.0, 0.04872365402770864] |
| clinical | 75 | 0.6593 [0.6593, 0.6593] | 5.0000 [4.0000, 5.0000] | 4.0000 [4.0000, 4.0000] | 75/75 [0.9512763459722913, 1.0] |
| admin | 75 | 1.0000 [1.0000, 1.0000] | 5.0000 [5.0000, 5.0000] | 5.0000 [5.0000, 5.0000] | 0/75 [0.0, 0.04872365402770864] |
| declaration | 75 | 1.0000 [1.0000, 1.0000] | 5.0000 [5.0000, 5.0000] | 5.0000 [5.0000, 5.0000] | 0/75 [0.0, 0.04872365402770864] |

Codex flags clinical under-specification: assessments refer to monitoring or improvement
without individual measurements/treatment details. Contracts form coherent short agreements.
Codex differs from gold on 75 clinical documents: named medical centers
as FACILITY rather than ORG_PARTY, and doctors as PROVIDER rather than PERSON; RO also
differs on facility boundaries. These are single-judge hypotheses, not majority-approved repairs.
No gold overlay was applied and no model score was copied onto changed gold.

## Harness identifier audit

Across all 1,500 documents: 1130/1130 unique document/ID subjects
pass checksum, known DOB/sex and raw-ID NATIONAL_ID coverage; Wilson CI [0.996612010237734, 1.0].
Explicit clinical DOB: 371 subjects; sex: 371 subjects.
Consistent DOB: 371; sex: 371; respective Wilson CIs [0.9897518183454066, 1.0] and [0.9897518183454066, 1.0].
No independent stated sex outside clinical rows or birth-county field was assumed.

## Limits and disposition

Keep dev: missing external judgments and missing three-family adjudication prevent validation.
No human/native-speaker review, legal/clinical certification, registry/address/bank lookup,
real-record representativeness, unseen-template generalization or model-performance win verified.
The holdout separates documents, not authored templates. CIs condition on this family and judges;
degenerate alpha/median CIs reflect identical within-type span counts and repeated ratings,
not certainty about population quality. No independent per-document model contexts were used for Codex.
Agreement is not accuracy, human IAA, privacy certification or proof against linkability.
No v1–v2 improvement claim: independent CI-disjoint held-out delta was not established.
