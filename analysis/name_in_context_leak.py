#!/usr/bin/env python3
"""KLU-118 v1 — the name-in-context residual leak channel + its 2x2 cross-tab vs the anchor.

The detection-F1 ≠ re-identification-protection dissociation is, until now, demonstrated only on
the decode-bearing national-ID anchor (one mechanism: a structured token). This script measures the
SECOND, non-token channel — a PERSON full name left UN-REDACTED on the post-detection residual — per
distinct subject ``(doc, country, normalized name)`` (same unit shape as the anchor), with a 95%
Wilson CI, and emits a per-document 2x2 cross-tab (id-leaked x name-leaked) to show the two channels
are INDEPENDENT.

CLAIM LANGUAGE (hard rule, KLU-118 design doc): the name channel is a **name-in-context leak /
residual quasi-identifier distinctiveness** signal on synthetic data, NEVER a "re-identification
rate" (that term is reserved for the deterministic national-ID anchor). All output is
config_status=dev, gated on KLU-27. A null/weak name-leak dissociation is an EXPECTED, valid finding.

Inputs / reproduce (scoring is heavy — run serial/foreground, see KLU-53 perf note)::

    # gold rows dumped locally from klusai-datasets (europriv-bench never imports the dataset pkg)
    python analysis/name_in_context_leak.py \
        --rows analysis/ro_realskeleton_two_family_rows.json \
        --adapter kp-model --adapter presidio --adapter spacy --adapter gliner \
        --outdir analysis
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CONFIG = "ro-realskeleton-v1"


def _load_rows(rows_path: Path) -> list[dict]:
    return json.loads(rows_path.read_text(encoding="utf-8"))


def _score(rows: list[dict], adapters: list[str]) -> dict[str, dict]:
    from europriv_bench.adapters import build
    from europriv_bench.runner import run_spec
    from europriv_bench.spec import DatasetRef, EvalSpec, Task

    spec = EvalSpec(
        name="qi-distinctiveness-ro-realskeleton",
        task=Task.DETECTION,
        languages=["ro"],
        domain="legal",
        dataset=DatasetRef(hf_id="klusai/europriv-bench", config=CONFIG, split="test"),
        metrics=["entity_f1", "national_id_leakage", "name_in_context_leakage",
                 "k_anonymity_violation"],
    )
    out: dict[str, dict] = {}
    for name in adapters:
        res = run_spec(spec, build(name), rows=rows)
        nic = res["scores"]["name_in_context_leakage"]
        nid = res["scores"]["national_id_leakage"]
        out[name] = {
            "model_id": res["model_id"],
            "detection_f1": res["scores"]["entity_f1"]["f1"],
            "id_leak_rate": nid["leak_rate"],
            "id_leak_ci": [nid["leak_rate_ci_low"], nid["leak_rate_ci_high"]],
            "id_subjects": int(nid["decode_bearing_total"]),
            "name_leak_rate": nic["name_leak_rate"],
            "name_leak_ci": [nic["name_leak_rate_ci_low"], nic["name_leak_rate_ci_high"]],
            "name_subjects": int(nic["name_subjects_total"]),
            "xtab": {
                "docs": int(nic["xtab_docs"]),
                "both_leaked": int(nic["xtab_both_leaked"]),
                "id_only_leaked": int(nic["xtab_id_only_leaked"]),
                "name_only_leaked": int(nic["xtab_name_only_leaked"]),
                "neither_leaked": int(nic["xtab_neither_leaked"]),
            },
            "k_anonymity_violation": res["scores"]["k_anonymity_violation"],
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, required=True,
                    help="Local gold rows JSON for ro-realskeleton-v1 (each {text, spans, ...}).")
    ap.add_argument("--adapter", dest="adapters", action="append", default=None,
                    help="Board adapter(s) to score; repeatable. Default = the 8 board models.")
    ap.add_argument("--outdir", type=Path, default=Path("analysis"))
    args = ap.parse_args()

    adapters = args.adapters or [
        "kp-model", "privacy-filter", "openmed", "tabularisai",
        "gliner", "gliner2", "spacy", "presidio",
    ]
    rows = _load_rows(args.rows)
    models = _score(rows, adapters)

    payload = {
        "config": CONFIG,
        "config_status": "dev",  # gated on KLU-27; NOT a citable/headline number
        "claim_language": (
            "name-in-context leak / residual quasi-identifier distinctiveness on synthetic data; "
            "NOT a re-identification rate (reserved for the national-ID anchor)"
        ),
        "models": models,
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    out_json = args.outdir / "name_in_context_leak_ro_realskeleton.json"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out_json}")
    for name, m in models.items():
        print(f"  {name}: F1={m['detection_f1']:.3f} id_leak={m['id_leak_rate']:.3f} "
              f"name_leak={m['name_leak_rate']:.3f} xtab={m['xtab']}")


if __name__ == "__main__":
    main()
