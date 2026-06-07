# RES-94 — synthetic realism / diversity gap (ours vs Ai4Privacy)  ·  2026-06-07

> **RELATIVE-REALISM / DIVERSITY GAP between TWO SYNTHETIC corpora — NOT a synthetic→real drift number.** Ai4Privacy is *more-realistic SYNTHETIC* (an LLM generator), **not real data**; a real-data drift number still needs TAB / real corpora. Do not read any number here as 'closed the real gap'. dev-tier diagnostic; feeds RES-95.

- ours: `klusai/ds-kp-general-{lang}-50k` (template-splice synthetic, the saturating eval corpus)
- reference: `ai4privacy/open-pii-masking-500k-ai4privacy` (Ai4Privacy LLM synthetic, CC-BY-4.0 open core)
- embedding model: `microsoft/mdeberta-v3-base`  (offline multilingual substitute for multilingual-E5 (E5 not in offline cache); mean-pooled, L2-normalized, CPU-only.)
- bootstrap seed `20260603`, resamples `2000`, 95% percentile CI; per-language sample `1500` docs/side (subsample seed `20260607`)
- intersecting languages scored: `en, it, de, fr, es, nl`
- **uncovered (flagged, honest coverage):** `ro, pl` — no Ai4Privacy counterpart in the cached release; not scored.

## Ranked: how templated/narrow OURS is vs Ai4Privacy (the RES-95 input)

Higher `templated_score` = ours is more templated/narrow relative to Ai4Privacy (unique-skeleton deficit + top-skeleton-share excess + TTR deficit).

| rank | lang | templated score | our unique-skel ratio | ai4p unique-skel ratio | centroid dist | MAUVE-style |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `de` | +1.335 | 0.004 | 0.997 | 0.0332 | 0.006 |
| 2 | `fr` | +1.323 | 0.004 | 0.999 | 0.0376 | 0.005 |
| 3 | `es` | +1.322 | 0.004 | 0.996 | 0.0264 | 0.006 |
| 4 | `en` | +1.308 | 0.004 | 0.992 | 0.0166 | 0.005 |
| 5 | `nl` | +1.307 | 0.004 | 0.995 | 0.0215 | 0.006 |
| 6 | `it` | +1.292 | 0.004 | 0.989 | 0.0293 | 0.007 |

## Per-language realism / diversity gap (with 95% CIs)

| lang | centroid dist | 95% CI | MAUVE-style | TTR ours/ai4p | sent-len var ours/ai4p | template-repetition: unique-ratio ours/ai4p (top-share) |
|---|---:|---|---:|---|---|---|
| `en` | 0.0166 | [0.0156, 0.0181] | 0.005 | 0.1120 / 0.2564 | 107.7 / 40.1 | 0.004 / 0.992 (top 0.181 / 0.006) |
| `it` | 0.0293 | [0.0273, 0.0312] | 0.007 | 0.1051 / 0.2425 | 60.8 / 43.0 | 0.004 / 0.989 (top 0.176 / 0.007) |
| `de` | 0.0332 | [0.0308, 0.0361] | 0.006 | 0.1069 / 0.2628 | 41.7 / 27.0 | 0.004 / 0.997 (top 0.187 / 0.001) |
| `fr` | 0.0376 | [0.0352, 0.0415] | 0.005 | 0.0698 / 0.2252 | 101.4 / 48.5 | 0.004 / 0.999 (top 0.174 / 0.001) |
| `es` | 0.0264 | [0.0249, 0.0278] | 0.006 | 0.0859 / 0.2458 | 75.9 / 41.3 | 0.004 / 0.996 (top 0.172 / 0.002) |
| `nl` | 0.0215 | [0.0205, 0.0229] | 0.006 | 0.1190 / 0.2642 | 51.6 / 30.7 | 0.004 / 0.995 (top 0.172 / 0.002) |

## Template-repetition — the load-bearing 'ours is templated' signal

Document skeletons mask every PII span to its `[LABEL]` placeholder and normalize digits/whitespace, so two docs differing only in spliced identifiers collapse to one skeleton. A template-splice generator yields few distinct skeletons (low unique-ratio, high top-share); an LLM generator yields many.

- `en`: **ours** 6/1500 unique (ratio 0.004, top-share 0.181) vs **Ai4Privacy** 1488/1500 unique (ratio 0.992, top-share 0.006)
- `it`: **ours** 6/1500 unique (ratio 0.004, top-share 0.176) vs **Ai4Privacy** 1484/1500 unique (ratio 0.989, top-share 0.007)
- `de`: **ours** 6/1500 unique (ratio 0.004, top-share 0.187) vs **Ai4Privacy** 1496/1500 unique (ratio 0.997, top-share 0.001)
- `fr`: **ours** 6/1500 unique (ratio 0.004, top-share 0.174) vs **Ai4Privacy** 1499/1500 unique (ratio 0.999, top-share 0.001)
- `es`: **ours** 6/1500 unique (ratio 0.004, top-share 0.172) vs **Ai4Privacy** 1494/1500 unique (ratio 0.996, top-share 0.002)
- `nl`: **ours** 6/1500 unique (ratio 0.004, top-share 0.172) vs **Ai4Privacy** 1493/1500 unique (ratio 0.995, top-share 0.002)

## Honest framing & limitations

- **comparison_kind**: relative-realism-and-diversity gap between TWO SYNTHETIC corpora
- **NOT**: this is NOT a synthetic->real drift number; Ai4Privacy is more-realistic SYNTHETIC, not real. A real-data drift number still requires TAB / real corpora.
- **ours**: ds-kp-general-{lang} — KlusAI template-splice synthetic (the saturating eval corpus)
- **reference**: Ai4Privacy open core — LLM-generated synthetic (CC-BY-4.0), de-saturating baseline
- Ai4Privacy source is the cached open-pii-masking-500k release (same CC-BY-4.0 LLM open core); pii-masking-openpii-1m has only its README cached offline. Labelled, not silent.
- Embedding model is microsoft/mdeberta-v3-base, the offline multilingual substitute for multilingual-E5 (not cached). Absolute embedding distances are encoder-dependent; the language RANKING and the diversity proxies are the robust, encoder-independent signals.
- ro and pl have no Ai4Privacy counterpart in the cached release and are flagged uncovered (honest coverage), not blocked.
- MAUVE-style is a self-contained quantize+divergence-frontier implementation (the pip `mauve` package is unavailable offline); same construction, frozen offline encoder.
- All numbers are computed here from the offline cache; nothing is hardcoded. CPU-only.
