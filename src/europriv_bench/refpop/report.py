"""RES-17 (KLU-118 v2) — attribution + labelling report emitter for the refpop / PURR module.

Auto-emits the **required source attributions** (design-doc: "``report.py`` auto-emits the required
attributions") for every vendored reference-population source on the manifest, plus the
**method citation** for the Rocher 2019 estimator, plus the mandatory **status / red-team labels**:

  * the placeholder warning when the underlying joint is the synthetic fixture, and
  * the "internal sensitivity-analysis machinery, NOT a reported metric (pending census-calibrated
    generator)" status — so a PURR number can never be lifted out of context.

This module formats; it does not compute any PURR.
"""

from __future__ import annotations

from collections.abc import Mapping

from . import load_manifest
from .build_joint import Joint
from .uniqueness import NOT_REPORTED_LABEL

ROCHER_CITATION = (
    "Population-uniqueness estimator: Rocher, Hendrickx & de Montjoye (2019), "
    '"Estimating the success of re-identifications in incomplete datasets using generative models", '
    "Nature Communications 10:3069. Method/reference code under CC-BY-4.0."
)

# The red-team Must-NOT-do rules, restated in machine-attached form so report consumers always see
# the guardrails next to any number.
RED_TEAM_RULES = (
    "Lead with ΔPURR and model rankings (robust to the reference-population choice); treat absolute "
    "PURR as reference-conditional — never a single absolute PURR scalar as meaningful.",
    "No uniqueness from independent marginals presented as meaningful — upper bound only.",
    "Post-detection residual only — uniqueness is computed on the residual QI tuple, never raw text.",
    "No cross-reference-population number transfer; no promotion out of dev; no headline use "
    "(gated on native-speaker/IAA validation, RES-77/KLU-27).",
)


def source_attributions() -> list[str]:
    """The attribution strings for every vendored reference-population source on the manifest."""
    manifest = load_manifest()
    lines: list[str] = []
    for src in manifest.get("sources", []):
        for comp in src.get("components", []):
            attribution = str(comp.get("attribution", "")).strip()
            if attribution:
                lines.append(f"[{src['id']}/{comp.get('license', '?')}] {attribution}")
    return lines


def attribution_block(joint: Joint | None = None) -> str:
    """A ready-to-print attribution + status block.

    When ``joint`` is supplied, the block leads with the joint's placeholder/status label so a
    PURR figure can never be detached from "NOT a reported metric / NOT real census data".
    """
    out: list[str] = []
    out.append("== Reference-population attribution & status ==")
    if joint is not None:
        if joint.placeholder:
            out.append(f"STATUS: {NOT_REPORTED_LABEL}")
            out.append(f"REFERENCE: {joint.label}")
        else:
            out.append(f"REFERENCE: {joint.label or 'calibrated reference population'}")
        out.append(f"axes={list(joint.axes)} population_total={joint.n}")
    out.append("")
    out.append(ROCHER_CITATION)
    out.append("")
    out.append("Vendored source attributions:")
    attrs = source_attributions()
    if attrs:
        out.extend(f"  - {line}" for line in attrs)
    else:
        out.append("  (no census population sources vendored yet — synthetic placeholder only)")
    out.append("")
    out.append("Red-team Must-NOT-do (enforced):")
    out.extend(f"  - {rule}" for rule in RED_TEAM_RULES)
    return "\n".join(out)


def annotate_result(result: Mapping[str, object], joint: Joint) -> dict[str, object]:
    """Attach the citation, attributions, and status labels to a PURR/ΔPURR result dict (copy)."""
    enriched = dict(result)
    enriched["method_citation"] = ROCHER_CITATION
    enriched["source_attributions"] = source_attributions()
    enriched["red_team_rules"] = list(RED_TEAM_RULES)
    enriched["status_label"] = (
        NOT_REPORTED_LABEL if joint.placeholder else "calibrated reference (eligible to report)"
    )
    enriched["reported_metric"] = not joint.placeholder
    return enriched
