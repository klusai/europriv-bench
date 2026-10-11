"""Safety controls for dev selection, exact threshold coverage and test isolation."""
import pytest

from analysis.calibrate_res100 import receipt, select, validate_freeze
from analysis.score_res100 import write
from europriv_bench.metrics import residual_leakage_v2


def test_threshold_boundary_does_not_expand_partial_identifiers():
    entities = [{"start": 0, "end": 4, "label": "S-PERSON", "score": .9},
                {"start": 5, "end": 10, "label": "E-PERSON", "score": .8}]
    row = {"text": "John Smith", "spans": [{"start": 0, "end": 10, "label": "PERSON"}]}
    kept = receipt(row["text"], entities, .9)
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
        {"threshold": 0, "macro_leak": 0, "macro_utility": .2, "feasible": False},
        {"threshold": .8, "macro_leak": .2, "macro_utility": .1, "feasible": True},
        {"threshold": .9, "macro_leak": .2, "macro_utility": .05, "feasible": True},
        {"threshold": .95, "macro_leak": .2, "macro_utility": .05, "feasible": True},
    ]
    assert select(grid) == .9
    with pytest.raises(ValueError, match="feasible"):
        select(grid[:1])


def test_test_phase_requires_freeze_and_rejects_protocol_drift(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_freeze(tmp_path)
    write(tmp_path / "calibration-freeze.json", {"protocol_sha256": "wrong"})
    with pytest.raises(ValueError, match="protocol"):
        validate_freeze(tmp_path)
