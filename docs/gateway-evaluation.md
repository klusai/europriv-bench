# Gateway full-PII dev evaluation — RES-126

Registered before model scoring: eight specs for `gateway-traffic-v1`, primary
endpoint `all_leak_rate`, all DIRECT/QUASI/UNSPECIFIED slices, worst language,
95% Wilson subject intervals and paired conversation-cluster percentile bootstrap
(candidate minus each comparator, 2,000 resamples, RNG seed 126). One conversation
is one cluster, including negatives. Identifier subjects are not unique people.
Translations can share families across languages; pooled inference is descriptive,
and language-specific comparisons are mandatory. No checkpoint selection on test.

Load unpublished data with `EUROPRIV_GATEWAY_PATH=/path/to/artifacts/gateway-traffic-v1`
and `EUROPRIV_GATEWAY_MANIFEST=/path/to/conf/gateway_traffic_manifest.yaml`.
The same values can be supplied as `dataset.local_path` and `dataset.manifest_path`.
After publication remove overrides and pin `dataset.revision`, `dataset.files`
(JSONL or single parquet) and Hub `manifest_path`; download with `hf_hub_download`
and read parquet with pyarrow. No streaming. Record both file SHA-256 values.
No data is copied into this repository. Sources must have explicit licence, URL,
train/redistribution rights and split admission. Synthetic data stays `dev`.

The coordinate policy is message order, then part order, with one newline between
text parts. Roles are metadata. Gold and field offsets are translated into this
space, preserving entity IDs across turns. `retain` spans are utility negatives.
Unknown part types, invalid spans, split mismatches and duplicate IDs fail closed.
Native review and family/subject/translation disjointness remain dataset gates.

KP and stock Presidio use an explicit local `delete-exact-union-v1` operator.
It deletes every raw detector interval without gold-label filtering or whitespace
token expansion, and saves input/output hashes with intervals. KP uses the simple
aggregation pipeline with 512-token fast-tokenizer overflow windows (stride 64), screening
the entire conversation. Presidio retains the stock English engine, threshold 0,
and existing entity inventory. Shield remains its separately pinned exact HTTP
replace-policy operator, including native types outside the KP mapping.
These operators are distinct from production KP gateway integration.

`gateway_utility` is the fraction of gold non-PII non-whitespace characters removed
and its complement (character retention), not semantic task utility. Empty support
is unavailable. This historical registration retains the paired utility delta upper
bound <=0. New post-registration evaluations may explicitly select [contract v3](gateway-contract.md)
with `--contract-version 3` before scoring and comparison; its upper-bound margin is +0.01.
Earlier evaluations and verdicts remain unchanged.
No-mask and full-mask controls verify metric extremes. Shuffled-label coverage
must be invariant (v2 is intentionally label-independent); shuffled gold positions
provide a separate destructive alignment control. Masked-input inference replaces
protected non-whitespace characters with spaces at identical offsets, retains the
original gold only as a diagnostic target, and reports residual overlap. It is not
a second estimate of real-input privacy or a guaranteed zero prediction rate.

TAB, RO and PL legacy specifications and existing leaderboard rows remain frozen.
Their historical results do not establish a residual-v2 anchor pass for a new
operator. Every contract line receives an explicit verdict; absent three independent
training seeds, reviewed gold or current anchor checks means not established.
Latency/load and semantic utility are outside this quality run.

Run `PYTHONPATH=src python analysis/score_gateway.py --help` for resumable local
scoring. Prediction receipts and logs belong in the assigned scratch directory.

The scored data snapshot has 1,000 conversations, 2,118 declared fictional person
subjects and 4,506 metric identifier subjects per language. These denominators
are different: one person may have several independently protected identifiers.
Each language has 1,000 distinct source-document IDs. The annotation guide SHA-256
is `e71e2da9a35bd8fe03effb9a54d088bb45226dee4d687b1ec4b1232828b1e0dc`.

Model registrations use seed 0: `kp-deid-mdeberta-280m`,
`res72-cjeu-tab-seed0` (560M legal) and `res104-tab-seed0` (TAB-trained 560M).
The latter's merged weights hash was checked against the RES-104 training receipt.
Stock Presidio and the separately pinned Shield service each have one inference run.
Per-row `run_pin` hashes source/runtime/model identity; full weight manifests,
operator receipts and the exact producing source snapshots remain in scratch.
`cluster_intervals.delta` is an absolute rate computed against an all-zero reference;
`gateway-comparisons.json` contains the actual paired candidate-minus-comparator deltas.

After all engines complete, run `analysis/score_gateway.py --scratch ... --compare`,
then `analysis/splice_gateway.py --scratch ...` to generate the result report and
splice the complete 5×8 matrix. Splicing rejects incomplete runs or differing gold
hashes, forces `dev`, and preserves every historical row. Full corruption results
are retained in `baselines/gateway-controls.json`. None of these commands publishes.

Shield's `service_provenance.resolved_accelerator` is the authoritative service
device (local MPS for this run). Its `run_pin.device` records the CPU HTTP client's
local environment setting; it is not a CPU inference or latency claim. The partial
CPU probe remains separate in scratch and is excluded from every scored row.
