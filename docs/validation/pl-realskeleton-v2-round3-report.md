# pl-realskeleton-v2: round-3 external panel

Status: **dev**. All frozen gates must pass for promotion.

[Preregistration](round3-protocol.md) · [Model selection](round3-model-manifest.json) · [Reproduction](round3-runbook.md).

Data revision: `79c7a91c47be20c8d214b05b09c2850fe8049037` ([datasets PR #23](https://github.com/klusai/klusai-datasets/pull/23)); CC-BY-4.0 authored synthetic data. Same round-2 holdout: 300/config, 75/type; population 1,500/config.
Sampling seed 7712; generation seed 2026101277 (RO) / 2026101278 (PL); inference seed 77.
One seed per component/language; no repeated-seed inference. 95% CIs: 2,000 document-cluster
bootstrap draws, stratified overall, seed 7701; Wilson intervals for proportions.

DeepSeek replaces Mistral for availability only. Gemini/Qwen each reuse five frozen RO outputs.
Codex remains supplemental; its prior review is not counted as a required external seat.
Round-2 scores were already known. No new sample, changed prompts, or selected retries.

| Gate | Result |
|---|---|
| sample | pass |
| complete | fail/unverified |
| agreement | pass |
| ratings | pass |
| artifacts | pass |
| decode | pass |
| gold_errors | fail/unverified |

Majority-approved gold operations: 0; unresolved conflicts: 0. These counts need complete B to establish no errors.
Stage-B valid documents: deepseek/deepseek-v4.1-flash: 0, google/gemini-2.5-flash: 0, qwen/qwen3-235b-a22b-2507: 0.
Malformed completed outputs remain missing; no repair/retry of their judgments.
Stage-A/B validation errors: {}.

| Type | Complete n / sampled n | DeepSeek / Gemini / Qwen valid A | Majority artifacts [Wilson 95% CI] |
|---|---:|---|---|
| overall | 165 / 300 | 170 / 170 / 165 | 0/165 [0.0, 0.022751778999029526] |
| admin | 75 / 75 | 75 / 75 / 75 | 0/75 [0.0, 0.04872365402770864] |
| clinical | 75 / 75 | 75 / 75 / 75 | 0/75 [0.0, 0.04872365402770864] |
| contract | 15 / 75 | 20 / 20 / 15 | 0/15 [0.0, 0.20388264107463847] |
| declaration | 0 / 75 | 0 / 0 / 0 | 0/0 None |

Statistics below use only documents with all three valid external outputs. Partial-case
estimates cannot establish a config-wide pass. No complete cases means unavailable CIs.

| Type | n | Statistic / judge | Estimate [95% CI] |
|---|---:|---|---|
| overall | 165 | alpha: panel | 0.8463 [0.8355, 0.8574] |
| overall | 165 | alpha: deepseek/deepseek-v4.1-flash | 0.8676 [0.8578, 0.8769] |
| overall | 165 | alpha: google/gemini-2.5-flash | 0.8781 [0.8664, 0.8888] |
| overall | 165 | alpha: qwen/qwen3-235b-a22b-2507 | 0.8705 [0.8620, 0.8786] |
| overall | 165 | fluency: deepseek/deepseek-v4.1-flash | 5.0000 [5.0000, 5.0000] |
| overall | 165 | naturalness: deepseek/deepseek-v4.1-flash | 5.0000 [4.0000, 5.0000] |
| overall | 165 | fluency: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| overall | 165 | naturalness: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| overall | 165 | fluency: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| overall | 165 | naturalness: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| admin | 75 | alpha: panel | 0.8977 [0.8802, 0.9147] |
| admin | 75 | alpha: deepseek/deepseek-v4.1-flash | 0.9422 [0.9182, 0.9649] |
| admin | 75 | alpha: google/gemini-2.5-flash | 1.0000 [1.0000, 1.0000] |
| admin | 75 | alpha: qwen/qwen3-235b-a22b-2507 | 0.8947 [0.8815, 0.9088] |
| admin | 75 | fluency: deepseek/deepseek-v4.1-flash | 5.0000 [5.0000, 5.0000] |
| admin | 75 | naturalness: deepseek/deepseek-v4.1-flash | 5.0000 [5.0000, 5.0000] |
| admin | 75 | fluency: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| admin | 75 | naturalness: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| admin | 75 | fluency: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| admin | 75 | naturalness: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| clinical | 75 | alpha: panel | 0.7682 [0.7501, 0.7868] |
| clinical | 75 | alpha: deepseek/deepseek-v4.1-flash | 0.7919 [0.7840, 0.8004] |
| clinical | 75 | alpha: google/gemini-2.5-flash | 0.7683 [0.7474, 0.7896] |
| clinical | 75 | alpha: qwen/qwen3-235b-a22b-2507 | 0.8407 [0.8289, 0.8536] |
| clinical | 75 | fluency: deepseek/deepseek-v4.1-flash | 5.0000 [5.0000, 5.0000] |
| clinical | 75 | naturalness: deepseek/deepseek-v4.1-flash | 5.0000 [4.0000, 5.0000] |
| clinical | 75 | fluency: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| clinical | 75 | naturalness: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| clinical | 75 | fluency: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| clinical | 75 | naturalness: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| contract | 15 | alpha: panel | 0.9616 [0.9501, 0.9769] |
| contract | 15 | alpha: deepseek/deepseek-v4.1-flash | 0.9138 [0.9138, 0.9138] |
| contract | 15 | alpha: google/gemini-2.5-flash | 0.9137 [0.9136, 0.9138] |
| contract | 15 | alpha: qwen/qwen3-235b-a22b-2507 | 0.8853 [0.8625, 0.9024] |
| contract | 15 | fluency: deepseek/deepseek-v4.1-flash | 5.0000 [5.0000, 5.0000] |
| contract | 15 | naturalness: deepseek/deepseek-v4.1-flash | 4.0000 [4.0000, 4.0000] |
| contract | 15 | fluency: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| contract | 15 | naturalness: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| contract | 15 | fluency: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| contract | 15 | naturalness: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| declaration | 0 | Agreement / fluency / naturalness | unavailable |

| Population type | ID consistency | Wilson 95% CI | Explicit DOB / sex consistent |
|---|---|---|---|
| overall | 1110/1110 | [0.9965511759101382, 1.0] | 352/352 / 352/352 |
| admin | 0/0 | None | 0/0 / 0/0 |
| clinical | 352/352 | [0.9892046211170977, 1.0] | 352/352 / 352/352 |
| contract | 378/378 | [0.9899396902300837, 1.0] | 0/0 / 0/0 |
| declaration | 380/380 | [0.9899921093210813, 1.0] | 0/0 / 0/0 |

Decode includes checksum, known DOB/sex, raw national-ID gold coverage and explicit clinical fields.
Per-field Wilson CIs and exhaustive disagreements are in the companion JSON/CSV. Absent independent
fields outside clinical records are not invented. No registry or address/bank lookup was performed.

Cumulative round-2+3 usage.cost: $0.86720452; unknown-cost reservations: $0.31770000; conservative liability: $1.18490452 / $25.
Prior liabilities are retained; failed requests are not assumed free. See round3-execution.json.
Transport stop: HTTP 400 from GMICloud for qwen/qwen3-235b-a22b-2507. Full sanitized fallback trail and raw-error hash are in round3-execution.json.

Limitations: shared authored templates and correlated model errors; bootstrap CIs condition on
these judges/template family and do not measure unseen-template or model-family uncertainty.
No human/native-speaker validation, clinical/legal certification, privacy guarantee, real-world
representativeness, or CI-disjoint model-performance win was verified. Agreement is not accuracy
or human IAA. The supplemental Codex review used shared template-assisted context (round 2).
No gold edits or publication. Failed/incomplete gates keep dev, never citable-validated.
