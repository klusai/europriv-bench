# Gateway metric and SLO contract — RES-121 / RES-120

Contract version: **1**. Residual metric version: **2**. Status: frozen engineering acceptance
criteria; **no gateway/model acceptance or production readiness demonstrated by this change**.
Changes to units, coverage, policy or thresholds require a new contract/metric version, never an
in-place reinterpretation of historical scores.

## 1. Frozen metric semantics

`tab_reid_leakage` and `name_in_context_leakage` remain historical **v1**; explicit `_v1` aliases
resolve to the same functions. Existing specs, score artifacts, national-ID metrics and prediction
fairness filtering remain unchanged. In v1, an occurrence counts as detected when **any** overlapping
whitespace token is non-O; all occurrences must be detected. This is an any-overlap proxy: masking
`John` in `John Smith` can produce zero name leak. Do not relabel those scores as full-span protection.
Reproduction requires the original harness commit, spec/data revision and split, checkpoint/tokenizer,
crosswalk, thresholds and predictions. New aliases alone cannot reconstruct missing run provenance.

New keys (implemented in `europriv_bench.metrics`):

| Key | Gold scope and unit |
|---|---|
| `tab_reid_leakage_v2` | Every TAB span must carry `entity_id` and DIRECT/QUASI. Unit remains `(document index, entity_id, identifier_type)`; repeated mentions/aliases share a unit. Missing metadata is an error. |
| `residual_leakage_v2` | Every gold protected span, across all PII labels. Explicit entity IDs group coreference within a document and sensitivity class. Without IDs, group by `(document index, country, label, whitespace-normalized exact value, identifier_type)`; these are identifier subjects, not unique people. Missing sensitivity is UNSPECIFIED, never silently DIRECT. |

For gateway scoring, one row must represent the entire conversation: concatenate screened text fields
in a frozen order, translate both gold and operator offsets into that coordinate space, and retain
cross-turn entity IDs. Never treat repeated turns as independent subjects or bootstrap clusters.

Input: one list of actual removed/replaced intervals per original text, using Python Unicode code-point
offsets `[start,end)`, not UTF-8 bytes or UTF-16 code units. Intervals may overlap, abut, or arrive out of
order; score their union. Offsets must be integers within bounds, with `start < end`. Missing prediction
rows, invalid offsets, whitespace-only gold spans and unknown sensitivity classes fail loudly.

An occurrence is protected iff **every non-whitespace character** in its gold span is covered. Only
`str.isspace()` characters are exempt; punctuation, digits, diacritics and combining marks count.
One uncovered character in any occurrence makes that subject leak. No case folding, Unicode
normalization, fuzzy matching, BIOES expansion, or predicted-label correctness affects coverage.
Spans from any prediction label count if the frozen operator actually removes those characters.
Keep context-sensitive public dates/organizations out of protected gold according to the frozen
annotation policy; report their removal as utility loss. Overlapping gold is supported by v2-only
specs; specs also requesting legacy tag metrics require BIOES-representable gold.

Outputs: `metric_version=2`, `{all,direct,quasi,unspecified}_subjects_{total,leaked}`, leak rates,
two-sided **95% Wilson CIs**, and `*_available`. An empty group has `available=0` and numeric zero
sentinels for rate/CI: **unavailable, never a measured 0%**. Denominators are gold-defined and identical
across systems. `residual_subject_detection_v2` emits deterministic identities, document clusters and
binary outcomes for paired analysis. Wilson intervals are descriptive subject-count intervals; correlated
mentions/subjects require document/conversation-cluster bootstrap for comparative inference.

This is **residual identifier leakage**, not empirical attacker re-identification probability, population
uniqueness, or the PURR v2 discussed in `klu-118-qi-distinctiveness-design.md`.

## 2. Harness use and controls

`run_spec` accepts the new metric keys and obtains coverage from `adapter.redaction_spans(texts)` or
an explicitly supplied `redaction_spans=` replay. `dumps=` includes a separate, metric-versioned v2
subject record. Exact coverage uses no token-label fairness mask. Legacy metrics still use their original
path, so both versions can be scored in one run. V2-only replay needs no model/token predictions.
Replay intervals must come from the same pinned
model/service, policy and inputs as the recorded run; retain operator receipts with prediction artifacts.

