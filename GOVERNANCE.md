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

## `config_status` policy (forthcoming)

To distinguish exploratory configs from those safe to cite, each eval config will carry a
`config_status`:

- **`dev`** — default. Usable for development and iteration. Numbers from `dev` configs MUST
  NOT be cited as validated benchmark results.
- **`citable-validated`** — promotable ONLY after native-speaker review and inter-annotator
  agreement (IAA) sign-off on the underlying gold data. A config cannot be marked
  `citable-validated` without recorded native-speaker/IAA validation.

This field is implemented in KLU-8's schema-3 work (eval-spec schema version 3); this section
defines the policy the schema enforces. Until then, treat all configs as `dev` for citation
purposes.

## CHANGELOG

### Unreleased
- **Governance:** externalized the taxonomy crosswalk from a hardcoded Python list into
  `conf/taxonomy.yaml` (single source of truth), loaded at import with a `version` ↔
  `TAXONOMY_VERSION` sync check that fails loud on mismatch. Behavior-preserving: the loaded
  entity set, crosswalk, and BIOES label space are unchanged. Added `GOVERNANCE.md` and a
  contract test (`tests/test_taxonomy_contract.py`). (KLU-9)

### 0.2.0
- Added `NATIONAL_ID` and `COMPANY_ID` entity types; national IDs split out of `ACCOUNT_ID`.
