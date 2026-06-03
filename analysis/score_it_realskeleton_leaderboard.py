#!/usr/bin/env python3
"""Score the 8 board models on it-realskeleton-v1 and merge the rows into the leaderboard (KLU-105).

``it-realskeleton-v1`` is not yet published to the HF hub, so we score from LOCALLY-generated gold
rows (dumped from klusai-datasets' ``it_skeletons.generate_dataset``) — the same decoupling the
RO/PL real-skeleton tracks use. Each ``run_spec`` row is a complete, annotated leaderboard entry
(entity F1/F2 + national_id_leakage, contamination=clean_held_out, config_status=dev). We merge the
8 new rows into ``baselines/leaderboard.json`` (and ``leaderboard-full.json``) and re-aggregate via
``build_leaderboard`` so existing entries are preserved.

Reproduce (foreground; heavy)::

    python -c "import json; from klusai.privacy.datasets.data.it_skeletons import generate_dataset; \\
        json.dump(list(generate_dataset(1500, seed=20260531)), \\
        open('analysis/it_realskeleton_rows_full.json','w'), ensure_ascii=False)"
    python analysis/score_it_realskeleton_leaderboard.py --rows analysis/it_realskeleton_rows_full.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from europriv_bench.adapters import build
from europriv_bench.leaderboard import build_leaderboard
from europriv_bench.runner import run_spec
from europriv_bench.spec import EvalSpec

SPEC = "evaluations/pii-detection-it-realskeleton.yaml"
CONFIG = "it-realskeleton-v1"
BOARD = ["kp-model", "privacy-filter", "openmed", "tabularisai",
         "gliner", "gliner2", "spacy", "presidio"]


def _existing_rows(lb_path: Path) -> list[dict]:
    """Flatten an existing leaderboard.json back to a flat list of result rows (dropping any prior
    rows for CONFIG so a re-run replaces them rather than duplicating)."""
    if not lb_path.exists():
        return []
    lb = json.loads(lb_path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for entry_rows in lb.get("entries", {}).values():
        for r in entry_rows:
            if (r.get("dataset") or {}).get("config") != CONFIG:
                rows.append(r)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, required=True, help="Local IT gold rows JSON (country='IT').")
    ap.add_argument("--out", type=Path, default=Path("baselines/leaderboard.json"))
    ap.add_argument("--full-out", type=Path, default=Path("baselines/leaderboard-full.json"))
    args = ap.parse_args()

    gold_rows = json.loads(args.rows.read_text(encoding="utf-8"))
    if not gold_rows or gold_rows[0].get("country") != "IT":
        raise SystemExit(f"{args.rows}: rows must carry country='IT'")
    spec = EvalSpec.from_yaml(SPEC)

    new_rows = []
    for name in BOARD:
        model = build(name)
        res = run_spec(spec, model, rows=gold_rows)
        nid = res["scores"]["national_id_leakage"]
        print(f"{name:16s} f1={res['scores']['entity_f1']['f1']:.3f} "
              f"leak={nid['leak_rate']:.4f} ({int(nid['decode_bearing_missed'])}/"
              f"{int(nid['decode_bearing_total'])}) leaked_qi={int(nid['leaked_quasi_identifiers'])}")
        new_rows.append(res)

    for out in (args.out, args.full_out):
        merged = _existing_rows(out) + new_rows
        out.write_text(json.dumps(build_leaderboard(merged), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {out} ({len(merged)} rows total)")


if __name__ == "__main__":
    main()
