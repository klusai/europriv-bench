"""Versioned utility acceptance; synthetic controls are not model evidence."""

import json
import math

import pytest

from analysis.report_res100_calibration import gates
from europriv_bench.gateway_contract import utility_gate


@pytest.mark.parametrize(
    ("upper", "passes"),
    [(0.009, True), (0.01, True), (math.nextafter(0.01, math.inf), False), (0.02, False)],
)
def test_v3_upper_ci_boundary_is_one_absolute_percentage_point(upper, passes):
    result = utility_gate([0, upper], contract_version=3)
    assert result["pass"] is passes
    assert result["margin"] == 0.01
    assert result["contract_version"] == 3


@pytest.mark.parametrize("version", [1, 2])
def test_old_contract_keeps_zero_margin(version):
    assert utility_gate([-0.01, 0], contract_version=version)["pass"]
    result = utility_gate([0.005, 0.008], contract_version=version)
    assert not result["pass"]
    assert result["regression"]
    assert result["margin"] == 0


def test_v3_crossing_margin_is_not_established_inferiority():
    result = utility_gate([0.005, 0.011], contract_version=3)
    assert not result["pass"]
    assert not result["regression"]
    assert utility_gate([0.011, 0.02], contract_version=3)["regression"]
    assert not utility_gate([0.01, 0.02], contract_version=3)["regression"]


@pytest.mark.parametrize("version", [1, 2, 3])
def test_unavailable_utility_never_passes(version):
    result = utility_gate(None, contract_version=version)
    assert not result["pass"]
    assert not result["regression"]


@pytest.mark.parametrize("version", [0, 4, "3", True, 3.0])
def test_unknown_contract_is_rejected(version):
    with pytest.raises(ValueError, match="contract version"):
        utility_gate([0, 0], contract_version=version)


@pytest.mark.parametrize("interval", [[], [0], [0.02, 0.01], [0, math.nan], [-math.inf, 0], [0, 2]])
def test_invalid_ci_is_rejected(interval):
    with pytest.raises(ValueError, match="95% rate CI"):
        utility_gate(interval, contract_version=3)


def scored(leak, removed, *, version=3):
    return {
        "row": {
            "contract_version": version,
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
        "counts": {"v2_all": [[leak, 1]] * 2, "over_redaction": [[removed, 100]] * 2},
    }


def test_verdict_selects_contract_without_establishing_a_win():
    candidate, comparator = scored(0, 1), scored(1, 0)
    historical = gates(candidate, comparator)
    v2 = gates(candidate, comparator, contract_version=2)
    v3 = gates(candidate, comparator, contract_version=3)
    assert historical["verdict"] == v2["verdict"] == "loss: over-redaction regression"
    assert v3["utility_gate"]["ci95"] == [0.01, 0.01]
    assert all(v3["numerical_gates"].values())
    assert v3["verdict"] == "not established"  # Needs seeds, anchors, review, all configs.
    for key in ("disjoint_wilson", "paired_privacy"):
        assert historical["numerical_gates"][key] == v3["numerical_gates"][key]
    assert gates(scored(0, 2), comparator, contract_version=3)["verdict"] == "loss: over-redaction regression"


def test_v3_does_not_relax_privacy_or_per_comparator_requirement():
    tied = gates(scored(0, 1), scored(0, 0), contract_version=3)
    assert tied["numerical_gates"]["utility_noninferiority"]
    assert not tied["numerical_gates"]["disjoint_wilson"]
    assert not tied["numerical_gates"]["paired_privacy"]
    worse = gates(scored(1, 1), scored(0, 0), contract_version=3)
    assert worse["verdict"] == "loss: residual-leak regression"
    candidate = scored(0, 2)
    results = [gates(candidate, baseline, contract_version=3) for baseline in (scored(1, 1), scored(1, 0))]
    assert [r["numerical_gates"]["utility_noninferiority"] for r in results] == [True, False]


def test_v3_rejects_unregistered_historical_candidate():
    candidate = scored(0, 1, version=1)
    with pytest.raises(ValueError, match="prospectively registered"):
        gates(candidate, scored(1, 0), contract_version=3)


def test_gateway_compare_pins_version_and_rejects_historical_rows(tmp_path, monkeypatch):
    from analysis import score_gateway

    monkeypatch.setattr(score_gateway, "LANGUAGES", ("ro",))
    monkeypatch.setattr(score_gateway, "build_leaderboard", lambda rows: {"rows": rows})
    for name, leak, removed in (("kp-280m", 0, 1), ("presidio", 1, 0), ("shield", 1, 0)):
        row = {
            "run_label": name,
            "languages": ["ro"],
            "dataset": {"data_sha256": "same"},
            "scores": scored(leak, removed)["row"]["scores"],
            "run_pin": {"contract_version": 3},
        }
        clusters = {key: [[leak, 1]] * 2 for key in ("all", "direct", "quasi", "unspecified")}
        clusters.update(utility=[[removed, 100]] * 2, conversation_ids=["a", "b"])
        (tmp_path / f"{name}-ro.row.json").write_text(json.dumps(row))
        (tmp_path / f"{name}-ro.clusters.json").write_text(json.dumps(clusters))
    score_gateway.compare(tmp_path, contract_version=3)
    results = json.loads((tmp_path / "comparisons.json").read_text())
    assert len(results) == 2
    assert all(r["utility_pass"] and r["contract_version"] == 3 for r in results)
    assert all(r["verdict"].startswith("not established") for r in results)
    path = tmp_path / "kp-280m-ro.row.json"
    row = json.loads(path.read_text())
    row.pop("run_pin")
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="historical"):
        score_gateway.compare(tmp_path, contract_version=3)
    score_gateway.compare(tmp_path)  # Historical rows retain the strict default.
    assert not any(r["utility_pass"] for r in json.loads((tmp_path / "comparisons.json").read_text()))
