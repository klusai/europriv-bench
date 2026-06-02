# EuroPriv-Bench

A **unified, openly-licensed, reproducible benchmark** for privacy-focused NLP across
European languages and the **legal + clinical** domains, under one harmonized GDPR-aligned
taxonomy — with **re-identification-risk / privacy-utility** metrics as the headline, not
just detection-F1.

> Repo + Hugging Face share one slug: `klusai/europriv-bench`.

## Why this exists

The privacy-filter lineage (`openai/privacy-filter` → `OpenMed/privacy-filter-multilingual`
→ the AI4Privacy training substrate) ships **no standardized evaluation**. The broader
field has fragmented benchmarks (TAB, AI4Privacy mini/nano, MultiGraSCCo, MEDDOCAN, MAPA),
but **none unifies** (a) European cross-lingual breadth, (b) *both* legal and clinical,
(c) one harmonized GDPR taxonomy, and (d) re-identification-risk + privacy-utility metrics
in one reproducible, openly-licensed leaderboard. EuroPriv-Bench is that unification —
built *on top of* the prior art (see [`docs/prior-art.md`](docs/prior-art.md)), re-using
their splits and metrics rather than competing with them.

## What it scores

| Task | Status |
|---|---|
| PII/PHI **detection** (entity/token F1, recall-weighted F2) | wired (Phase 1) |
| **Anonymization** / pseudonymization + utility-after-redaction | Phase 4 |
| Document-level **privacy/sensitivity classification** | Phase 4 |
| **Privacy leakage** (membership inference / re-identification risk) | Phase 4 |

Metrics that aren't implemented yet raise `NotImplementedError` (the harness never reports
a fake number).

## Layout

```
src/europriv_bench/   harness core: taxonomy, spans (shared source of truth),
                      spec, metrics, adapters, runner, leaderboard, main (CLI)
evaluations/          versioned YAML eval specs (one per task × lang × domain)
baselines/            committed leaderboard JSON
docs/                 prior-art comparison + harmonized taxonomy crosswalk
tests/                smoke tests (run end-to-end with the dummy adapter)
CONTRIBUTING.md       program-wide repo-layout + namespace conventions
```

This repo is the single source of truth for the harmonized **taxonomy** (`europriv_bench.taxonomy`)
and **span alignment** (`europriv_bench.spans`); `klusai-datasets` and `klusai-models` import
these rather than copying them.

## Usage

```bash
make install                       # editable install + dev deps into .venv
source .venv/bin/activate
europriv list                      # list & validate eval specs
europriv taxonomy                  # print the KP taxonomy + BIOES label space
europriv run --adapter dummy       # run the suite with the all-O baseline
make check                         # tests + ruff
```

Adding a baseline model = subclass `Adapter`, map its native labels onto the KP BIOES space
via the crosswalk in `taxonomy.py`, register it in `adapters.BUILDERS`. Planned baselines:
`openai/privacy-filter`, `OpenMed/privacy-filter-multilingual`, `tabularisai/eu-pii-safeguard`,
GLiNER-PII, MAPA, Presidio, mDeBERTa/XLM-R. (Piiranha-v1 is **CC-BY-NC-ND** → baseline-only,
never a base model or redistributed artifact.)

## Submit your model to the leaderboard

EuroPriv-Bench is an open, neutral scorekeeper: anyone can land a system on the public board
through a **no-secrets** submission CI — fill a model card, open a PR, and the CI scores it on the
held-out gold and appends a provenance-stamped row (you never submit scores). Third-party systems
already on the board via this path: **Microsoft Presidio**, **GLiNER2**, **spaCy**. Full how-to and
worked examples: [`submissions/README.md`](submissions/README.md). Cloud APIs (Azure AI Language,
AWS Comprehend) need credentials → a separate human-gated path, not the self-serve CI.

## License

Code: Apache-2.0. Benchmark data: built only from cleanly-licensed sources so the whole
suite stays openly redistributable — a deliberate edge over license-encumbered competitors.
