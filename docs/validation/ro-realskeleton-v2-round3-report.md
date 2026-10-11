# ro-realskeleton-v2: round-3 external panel

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
| agreement | fail/unverified |
| ratings | pass |
| artifacts | pass |
| decode | pass |
| gold_errors | fail/unverified |

Majority-approved gold operations: 0; unresolved conflicts: 0. These counts need complete B to establish no errors.
Stage-B valid documents: deepseek/deepseek-v4.1-flash: 0, google/gemini-2.5-flash: 0, qwen/qwen3-235b-a22b-2507: 0.
Malformed completed outputs remain missing; no repair/retry of their judgments.
Stage-A/B validation errors: {"'fluency'": 10, "Overlapping/duplicate annotations": 7}.

| Type | Complete n / sampled n | DeepSeek / Gemini / Qwen valid A | Majority artifacts [Wilson 95% CI] |
|---|---:|---|---|
| overall | 284 / 300 | 289 / 299 / 295 | 0/284 [0.0, 0.013345691846429175] |
| admin | 75 / 75 | 75 / 75 / 75 | 0/75 [0.0, 0.04872365402770864] |
| clinical | 59 / 75 | 64 / 74 / 70 | 0/59 [0.0, 0.06112913717268342] |
| contract | 75 / 75 | 75 / 75 / 75 | 0/75 [0.0, 0.04872365402770864] |
| declaration | 75 / 75 | 75 / 75 / 75 | 0/75 [0.0, 0.04872365402770864] |

Statistics below use only documents with all three valid external outputs. Partial-case
estimates cannot establish a config-wide pass. No complete cases means unavailable CIs.

| Type | n | Statistic / judge | Estimate [95% CI] |
|---|---:|---|---|
| overall | 284 | alpha: panel | 0.7275 [0.7167, 0.7386] |
| overall | 284 | alpha: deepseek/deepseek-v4.1-flash | 0.8607 [0.8411, 0.8787] |
| overall | 284 | alpha: google/gemini-2.5-flash | 0.8822 [0.8763, 0.8883] |
| overall | 284 | alpha: qwen/qwen3-235b-a22b-2507 | 0.6148 [0.6052, 0.6242] |
| overall | 284 | fluency: deepseek/deepseek-v4.1-flash | 5.0000 [5.0000, 5.0000] |
| overall | 284 | naturalness: deepseek/deepseek-v4.1-flash | 5.0000 [5.0000, 5.0000] |
| overall | 284 | fluency: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| overall | 284 | naturalness: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| overall | 284 | fluency: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| overall | 284 | naturalness: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| admin | 75 | alpha: panel | 0.8307 [0.8133, 0.8491] |
| admin | 75 | alpha: deepseek/deepseek-v4.1-flash | 0.8605 [0.8400, 0.8823] |
| admin | 75 | alpha: google/gemini-2.5-flash | 0.8609 [0.8586, 0.8630] |
| admin | 75 | alpha: qwen/qwen3-235b-a22b-2507 | 0.7606 [0.7472, 0.7746] |
| admin | 75 | fluency: deepseek/deepseek-v4.1-flash | 5.0000 [5.0000, 5.0000] |
| admin | 75 | naturalness: deepseek/deepseek-v4.1-flash | 5.0000 [5.0000, 5.0000] |
| admin | 75 | fluency: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| admin | 75 | naturalness: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| admin | 75 | fluency: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| admin | 75 | naturalness: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| clinical | 59 | alpha: panel | 0.7672 [0.7605, 0.7733] |
| clinical | 59 | alpha: deepseek/deepseek-v4.1-flash | 0.7554 [0.7399, 0.7707] |
| clinical | 59 | alpha: google/gemini-2.5-flash | 0.6799 [0.6544, 0.7041] |
| clinical | 59 | alpha: qwen/qwen3-235b-a22b-2507 | 0.6813 [0.6797, 0.6830] |
| clinical | 59 | fluency: deepseek/deepseek-v4.1-flash | 5.0000 [5.0000, 5.0000] |
| clinical | 59 | naturalness: deepseek/deepseek-v4.1-flash | 5.0000 [4.0000, 5.0000] |
| clinical | 59 | fluency: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| clinical | 59 | naturalness: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| clinical | 59 | fluency: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| clinical | 59 | naturalness: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| contract | 75 | alpha: panel | 0.7147 [0.6885, 0.7406] |
| contract | 75 | alpha: deepseek/deepseek-v4.1-flash | 0.8385 [0.7881, 0.8872] |
| contract | 75 | alpha: google/gemini-2.5-flash | 0.9287 [0.9234, 0.9346] |
| contract | 75 | alpha: qwen/qwen3-235b-a22b-2507 | 0.5965 [0.5795, 0.6124] |
| contract | 75 | fluency: deepseek/deepseek-v4.1-flash | 5.0000 [5.0000, 5.0000] |
| contract | 75 | naturalness: deepseek/deepseek-v4.1-flash | 4.0000 [4.0000, 5.0000] |
| contract | 75 | fluency: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| contract | 75 | naturalness: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| contract | 75 | fluency: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| contract | 75 | naturalness: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| declaration | 75 | alpha: panel | 0.6027 [0.5827, 0.6251] |
| declaration | 75 | alpha: deepseek/deepseek-v4.1-flash | 0.9698 [0.9413, 0.9939] |
| declaration | 75 | alpha: google/gemini-2.5-flash | 0.9924 [0.9849, 0.9985] |
| declaration | 75 | alpha: qwen/qwen3-235b-a22b-2507 | 0.4364 [0.4107, 0.4655] |
| declaration | 75 | fluency: deepseek/deepseek-v4.1-flash | 5.0000 [5.0000, 5.0000] |
| declaration | 75 | naturalness: deepseek/deepseek-v4.1-flash | 5.0000 [5.0000, 5.0000] |
| declaration | 75 | fluency: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| declaration | 75 | naturalness: google/gemini-2.5-flash | 5.0000 [5.0000, 5.0000] |
| declaration | 75 | fluency: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |
| declaration | 75 | naturalness: qwen/qwen3-235b-a22b-2507 | 5.0000 [5.0000, 5.0000] |

| Population type | ID consistency | Wilson 95% CI | Explicit DOB / sex consistent |
|---|---|---|---|
| overall | 1130/1130 | [0.996612010237734, 1.0] | 371/371 / 371/371 |
| admin | 0/0 | None | 0/0 / 0/0 |
| clinical | 371/371 | [0.9897518183454066, 1.0] | 371/371 / 371/371 |
| contract | 417/417 | [0.9908719940403783, 1.0] | 0/0 / 0/0 |
| declaration | 342/342 | [0.9888924729030792, 1.0] | 0/0 / 0/0 |

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
