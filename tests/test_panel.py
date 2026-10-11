import json
from collections import Counter
from unittest.mock import patch

import pytest

from europriv_bench.panel import align, alpha_counts, alpha_from_counts, decode_audit, sample_rows
from europriv_bench.panel_api import CAP, BudgetClient, atomic_json, reservation


def test_exact_alignment_repeats_unicode_and_rejects_guessing():
    assert align("Ștefan și Ștefan", [{"text": "Ștefan", "occurrence": 2, "label": "PERSON"}]) == [
        {"start": 10, "end": 16, "label": "PERSON"}
    ]
    with pytest.raises(ValueError):
        align("Ștefan", [{"text": "Stefan", "occurrence": 1, "label": "PERSON"}])
    with pytest.raises(ValueError):
        align("a", [{"text": "a", "occurrence": 1, "label": "PERSON"}] * 2)


def test_nominal_alpha_known_values_and_boundaries():
    units = [(0, 2), (3, 5)]
    first = dict(zip(units, ["PERSON", "PHONE"]))
    assert alpha_from_counts(*alpha_counts([first, first], units)) == 1
    second = dict(zip(units, ["PHONE", "PERSON"]))
    # All four ordered observations disagree; expected disagreement = 8/3.
    assert alpha_from_counts(*alpha_counts([first, second], units)) == -0.5
    assert alpha_from_counts(0, Counter(PERSON=4)) is None
    assert alpha_from_counts(*alpha_counts([first, {(0, 1): "PERSON", (3, 5): "PHONE"}], [*units, (0, 1)])) < 1


def test_stratified_sampling_reproducible_and_balanced():
    rows = [
        {"text": heading + str(i), "domain": domain}
        for heading, domain in [
            ("notice", "admin"),
            ("SCRISOARE", "clinical"),
            ("CONTRACT", "legal"),
            ("DECLARAȚIE", "legal"),
        ]
        for i in range(90)
    ]
    result = sample_rows(rows)
    assert result == sample_rows(rows)
    assert len({r["id"] for r in result}) == 300
    assert set(Counter(r["stratum"] for r in result).values()) == {75}


def test_decode_checks_stated_dob_and_gold_coverage():
    text = "CNP: 2680219165213 Data nașterii: 19.02.1968"
    row = {"text": text, "domain": "clinical", "spans": [{"start": 5, "end": 18, "label": "NATIONAL_ID"}]}
    assert decode_audit([row], "RO")["pass"]
    assert not decode_audit([{**row, "text": text.replace("1968", "1969")}], "RO")["pass"]
    assert not decode_audit([{**row, "spans": []}], "RO")["pass"]


class Response:
    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return json.dumps(self.raw).encode()


def request():
    return {"model": "test", "max_tokens": 8192, "messages": [{"role": "user", "content": "hello"}]}


