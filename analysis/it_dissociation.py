#!/usr/bin/env python3
"""KLU-105 — the detection≠re-id dissociation on IT (codice fiscale), 3rd identifier + language.

The third decode-bearing measurement, after RO/CNP (``ro-realskeleton-v1``) and PL/PESEL
(``pl-realskeleton-v1``). The codice fiscale is the **richest** of the three: a missed (un-redacted)
CF deterministically discloses DATE_OF_BIRTH + SEX + **PLACE_OF_BIRTH** (the Belfiore comune/country
of birth), decoded with omocodia reversed and place resolved against the pinned Belfiore snapshot. So
the disclosure surface — and the leaked-quasi-identifier count — is larger here than for CNP/PESEL.

``it-realskeleton-v1`` ships **one authored template family for now** (a 2nd independent IT family is
required before citing — the KLU-101 RO hardening, replicated for IT), so this reports the
dissociation as a **per-typed-detector difference-of-proportions** on that single family:

    per typed-detector:
        gap = leak_rate(typed-detector)  −  leak_rate(protector=kp-deid)
        Newcombe (1998) hybrid-score CI on the difference of two INDEPENDENT proportions.
    The dissociation HOLDS for a detector iff the gap CI EXCLUDES 0 (low > 0).

Pre-registered N: **300 docs → ≈224 distinct CF subjects** so the protector-leak Wilson **upper bound
≤ 0.02** at ≈0 leak (250 docs → 182 subjects → UB 0.0207, just over; 300 → 224 → 0.017). Per-distinct-
subject ``(doc, country, normalized value)`` dedup is inherited from the harness leak metric (the
discharge letter repeats the patient CF → one subject; KLU-49).

Inputs
------
* ``--rows`` JSON: a list of gold rows ``{text, spans, country, ...}`` for ``it-realskeleton-v1``,
  generated locally from klusai-datasets (``it_skeletons.generate_dataset``) so the two repos stay
  decoupled — europriv-bench never imports the dataset package. Each row MUST carry ``country='IT'``.
  (Falls back to loading the HF config when ``--rows`` is omitted.)

Reproduce (scoring is heavy — run serial/foreground)::

    # 1. dump the gold rows from klusai-datasets (its venv has the IT pack)
    python -c "import json; from klusai.privacy.datasets.data.it_skeletons import \\
        generate_dataset; json.dump(list(generate_dataset(300, seed=20260531)), \\
        open('analysis/it_realskeleton_rows.json','w'), ensure_ascii=False)"

    # 2. score every board model + emit the per-typed-detector gap table (europriv-bench venv)
    python analysis/it_dissociation.py \\
        --rows analysis/it_realskeleton_rows.json \\
        --adapter kp-model --adapter privacy-filter --adapter openmed --adapter tabularisai \\
        --adapter gliner --adapter gliner2 --adapter spacy --adapter presidio \\
        --outdir analysis
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from europriv_bench.metrics import newcombe_diff_ci, wilson_interval

CONFIG = "it-realskeleton-v1"
COUNTRY = "IT"
PROTECTOR = "kp-model"  # the de-id protector (kp-deid) — the 0-leak arm of every gap
# Pre-registered: 300 docs ≈ 224 distinct CF subjects → protector-leak Wilson UB ≈ 0.017 ≤ 0.02.
PREREGISTERED_N_DOCS = 300


# --------------------------------------------------------------------------- #
# Statistics (no models / no scoring — unit-testable in isolation)
# --------------------------------------------------------------------------- #
def detector_gap(detector: dict, protector: dict) -> dict:
    """One per-detector gap row: gap = leak_rate(detector) − leak_rate(protector) + Newcombe CI.

    ``detector`` / ``protector`` are leak summaries ``{"adapter", "missed", "total", "leak_rate"}``
    (missed/total are distinct-subject counts). The difference-of-proportions CI is Newcombe's
    hybrid-score interval; the dissociation holds for this detector iff ``ci_low > 0``.
    """
    s1, n1 = detector["missed"], detector["total"]
    s2, n2 = protector["missed"], protector["total"]
    diff, low, high = newcombe_diff_ci(s1, n1, s2, n2)
    return {
        "detector": detector["adapter"],
        "detector_leak_rate": (s1 / n1) if n1 else 0.0,
        "detector_missed": s1,
        "detector_total": n1,
        "protector": protector["adapter"],
        "protector_leak_rate": (s2 / n2) if n2 else 0.0,
        "protector_missed": s2,
        "protector_total": n2,
        "gap": diff,
        "gap_ci_low": low,
        "gap_ci_high": high,
        "dissociation_holds": low > 0.0,
    }


def dissociation(leaks: dict[str, dict]) -> dict:
    """Build all gap rows: protector vs every OTHER scored model.

    ``leaks`` maps adapter -> leak summary. The protector is ``kp-model``; each non-protector model
    is a typed-detector arm. A model that itself reaches 0 leak yields a gap whose CI may include 0
    (reported honestly, not gamed). The dissociation "holds" iff it holds for ≥1 typed-detector arm.
    """
    protector = leaks[PROTECTOR]
    prot_low, prot_high = wilson_interval(protector["missed"], protector["total"])
    gaps = [detector_gap(leaks[a], protector) for a in sorted(leaks) if a != PROTECTOR]
    return {
        "protector": PROTECTOR,
        "protector_leak_rate": protector["leak_rate"],
        "protector_missed": protector["missed"],
        "protector_total": protector["total"],
        "protector_leak_wilson_low": prot_low,
        "protector_leak_wilson_high": prot_high,  # pre-registered N target: ≤ 0.02
        "protector_leaked_quasi_identifiers": protector.get("leaked_qi", 0),
        "gaps": gaps,
        "holds": any(g["dissociation_holds"] for g in gaps),
    }


# --------------------------------------------------------------------------- #
# Scoring (loads gold rows, runs each adapter) — needs model backends
# --------------------------------------------------------------------------- #
def _load_rows(rows_path: Path | None) -> list[dict]:
    if rows_path is not None:
        rows = json.loads(rows_path.read_text(encoding="utf-8"))
        if not rows or rows[0].get("country") != COUNTRY:
            raise SystemExit(f"{rows_path}: rows must carry country='IT' (regen from it_skeletons)")
        return rows
    from datasets import load_dataset
    ds = load_dataset("klusai/europriv-bench", CONFIG, split="test")
    rows = [dict(r) for r in ds]
    if not rows or rows[0].get("country") != COUNTRY:
        raise SystemExit(f"HF config {CONFIG} rows lack country='IT'; pass --rows with local rows")
    return rows


def _score(rows: list[dict], adapters: list[str]) -> dict[str, dict]:
    """Score every adapter on the IT rows → adapter -> leak summary + F1."""
    from europriv_bench.adapters import build
    from europriv_bench.runner import run_spec
    from europriv_bench.spec import DatasetRef, EvalSpec, Task

    spec = EvalSpec(
        name="it-realskeleton",
        task=Task.DETECTION,
        languages=["it"],
        domain="legal",
        dataset=DatasetRef(hf_id="klusai/europriv-bench", config=CONFIG, split="test"),
        metrics=["entity_f1", "national_id_leakage"],
    )
    out: dict[str, dict] = {}
    for name in adapters:
        model = build(name)
        res = run_spec(spec, model, rows=rows)
        nid = res["scores"]["national_id_leakage"]
        out[name] = {
            "adapter": name,
            "model_id": res["model_id"],
            "f1": res["scores"]["entity_f1"]["f1"],
            "leak_rate": nid["leak_rate"],
            "missed": int(nid["decode_bearing_missed"]),
            "total": int(nid["decode_bearing_total"]),
            "leaked_qi": int(nid["leaked_quasi_identifiers"]),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, default=None,
                    help="Local IT gold rows JSON (each row country='IT'). Omit to load HF.")
    ap.add_argument("--adapter", dest="adapters", action="append", default=None,
                    help="Board adapter(s) to score; repeatable. Default = the 8 board models.")
    ap.add_argument("--outdir", type=Path, default=Path("analysis"))
    ap.add_argument("--require-hold", action="store_true",
                    help="Exit non-zero unless the dissociation holds (a gap CI excludes 0).")
    args = ap.parse_args()

    adapters = args.adapters or [
        "kp-model", "privacy-filter", "openmed", "tabularisai",
        "gliner", "gliner2", "spacy", "presidio",
    ]
    if PROTECTOR not in adapters:
        raise SystemExit(f"protector {PROTECTOR!r} must be among the scored adapters")

    rows = _load_rows(args.rows)
    leaks = _score(rows, adapters)
    diss = dissociation(leaks)
    diss["n_docs"] = len(rows)
    diss["models"] = leaks

    payload = {"config": CONFIG, "country": COUNTRY, "dissociation": diss}
    args.outdir.mkdir(parents=True, exist_ok=True)
    out_json = args.outdir / "it_dissociation.json"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Markdown report (human / paper).
    lines = [
        f"# detection≠re-id dissociation — `{CONFIG}` (KLU-105, codice fiscale)",
        "",
        "The THIRD decode-bearing identifier + language (after RO/CNP and PL/PESEL). A missed codice "
        "fiscale discloses **DATE_OF_BIRTH + SEX + PLACE_OF_BIRTH** (Belfiore comune/country, omocodia "
        "reversed) — the richest of the three. Difference-of-proportions: **gap = leak_rate("
        "typed-detector) − leak_rate(protector=kp-deid)**, Newcombe (1998) hybrid-score CI; the "
        "dissociation **holds** iff a typed-detector's gap CI **excludes 0** (`low > 0`). "
        "Per-distinct-subject `(doc, country=IT, value)` dedup (KLU-49); the discharge letter repeats "
        "the patient CF → one subject.",
        "",
        f"**Dissociation holds on IT: {'YES' if diss['holds'] else 'NO'}.**",
        "",
        f"Protector (kp-deid) leak-rate {diss['protector_leak_rate']:.4f} over "
        f"{diss['protector_total']} distinct codice-fiscale subjects "
        f"(n={diss['n_docs']} docs; pre-registered ≥{PREREGISTERED_N_DOCS}); 95% Wilson upper bound "
        f"**{diss['protector_leak_wilson_high']:.4f}** (pre-registered target ≤ 0.02). Place-of-birth "
        "is counted in the disclosed quasi-identifiers (3 QIs per leaked CF: DOB + SEX + "
        "PLACE_OF_BIRTH).",
        "",
        "| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |",
        "|---|---:|---:|---:|:--:|:--:|",
    ]
    for g in diss["gaps"]:
        lines.append(
            f"| {g['detector']} | {g['detector_leak_rate']:.4f} ({g['detector_missed']}/{g['detector_total']}) "
            f"| {g['protector_leak_rate']:.4f} ({g['protector_missed']}/{g['protector_total']}) "
            f"| {g['gap']:+.4f} | [{g['gap_ci_low']:+.4f}, {g['gap_ci_high']:+.4f}] "
            f"| {'YES' if g['dissociation_holds'] else 'no'} |"
        )
    lines.append("")
    out_md = args.outdir / "it_dissociation.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote {out_json} and {out_md}")
    print(f"dissociation holds on IT: {diss['holds']} "
          f"(protector_leak_UB={diss['protector_leak_wilson_high']:.4f}, "
          f"subjects={diss['protector_total']})")

    if args.require_hold and not diss["holds"]:
        raise SystemExit("dissociation does NOT hold on IT")


if __name__ == "__main__":
    main()
