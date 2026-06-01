# Leaderboard submissions

Drop your filled model card here to submit a public model to the EuroPriv-Bench leaderboard.

1. Copy [`.github/MODEL_CARD_TEMPLATE.yaml`](../.github/MODEL_CARD_TEMPLATE.yaml) to
   `submissions/<org>-<model>.yaml` and fill every field (revision-pinned HF id, an adapter
   scheme from `adapters.BUILDERS`, training-data provenance, contamination statement).
2. Validate locally: `europriv submission validate-card submissions/<org>-<model>.yaml`.
3. Open a PR using the `submission.md` PR template.

You do **not** submit scores. The submission CI ([`.github/workflows/submission.yml`](../.github/workflows/submission.yml))
builds the declared built-in adapter, runs `europriv run` on the public configs in a
**no-secrets sandbox** (public models only — no `HF_TOKEN`), validates your card, and appends a
provenance-stamped schema-3 row (`contamination=unknown` until classified). Private/gated models
needing org secrets are a separate human-gated path (KLU-10). Full protocol: klusai-papers
`SUBMISSIONS.md`.
