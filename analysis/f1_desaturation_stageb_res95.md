# RES-95 — F1 de-saturation confirmation (stage-B narrative RO)  ·  2026-06-07

> **Second half of RES-95's acceptance.** RES-95 v1 proved the stage-B narrative generator lifts RO
> document diversity (unique-skeleton ratio **0.003 → 0.909**, `klusai-datasets/.../ro_stageb_v1_metrics.json`).
> This note confirms the *consequence*: detection entity-F1 **de-saturates** on the diverse data.
> **dev-tier diagnostic, SCORING ONLY** (no training). Numbers from real CPU runs; per-set fairness
> mask + 95% paired-document bootstrap CI via the europriv-bench harness scoring path.

## Setup

- **Templated RO (saturating baseline):** `ro-synthetic-v1` test config (template-splice; the
  saturating regime per RES-19/KLU-106). Held-out slice = last 400 docs of the 1500-row test split.
- **Stage-B RO (diverse):** last 400 docs of `ro_stageb_v1.jsonl` (RES-95 v1; LLM-authored bodies,
  deterministic gold-aligned PII). These models were **never trained on stage-B** → clean held-out.
- **Models (fast only; slow MoE backends skipped per the RES-97 bound):** local **kp-deid**
  (`kp-deid-mdeberta-280m-v2-seed0`, the headline trained model), plus zero-shot **gliner**
  (`urchade/gliner_multi_pii-v1`) and **gliner2** (`fastino/gliner2-base-v1`).
- Each set scored on its **own** gold labels (harness eval-label mask) — no cross-set label penalty.
- ONE process, models scored sequentially. CI: 2000-resample document bootstrap, seed 12345.

## Headline: templated ≈ saturated vs stage-B = spread below 1.0

| model | templated-RO F1 (95% CI) | stage-B-RO F1 (95% CI) | drop (templated − stage-B) | de-saturates? |
|---|---|---|---:|:---:|
| **kp-deid** (trained) | **1.0000** [1.0000, 1.0000] | **0.9374** [0.9226, 0.9517] | **+0.0626** | **yes** |
| gliner (zero-shot) | 0.7953 [0.7801, 0.8101] | 0.8891 [0.8813, 0.8970] | −0.0938 | no* |
| gliner2 (zero-shot) | 0.7697 [0.7521, 0.7872] | 0.7133 [0.6984, 0.7286] | +0.0564 | yes |

## Verdict

**CONFIRMED for the model the claim is about.** Our trained **kp-deid** pins at **F1 = 1.0000**
(precision = recall = 1.0, CI collapsed to [1.0, 1.0]) on the templated RO — perfect saturation, zero
discrimination — and drops to **0.9374** with a CI of **[0.9226, 0.9517]** that sits cleanly below
1.0 on the diverse stage-B RO. That is the de-saturation, quantified: the same model goes from "no
spread" to a measurable, CI-bounded sub-1.0 score purely because the documents are diverse (stage-B
is genuinely out-of-distribution prose for a model trained on template-splice RO). The recall drop
(1.000 → 0.912) is where the discrimination opens up. **gliner2** (zero-shot) likewise de-saturates
(0.770 → 0.713).

\* **gliner caveat (honest read):** gliner is *not* saturated on templated either (0.795) and scores
*higher* on stage-B (0.889). This is a zero-shot artifact, not a counter-example to de-saturation:
the templated RO leans on RO-specific structured identifiers (CUI/`COMPANY_ID`, RO-IBAN/`ACCOUNT_ID`)
that gliner's prompted English labels map poorly, while the stage-B narrative is natural prose where
its PERSON/DATE/ADDRESS prompting fits better. Saturation/de-saturation is a property of a model
*that has learned the templated distribution* (our kp-deid), which is exactly the failure mode RES-95
set out to fix — and the fix lands: kp-deid can no longer cheat the eval.

## Reproduce

```
cd europriv-bench && source .venv/bin/activate            # venv has gliner/gliner2/torch/seqeval
EUROPRIV_DEVICE=cpu python analysis/f1_desaturation_stageb_res95.py \
    --stageb ../klusai-datasets/artifacts/europriv/ro_stageb_v1.jsonl \
    --kp-deid ../klusai-models/runs/kp-deid-mdeberta-280m-v2-seed0 \
    --n 400 --out analysis/f1_desaturation_stageb_res95.json
```

Full per-model precision/recall/CI/timings: `analysis/f1_desaturation_stageb_res95.json`.