def test_paid_response_cached_and_cost_logged(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    with patch("urllib.request.urlopen", return_value=Response({"usage": {"cost": 0.001}})) as call:
        client = BudgetClient(tmp_path, "protocol")
        client.complete(request())
        client.complete(request())
        BudgetClient(tmp_path, "protocol").complete(request())
        assert call.call_count == 1
        assert client.totals()["actual_usd"] == 0.001
        assert client.totals()["reserved_usd"] == 0


def test_unknown_cost_retains_liability_and_stops_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    with patch("urllib.request.urlopen", return_value=Response({"usage": {}})) as call:
        client = BudgetClient(tmp_path, "protocol")
        with pytest.raises(ValueError):
            client.complete(request())
        assert client.totals()["reserved_usd"] == reservation(request())
        with pytest.raises(RuntimeError, match="Unresolved"):
            BudgetClient(tmp_path, "protocol").complete(request())
        assert call.call_count == 1


def test_budget_reserves_before_call_and_offline_never_calls(tmp_path):
    atomic_json(tmp_path / "ledger.json", {"past": {"state": "complete", "cost": CAP - 0.001}})
    with patch("urllib.request.urlopen") as call:
        with pytest.raises(RuntimeError, match="budget"):
            BudgetClient(tmp_path, "protocol").complete(request())
        with pytest.raises(RuntimeError, match="Offline"):
            BudgetClient(tmp_path, "protocol", offline=True).complete(request())
        call.assert_not_called()


def test_panel_status_schema_preservation_and_runner(monkeypatch):
    from europriv_bench import leaderboard
    from europriv_bench.adapters import build
    from europriv_bench.runner import run_spec
    from europriv_bench.spec import DatasetRef, EvalSpec, Task

    assert leaderboard.PANEL_VALIDATED in leaderboard.CONFIG_STATUS_VALUES
    assert leaderboard.PANEL_VALIDATED != leaderboard.CITABLE_VALIDATED
    assert leaderboard.config_status_for("ro-realskeleton-v1") == "dev"
    row = {"dataset": {"config": "ro-realskeleton-v1"}, "config_status": "panel-validated"}
    assert leaderboard.annotate_row(row)["config_status"] == "panel-validated"
    with pytest.raises(ValueError, match="Unknown config_status"):
        leaderboard.annotate_row({"config_status": "native-panel-validated"})
    monkeypatch.setattr(leaderboard, "_PANEL_VALIDATED_CONFIGS", frozenset({"test-passing-panel"}))
    spec = EvalSpec(
        name="panel",
        task=Task.DETECTION,
        dataset=DatasetRef(hf_id="test", config="test-passing-panel"),
        metrics=["entity_f1"],
    )
    result = run_spec(spec, build("dummy"), rows=[{"text": "hello", "spans": []}])
    assert result["config_status"] == "panel-validated"


def test_http_rejection_keeps_body_and_reserved_cost(tmp_path, monkeypatch):
    import io
    from urllib.error import HTTPError

    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-test-key")
    rejection = HTTPError(
        "https://openrouter.ai",
        429,
        "rate limited",
        {"Retry-After": "60"},
        io.BytesIO(b'{"error":"rate limit secret-test-key"}'),
    )
    with patch("urllib.request.urlopen", side_effect=rejection):
        client = BudgetClient(tmp_path, "protocol")
        with pytest.raises(HTTPError):
            client.complete(request())
        saved = json.loads(next(tmp_path.glob("*.error.json")).read_text())
        assert saved["http_status"] == 429
        assert "secret-test-key" not in saved["body"]
        assert client.totals()["reserved_usd"] > 0


def test_majority_adjudication_preserves_conflicting_originals():
    from analysis.panel_report import adjudicate
    from europriv_bench.panel import MODELS

    row = {"id": "1", "sha256": "hash", "spans": [{"start": 0, "end": 4, "label": "PERSON"}]}
    proposals = [{"id": "0", "operation": "add", "start": 0, "end": 4, "label": "PROVIDER"}]
    reviews = {m: {"1": {"votes": [{"id": "0", "approve": i < 2, "reason": "provider"}]}} for i, m in enumerate(MODELS)}
    result = adjudicate(row, proposals, reviews)
    assert result["approved"] == 1
    assert result["conflict"] and result["overlay"] is None
    proposals.append({"id": "1", "operation": "remove", "start": 0, "end": 4, "label": "PERSON"})
    for review in reviews.values():
        review["1"]["votes"].append({"id": "1", "approve": True, "reason": "replace"})
    result = adjudicate(row, proposals, reviews)
    assert result["overlay"]["spans"] == [{"start": 0, "end": 4, "label": "PROVIDER"}]
    assert not adjudicate(row, proposals, {MODELS[0]: reviews[MODELS[0]]})["complete"]


def test_bootstrap_perfect_panel_has_unit_alpha():
    from analysis.panel_report import bootstrap
    from europriv_bench.panel import MODELS

    rows = [
        {
            "id": str(i),
            "stratum": "admin",
            "spans": [{"start": 0, "end": 1, "label": "PERSON"}, {"start": 3, "end": 4, "label": "PHONE"}],
        }
        for i in range(4)
    ]
    annotations = {m: {r["id"]: {"spans": r["spans"], "fluency": 4, "naturalness": 5} for r in rows} for m in MODELS}
    stats = bootstrap(rows, annotations)
    assert stats["alpha"]["panel"]["estimate"] == 1
    assert stats["alpha"]["panel"]["ci95"] == [1, 1]
    assert stats["ratings"][MODELS[0]]["fluency"]["ci95"] == [4, 4]


def test_all_gates_required_and_empty_panel_cannot_pass():
    from analysis.panel_report import evaluate
    from europriv_bench.panel import MODELS, digest

    rows = []
    for i in range(300):
        heading, domain, group = [
            ("SCRISOARE MEDICALĂ", "clinical", "clinical"),
            ("Către:", "admin", "admin"),
            ("CONTRACT", "legal", "contract"),
            ("DECLARAȚIE", "legal", "declaration"),
        ][i // 75]
        text = heading + "\nCNP: 2680219165213 Data nașterii: 19.02.1968"
        start = text.index("2680219165213")
        spans = [
            {"start": start, "end": start + 13, "label": "NATIONAL_ID"},
            {"start": len(text) - 10, "end": len(text), "label": "DATE"},
        ]
        rows.append(
            {"id": str(i), "text": text, "spans": spans, "sha256": digest(text), "domain": domain, "stratum": group}
        )
    annotations = {
        m: {r["id"]: {"spans": r["spans"], "fluency": 4, "naturalness": 4, "artifacts": []} for r in rows}
        for m in MODELS
    }
    stats, _, _ = evaluate("ro-realskeleton-v1", rows, rows, annotations, {}, [])
    assert stats["passed"]
    # A config with successful annotations but a failed linguistic threshold must remain dev.
    for output in annotations[MODELS[0]].values():
        output["fluency"] = 3
    stats, _, _ = evaluate("ro-realskeleton-v1", rows, rows, annotations, {}, [])
    assert not stats["passed"] and stats["config_status"] == "dev"
    stats, disagreements, _ = evaluate("ro-realskeleton-v1", rows, rows, {m: {} for m in MODELS}, {}, [])
    assert stats["n"] == 0 and not stats["passed"]
    assert len(disagreements) == 900
