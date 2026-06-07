# RES-94 — synthetic realism / diversity gap (ours vs Ai4Privacy)  ·  2026-06-07

> **RELATIVE-REALISM / DIVERSITY GAP between TWO SYNTHETIC corpora — NOT a synthetic→real drift number.** Ai4Privacy is *more-realistic SYNTHETIC* (an LLM generator), **not real data**; a real-data drift number still needs TAB / real corpora. Do not read any number here as 'closed the real gap'. dev-tier diagnostic; feeds RES-95.

- ours: `klusai/ds-kp-general-{lang}-50k` (template-splice synthetic, the saturating eval corpus)
- reference: `ai4privacy/pii-masking-openpii-1m` (CC-BY-4.0) — Ai4Privacy LLM synthetic, verified-clean open core (RES-93); the Llama-Community-licensed 500k tier is excluded and NOT used
- embedding model: `microsoft/mdeberta-v3-base`  (offline multilingual substitute for multilingual-E5 (E5 not in offline cache); mean-pooled, L2-normalized, CPU-only.)
- bootstrap seed `20260603`, resamples `2000`, 95% percentile CI; per-language sample `1500` docs/side (subsample seed `20260607`)
- intersecting languages scored: `ro, en, pl, it, de, fr, es, nl`

## Ranked: how templated/narrow OURS is vs Ai4Privacy (the RES-95 input)

Higher `templated_score` = ours is more templated/narrow relative to Ai4Privacy (unique-skeleton deficit + top-skeleton-share excess + TTR deficit).

| rank | lang | templated score | our unique-skel ratio | ai4p unique-skel ratio | centroid dist | MAUVE-style |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `pl` | +1.308 | 0.004 | 1.000 | 0.0234 | 0.005 |
| 2 | `de` | +1.282 | 0.004 | 1.000 | 0.0366 | 0.004 |
| 3 | `ro` | +1.260 | 0.004 | 1.000 | 0.0469 | 0.005 |
| 4 | `fr` | +1.260 | 0.004 | 1.000 | 0.0396 | 0.004 |
| 5 | `nl` | +1.248 | 0.004 | 1.000 | 0.0259 | 0.004 |
| 6 | `es` | +1.245 | 0.004 | 1.000 | 0.0347 | 0.004 |
| 7 | `it` | +1.239 | 0.004 | 1.000 | 0.0342 | 0.004 |
| 8 | `en` | +1.229 | 0.004 | 1.000 | 0.0278 | 0.005 |

## Per-language realism / diversity gap (with 95% CIs)

| lang | centroid dist | 95% CI | MAUVE-style | TTR ours/ai4p | sent-len var ours/ai4p | template-repetition: unique-ratio ours/ai4p (top-share) |
|---|---:|---|---:|---|---|---|
| `ro` | 0.0469 | [0.0439, 0.0493] | 0.005 | 0.0863 / 0.1778 | 25.6 / 109.0 | 0.004 / 1.000 (top 0.173 / 0.001) |
| `en` | 0.0278 | [0.0264, 0.0293] | 0.005 | 0.1120 / 0.1645 | 107.7 / 102.7 | 0.004 / 1.000 (top 0.181 / 0.001) |
| `pl` | 0.0234 | [0.0220, 0.0244] | 0.005 | 0.0849 / 0.2211 | 19.9 / 90.2 | 0.004 / 1.000 (top 0.176 / 0.001) |
| `it` | 0.0342 | [0.0332, 0.0361] | 0.004 | 0.1051 / 0.1731 | 60.8 / 117.1 | 0.004 / 1.000 (top 0.176 / 0.001) |
| `de` | 0.0366 | [0.0342, 0.0386] | 0.004 | 0.1069 / 0.2073 | 41.7 / 78.4 | 0.004 / 1.000 (top 0.187 / 0.001) |
| `fr` | 0.0396 | [0.0366, 0.0420] | 0.004 | 0.0698 / 0.1602 | 101.4 / 115.5 | 0.004 / 1.000 (top 0.174 / 0.001) |
| `es` | 0.0347 | [0.0332, 0.0366] | 0.004 | 0.0859 / 0.1641 | 75.9 / 129.0 | 0.004 / 1.000 (top 0.172 / 0.001) |
| `nl` | 0.0259 | [0.0249, 0.0273] | 0.004 | 0.1190 / 0.1995 | 51.6 / 97.8 | 0.004 / 1.000 (top 0.172 / 0.001) |

