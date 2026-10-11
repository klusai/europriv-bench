"""Gateway boundaries, paired inference and exact operators without model downloads."""
import copy
import json
from types import SimpleNamespace

import pytest
import yaml

from europriv_bench.adapters import DummyAdapter, KpModelAdapter, PresidioAdapter
from europriv_bench.gateway import (
    cluster_counts,
    flatten_conversation,
    gateway_utility,
    load_gateway,
    paired_cluster_bootstrap,
    utility_counts,
)
from europriv_bench.gateway_operator import GatewayDeletionAdapter, delete_intervals
from europriv_bench.metrics import residual_leakage_v2
from europriv_bench.runner import ConfigUnavailableError, run_spec
from europriv_bench.spec import DatasetRef, EvalSpec, Task


def conversation():
    return {"schema_version": "gateway-traffic-v1", "config_status": "dev", "id": "c1", "split": "test",
            "language": "ro", "source_id": "originals",
            "messages": [{"role": "user", "parts": [{"type": "text", "text": "Ștefan!"}]},
                         {"role": "assistant", "parts": [{"type": "text", "text": "Ștefan 2026"}]}],
            "spans": [{"message": 0, "part": 0, "start": 0, "end": 6, "text": "Ștefan", "label": "PERSON",
                       "entity_id": "p1", "identifier_class": "DIRECT", "protection": "mask"},
                      {"message": 1, "part": 0, "start": 0, "end": 6, "text": "Ștefan", "label": "PERSON",
                       "entity_id": "p1", "identifier_class": "DIRECT", "protection": "pseudonymize"},
                      {"message": 1, "part": 0, "start": 7, "end": 11, "text": "2026", "label": "DATE",
                       "entity_id": "date", "identifier_class": "QUASI", "protection": "retain"}]}


def spec(**kwargs):
    return EvalSpec(name="gateway", task=Task.DETECTION, languages=["ro"],
                    dataset=DatasetRef(hf_id="test", config="gateway-traffic-v1", loader="gateway", **kwargs),
                    metrics=["residual_leakage_v2", "gateway_utility"])


def test_conversation_coreference_retained_utility_and_harness():
    row = flatten_conversation(conversation())
    assert row["text"] == "Ștefan!\nȘtefan 2026"
    assert [(s["start"], s["end"]) for s in row["spans"]] == [(0, 6), (8, 14)]
    score = run_spec(spec(), DummyAdapter(), rows=[row], redaction_spans=[[(0, 6)]], dumps=[])
    assert score["config_status"] == "dev"
    assert score["scores"]["residual_leakage_v2"]["all_subjects_total"] == 1
    assert score["scores"]["residual_leakage_v2"]["all_leak_rate"] == 1
    assert gateway_utility([row], [[(15, 19)]])["over_redaction_rate"] == 4 / 5
    assert residual_leakage_v2([row], [[(0, 6), (8, 14)]])["all_leak_rate"] == 0


@pytest.mark.parametrize("corrupt", ["bounds", "surface", "part", "class", "policy"])
def test_flatten_rejects_corruption(corrupt):
    row = conversation()
    if corrupt == "bounds":
        row["spans"][0]["start"] = -1
    elif corrupt == "surface":
        row["spans"][0]["text"] = "other"
    elif corrupt == "part":
        row["messages"][0]["parts"][0]["type"] = "image"
    elif corrupt == "class":
        row["spans"][0]["identifier_class"] = "unknown"
    else:
        row["spans"][0]["protection"] = "unknown"
    with pytest.raises(ValueError):
        flatten_conversation(row)


def test_local_loader_provenance_license_split_and_duplicate(tmp_path, monkeypatch):
    data, manifest = tmp_path / "test.jsonl", tmp_path / "manifest.yaml"
    row = conversation()
    data.write_text(json.dumps(row) + "\n")
    policy = {"dataset": "gateway-traffic-v1", "config_status": "dev", "sources": {
        "originals": {"permitted_train": True, "permitted_redistribute": True, "license": "CC-BY-4.0",
                      "url": "https://example.org/source", "allowed_gateway_splits": ["test"]}}}
    manifest.write_text(yaml.safe_dump(policy))
    monkeypatch.setenv("EUROPRIV_GATEWAY_PATH", str(tmp_path))
    rows = load_gateway(spec())
    assert len(rows) == 1 and len(rows.source_metadata["data_sha256"]) == 64
    data.write_text((json.dumps(row) + "\n") * 2)
    with pytest.raises(ValueError, match="duplicate"):
        load_gateway(spec())
    row["split"] = "dev"
    data.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="split"):
        load_gateway(spec())
    row["split"] = "test"
    data.write_text(json.dumps(row))
    policy["sources"]["originals"]["permitted_train"] = False
    manifest.write_text(yaml.safe_dump(policy))
    with pytest.raises(ValueError, match="licence"):
        load_gateway(spec())


