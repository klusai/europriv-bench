import io
import json
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from analysis.panel_round2 import request
from europriv_bench.panel import MODELS
from europriv_bench.panel_api import CAP, atomic_json, reservation
from europriv_bench.panel_round2_api import RetryBudgetClient


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return json.dumps({"usage": {"cost": 0.001}}).encode()


def limited():
    return HTTPError("https://openrouter.ai", 429, "limited", {}, io.BytesIO(b'{"error":"limited"}'))


def test_retry_keeps_unknown_liability_and_reuses_success_after_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    req = request(MODELS[0], [], "a")
    with patch("urllib.request.urlopen", side_effect=[limited(), Response()]) as call, patch("time.sleep"):
        client = RetryBudgetClient(tmp_path, "protocol")
        client.complete(req)
        restarted = RetryBudgetClient(tmp_path, "protocol")
        restarted.complete(req)
        assert call.call_count == 2
        assert restarted.totals()["actual_usd"] == 0.001
        assert restarted.totals()["reserved_usd"] == reservation(req)
        assert restarted.totals()["unknown_cost_requests"] == 1


def test_retries_cannot_cross_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    req = request(MODELS[0], [], "a")
    atomic_json(tmp_path / "ledger.json", {"old": {"state": "complete", "cost": CAP - 1.5 * reservation(req)}})
    with patch("urllib.request.urlopen", side_effect=limited()) as call, patch("time.sleep"):
        with pytest.raises(RuntimeError, match="budget"):
            RetryBudgetClient(tmp_path, "protocol").complete(req)
        assert call.call_count == 1


def test_exhausted_429_does_not_reset_on_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    req = request(MODELS[0], [], "a")
    with patch("urllib.request.urlopen", side_effect=[limited() for _ in range(6)]) as call, patch("time.sleep"):
        for _ in range(2):
            with pytest.raises(RuntimeError, match="Six HTTP 429"):
                RetryBudgetClient(tmp_path, "protocol").complete(req)
        assert call.call_count == 6
        assert RetryBudgetClient(tmp_path, "protocol").totals()["reserved_usd"] == pytest.approx(6 * reservation(req))


def test_pending_stops_but_offline_cache_never_dispatches(tmp_path):
    atomic_json(tmp_path / "ledger.json", {"interrupted": {"state": "pending", "reserved": 0.1}})
    with patch("urllib.request.urlopen") as call:
        with pytest.raises(RuntimeError, match="Unresolved"):
            RetryBudgetClient(tmp_path, "protocol").complete(request(MODELS[0], [], "a"))
        with pytest.raises(RuntimeError, match="Offline"):
            RetryBudgetClient(tmp_path, "protocol", offline=True).complete(request(MODELS[0], [], "a"))
        call.assert_not_called()


def test_provider_fallback_preserves_exact_models():
    for model in MODELS:
        req = request(model, [], "a")
        assert req["model"] == model and "models" not in req
        assert "only" not in req["provider"] and req["provider"]["allow_fallbacks"]
