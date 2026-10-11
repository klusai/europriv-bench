# RES-77 autonomous LLM-panel protocol (pre-registration)

Frozen before paid inference, 2026-10-11. This is **autonomous LLM-panel validation**,
never native-speaker review or human validation. `citable-validated` remains human-only.
Main checked at task start: no existing RO panel protocol/results.

## Population, sample, and provenance

- Existing synthetic CC-BY-4.0 `klusai/europriv-bench`, test split, immutable HF revision
  `58faa4fa572cd8064818a6e1f8ca6e361b959c00`, RO and PL `*-realskeleton-v1`.
  Source: https://huggingface.co/datasets/klusai/europriv-bench . No new corpus.
- Exactly 300 documents per config: simple random sampling without replacement of 75 from
  each of clinical letter, legal contract, legal declaration, administrative notice.
  Identify types by the fixed heading (admin by domain); sort source row indices before
  sampling with Python `random.Random(77)`, in sorted stratum order, separately per config.
  Report strata/population counts. Equal-stratum estimates describe this balanced sample,
  not population-weighted performance. One sampling seed; no repeated model seeds.
- Retain source index, text SHA256, source revision, sample and protocol SHA256, model IDs,
  request parameters, provider, raw responses, usage/cost, timestamps and all disagreements.
  Download with `hf_hub_download` + pyarrow, never streaming parquet.
- Only synthetic text goes to APIs. Gold, decoded IDs and model outputs remain local.

## Judges and frozen procedure

Live catalogue and endpoint snapshots are saved in scratch before inference:
https://openrouter.ai/api/v1/models . Three different model families:
`mistralai/mistral-large-2512` (Mistral provider only), `google/gemini-2.5-flash`
(Google/Google AI Studio), `qwen/qwen3-235b-a22b-2507` (prefer Nebius; allow other
catalogue providers within price ceiling). These are multilingual judges selected for
Romanian/Polish plausibility and cost, not independently certified language competence.
Mistral is preferred; EU processing residency is **not** established by provider identity.
No model substitution after seeing outcomes. Temperature 0, seed 77 where supported;
provider nondeterminism remains possible. No tools, search, or external enrichment.

1. Stage A: each judge independently receives raw text, canonical KP taxonomy 0.2.0 and
   identical instructions, never gold or other judges' output. Batches of 5 documents.
   Return every entity as exact verbatim text + 1-based occurrence + KP label (mapped
   deterministically to character offsets), fluency and naturalness each on a 1–5 scale,
   plus concrete template-artifact flags. Include every repeated mention; exclude field
   labels/honorifics/punctuation. No normalization/fuzzy alignment of judge output.
   1 = unusable, 2 = major errors, 3 = understandable but conspicuously artificial,
   4 = minor defects, 5 = idiomatic/plausible for that document genre.
2. Freeze A responses. Candidate gold errors are every exact span-label tuple in the
   symmetric difference between gold and any judge. Stage B: each judge independently
   sees raw text, gold, and anonymized candidate add/remove operations, and flags which
   are gold errors with a reason. It sees no votes, judge identities, or ratings.
   A majority (>=2 of 3) approves an operation. Conflicting/overlapping approved edits
   remain unresolved, never silently applied. Gold-review responses cannot change A.
3. List **every** span disagreement (including boundary differences), rating difference,
   artifact flag, review vote/reason, malformed response and decode failure in CSV.
   Majority errors are LLM-adjudicated hypotheses, not human-certified corrections.

## Metrics and irrevocable gates

- Span-level nominal Krippendorff alpha: units are the union of exact `(start,end)` spans
  across gold + all three A judges per document; categories are KP types or ABSENT.
  Boundary mismatches produce separate units; no background true negatives. Report
  panel-vs-panel (three raters) and each judge-vs-gold (two raters) on this same universe.
  This is exact-span nominal alpha, **not** character/token alpha or unitizing alpha-U.
- Report 95% percentile CIs from 2,000 document-cluster bootstrap replicates, stratified
  by the four document types, seed 7701. Undefined alpha cannot pass. All three
  judge-vs-gold point estimates AND panel-vs-panel alpha must be >=0.80.
- Each judge's median fluency AND median naturalness must be >=4/5. Report medians and
  bootstrap CIs. Majority artifact-flagged documents must be <=5%; report Wilson 95% CI.
- CNP/PESEL: harness registry decode on **all 1,500** source documents, deduplicated
  `(document, normalized ID)` subjects. Require valid checksum, known DOB/sex and 100%
  agreement with explicitly stated DOB/sex when present. Check all raw-text 13-/11-digit
  IDs and their gold NATIONAL_ID coverage. Compare explicit DOB only in clinical rows
  (single patient); absence of independent sex/county fields is reported, not invented.
  Report denominators + Wilson CIs; checksum validity alone is not semantic consistency.
- Completeness: all 300 documents have valid A outputs from three families and all proposed
  gold changes have three valid B votes. No majority-approved gold errors or unresolved
  edit conflicts may remain. Any failed gate => original config stays `dev`.
- No outcome-based exclusions, changed thresholds, or replacement samples. Malformed
  outputs count as missing; cache them and fail completeness rather than reinterpret them.
  Operational fixes may repair code but cannot modify frozen prompts or valid judgments.

## Corrections and scope

Preserve original validation outcomes. Emit majority-approved nonconflicting gold repairs
as a local overlay with source hashes; never overwrite the published v1 data or claim the
same scored revision has changed. Re-score affected rows through the harness only when
stored predictions or local CPU models are available. Record unavailable rows explicitly;
never copy old scores onto changed gold. Generator changes outside this assigned worktree
must be delivered as a reviewable patch/instructions, not edits in another worktree.
A repaired config needs a separate pre-registration and fresh held-out validation; this
run cannot promote a repaired config by retesting the same 300 documents.

## Spend, caching, stopping

Hard total cap USD 25, including invalid responses and retries. Reserve a conservative
per-request maximum before dispatch using UTF-8 prompt bytes + framing allowance (token
upper bound) and bounded output tokens at enforced OpenRouter provider price ceilings.
Use `usage.cost` on every response; log it durably and release unused reservation.
An unknown cost/network interruption keeps its full reservation and stops further calls;
never assume a failed call was free. On restart unresolved requests stop paid work.
Stop before any reservation could cross $25. No automatic paid retries. Cache key hashes
full request + frozen protocol; reruns reuse responses, with a process lock to prevent
parallel duplicate spending. Record actual spend and outstanding worst-case liabilities.
API routing/cost references: https://openrouter.ai/docs/guides/routing/provider-selection
and https://openrouter.ai/docs/guides/guides/usage-accounting .

## Limitations required in each report

LLMs can share systematic errors, prefer polished synthetic prose, and miss culturally
specific defects; family diversity does not imply independent errors. Agreement with
synthetic gold is not accuracy or proof of privacy, representativeness, native competence,
absence of real-world linkability, or human IAA. One seed, one authored template family,
and 300 sampled docs/config limit generalization; bootstrap CIs do not capture model or
template-family uncertainty. No model-performance win is claimed by this audit.
