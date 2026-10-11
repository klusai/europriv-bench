# RES-77 round 2: independent v2 pre-registration

Frozen 2026-10-11 before inspecting held-out documents or scoring. Fetched main
`14cfc44d5218e2f96081fc7ea8db5b07eb2880b3`: no existing v2 round-2 report.
The original [round-1 protocol](panel-protocol.md) supplies the unchanged prompts,
taxonomy, annotation rubric, exact-span alpha definition, adjudication, and gates.
This document supersedes only its sample/provenance and transport rules for round 2.

## Frozen population and independence

Source: https://github.com/klusai/klusai-datasets, branch `res-77-ro-generator-v2`,
PR #23. Original authored synthetic prose, CC-BY-4.0; no new external corpus.
Use the final local build (`ro-gen-v2/v2-final`), never published v1 or development v2.
Pin the source commit and build manifests in the round-2 sample manifest.
Each population is 1,500 docs; generation seeds 2026101277 RO and 2026101278 PL.
Use the already reserved 300/language: 75 each admin, clinical, contract, declaration,
sampling seed 7712 after excluding the author's 25/type self-review (seed 7711).
No resampling, exclusions, generator repairs, or outcome-dependent substitutions.

| Config | SHA256 heldout-review.jsonl | SHA256 test.jsonl |
|---|---|---|
| ro-realskeleton-v2 | cf320aebb7fd53c68ebb16e18116cbe0fea1f4e9f6cd8f0cc7d16e49b4daa470 | 3b03b17125a643d5c1118ff476e61df704dd1458f2a1f9dc53140c3b21ab7bb7 |
| pl-realskeleton-v2 | bcb99ae771c20e11f2dd77f4cd27560bb97a67d82a7c8240bc834eedef835e29 | 1fdcf3ee0ba4c3b7d87c16d4be353acc4ddb60bce1fec8fa4a6e84f5c2ea593a |

The v2 author's self-review DOES NOT COUNT as independent validation and is not
read by this reviewer. Build manifests/protocol were inspected for provenance,
not used as scored evidence. Codex reads raw held-out text with no gold or panel
outputs, annotates exact spans and rates fluency/naturalness with artifact reasons,
freezes its annotations before gold comparison, and remains a supplemental judge.
Its scores cannot replace any of the three required external families. Report
session context/template dependence and unavailable decoding settings explicitly.

## Judges, execution, and budget

Keep exact IDs: `mistralai/mistral-large-2512`, `google/gemini-2.5-flash`,
`qwen/qwen3-235b-a22b-2507`. No model substitution. Temperature 0, seed 77,
batches of five, output cap 8192, same Stage A/B instructions as round 1.
Allow provider fallback for the SAME model: prefer Mistral, Google, and Nebius
respectively, with OpenRouter's fallback enabled and no restrictive provider-only
list. Retain price ceilings $0.60/M input, $3/M output, $0/request.
Snapshot the live model/endpoint catalogue before calls. No residency claim.

Use OPENROUTER_API_KEY from environment. New round-2 ledger, hard total USD 25;
round-1 liabilities remain separate and are not overwritten. Cache full requests,
responses, errors, timestamps, provider, protocol/sample hashes and usage.cost.
Reserve the conservative request bound BEFORE EACH attempt. Successful responses
must supply finite nonnegative usage.cost. Unknown-cost errors retain their FULL
reservation; never treat 429 as free. Only HTTP 429 is retried, at most five retries
after the first attempt, sleeping min(32, 2**retry) seconds plus uniform [0,1) jitter
and honoring Retry-After up to 60 seconds (longer delays stop for a later resume).
429 liability remains counted across retries/restarts. Other unknown costs stop
paid work. Six exhausted 429 attempts stop the run rather than advancing batches.
Pending interrupted requests stop work until reconciled. Serial calls,
durable atomic state, and a process lock prevent duplicate dispatch. Stop before
known spend plus all outstanding bounds plus the next bound would reach $25.
Malformed completed outputs stay missing; no outcome-dependent retry or reinterpretation.

Routing/accounting references:
https://openrouter.ai/docs/guides/routing/provider-selection and
https://openrouter.ai/docs/cookbook/administration/usage-accounting .

## Unchanged irrevocable gates and reports

- Three judge-vs-gold exact-span nominal alphas AND panel alpha each >=0.80;
  undefined values fail. Union exact boundaries, ABSENT category, no background TNs.
- Each external judge median fluency AND naturalness >=4/5.
- Majority artifact-flagged documents <=5%.
- Complete A for all 300 docs per language from all three families; every proposed
  gold change receives three B votes. No majority gold error or unresolved conflict.
- Harness CNP/PESEL decode on all 1,500/config: valid checksum, known DOB/sex,
  raw numeric ID gold coverage, and 100% agreement with explicit clinical DOB/sex.
  Parse v2's explicit textual sex fields; report absent independent fields honestly.

Report overall AND each of contract/clinical/admin/declaration separately, with n.
Alpha/median 95% percentile CIs: 2,000 document-cluster bootstrap replicates,
stratified by type for overall estimates, seed 7701. Artifact/decode proportions:
Wilson 95% CIs. One sampling seed, one generation seed/language, one judge run;
no repeated inference seeds. Per-type results are diagnostics, not new gates.
Any missing/failed gate keeps dev. Only every gate passing permits panel-validated;
never citable-validated. Do not publish or claim a performance win. CIs condition
on this template family and these judges; no native competence, human IAA, privacy,
real-world representativeness, unseen-template generalization, or v1-v2 win claim.
