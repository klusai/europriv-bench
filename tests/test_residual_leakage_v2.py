"""RES-121: strict residual coverage, legacy reproduction and harness negative controls."""

import pytest

from europriv_bench.adapters import BaseAdapter
from europriv_bench.metrics import (
    ROW_REGISTRY,
    name_in_context_leakage,
    residual_leakage_v2,
    residual_subject_detection_v2,
    tab_reid_leakage,
    tab_reid_leakage_v2,
    wilson_interval,
)
from europriv_bench.runner import run_spec
from europriv_bench.spec import DatasetRef, EvalSpec, Task

ROW = {"text": "John Smith", "spans": [
    {"start": 0, "end": 10, "label": "PERSON", "entity_id": "p1", "identifier_type": "DIRECT"},
]}


def test_partial_name_negative_control_preserves_v1_and_leaks_in_v2():
    tags = [["S-PERSON", "O"]]  # John masked, Smith readable
    legacy = tab_reid_leakage([ROW], tags)
    assert legacy["direct_leak_rate"] == 0
    assert ROW_REGISTRY["tab_reid_leakage_v1"]([ROW], tags) == legacy
    assert ROW_REGISTRY["name_in_context_leakage_v1"] is name_in_context_leakage
    assert name_in_context_leakage([ROW], tags)["name_leak_rate"] == 0
    strict = tab_reid_leakage_v2([ROW], [[(0, 4)]])
    assert strict["direct_subjects_total"] == strict["direct_subjects_leaked"] == 1
    assert strict["direct_leak_rate"] == 1
    assert (strict["direct_leak_rate_ci_low"], strict["direct_leak_rate_ci_high"]) == wilson_interval(1, 1)


@pytest.mark.parametrize("masks,expected", [
    ([], 1), ([(0, 1), (5, 10)], 1),  # partial character masking inside John
    ([(0, 4), (5, 9)], 1),           # one visible final character
    ([(0, 4), (5, 10)], 0),          # whitespace is exempt
    ([(0, 10)], 0), ([(5, 10), (0, 7), (0, 4)], 0),  # union, overlaps, unordered
])
def test_exact_character_union(masks, expected):
    assert residual_leakage_v2([ROW], [masks])["all_leak_rate"] == expected


def test_unicode_combining_marks_and_punctuation_are_not_exempt():
    text = "Ștefan-Ion\u0301"
    row = {"text": text, "spans": [{"start": 0, "end": len(text), "label": "PERSON"}]}
    for masks in [[(0, len(text) - 1)], [(0, 6), (7, len(text))]]:
        assert residual_leakage_v2([row], [masks])["all_leak_rate"] == 1
    assert residual_leakage_v2([row], [[(0, len(text))]])["all_leak_rate"] == 0


def test_any_occurrence_leaks_and_documents_are_separate_clusters():
    row = {"text": "John Smith / Smith", "spans": [
        ROW["spans"][0], dict(ROW["spans"][0], start=13, end=18),
    ]}
    subjects = residual_subject_detection_v2([row, row], [[(0, 10)], [(0, 18)]])
    assert [s["occurrences"] for s in subjects] == [2, 2]
    assert [s["leaked"] for s in subjects] == [True, False]
    assert [s["doc"] for s in subjects] == [0, 1]
    stats = tab_reid_leakage_v2([row, row], [[(0, 10)], [(0, 18)]])
    assert stats["direct_subjects_total"] == 2
    assert stats["direct_leak_rate"] == .5
    assert stats["direct_leak_rate_ci_low"] == wilson_interval(1, 2)[0]


def test_all_pii_fallback_and_sensitivity_denominators():
    row = {"text": "Ana Ana x@y.org Acme", "spans": [
        {"start": 0, "end": 3, "label": "PERSON"},
        {"start": 4, "end": 7, "label": "PERSON"},
        {"start": 8, "end": 15, "label": "EMAIL", "entity_id": 0, "identifier_type": "DIRECT"},
        {"start": 16, "end": 20, "label": "ORG_PARTY", "entity_id": 0, "identifier_type": "QUASI"},
    ]}
    stats = residual_leakage_v2([row], [[(0, 3), (8, 15)]])
    assert stats["all_subjects_total"] == 3
    assert stats["all_subjects_leaked"] == 2
    assert stats["direct_leak_rate"] == 0
    assert stats["quasi_leak_rate"] == stats["unspecified_leak_rate"] == 1
    with pytest.raises(ValueError, match="requires entity_id"):
        tab_reid_leakage_v2([row], [[]])


