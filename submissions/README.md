# Call for submissions — put your model on the EuroPriv-Bench leaderboard

EuroPriv-Bench is an **open, neutral scorekeeper**: anyone can land a system on the public board
through a **no-secrets** CI that scores it on the held-out gold and stamps a provenance row. You do
**not** submit scores — the CI computes them. KlusAI's own `kp-*` models are ranked on the *same*
board under the *same* rules.

The headline metric is **re-identification risk** (how many decode-bearing national IDs leak),
not just detection-F1 — and most off-the-shelf systems were never tuned for it. That is exactly
the picture this board makes legible.

## How to submit (self-serve, ~5 minutes of editing)

1. **Pick the adapter** that calls your system. It MUST be one of the built-in schemes in
   `adapters.BUILDERS` — no submitter code runs in CI, only a declared built-in is instantiated:

   | scheme | wraps |
   |---|---|
   | `privacy-filter` / `openmed` / `tabularisai` | HF token-classification PII models |
   | `gliner` | GLiNER zero-shot NER (`urchade/gliner_multi_pii-v1`) |
   | `gliner2` | GLiNER2 schema-based IE (`fastino/gliner2-base-v1`) |
   | `spacy` | spaCy statistical NER (`en_core_web_lg`) |
   | `presidio` | Presidio orchestration (regex/checksum + spaCy NER) |
   | `kp-model` | KlusAI `kp-*` finetunes |

   If your system isn't covered, open an issue first — a new adapter (≈30 lines: map your native
   entity types onto the KP taxonomy, register in `BUILDERS`) lands as a separate PR. The
   `gliner2` and `spacy` adapters (KLU-108) are the most recent worked examples of that.

2. **Copy** [`.github/MODEL_CARD_TEMPLATE.yaml`](../.github/MODEL_CARD_TEMPLATE.yaml) to
   `submissions/<org>-<model>.yaml` and fill **every** field:
   - `hf_model_id` — a **version-pinned** reference. HF model → `org/model@<commit-sha>`;
     a non-HF tool/package (Presidio, a spaCy model) → `org/tool@<release-version>`. The `@`
     pins an immutable version so the row stamps exactly what produced the score.
   - `adapter` — one of the schemes above.
   - `training_data` — provenance **and licensing** (we only accept cleanly-licensed deps).
   - `contamination_statement` — does your training data overlap our held-out gold? Say what you
     know. External rule-based / off-the-shelf systems with no overlap are `clean_held_out`.

3. **Validate locally:** `europriv submission validate-card submissions/<org>-<model>.yaml`.

4. **Open a PR** using the [`submission.md`](../.github/PULL_REQUEST_TEMPLATE/submission.md) PR
   template. The submission CI takes it from there.

## What the CI does (no-secrets sandbox)

The submission CI ([`.github/workflows/submission.yml`](../.github/workflows/submission.yml)) runs
on `pull_request` against the PR's own checkout, with a **read-only token and no access to repo/org
secrets** — so untrusted adapter code can never exfiltrate them. It installs the public adapter
backends, validates your card, runs the **reproduction gate** (the committed privacy-filter EN
anchor, 0.415 ±0.02, must still hold), instantiates your declared built-in adapter, runs
`europriv run` on the **public** configs (public models only — pulled anonymously, no `HF_TOKEN`),
and appends a provenance-stamped schema-3 row.

External rows are recorded `contamination=unknown` until classified; rule-based / off-the-shelf
systems trained on none of our gold are `clean_held_out` (see
[`../GOVERNANCE.md`](../GOVERNANCE.md) and `leaderboard.classify_contamination`). Private/gated
models that need org secrets are a **separate, human-gated** path (KLU-10) — intentionally not
wired here. Full protocol: klusai-papers `SUBMISSIONS.md`.

## Worked examples (copy one)

Three real third-party systems are already on the board via this exact path — each filled card is a
template you can copy:

- **[`microsoft-presidio.yaml`](microsoft-presidio.yaml)** (KLU-52) — the first third-party
  submission. Presidio is an MIT-licensed orchestration **tool**, not an HF model, so it shows the
  non-HF pattern: pin the **PyPI release** (`org/tool@<version>`), `adapter: presidio`,
  `clean_held_out` everywhere.
- **[`fastino-gliner2.yaml`](fastino-gliner2.yaml)** (KLU-108) — GLiNER2 (Fastino, Apache-2.0), an
  **HF model** revision-pinned by commit SHA, scored zero-shot via the `gliner2` adapter.
- **[`explosion-spacy.yaml`](explosion-spacy.yaml)** (KLU-108) — spaCy `en_core_web_lg` (MIT). A
  non-HF model **package**, release-pinned (`spacy/en_core_web_lg@3.8.0`), via the `spacy` adapter.

## Optional upside: cloud APIs (human-gated)

Cloud PII services — **Azure AI Language**, **AWS Comprehend** — are credentialed/billed and cannot
run in the no-secrets sandbox. They are an explicitly **human-gated** path (a maintainer runs them
with their own keys, off-CI, and lands the row): the no-credentials systems above are the
self-serve path an outside contributor can follow today.