def test_unpublished_gateway_explicitly_unavailable(monkeypatch):
    monkeypatch.delenv("EUROPRIV_GATEWAY_PATH", raising=False)
    with pytest.raises(ConfigUnavailableError):
        load_gateway(spec())


def test_paired_cluster_ci_counts_conversations_not_mentions():
    rows = [flatten_conversation(conversation()) for _ in range(5)]
    a = cluster_counts(rows, [[(0, 6), (8, 14)]] * 5)
    b = cluster_counts(rows, [[]] * 5)
    assert a == [[0, 1]] * 5  # repeated mentions are one subject, not two samples
    ci = paired_cluster_bootstrap(a, b)
    assert ci["n"] == 5 and ci["clusters"] == 5
    assert ci["delta"] == ci["ci_low"] == ci["ci_high"] == -1
    tie = paired_cluster_bootstrap(a, a)
    assert tie["ci_high"] == 0
    assert not paired_cluster_bootstrap([[0, 0]], [[0, 0]])["available"]
    with pytest.raises(ValueError, match="denominators"):
        paired_cluster_bootstrap(a, [[0, 2]] * 5)
    with pytest.raises(ValueError, match="2000"):
        paired_cluster_bootstrap(a, b, resamples=1999)


def test_utility_union_empty_denominator_and_no_worse():
    row = {"text": "Joe xy", "spans": [{"start": 0, "end": 3, "label": "PERSON"}]}
    assert utility_counts([row], [[(0, 5), (4, 6)]]) == [(2, 2)]
    assert gateway_utility([row], [[]])["character_retention"] == 1
    row["spans"][0]["end"] = 6
    assert gateway_utility([row], [[(0, 6)]])["available"] == 0


def test_exact_kp_operator_uses_raw_offsets_and_overflow():
    class Pipe:
        tokenizer = SimpleNamespace(is_fast=True, model_max_length=10**30)
        model = SimpleNamespace(config=SimpleNamespace(max_position_embeddings=512))

        def __call__(self, texts, **kwargs):
            assert kwargs["stride"] == 64
            return [[{"start": 0, "end": 1}] for _ in texts]

    kp = KpModelAdapter("local")
    kp._pipe = Pipe()
    operator = GatewayDeletionAdapter(kp)
    assert operator.redaction_spans(["Ștefan!"]) == [[(0, 1)]]
    assert delete_intervals("Ștefan!", [(0, 1)]) == "tefan!"
    assert operator.receipts[0]["operator"] == "delete-exact-union-v1"
    assert delete_intervals("abc", [(1, 3), (0, 2)]) == ""
    with pytest.raises(ValueError):
        delete_intervals("abc", [(0, 4)])


def test_presidio_operator_preserves_stock_policy():
    def analyze(**kwargs):
        assert kwargs["language"] == "en" and kwargs["score_threshold"] == 0
        return [SimpleNamespace(start=0, end=2)]

    presidio = PresidioAdapter()
    presidio._engine = SimpleNamespace(analyze=analyze)
    assert GatewayDeletionAdapter(presidio).redaction_spans(["Joe"]) == [[(0, 2)]]


def test_label_shuffle_cannot_change_explicit_entity_v2():
    row = flatten_conversation(conversation())
    changed = copy.deepcopy(row)
    for span in changed["spans"]:
        span["label"] = "EMAIL"
    assert residual_leakage_v2([row], [[]]) == residual_leakage_v2([changed], [[]])


