#!/usr/bin/env python3
"""RES-93 headline check: does detection F1 stop saturating on the external Ai4Privacy open-core
track vs our own template-splice synthetic (control F1 = 1.000 on de/fr/nl/pl/ro)?

Scores the board adapters against the locally-curated held-out Ai4Privacy slices (gold pulled at
eval time, never committed — same as the harness convention). Writes a leaderboard JSON + a
plain-text saturation summary. Numbers are computed here, never hardcoded.

    python analysis/ai4privacy_openpii_saturation.py --gold /tmp/ai4p_gold --limit 200
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

LANGS = ["ro", "pl", "cs", "sv", "el", "fi", "hu", "de", "fr", "nl"]
# The board: local kp-deid + the runnable baselines (all cached on this box).
ADAPTERS = ["kp-model", "privacy-filter", "openmed", "tabularisai",
            "gliner", "gliner2", "spacy", "presidio", "dummy"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="/tmp/ai4p_gold")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--adapters", default=",".join(ADAPTERS),
                    help="comma-separated adapter subset to score (others recorded as pending)")
    ap.add_argument("--out", default="analysis/ai4privacy_openpii_leaderboard.json")
    ap.add_argument("--summary", default="analysis/ai4privacy_openpii_saturation.json")
    args = ap.parse_args()

    gold_dir = Path(args.gold)
    specs = {lang: EvalSpec.from_yaml(f"evaluations/pii-detection-ai4privacy-openpii-{lang}.yaml")
             for lang in LANGS}
    gold = {lang: [json.loads(line) for line in open(gold_dir / f"{lang}.jsonl")][:args.limit]
            for lang in LANGS}

    scored_adapters = [a for a in args.adapters.split(",") if a]
    pending_adapters = [a for a in ADAPTERS if a not in scored_adapters]

    results: list[dict] = []
    for aname in scored_adapters:
        try:
            adapter = build(aname)
        except Exception as e:  # noqa: BLE001
            print(f"[skip] {aname}: build failed ({e})")
            continue
        for lang in LANGS:
            t0 = time.time()
            try:
                res = run_spec(specs[lang], adapter, rows=gold[lang], limit=args.limit)
            except Exception as e:  # noqa: BLE001
                print(f"[fail] {aname} {lang}: {e}")
                continue
            f1 = res["scores"]["entity_f1"]["f1"]
            print(f"  {aname:16} {lang}  F1={f1:.3f}  n={res['n']}  "
                  f"{res['contamination']:16} {time.time()-t0:5.1f}s")
            results.append(res)

    write_leaderboard(results, args.out)

    # Saturation summary: per-adapter F1 spread across the 10 languages, and the board-wide spread
    # per language (max-min). The headline: are these < 1.0 and spread out (vs control == 1.000)?
    by_adapter: dict[str, dict[str, float]] = {}
    for r in results:
        by_adapter.setdefault(r["adapter"], {})[r["languages"][0]] = r["scores"]["entity_f1"]["f1"]
    summary = {
        "track": "ai4privacy-openpii-{lang}-v1",
        "source": "ai4privacy/pii-masking-openpii-1m (CC-BY-4.0 open core)",
        "label": "external synthetic (Ai4Privacy LLM generator, not KP, not real); config_status=dev",
        "limit_per_lang": args.limit,
        "languages": LANGS,
        "scored_adapters": scored_adapters,
        "pending_adapters": pending_adapters,
        "per_adapter": {},
        "board_f1_range_per_lang": {},
    }
    for a, byl in by_adapter.items():
        vals = list(byl.values())
        summary["per_adapter"][a] = {
            "f1_by_lang": {k: round(v, 4) for k, v in byl.items()},
            "min": round(min(vals), 4), "max": round(max(vals), 4),
            "mean": round(sum(vals) / len(vals), 4),
        }
    scoring_adapters = [a for a in by_adapter if a != "dummy"]
    for lang in LANGS:
        vals = [by_adapter[a][lang] for a in scoring_adapters if lang in by_adapter[a]]
        if vals:
            summary["board_f1_range_per_lang"][lang] = {
                "min": round(min(vals), 4), "max": round(max(vals), 4),
                "spread": round(max(vals) - min(vals), 4),
            }
    overall = [v for a in scoring_adapters for v in by_adapter[a].values()]
    summary["headline"] = {
        "max_f1_any_model_any_lang": round(max(overall), 4) if overall else None,
        "saturates": bool(overall and max(overall) >= 0.999),
        "verdict": ("NON-SATURATING: best F1 well below 1.0 — spread restored"
                    if overall and max(overall) < 0.999
                    else "still saturating"),
    }
    Path(args.summary).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\n=== HEADLINE ===")
    print(json.dumps(summary["headline"], indent=2))
    print("wrote", args.out, "and", args.summary)


if __name__ == "__main__":
    main()
