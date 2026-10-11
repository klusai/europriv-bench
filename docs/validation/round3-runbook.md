# Reproducing RES-77 round 3

The [protocol](round3-protocol.md) was committed as `426e09e` before paid inference.
The [model manifest](round3-model-manifest.json) freezes selection and availability evidence.
RO/PL source revision is `79c7a91c47be20c8d214b05b09c2850fe8049037`
([datasets PR #23](https://github.com/klusai/klusai-datasets/pull/23)). No data was published.

Use Python 3.13 with the repo's `dev,panel` dependencies, from this worktree:

```sh
SCRATCH=/Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/res77-r3
PREVIOUS=/Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/res77-r2
SOURCE=/Users/mihai/codespace/rb-gtm-2026-10/estate/scratch/ro-gen-v2/v2-final
# Fresh preparation only: refuses an existing freeze/ledger.
python -m analysis.panel_round3 --scratch "$SCRATCH" --previous "$PREVIOUS" --source "$SOURCE" --stage prepare
# Paid continuation: never reset/delete caches, reservations or exhausted requests.
python -m analysis.panel_round3 --scratch "$SCRATCH" --stage a > "$SCRATCH/stage-a.log" 2>&1
# B requires all valid A judgments; never reinterpret malformed outputs to unlock B.
python -m analysis.panel_round3 --scratch "$SCRATCH" --stage b > "$SCRATCH/stage-b.log" 2>&1
# Offline scoring only (run after the execution process exits):
python -m analysis.panel_round3_report --scratch "$SCRATCH" --out docs/validation
make check
```

This worktree used the existing Python 3.13 environment without modifying it:
`PATH=/Users/mihai/codespace/europriv-bench/.venv/bin:$PATH PYTHONPATH=src`.
Coverage output was directed to scratch with `COVERAGE_FILE=$SCRATCH/.coverage`.
No training, GPUs, new environments, cloud resources, push, PR or HF publication.

`--offline` on A/B replays cache only and refuses missing responses without dispatch.
Replay reconstructs stage files; after an operational stop it reaches the same frozen
stop boundary, without resetting attempt counts or liabilities. The caller holds a
process lock. The new ledger preserves every round-2 entry, including all nine unknown-cost
429 reservations, and reserves every new request before dispatch against the same $25 cap.
`round3-execution.json` separates new round-3 actual cost from cumulative round-2+3 liability.
Round-1 evidence remains unchanged and is accounted separately.

Carried judgments are only the five RO Gemini and five RO Qwen outputs. Their raw
responses reproduce the committed annotations exactly under the unchanged prompts/sample.
Mistral outputs stay in round 2 and do not contribute to round-3 scores. Codex is a
supplemental GPT-family reviewer, not an external seat or an additional independent run.

Raw requests, responses, errors, provider snapshots, immutable source copies, cache,
freeze metadata and overlays remain in scratch for audit/resume. Committed JSON/CSV
files preserve annotations, costs, source hashes, all disagreements and per-type CIs.
Results reports state the actual stop/completion outcome and every gate's disposition.
No gold overlay is applied. Incomplete or failed results cannot promote either config.

## Recorded execution outcome

Both configs remain **dev**. See [RO](ro-realskeleton-v2-round3-report.md) and
[PL](pl-realskeleton-v2-round3-report.md) for all gates and per-type CIs.
All Romanian Stage-A batches were attempted. Seventeen document judgments are
invalid (11 DeepSeek, 1 Gemini, 5 Qwen), retained without reinterpretation or retry.
Polish processing stopped on Qwen batch 34: OpenRouter returned HTTP 400 after
Nebius timed out (504) and DeepInfra/Parasail/Venice/Google routes returned 429.
The final GMICloud backend reported `UnavailableModel` and said its requested model
was deprecated/unavailable. This is endpoint evidence, not a claim that Qwen was
removed from the entire OpenRouter catalogue. DeepSeek's replacement route worked.

The failed request supplied no `usage.cost`; its full $0.032967 reservation remains.
The preregistered non-429 stop rule therefore forbids further paid calls or retrying
this request. No route/model substitution was made after inspecting judgments.
Polish valid A coverage is 170 DeepSeek / 170 Gemini / 165 Qwen documents of 300.
The remaining Polish batches were not dispatched. Stage B refused incomplete A
before dispatch; no gold-error adjudication or repair is claimed.

Round 3 made 280 new attempts: 279 successful API responses (including malformed
judgments) and one unknown-cost HTTP 400. New confirmed cost: $0.85778692.
Cumulative round-2+3 confirmed cost: $0.86720452; reservations: $0.31770000;
conservative total: $1.18490452, below $25. The inherited nine 429 reservations
remain counted. These totals do not establish that rejected requests were free.

Offline Stage-A replay reached the same missing request without network dispatch;
annotations and ledger were byte-identical afterward (`replay-verification.json`).
The frozen round-3 run cannot be completed by resetting this ledger or retrying
malformed outputs. A future continuation needs billing reconciliation plus a
prospective operational addendum for transport; it must preserve these failures,
all valid judgments, unchanged thresholds and the original liabilities. Merely
finishing transport would not remove the observed Romanian agreement failure.
