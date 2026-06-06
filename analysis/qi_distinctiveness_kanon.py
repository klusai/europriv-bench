#!/usr/bin/env python3
"""KLU-118 v1 item 2 — within-corpus k-anonymity-violation diagnostic over the residual QI tuple.

A SIBLING of ``analysis/name_in_context_leak.py``. Emits the exploratory k-anonymity-violation
diagnostic for ``ro-realskeleton-v1``: the within-corpus **equivalence-class-size distribution**
(a histogram, NEVER a single scalar) plus the k=1 / k<5 violation rates over the POST-DETECTION
RESIDUAL QI tuple (DOB-band + sex + county→NUTS-2 from the CNP, + a surviving-HEALTH_CONDITION
rare-condition flag), derived additively from data already in gold.

CLAIM LANGUAGE (hard rule, KLU-118 design doc): this is **"sample distinctiveness, not population
re-identification"** — never a re-identification rate (reserved for the deterministic national-ID
anchor), and never a single headline scalar. All output is config_status=dev, gated on KLU-27.

Two deterministic, model-free residual bounds are emitted so the artifact is reproducible offline
(no model backends, matching KLU-53's serial-scoring note):
  * ``null_detector`` — redacts NOTHING → MAXIMAL residual (the distinctiveness UPPER BOUND).
  * ``perfect_detector`` — redacts every gold span → residual carries no QI (the diagnostic
    correctly reports that nothing survives → unavailable for that residual).

Reproduce::

    python analysis/qi_distinctiveness_kanon.py \
        --rows analysis/ro_realskeleton_two_family_rows.json --outdir analysis
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CONFIG = "ro-realskeleton-v1"
LABEL = "sample distinctiveness, not population re-identification"


def _load_rows(rows_path: Path) -> list[dict]:
    return json.loads(rows_path.read_text(encoding="utf-8"))


def _null_pred(rows: list[dict]) -> list[list[str]]:
    from europriv_bench.spans import whitespace_tokens

    return [["O"] * len(whitespace_tokens(r["text"])) for r in rows]


def _perfect_pred(rows: list[dict]) -> list[list[str]]:
    from europriv_bench.spans import Span, char_spans_to_bioes

    return [
        char_spans_to_bioes(
            r["text"], [Span(s["start"], s["end"], s["label"]) for s in r.get("spans", [])]
        )
        for r in rows
    ]


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--rows", type=Path, required=True,
                    help="Local gold rows JSON for ro-realskeleton-v1 (each {text, spans, ...}).")
    ap.add_argument("--outdir", type=Path, default=Path("analysis"))
    args = ap.parse_args()

    from europriv_bench.metrics import k_anonymity_violation
    from europriv_bench.qi_schema import QI_FIELDS, QI_SCHEMA_VERSION

    rows = _load_rows(args.rows)
    residuals = {
        "null_detector": _null_pred(rows),       # max residual → distinctiveness upper bound
        "perfect_detector": _perfect_pred(rows),  # everything redacted → nothing survives
    }
    diagnostics = {name: k_anonymity_violation(rows, pred) for name, pred in residuals.items()}

    payload = {
        "config": CONFIG,
        "config_status": "dev",  # gated on KLU-27; NOT a citable/headline number
        "diagnostic": "k_anonymity_violation",
        "label": LABEL,
        "claim_language": (
            "within-corpus k-anonymity-violation over the residual quasi-identifier tuple; "
            "sample distinctiveness, NOT population re-identification (the latter reserved for the "
            "deterministic national-ID anchor). Reported as the equivalence-class-size distribution, "
            "never a single scalar headline."
        ),
        "qi_schema_version": QI_SCHEMA_VERSION,
        "qi_fields": list(QI_FIELDS),
        "qi_derivation": {
            "dob_band": "CNP-decoded DOB → 5-year year-of-birth band",
            "sex": "CNP-decoded sex",
            "nuts2": "CNP-decoded county → NUTS-2 (vendored Eurostat/ROU-OGL crosswalk)",
            "rare_condition": "True iff a HEALTH_CONDITION span survives the residual",
            "nationality": "OMITTED — absent from ro-realskeleton-v1 gold",
            "isco_major": "OMITTED — no profession label in the taxonomy / gold",
        },
        "residual_bounds": diagnostics,
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    out_json = args.outdir / "qi_distinctiveness_kanon_ro_realskeleton.json"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out_json}")
    for name, d in diagnostics.items():
        if d.get("available"):
            print(f"  {name}: n={d['n_subjects']} classes={d['n_equivalence_classes']} "
                  f"k1={d['k1_violation_rate']:.3f} k<5={d['klt5_violation_rate']:.3f}")
        else:
            print(f"  {name}: unavailable ({d.get('reason', '')[:60]}...)")


if __name__ == "__main__":
    main()
