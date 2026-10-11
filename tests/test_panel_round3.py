import json
from unittest.mock import patch

import pytest

from analysis import panel_round2 as prior
from analysis.panel_report import adjudicate
from analysis.panel_round3 import MODELS, carry_forward, request
from europriv_bench.panel import digest
from europriv_bench.panel_api import atomic_json
from europriv_bench.panel_round2_api import RetryBudgetClient


def test_replacement_keeps_prompts_and_distinct_families():
    assert len({m.split("/")[0] for m in MODELS}) == 3
    for m in MODELS:
        new, old = request(m, [], "a"), prior.request(m, [], "a")
        assert new["messages"] == old["messages"]
        assert new["max_tokens"] == 8192 and new["temperature"] == 0 and new["seed"] == 77
        assert new["provider"]["allow_fallbacks"]
        if m == MODELS[0]:
            assert new["provider"]["order"][0] == "alibaba"
            assert "sort" not in new["provider"]
        else:
            assert new == old


def test_adjudication_uses_replacement_votes_not_old_mistral():
    row = {"id": "1", "sha256": "hash", "spans": []}
    proposals = [{"id": "p", "start": 0, "end": 1, "label": "PERSON", "operation": "add"}]
    vote = {"1": {"votes": [{"id": "p", "approve": True, "reason": "person"}]}}
    old = {m: vote for m in (*MODELS[1:], "mistralai/mistral-large-2512")}
    assert not adjudicate(row, proposals, old, models=MODELS)["complete"]
    result = adjudicate(row, proposals, {m: vote for m in MODELS}, models=MODELS)
    assert result["complete"] and result["approved"] == 1


def test_carried_evidence_requires_raw_response(tmp_path):
    (tmp_path / "cache").mkdir()
    sample = {"ro-realskeleton-v2": []}
    evidence = {"sample_sha256": digest(sample), "stage_a": {"ro-realskeleton-v2": {m: {"1": {}} for m in MODELS[1:]}}}
    with patch("pathlib.Path.read_text", return_value=json.dumps(evidence)):
        with pytest.raises(ValueError, match="Missing raw evidence"):
            carry_forward(tmp_path, sample)


def test_inherited_liabilities_count_towards_cap(tmp_path):
    atomic_json(
        tmp_path / "ledger.json",
        {
            "old-success": {"state": "complete", "cost": 24.9},
            "old-429": {"state": "rate_limited", "reserved": 0.09},
        },
    )
    with patch("urllib.request.urlopen") as dispatch:
        with pytest.raises(RuntimeError, match="budget"):
            RetryBudgetClient(tmp_path, "round3").complete(request(MODELS[0], [], "a"))
        dispatch.assert_not_called()


def test_type_statistics_keep_missing_replacement_out_of_complete_cases():
    from analysis.panel_round3_report import summary

    rows = [
        {
            "id": str(i),
            "stratum": "admin",
            "spans": [{"start": 0, "end": 1, "label": "PERSON"}, {"start": 2, "end": 3, "label": "PHONE"}],
        }
        for i in range(2)
    ]
    annotations = {
        m: {r["id"]: {"spans": r["spans"], "fluency": 5, "naturalness": 4, "artifacts": []} for r in rows}
        for m in MODELS
    }
    del annotations[MODELS[0]]["1"]
    value = summary(rows, annotations)
    assert value["n"] == 1 and value["sampled_n"] == 2
    assert value["valid_per_model"][MODELS[0]] == 1
    assert set(value["alpha"]) == {"panel", *MODELS}
    assert all(v["estimate"] == 1 for v in value["alpha"].values())
    assert value["ratings"][MODELS[0]]["naturalness"]["ci95"] == [4, 4]
    assert value["artifacts"]["ci95"][0] == 0


def test_continuation_dispatches_only_missing_seat(tmp_path):
    rows = [{"id": str(i), "language": "ro", "text": "document"} for i in range(5)]
    samples = {"ro-realskeleton-v2": rows}
    freeze = {"protocol_sha256": "test"}
    atomic_json(tmp_path / "samples.json", samples)
    atomic_json(tmp_path / "frozen.json", {**freeze, "sample_sha256": digest(samples)})
    answers = [{"id": r["id"], "spans": [], "fluency": 5, "naturalness": 5, "artifacts": []} for r in rows]
    initial = {"ro-realskeleton-v2": {m: {a["id"]: a for a in answers} if m in MODELS[1:] else {} for m in MODELS}}
    raw = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"documents": answers})}}]}
    with patch("analysis.panel_round2.RetryBudgetClient") as client:
        client.return_value.complete.return_value = raw
        client.return_value.evidence.return_value = {}
        prior.run(tmp_path, "a", models=MODELS, freeze=lambda: freeze, request_builder=request, initial=initial)
        client.return_value.complete.assert_called_once()
        assert client.return_value.complete.call_args.args[0]["model"] == MODELS[0]
    output = json.loads((tmp_path / "stage-a.json").read_text())
    assert all(len(v) == 5 for v in output["annotations"]["ro-realskeleton-v2"].values())
    assert initial["ro-realskeleton-v2"][MODELS[0]] == {}


def test_report_refuses_population_outside_pinned_revision(tmp_path):
    from analysis.panel_round3_report import generate

    atomic_json(tmp_path / "samples.json", {})
    atomic_json(tmp_path / "populations.json", {"ro-realskeleton-v2": [{"text": "changed"}]})
    with pytest.raises(ValueError, match="pinned data revision"):
        generate(tmp_path, tmp_path / "out")
