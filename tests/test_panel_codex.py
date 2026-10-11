"""Supplemental judges must not fabricate agreement or bypass the frozen audit."""

import hashlib
import json
from pathlib import Path

import pytest

from analysis.panel_report import CODEX, bootstrap, load_codex, supplemental
from europriv_bench.panel import MODELS, alpha_counts, alpha_from_counts, digest


def fixture_record():
    text = "Ana 123"
    row = {
        "id": "0",
        "stratum": "admin",
        "text": text,
        "sha256": digest(text),
        "spans": [{"start": 0, "end": 3, "label": "PERSON"}, {"start": 4, "end": 7, "label": "CASE_NUMBER"}],
    }
    record = {
        "id": "0",
        "stratum": "admin",
        "config": "test",
        "reviewer": CODEX,
        "source_revision": "revision",
        "text_sha256": digest(text),
        "raw_utf8_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "spans": [{**s, "text": text[s["start"] : s["end"]]} for s in row["spans"]],
        "fluency": 4,
        "naturalness": 3,
        "reason": "Concrete defect.",
        "artifacts": ["Defect"],
        "gold_review_status": "pending_after_A_freeze",
    }
    return row, record


def save_fixture(tmp_path, record):
    frozen = json.dumps(record, ensure_ascii=False) + "\n"
    payload_hash = digest([record])
    record = {**record, "stage_a_sha256": digest(record), "gold_errors": [], "gold_review_status": "reviewed"}
    path = tmp_path / "annotations.jsonl"
    path.write_text(json.dumps(record, ensure_ascii=False) + "\n")
    manifest = {
        "source_revision": "revision",
        "configs": {
            "test": {
                "annotations_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "stage_a_payload_sha256": payload_hash,
                "stage_a_file_sha256": hashlib.sha256(frozen.encode()).hexdigest(),
            }
        },
    }
    return path, manifest


def test_single_judge_cannot_create_panel_alpha():
    row, a = fixture_record()
    stats = bootstrap([row], {CODEX: {"0": a}}, models=(CODEX,))
    assert stats["alpha"][CODEX]["estimate"] == 1
    assert stats["alpha"]["panel"]["estimate"] is None
    assert stats["alpha"]["panel"]["ci95"] is None
    assert stats["alpha"]["panel"]["defined_bootstraps"] == 0
    assert alpha_from_counts(*alpha_counts([{(0, 3): "PERSON"}], [(0, 3)])) is None


def test_codex_is_fourth_rater_without_replacing_missing_models():
    row, a = fixture_record()
    a["gold_errors"] = []
    missing = {m: {} for m in MODELS}
    result, _ = supplemental([row], missing, {"0": a})
    assert result["expanded_panel"]["n"] == 0
    assert result["codex_vs_gold"]["n"] == 1
    assert result["valid_per_model"] == {**dict.fromkeys(MODELS, 0), CODEX: 1}
    assert result["changes_frozen_verdict"] is False
    assert missing == {m: {} for m in MODELS}
    others = {m: {"0": {**a, "spans": row["spans"]}} for m in MODELS}
    a["spans"] = [{"start": 0, "end": 2, "label": "PERSON"}, row["spans"][1]]
    result, discrepancies = supplemental([row], others, {"0": a})
    assert result["expanded_panel"]["n"] == 1
    assert result["expanded_panel"]["alpha"]["panel"]["estimate"] < 1
    assert len([d for d in discrepancies if d["kind"] == "supplemental_span"]) == 2


def test_loader_checks_frozen_payload_and_exact_spans(tmp_path):
    row, record = fixture_record()
    path, manifest = save_fixture(tmp_path, record)
    assert load_codex(path, [row], "test", manifest)["0"]["naturalness"] == 3
    changed = json.loads(path.read_text())
    changed["naturalness"] = 5
    path.write_text(json.dumps(changed) + "\n")
    with pytest.raises(ValueError, match="file hash"):
        load_codex(path, [row], "test", manifest)
    manifest["configs"]["test"]["annotations_file_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="stage A changed"):
        load_codex(path, [row], "test", manifest)


@pytest.mark.parametrize("defect", ["offset", "overlap", "label", "source", "sample", "rating", "review"])
def test_loader_rejects_malformed_annotations(tmp_path, defect):
    row, record = fixture_record()
    if defect == "offset":
        record["spans"][0]["end"] = 2
    elif defect == "overlap":
        record["spans"].append(record["spans"][0])
    elif defect == "label":
        record["spans"][0]["label"] = "FAKE"
    elif defect == "source":
        record["raw_utf8_sha256"] = "wrong"
    elif defect == "sample":
        record["id"] = "extra"
    elif defect == "rating":
        record["fluency"] = True
    else:
        record["spans"][0]["label"] = "PROVIDER"  # Unreviewed label change.
    path, manifest = save_fixture(tmp_path, record)
    with pytest.raises(ValueError):
        load_codex(path, [row], "test", manifest)


def test_committed_annotations_preserve_frozen_a_and_manifest():
    root = Path(__file__).resolve().parents[1] / "docs/validation"
    manifest = json.loads((root / "codex-review-manifest.json").read_text())
    for filename, key in [
        ("panel-protocol.md", "protocol_sha256"),
        ("panel-sample-manifest.json", "sample_manifest_sha256"),
    ]:
        assert hashlib.sha256((root / filename).read_bytes()).hexdigest() == manifest[key]
    samples = json.loads((root / "panel-sample-manifest.json").read_text())["samples"]
    for config, metadata in manifest["configs"].items():
        path = root / metadata["annotations_file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata["annotations_file_sha256"]
        records = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(records) == 300
        assert {a["id"] for a in records} == {r["id"] for r in samples[config]}
        frozen = []
        for record in records:
            a = {k: v for k, v in record.items() if k not in {"stage_a_sha256", "gold_errors"}}
            a["gold_review_status"] = "pending_after_A_freeze"
            assert digest(a) == record["stage_a_sha256"]
            frozen.append(a)
        assert digest(frozen) == metadata["stage_a_payload_sha256"]
        content = "".join(json.dumps(a, ensure_ascii=False) + "\n" for a in frozen).encode()
        assert hashlib.sha256(content).hexdigest() == metadata["stage_a_file_sha256"]
