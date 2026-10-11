# RES-77 round 3: availability-only replacement preregistration

Frozen 2026-10-11 before round-3 inference or scoring. No previous round-3 report
existed at startup. This operational addendum supersedes only the Mistral seat,
its routing, and continuation accounting in [round 2](round2-protocol.md).
All original prompts, sample, statistics, adjudication and thresholds remain fixed.
Round-2 results were already known; this is not a new blind sample or a new win claim.

## Availability evidence and selection

[Round 1](panel-execution.json) records six initial Mistral HTTP 429 failures.
[Round 2](round2-execution.json) records nine 429s, with the second Mistral batch
exhausting all six attempts. The preserved raw error files in
`estate/scratch/res77-r2/cache/*.error.json` identify `upstream_provider_shared_pool`.
The model manifest below records their hashes and sanitized error evidence.
This replacement is authorized for availability only; no outcome probes are used.

The live https://openrouter.ai/api/v1/models catalogue and model `/endpoints` snapshots
were retrieved before scoring. Eligible multilingual general-purpose candidates:
DeepSeek V3.2, V4.1 Flash, V4 Flash 0731, Llama 4 Maverick, Llama 4 Scout.
Qwen is ineligible because it already occupies a seat; GPT includes Codex.
These are plausible RO/PL judges, not independently certified native-language experts.
Eligibility: active endpoint, temperature/max_tokens/response_format support,
input <=$0.60/M and output <=$3/M, and no request charge.
Rank models by best daily uptime, then number of distinct eligible providers with
daily uptime >=99.9%, then model ID lexically. Missing uptime ranks last.
Rank preferred endpoints by daily, 30-minute, then 5-minute uptime descending;
ties use endpoint tag lexically. Fallback stays within the SAME model and price caps.
Freeze the resulting list and snapshots in `round3-model-manifest.json`.

Chosen replacement: `deepseek/deepseek-v4.1-flash` (DeepSeek family; 23 eligible
providers >=99.9% daily uptime). Other candidate provider counts: V3.2 1,
V4 Flash 0731 17, Maverick 3, Scout 0. Best eligible daily uptime is 100% for
the first four; Scout's sole eligible endpoint has no uptime observation.
Preferred DeepSeek endpoint: `alibaba`, then the frozen uptime ordering.
Retain `google/gemini-2.5-flash` and `qwen/qwen3-235b-a22b-2507` unchanged.
Codex remains a supplemental GPT-family judge, never an external-seat replacement.

## Immutable data and carried evidence

Same reserved 300/config (75 admin/clinical/contract/declaration), sample seed 7712,
excluding author's review seed 7711. Generation seeds 2026101277 RO / 2026101278 PL.
Source: https://github.com/klusai/klusai-datasets/pull/23,
exact revision `79c7a91c47be20c8d214b05b09c2850fe8049037`, confirmed against
`refs/pull/23/head`. Original authored synthetic data, CC-BY-4.0, no new corpus.
Held-out/population byte hashes remain those of `round2-sample-manifest.json`.
No resampling, prompt changes, repairs, exclusions, or outcome-based reruns.
Carry forward the five valid RO Gemini and five valid RO Qwen Stage-A judgments,
verified against their raw cached responses. Exclude all Mistral judgments from
round-3 metrics, preserving them in round 2. Freeze carry-forward evidence hashes.

## Execution and accounting

Explicit task authorization permits this OpenRouter evaluation under a hard $25 cap.
Use environment OPENROUTER_API_KEY; serial calls, temperature 0, seed 77 where
supported, batches of five, maximum 8192 output tokens. Preserve round-2 routing
for Gemini/Qwen. No paid candidate probes. Cache and backoff follow round 2:
at most six attempts per request, only 429 retried, full unknown-cost reservations
retained; other errors or pending requests stop. Malformed outputs stay missing.
Copy the entire round-2 ledger into the round-3 ledger before dispatch, preserving
all $0.2941506 known/reserved prior liability. The $25 cap therefore includes
round 2 plus new round 3; round-1 ledger remains separately preserved.
Never reset the ledger or exhausted requests. Interrupted runs resume cached work.
Stage B runs only after complete Stage A; every candidate requires three votes.

## Unchanged gates, uncertainty and disposition

All three external judge-vs-gold exact-span nominal alphas and panel alpha >=0.80;
each judge's median fluency and naturalness >=4; majority artifact documents <=5%;
complete A on all 300/config and three B votes per candidate; no majority gold
errors or unresolved conflicts; all-population CNP/PESEL checks pass, including
gold coverage and explicit clinical DOB/sex consistency. Undefined values fail.
Only every gate passing permits `panel-validated`; otherwise keep `dev`.
Never `citable-validated`. Gates use overall point estimates; per-type diagnostics
do not introduce new thresholds. Report n and 95% CIs overall and per type:
2,000 document-cluster bootstrap replicates, stratified overall, seed 7701;
Wilson intervals for artifact/decode proportions. One sampling/generation seed
per language and one inference seed; no repeated-seed inference.
Report shared-template/model uncertainty, missing judgments, and limitations.
No human/native-language certification, real-world generalization, privacy claim,
or CI-disjoint model-performance win is established by this audit. No publishing.