The base adapter raises if exact coverage is unavailable. Existing model adapters are **not yet v2
service baselines**: `KpModelAdapter.predict_spans` expands onto the whitespace grid, and token tags
cannot prove that a partial token was fully removed. Implement the exact service/operator adapter in
the follow-up; do not manufacture character coverage from those predictions. V2 is currently wired
through detection specs with operator coverage; the existing anonymization-text path rejects v2.

Example local replay (no model download or inference):

```python
from europriv_bench.metrics import tab_reid_leakage_v2

rows = [{"text": "John Smith", "spans": [{"start": 0, "end": 10,
         "label": "PERSON", "entity_id": "p1", "identifier_type": "DIRECT"}]}]
score = tab_reid_leakage_v2(rows, [[(0, 4)]])
assert score["direct_subjects_leaked"] == 1  # Smith survives
```

Mandatory controls in `tests/test_residual_leakage_v2.py`: no masks leak; full coverage protects;
given-name-only and partial-character masks leak; one missed repeated mention leaks; overlapping
coverage is unioned; Unicode boundaries and punctuation are retained; zero support is unavailable;
bad alignment/counts fail. A harness-scored negative control shows v1=0 versus v2=1 on the same
partially masked name, with n=1 and Wilson intervals. It proves metric behavior, not a model win.
Pseudonym operators must attest that replacements do not copy protected source fragments; coverage
alone cannot validate arbitrary replacement contents, restoration, side channels or semantic utility.

## 3. Zero floors and what counts as a win

The frozen legacy RO/PL national-ID anchor is a **tie** when kp and Presidio both leak 0%.
Increasing n narrows intervals but cannot turn equal zero rates into strict superiority. Preserve it
as a regression anchor. A faster tied model may be a performance improvement, never a privacy win.

Existing harness evidence from RES-120 (95% Wilson; configs remain `dev`):

| Anchor | Docs / subjects | kp and stock Presidio | Seed/run scope |
|---|---:|---|---|
| RO real-skeleton v1 | 1,500 / 1,123 | 0% [0%, 0.3409%] | kp v2 seeds 0/1 zero; baseline one run |
| PL real-skeleton v1 | 1,500 / 1,096 | 0% [0%, 0.3493%] | kp v2 seeds 0/1 zero; baseline one run |

