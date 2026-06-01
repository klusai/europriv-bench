"""Smoke tests — the harness must run end-to-end before any model is wired up."""

import json
from pathlib import Path

import pytest

from europriv_bench.adapters import build
from europriv_bench.leaderboard import (
    CONFIG_STATUS_VALUES,
    CONTAMINATION_VALUES,
    DEFAULT_CONFIG_STATUS,
    annotate_row,
    build_leaderboard,
    classify_contamination,
    format_leaderboard,
)
from europriv_bench.metrics import entity_f1, entity_f2
from europriv_bench.runner import run_spec
from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes, whitespace_tokens
from europriv_bench.spec import Task, load_suite
from europriv_bench.taxonomy import BY_NAME, bioes_labels


def test_taxonomy_label_space():
    labels = bioes_labels()
    assert labels[0] == "O"
    assert len(labels) == 1 + 4 * len(BY_NAME)
    assert "S-PERSON" in labels and "B-MRN" in labels


def test_entity_f1_perfect_and_recall():
    gold = [["S-PERSON", "O", "S-EMAIL"]]
    assert entity_f1(gold, gold)["f1"] == 1.0
    pred = [["S-PERSON", "O", "O"]]
    assert entity_f2(gold, pred)["recall"] == 0.5


def test_spans_roundtrip_and_validate():
    text = "Ion Popescu a scris lui Maria"  # 6 whitespace tokens
    assert whitespace_tokens(text)[0] == ("Ion", 0, 3)
    tags = char_spans_to_bioes(text, [Span(0, 11, "PERSON"), Span(24, 29, "PERSON")])
    assert tags == ["B-PERSON", "E-PERSON", "O", "O", "O", "S-PERSON"]
    validate_bioes(tags)
    with pytest.raises(ValueError):
        char_spans_to_bioes("a b", [Span(10, 12, "PERSON")])  # off-by-one → no aligned token
    # Two entities sharing one whitespace token (punctuation-joined) must fail loud, not corrupt BIOES.
    with pytest.raises(ValueError, match="token collision"):
        char_spans_to_bioes("Smith-Jones", [Span(0, 5, "PERSON"), Span(6, 11, "PERSON")])


def test_suite_loads_and_validates():
    specs = load_suite("evaluations")
    assert specs and all(s.dataset.hf_id for s in specs)


def test_dummy_adapter_runs_detection_with_provenance():
    spec = next(s for s in load_suite("evaluations") if s.task is Task.DETECTION)
    gold = (["Ion Popescu locuiește aici"], [["B-PERSON", "E-PERSON", "O", "O"]])
    result = run_spec(spec, build("dummy"), gold=gold, timestamp="2026-05-30T00:00:00Z")
    assert result["adapter"] == "dummy" and result["model_id"] == "dummy"
    assert result["scores"]["entity_f1"]["recall"] == 0.0
    # provenance present
    assert result["taxonomy_version"] and result["europriv_bench_version"]
    assert result["dataset"]["hf_id"] == spec.dataset.hf_id
    # schema-3 governance markers emitted on every run
    assert result["contamination"] in CONTAMINATION_VALUES
    assert result["config_status"] == "dev"


def test_run_spec_rejects_unknown_metric(tmp_path):
    spec = next(s for s in load_suite("evaluations") if s.task is Task.DETECTION)
    spec.metrics = ["entity_f1", "made_up_metric"]
    with pytest.raises(KeyError):
        run_spec(spec, build("dummy"), gold=(["x"], [["O"]]))


def test_leaderboard_schema3_groups_by_adapter_and_model():
    lb = build_leaderboard([
        {"adapter": "dummy", "model_id": "dummy", "spec": "a"},
        {"adapter": "dummy", "model_id": "dummy", "spec": "b"},
    ])
    assert lb["schema"] == 3
    assert len(lb["entries"]["dummy::dummy"]) == 2


