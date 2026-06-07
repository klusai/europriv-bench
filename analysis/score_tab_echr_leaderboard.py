#!/usr/bin/env python3
"""RES-89: score the board on the TAB ECHR REAL-data gold config (tab-echr-legal-en-v1).

The program's FIRST real-data test: real English ECHR court judgments, manually annotated +
peer-reviewed (Pilán et al. 2022), remapped to the KP taxonomy. Scores the board adapters that run
quickly on this Mac (kp-model, gliner, gliner2, spacy, presidio, tabularisai); the MoE backends
(privacy-filter, openmed) are slow on CPU — score them only if requested (e.g. via the --workers
parallel path elsewhere), else record them as pending (honest coverage, never blocking).

Gold is pulled from HF at eval time (the published `tab-echr-legal-en-v1` test split) — never
hardcoded. Numbers are computed here. Writes a leaderboard JSON + a summary.

    python analysis/score_tab_echr_leaderboard.py
    python analysis/score_tab_echr_leaderboard.py --adapters kp-model,gliner,privacy-filter,openmed
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from europriv_bench.adapters import build
from europriv_bench.leaderboard import write_leaderboard
from europriv_bench.runner import run_spec
from europriv_bench.spec import EvalSpec

SPEC = "evaluations/pii-detection-tab-echr-legal-en.yaml"
# Full board (minus dummy). FAST subset scored by default on this Mac; MoE pair recorded pending.
ALL_ADAPTERS = ["kp-model", "gliner", "gliner2", "spacy", "presidio", "tabularisai",
                "privacy-filter", "openmed"]
FAST_ADAPTERS = ["kp-model", "gliner", "gliner2", "spacy", "presidio", "tabularisai"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapters", default=",".join(FAST_ADAPTERS),
                    help="comma-separated adapter subset to score (others recorded as pending)")
    ap.add_argument("--limit", type=int, default=None, help="cap docs (None = all 127)")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--out", default="analysis/tab_echr_leaderboard.json")
    ap.add_argument("--summary", default="analysis/tab_echr_summary.json")
    args = ap.parse_args()

    try:
        import torch
        torch.set_num_threads(args.threads)
    except ImportError:
        pass

    spec = EvalSpec.from_yaml(SPEC)
    scored_adapters = [a for a in args.adapters.split(",") if a]
    pending_adapters = [a for a in ALL_ADAPTERS if a not in scored_adapters]

    results: list[dict] = []
    for aname in scored_adapters:
        try:
            adapter = build(aname)
        except Exception as e:  # noqa: BLE001
            print(f"[skip] {aname}: build failed ({e})")
            pending_adapters.append(aname)
            continue
        t0 = time.time()
        try:
            res = run_spec(spec, adapter, limit=args.limit)  # gold pulled from HF
        except Exception as e:  # noqa: BLE001
            print(f"[fail] {aname}: {e}")
            pending_adapters.append(aname)
            continue
        s = res["scores"]
        print(f"  {aname:16} F1={s['entity_f1']['f1']:.3f} F2={s['entity_f2']['f2']:.3f} "
              f"n={res['n']} {res['contamination']} {res['config_status']} {time.time()-t0:5.1f}s")
        results.append(res)

    write_leaderboard(results, args.out)

    by_adapter = {r["adapter"]: r for r in results}
    summary = {
        "config": "tab-echr-legal-en-v1",
        "source": "Text Anonymization Benchmark (TAB), Pilán et al. 2022, Computational Linguistics 48(4)",
        "license": "MIT (TAB data; NOT CC-BY — CC-BY covers only the journal article)",
        "label": "REAL, peer-reviewed, externally-annotated legal gold (ECHR); config_status=real-external-gold",
        "n_docs": next(iter(results), {}).get("n"),
        "scored_adapters": scored_adapters,
        "pending_adapters": sorted(set(pending_adapters)),
        "pending_note": ("MoE backends (privacy-filter, openmed) are slow on this Mac's CPU; "
                         "scored separately via the --workers parallel path or flagged pending — "
                         "honest coverage, never blocking the fast subset."),
        "per_adapter": {
            a: {"entity_f1": round(r["scores"]["entity_f1"]["f1"], 4),
                "entity_f2": round(r["scores"]["entity_f2"]["f2"], 4),
                "precision": round(r["scores"]["entity_f1"]["precision"], 4),
                "recall": round(r["scores"]["entity_f1"]["recall"], 4),
                "contamination": r["contamination"],
                "config_status": r["config_status"]}
            for a, r in by_adapter.items()
        },
    }
    Path(args.summary).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("wrote", args.out, "and", args.summary)


if __name__ == "__main__":
    main()
