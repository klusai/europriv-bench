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


def format_leaderboard(lb: dict) -> str:
    """Render a leaderboard dict as plain-text tables: detection F1/F2, then CNP leakage."""
    by_spec: dict[str, dict[str, dict]] = {}
    models: set[str] = set()
    for key, rows in lb.get("entries", {}).items():
        model = key.split("::", 1)[0]
        models.add(model)
        for r in rows:
            by_spec.setdefault(r["spec"], {})[model] = r
    cols = sorted(models)

    out = [f"EuroPriv-Bench leaderboard (schema {lb.get('schema')})", "", "Detection — entity F1 / F2:"]
    out.append("  " + f"{'spec':44}" + "".join(f"{m:>20}" for m in cols))
    for spec in sorted(by_spec):
        line = "  " + f"{spec[:44]:44}"
        for m in cols:
            r = by_spec[spec].get(m)
            sc = r["scores"].get("entity_f1") if r else None
            f2 = r["scores"].get("entity_f2") if r else None
            cell = f"{sc['f1']:.3f}/{f2['f2']:.3f}" if sc and f2 else "-"
            line += f"{cell:>20}"
        out.append(line)

    leak = [
        (spec, m, by_spec[spec][m]["scores"]["cnp_leakage"])
        for spec in sorted(by_spec) for m in cols
        if m in by_spec[spec] and "cnp_leakage" in by_spec[spec][m]["scores"]
    ]
    if leak:
        out += ["", "CNP re-identification leakage (leak_rate ↓ better):",
                "  " + f"{'spec':44}{'model':>14}{'leak_rate':>11}{'missed':>9}{'leaked_QI':>11}"]
        for spec, m, s in leak:
            out.append("  " + f"{spec[:44]:44}{m[:14]:>14}{s['leak_rate']:>11.3f}"
                       f"{int(s['cnp_missed']):>9}{int(s['leaked_quasi_identifiers']):>11}")
    return "\n".join(out)
