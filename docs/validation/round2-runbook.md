# Reproducing RES-77 round 2

Both configs remain **dev**. See the [RO report](ro-realskeleton-v2-round2-report.md)
and [PL report](pl-realskeleton-v2-round2-report.md). The author's self-review was
not read; build provenance alone was used. Round-1 files remain unchanged.

Python 3.13, `pip install -e '.[dev,panel]'`. Run from the repo root:

```sh
SCRATCH=/Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/res77-r2
SOURCE=/Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/ro-gen-v2/v2-final
# Fresh preparation only; refuses to replace an existing frozen run:
python -m analysis.panel_round2 --scratch "$SCRATCH" --source "$SOURCE" --stage prepare
# Paid execution, only within the frozen policy and original ledger:
python -m analysis.panel_round2 --scratch "$SCRATCH" --stage a > "$SCRATCH/stage-a.log" 2>&1
# B refuses incomplete A; it did not run in this attempt:
python -m analysis.panel_round2 --scratch "$SCRATCH" --stage b > "$SCRATCH/stage-b.log" 2>&1
# Offline report reproduction (no inference):
python -m analysis.panel_round2_report --scratch "$SCRATCH" --out docs/validation
make check
```

`--offline` on A/B only replays complete cached responses, refuses cache misses,
and never sleeps for retry delays. Raw responses, request bodies, endpoint snapshots,
source rows, freeze metadata and the complete ledger remain in scratch.
Committed annotations, sample hashes, source revision, execution totals, endpoint
manifest, exhaustive disagreements and per-type CIs provide the reviewable evidence.
The Codex manifest records the blind review procedure and its limitations.

## Execution outcome and continuation limit

Twelve attempts: three successful responses, nine HTTP 429s. Five RO admin
documents have all three external judgments; 295 RO and all 300 PL documents
have none. No malformed response was retried. The first Mistral batch succeeded
on its fourth attempt; the second exhausted all six attempts. Error metadata
identifies `upstream_provider_shared_pool`, not an inferred account-credit issue.

Provider fallback was enabled for the exact same model ID. The live Mistral
catalogue listed only two Mistral endpoints (standard/priority), so no independent
provider alternative was advertised for that model. Successful response providers:
Mistral, Google AI Studio, Nebius. No model substitutions or extra credentials.

Confirmed `usage.cost`: **$0.0094176**. Unknown-cost reservations: **$0.284733**.
Known plus conservative reserved liability: **$0.2941506**, below the $25 cap.
These are not a claim that the 429s were free. Never delete/reset the ledger.
The exhausted request will stay exhausted on replay; a continuation beyond the
six-attempt rule requires a recorded operational addendum and billing reconciliation,
preserving this report, all judgments and the full original liabilities. It must
not change sample, model IDs, prompts, thresholds or valid outputs after inspection.

## Local audit details

The harness now recognizes clinical domain metadata despite the changed Polish
heading and checks v2's explicit Romanian/Polish textual sex fields. Negative tests
confirm that swapped or unknown sex values fail. The independent source preparation
reconstructs the original exclusion and reserved selection without reading author
self-review files. Frozen Codex files are hash-checked before offline scoring.

All 600 Codex records have exact offsets, ratings, reasons and artifact flags.
Codex used 11 raw-text prose variants/language plus every document's slot values;
code transcribed its selected annotations without reading gold. This shares context
and judgment across repeated prose and is disclosed as template-assisted review.
The script hash and freeze timestamp are in `round2-codex-manifest.json`; transcription
code and rendered review inputs remain in scratch. The clinical disagreement is a
taxonomy/boundary hypothesis, not adjudicated correction. No gold was changed.

Degenerate alpha CIs are expected here: within each stratum the span-label counts
and disagreement patterns repeat exactly. The cluster bootstrap therefore cannot
measure uncertainty across template families or judges. No v1–v2 win was established.