def test_empty_denominator_is_unavailable_not_perfect_privacy():
    stats = residual_leakage_v2([{"text": "hello", "spans": []}], [[]])
    assert stats["all_available"] == stats["all_subjects_total"] == 0
    assert stats["all_leak_rate"] == stats["all_leak_rate_ci_high"] == 0  # documented sentinels
    assert residual_leakage_v2([], [])["all_available"] == 0


@pytest.mark.parametrize("masks", [[], [[], []], [[(-1, 3)]], [[(0, 11)]], [[(2, 2)]], [[(0.0, 4)]]])
def test_malformed_predictions_fail_instead_of_dropping_gold(masks):
    with pytest.raises(ValueError):
        residual_leakage_v2([ROW], masks)


@pytest.mark.parametrize("change", [{"start": -1}, {"end": 11}, {"start": 4, "end": 5},
                                      {"identifier_type": "OTHER"}])
def test_malformed_gold_fails(change):
    row = dict(ROW, spans=[dict(ROW["spans"][0], **change)])
    with pytest.raises(ValueError):
        residual_leakage_v2([row], [[]])


class PartialMaskAdapter(BaseAdapter):
    name = model_id = "partial-name-negative-control"

    def predict_tags(self, texts):
        return [["S-PERSON", "O"] for _ in texts]

    def redaction_spans(self, texts):
        return [[(0, 4)] for _ in texts]


def control_spec():
    return EvalSpec(name="res121-negative-control", task=Task.DETECTION, languages=["en"],
                    dataset=DatasetRef(hf_id="local-authored-control"),
                    metrics=["tab_reid_leakage", "tab_reid_leakage_v1", "tab_reid_leakage_v2",
                             "residual_leakage_v2"])


def test_runner_scores_versions_side_by_side_and_dumps_same_outcomes():
    dumps = []
    result = run_spec(control_spec(), PartialMaskAdapter(), rows=[ROW], dumps=dumps)
    scores = result["scores"]
    assert scores["tab_reid_leakage"] == scores["tab_reid_leakage_v1"]
    assert scores["tab_reid_leakage"]["direct_leak_rate"] == 0
    assert scores["tab_reid_leakage_v2"]["direct_leak_rate"] == 1
    assert scores["residual_leakage_v2"]["all_leak_rate"] == 1
    assert len(dumps) == 2
    for dump in dumps:
        assert dump["metric_version"] == 2
        assert dump["subjects"][0]["leaked"]


def test_runner_exact_coverage_is_independent_of_token_fairness_mask_and_limit():
    class WrongLabelAdapter(PartialMaskAdapter):
        def predict_tags(self, texts):
            return [["S-EMAIL", "S-EMAIL"] for _ in texts]

    result = run_spec(control_spec(), WrongLabelAdapter(), rows=[ROW, ROW],
                      redaction_spans=[[(0, 10)], []], limit=1)
    assert result["n"] == 1
    assert result["scores"]["tab_reid_leakage"]["direct_leak_rate"] == 1  # legacy fairness mask
    assert result["scores"]["tab_reid_leakage_v2"]["direct_leak_rate"] == 0  # actual coverage


def test_runner_rejects_lossy_tag_fallback_and_missing_gold():
    with pytest.raises(NotImplementedError, match="exact redaction_spans"):
        run_spec(control_spec(), BaseAdapter(), rows=[ROW])
    with pytest.raises(ValueError, match="needs gold rows"):
        run_spec(control_spec(), PartialMaskAdapter(), gold=(["John Smith"], [["B-PERSON", "E-PERSON"]]))


def test_runner_rejects_unsupported_anonymization_route():
    spec = control_spec()
    spec.task = Task.ANONYMIZATION
    with pytest.raises(ValueError, match="detection runner"):
        run_spec(spec, PartialMaskAdapter(), rows=[ROW])


def test_span_only_replay_needs_no_model_or_lossy_gold_alignment():
    spec = control_spec()
    spec.metrics = ["residual_leakage_v2"]
    row = dict(ROW, spans=[*ROW["spans"], dict(ROW["spans"][0], start=5, entity_id="p2")])
    result = run_spec(spec, BaseAdapter(), rows=[row], redaction_spans=[[(0, 10)]])
    score = result["scores"]["residual_leakage_v2"]
    assert score["all_subjects_total"] == 2
    assert score["all_leak_rate"] == 0


def test_span_only_adapter_needs_no_predict_tags():
    class CoverageOnlyAdapter(BaseAdapter):
        def redaction_spans(self, texts):
            return [[] for _ in texts]

    spec = control_spec()
    spec.metrics = ["residual_leakage_v2"]
    result = run_spec(spec, CoverageOnlyAdapter(), rows=[ROW])
    assert result["scores"]["residual_leakage_v2"]["all_leak_rate"] == 1
