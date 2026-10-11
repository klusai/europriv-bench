# RES-100 calibration runtime notes

Before threshold freeze or test access, the shared RES-127 CPU Shield endpoint
on port 11447 timed out on the first TAB-dev batch, then stopped during the retry's
post-inference attestation. The 80 completed TAB-dev receipts from the retry are archived
as diagnostic evidence; they are excluded from calibration and rerun on the dedicated
instance. Failed batches never become scored receipts.

A dedicated local CPU service was started on port 11449 from the existing RES-122
pinned source and environment; its lock, readiness files, logs and reviewed pin
live in the assigned RES-100 calibration scratch. No GPU or paid service is used.
The new process passed readiness and exact service attestation. Threshold 0.8,
DEFAULT replace, source/model identity and language-fallback semantics are retained.
No calibration objective, confidence grid, data split or contract gate changes.
These quality-inference retries do not establish service/load acceptance.

The only calibration-runner edit after initial dev inference began is the Shield
endpoint/pin location. Already running candidate/base/encoder processes retain
the initial source SHA in their receipts; their inference implementation and
settings are unchanged. `inference-source/` and `runtime-provenance.json` in scratch
retain that source. Test receipt identities retain the producing source SHA, and
the report checks candidate dev/test weights, packages and inference settings.

The dedicated CPU Shield configuration pin exactly equals the prior CPU pin
(field-by-field comparison); process instance identity is verified per request.
The owned service was stopped after all 28 Shield test-config receipts were complete.

Test configs are partitioned into two disjoint, alternating config lists per seed
(six CPU inference workers, four threads each). Each config keeps batch 16,
fp32, the frozen threshold and identical window/stride settings; no document is
split across workers. Per-config receipts are atomic and have separate filenames.
This schedules quality inference only and supplies no throughput/latency claim.
The test execution order puts TAB and the RO/PL legacy anchors first, then the
remaining configs in lexical order. All 28 configs remain required for every seed;
this changes scheduling only, after threshold freeze, without result-based selection.
The missing base-model gateway configs likewise use two disjoint CPU workers.
The initial test scheduling was stopped at saved batch boundaries and resumed
under the same receipt identities; neither thresholds nor predictions are replaced.

The eight-worker test phase caused heavy shared-host memory compression (94 GiB
resident/used with roughly 30 GiB compressed, near-zero CPU idle). It was stopped
and resumed from the last atomic batch receipts with one worker per candidate seed
and one base worker. Model/device/dtype/batch/window/stride/threshold and four
threads per worker are unchanged. Partial in-flight batches are recomputed; saved
receipts are neither dropped nor substituted. No other agent's processes were stopped.

The freeze retains complete dev native confidence predictions, their raw local
mask receipts and the harness-scored grid. Final calibrated operator receipt
files are exported by deterministic replay from those same native predictions
and the frozen thresholds, with no new inference or selection. For test rows,
export verifies exact equality of harness residual-v2 scores and every paired
v2/utility cluster count before adding the calibrated receipt SHA to the row.
Raw detector receipts and calibrated mask receipts remain separate in scratch.

The final board check required registering the calibrated adapter name in the
existing RES-100 contamination policy: known RO synthetic overlap remains
`in_distribution`; other configs remain `unknown`. This metadata integration was
made after scoring and changes no inference, coverage, score or contract gate.
