"""KLU-101 — per-family difference-of-proportions dissociation logic in the analysis script.

Covers the *statistics* only (no model backends): the per-family gap = leak(detector) −
leak(protector), the Newcombe CI on the difference, and the "holds iff CI excludes 0" verdict.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "family_dissociation",
    Path(__file__).resolve().parent.parent / "analysis" / "family_dissociation.py",
)
fd = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fd)


def _leak(adapter, missed, total):
    return {"adapter": adapter, "missed": missed, "total": total,
            "leak_rate": (missed / total) if total else 0.0}


def test_family_gap_excludes_zero_when_detector_leaks_and_protector_does_not():
    g = fd.family_gap(_leak("gliner", 40, 200), _leak("kp-model", 0, 200))
    assert g["gap"] > 0
    assert g["gap_ci_low"] > 0          # CI excludes 0
    assert g["dissociation_holds"] is True


def test_family_gap_includes_zero_when_both_protect():
    g = fd.family_gap(_leak("presidio", 0, 200), _leak("kp-model", 0, 200))
    assert g["gap"] == 0.0
    assert g["gap_ci_low"] <= 0.0 <= g["gap_ci_high"]
    assert g["dissociation_holds"] is False


def test_family_dissociation_holds_if_any_detector_arm_excludes_zero():
    leaks = {
        "kp-model": _leak("kp-model", 0, 200),     # protector
        "gliner": _leak("gliner", 35, 200),        # leaks a lot → gap CI excludes 0
        "presidio": _leak("presidio", 0, 200),     # also protects → gap includes 0
    }
    d = fd.family_dissociation(leaks)
    assert d["holds"] is True
    holds_by_det = {g["detector"]: g["dissociation_holds"] for g in d["gaps"]}
    assert holds_by_det["gliner"] is True
    assert holds_by_det["presidio"] is False
    # Protector Wilson upper bound is the pre-registered N target (≤0.02 at n=200, 0 leak).
    assert d["protector_leak_wilson_high"] < 0.02
    # The protector itself is not a gap row.
    assert "kp-model" not in holds_by_det


def test_family_dissociation_does_not_hold_when_no_detector_separates():
    leaks = {
        "kp-model": _leak("kp-model", 1, 200),
        "presidio": _leak("presidio", 1, 200),
    }
    d = fd.family_dissociation(leaks)
    assert d["holds"] is False
