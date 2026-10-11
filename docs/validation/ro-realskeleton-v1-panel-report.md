# ro-realskeleton-v1: autonomous LLM-panel audit

**Outcome: NOT VALIDATED; config_status=dev.**
This is an autonomous LLM-panel audit, never native-speaker review or human validation.

Protocol: [pre-registration](panel-protocol.md), committed before paid inference.
Source: `klusai/europriv-bench`, revision `58faa4fa572cd8064818a6e1f8ca6e361b959c00`, test split, CC-BY-4.0.
Protocol SHA256: `c1dcb67199e23e1ff6606996987a80f0ba9967b61682ec6855383c8f2080127c`.
Sample manifest SHA256: `e6a0dfef75734aced33b151d7cc61a0581f2b8c5ede99c4624326edd810374a4`.
Population n=1500; sampled n=300; complete three-judge n=0.
Sampling seed=77; seed count=1. Bootstrap seed=7701, 2,000 stratified document resamples when defined.

| Stratum | Population | Sample |
|---|---:|---:|
| admin | 377 | 75 |
| clinical | 397 | 75 |
| contract | 339 | 75 |
| declaration | 387 | 75 |

| Judge / comparison | Valid n | Exact-span alpha [95% CI] | Fluency median [95% CI] | Naturalness median [95% CI] |
|---|---:|---|---|---|
| mistralai/mistral-large-2512 vs gold | 0 | unavailable | unavailable | unavailable |
| google/gemini-2.5-flash vs gold | 0 | unavailable | unavailable | unavailable |
| qwen/qwen3-235b-a22b-2507 vs gold | 0 | unavailable | unavailable | unavailable |
| Panel vs panel | 0 | unavailable | — | — |

Alpha uses exact-boundary union units and KP/ABSENT nominal categories, not token accuracy or alpha-U.
CIs are stratified document-cluster percentile bootstrap CIs; no intervals are fabricated for missing judgments.

Full-population ID consistency: 1123/1123 distinct document/ID subjects; Wilson 95% CI 1.0000 [0.9966, 1.0000].
Explicit clinical DOB comparisons: 397 subjects. Checks include checksum, known DOB/sex and gold NATIONAL_ID coverage. Independent sex/county fields were not available; name-based sex or address-based birthplace consistency was not inferred.
Majority artifact flags: 0/0 complete documents; Wilson 95% CI unavailable.
Majority-approved gold operations: 0; conflicting documents: 0.
Zero approved operations with missing judgments is **not evidence that the gold is correct**.

| Pre-registered gate | Pass |
|---|---|
| sample | yes |
| complete | no |
| agreement | no |
| ratings | no |
| artifacts | no |
| decode | yes |
| gold_errors | no |

## Execution and spend

Execution diagnostics (counts are missing document/judge annotations, not API requests): {"HTTP Error 429: Too Many Requests": 30, "Unresolved request liability: no further paid calls": 870}.
Shared ledger records 6 attempted API requests and 6 unresolved request costs. Unresolved costs prevent further paid calls under the frozen protocol. See [execution record](panel-execution.json) for the initial attempt; missing judgments prevent a complete linguistic or annotation-quality verdict.

Shared RO+PL ledger: confirmed response costs $0.000000; outstanding worst-case reservations $0.179689; cap $25.
Responses carrying usage.cost: 0. These shared totals must not be added across reports.
See [ro-realskeleton-v1-disagreements.csv](ro-realskeleton-v1-disagreements.csv) for every observed disagreement, artifact, review vote, decode failure and missing annotation. Local raw responses, request ledger, sample texts and logs stay in scratch; the committed sample manifest identifies source rows/hashes.

## Corrections and leaderboard

Approved nonconflicting operations are exported to a local source-hashed overlay. The original revision and its audit result are preserved. No published dataset is mutated or promoted by this script.
No gold correction is established without the required votes. If no overlay exists, no leaderboard row has affected gold and no rescore is warranted. An overlay requires harness rescoring and a new held-out protocol before any promotion; original scores cannot be copied to repaired gold.

## Limitations

LLMs can share systematic errors and favor synthetic prose; different model families do not imply independent errors. Agreement is neither human IAA nor evidence of native competence, privacy, real-world representativeness or absence of linkability. One sampling seed and one authored template family limit generalization; document bootstrap CIs omit model and template-family uncertainty. Missing judgments prevent all linguistic/agreement conclusions. No model-performance win, human review, clinical correctness, or real-world privacy guarantee was verified.
