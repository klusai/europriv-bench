"""RES-86 — the consolidated multi-language dissociation summary builder.

Covers the *re-derivation* logic (no model backends, no scoring): the per-row gap-CI tally counts
how many scored typed-detectors have a Newcombe gap CI excluding 0, the RO two-family aggregation
sums detector arms and takes the worst-case Wilson UB, PL is reported as a coverage gap (not
fabricated), and the assembled summary re-derives byte-for-byte from the committed artifacts so the
committed dissociation_summary.{md,json} stay regenerable (the --check contract).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ANALYSIS = Path(__file__).resolve().parent.parent / "analysis"
_SPEC = importlib.util.spec_from_file_location(
    "build_dissociation_summary", _ANALYSIS / "build_dissociation_summary.py"
)
bds = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bds)


def _diss(gaps, prot_ub=0.017, models=("kp-model", "gliner", "gliner2")):
    return {
        "protector_leak_rate": 0.0,
        "protector_leak_wilson_high": prot_ub,
        "protector_missed": 0,
        "protector_total": 221,
        "protector_leaked_quasi_identifiers": 0,
        "gaps": gaps,
        "holds": any(g["dissociation_holds"] for g in gaps),
        "n_docs": 300,
        "models": {m: {} for m in models},
    }


def test_summarize_counts_only_detectors_whose_ci_excludes_zero():
    diss = _diss([
        {"detector": "gliner", "dissociation_holds": True},
        {"detector": "gliner2", "dissociation_holds": True},
        {"detector": "privacy-filter", "dissociation_holds": False},
    ])
    s = bds.summarize_dissociation(diss)
    assert s["n_detectors_scored"] == 3
    assert s["n_detectors_gap_ci_excludes_0"] == 2
    assert s["holds"] is True
    assert "kp-model" in s["models_scored"]  # the protector is listed under models scored


def test_ro_family_aggregation_sums_arms_and_takes_worst_case_ub():
    payload = {
        "families": {
            "A": _diss([{"detector": "g", "dissociation_holds": True}], prot_ub=0.0198),
            "B": _diss([
                {"detector": "g", "dissociation_holds": True},
                {"detector": "h", "dissociation_holds": True},
            ], prot_ub=0.0151),
        },
        "dissociation_holds_across_all_families": True,
    }
    agg = bds.summarize_ro_families(payload)
    assert agg["protector_leak_wilson_high"] == 0.0198  # worst-case across families
    assert agg["holds"] is True
    holds = sum(f["n_detectors_gap_ci_excludes_0"] for f in agg["families"].values())
    scored = sum(f["n_detectors_scored"] for f in agg["families"].values())
    assert (holds, scored) == (3, 3)


def test_build_summary_covers_eleven_langs_all_with_committed_artifacts():
    summary = bds.build_summary()
    assert summary["n_languages"] == 11
    assert summary["language_order"][0] == "RO"  # the original anchor leads
    # RES-87: PL/PESEL now ships a committed pl_dissociation.json scored on pl-realskeleton-v1 —
    # the earlier coverage gap is closed, so all 11 decode-bearing languages have a real artifact.
    pl = summary["languages"]["PL"]
    assert pl["artifact"] == "pl_dissociation.json"
    assert pl["config"] == "pl-realskeleton-v1"
    assert pl["id_name"] == "PESEL"
    assert pl["holds"] is not None
    assert pl["protector_leak_rate"] is not None
    assert pl["protector_leak_wilson_high"] is not None
    assert "MISSING ARTIFACT" not in (pl.get("note") or "")
    assert summary["n_languages_artifact_present"] == 11
    # Legal + name-in-context are separate sections, both present.
    assert summary["legal_domain"]["domain"] == "legal"
    assert summary["name_in_context"]["models_scored"]
    # Re-id reserved for the national-ID channel: name-in-context is residual distinctiveness only.
    assert summary["name_in_context"]["k_anonymity_available"] is False


def test_caveats_carry_the_required_disciplines():
    blob = " ".join(bds.build_summary()["caveats"]).lower()
    for needle in ("config_status=dev", "single authored", "coverage varies",
                   "res-53", "first *unified*", "residual distinctiveness"):
        assert needle.lower() in blob, needle


def test_coverage_is_uniform_full_model_basis_res96():
    # RES-96: every decode-bearing language + legal scores the SAME board-model basis. The summary
    # derives that basis from the committed artifacts (intersection of per-language models_scored).
    summary = bds.build_summary()
    assert summary["coverage_is_uniform"] is True
    # kp-deid (the protector) plus the seven typed detectors — the full 8-model board.
    assert "kp-model" in summary["uniform_model_basis"]
    assert len(summary["uniform_model_basis"]) == 8
    # Every language row (and legal) scores exactly that basis — no language is a subset.
    basis = set(summary["uniform_model_basis"])
    for cc in summary["language_order"]:
        assert set(summary["languages"][cc]["models_scored"]) == basis, cc
    assert set(summary["legal_domain"]["models_scored"]) == basis
    # The caveat narrates the closed gap (RES-96 ran the re-score the RES-53 GPU gate had blocked).
    blob = " ".join(summary["caveats"]).lower()
    assert "uniform" in blob and "res-96" in blob


def test_committed_summary_files_are_regenerable():
    summary = bds.build_summary()
    fresh_json = json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    fresh_md = bds.render_markdown(summary)
    assert (_ANALYSIS / "dissociation_summary.json").read_text(encoding="utf-8") == fresh_json
    assert (_ANALYSIS / "dissociation_summary.md").read_text(encoding="utf-8") == fresh_md
