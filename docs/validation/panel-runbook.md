# Reproducing the RES-77 audit

Use Python 3.13 and install `pip install -e '.[dev,panel]'`. No GPU or model weights are
needed. Only the A/B commands can make paid calls, via `OPENROUTER_API_KEY`.
All raw data, request bodies, cached responses, resumable stage files and spend ledger
belong in the coordinator-assigned scratch directory. Never delete a ledger to reset spend.

```sh
SCRATCH=/Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/res77-panel
python analysis/panel_validation.py --scratch "$SCRATCH" --stage prepare
python analysis/panel_validation.py --scratch "$SCRATCH" --stage a > "$SCRATCH/stage-a.log" 2>&1
python analysis/panel_validation.py --scratch "$SCRATCH" --stage b > "$SCRATCH/stage-b.log" 2>&1
python analysis/panel_report.py --scratch "$SCRATCH" --out docs/validation
```

Preparation pins the public dataset revision and records 75 documents/type/config.
The A/B runner uses immutable request/protocol hashes; replaying completed requests is free.
`--offline` forbids all network inference and fails cache misses. Reports are always offline.
Stage B reads frozen stage-A annotations, never changes them, and only reviews documents
with all three valid A outputs. Do not run B on incomplete A as a substitute for completion.

## Current execution blocker

The first six Mistral requests (30 RO admin documents, one judge each) returned HTTP 429;
no successful response or `usage.cost` was obtained. The remaining 1,770 document/judge
assignments were not sent. Stage B did not run. The account read endpoint showed spending
capacity, but does not establish whether these individual failed requests incurred costs.
The initial transport lost error bodies/headers; that diagnostic defect is now fixed and
covered by a test. It cannot retrospectively establish the specific rate-limit cause.
Request bodies were reconstructed from the frozen inputs and matched to ledger hashes;
no inference was repeated to obtain diagnostics.

The original frozen protocol explicitly stops on unknown cost. Its six reservations total
$0.1796892; confirmed response costs are $0, **not a claim of zero actual charges**.
An operator must reconcile the pending requests against provider billing before a paid
continuation. Preserve the original ledger and evidence; a continuation needs an explicit
operational addendum if it changes the unknown-cost/no-retry rule. Do not silently alter
thresholds, prompt wording, judges, sample, or the original incomplete reports.

## Protocol wording clarification

The pre-registration's sentence saying gold remains local refers to storage, but is too
broad about transmission: its explicit Stage B procedure sends **synthetic gold span
annotations** alongside synthetic text to the same judges. Decoded identifier fields and
other judges' votes are not sent. Stage A never sees gold. No Stage B ran in this attempt.
The original pre-registration is preserved byte-for-byte for its recorded hash.

## Repairs and status

`panel_report.py` exports majority-approved, nonconflicting edits to source-hashed local
`*-gold-overlay.json`. It preserves original outcomes, detects conflicting edits, and never
promotes configs or overwrites published data. There are no established corrections in
this incomplete run; both overlays are empty and no leaderboard row requires rescoring.
If a later completed run finds errors, apply reviewed corrections to a new dataset revision,
re-score affected rows through `run_spec` using stored predictions/local CPU adapters, and
record unavailable models rather than copying old scores. Generator changes in another
repo must be delivered to its coordinator, not edited outside the assigned worktree.

Promotion to `panel-validated` is a curated change to `_PANEL_VALIDATED_CONFIGS` after a
passing, source-pinned report; the set is currently empty. `citable-validated` remains
reserved for human sign-off. The sample/CI results never certify native fluency, human IAA,
real-world privacy, or generalization beyond these authored synthetic templates.

## No-cost Codex follow-up

[Codex session review](codex-review.md) adds 300 raw-text annotations/config plus single-judge
hypotheses, retaining the frozen judges, thresholds, source and verdict. Reproduce the supplement
with `panel_report.py --codex-dir docs/validation` and `--overlay-out` pointing to the follow-up
scratch. The original A/B ledger and reservations remain unchanged. Both configs still stay `dev`;
Codex cannot substitute for the missing three-family panel. Romanian generator changes are delivered
as a [tested patch and fix list](codex-ro-quality-fixes.md), not applied outside the assigned worktree.