def test_classify_contamination_known_cases():
    # OpenMed + tabularisai were trained on AI4Privacy → in_distribution on the 6 general configs.
    for adapter in ("openmed", "tabularisai"):
        for cfg in ("en", "de", "fr", "it", "es", "nl"):
            assert classify_contamination(adapter, cfg) == "in_distribution"
    # The RO real-skeleton track is clean held-out for every model (none trained on it).
    for adapter in ("openmed", "tabularisai", "gliner", "privacy-filter"):
        assert classify_contamination(adapter, "ro-realskeleton-v1") == "clean_held_out"
    # Models with unknown training data, or the synthetic RO track → unknown.
    assert classify_contamination("gliner", "en") == "unknown"
    assert classify_contamination("privacy-filter", "de") == "unknown"
    assert classify_contamination("openmed", "ro-synthetic-v1") == "unknown"


def test_build_leaderboard_annotates_both_markers_defaulting_to_dev():
    lb = build_leaderboard([
        {"adapter": "openmed", "model_id": "OpenMed/x", "spec": "en",
         "dataset": {"config": "en"}},
        {"adapter": "gliner", "model_id": "g", "spec": "ro",
         "dataset": {"config": "ro-realskeleton-v1"}},
    ])
    rows = {r["adapter"]: r for k, v in lb["entries"].items() for r in v}
    assert rows["openmed"]["contamination"] == "in_distribution"
    assert rows["gliner"]["contamination"] == "clean_held_out"
    # No config is citable until KLU-27's sign-off: everything defaults to dev.
    for r in rows.values():
        assert r["config_status"] == "dev" == DEFAULT_CONFIG_STATUS
        assert r["contamination"] in CONTAMINATION_VALUES
        assert r["config_status"] in CONFIG_STATUS_VALUES


def test_annotate_row_preserves_existing_markers():
    # A future curated promotion (KLU-27) must survive re-aggregation.
    row = annotate_row({"adapter": "openmed", "dataset": {"config": "en"},
                        "contamination": "clean_held_out", "config_status": "citable-validated"})
    assert row["contamination"] == "clean_held_out"
    assert row["config_status"] == "citable-validated"


_BASELINE_FILES = ["baselines/leaderboard.json", "baselines/leaderboard-full.json"]


@pytest.mark.parametrize("rel", _BASELINE_FILES)
def test_committed_baseline_is_schema3_with_markers(rel):
    """Every committed baseline row is schema 3, carries both markers, defaults to dev, and —
    where it has cnp_leakage — keeps the merged Wilson CI fields (no regression on KLU-6)."""
    root = Path(__file__).resolve().parents[1]
    d = json.loads((root / rel).read_text())
    assert d["schema"] == 3
    for rows in d["entries"].values():
        for r in rows:
            assert r["contamination"] in CONTAMINATION_VALUES
            assert r["config_status"] in CONFIG_STATUS_VALUES
            # No config is citable-validated until KLU-27 sign-off lands.
            assert r["config_status"] == "dev"
            # Derived markers match the policy in leaderboard.classify_contamination.
            assert r["contamination"] == classify_contamination(r["adapter"], r["dataset"]["config"])
            leak = r["scores"].get("cnp_leakage")
            if leak is not None:
                assert "leak_rate_ci_low" in leak and "leak_rate_ci_high" in leak


def test_format_leaderboard_renders_detection_and_leakage():
    lb = build_leaderboard([
        {"adapter": "m", "model_id": "m", "spec": "ro",
         "scores": {"entity_f1": {"f1": 0.5}, "entity_f2": {"f2": 0.4},
                    "cnp_leakage": {"leak_rate": 0.9, "cnp_missed": 9.0, "leaked_quasi_identifiers": 27.0}}},
    ])
    text = format_leaderboard(lb)
    assert "Detection" in text and "0.500/0.400" in text
    assert "leakage" in text and "0.900" in text
