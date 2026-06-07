#!/usr/bin/env python3
"""RES-95 confirmation — does stage-B narrative data DE-SATURATE detection F1?

RES-95 v1 proved the stage-B narrative generator lifts Romanian document diversity (unique-skeleton
ratio 0.003 -> 0.909, see ``ro_stageb_v1_metrics.json``). This script confirms the *consequence*:
that detection entity-F1 stops saturating on the diverse stage-B data.

The experiment (SCORING ONLY — no training):
  * **Templated RO baseline** — the existing ``ro-synthetic-v1`` test config (template-splice; the
    saturating regime per RES-19/KLU-106). Capped to a held-out slice of N docs.
  * **Stage-B RO** — a held-out slice carved from ``ro_stageb_v1.jsonl`` (the diverse LLM-authored
    bodies with deterministic, gold-aligned PII). These models were NEVER trained on stage-B, so any
    deterministic slice is a clean held-out for them.

For each fast model (kp-deid local checkpoint, plus gliner/gliner2 if their extras import) we score
strict entity-F1 on BOTH sets, using the harness scoring path verbatim (``_rows_to_gold`` +
``entity_f1`` + the eval-label fairness mask — each set scored on its own gold labels). We add a
paired-document bootstrap percentile CI on the micro-F1 (precomputed per-doc IOBES counts, the
KLU-106 trick) so the spread is quantified, not eyeballed.

Headline: templated F1 ~ 1.0 (saturated, CI hugging 1.0) vs stage-B F1 spread BELOW 1.0 (the
de-saturation delta), per model. config_status=dev; numbers from real runs only.

ONE process, models scored sequentially (RES-97 bound: no concurrent runs against the same output).

Run from the europriv-bench repo root, inside its venv (has gliner/gliner2/torch/seqeval):

    EUROPRIV_DEVICE=cpu python analysis/f1_desaturation_stageb_res95.py \
        --stageb /Users/mihai/codespace/klusai-datasets/artifacts/europriv/ro_stageb_v1.jsonl \
        --kp-deid /Users/mihai/codespace/klusai-models/runs/kp-deid-mdeberta-280m-v2-seed0 \
        --n 400 --out analysis/f1_desaturation_stageb_res95.json
"""

from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import click

BOOTSTRAP_ITERS = 2000
BOOTSTRAP_SEED = 12345


def _load_stageb_rows(path: str, n: int) -> list[dict]:
    """Carve a deterministic held-out slice (the LAST ``n`` docs) from the stage-B jsonl.

    Stage-B v1 is a generation batch (no train split); these scoring models never saw it, so the
    tail slice is a clean held-out. Taking the tail (not the head) avoids the leading docs that any
    eyeballing/spot-check would have looked at first.
    """
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) < n:
        raise click.UsageError(f"stage-B file has only {len(rows)} rows (< requested {n})")
    return rows[-n:]


def _doc_entity_counts(gold_tags, pred_tags):
    """Per-document strict (IOBES) entity counts ``(tp, n_pred, n_gold)`` (KLU-106 verbatim).

    seqeval corpus F1 is micro (entities pooled across docs), so micro-F1 over any document multiset
    is exactly reconstructable from the summed per-doc counts — turning each bootstrap iteration into
    O(n) integer sums instead of an O(n) seqeval re-parse.
    """
    from seqeval.scheme import IOBES, Entities

    tps, npreds, ngolds = [], [], []
    for g, p in zip(gold_tags, pred_tags):
        eg = Entities([g], scheme=IOBES).entities[0]
        ep = Entities([p], scheme=IOBES).entities[0]
        sg = {(e.tag, e.start, e.end) for e in eg}
        sp = {(e.tag, e.start, e.end) for e in ep}
        tps.append(len(sg & sp))
        npreds.append(len(sp))
        ngolds.append(len(sg))
    return tps, npreds, ngolds


def _micro_f1(tp: int, n_pred: int, n_gold: int) -> float:
    prec = tp / n_pred if n_pred else 0.0
    rec = tp / n_gold if n_gold else 0.0
    return 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0


