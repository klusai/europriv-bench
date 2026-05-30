"""Aggregate per-spec results into the leaderboard artifact (committed to baselines/).

Schema 2: grouped by ``adapter::model_id`` so two finetunes of the same family are distinct
entries. Each row keeps full provenance from the runner.
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMA = 2


def _key(row: dict) -> str:
    return f"{row.get('adapter', '?')}::{row.get('model_id', '?')}"


def build_leaderboard(results: list[dict]) -> dict:
    """Group results by (adapter, model_id). Sorted for stable diffs."""
    grouped: dict[str, list[dict]] = {}
    for r in results:
        grouped.setdefault(_key(r), []).append(r)
    return {
        "schema": SCHEMA,
        "entries": {k: sorted(rows, key=lambda x: x.get("spec", "")) for k, rows in sorted(grouped.items())},
    }


def write_leaderboard(results: list[dict], out: str | Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_leaderboard(results), indent=2, ensure_ascii=False), encoding="utf-8")
    return out
