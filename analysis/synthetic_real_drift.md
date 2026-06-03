# KLU-103 — synthetic→real drift metric (Paper 2 contribution)

> **dev-tier, not citable.** Feeds Paper 2 (unwritten). Re-id counting is per distinct subject. Model scores are pulled verbatim from the committed leaderboard (no re-scoring); only descriptive corpus stats touch the gold rows. CPU-only — **MMD deferred** (GPU; KLU-106).

- synthetic config: `ro-synthetic-v1`  (content hash `66c2041b8af86b4cf637c6e082df912a6b0bb72cb409df3e59d21beff385589b`)
- real config: `ro-realskeleton-v1`  (content hash `cc9e66dafe19565df06c343f2756dbec6ec6c7bc3a33f0dcec200c7e4a3fe5c6`)
- bootstrap seed: `20260603`, resamples: `10000`, CI: 95% percentile
- label intersection: `ACCOUNT_ID, ADDRESS, COMPANY_ID, DATE, EMAIL, NATIONAL_ID, PERSON, PHONE`

## Headline

**On the re-id (NATIONAL_ID) detection rate, synthetic overstates real-context performance by 13.7 pp on average across 8 models (range -1.9 to +35.4 pp).**

## 1. Primary — per-model like-for-like drift (defensible)

Re-id leak is the primary metric (per distinct CNP subject; label = `NATIONAL_ID`). `detection_rate` gap (↑ better) drives the headline: **+gap ⇒ synthetic overstates real-context performance**. `leak_rate` gap (↓ better) is the dual. CIs are a per-subject Bernoulli bootstrap over the committed subject counts. Entity-F1 is secondary and **aggregate-level only** (see Limitations).

| model | det-rate Δ (syn−real) | 95% CI | leak-rate Δ | 95% CI | entity-F1 Δ (agg) |
|---|---:|---|---:|---|---:|
| `gliner2::fastino/gliner2-base-v1` | +20.5 pp | [+17.4, +23.6] | -20.5 pp | [-23.6, -17.4] | +14.5 pp |
| `gliner::urchade/gliner_multi_pii-v1` | +30.2 pp | [+27.5, +32.9] | -30.2 pp | [-32.9, -27.5] | -4.0 pp |
| `kp-model::klusai/kp-deid-mdeberta-280m` | +0.0 pp | [+0.0, +0.0] | +0.0 pp | [+0.0, +0.0] | +25.9 pp |
| `openmed::OpenMed/privacy-filter-multilingual` | +24.5 pp | [+21.8, +27.2] | -24.5 pp | [-27.2, -21.8] | +16.4 pp |
| `presidio::presidio-analyzer+en_core_web_lg` | +0.0 pp | [+0.0, +0.0] | +0.0 pp | [+0.0, +0.0] | +8.1 pp |
| `privacy-filter::openai/privacy-filter` | +1.3 pp | [+0.6, +2.0] | -1.3 pp | [-2.0, -0.6] | +21.2 pp |
| `spacy::spacy/en_core_web_lg@3.8.0` | -1.9 pp | [-4.4, +0.6] | +1.9 pp | [-0.6, +4.4] | +4.3 pp |
| `tabularisai::tabularisai/eu-pii-safeguard` | +35.4 pp | [+32.5, +38.1] | -35.4 pp | [-38.1, -32.5] | +13.0 pp |

## 2. Label-matched control (confound check)

NATIONAL_ID re-id leak gap after down-sampling both configs to matched per-config subject counts (min of the two). Preserves each config's detection probability; isolates realness from the raw subject-count imbalance.

| model | matched subjects/config | leak-rate Δ (matched) | 95% CI |
|---|---:|---:|---|
| `gliner2::fastino/gliner2-base-v1` | 1017 | -20.6 pp | [-23.8, -17.3] |
| `gliner::urchade/gliner_multi_pii-v1` | 1017 | -30.2 pp | [-33.0, -27.3] |
| `kp-model::klusai/kp-deid-mdeberta-280m` | 1017 | +0.0 pp | [+0.0, +0.0] |
| `openmed::OpenMed/privacy-filter-multilingual` | 1017 | -24.5 pp | [-27.3, -21.6] |
| `presidio::presidio-analyzer+en_core_web_lg` | 1017 | +0.0 pp | [+0.0, +0.0] |
| `privacy-filter::openai/privacy-filter` | 1017 | -1.3 pp | [-2.1, -0.6] |
| `spacy::spacy/en_core_web_lg@3.8.0` | 1017 | +1.9 pp | [-0.7, +4.4] |
| `tabularisai::tabularisai/eu-pii-safeguard` | 1017 | -35.4 pp | [-38.4, -32.4] |

## 3. Descriptive corpus shift — **corpus-composition, not model drift**

> These describe how the two *corpora* differ. They are **NOT** a model-drift signal and must never be read as one.

- **Label-distribution shift** — TV distance `0.1439`, Jensen-Shannon distance `0.2940`  (TV + Jensen-Shannon distance (bounded, symmetric); raw KL deliberately avoided.)
- **Length shift** — Wasserstein-1 `46.44` whitespace tokens (synthetic mean 18.8 vs real 65.2 tokens; Earth-Mover's Distance (Wasserstein-1) over document token counts.)

## Limitations (recorded for honesty)

- entity_f1 gap is reported at the aggregate level only: the committed leaderboard stores a single corpus-level precision/recall/f1 per (model, config), with no per-document or per-label breakdown, so neither a per-label restriction nor a per-document bootstrap CI is recoverable for entity_f1 from committed artifacts.
- re-id-leak gap CI is a per-distinct-subject Bernoulli bootstrap reconstructed from the committed aggregate subject counts (cnp_detected / cnp_total) for BOTH configs; the leaderboard does not commit per-subject flags for ro-synthetic-v1, so the resample is over the binomial implied by those counts rather than over joined per-document records.
- re-id leak is a single-label (NATIONAL_ID/CNP) signal, so the 'per-label' restriction for the primary leak metric is the NATIONAL_ID label itself; the label intersection drives the entity-F1 reading and the descriptive label-distribution metric.
- MMD / embedding-distribution distance is deferred (needs a GPU encoder; KLU-106 owns the GPU). This artifact is CPU-only.

## Deferred

- **MMD / embedding-distribution distance** — deferred (needs a frozen GPU encoder over length-matched buckets; KLU-106 owns the GPU). Optional future addition; this artifact is CPU-only.
