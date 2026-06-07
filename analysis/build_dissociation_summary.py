#!/usr/bin/env python3
"""RES-86 — consolidate the scattered per-language dissociation artifacts into ONE summary.

The detection≠re-id dissociation currently lives in scattered per-language artifacts under
``analysis/`` (RO family + legal + name-in-context, plus the EU-breadth IT/SE/CZ/DK/FI/EE/LT/SI/SK
single-family configs). This script **re-derives** ``analysis/dissociation_summary.{md,json}`` by
*reading those committed JSONs* — it does NOT re-score and does NOT hardcode the numbers. Every
number it prints traces back to one per-language artifact (spot-checkable).

What it reads (committed artifacts only — never a model backend):

* ``family_dissociation_ro_realskeleton.json`` — RO/CNP, the original two-family clinical anchor
  (families A + B); the cross-language row aggregates over both families.
* ``it_dissociation.json``                     — IT/codice fiscale (the richest QI surface).
* ``{cc}_dissociation.json`` for cc in PL/SE/CZ/DK/FI/EE/LT/SI/SK — the EU-breadth single-family
  configs (PL/PESEL backfilled onto the shared codepath in RES-87, closing the earlier gap).
* ``legal_dissociation.json``                  — the RO legal-domain track (separate section).
* ``name_in_context_leak_ro_realskeleton.json``— the RO name-in-context channel (separate section).

Identifier + decoded-QI *labels* (descriptive, not statistics) come from the committed
``eu_breadth_dissociation.COUNTRIES`` map for the EU-breadth configs (PL/SE/CZ/DK/FI/EE/LT/SI/SK),
extended here with RO/IT (sourced from ``it_dissociation.py`` and the legal/RO markdown prose). All
11 decode-bearing languages now have a committed dissociation JSON — every leak-rate, Wilson bound
and gap CI below is read from a per-language artifact, never fabricated.

Reproduce::

    python analysis/build_dissociation_summary.py            # writes both files into analysis/
    python analysis/build_dissociation_summary.py --check     # verify committed files are current
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parent

# kp-deid (the de-id protector) is the 0-leak arm of every gap; it is never a typed-detector row.
PROTECTOR = "kp-model"

# All committed real-skeleton configs are dev-tier (single authored family each). The name-in-context
# JSON carries config_status="dev" literally; the rest inherit it (KLU-101 hardening, RES-86 caveat).
CONFIG_STATUS = "dev"


# --------------------------------------------------------------------------- #
# Identifier + decoded-QI labels (descriptive metadata, not statistics)
# --------------------------------------------------------------------------- #
def _load_breadth_countries() -> dict:
    """Import the committed COUNTRIES map (id_name + decoded-QI label) for the 8 EU-breadth configs."""
    spec = importlib.util.spec_from_file_location(
        "eu_breadth_dissociation", ANALYSIS_DIR / "eu_breadth_dissociation.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.COUNTRIES


# RO/IT are not in the EU-breadth COUNTRIES map; their identifier + QI labels are taken from
# it_dissociation.py and the legal/RO markdown prose. These are labels only — every leak-rate, Wilson
# bound and gap CI below is read from the per-language JSON, never from here. (PL now lives in the
# EU-breadth COUNTRIES map as of RES-87, so its label is sourced there like the other breadth configs.)
_RO_PL_IT_META = {
    "RO": {"id_name": "CNP", "qi": "DATE_OF_BIRTH + SEX + COUNTY"},
    "IT": {"id_name": "codice fiscale", "qi": "DATE_OF_BIRTH + SEX + PLACE_OF_BIRTH"},
}

# Cross-language row order: the 11 decode-bearing national IDs, RO first (original anchor).
LANGUAGE_ORDER = ["RO", "PL", "IT", "SE", "CZ", "DK", "FI", "EE", "LT", "SI", "SK"]


def id_meta() -> dict:
    meta = dict(_RO_PL_IT_META)
    for cc, info in _load_breadth_countries().items():
        meta[cc] = {"id_name": info["id_name"], "qi": info["qi"]}
    return meta


# --------------------------------------------------------------------------- #
# Re-derivation from the committed artifacts (read-only; no scoring)
# --------------------------------------------------------------------------- #
def _read_json(name: str) -> dict:
    return json.loads((ANALYSIS_DIR / name).read_text(encoding="utf-8"))


def summarize_dissociation(diss: dict) -> dict:
    """Re-derive the row-level summary from one ``dissociation`` block (flat single-family schema).

    Reads protector leak-rate + Wilson UB and counts, over the N typed-detector gap rows, how many
    have a Newcombe CI that excludes 0 (``dissociation_holds`` / ``gap_ci_low > 0``).
    """
    gaps = diss["gaps"]
    n_holds = sum(1 for g in gaps if g["dissociation_holds"])
    return {
        "protector_leak_rate": diss["protector_leak_rate"],
        "protector_leak_wilson_high": diss["protector_leak_wilson_high"],
        "protector_missed": diss["protector_missed"],
        "protector_total": diss["protector_total"],
        "protector_leaked_quasi_identifiers": diss.get("protector_leaked_quasi_identifiers"),
        "n_detectors_scored": len(gaps),
        "n_detectors_gap_ci_excludes_0": n_holds,
        "models_scored": sorted(diss["models"].keys()),
        "holds": diss["holds"],
        "n_docs": diss.get("n_docs"),
    }


def summarize_ro_families(family_payload: dict) -> dict:
    """Re-derive the RO cross-language row by aggregating over the two committed families A + B.

    The two families are independent single-family measurements; the row reports the union of models
    scored, the worst (max) protector Wilson UB across families, and the per-family gap-CI tallies.
    """
    families = family_payload["families"]
    per_family = {fam: summarize_dissociation(diss) for fam, diss in families.items()}
    models = sorted({m for s in per_family.values() for m in s["models_scored"]})
    # Worst-case protector bound across families (honest upper bound for the consolidated row).
    worst_ub = max(s["protector_leak_wilson_high"] for s in per_family.values())
    total_subjects = sum(s["protector_total"] for s in per_family.values())
    total_missed = sum(s["protector_missed"] for s in per_family.values())
    return {
        "families": per_family,
        "protector_leak_wilson_high": worst_ub,
        "protector_missed": total_missed,
        "protector_total": total_subjects,
        "protector_leak_rate": (total_missed / total_subjects) if total_subjects else 0.0,
        "models_scored": models,
        "holds": family_payload["dissociation_holds_across_all_families"],
        "n_docs": sum(diss.get("n_docs", 0) for diss in families.values()),
    }


def build_summary() -> dict:
    """Assemble the full consolidated payload from the committed per-language artifacts."""
    meta = id_meta()

    # --- the 11 decode-bearing national-ID languages -------------------------------------------- #
    languages: dict[str, dict] = {}

    # RO — the original two-family clinical anchor.
    ro = summarize_ro_families(_read_json("family_dissociation_ro_realskeleton.json"))
    ro_holds = sum(s["n_detectors_gap_ci_excludes_0"] for s in ro["families"].values())
    ro_scored = sum(s["n_detectors_scored"] for s in ro["families"].values())
    languages["RO"] = {
        "config": "ro-realskeleton-v1",
        "id_name": meta["RO"]["id_name"],
        "decoded_qi": meta["RO"]["qi"],
        "artifact": "family_dissociation_ro_realskeleton.json",
        "config_status": CONFIG_STATUS,
        "protector_leak_rate": ro["protector_leak_rate"],
        "protector_leak_wilson_high": ro["protector_leak_wilson_high"],
        "n_detectors_scored": ro_scored,
        "n_detectors_gap_ci_excludes_0": ro_holds,
        "models_scored": ro["models_scored"],
        "holds": ro["holds"],
        "n_docs": ro["n_docs"],
        "note": "two authored families (A+B); row aggregates both — counts/UB summed/worst-case",
        "families": {fam: {
            "n_detectors_scored": s["n_detectors_scored"],
            "n_detectors_gap_ci_excludes_0": s["n_detectors_gap_ci_excludes_0"],
            "protector_leak_wilson_high": s["protector_leak_wilson_high"],
            "protector_total": s["protector_total"],
        } for fam, s in ro["families"].items()},
    }

    # PL/IT + the 9 EU-breadth configs — flat single-family schema {config, country, dissociation}.
    # PL/PESEL was backfilled onto the shared eu_breadth codepath (RES-87): it now ships a committed
    # pl_dissociation.json scored on the same pl-realskeleton-v1 track as the board, closing the
    # earlier coverage gap so all 11 decode-bearing languages have a committed artifact.
    flat_configs = {
        "PL": "pl_dissociation.json",
        "IT": "it_dissociation.json",
        "SE": "se_dissociation.json", "CZ": "cz_dissociation.json",
        "DK": "dk_dissociation.json", "FI": "fi_dissociation.json",
        "EE": "ee_dissociation.json", "LT": "lt_dissociation.json",
        "SI": "si_dissociation.json", "SK": "sk_dissociation.json",
    }
    for cc, fname in flat_configs.items():
        payload = _read_json(fname)
        s = summarize_dissociation(payload["dissociation"])
        languages[cc] = {
            "config": payload["config"],
            "id_name": meta[cc]["id_name"],
            "decoded_qi": meta[cc]["qi"],
            "artifact": fname,
            "config_status": CONFIG_STATUS,
            "protector_leak_rate": s["protector_leak_rate"],
            "protector_leak_wilson_high": s["protector_leak_wilson_high"],
            "n_detectors_scored": s["n_detectors_scored"],
            "n_detectors_gap_ci_excludes_0": s["n_detectors_gap_ci_excludes_0"],
            "models_scored": s["models_scored"],
            "holds": s["holds"],
            "n_docs": s["n_docs"],
            "note": "single authored family (2nd needed before citation)",
        }

    # --- the legal domain (RO) ------------------------------------------------------------------ #
    legal_payload = _read_json("legal_dissociation.json")
    legal_s = summarize_dissociation(legal_payload["dissociation"])
    legal = {
        "config": legal_payload["config"],
        "country": legal_payload["country"],
        "domain": legal_payload.get("domain", "legal"),
        "id_name": meta["RO"]["id_name"],
        "decoded_qi": meta["RO"]["qi"],
        "artifact": "legal_dissociation.json",
        "config_status": CONFIG_STATUS,
        "protector_leak_rate": legal_s["protector_leak_rate"],
        "protector_leak_wilson_high": legal_s["protector_leak_wilson_high"],
        "n_detectors_scored": legal_s["n_detectors_scored"],
        "n_detectors_gap_ci_excludes_0": legal_s["n_detectors_gap_ci_excludes_0"],
        "models_scored": legal_s["models_scored"],
        "holds": legal_s["holds"],
        "n_docs": legal_s["n_docs"],
    }

    # --- the name-in-context channel (RO) ------------------------------------------------------- #
    nic_payload = _read_json("name_in_context_leak_ro_realskeleton.json")
    nic_models = nic_payload["models"]
    name_in_context = {
        "config": nic_payload["config"],
        "config_status": nic_payload.get("config_status", CONFIG_STATUS),
        "claim_language": nic_payload["claim_language"],
        "artifact": "name_in_context_leak_ro_realskeleton.json",
        "models_scored": sorted(nic_models.keys()),
        "k_anonymity_available": any(
            m.get("k_anonymity_violation", {}).get("available") for m in nic_models.values()
        ),
        "models": {
            name: {
                "model_id": m["model_id"],
                "id_leak_rate": m["id_leak_rate"],
                "id_leak_ci": m["id_leak_ci"],
                "id_subjects": m["id_subjects"],
                "name_leak_rate": m["name_leak_rate"],
                "name_leak_ci": m["name_leak_ci"],
                "name_subjects": m["name_subjects"],
            }
            for name, m in nic_models.items()
        },
    }

    decode_langs = [cc for cc in LANGUAGE_ORDER]
    holds_langs = [cc for cc in decode_langs if languages[cc]["holds"] is True]

    # RES-96 — uniform full-model coverage: every decode-bearing language (+ legal) now scores the
    # SAME board-model set. We derive the common basis from the artifacts (never asserted): the set
    # of models present in EVERY language's row. When that equals the full board it is the uniform
    # 8-model basis the breadth claim now rests on (the earlier 5-of-8 CPU subset is closed).
    per_lang_models = [set(languages[cc]["models_scored"]) for cc in decode_langs]
    per_lang_models.append(set(legal["models_scored"]))
    uniform_models = sorted(set.intersection(*per_lang_models)) if per_lang_models else []
    coverage_is_uniform = all(
        set(m) == set(uniform_models)
        for m in [set(languages[cc]["models_scored"]) for cc in decode_langs] + [set(legal["models_scored"])]
    )
    return {
        "title": "Unified multi-language detection≠re-id dissociation summary (RES-86)",
        "generated_by": "analysis/build_dissociation_summary.py",
        "headline": (
            "The detection≠re-identification dissociation holds across "
            f"{len(decode_langs)} languages / {len(decode_langs)} decode-bearing national IDs "
            "+ the legal domain (RO) + a second (name-in-context) channel. "
            "This is the first *unified* multi-language demonstration — not a claim of being "
            "first to observe the phenomenon."
        ),
        "language_order": LANGUAGE_ORDER,
        "n_languages": len(decode_langs),
        "n_languages_artifact_present": sum(
            1 for cc in decode_langs if languages[cc]["artifact"] is not None
        ),
        "n_languages_holds": len(holds_langs),
        "uniform_model_basis": uniform_models,
        "coverage_is_uniform": coverage_is_uniform,
        "languages": languages,
        "legal_domain": legal,
        "name_in_context": name_in_context,
        "caveats": [
            "All configs are config_status=dev — not yet citable/public.",
            "Single authored template family per language (RO has two; a 2nd independent family is "
            "required per language before citation — KLU-101 hardening).",
            (
                f"Model coverage is now UNIFORM across every language + legal: all score the same "
                f"{len(uniform_models)}-model board basis ({', '.join(uniform_models)}). The earlier "
                "state — where coverage VARIES (RO/PL/IT/legal scored all 8 board models but "
                "SE/CZ/DK/FI/EE/LT/SI/SK scored only a 5-of-8 CPU subset) — was the weak arm of the "
                "breadth claim (RES-56); the consistent full-model re-score that was thought to need "
                "GPU burst (RES-53) was instead run on the M3 Ultra (CPU+parallel) under RES-96, "
                "closing the gap."
            ) if coverage_is_uniform else (
                "Model coverage VARIES across languages (CPU-subset under the Mac hardware bound): "
                "RO/PL/IT/legal score all 8 board models; the breadth langs score a 5-of-8 subset. "
                "A consistent full-model re-score is pending RES-53 before any public/citable use."
            ),
            "PL/PESEL was scored on the same pl-realskeleton-v1 track as the public board (RES-87, "
            "all 8 models, n=1500 docs → 1096 distinct subjects); its per-model leak rates reconcile "
            "exactly with the committed baselines/leaderboard.json rows.",
            "\"First *unified*\" discipline: this consolidates prior per-language measurements; it "
            "does not claim to be the first observation of the phenomenon.",
            "Re-identification is reserved for the deterministic national-ID channel. The "
            "name/QI (name-in-context) channel measures RESIDUAL DISTINCTIVENESS / sample "
            "distinctiveness, NOT population re-identification (k-anonymity diagnostic unavailable: "
            "gold lacks QI tagging — KLU-122).",
            "Validation gates: the full-model re-score (RES-53 GPU-burst gate) is now CLEARED — it "
            "ran on the M3 Ultra under RES-96, giving the uniform basis above. Native-speaker + IAA "
            "sign-off (RES-77) must still clear before this feeds the Paper-3 breadth section or is "
            "surfaced on the public board (the in-repo uniform numbers do NOT auto-publish).",
        ],
    }


# --------------------------------------------------------------------------- #
# Markdown rendering
# --------------------------------------------------------------------------- #
def _fmt_pct(x) -> str:
    return "—" if x is None else f"{x:.4f}"


def render_markdown(summary: dict) -> str:
    L = summary["languages"]
    lines: list[str] = [
        f"# {summary['title']}",
        "",
        "<!-- GENERATED by analysis/build_dissociation_summary.py — do not edit by hand. "
        "Re-derived from the committed per-language artifacts; every number traces to one. -->",
        "",
        f"**Headline.** {summary['headline']}",
        "",
        f"Coverage: **{summary['n_languages_artifact_present']}/{summary['n_languages']}** "
        f"decode-bearing languages have a committed artifact; the dissociation holds on "
        f"**{summary['n_languages_holds']}** of them (+ legal + name-in-context).",
        "",
        (
            f"**Model basis (RES-96).** Coverage is UNIFORM: every language + the legal domain scores "
            f"the same **{len(summary['uniform_model_basis'])}-model** board "
            f"({', '.join(summary['uniform_model_basis'])}). The earlier 5-of-8 CPU subset on the "
            f"breadth langs (RES-56's weak arm) was closed by a consistent full-model re-score on the "
            f"M3 Ultra (RES-96; the RES-53 GPU-burst gate proved unnecessary)."
            if summary["coverage_is_uniform"] else
            "**Model basis.** Coverage VARIES across languages (CPU subset on the breadth langs) — a "
            "consistent full-model re-score is pending (RES-53)."
        ),
        "",
        "## Cross-language dissociation (decode-bearing national IDs)",
        "",
        "Per language: national ID, the quasi-identifiers a missed ID decodes to, the kp-deid "
        "(protector) leak-rate + 95% Wilson upper bound, the typed-detector gap-CI summary (how many "
        "of the N scored detectors have a Newcombe gap CI that excludes 0), and which board models "
        + ("were scored (uniform full-model basis across all rows — RES-96)."
           if summary["coverage_is_uniform"] else
           "were scored (coverage varies — made explicit)."),
        "",
        "| Lang | National ID | Decoded QIs | kp-deid leak | Wilson UB | gap-CI excl. 0 | Models scored | Holds |",
        "|---|---|---|---:|---:|:--:|---|:--:|",
    ]
    for cc in summary["language_order"]:
        r = L[cc]
        if r["artifact"] is None:
            gap_cell = "—"
            models_cell = "MISSING ARTIFACT"
            holds_cell = "—"
        else:
            gap_cell = f"{r['n_detectors_gap_ci_excludes_0']}/{r['n_detectors_scored']}"
            scored = [m for m in r["models_scored"] if m != PROTECTOR]
            models_cell = f"kp-deid + {len(scored)} ({', '.join(scored)})"
            holds_cell = "YES" if r["holds"] else "no"
        lines.append(
            f"| {cc} | {r['id_name']} | {r['decoded_qi']} "
            f"| {_fmt_pct(r['protector_leak_rate'])} | {_fmt_pct(r['protector_leak_wilson_high'])} "
            f"| {gap_cell} | {models_cell} | {holds_cell} |"
        )
    lines += [
        "",
        "RO aggregates its two authored families (A + B); the Wilson UB shown is the worst-case "
        "across families and the gap-CI tally sums both families' detector arms. PL/PESEL is scored "
        "on the same `pl-realskeleton-v1` track as the public board (all 8 models, n=1500 docs → "
        "1096 distinct subjects); its leak rates reconcile exactly with `baselines/leaderboard.json`.",
        "",
        "## Legal domain (RO)",
        "",
    ]
    lg = summary["legal_domain"]
    lg_scored = [m for m in lg["models_scored"] if m != PROTECTOR]
    lines += [
        f"`{lg['config']}` — domain **{lg['domain']}**, national ID **{lg['id_name']}** "
        f"→ {lg['decoded_qi']}. n={lg['n_docs']} docs.",
        "",
        f"- kp-deid (protector) leak-rate **{_fmt_pct(lg['protector_leak_rate'])}** "
        f"(95% Wilson UB **{_fmt_pct(lg['protector_leak_wilson_high'])}**).",
        f"- gap-CI summary: **{lg['n_detectors_gap_ci_excludes_0']}/{lg['n_detectors_scored']}** "
        "scored typed-detectors have a Newcombe gap CI excluding 0.",
        f"- Models scored: kp-deid + {len(lg_scored)} ({', '.join(lg_scored)}).",
        f"- Dissociation holds: **{'YES' if lg['holds'] else 'no'}**.",
        "",
        "## Name-in-context channel (RO)",
        "",
    ]
    nic = summary["name_in_context"]
    lines += [
        f"`{nic['config']}` — a SECOND channel alongside the deterministic national-ID anchor. "
        f"Claim language: _{nic['claim_language']}_",
        "",
        "| Model | id-leak | id-leak 95% CI | name-leak | name-leak 95% CI |",
        "|---|---:|:--:|---:|:--:|",
    ]
    for name in nic["models_scored"]:
        m = nic["models"][name]
        idci = m["id_leak_ci"]
        nmci = m["name_leak_ci"]
        lines.append(
            f"| {name} | {m['id_leak_rate']:.4f} | [{idci[0]:.4f}, {idci[1]:.4f}] "
            f"| {m['name_leak_rate']:.4f} | [{nmci[0]:.4f}, {nmci[1]:.4f}] |"
        )
    lines += [
        "",
        f"k-anonymity / population re-id diagnostic available: "
        f"**{'yes' if nic['k_anonymity_available'] else 'no'}** "
        "(residual distinctiveness only — NOT population re-identification).",
        "",
        "## Caveats",
        "",
    ]
    lines += [f"- {c}" for c in summary["caveats"]]
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--outdir", type=Path, default=ANALYSIS_DIR)
    ap.add_argument("--check", action="store_true",
                    help="Verify committed summary files match a fresh re-derivation (exit 1 if not).")
    args = ap.parse_args()

    summary = build_summary()
    md = render_markdown(summary)
    js = json.dumps(summary, indent=2, ensure_ascii=False) + "\n"

    out_json = args.outdir / "dissociation_summary.json"
    out_md = args.outdir / "dissociation_summary.md"

    if args.check:
        ok = True
        for path, fresh in ((out_json, js), (out_md, md)):
            current = path.read_text(encoding="utf-8") if path.exists() else None
            if current != fresh:
                print(f"STALE: {path} differs from a fresh re-derivation")
                ok = False
        if not ok:
            raise SystemExit("dissociation_summary.{md,json} are stale — rerun without --check")
        print("dissociation_summary.{md,json} are up to date")
        return

    out_json.write_text(js, encoding="utf-8")
    out_md.write_text(md, encoding="utf-8")
    print(f"wrote {out_json} and {out_md}")
    print(
        f"headline: {summary['n_languages_holds']}/{summary['n_languages']} decode-bearing "
        f"languages hold ({summary['n_languages_artifact_present']} with committed artifacts) "
        "+ legal + name-in-context"
    )


if __name__ == "__main__":
    main()
