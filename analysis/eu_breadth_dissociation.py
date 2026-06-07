#!/usr/bin/env python3
"""RES-80/RES-83 — the detection≠re-id dissociation on SE/CZ (RES-80) and DK/FI (RES-83).

The 4th–7th decode-bearing measurements, after RO/CNP, PL/PESEL and IT/codice-fiscale. Each
extends the headline to a NEW identifier in a NEW language:

  * SE personnummer — a missed (un-redacted) number discloses SEX + DATE_OF_BIRTH (birth month +
    day; the bare 10-digit form's century is carried only by the printed separator).
  * CZ rodné číslo  — a missed number discloses SEX + DATE_OF_BIRTH (the modern 10-digit form is
    fully date-recoverable, female month +50, YY-century convention).
  * DK CPR-nummer   — a missed number discloses SEX + DATE_OF_BIRTH (full date; century from the
    7th-digit/YY table — the mod-11 check was abolished in 2007, so we validate format + table).
  * FI henkilötunnus — a missed number discloses SEX + DATE_OF_BIRTH (full date; century from the
    marker; mod-31 control char over the 31-char map).

Each config ships **one authored template family for now** (a 2nd independent family is required
before citing — the KLU-101 hardening), so this reports the dissociation as a **per-typed-detector
difference-of-proportions** on that single family, identical in form to ``it_dissociation``:

    per typed-detector:
        gap = leak_rate(typed-detector)  −  leak_rate(protector=kp-deid)
        Newcombe (1998) hybrid-score CI on the difference of two INDEPENDENT proportions.
    The dissociation HOLDS for a detector iff the gap CI EXCLUDES 0 (low > 0).

Per-distinct-subject ``(doc, country, normalized value)`` dedup is inherited from the harness leak
metric (the discharge/epikris note repeats the patient ID → one subject; KLU-49). A **null is still
a finding**: if no typed detector separates from kp-deid on a language, we report that honestly.

Inputs
------
* ``--rows`` JSON: gold rows ``{text, spans, country, ...}`` for the config, generated locally from
  klusai-datasets (``se_skeletons`` / ``cz_skeletons``) so the two repos stay decoupled —
  europriv-bench never imports the dataset package. Each row MUST carry the right ``country``.
  (Falls back to loading the HF config when ``--rows`` is omitted.)

Reproduce (scoring is heavy — run serial/foreground)::

    # 1. dump the gold rows from klusai-datasets (its venv has the SE/CZ packs)
    python -c "import json; from klusai.privacy.datasets.data.se_skeletons import \\
        generate_dataset; json.dump(list(generate_dataset(300, seed=20260606)), \\
        open('analysis/se_realskeleton_rows.json','w'), ensure_ascii=False)"

    # 2. score every board model + emit the per-typed-detector gap table (europriv-bench venv)
    python analysis/eu_breadth_dissociation.py --country SE \\
        --rows analysis/se_realskeleton_rows.json \\
        --adapter kp-model --adapter privacy-filter --adapter tabularisai \\
        --adapter gliner --adapter gliner2 --outdir analysis
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from europriv_bench.metrics import newcombe_diff_ci, wilson_interval

PROTECTOR = "kp-model"  # the de-id protector (kp-deid) — the 0-leak arm of every gap
PREREGISTERED_N_DOCS = 300

# Per-country wiring: config slug + the human label for the identifier.
COUNTRIES = {
    # RES-87: PL PESEL — the original early decode-bearing measurement (after RO/CNP), backfilled
    # here onto the shared codepath so it ships a committed pl_dissociation.json like the others. A
    # missed PESEL discloses SEX + DATE_OF_BIRTH (the date digits are carried in full; the century is
    # encoded in the month field +20/+40/+60/+80 per the post-1999 convention).
    "PL": {"config": "pl-realskeleton-v1", "id_name": "PESEL", "lang": "pl",
           "qi": "SEX + DATE_OF_BIRTH (full date; century encoded in the month field)",
           "issue": "RES-87", "beyond": "RO"},
    "SE": {"config": "se-realskeleton-v1", "id_name": "personnummer", "lang": "sv",
           "qi": "SEX + DATE_OF_BIRTH (birth month + day)",
           "issue": "RES-80", "beyond": "RO/PL/IT"},
    "CZ": {"config": "cz-realskeleton-v1", "id_name": "rodné číslo", "lang": "cs",
           "qi": "SEX + DATE_OF_BIRTH (full date, modern 10-digit form)",
           "issue": "RES-80", "beyond": "RO/PL/IT"},
    # RES-83 EU-breadth batch 2: DK CPR + FI henkilötunnus (both decode-bearing → DOB + sex).
    "DK": {"config": "dk-realskeleton-v1", "id_name": "CPR-nummer", "lang": "da",
           "qi": "SEX + DATE_OF_BIRTH (full date; century from the 7th-digit/YY table)",
           "issue": "RES-83", "beyond": "RO/PL/IT/SE/CZ"},
    "FI": {"config": "fi-realskeleton-v1", "id_name": "henkilötunnus", "lang": "fi",
           "qi": "SEX + DATE_OF_BIRTH (full date; century from the marker)",
           "issue": "RES-83", "beyond": "RO/PL/IT/SE/CZ"},
    # RES-84 EU-breadth batch 3: EE isikukood + LT asmens kodas (Baltic two-pass mod-11 family;
    # both decode-bearing → DOB + sex; the century is carried by the 1st digit so DOB is full).
    "EE": {"config": "ee-realskeleton-v1", "id_name": "isikukood", "lang": "et",
           "qi": "SEX + DATE_OF_BIRTH (full date; century from the 1st digit)",
           "issue": "RES-84", "beyond": "RO/PL/IT/SE/CZ/DK/FI"},
    "LT": {"config": "lt-realskeleton-v1", "id_name": "asmens kodas", "lang": "lt",
           "qi": "SEX + DATE_OF_BIRTH (full date; century from the 1st digit)",
           "issue": "RES-84", "beyond": "RO/PL/IT/SE/CZ/DK/FI"},
    # RES-85 EU-breadth batch 3 remainder: SI EMŠO (richer surface — also REGION OF BIRTH, like the
    # IT codice-fiscale's place) + SK rodné číslo (the SAME algorithm as CZ; reuses the CZ decoder).
    "SI": {"config": "si-realskeleton-v1", "id_name": "EMŠO", "lang": "sl",
           "qi": "SEX + DATE_OF_BIRTH + REGION_OF_BIRTH (full date; ex-YU century convention)",
           "issue": "RES-85", "beyond": "RO/PL/IT/SE/CZ/DK/FI/EE/LT"},
    "SK": {"config": "sk-realskeleton-v1", "id_name": "rodné číslo", "lang": "sk",
           "qi": "SEX + DATE_OF_BIRTH (full date, modern 10-digit form; same algorithm as CZ)",
           "issue": "RES-85", "beyond": "RO/PL/IT/SE/CZ/DK/FI/EE/LT"},
}


# --------------------------------------------------------------------------- #
# Statistics (no models / no scoring — unit-testable in isolation)
# --------------------------------------------------------------------------- #
def detector_gap(detector: dict, protector: dict) -> dict:
    """One per-detector gap row: gap = leak_rate(detector) − leak_rate(protector) + Newcombe CI."""
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
    """Build all gap rows: protector vs every OTHER scored model."""
    protector = leaks[PROTECTOR]
    prot_low, prot_high = wilson_interval(protector["missed"], protector["total"])
    gaps = [detector_gap(leaks[a], protector) for a in sorted(leaks) if a != PROTECTOR]
    return {
        "protector": PROTECTOR,
        "protector_leak_rate": protector["leak_rate"],
        "protector_missed": protector["missed"],
        "protector_total": protector["total"],
        "protector_leak_wilson_low": prot_low,
        "protector_leak_wilson_high": prot_high,
        "protector_leaked_quasi_identifiers": protector.get("leaked_qi", 0),
        "gaps": gaps,
        "holds": any(g["dissociation_holds"] for g in gaps),
    }


# --------------------------------------------------------------------------- #
# Scoring (loads gold rows, runs each adapter) — needs model backends
# --------------------------------------------------------------------------- #
def _load_rows(rows_path: Path | None, country: str, config: str) -> list[dict]:
    if rows_path is not None:
        rows = json.loads(rows_path.read_text(encoding="utf-8"))
        if not rows or rows[0].get("country") != country:
            raise SystemExit(f"{rows_path}: rows must carry country='{country}'")
        return rows
    from datasets import load_dataset
    ds = load_dataset("klusai/europriv-bench", config, split="test")
    rows = [dict(r) for r in ds]
    if not rows or rows[0].get("country") != country:
        raise SystemExit(f"HF config {config} rows lack country='{country}'; pass --rows")
    return rows


def _score(rows: list[dict], adapters: list[str], country: str, config: str, lang: str) -> dict[str, dict]:
    """Score every adapter on the rows → adapter -> leak summary + F1."""
    from europriv_bench.adapters import build
    from europriv_bench.runner import run_spec
    from europriv_bench.spec import DatasetRef, EvalSpec, Task

    spec = EvalSpec(
        name=f"{country.lower()}-realskeleton",
        task=Task.DETECTION,
        languages=[lang],
        domain="legal",
        dataset=DatasetRef(hf_id="klusai/europriv-bench", config=config, split="test"),
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
    ap.add_argument("--country", required=True, choices=sorted(COUNTRIES))
    ap.add_argument("--rows", type=Path, default=None,
                    help="Local gold rows JSON (each row with the right country). Omit to load HF.")
    ap.add_argument("--adapter", dest="adapters", action="append", default=None,
                    help="Board adapter(s) to score; repeatable. Default = the 8 board models.")
    ap.add_argument("--outdir", type=Path, default=Path("analysis"))
    ap.add_argument("--require-hold", action="store_true",
                    help="Exit non-zero unless the dissociation holds (a gap CI excludes 0).")
    ap.add_argument("--merge", action="store_true",
                    help="Merge the freshly-scored --adapter(s) into the EXISTING committed "
                         "{cc}_dissociation.json (keeping its already-scored models) instead of "
                         "overwriting. Lets a fast-model pass be committed first, then the slow MoE "
                         "pair (privacy-filter, openmed) merged in (RES-96 bounded execution). The "
                         "protector may come from the existing file when not re-scored here.")
    args = ap.parse_args()

    cc = args.country
    meta = COUNTRIES[cc]
    adapters = args.adapters or [
        "kp-model", "privacy-filter", "openmed", "tabularisai",
        "gliner", "gliner2", "spacy", "presidio",
    ]

    rows = _load_rows(args.rows, cc, meta["config"])

    # In --merge mode, start from the committed models and overlay the freshly-scored adapters; the
    # protector is allowed to live in the existing file. Otherwise this run alone must carry it.
    existing: dict[str, dict] = {}
    stem = f"{cc.lower()}_dissociation"
    out_json = args.outdir / f"{stem}.json"
    if args.merge:
        if not out_json.exists():
            raise SystemExit(f"--merge: {out_json} does not exist; run a full pass first")
        existing = json.loads(out_json.read_text(encoding="utf-8"))["dissociation"]["models"]
    if PROTECTOR not in adapters and PROTECTOR not in existing:
        raise SystemExit(f"protector {PROTECTOR!r} must be scored here or present in {out_json}")

    fresh = _score(rows, adapters, cc, meta["config"], meta["lang"])
    leaks = {**existing, **fresh}  # freshly-scored adapters win on any overlap (re-score is authoritative)
    diss = dissociation(leaks)
    diss["n_docs"] = len(rows)
    diss["models"] = leaks

    payload = {"config": meta["config"], "country": cc, "dissociation": diss}
    args.outdir.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        f"# detection≠re-id dissociation — `{meta['config']}` ({meta['issue']}, {meta['id_name']})",
        "",
        f"A decode-bearing identifier + language extending the headline beyond {meta['beyond']}. A missed "
        f"{meta['id_name']} discloses **{meta['qi']}**. Difference-of-proportions: **gap = "
        f"leak_rate(typed-detector) − leak_rate(protector=kp-deid)**, Newcombe (1998) hybrid-score "
        f"CI; the dissociation **holds** iff a typed-detector's gap CI **excludes 0** (`low > 0`). "
        f"Per-distinct-subject `(doc, country={cc}, value)` dedup (KLU-49); the discharge note "
        f"repeats the patient id → one subject. A **null is still a finding**.",
        "",
        f"**Dissociation holds on {cc}: {'YES' if diss['holds'] else 'NO'}.**",
        "",
        f"Protector (kp-deid) leak-rate {diss['protector_leak_rate']:.4f} over "
        f"{diss['protector_total']} distinct {meta['id_name']} subjects "
        f"(n={diss['n_docs']} docs; pre-registered ≥{PREREGISTERED_N_DOCS}); 95% Wilson upper bound "
        f"**{diss['protector_leak_wilson_high']:.4f}** (target ≤ 0.02). kp-deid is RO-trained and has "
        f"never seen {meta['lang']} — this is a **zero-shot** transfer result.",
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
    out_md = args.outdir / f"{stem}.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote {out_json} and {out_md}")
    print(f"dissociation holds on {cc}: {diss['holds']} "
          f"(protector_leak_UB={diss['protector_leak_wilson_high']:.4f}, "
          f"subjects={diss['protector_total']})")

    if args.require_hold and not diss["holds"]:
        raise SystemExit(f"dissociation does NOT hold on {cc}")


if __name__ == "__main__":
    main()
