#!/usr/bin/env python3
"""RES-104: paired-bootstrap Δ CI for the re-id-risk #1 — kp-cjeu-structure vs the runner-up (spacy).

Takes the re-id win from "robust across seeds" to a citable significance claim: pairs the per-subject
DIRECT-identifier detection outcomes (same TAB subjects, same gold) for our CJEU-structure model and
spacy, and bootstraps the leak-rate difference. CI fully below 0 ⇒ kp leaks significantly fewer DIRECT
identifiers. Gold pulled from HF; runs in the europriv-bench venv (torch + spacy + KpModelAdapter).

    python analysis/reid_paired_bootstrap.py --kp-checkpoint /abs/path/to/runs/res72-cjeu-tab-seed0
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from datasets import load_dataset

from europriv_bench.adapters import KpModelAdapter, build
from europriv_bench.metrics import tab_reid_subject_detection
from europriv_bench.spans import Span, char_spans_to_bioes

N_BOOT = 2000
SEED = 20260613


def _mask(pred_tags, labels):
    keep = set(labels)
    return [[t if (t == "O" or t.split("-", 1)[1] in keep) else "O" for t in seq] for seq in pred_tags]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kp-checkpoint", required=True, help="abs path to the kp-cjeu-structure checkpoint")
    ap.add_argument("--out", default="analysis/reid_paired_bootstrap.json")
    args = ap.parse_args()

    ds = load_dataset("klusai/europriv-bench", "tab-echr-legal-en-v1", split="test")
    rows = [{"text": r["text"], "spans": r["spans"]} for r in ds]
    texts = [r["text"] for r in rows]
    gold = [char_spans_to_bioes(r["text"], [Span(s["start"], s["end"], s["label"]) for s in r["spans"]])
            for r in rows]
    labels = sorted({t.split("-", 1)[1] for seq in gold for t in seq if t != "O"})

    kp_pred = _mask(KpModelAdapter(model_id=args.kp_checkpoint).predict_tags(texts), labels)
    sp_pred = _mask(build("spacy").predict_tags(texts), labels)

    kp = {(d["doc"], d["entity_id"], d["identifier_type"]): d["detected"]
          for d in tab_reid_subject_detection(rows, kp_pred) if d["identifier_type"] == "DIRECT"}
    sp = {(d["doc"], d["entity_id"], d["identifier_type"]): d["detected"]
          for d in tab_reid_subject_detection(rows, sp_pred) if d["identifier_type"] == "DIRECT"}
    keys = sorted(set(kp) & set(sp))
    # leak = not detected; per-subject paired (kp_leak, spacy_leak)
    pairs = [(0 if kp[k] else 1, 0 if sp[k] else 1) for k in keys]
    n = len(pairs)
    kp_leak = sum(p[0] for p in pairs) / n
    sp_leak = sum(p[1] for p in pairs) / n
    point = kp_leak - sp_leak  # negative ⇒ kp leaks less (better)

    rng = random.Random(SEED)
    deltas = []
    for _ in range(N_BOOT):
        idx = [rng.randrange(n) for _ in range(n)]
        a = sum(pairs[i][0] for i in idx) / n
        b = sum(pairs[i][1] for i in idx) / n
        deltas.append(a - b)
    deltas.sort()
    lo, hi = deltas[int(0.025 * N_BOOT)], deltas[int(0.975 * N_BOOT)]

    out = {
        "comparison": "kp-cjeu-structure vs spacy (runner-up) — DIRECT-identifier leak rate on TAB",
        "n_paired_direct_subjects": n,
        "kp_direct_leak": round(kp_leak, 4),
        "spacy_direct_leak": round(sp_leak, 4),
        "delta_kp_minus_spacy": round(point, 4),
        "delta_ci95": [round(lo, 4), round(hi, 4)],
        "n_bootstrap": N_BOOT,
        "significant": bool(hi < 0),
        "reading": ("kp leaks SIGNIFICANTLY fewer DIRECT identifiers (Δ CI fully below 0)"
                    if hi < 0 else "not significant at 95%"),
    }
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
