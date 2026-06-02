# Governance

EuroPriv-Bench aims to be the neutral yardstick the field is ranked on. That only works if
numbers are *comparable* and the taxonomy is *stable and auditable*. This document defines the
governance contract: what is immutable, when scores may be compared, what guarantees the
harness makes, and how the taxonomy and configs evolve.

## Immutable config names

The following names are part of the public contract. Once published they MUST NOT be renamed,
repurposed, or have their meaning changed under the same version — doing so silently breaks
every downstream dataset, model label map, and leaderboard that references them.

- **`conf/taxonomy.yaml`** — the single source of truth for the harmonized KP taxonomy, the
  crosswalk to external schemes, and the BIOES label space. Loaded once at import by
  `src/europriv_bench/taxonomy.py`. It carries a `version` field that MUST equal
  `TAXONOMY_VERSION`; on mismatch import fails loud (`ValueError`). Never edit the entity set,
  entity order, or label space without bumping `version` (see below).
- **`TAXONOMY_VERSION`** (in `src/europriv_bench/taxonomy.py`) — the in-code anchor for the
  taxonomy version. Stamped into every eval spec result and the leaderboard.
- **KP entity-type names** (e.g. `PERSON`, `NATIONAL_ID`, `HEALTH_CONDITION`) and the derived
  **BIOES labels** (`O`, `B-/I-/E-/S-<TYPE>`). The entity *order* in `conf/taxonomy.yaml`
  defines the label order; reordering changes the label space and requires a version bump.
- **Crosswalk source scheme keys** (`openai`, `ai4privacy`, `hipaa`, `mapa`, `openmed`,
  `azure`, `tabularisai`). Datasets and adapters key off these.
- **Metric keys** in `src/europriv_bench/metrics.py` (e.g. `entity_f1`, `entity_f2`,
  `cnp_leakage`) and **eval-spec names** under `evaluations/`.

## Version-comparability rules

A benchmark number is only meaningful relative to the versions that produced it. Therefore:

- **Scores are comparable ONLY when they share the same `TAXONOMY_VERSION` *and* the same
  harness version** (`europriv_bench.__version__`, recorded as `europriv_bench_version` in
  every result row alongside `taxonomy_version`).
- Do **not** compare leaderboard entries across a taxonomy bump or a harness bump. A bump can
  change the label space, the crosswalk, or the metric implementation — any of which moves the
  numbers for reasons unrelated to model quality.
- Every result row carries its provenance (`taxonomy_version`, `europriv_bench_version`,
  dataset config/split, dataset revision). Reproductions MUST match on all of these.
- **Version bump policy:** bump `TAXONOMY_VERSION` (and the `version` in `conf/taxonomy.yaml`,
  together) on any change to the entity set, entity order, GDPR-Art.9 marking, or the BIOES
  label space. Crosswalk-only additions that do not change the KP label space still warrant a
  patch bump so coverage numbers remain attributable.

## Metric-stability contract

- Metric **keys** and their **semantics** are stable within a harness version. A given key
  always computes the same quantity the same way; changing the computation requires a harness
  version bump (and breaks cross-version comparability, see above).
- Metrics are **deterministic**: identical inputs (gold + predictions, same label space)
  produce identical outputs.
- The BIOES label space scored against is exactly `bioes_labels()`, derived from
  `conf/taxonomy.yaml`. Gold curation and model adapters share this one space via the
  crosswalk, so detection scores are apples-to-apples.
- Confidence intervals and any statistical reporting are part of the metric contract: their
  method is fixed within a harness version.

## `config_status` policy

To distinguish exploratory configs from those safe to cite, each leaderboard row carries a
per-`(model, config)` `config_status`:

- **`dev`** — default. Usable for development and iteration. Numbers from `dev` configs MUST
  NOT be cited as validated benchmark results.
- **`citable-validated`** — promotable ONLY after native-speaker review and inter-annotator
  agreement (IAA) sign-off on the underlying gold data. A config cannot be marked
  `citable-validated` without recorded native-speaker/IAA validation.

This field is implemented in the schema-3 leaderboard (KLU-8). **Everything currently defaults to
`dev`**: no config is `citable-validated` until the native-speaker / IAA sign-off lands — that
gate is tracked in **KLU-27**. Until a row is explicitly promoted there, treat all configs as
`dev` for citation purposes. The promotion is a curated, recorded change to the row's
`config_status`; re-aggregating the leaderboard never silently flips it back (`annotate_row`
preserves any value already present).

