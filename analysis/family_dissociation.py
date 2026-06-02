#!/usr/bin/env python3
"""KLU-101 — the detection≠re-id dissociation, PER TEMPLATE FAMILY.

The dissociation headline used to rest on a *single* authored RO template family — a single-family
result is not validated generalization. ``ro-realskeleton-v1`` now ships **two independent template
families** (A = official correspondence, B = academic registry; independence hard-gated in
klusai-datasets' ``make check`` via a token 5-gram Jaccard ≤ 0.10). This script confirms the
dissociation **holds within each family independently**, reported as a *difference-of-proportions*
(not two eyeballed CIs):

    per family, per typed-detector:
        gap = leak_rate(typed-detector)  −  leak_rate(protector=kp-deid)
        Newcombe (1998) hybrid-score CI on the difference of two proportions.
    The dissociation HOLDS for a family iff the gap CI EXCLUDES 0 (low > 0).

Pre-registered per-family N: ≥150–200 distinct CNP subjects so the protector-leak Wilson **upper
bound ≤ 0.02** at ≈0 leak. Per-distinct-subject ``(doc, country, normalized value)`` dedup is
inherited from the harness leak metric (no CASS-style duplicate-CNP regression, KLU-49).

Inputs
------
* ``--rows`` JSON: a list of gold rows ``{text, spans, family, ...}`` for ``ro-realskeleton-v1``,
  generated locally from klusai-datasets (``generate_combined_dataset``) so the two repos stay
  decoupled — europriv-bench never imports the dataset package. Each row MUST carry ``family``.
  (Falls back to loading the HF config when ``--rows`` is omitted and the config carries ``family``.)

Reproduce (scoring is heavy — run serial/foreground, see KLU-53 perf note)::

    # 1. dump the two-family gold rows from klusai-datasets (its venv has both packs)
    python -c "import json; from klusai.privacy.datasets.data.ro_skeletons import \\
        generate_combined_dataset; json.dump(list(generate_combined_dataset(200, seed=20260531)), \\
        open('analysis/ro_realskeleton_two_family_rows.json','w'), ensure_ascii=False)"

    # 2. score every board model per family + emit the per-family gap table (europriv-bench venv)
    python analysis/family_dissociation.py \\
        --rows analysis/ro_realskeleton_two_family_rows.json \\
        --adapter kp-model --adapter privacy-filter --adapter openmed --adapter tabularisai \\
        --adapter gliner --adapter gliner2 --adapter spacy --adapter presidio \\
        --outdir analysis
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from europriv_bench.metrics import newcombe_diff_ci, wilson_interval

CONFIG = "ro-realskeleton-v1"
PROTECTOR = "kp-model"  # the de-id protector (kp-deid) — the 0-leak arm of every gap


# --------------------------------------------------------------------------- #
# Statistics (no models / no scoring — unit-testable in isolation)
# --------------------------------------------------------------------------- #
def family_gap(detector: dict, protector: dict) -> dict:
    """One per-family gap row: gap = leak_rate(detector) − leak_rate(protector) + Newcombe CI.

    ``detector`` / ``protector`` are per-family leak summaries
    ``{"adapter", "missed", "total", "leak_rate"}`` (missed/total are distinct-subject counts). The
    difference-of-proportions CI is Newcombe's hybrid-score interval; the dissociation holds for
    this (family, detector) iff ``ci_low > 0``.
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


def family_dissociation(family_leaks: dict[str, dict]) -> dict:
    """Build all gap rows for one family: protector vs every OTHER model that leaks something.

    ``family_leaks`` maps adapter -> leak summary for ONE family. The protector is ``kp-model``.
    Each non-protector model is a "typed-detector" arm of the dissociation; a model that itself
    reaches 0 leak yields a gap whose CI may include 0 (reported honestly, not gamed)."""
    protector = family_leaks[PROTECTOR]
    prot_low, prot_high = wilson_interval(protector["missed"], protector["total"])
    gaps = [family_gap(family_leaks[a], protector)
            for a in sorted(family_leaks) if a != PROTECTOR]
    # The dissociation "holds for the family" if it holds for at least one typed-detector arm
    # (some content-NER detector leaks significantly more than the protector).
    return {
        "protector": PROTECTOR,
        "protector_leak_rate": protector["leak_rate"],
        "protector_missed": protector["missed"],
        "protector_total": protector["total"],
        "protector_leak_wilson_low": prot_low,
        "protector_leak_wilson_high": prot_high,  # pre-registered N target: ≤ 0.02
        "gaps": gaps,
        "holds": any(g["dissociation_holds"] for g in gaps),
    }


# --------------------------------------------------------------------------- #
# Scoring (loads gold rows, runs each adapter per family) — needs model backends
# --------------------------------------------------------------------------- #
def _load_rows(rows_path: Path | None) -> list[dict]:
    if rows_path is not None:
        rows = json.loads(rows_path.read_text(encoding="utf-8"))
        if not rows or "family" not in rows[0]:
            raise SystemExit(f"{rows_path}: rows must carry a 'family' tag (regen with KLU-101 generator)")
        return rows
    # Fallback: HF config (only usable once the family-tagged config is published).
    from datasets import load_dataset
    ds = load_dataset("klusai/europriv-bench", CONFIG, split="test")
    rows = [dict(r) for r in ds]
    if not rows or "family" not in rows[0]:
        raise SystemExit(f"HF config {CONFIG} has no 'family' tag; pass --rows with locally-generated rows")
    return rows


