"""Controls for candidate defaults, exact replay and versioned acceptance."""

import pytest

from analysis.calibrate_res100 import receipt
from analysis.score_gateway_moe import evaluate, immutable
from analysis.score_res100 import row_digest


def test_gateway_keeps_colliding_gold_and_exact_coverage():
    rows = [
        {
            "text": "Ann/123 ok",
            "spans": [
                {"start": 0, "end": 3, "label": "PERSON", "entity_id": "a", "identifier_type": "DIRECT"},
                {"start": 4, "end": 7, "label": "CASE_NUMBER", "entity_id": "b", "identifier_type": "DIRECT"},
            ],
        }
    ]
    frozen = {
        "rows": rows,
        "dataset": {"loader": "gateway"},
        "spec": {
            "name": "control",
            "task": "detection",
            "dataset": {"hf_id": "test", "loader": "gateway"},
            "metrics": ["residual_leakage_v2", "gateway_utility"],
        },
    }
    rec = receipt(rows[0]["text"], [{"start": 0, "end": 2, "label": "S-PERSON", "score": 0.01}])
    result = evaluate(frozen, [rec], "kp-deid-moe-gateway", 0, {"gold_sha256": row_digest(rows)})
    assert result["row"]["scores"]["residual_leakage_v2"]["all_subjects_leaked"] == 2
    assert result["counts"]["over_redaction"] == [[0, 3]]
    assert result["row"]["uncertainty"]["bootstrap_unit"] == "conversation"
    assert "entity_f1_and_legacy" in result["row"]["metric_unavailability"]
    assert rec["intervals"] == [[0, 2]]  # Low confidence still retained at the default point.
    with pytest.raises(ValueError, match="Incomplete"):
        evaluate(frozen, [], "candidate", 0, {"gold_sha256": row_digest(rows)})
    with pytest.raises(ValueError, match="mismatched"):
        evaluate(frozen, [rec], "candidate", 0, {"gold_sha256": "different"})


def test_immutable_resume_rejects_changed_pins(tmp_path):
    path = tmp_path / "pin.json"
    immutable(path, {"gold": "a"})
    immutable(path, {"gold": "a"})
    with pytest.raises(ValueError, match="Frozen identity"):
        immutable(path, {"gold": "b"})


def test_v3_boundary_pass_is_not_an_overall_win():
    from analysis.report_gateway_moe import comparison

    def result(leak, removed):
        return {
            "row": {
                "n": 2,
                "dataset": {"loader": "gateway"},
                "inference_provenance": {"gold_sha256": "same"},
                "scores": {
                    "residual_leakage_v2": {
                        "all_available": 1,
                        "all_leak_rate_ci_low": leak,
                        "all_leak_rate_ci_high": leak,
                    }
                },
            },
            "counts": {"v2_all": [[leak, 1], [leak, 1]], "over_redaction": [[removed, 100], [removed, 100]]},
        }

    output = comparison(result(0, 1), result(1, 0))
    assert output["unit"] == "conversation"
    assert output["contracts"]["3"]["numerical_pass"]
    assert output["contracts"]["3"]["verdict"] == "not established"
    assert output["contracts"]["2"]["verdict"] == "loss: over-redaction regression"
    assert not comparison(result(0, 2), result(1, 0))["contracts"]["3"]["numerical_pass"]
