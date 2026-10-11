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
