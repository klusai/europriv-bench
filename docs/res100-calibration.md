# RES-100 dev-only operating-point calibration

Registered 2026-10-11 against main `95bdec1`, before this task opens test gold or
runs test inference. Main has seed 0 only and no calibration record.

## Selection rule (frozen before inference)

Each independent MoE training seed 0/1/2 receives ONE global native-span confidence
threshold, shared across every language/config. Transformers simple aggregation,
256-token windows, stride 64, CPU fp32, batch 16, four threads; normalize remaining
BIOES prefixes. Keep an aggregated span iff its mean softmax confidence >= threshold.
Apply the existing exact literal-block operator to all retained native labels,
including labels without a KP mapping. This is post-aggregation filtering, not a
new BIOES decoder. Grid: 0, .50, .60, .70, .80, .85, .90, .95, .97, .98, .99,
.995, .999, .9999, 1.000001 (explicit no-mask fallback).

Minimize the equal-config macro mean of harness residual-leak v2 `all_leak_rate`
subject to candidate point-estimate over-redaction <= EACH of the five frozen
comparators on EVERY dev config. Comparators: pinned base privacy-filter, kp-280m,
TAB-trained 560m seed0, stock Presidio, and separately pinned local CPU Shield.
All comparators keep their existing default operating point; no comparator tuning.
Tie break: lower macro over-redaction, then lower threshold. No test-based grid
extension, threshold change, seed choice or comparator substitution. Missing dev
comparator evidence blocks threshold freeze. The user may narrow the utility
reference before dev inference; any such amendment must be recorded here first.
The dev point constraint is selection only: test acceptance still requires the
paired utility CI upper bound <=0, with no margin or relaxation.

## Data and separation

- Gateway dev: `/Users/mihai/codespace/research-worktrees/res124/artifacts/gateway-traffic-v1/dev.jsonl`,
  manifest `res124/conf/gateway_traffic_manifest.yaml`, revision 4, CC-BY-4.0;
  source URLs/licence/split admission retained from the manifest. 200 conversations
  per language; RO/EN/DE/FR/ES/IT/NL/PL each forms a separate constraint.
- TAB dev: RES-125 `tab-data/dev.jsonl`, 126 curated documents; MIT;
  source https://github.com/NorskRegnesentral/text-anonymization-benchmark at
  `558e09e26d6b36f5f78440074e6a233946d98bd9`. RES-125 tab-manifest.json
  pins curation, licence and dev SHA `267d01bfc90c0814747720840c07f6b54e69738040756fc972c9e164ecfcfa7e`.
- General configs at benchmark revision `58faa4fa572cd8064818a6e1f8ca6e361b959c00`
  expose test only (Hub filename inventory checked without opening gold).
  OpenPII validation is already the scored evaluation partition: it is excluded
  from calibration, not relabelled as independent dev. No new source is added.

Before test access, persist the selected thresholds, full dev grid scores,
ordered-gold hashes, checkpoint/tokenizer hashes, source/runtime pins, exact
operator receipts and this protocol's SHA. Freeze is immutable on resume.
Test: all 20 available original detection configs plus eight gateway language
configs via #54 local loader. Unpublished Italian/legal real-skeleton specs remain
explicitly unavailable. OpenPII retains its actual `validation` split label.

## Reporting and acceptance

Retain separate rows per seed and config; never pool seeds as independent gold.
Use harness scores only: n documents/conversations, n identifier subjects,
DIRECT/QUASI/UNSPECIFIED support, Wilson 95% intervals; paired cluster percentile
95% CIs with 2,000 resamples and RNG seed 100 for leakage and over-redaction.
Report min/max across three seed estimates and all per-seed intervals.
Exact same ordered gold is mandatory for pairing. Existing comparator receipts
may be replayed only with verified gold/operator identity and their original
runtime/truncation provenance; missing coverage must be filled or reported.

All verdicts follow gateway-contract v1: each of three seeds must pass disjoint
Wilson, negative paired leak CI and nonpositive utility CI upper bounds; preserve
RO/PL legacy zero floors. TAB DIRECT is a separately named secondary endpoint.
Gateway-wide acceptance also needs all eight languages, native review and
subject/source/scenario-family/translation disjointness. Synthetic gateway gold
stays dev even for its test partition. Load/SLO, deployment equivalence, semantic
utility, attacker re-identification and reviewed independent gold are unverified.
Historical seed0 rows remain intact; calibrated rows use a distinct model key.