Here “kp v2” names the existing model, **not this metric**. These are legacy national-ID results;
they supply no residual-v2 rate. Source: the
[RES-120 evidence ledger](https://github.com/klusai/klusai-models/blob/1856d8817996b4d0c5f04137acec1bb8e3aef87d/docs/north-star-gap.md),
§2, citing harness leaderboard artifacts. No models were rescored for RES-121.

Pre-register a distinct harder held-out full-PII configuration before inspecting its results; never
replace the saturated anchor or tune against its successor's test split. Pin gold, annotation policy,
service/model/tokenizer hashes, operators, entity filters, crosswalks, thresholds and seed IDs. Preserve
subject/source/scenario-family/translation disjointness and native-review gates. Report stock EuroPriv
Presidio and exact deployed Shield as **separate comparators**; a stock-baseline win does not transfer.

A scoped privacy win requires **all** of:

1. On the same held-out configuration, candidate v2 Wilson upper bound is strictly below comparator
   lower bound on the predeclared primary endpoint (`all_leak_rate`; TAB DIRECT can be a separately
   named endpoint). Use at least three independent candidate training seeds; each seed must pass.
   Do not pool repeated scoring of the same gold subjects as independent n.
2. Paired conversation/document-cluster bootstrap for candidate minus comparator has a 95% upper
   bound <0, with ≥2,000 resamples and recorded RNG seed. Report subject n, cluster n, per-seed
   estimates/CIs and deltas. This paired CI alone does not replace the disjoint-Wilson requirement.
3. Over-redaction (fraction of gold non-PII, non-whitespace characters removed) has a paired cluster
   bootstrap delta upper bound ≤0: literal no-worse utility margin. Report empty utility denominators
   as unavailable. Preserve v1 national-ID zero floors (any observed new leak fails that anchor).
4. Gateway-wide claims pass every required language (RO/EN/DE/FR/ES/IT/NL/PL), not just a pooled
   average; report worst-language and DIRECT/QUASI/UNSPECIFIED slices, missing support and all seeds.
   Missing reviewed gold, baseline or support means **not established**. Declare endpoints/slices
   before scoring and report all of them, not the best checkpoint/slice alone.

Overlapping CIs or zero/zero means no established superiority; equality of point estimates is not a
statistical equivalence claim. If the new configuration also saturates, report the tie and register
another independent challenge before collecting it. The comparative/utility bootstrap and future
gateway dataset are follow-up work; this change implements the coverage metric and outcome dumps.

## 4. Latency and load acceptance

Freeze the RES-120 proposal as the engineering gate: **added end-to-end p95 ≤250 ms while completing
≥15 short chat requests/s**, with the quality-approved configuration on the target CPU deployment.
This is a target, not a measured capacity claim or evidence of product/production sign-off.

Short lane: ≤256 input tokens using the pinned deployed tokenizer, covering all eight languages on a
frozen replay corpus with the same lengths, payload shapes and language mix for every engine. A request
includes all screened text fields/turns; no silent truncation. Timing starts at gateway screening enqueue
and ends with the final screened immutable body ready for dispatch (or refusal). Include queueing,
tokenization, inference, operator/maps, serialization and transport; exclude upstream LLM generation.

Protocol: pin hardware/OS/runtime, model/graph/quantization, process/thread counts, replicas, batch
size/wait, queue capacity, client connections and timeouts. Use open-loop arrivals to avoid coordinated
omission. After a recorded warmup, run ≥3 separate 10-minute trials per load point at offered rates
1, 5, 10.5, 15, 16 and 20 req/s. Add points around saturation; do not infer multi-lane scaling.
At **16 offered req/s**, each trial must meet the following gate (9,600 offered requests/trial):

| Measure | Gate |
|---|---|
| Successful screening latency | p95 point estimate and 95% bootstrap upper bound ≤250 ms |
| Successful completed throughput | ≥15 req/s in every trial; exclude refusals, timeouts and errors |
| Errors + timeouts + overload refusals | Combined ≤0.1% of offered requests; count each request once |
| Screening deadline | 1,000 ms from enqueue; cancel/refuse at expiry and never dispatch unscreened input |
| Bypass/truncation | Zero silent bypasses or truncated accepted payloads; failures cause no upstream call |

The 16 req/s offered point leaves room to demonstrate 15 successful completions/s without treating
errors as useful throughput. Report offered/completed/failed counts, outstanding/drained requests,
concurrency, p50/p95/p99, cold starts, per-language tails, queue depth, memory and saturation curves.
Use ≥2,000 time-block bootstrap resamples (fixed 10-second blocks, recorded RNG seed) per trial for
latency/throughput CIs; publish the three trials separately. Drain the queue and account for every
request; do not omit failed/slow requests from the denominator or hide them behind successful tails.

Long requests (257–2,048 tokens) use a separately bounded queue/lane and reported SLO; this contract
does **not** assert a long-input latency pass. Exercise long-input interference and mixed-language
traffic before gateway rollout. Longer/unsupported payloads require explicit admission/refusal, never
silent partial screening. Deadline-bounded fallback may use only a separately quality-approved engine;
record the actual engine and do not transfer kp quality claims to fallback responses.

Existing local CPU timing evidence (RES-120 §4; Apple M3 Ultra, CPU fp32, batch 1, eight intra-op
threads, one process, ten warmups, same 200 fictional inputs, one timed pass/model, seed0 checkpoint):

| Model | n | p95 ms [95% bootstrap CI] | Sequential req/s [95% CI] |
|---|---:|---:|---:|
| kp-280m | 200 | 147.97 [142.55, 157.88] | 9.04 [8.81, 9.28] |
| kp-560m-legal | 200 | 284.41 [206.66, 347.89] | 6.07 [5.76, 6.37] |

Those intervals use 5,000 input resamples, RNG seed 120, conditional on a single pass on a shared
host; they exclude transport, queueing and operators. The 280M timing is below 250 ms locally but
does not demonstrate the service/load gate; the 560M point estimate already exceeds it. Neither
single lane demonstrated 15 req/s. **Presidio ~10.5 req/s is an unverified planning input** with no
matched receipt, n, seed/run count or CI in the inspected evidence; it is not a scored head-to-head.
Re-measure all engines on identical deployment/workload before claiming latency or throughput wins.

Not verified here: model residual-v2 quality, exact Shield coverage, reviewed gateway gold, comparative
bootstrap/utility acceptance, HTTP load, ONNX/int8, target Outpost/blade capacity, or live integration.
No GPUs, cloud resources, paid APIs or new external data sources are needed for this contract change.
