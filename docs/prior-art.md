# Prior-art comparison & kill/pivot check (Phase 0)

**Purpose:** before investing in EuroPriv-Bench, confirm the unmet intersection it claims
still exists. This is the plan's **kill/pivot gate**: *if a single existing artifact already
covers European-cross-lingual + legal&clinical + privacy-utility + a harmonized GDPR
taxonomy in one open, reproducible leaderboard, the benchmark-as-flagship is dead — pivot
weight to the under-served-language SOTA pillar instead.*

_Last refreshed: 2026-05-30. Re-run immediately before publishing (fast-moving field)._

## The intersection we require (all five at once)

(a) **European cross-lingual** breadth · (b) **both legal AND clinical** · (c) **one
harmonized GDPR-aligned taxonomy** · (d) **re-identification-risk / privacy-utility**
metrics (not just detection-F1) · (e) **one reproducible, openly-licensed, leaderboard**.

## Comparison

| Artifact | (a) Euro x-lingual | (b) legal & clinical | (c) harmonized GDPR taxonomy | (d) re-id / utility metric | (e) open leaderboard | License |
|---|---|---|---|---|---|---|
| **TAB** (Pilán et al. 2022) | ✗ (EN only) | legal only (ECHR) | partial (direct/quasi) | ✅ privacy + utility | partial (corpus, no live LB) | open (GitHub) |
| **AI4Privacy mini-10k / nano-1k** | ✅ ~25 EU + others | ✗ (general) | ✗ (PII labels) | ✗ (detection-F1) | ✗ | CC-BY-4.0 |
| **MultiGraSCCo** (2026) | partial (~10, MT-projected) | clinical only | partial (PHI + indirect) | partial (identifier-level) | ✗ | open |
| **MEDDOCAN** (2019) | ✗ (ES only) | clinical only | GDPR-derived (ES) | ✗ (detection) | task (closed) | open (synthetic) |
| **MAPA** | ✅ 24 EU | ✅ legal + clinical | GDPR-derived | ✗ (detection) | ✗ (toolkit/data) | EU-funded OSS |
| **MedPriv-Bench / ASQ-PHI** (2026) | ✗ (EN clinical) | clinical only | clinical | ✅ re-id / utility | ✗ | research |
| **PII-Bench / RAT-Bench** (2025–26) | partial | ✗ | ✗ | partial | ✗ | research |
| **privbench / privacy-arena-data** | unknown (gated) | unknown | unknown | unknown | unknown | gated, no card |
| **EuroPriv-Bench (this)** | ✅ 20 langs | ✅ both | ✅ harmonized crosswalk | ✅ headline metric | ✅ live leaderboard | open only |

## Verdict — PROCEED (gate not triggered)

No single existing artifact covers all of (a)–(e):

- **MAPA** is the closest on coverage (24 EU langs, legal + clinical, GDPR) but is a
  **detection toolkit/dataset, not a privacy-utility benchmark with a leaderboard** — misses (d), (e).
- **TAB** owns the privacy-utility metric framework (d) but is **English, legal-only** — misses (a), (b).
- **MultiGraSCCo** is multilingual + GDPR-aware but **clinical-only, MT-projected, no leaderboard** — misses (b), (d/e).
- **AI4Privacy** splits are cross-lingual European but **detection-only, general-domain** — misses (b), (c), (d).

The unmet intersection is real and narrow. **EuroPriv-Bench's defensible claim is "first to
*unify*," not "first."** We explicitly **subsume** TAB / MEDDOCAN / MAPA / AI4Privacy splits
(re-using their metrics where applicable) so we build on the field rather than ignore it.

## Watch items

- **`privbench/privacy-arena-data`** (HF, 532 GB, gated, ~97 dl/mo, no card) — confirmed to
  exist but opaque. Cannot inspect without agreeing to access terms. **Could** become a
  competing leaderboard; revisit before publication.
- Several relevant artifacts (MultiGraSCCo, MedPriv-Bench, ASQ-PHI, Azure synthetic-replacement)
  are dated 2026 — re-run this scan at submission time so "first unified" still holds.

## Licensing notes that constrain reuse

- **Piiranha-v1 = CC-BY-NC-ND-4.0** (verified live): evaluation baseline only — never a
  finetuning base or a redistributed artifact.
- **AI4Privacy**: license verified live (RES-93, 2026-06-07). `ai4privacy/pii-masking-openpii-1m`
  is the verified-clean **open core** — card body states "License: CC-BY-4.0. Copyright © 2026 Ai
  Suisse SA … research, commercial use, redistribution, and modification," no Llama clause. This is
  the source the benchmark uses. The larger `open-pii-masking-500k-ai4privacy` tier is **Llama-
  Community-License-bound** (card: "created using Llama models (versions 3.1 and 3.3) … subject to
  the Llama Community License Agreement"; "Built with Llama") — **excluded**, despite a cosmetic
  `license_name: cc-by-4.0` in its YAML. The `pii-masking-300k`/`-200k` tiers carry a custom
  company-size-tiered `license.md` — also **excluded**. See `docs/crosswalk-ai4privacy.md` and the
  `klusai-datasets` manifest `conf/ai4privacy_openpii_manifest.yaml`.
- Build EuroPriv-Bench only from cleanly-licensed sources (TAB/ECHR, CC-BY AI4Privacy splits,
  MEDDOCAN, EUR-Lex, KlusAI synthetic) to keep the whole suite openly redistributable.
