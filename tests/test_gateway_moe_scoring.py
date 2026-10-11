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
    old = result(0, 0)
    old["row"]["dataset"] = {"config": "legacy-without-loader"}
    assert comparison(old, result(1, 0))["unit"] == "document"


def test_incomplete_seed_cannot_overwrite_leaderboard(tmp_path, monkeypatch):
    from analysis import report_gateway_moe
    from analysis.score_res100 import write

    write(tmp_path / "availability.json", {"configs": ["missing"], "unavailable": []})
    write(tmp_path / "results/seed0--other.json", {})
    monkeypatch.setattr(report_gateway_moe, "ROOT", tmp_path)
    board = tmp_path / "baselines/leaderboard.json"
    write(board, {"entries": {"historical": [{"keep": True}]}})
    original = board.read_bytes()
    with pytest.raises(ValueError, match="incomplete seed"):
        report_gateway_moe.report(tmp_path, splice=True)
    assert board.read_bytes() == original


def test_three_seed_gate_requires_every_seed_on_the_same_endpoint():
    from analysis.report_gateway_moe import COMPARATORS, seed_summary

    def record(seed, passed):
        return {
            "config": "tab-echr-legal-en-v1",
            "seed": seed,
            "comparisons": {
                name: {
                    "contracts": {"3": {"numerical_pass": passed}},
                    "secondary_TAB_DIRECT": {"contracts": {"3": {"numerical_pass": True}}},
                }
                for name in COMPARATORS
            },
        }

    records = [record(0, True), record(1, True), record(2, False)]
    result = seed_summary(records, [0, 1, 2], "3")
    assert not any(result["tab-echr-legal-en-v1/all"].values())
    assert all(result["tab-echr-legal-en-v1/DIRECT"].values())
    assert not any(seed_summary(records[:2], [0, 1], "3")["tab-echr-legal-en-v1/DIRECT"].values())
    with pytest.raises(ValueError, match="Incomplete or duplicate"):
        seed_summary(records[:2], [0, 1, 2], "3")
    with pytest.raises(ValueError, match="Incomplete or duplicate"):
        seed_summary([records[0], records[0], records[2]], [0, 1, 2], "3")
