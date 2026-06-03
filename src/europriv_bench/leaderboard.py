"""Aggregate per-spec results into the leaderboard artifact (committed to baselines/).

Schema 3: grouped by ``adapter::model_id`` so two finetunes of the same family are distinct
entries. Each row keeps full provenance from the runner, plus two per-``(model, config)``
governance markers:

  * **contamination** — whether the eval config overlaps the model's training distribution:
    ``in_distribution`` (the model was trained on the same source data), ``clean_held_out``
    (no baseline was trained on this data — a fair held-out test), or ``unknown`` (overlap not
    established). OpenMed and tabularisai were trained on AI4Privacy, which is the source of the
    six general-text configs (en/de/fr/it/es/nl), so those rows are ``in_distribution``. The
    real-skeleton tracks (``ro-realskeleton-v1``, ``pl-realskeleton-v1``, ``it-realskeleton-v1``)
    are ``clean_held_out`` for every model. External systems that learn from none of our data — the rule-based Presidio
    orchestration baseline, and the third-party NER/IE systems ``spacy`` (OntoNotes-trained) and
    ``gliner2`` (Fastino's own pretraining) — are ``clean_held_out`` on every config. The ``kp-model`` family (kp-deid-mdeberta-280m, KLU-44) was trained on the KP
    synthetic LocalePacks ``ds-kp-general-{ro,en,pl}-50k`` (ro/en/pl only), so on a kp-model row the
    marker is *config-dependent*: ``ro-synthetic-v1`` (same RO LocalePack generator) is
    ``in_distribution``; the cross-lingual AI4Privacy configs fr/es/de/it/nl (languages never in
    training) are ``clean_held_out`` (genuine zero-shot transfer); and ``en`` (a trained language,
    but the board's en config is a *different* AI4Privacy generator — and see the KLU-54 low
    eval-loss concern) is ``unknown`` — never ``clean_held_out``.
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

# The real-skeleton tracks (RO/CNP, PL/PESEL, IT/codice-fiscale, and the legal-domain track) are
# genuinely clean held-out sets: no baseline on the board was trained on them. it-realskeleton-v1 is
# the IT LocalePack the kp-model was NOT trained on (trained ro/en/pl only) and an authored
# real-skeleton, not the AI4Privacy `it` generator. legal-realskeleton-v1 (KLU-111) reuses the RO PII
# generators but is an authored LEGAL-genre skeleton family distinct from any TRAINING config — the
# same basis on which ro-realskeleton-v1 is clean_held_out while only the general-text ro-synthetic-v1
# (the RO LocalePack at a different seed) is in_distribution. Marked clean_held_out for every model.
_CLEAN_HELD_OUT_CONFIGS = frozenset({
    "ro-realskeleton-v1", "pl-realskeleton-v1", "it-realskeleton-v1", "legal-realskeleton-v1",
})

# External systems trained on NONE of our data — so every config is a genuine clean held-out test
# for them (no train/eval overlap to flag). This covers rule-based / orchestration baselines
# (Presidio: regex/checksum recognizers + an off-the-shelf NER), and third-party NER/IE systems
# whose training corpora are unrelated to the EuroPriv-Bench gold: spaCy (en_core_web_lg, trained
# on OntoNotes 5.0) and GLiNER2 (fastino/gliner2-*, pretrained on its own data). Presidio (KLU-52)
# was the first; spaCy + GLiNER2 land via the same no-secrets CI under KLU-108.
_RULE_BASED_ADAPTERS = frozenset({"presidio", "spacy", "gliner2"})

# --- kp-deid (KlusAI `kp-model` family) contamination ----------------------------------------
# kp-deid-mdeberta-280m (KLU-44) was trained on the KP synthetic LocalePacks
# ``klusai/ds-kp-general-{ro,en,pl}-50k`` (150k general-text docs; ro/en/pl ONLY). The marker on a
# kp-model row therefore depends on the *language* and *generator* of the eval config — mirroring
# how OpenMed/tabularisai are flagged in-distribution for their AI4Privacy training source above.
_KP_TRAINED_ADAPTERS = frozenset({"kp-model"})

# Configs generated by the SAME KP LocalePack the model trained on → genuine train/test-generator
# overlap (the RO synthetic track is the RO LocalePack at a different seed). Not a fair held-out
# measurement: in_distribution. (The en/pl LocalePacks are NOT published as EuroPriv-Bench configs;
# the board's ``en`` config is AI4Privacy-sourced — a *different* generator — handled below.)
_KP_IN_DISTRIBUTION_CONFIGS = frozenset({"ro-synthetic-v1"})

# AI4Privacy general configs in *languages the model was trained on* (only ``en`` here). NOT a
# confirmed train/test split (the board's en config is AI4Privacy, a different generator than the
# model's KP en LocalePack), but the model is NOT zero-shot on English either — so it is honestly
# ``unknown`` (overlap plausible, not established), never ``clean_held_out``. The implausibly low
# KLU-44 held-out eval-loss (KLU-54) is a further reason not to treat same-language rows as clean.
_KP_TRAINED_LANGUAGE_CONFIGS = frozenset({"en"})

# AI4Privacy general configs in languages NOT in the model's training set → genuine zero-shot
# cross-lingual transfer, clean held-out for the kp-model family.
_KP_CROSS_LINGUAL_CONFIGS = _AI4PRIVACY_CONFIGS - _KP_TRAINED_LANGUAGE_CONFIGS  # fr, es, de, it, nl


def classify_contamination(adapter: str | None, config: str | None) -> str:
    """Contamination marker for one ``(adapter, config)`` pair.

    ``in_distribution`` when the adapter's model was trained on the eval config's source data;
    ``clean_held_out`` for configs no baseline was trained on; else ``unknown`` (overlap not
    established — e.g. a same-language but different-generator config, or a baseline whose training
    data we don't know).
    """
    if config in _CLEAN_HELD_OUT_CONFIGS:
        return CLEAN_HELD_OUT
    # Rule-based orchestration baselines (Presidio): no training data of ours → clean held-out
    # on EVERY config, including the AI4Privacy general configs others overlap with.
    if adapter in _RULE_BASED_ADAPTERS:
        return CLEAN_HELD_OUT
    if adapter in _AI4PRIVACY_TRAINED_ADAPTERS and config in _AI4PRIVACY_CONFIGS:
        return IN_DISTRIBUTION
    if adapter in _KP_TRAINED_ADAPTERS:
        # ro-synthetic shares the model's RO LocalePack generator → in_distribution.
        if config in _KP_IN_DISTRIBUTION_CONFIGS:
            return IN_DISTRIBUTION
        # fr/es/de/it/nl: languages absent from training → zero-shot cross-lingual, clean held-out.
        if config in _KP_CROSS_LINGUAL_CONFIGS:
            return CLEAN_HELD_OUT
        # en: trained language but different (AI4Privacy) generator → unknown, never clean_held_out.
        if config in _KP_TRAINED_LANGUAGE_CONFIGS:
            return UNKNOWN
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