def _bootstrap_f1_ci(gold_tags, pred_tags, *, iters=BOOTSTRAP_ITERS, seed=BOOTSTRAP_SEED):
    """95% percentile bootstrap CI for micro entity-F1 (resample documents with replacement)."""
    tp, npred, ngold = _doc_entity_counts(gold_tags, pred_tags)
    n = len(gold_tags)
    rng = random.Random(seed)
    base = _micro_f1(sum(tp), sum(npred), sum(ngold))
    vals = []
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        vals.append(_micro_f1(sum(tp[i] for i in idx), sum(npred[i] for i in idx), sum(ngold[i] for i in idx)))
    vals.sort()
    lo = vals[int(0.025 * iters)]
    hi = vals[min(iters - 1, int(0.975 * iters))]
    return base, lo, hi


def _score_model_on_set(adapter, rows):
    """Strict entity-F1 (+ P/R) and bootstrap CI for one model on one row set, harness scoring path.

    The adapter's predictions are masked to the gold eval-labels PRESENT in this set (the harness
    fairness mask) so each dataset is scored on its own labels — no cross-set label penalty.
    """
    from europriv_bench.metrics import entity_f1
    from europriv_bench.runner import _rows_to_gold

    texts = [r["text"] for r in rows]
    _, gold_tags = _rows_to_gold(rows)
    eval_labels = {t.split("-", 1)[1] for seq in gold_tags for t in seq if t != "O"}

    t0 = time.time()
    pred_tags = adapter.predict_tags(texts)
    secs = time.time() - t0

    masked = [
        [t if (t == "O" or t.split("-", 1)[1] in eval_labels) else "O" for t in seq]
        for seq in pred_tags
    ]
    m = entity_f1(gold_tags, masked)
    f1, lo, hi = _bootstrap_f1_ci(gold_tags, masked)
    return {
        "f1": round(m["f1"], 4),
        "precision": round(m.get("precision", 0.0), 4),
        "recall": round(m.get("recall", 0.0), 4),
        "f1_ci95_low": round(lo, 4),
        "f1_ci95_high": round(hi, 4),
        "eval_labels": sorted(eval_labels),
        "seconds": round(secs, 1),
    }


def _build_baseline(name):
    """Instantiate an optional baseline adapter; return None (skip-and-report) if the extra is absent."""
    from europriv_bench.adapters import build

    try:
        return build(name)
    except Exception as e:  # extra not installed on this machine
        return str(e).splitlines()[0][:160]


@click.command()
@click.option("--stageb", required=True, help="Path to ro_stageb_v1.jsonl (RES-95 v1 stage-B batch).")
@click.option("--kp-deid", "kp_deid", required=True, help="Local kp-deid checkpoint dir (or HF id).")
@click.option("--templated-spec", default="evaluations/pii-detection-ro-synthetic.yaml",
              help="Templated RO held-out spec (ro-synthetic-v1) — the saturating baseline.")
@click.option("--n", type=int, default=400, help="Held-out docs per set (matched).")
@click.option("--baselines", "baseline_names", default="gliner,gliner2",
              help="Comma list of optional fast baselines (skipped cleanly if extra absent).")
