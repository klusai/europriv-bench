"""Safety controls for dev selection, exact threshold coverage and test isolation."""

import pytest

from analysis.calibrate_res100 import receipt, select, validate_freeze
from analysis.score_res100 import write
from europriv_bench.metrics import residual_leakage_v2


def test_threshold_boundary_does_not_expand_partial_identifiers():
    entities = [
        {"start": 0, "end": 4, "label": "S-PERSON", "score": 0.9},
        {"start": 5, "end": 10, "label": "E-PERSON", "score": 0.8},
    ]
    row = {"text": "John Smith", "spans": [{"start": 0, "end": 10, "label": "PERSON"}]}
    kept = receipt(row["text"], entities, 0.9)
    assert kept["intervals"] == [[0, 4]]
    assert kept["output"] == "█ Smith"
    assert residual_leakage_v2([row], [kept["intervals"]])["all_leak_rate"] == 1
    assert receipt(row["text"], entities, 1.000001)["intervals"] == []


def test_invalid_confidence_and_native_offsets_fail_closed():
    for score in (float("nan"), -1, 2):
        with pytest.raises(ValueError, match="confidence"):
            receipt("John", [{"start": 0, "end": 4, "label": "PERSON", "score": score}])
    with pytest.raises(ValueError):
        receipt("John", [{"start": 0, "end": 5, "label": "PERSON", "score": 1}])


def test_selection_rejects_infeasible_privacy_leader_and_breaks_ties():
    grid = [
        {"threshold": 0, "macro_leak": 0, "macro_utility": 0.2, "feasible": False},
        {"threshold": 0.8, "macro_leak": 0.2, "macro_utility": 0.1, "feasible": True},
        {"threshold": 0.9, "macro_leak": 0.2, "macro_utility": 0.05, "feasible": True},
        {"threshold": 0.95, "macro_leak": 0.2, "macro_utility": 0.05, "feasible": True},
    ]
    assert select(grid) == 0.9
    with pytest.raises(ValueError, match="feasible"):
        select(grid[:1])


def test_test_phase_requires_freeze_and_rejects_protocol_drift(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_freeze(tmp_path)
    write(tmp_path / "calibration-freeze.json", {"protocol_sha256": "wrong"})
    with pytest.raises(ValueError, match="protocol"):
        validate_freeze(tmp_path)


def test_paired_privacy_improvement_cannot_hide_utility_regression():
    from analysis.report_res100_calibration import gates

    def result(leak, removed):
        return {
            "row": {
                "n": 2,
                "inference_provenance": {"gold_sha256": "same"},
                "scores": {
                    "residual_leakage_v2": {
                        "all_available": 1,
                        "all_leak_rate_ci_low": leak,
                        "all_leak_rate_ci_high": leak,
                    }
                },
            },
            "counts": {"v2_all": [[int(leak), 1], [int(leak), 1]], "over_redaction": [[removed, 100], [removed, 100]]},
        }

    verdict = gates(result(0, 1), result(1, 0))
    assert verdict["numerical_gates"]["disjoint_wilson"]
    assert verdict["numerical_gates"]["paired_privacy"]
    assert not verdict["numerical_gates"]["no_worse_utility"]
    assert verdict["verdict"] == "loss: over-redaction regression"
    # Numerically passing is still not a contract win without review/disjointness.
    assert gates(result(0, 0), result(1, 0))["verdict"] == "not established"
