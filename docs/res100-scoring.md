# RES-100 CPU harness scoring

The scored system is the merged RES-100 privacy-filter MoE plus a local literal masking
operator. It is not the deployed gateway. See `res100-scoring-protocol.json` for the frozen
endpoints and `gateway-contract.md` for acceptance. Results remain single-seed observations
until independent training seeds and every acceptance gate are available.

Run from this worktree with Python 3.13, transformers 5.10.2, torch 2.12.0 and peft 0.19.1
(the exact `klusai-models` moe extra), pyarrow and the harness dev dependencies. No training or paid service is used.
The following command discovers all `seed*/merged` checkpoints, resumes saved batches,
scores the pinned base under the same inference policy, compares available local receipts,
and splices only complete seed suites into the leaderboard:

```bash
PYTHONPATH=src:. .venv/bin/python analysis/score_res100.py \
  --scratch /Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/res100-score \
  --checkpoints /Users/mihai/codespace/research-artifacts/res100 \
  --receipt-source /Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/res125 \
  --base --splice
```

New seed directories can be added and the identical command re-run. Prediction identity
checks reject changed checkpoint files, gold, runtime, adapter source or inference settings.
Gold and exact native-span/output receipts stay in scratch. JSON writes are atomic; a failed
batch is repeated, not counted twice. Complete configs are scored immediately through
`run_spec`; the final splice refuses an incomplete seed. `--configs` supports diagnostic
subsets, which cannot be spliced until the full suite is complete.

The public benchmark revision exposes ten configs, including TAB; ten additional OpenPII
slices use the already-pinned source specs and licenses. Italian and legal real-skeleton specs
are unavailable on that revision and explicitly reported. No evaluation data is redistributed.

The candidate tokenizer's saved limit is 256. Evaluation uses overlapping 256-token windows
(stride 64) to retain long-document coverage. Transformers' simple aggregation only removes
B/I prefixes; the adapter also normalizes remaining E/S prefixes before KP label mapping.
Exact masking uses native offsets, including unmapped base labels, without token expansion
or the detection fairness mask. Every candidate/base output is checked against its intervals.

F1 and utility intervals use 2,000 document bootstrap resamples, RNG seed 100. Legacy and
v2 leakage use the harness Wilson intervals; comparative intervals use paired document
resampling on identical ordered gold. DIRECT/QUASI/UNSPECIFIED support is explicit; empty
support is unavailable. Seeds are never pooled as independent gold subjects.

Main leaderboard comparisons are historical aggregates, which cannot supply paired CIs.
RES-125 receipts are separate local reruns with their original operator/runtime provenance:
encoder runs can truncate at 512 tokens and retain historical E/S label handling. These
protocol differences remain visible. Missing or incomplete receipts are unverified. The
TAB-trained 560M seed receipts are named explicitly; main's `560m-legal` entry is retained
as a historical comparison without asserting checkpoint equivalence.

Not verified: gateway service/load acceptance, a new reviewed harder held-out challenge,
training/evaluation subject and source disjointness, or empirical attacker re-identification.
The eight-language training mixture means old RO/EN/PL-only contamination assumptions do
not apply; RES-100 rows conservatively retain unknown contamination outside RO synthetic.

The subsequent [dev-only calibration protocol](res100-calibration.md) and
[three-seed calibrated results](res100-calibrated-results.md) are separate evidence.
Their distinct leaderboard keys preserve these historical, uncalibrated seed-0 rows.
