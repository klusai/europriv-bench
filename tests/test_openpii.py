"""Published OpenPII config/shards, curation boundaries and scoring provenance."""

from pathlib import Path

import pyarrow as pa
import pytest
from pyarrow import parquet

from europriv_bench.adapters import DummyAdapter
from europriv_bench.leaderboard import annotate_row
from europriv_bench.openpii import map_openpii_row
from europriv_bench.runner import _load_gold_rows, run_spec
from europriv_bench.spec import EvalSpec


def native(uid="one", language="ro"):
    return {
        "uid": uid, "language": language, "source_text": "Dr Ana Pop",
        "privacy_mask": [
            {"start": 0, "end": 2, "value": "Dr", "label": "TITLE"},
            {"start": 3, "end": 6, "value": "Ana", "label": "GIVENNAME"},
            {"start": 7, "end": 10, "value": "Pop", "label": "SURNAME"},
        ],
    }


def spec(max_rows=2):
    result = EvalSpec.from_yaml("evaluations/pii-detection-ai4privacy-openpii-ro.yaml")
    result.dataset.max_rows = max_rows
    return result


def shards(monkeypatch, tmp_path, rows):
    calls = []
    for i, batch in enumerate(rows):
        parquet.write_table(pa.Table.from_pylist(batch), tmp_path / f"{i:04}.parquet")

    def download(repo_id, filename, **kwargs):
        calls.append((repo_id, filename, kwargs))
        return str(tmp_path / Path(filename).name)

    def forbidden(*args, **kwargs):
        pytest.fail("OpenPII must download parquet directly, never call datasets.load_dataset")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", download)
    monkeypatch.setattr("datasets.load_dataset", forbidden)
    return calls


def test_published_shards_filter_map_and_score(monkeypatch, tmp_path):
    calls = shards(monkeypatch, tmp_path, [[native("foreign", "de"), native()], [native("two"), native("three")]])
    evaluation = spec()
    rows = _load_gold_rows(evaluation)
    assert [row["uid"] for row in rows] == ["one", "two"]
    assert rows[0]["unmapped_labels"] == {"TITLE": 1}
    assert [span["label"] for span in rows[0]["spans"]] == ["PERSON", "PERSON"]
    assert len(calls) == 2
    assert all(call[0] == evaluation.dataset.hf_id for call in calls)
    assert all(call[2] == {"repo_type": "dataset", "revision": evaluation.dataset.revision} for call in calls)
    adapter = DummyAdapter()
    adapter.name = "openmed"
    result = run_spec(evaluation, adapter, rows=rows)
    assert result["n"] == 2
    assert result["scores"]["entity_f1"]["f1"] == 0
    assert result["contamination"] == "in_distribution"
    assert result["dataset"]["config"] == "default"
    assert result["dataset"]["eval_config"] == "ai4privacy-openpii-ro-v1"
    assert result["dataset"]["curation"]["candidate_rows"] == 2
    del result["contamination"]
    assert annotate_row(result)["contamination"] == "in_distribution"


def test_token_collisions_counted_without_replacement(monkeypatch, tmp_path):
    collision = native("collision")
    collision["source_text"] = "Dr Ana-Pop"
    shards(monkeypatch, tmp_path, [[collision, native(), native("replacement")]])
    rows = _load_gold_rows(spec())
    assert [row["uid"] for row in rows] == ["one"]
    assert rows.source_metadata["curation"]["excluded_token_collision_uids"] == ["collision"]


def test_invalid_annotation_fails_loudly():
    row = native()
    row["privacy_mask"][1]["value"] = "wrong"
    with pytest.raises(ValueError, match="span/value mismatch"):
        map_openpii_row(row)


def test_short_slice_fails(monkeypatch, tmp_path):
    shards(monkeypatch, tmp_path, [[native()], [native("foreign", "de")]])
    with pytest.raises(ValueError, match="expected 2 candidates, found 1"):
        _load_gold_rows(spec())


def test_missing_parquet_not_silently_skipped(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("pinned shard missing")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", missing)
    with pytest.raises(FileNotFoundError, match="pinned shard missing"):
        _load_gold_rows(spec())


@pytest.mark.parametrize("path", sorted(Path("evaluations").glob("*openpii*.yaml")))
def test_all_yaml_sources_match_published_layout(path):
    evaluation = EvalSpec.from_yaml(path)
    source = evaluation.dataset
    assert source.hf_id == "ai4privacy/pii-masking-openpii-1m"
    assert (source.config, source.split, source.loader) == ("default", "validation", "ai4privacy-openpii")
    assert source.revision == "c064392b9d3ddccc3a2997d41630631f9be465f0"
    assert source.files == ["default/validation/0000.parquet", "default/validation/0001.parquet"]
    assert source.identity == f"ai4privacy-openpii-{evaluation.languages[0]}-v1"
    assert source.max_rows == 400