@click.option("--threads", type=int, default=4)
@click.option("--out", default="analysis/f1_desaturation_stageb_res95.json")
def main(stageb, kp_deid, templated_spec, n, baseline_names, threads, out):
    try:
        import torch

        torch.set_num_threads(threads)
    except ImportError:
        pass
    os.environ.setdefault("EUROPRIV_DEVICE", "cpu")  # deterministic CPU scoring

    from europriv_bench.adapters import KpModelAdapter
    from europriv_bench.runner import _load_gold_rows
    from europriv_bench.spec import EvalSpec

    # --- the two matched held-out RO sets ---
    stageb_rows = _load_stageb_rows(stageb, n)
    templated_all = _load_gold_rows(EvalSpec.from_yaml(templated_spec))
    templated_rows = templated_all[-n:] if len(templated_all) >= n else templated_all
    print(f"[data] stage-B held-out: {len(stageb_rows)} docs (tail of {stageb})")
    print(f"[data] templated held-out: {len(templated_rows)} docs (tail of ro-synthetic-v1, total {len(templated_all)})")

    # --- model set: kp-deid (required) + optional fast baselines ---
    models = [("kp-deid", KpModelAdapter(model_id=kp_deid))]
    skips = {}
    for name in [b for b in baseline_names.split(",") if b]:
        adapter = _build_baseline(name)
        if isinstance(adapter, str):
            skips[name] = adapter
            print(f"[skip] {name}: {adapter}")
        else:
            models.append((name, adapter))

    # --- score each model on BOTH sets, sequentially (ONE process) ---
    per_model = []
    for name, adapter in models:
        print(f"[score] {name} ({getattr(adapter, 'model_id', name)}) ...")
        try:
            templated = _score_model_on_set(adapter, templated_rows)
            stage_b = _score_model_on_set(adapter, stageb_rows)
        except Exception as e:  # model loaded but failed at inference — report precisely, do not thrash
            print(f"[error] {name} failed at inference: {e}")
            skips[name] = f"inference_error: {str(e).splitlines()[0][:160]}"
            continue
        delta = round(templated["f1"] - stage_b["f1"], 4)
        desaturates = bool(stage_b["f1_ci95_high"] < 0.999 and stage_b["f1"] < templated["f1"])
        per_model.append({
            "model": name,
            "model_id": getattr(adapter, "model_id", name),
            "templated_ro": templated,
            "stageb_ro": stage_b,
            "f1_drop_templated_minus_stageb": delta,
            "stageb_desaturates": desaturates,
        })
        print(f"       templated F1={templated['f1']:.4f} [{templated['f1_ci95_low']:.4f},"
              f"{templated['f1_ci95_high']:.4f}]  |  stage-B F1={stage_b['f1']:.4f} "
              f"[{stage_b['f1_ci95_low']:.4f},{stage_b['f1_ci95_high']:.4f}]  |  drop={delta:+.4f}  "
              f"desat={desaturates}")

    any_desat = any(c["stageb_desaturates"] for c in per_model)
    verdict = (
        "CONFIRMED: stage-B de-saturates detection F1 (templated near 1.0; stage-B spreads below 1.0)."
        if any_desat else
        "NOT confirmed on this slice (stage-B F1 did not drop below the templated baseline)."
    )

    scorecard = {
        "issue": "RES-95 (F1 de-saturation confirmation — second half of acceptance)",
        "config_status": "dev",
        "question": "Does the diverse stage-B narrative data de-saturate detection entity-F1 vs the "
                    "templated ro-synthetic baseline (which pins near 1.0)?",
        "scoring_only": True,
        "device": os.environ.get("EUROPRIV_DEVICE", "cpu"),
        "n_per_set": n,
        "datasets": {
            "templated_ro": {"spec": templated_spec, "config": "ro-synthetic-v1", "held_out_n": len(templated_rows),
                             "regime": "template-splice (saturating, RES-19/KLU-106)"},
            "stageb_ro": {"path": stageb, "held_out_n": len(stageb_rows), "slice": "tail",
                          "regime": "stage-B LLM-authored narrative (RES-95 v1; skeleton ratio 0.909)"},
        },
        "bootstrap": {"iters": BOOTSTRAP_ITERS, "seed": BOOTSTRAP_SEED,
                      "ci": "95% percentile, micro entity-F1, resampling documents"},
        "scoring_path": "europriv_bench harness: _rows_to_gold + entity_f1 + eval-label fairness mask",
        "per_model": per_model,
        "skipped_models": skips,
        "verdict": verdict,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(scorecard, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[verdict] {verdict}")
    print(f"[wrote] {out}")


if __name__ == "__main__":
    main()
