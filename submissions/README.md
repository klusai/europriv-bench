# Leaderboard submissions

Drop your filled model card here to submit a public model to the EuroPriv-Bench leaderboard.

1. Copy [`.github/MODEL_CARD_TEMPLATE.yaml`](../.github/MODEL_CARD_TEMPLATE.yaml) to
   `submissions/<org>-<model>.yaml` and fill every field (version-pinned id, an adapter scheme
   from `adapters.BUILDERS`, training-data provenance, contamination statement).
2. Validate locally: `europriv submission validate-card submissions/<org>-<model>.yaml`.
3. Open a PR using the `submission.md` PR template.

**Worked example — [`microsoft-presidio.yaml`](microsoft-presidio.yaml):** the first third-party
model on the board (Microsoft Presidio, KLU-52), landed via this exact path. Presidio is an
MIT-licensed orchestration *tool* rather than an HF model, so it shows how a non-HF, rule-based
system fills the card: the version-pinned id pins the PyPI release (`org/tool@<version>`) instead
of an HF revision, and `contamination` is `clean_held_out` everywhere (no training data of ours).
The `presidio` adapter wraps `presidio-analyzer`'s `AnalyzerEngine` and maps its entity types onto
the KP taxonomy. Submitting a non-HF tool needs the `presidio` extra in the harness install — the
submission CI already installs it.

You do **not** submit scores. The submission CI ([`.github/workflows/submission.yml`](../.github/workflows/submission.yml))
builds the declared built-in adapter, runs `europriv run` on the public configs in a
**no-secrets sandbox** (public models only — no `HF_TOKEN`), validates your card, and appends a
provenance-stamped schema-3 row (`contamination=unknown` until classified). Private/gated models
needing org secrets are a separate human-gated path (KLU-10). Full protocol: klusai-papers
`SUBMISSIONS.md`.
