<!--
EuroPriv-Bench leaderboard submission.

Use this template to add a MODEL to the public leaderboard. Open your PR with
`?template=submission.md` appended to the compare URL to select it.

Protocol: klusai-papers SUBMISSIONS.md. You submit a model + adapter scheme + filled model
card — NOT scores. The submission CI builds the declared built-in adapter, runs `europriv run`
on the PUBLIC configs in a no-secrets sandbox, validates your card, and appends a
provenance-stamped schema-3 row (contamination=unknown until classified). See
.github/MODEL_CARD_TEMPLATE.yaml.
-->

## Submission

- **Hugging Face model id (revision-pinned, `org/model@<sha>`):**
- **Adapter scheme** (one of `adapters.BUILDERS`: `privacy-filter` / `openmed` / `tabularisai` / `gliner` / `kp-model`):
- **Model card file** (path to your filled copy of `MODEL_CARD_TEMPLATE.yaml`, e.g. `submissions/<org>-<model>.yaml`):

## Checklist

- [ ] The model is **public** on Hugging Face and the id pins a **revision/commit**, not a moving tag.
- [ ] The adapter scheme is one of the built-in `adapters.BUILDERS` (no custom adapter code in this PR).
- [ ] A filled model card is included and passes `europriv submission validate-card <card>`.
- [ ] The contamination statement describes any overlap with the held-out gold splits.
- [ ] I am **not** self-reporting scores — CI produces the leaderboard row.

<!--
Note: CI runs the public-config path with NO repository secrets and no HF_TOKEN (public models
only). Org-secret-backed runs (private/gated models) are a separate human-gated path — KLU-10.
-->
