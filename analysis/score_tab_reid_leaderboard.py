#!/usr/bin/env python3
"""RES-72/104 pivot — re-identification-risk leaderboard on TAB (real legal gold).

Reframes the TAB board around the program's FLAGSHIP metric instead of detection-F1: of the
manually-annotated DIRECT / QUASI identifiers a de-id model should remove, what fraction does it
LEAVE in the residual (``tab_reid_leakage``)? Lower = less re-identification risk. This is the axis
no competitor reports — and detection-F1 leaders are not necessarily re-id-risk leaders (the
detection-vs-re-identification dissociation, on REAL legal data).

Gold pulled from HF at eval time. Scores the fast board adapters; MoE pair recorded pending (slow on
CPU, like the detection board). Writes a leaderboard JSON ranked by DIRECT-identifier leak rate.

    python analysis/score_tab_reid_leaderboard.py
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from europriv_bench.adapters import build
from europriv_bench.runner import run_spec
from europriv_bench.spec import EvalSpec

SPEC = "evaluations/pii-detection-tab-echr-legal-en.yaml"
ALL_ADAPTERS = ["kp-model", "gliner", "gliner2", "spacy", "presidio", "tabularisai",
                "privacy-filter", "openmed"]
FAST_ADAPTERS = ["kp-model", "gliner", "gliner2", "spacy", "presidio", "tabularisai"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapters", default=",".join(FAST_ADAPTERS))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--out", default="analysis/tab_reid_leaderboard.json")
    args = ap.parse_args()
    try:
        import torch
        torch.set_num_threads(args.threads)
    except ImportError:
        pass

    spec = EvalSpec.from_yaml(SPEC)
    scored = [a for a in args.adapters.split(",") if a]
    pending = [a for a in ALL_ADAPTERS if a not in scored]
    entries: list[dict] = []
    for aname in scored:
        try:
            adapter = build(aname)
            t0 = time.time()
            res = run_spec(spec, adapter, limit=args.limit)
        except Exception as e:  # noqa: BLE001
            print(f"[skip] {aname}: {e}")
            pending.append(aname)
            continue
        s = res["scores"]
        rl = s.get("tab_reid_leakage", {})
        entries.append({
            "adapter": aname,
            "model_id": res.get("model_id"),
            "entity_f1": round(s["entity_f1"]["f1"], 4),
            "direct_leak_rate": round(rl.get("direct_leak_rate", float("nan")), 4),
            "direct_leak_ci": [round(rl.get("direct_leak_rate_ci_low", 0), 4),
                               round(rl.get("direct_leak_rate_ci_high", 0), 4)],
            "quasi_leak_rate": round(rl.get("quasi_leak_rate", float("nan")), 4),
            "all_leak_rate": round(rl.get("all_leak_rate", float("nan")), 4),
            "direct_subjects": int(rl.get("direct_subjects_total", 0)),
            "quasi_subjects": int(rl.get("quasi_subjects_total", 0)),
        })
        print(f"  {aname:14} F1={entries[-1]['entity_f1']:.3f}  "
              f"DIRECT-leak={entries[-1]['direct_leak_rate']:.3f}  "
              f"QUASI-leak={entries[-1]['quasi_leak_rate']:.3f}  ({time.time()-t0:.0f}s)")

    entries.sort(key=lambda e: e["direct_leak_rate"])  # ↓ less re-id risk = better
    board = {
        "config": "tab-echr-legal-en-v1",
        "metric": "tab_reid_leakage — per-subject DIRECT/QUASI identifier leak rate on the "
                  "post-detection residual (lower = less re-identification risk)",
        "label": "REAL legal gold (TAB ECHR, Pilán et al. 2022); flagship re-id-risk axis (RES-72/104)",
        "ranked_by": "direct_leak_rate (ascending)",
        "scored_adapters": scored,
        "pending_adapters": sorted(set(pending)),
        "n_docs": None,
        "entries": entries,
    }
    Path(args.out).write_text(json.dumps(board, indent=2))
    print(f"\nwrote {args.out}")
    print("\nRE-ID-RISK RANKING (DIRECT-identifier leak rate ↓):")
    for i, e in enumerate(entries, 1):
        print(f"  {i}. {e['adapter']:14} DIRECT-leak={e['direct_leak_rate']:.3f}  (det-F1={e['entity_f1']:.3f})")


if __name__ == "__main__":
    main()