def test_hub_single_parquet_uses_pinned_download(tmp_path, monkeypatch):
    import huggingface_hub
    import pyarrow as pa
    import pyarrow.parquet as pq

    monkeypatch.delenv("EUROPRIV_GATEWAY_PATH", raising=False)
    monkeypatch.delenv("EUROPRIV_GATEWAY_MANIFEST", raising=False)
    pq.write_table(pa.Table.from_pylist([conversation()]), tmp_path / "test.parquet")
    policy = {"dataset": "gateway-traffic-v1", "config_status": "dev", "sources": {
        "originals": {"permitted_train": True, "permitted_redistribute": True, "license": "CC-BY-4.0",
                      "url": "https://example.org/source", "allowed_gateway_splits": ["test"]}}}
    (tmp_path / "manifest.yaml").write_text(yaml.safe_dump(policy))
    calls = []

    def download(repo, filename, **kwargs):
        calls.append((repo, filename, kwargs))
        return str(tmp_path / filename)

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", download)
    rows = load_gateway(spec(revision="a" * 40, files=["test.parquet"], manifest_path="manifest.yaml"))
    assert len(rows) == 1 and not rows.source_metadata["local_override"]
    assert all(call[2] == {"repo_type": "dataset", "revision": "a" * 40} for call in calls)


def test_registered_specs_and_legacy_anchors_remain_distinct():
    from pathlib import Path

    paths = list(Path("evaluations").glob("pii-detection-gateway-traffic-*.yaml"))
    assert len(paths) == 8
    assert {EvalSpec.from_yaml(path).languages[0] for path in paths} == {"ro", "en", "de", "fr", "es", "it", "nl", "pl"}
    for name in ("tab-echr-legal-en", "ro-realskeleton", "pl-realskeleton"):
        anchor = EvalSpec.from_yaml(f"evaluations/pii-detection-{name}.yaml")
        assert "residual_leakage_v2" not in anchor.metrics
        assert anchor.dataset.config != "gateway-traffic-v1"


def test_controls_detect_alignment_corruption_and_mask_input():
    import importlib.util

    module_spec = importlib.util.spec_from_file_location("score_gateway", "analysis/score_gateway.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    row = flatten_conversation(conversation())

    class Operator(DummyAdapter):
        def redaction_spans(self, texts):
            assert texts == ["      !\n       2026"] * 10
            return [[]] * 10

    adapter = Operator()
    output = module.controls(spec(), adapter, [row] * 10, [[(0, 6), (8, 14)]] * 10)
    assert output["none"]["residual_leakage_v2"]["all_leak_rate"] == 1
    assert output["full"]["residual_leakage_v2"]["all_leak_rate"] == 0
    assert output["full"]["gateway_utility"]["over_redaction_rate"] == 1
    assert output["shuffled_labels"]["residual_leakage_v2"]["all_leak_rate"] == 0
    assert output["shuffled_positions"]["residual_leakage_v2"]["all_leak_rate"] > 0
    assert output["masked_input"]["n"] == 10


def test_splice_preserves_all_historical_rows_and_rejects_partial():
    import importlib.util

    module_spec = importlib.util.spec_from_file_location("splice_gateway", "analysis/splice_gateway.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    anchor = {"adapter": "old", "model_id": "old", "dataset": {"config": "tab-echr-legal-en-v1"},
              "spec": "anchor", "scores": {"tab_reid_leakage": {"direct_leak_rate": .1}}}
    board = {"schema": 3, "entries": {"old::old": [anchor]}}
    rows = [{"run_label": label, "adapter": label, "model_id": label, "languages": [lang], "spec": lang,
             "config_status": "dev", "n": 1000, "limit": None,
             "dataset": {"config": "gateway-traffic-v1", "data_sha256": "same"}}
            for label in module.LABELS for lang in module.LANGUAGES]
    result = module.splice(board, rows)
    assert result["entries"]["old::old"] == [anchor]
    assert "contamination" not in anchor
    with pytest.raises(ValueError, match="partial"):
        module.splice(board, rows[:-1])
    rows[0]["dataset"]["data_sha256"] = "different"
    with pytest.raises(ValueError, match="hash"):
        module.splice(board, rows)


def test_gateway_governance_does_not_inherit_generic_clean_claim():
    from europriv_bench.leaderboard import classify_contamination, config_status_for

    for adapter in ("kp-model", "presidio", "shield", "spacy", "gliner2"):
        for config in ("gateway-traffic-v1", "gateway-traffic-v1/ro", "gateway-traffic-v1/pl"):
            assert classify_contamination(adapter, config) == "unknown"
            assert config_status_for(config) == "dev"
    assert classify_contamination("presidio", "ro-realskeleton-v1") == "clean_held_out"
