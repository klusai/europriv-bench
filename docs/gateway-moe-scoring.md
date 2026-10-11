# Gateway-trained MoE default operating point

Prospective scoring protocol, 2026-10-11: gateway-trained privacy-filter MoE,
seed 0 initially, later seeds scored with the same command. No test-time selection
or calibration. Checkpoint SHA manifest and training seed must match. CPU fp32,
transformers 5.10.2, torch 2.12.0, peft 0.19.1; four threads, batch 16.
Use the saved tokenizer default of 512 tokens, overflow stride 64; simple
aggregation with remaining BIOES prefixes normalized. Apply every native span,
without confidence filtering, through the exact literal-block union operator.
This is the local harness operator, not a deployed gateway equivalence claim.

Inference starts only after the prospective contract v3 commit is available.
Pin that commit before inference. Report both v2 and v3 verdicts without changing
any prior result. V3 allows paired utility delta CI upper <= .01 absolute;
privacy, zero-floor, three-seed and reviewed/disjoint-held-out requirements remain.

Reuse the ordered gold and licensed source pins of #53/#54/#57: 20 available
configs plus eight gateway-traffic-v1 test language configs, using the #54 local
override and revalidating its loader/source hashes. Two unpublished Italian/legal
real-skeleton configs remain explicitly unavailable at the pinned revision.
OpenPII retains its actual validation split. Gateway synthetic test remains dev.
No new data source or data redistribution. Gateway train/test disjointness is
reported by the training task; this run does not independently audit it.

Use harness F1, legacy national-ID/name/TAB leakage, exact residual-v2 all/DIRECT/
QUASI/UNSPECIFIED Wilson intervals, and non-PII character over-redaction. Gateway
annotations collide on the whitespace-token grid; retain its registered v2-only
spec and explicitly mark legacy/F1 unavailable, without dropping or moving gold.
Use 2,000 document/conversation bootstrap resamples, RNG seed 100 (as #53/#57),
for F1, utility and paired candidate-minus-comparator deltas. Never pool seeds.

Comparators: pinned base privacy-filter, default RES-100 MoE seed0 (replay raw
pre-calibration detections at threshold 0), kp-280m, TAB-trained 560m seed0,
stock Presidio and exact pinned Shield. Check receipt hashes and identical ordered
gold; retain original runtime, operator, truncation and label-decoding provenance.
Comparisons assess complete pipelines, including their historical window policies.
Shield remains a separate system. No service or paid API is started.

Run from this worktree using the existing Python 3.13 MoE runtime:

```bash
PYTHONPATH=src:. /Users/mihai/codespace/research-worktrees/res100-cal/.venv/bin/python \
  -u analysis/score_gateway_moe.py --splice \
  > /Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/gw-score/scoring.log 2>&1
```

The command discovers seed directories; `--seeds 0` restricts an initial run.
Atomic batch receipts resume without repeating completed inference. Changed gold,
checkpoint, source, runtime or inference policy fails closed. Only complete seed
suites may be spliced. Raw gold and receipts stay in scratch, aggregate rows in git.
No publication, push, training, cloud compute or GPU inference is performed.
