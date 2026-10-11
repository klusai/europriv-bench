"""Auditable OpenRouter transport with persistent conservative cost reservations."""

from __future__ import annotations

import json
import math
import os
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from .panel import digest

CAP = 25.0
PRICES = {"prompt": 0.60, "completion": 3.0, "request": 0.0}  # USD / million tokens


def atomic_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def reservation(request: dict) -> float:
    # UTF-8 byte count bounds tokens for these byte-fallback tokenizers; extra framing margin.
    prompt_bound = len(json.dumps(request["messages"], ensure_ascii=False).encode()) + 4096
    return (prompt_bound * PRICES["prompt"] + request["max_tokens"] * PRICES["completion"]) / 1e6


class BudgetClient:
    """One process (caller holds file lock); threads share a durable global ledger."""

    def __init__(self, directory: Path, protocol_sha: str, offline: bool = False):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.ledger_path = directory / "ledger.json"
        self.ledger = json.loads(self.ledger_path.read_text()) if self.ledger_path.exists() else {}
        self.protocol_sha = protocol_sha
        self.lock = threading.RLock()
        self.stopped = any(x["state"] != "complete" for x in self.ledger.values())
        self.offline = offline

    def totals(self) -> dict:
        with self.lock:
            entries = list(self.ledger.values())
            return {
                "actual_usd": sum(x.get("cost", 0) for x in entries),
                "reserved_usd": sum(x["reserved"] for x in entries if x["state"] != "complete"),
                "responses": sum(x["state"] == "complete" for x in entries),
                "attempts": len(entries),
                "unknown_cost_requests": sum(x["state"] != "complete" for x in entries),
            }

    def complete(self, request: dict) -> dict:
        key = digest({"protocol": self.protocol_sha, "request": request})
        cache = self.directory / f"{key}.json"
        with self.lock:
            if cache.exists() and self.ledger.get(key, {}).get("state") == "complete":
                return json.loads(cache.read_text())["response"]
            if self.offline:
                raise RuntimeError("Offline cache miss")
            if self.stopped or key in self.ledger:
                raise RuntimeError("Unresolved request liability: no further paid calls")
            bound = reservation(request)
            totals = self.totals()
            if totals["actual_usd"] + totals["reserved_usd"] + bound >= CAP:
                self.stopped = True
                raise RuntimeError("Hard USD 25 budget would be reached; refusing request")
            self.ledger[key] = {
                "state": "pending",
                "reserved": bound,
                "model": request["model"],
                "timestamp": datetime.now(UTC).isoformat(),
            }
            atomic_json(self.ledger_path, self.ledger)
        atomic_json(cache.with_suffix(".request.json"), {"request": request, "protocol_sha256": self.protocol_sha})
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(request).encode(),
                headers={
                    "Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
                    "Content-Type": "application/json",
                    "X-Title": "RES-77 synthetic panel audit",
                },
            )
            with urllib.request.urlopen(req, timeout=180) as response:
                raw = json.load(response)
            atomic_json(cache, {"request": request, "protocol_sha256": self.protocol_sha, "response": raw})
            cost = raw.get("usage", {}).get("cost")
            if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
                raise ValueError("Missing/invalid usage.cost; reservation retained")
            with self.lock:
                self.ledger[key].update(state="complete", cost=cost, response_id=raw.get("id"))
                atomic_json(self.ledger_path, self.ledger)
                if cost > bound or self.totals()["actual_usd"] >= CAP:
                    self.stopped = True
                    raise ValueError("Provider exceeded reserved cost; abort")
            return raw
        except urllib.error.HTTPError as exc:
            # Rejections can carry useful rate-limit diagnostics, but never assume zero cost.
            body = exc.read().decode("utf-8", errors="replace")
            secret = os.environ.get("OPENROUTER_API_KEY", "")
            if secret:
                body = body.replace(secret, "[redacted]")
            atomic_json(
                cache.with_suffix(".error.json"),
                {
                    "request": request,
                    "http_status": exc.code,
                    "body": body,
                    "retry_after": exc.headers.get("Retry-After"),
                },
            )
            with self.lock:
                self.stopped = True
            raise
        except Exception:
            with self.lock:
                self.stopped = True
            raise