def _score_family(rows: list[dict], adapters: list[str]) -> dict[str, dict]:
    """Score every adapter on one family's rows → adapter -> leak summary + F1."""
    from europriv_bench.adapters import build
    from europriv_bench.runner import run_spec
    from europriv_bench.spec import DatasetRef, EvalSpec, Task

    spec = EvalSpec(
        name="ro-realskeleton-family",
        task=Task.DETECTION,
        languages=["ro"],
        domain="legal",
        dataset=DatasetRef(hf_id="klusai/europriv-bench", config=CONFIG, split="test"),
        metrics=["entity_f1", "cnp_leakage"],
    )
    out: dict[str, dict] = {}
    for name in adapters:
        model = build(name)
        res = run_spec(spec, model, rows=rows)
        cnp = res["scores"]["cnp_leakage"]
        out[name] = {
            "adapter": name,
            "model_id": res["model_id"],
            "f1": res["scores"]["entity_f1"]["f1"],
            "leak_rate": cnp["leak_rate"],
            "missed": int(cnp["cnp_missed"]),
            "total": int(cnp["cnp_total"]),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, default=None,
                    help="Local two-family gold rows JSON (each row tagged 'family'). Omit to load HF.")
    ap.add_argument("--adapter", dest="adapters", action="append", default=None,
                    help="Board adapter(s) to score; repeatable. Default = the 8 board models.")
    ap.add_argument("--outdir", type=Path, default=Path("analysis"))
    ap.add_argument("--require-hold", action="store_true",
                    help="Exit non-zero unless the dissociation holds in EVERY family (CI excludes 0).")
    args = ap.parse_args()

    adapters = args.adapters or [
        "kp-model", "privacy-filter", "openmed", "tabularisai",
        "gliner", "gliner2", "spacy", "presidio",
    ]
    if PROTECTOR not in adapters:
        raise SystemExit(f"protector {PROTECTOR!r} must be among the scored adapters")

    rows = _load_rows(args.rows)
    by_family: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_family[r["family"]].append(r)

    per_family: dict[str, dict] = {}
    for fam in sorted(by_family):
        leaks = _score_family(by_family[fam], adapters)
        genre = next((r.get("genre") for r in by_family[fam] if r.get("genre")), "")
        diss = family_dissociation(leaks)
        diss["genre"] = genre
        diss["n_docs"] = len(by_family[fam])
        diss["models"] = leaks
        per_family[fam] = diss

    all_hold = all(d["holds"] for d in per_family.values())
    payload = {
        "config": CONFIG,
        "families": per_family,
        "dissociation_holds_across_all_families": all_hold,
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    out_json = args.outdir / "family_dissociation_ro_realskeleton.json"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Markdown report (human / paper).
    lines = [
        f"# Per-family detection≠re-id dissociation — `{CONFIG}` (KLU-101)",
        "",
        "Difference-of-proportions per family: **gap = leak_rate(typed-detector) − "
        "leak_rate(protector=kp-deid)**, with a Newcombe (1998) hybrid-score CI on the difference. "
        "The dissociation **holds** for a family iff a typed-detector's gap CI **excludes 0** "
        "(`low > 0`). Per-distinct-subject `(doc, country, value)` dedup (KLU-49).",
        "",
        f"**Dissociation holds across BOTH families: {'YES' if all_hold else 'NO'}.**",
        "",
    ]
    for fam, d in per_family.items():
        lines += [
            f"## Family {fam} — {d['genre']}  (n={d['n_docs']} docs)",
            "",
            f"Protector (kp-deid) leak-rate {d['protector_leak_rate']:.4f} over {d['protector_total']} "
            f"distinct CNP subjects; 95% Wilson upper bound **{d['protector_leak_wilson_high']:.4f}** "
            f"(pre-registered target ≤ 0.02). Dissociation holds in this family: "
            f"**{'YES' if d['holds'] else 'NO'}**.",
            "",
            "| typed-detector | detector leak | protector leak | gap | Newcombe 95% CI | excludes 0 |",
            "|---|---:|---:|---:|:--:|:--:|",
        ]
        for g in d["gaps"]:
            lines.append(
                f"| {g['detector']} | {g['detector_leak_rate']:.4f} ({g['detector_missed']}/{g['detector_total']}) "
                f"| {g['protector_leak_rate']:.4f} ({g['protector_missed']}/{g['protector_total']}) "
                f"| {g['gap']:+.4f} | [{g['gap_ci_low']:+.4f}, {g['gap_ci_high']:+.4f}] "
                f"| {'YES' if g['dissociation_holds'] else 'no'} |"
            )
        lines.append("")
    out_md = args.outdir / "family_dissociation_ro_realskeleton.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote {out_json} and {out_md}")
    print(f"dissociation holds across all families: {all_hold}")
    for fam, d in per_family.items():
        print(f"  family {fam} ({d['genre']}): holds={d['holds']} "
              f"protector_leak_UB={d['protector_leak_wilson_high']:.4f}")

    if args.require_hold and not all_hold:
        raise SystemExit("dissociation does NOT hold in every family")


if __name__ == "__main__":
    main()
