"""RES-80/RES-83 — SE/CZ/DK/FI difference-of-proportions dissociation logic in the analysis script.

Covers the *statistics* only (no model backends): the per-detector gap = leak(detector) −
leak(protector), the Newcombe CI on the difference, and the "holds iff CI excludes 0" verdict on
the single SE/CZ/DK/FI template family. A null (no detector separates) is asserted to report as NO.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "eu_breadth_dissociation",
    Path(__file__).resolve().parent.parent / "analysis" / "eu_breadth_dissociation.py",
)
ebd = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ebd)


def _leak(adapter, missed, total, leaked_qi=None):
    return {"adapter": adapter, "missed": missed, "total": total,
            "leak_rate": (missed / total) if total else 0.0,
            "leaked_qi": leaked_qi if leaked_qi is not None else missed * 2}


def test_countries_cover_se_cz_dk_fi_ee_lt():
    assert set(ebd.COUNTRIES) == {"SE", "CZ", "DK", "FI", "EE", "LT"}
    assert ebd.COUNTRIES["SE"]["config"] == "se-realskeleton-v1"
    assert ebd.COUNTRIES["CZ"]["config"] == "cz-realskeleton-v1"
    assert ebd.COUNTRIES["DK"]["config"] == "dk-realskeleton-v1"
    assert ebd.COUNTRIES["FI"]["config"] == "fi-realskeleton-v1"
    # RES-84: EE isikukood + LT asmens kodas (Baltic two-pass mod-11 family).
    assert ebd.COUNTRIES["EE"]["config"] == "ee-realskeleton-v1"
    assert ebd.COUNTRIES["LT"]["config"] == "lt-realskeleton-v1"


def test_detector_gap_excludes_zero_when_detector_leaks_and_protector_does_not():
    g = ebd.detector_gap(_leak("gliner", 90, 224), _leak("kp-model", 0, 224))
    assert g["gap"] > 0
    assert g["gap_ci_low"] > 0          # CI excludes 0 → dissociation holds for this detector
    assert g["dissociation_holds"] is True


def test_detector_gap_includes_zero_when_both_protect():
    g = ebd.detector_gap(_leak("privacy-filter", 1, 224), _leak("kp-model", 0, 224))
    assert g["gap_ci_low"] <= 0.0 <= g["gap_ci_high"]
    assert g["dissociation_holds"] is False


def test_dissociation_holds_if_any_detector_arm_excludes_zero():
    leaks = {
        "kp-model": _leak("kp-model", 0, 224),
        "gliner": _leak("gliner", 90, 224),
        "privacy-filter": _leak("privacy-filter", 1, 224),
    }
    d = ebd.dissociation(leaks)
    assert d["holds"] is True
    holds_by_det = {g["detector"]: g["dissociation_holds"] for g in d["gaps"]}
    assert holds_by_det["gliner"] is True
    assert holds_by_det["privacy-filter"] is False
    assert "kp-model" not in holds_by_det  # the protector is not a gap row


def test_dissociation_reports_null_when_no_detector_separates():
    # A NULL result is still a finding: if every detector also protects, holds=False (reported).
    leaks = {
        "kp-model": _leak("kp-model", 1, 224),
        "presidio": _leak("presidio", 1, 224),
        "spacy": _leak("spacy", 2, 224),
    }
    d = ebd.dissociation(leaks)
    assert d["holds"] is False
