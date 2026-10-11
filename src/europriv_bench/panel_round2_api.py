"""Serial round-2 retry policy; preserves round-1 transport and all retry liabilities."""

from __future__ import annotations

import json
import random
import time
import urllib.error
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from .panel import digest
from .panel_api import BudgetClient, atomic_json


class RetryBudgetClient(BudgetClient):
    """Caller holds process lock; at most six attempts per immutable request.

    Each attempt uses the original conservative transport/ledger, under an
    attempt-specific protocol fingerprint. A 429 is retained as an unknown-cost
    liability, but explicitly permits another reserved attempt in this protocol.
    All other incomplete entries still stop dispatch, including across restarts.
    """

    def __init__(self, directory, protocol_sha, offline=False):
        super().__init__(directory, protocol_sha, offline)
        self.root_protocol_sha = protocol_sha
        self.stopped = any(x["state"] not in {"complete", "rate_limited"} for x in self.ledger.values())

    def complete(self, request):
        for attempt in range(6):
            self.protocol_sha = digest({"protocol": self.root_protocol_sha, "attempt": attempt})
            key = digest({"protocol": self.protocol_sha, "request": request})
            entry = self.ledger.get(key, {})
            if entry.get("state") == "rate_limited":
                if not self.offline:
                    self._wait(entry)
                continue
            try:
                return super().complete(request)
            except urllib.error.HTTPError as exc:
                if exc.code != 429:
                    raise
                now = datetime.now(UTC)
                delay = min(32, 2**attempt) + random.SystemRandom().random()
                retry_after = exc.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        try:
                            delay = max(delay, (parsedate_to_datetime(retry_after) - now).total_seconds())
                        except (ValueError, TypeError):
                            pass
                entry = self.ledger[key]
                entry.update(
                    state="rate_limited",
                    root_protocol_sha256=self.root_protocol_sha,
                    attempt=attempt,
                    retry_at=now.timestamp() + delay,
                )
                atomic_json(self.ledger_path, self.ledger)
                self.stopped = False
                if attempt < 5:
                    self._wait(entry)
        raise RuntimeError("Six HTTP 429 attempts exhausted; stop run, retain all liabilities")

    @staticmethod
    def _wait(entry):
        delay = max(0, entry["retry_at"] - datetime.now(UTC).timestamp())
        if delay > 60:
            raise RuntimeError("Retry-After exceeds 60 seconds; resume later without resetting ledger")
        if delay:
            time.sleep(delay)

    def evidence(self):
        return {
            **self.totals(),
            "protocol_sha256": self.root_protocol_sha,
            "known_plus_reserved_usd": self.totals()["actual_usd"] + self.totals()["reserved_usd"],
            "rate_limited_attempts": sum(e["state"] == "rate_limited" for e in self.ledger.values()),
            "ledger_sha256": digest(json.loads(self.ledger_path.read_text())) if self.ledger_path.exists() else None,
        }
