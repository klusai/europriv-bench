"""KLU-111 — legal-domain (CNP) difference-of-proportions dissociation logic in the analysis script.

Covers the *statistics* only (no model backends): the per-detector gap = leak(detector) −
leak(protector), the Newcombe CI on the difference, and the "holds iff CI excludes 0" verdict on the
single legal template family (legal-realskeleton-v1).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "legal_dissociation",
    Path(__file__).resolve().parent.parent / "analysis" / "legal_dissociation.py",
)
lgd = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(lgd)


def _leak(adapter, missed, total, leaked_qi=None):
    return {"adapter": adapter, "missed": missed, "total": total,
            "leak_rate": (missed / total) if total else 0.0,
            "leaked_qi": leaked_qi if leaked_qi is not None else missed * 3}


def test_detector_gap_excludes_zero_when_detector_leaks_and_protector_does_not():
    g = lgd.detector_gap(_leak("gliner", 600, 1500), _leak("kp-model", 0, 1500))
    assert g["gap"] > 0
    assert g["gap_ci_low"] > 0          # CI excludes 0
    assert g["dissociation_holds"] is True


def test_detector_gap_includes_zero_when_both_protect():
    g = lgd.detector_gap(_leak("privacy-filter", 1, 1500), _leak("kp-model", 0, 1500))
    assert g["gap_ci_low"] <= 0.0 <= g["gap_ci_high"]
    assert g["dissociation_holds"] is False


def test_dissociation_holds_if_any_detector_arm_excludes_zero():
    leaks = {
        "kp-model": _leak("kp-model", 0, 1500),             # protector — 0/1500
        "gliner": _leak("gliner", 600, 1500),               # leaks → gap CI excludes 0
        "privacy-filter": _leak("privacy-filter", 1, 1500),  # ~0 → gap includes 0
    }
    d = lgd.dissociation(leaks)
    assert d["holds"] is True
    holds_by_det = {g["detector"]: g["dissociation_holds"] for g in d["gaps"]}
    assert holds_by_det["gliner"] is True
    assert holds_by_det["privacy-filter"] is False
    # Pre-registered N target: protector Wilson upper bound ≤ 0.02 at 0 leak over 1500 subjects.
    assert d["protector_leak_wilson_high"] < 0.02
    assert "kp-model" not in holds_by_det  # the protector is not a gap row


def test_dissociation_does_not_hold_when_no_detector_separates():
    leaks = {
        "kp-model": _leak("kp-model", 1, 1500),
        "presidio": _leak("presidio", 1, 1500),
    }
    d = lgd.dissociation(leaks)
    assert d["holds"] is False
