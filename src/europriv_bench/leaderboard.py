"""Aggregate per-spec results into the leaderboard artifact (committed to baselines/).

Schema 3: grouped by ``adapter::model_id`` so two finetunes of the same family are distinct
entries. Each row keeps full provenance from the runner, plus two per-``(model, config)``
governance markers:

  * **contamination** — whether the eval config overlaps the model's training distribution:
    ``in_distribution`` (the model was trained on the same source data), ``clean_held_out``
    (no baseline was trained on this data — a fair held-out test), or ``unknown`` (overlap not
    established). OpenMed and tabularisai were trained on AI4Privacy, which is the source of the
    six general-text configs (en/de/fr/it/es/nl), so those rows are ``in_distribution``. The
    real-skeleton tracks (``ro-realskeleton-v1``, ``pl-realskeleton-v1``) are ``clean_held_out``
    for every model.
  * **config_status** — ``dev`` (default; usable for iteration, MUST NOT be cited as a validated
    result) or ``citable-validated`` (promotable ONLY after native-speaker review + IAA sign-off
    on the gold data — that gate lands in KLU-27). Everything defaults to ``dev`` here: no config
    is citable-validated until that sign-off lands. See GOVERNANCE.md (`config_status` policy).
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMA = 3

# Contamination enum (per model, config). See module docstring + GOVERNANCE.md.
IN_DISTRIBUTION = "in_distribution"
CLEAN_HELD_OUT = "clean_held_out"
UNKNOWN = "unknown"
CONTAMINATION_VALUES = frozenset({IN_DISTRIBUTION, CLEAN_HELD_OUT, UNKNOWN})

# config_status enum (per model, config). Default everything to ``dev`` until KLU-27's
# native-speaker / IAA sign-off promotes a config to ``citable-validated``.
DEV = "dev"
CITABLE_VALIDATED = "citable-validated"
CONFIG_STATUS_VALUES = frozenset({DEV, CITABLE_VALIDATED})
DEFAULT_CONFIG_STATUS = DEV

# Adapters whose models were trained on AI4Privacy, the source of the six general-text configs
# below. Their rows on those configs are in-distribution (train/eval overlap) and so are NOT a
# fair held-out measurement — the marker exists to flag exactly that.
_AI4PRIVACY_TRAINED_ADAPTERS = frozenset({"openmed", "tabularisai"})
_AI4PRIVACY_CONFIGS = frozenset({"en", "de", "fr", "it", "es", "nl"})

# The real-skeleton tracks (RO/CNP, PL/PESEL) are genuinely clean held-out sets: no baseline on
# the board was trained on them. Marked clean_held_out for every model.
_CLEAN_HELD_OUT_CONFIGS = frozenset({"ro-realskeleton-v1", "pl-realskeleton-v1"})


def classify_contamination(adapter: str | None, config: str | None) -> str:
    """Contamination marker for one ``(adapter, config)`` pair.

    ``in_distribution`` when the adapter's model was trained on the eval config's source data;
    ``clean_held_out`` for configs no baseline was trained on; else ``unknown`` (overlap not
    established — e.g. the synthetic RO track, or a baseline whose training data we don't know).
    """
    if config in _CLEAN_HELD_OUT_CONFIGS:
        return CLEAN_HELD_OUT
    if adapter in _AI4PRIVACY_TRAINED_ADAPTERS and config in _AI4PRIVACY_CONFIGS:
        return IN_DISTRIBUTION
    return UNKNOWN


def annotate_row(row: dict) -> dict:
    """Return ``row`` with schema-3 markers filled in (idempotent; preserves existing values).

    ``contamination`` is derived from ``(adapter, dataset.config)`` when absent; ``config_status``
    defaults to ``dev``. Never overwrites a value already present, so a future curated promotion to
    ``citable-validated`` (KLU-27) survives re-aggregation.
    """
    if "contamination" not in row:
        row["contamination"] = classify_contamination(row.get("adapter"), (row.get("dataset") or {}).get("config"))
    if "config_status" not in row:
        row["config_status"] = DEFAULT_CONFIG_STATUS
    return row


def _key(row: dict) -> str:
    return f"{row.get('adapter', '?')}::{row.get('model_id', '?')}"


def build_leaderboard(results: list[dict]) -> dict:
    """Group results by (adapter, model_id). Sorted for stable diffs.

    Each row is annotated with the schema-3 governance markers (``contamination``,
    ``config_status``) if it doesn't already carry them.
    """
    grouped: dict[str, list[dict]] = {}
    for r in results:
        grouped.setdefault(_key(r), []).append(annotate_row(r))
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