## Template-repetition — the load-bearing 'ours is templated' signal

Document skeletons mask every PII span to its `[LABEL]` placeholder and normalize digits/whitespace, so two docs differing only in spliced identifiers collapse to one skeleton. A template-splice generator yields few distinct skeletons (low unique-ratio, high top-share); an LLM generator yields many.

- `ro`: **ours** 6/1500 unique (ratio 0.004, top-share 0.173) vs **Ai4Privacy** 1500/1500 unique (ratio 1.000, top-share 0.001)
- `en`: **ours** 6/1500 unique (ratio 0.004, top-share 0.181) vs **Ai4Privacy** 1500/1500 unique (ratio 1.000, top-share 0.001)
- `pl`: **ours** 6/1500 unique (ratio 0.004, top-share 0.176) vs **Ai4Privacy** 1500/1500 unique (ratio 1.000, top-share 0.001)
- `it`: **ours** 6/1500 unique (ratio 0.004, top-share 0.176) vs **Ai4Privacy** 1500/1500 unique (ratio 1.000, top-share 0.001)
- `de`: **ours** 6/1500 unique (ratio 0.004, top-share 0.187) vs **Ai4Privacy** 1500/1500 unique (ratio 1.000, top-share 0.001)
- `fr`: **ours** 6/1500 unique (ratio 0.004, top-share 0.174) vs **Ai4Privacy** 1500/1500 unique (ratio 1.000, top-share 0.001)
- `es`: **ours** 6/1500 unique (ratio 0.004, top-share 0.172) vs **Ai4Privacy** 1500/1500 unique (ratio 1.000, top-share 0.001)
- `nl`: **ours** 6/1500 unique (ratio 0.004, top-share 0.172) vs **Ai4Privacy** 1500/1500 unique (ratio 1.000, top-share 0.001)

## Honest framing & limitations

- **comparison_kind**: relative-realism-and-diversity gap between TWO SYNTHETIC corpora
- **NOT**: this is NOT a synthetic->real drift number; Ai4Privacy is more-realistic SYNTHETIC, not real. A real-data drift number still requires TAB / real corpora.
- **ours**: ds-kp-general-{lang} — KlusAI template-splice synthetic (the saturating eval corpus)
- **reference**: ai4privacy/pii-masking-openpii-1m — LLM-generated synthetic, verified-clean CC-BY-4.0 open core (RES-93); de-saturating baseline
- Ai4Privacy source is ai4privacy/pii-masking-openpii-1m (CC-BY-4.0) — the verified-clean open core (RES-93). The Llama-Community-licensed 500k tier is excluded by the license gate and is never used. The 1m dataset is streamed over network row-by-row (only its README is cached); the stream stops once each target language has sample docs.
- Embedding model is microsoft/mdeberta-v3-base, the offline multilingual substitute for multilingual-E5 (not cached). Absolute embedding distances are encoder-dependent; the language RANKING and the diversity proxies are the robust, encoder-independent signals.
- All eight of our languages (incl. ro and pl) have an openpii-1m counterpart and are scored — the prior ro/pl coverage gap is closed.
- MAUVE-style is a self-contained quantize+divergence-frontier implementation (the pip `mauve` package is unavailable offline); same construction, frozen offline encoder.
- All numbers are computed here at run time; nothing is hardcoded. CPU-only.