## `contamination` policy

Detection F1 on data a model was trained on is not a fair held-out measurement. Each schema-3
leaderboard row carries a per-`(model, config)` `contamination` marker so consumers can tell
overlapping rows from genuinely held-out ones:

- **`in_distribution`** — the model was trained on the eval config's source data, so the score
  is inflated by train/eval overlap. OpenMed and tabularisai were trained on **AI4Privacy**, the
  source of the six general-text configs (`en`/`de`/`fr`/`it`/`es`/`nl`), so those rows are
  `in_distribution`.
- **`clean_held_out`** — no baseline on the board was trained on this data. The RO real-skeleton
  track (`ro-realskeleton-v1`) is `clean_held_out` for every model.
- **`unknown`** — overlap not established (e.g. a baseline whose training set we don't know, or
  the synthetic RO track).

Rule-based / orchestration baselines (e.g. **Presidio**) learn from none of our data — regex +
checksum recognizers plus an off-the-shelf NER — so every config is `clean_held_out` for them,
including the AI4Privacy general configs the trained baselines overlap with.

The marker is derived from `(adapter, dataset.config)` by `leaderboard.classify_contamination`.

## CHANGELOG

### Unreleased
- **First third-party leaderboard submission via the no-secrets CI (KLU-52):** added the
  `presidio` adapter wrapping Microsoft Presidio (`presidio-analyzer`, MIT) — the first external
  baseline on the board, landed through the submission CI. Presidio is an orchestration *tool*
  (regex/checksum recognizers + a spaCy NER), not an HF model, so the adapter wraps the
  `AnalyzerEngine` and maps Presidio's entity types onto the KP taxonomy (no native crosswalk
  scheme). Marked `clean_held_out` on every config (rule-based; no training data of ours). Worked
  example: `submissions/microsoft-presidio.yaml`. Minimal submission-path fixes so an external,
  non-HF adapter can actually land: model-card id accepts a version-pinned non-HF tool reference
  (`org/tool@<version>`); the serial `europriv run` path now skips a spec whose dataset config is
  not on the public HF revision (with a warning) instead of crashing the whole run — keeping the
  no-secrets CI green; CI installs the `presidio` extra + the spaCy model when a presidio card is
  present; and the `Makefile` reproduction-gate recipe no longer hard-`source`s a `.venv` (the CI
  runner installs into system Python with no venv, so the old `source .venv/bin/activate` died with
  `source: not found` and made the submission gate un-passable — now it activates `.venv` only when
  present and otherwise uses the python on PATH). Scored on the 8 public configs (the
  `pl-realskeleton-v1` track is not yet published to the public HF dataset, so it is skipped).
- **Leaderboard schema 3 (KLU-8):** added two per-`(model, config)` governance markers —
  `contamination` (`in_distribution` | `clean_held_out` | `unknown`) and `config_status`
  (`dev` | `citable-validated`, defaulting to `dev`). `runner.run_spec` now emits both on every
  run; `leaderboard.build_leaderboard` backfills them on aggregation (idempotent — preserves any
  curated value). Migrated `baselines/leaderboard.json` and `baselines/leaderboard-full.json` to
  schema 3 (OpenMed/tabularisai general-text rows marked `in_distribution`, RO real-skeleton rows
  `clean_held_out`, all configs `dev`) and backfilled the KLU-6 Wilson CIs into
  `leaderboard-full.json` so both baseline files are consistent. Additive only; the merged Wilson
  CI fields are preserved. No config is citable-validated until the KLU-27 native-speaker/IAA
  sign-off.
- **Governance:** externalized the taxonomy crosswalk from a hardcoded Python list into
  `conf/taxonomy.yaml` (single source of truth), loaded at import with a `version` ↔
  `TAXONOMY_VERSION` sync check that fails loud on mismatch. Behavior-preserving: the loaded
  entity set, crosswalk, and BIOES label space are unchanged. Added `GOVERNANCE.md` and a
  contract test (`tests/test_taxonomy_contract.py`). (KLU-9)

### 0.2.0
- Added `NATIONAL_ID` and `COMPANY_ID` entity types; national IDs split out of `ACCOUNT_ID`.
