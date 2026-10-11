"""Controls for exact MoE coverage and paired document statistics."""

import numpy as np
import pytest

from analysis.score_res100 import ci, samples, score, utility_counts
from europriv_bench.adapters import Res100MoEAdapter
from europriv_bench.metrics import residual_leakage_v2


def test_kp_bioes_prefix_and_exact_partial_coverage():
    adapter = Res100MoEAdapter("unused")
    calls = []

    def pipe(texts, **kwargs):
        calls.append(kwargs)
        return [[{"entity_group": "S-PERSON", "start": 0, "end": 4}]]

    adapter._pipe = pipe
    receipt = adapter.predict_receipts(["John Smith"])[0]
    assert receipt["tags"] == ["S-PERSON", "O"]
    assert receipt["intervals"] == [[0, 4]]
    assert receipt["output"] == "█ Smith"
    assert calls == [{"batch_size": 16, "stride": 64}]
    rows = [{"text": "John Smith", "spans": [{"start": 0, "end": 10, "label": "PERSON"}]}]
    assert residual_leakage_v2(rows, [receipt["intervals"]])["all_leak_rate"] == 1


def test_unmapped_native_base_label_still_masked():
    adapter = Res100MoEAdapter("unused", scheme="openai")
    adapter._pipe = lambda texts, **kwargs: [[{"entity_group": "unmapped", "start": 0, "end": 3}]]
    receipt = adapter.predict_receipts(["abc"])[0]
    assert receipt["tags"] == ["O"]
    assert receipt["output"] == "█"


def test_invalid_offsets_fail():
    adapter = Res100MoEAdapter("unused")
    adapter._pipe = lambda texts, **kwargs: [[{"entity_group": "PERSON", "start": 0, "end": 5}]]
    with pytest.raises(ValueError, match="offsets"):
        adapter.predict_receipts(["abc"])


def test_utility_union_unicode_and_empty_support():
    row = {"text": "é! A B", "spans": [{"start": 0, "end": 1, "label": "PERSON"}]}
    assert utility_counts(row, [[0, 3], [1, 4]]) == [2, 3]
    assert utility_counts({"text": "  ", "spans": []}, []) == [0, 0]
    indices = np.array([[0], [0]])
    assert ci(samples([[0, 0]], indices)) is None
    assert ci(samples([[0, 3]], indices) - samples([[1, 3]], indices)) == pytest.approx([-1 / 3, -1 / 3])


def test_score_negative_control_harness_v1_v2():
    rows = [
        {
            "text": "John Smith ok",
            "spans": [{"start": 0, "end": 10, "label": "PERSON", "entity_id": "p", "identifier_type": "DIRECT"}],
        }
    ]
    frozen = {
        "rows": rows,
        "dataset": {"hf_id": "test", "config": "tab", "split": "test"},
        "spec": {
            "name": "control",
            "task": "detection",
            "dataset": {"hf_id": "test", "config": "tab"},
            "metrics": ["entity_f1", "tab_reid_leakage"],
        },
    }
    result, counts = score(
        frozen, [{"tags": ["S-PERSON", "O", "O"], "intervals": [[0, 4]]}], "control", "control", 0, {}
    )
    assert result["scores"]["tab_reid_leakage"]["direct_leak_rate"] == 0
    assert result["scores"]["residual_leakage_v2"]["direct_leak_rate"] == 1
    assert counts["v2_direct"] == [[1, 1]]
    assert result["seed_scope"] == "single-seed"


def test_paired_ci_keeps_documents_and_rejects_mismatched_gold():
    from analysis.report_res100 import paired

    candidate = {
        "row": {"n": 2, "inference_provenance": {"gold_sha256": "same"}},
        "counts": {"v2_all": [[0, 10], [0, 1]], "over_redaction": [[0, 50], [0, 2]]},
    }
    comparator = {
        "row": {"n": 2, "inference_provenance": {"gold_sha256": "same"}},
        "counts": {"v2_all": [[10, 10], [1, 1]], "over_redaction": [[5, 50], [0, 2]]},
    }
    result = paired(candidate, comparator)
    assert result["n_clusters"] == 2
    assert result["deltas"]["v2_all"]["ci95"] == [-1, -1]
    assert result["deltas"]["over_redaction"]["ci95"][1] == 0
    comparator["row"]["inference_provenance"]["gold_sha256"] = "different"
    with pytest.raises(ValueError, match="different ordered gold"):
        paired(candidate, comparator)


def test_moe_contamination_does_not_inherit_old_family_assumptions():
    from europriv_bench.leaderboard import classify_contamination

    assert classify_contamination("kp-deid-moe-res100", "ro-synthetic-v1") == "in_distribution"
    for config in ("de", "ai4privacy-openpii-fr-v1", "tab-echr-legal-en-v1", "ro-realskeleton-v1"):
        assert classify_contamination("kp-deid-moe-res100", config) == "unknown"
    assert classify_contamination("kp-model", "de") == "clean_held_out"
