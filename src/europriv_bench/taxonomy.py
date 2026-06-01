"""The harmonized KlusAI Privacy (KP) entity taxonomy + BIOES label space + crosswalk.

This is *standardization*, not invention: every target scheme below is mature. The
contribution is one GDPR-aligned crosswalk that unifies them across general + legal +
clinical for European jurisdictions, plus explicit GDPR-Art.9 (special-category) and
direct-vs-quasi-identifier marking (à la TAB / MultiGraSCCo).

Entity tags use BIOES so the label space is directly compatible with `openai/privacy-filter`
(enabling head-to-head scoring).

The crosswalk is **not** hand-coded here: it is the single, versioned source of truth in
``conf/taxonomy.yaml``, loaded once at import. ``TAXONOMY_VERSION`` below is the in-code
anchor; the YAML must echo the same ``version`` or import fails loud (see GOVERNANCE.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

# Bump whenever the entity set or BIOES label space changes. Stamped into eval specs and the
# leaderboard so dataset gold labels, model label maps, and scores are provably the same version.
# MUST equal `version` in conf/taxonomy.yaml — the loader fails loud on mismatch.
TAXONOMY_VERSION = "0.2.0"  # 0.2.0: added NATIONAL_ID + COMPANY_ID; national IDs split out of ACCOUNT_ID


class Tier(str, Enum):
    CORE = "core"          # shared base — overlaps OpenAI's 8 + AI4Privacy core
    CLINICAL = "clinical"  # PHI — HIPAA-18 anchored
    LEGAL = "legal"        # legal quasi-identifiers — MAPA anchored


class IdentifierClass(str, Enum):
    DIRECT = "direct"      # identifies an individual on its own
    QUASI = "quasi"        # identifies in combination (re-identification risk)


@dataclass(frozen=True)
class EntityType:
    """One harmonized entity type with its crosswalk to external schemes."""

    name: str                      # canonical KP label, e.g. "PERSON"
    tier: Tier
    identifier_class: IdentifierClass
    gdpr_special: bool = False     # GDPR Art. 9 special category (e.g. health)
    crosswalk: dict[str, list[str]] = field(default_factory=dict)  # scheme -> source labels


# --- Single source of truth: conf/taxonomy.yaml -------------------------------------------
# Resolve relative to the package, walking up to the repo root (editable install) and falling
# back to package-bundled data (wheel install). Keeps load behavior identical either way.
_CONF_NAME = "taxonomy.yaml"


def _locate_conf() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "conf" / _CONF_NAME
        if candidate.is_file():
            return candidate
    # Fallback: bundled alongside the package (wheel/sdist via package_data).
    bundled = here.parent / "conf" / _CONF_NAME
    if bundled.is_file():
        return bundled
    raise FileNotFoundError(
        f"taxonomy config {_CONF_NAME!r} not found (looked under conf/ up the tree from {here})"
    )


def _load_taxonomy() -> tuple[tuple[str, ...], list[EntityType]]:
    with open(_locate_conf(), encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    yaml_version = doc.get("version")
    if yaml_version != TAXONOMY_VERSION:
        raise ValueError(
            f"taxonomy version mismatch: {_CONF_NAME} carries version={yaml_version!r} but "
            f"TAXONOMY_VERSION={TAXONOMY_VERSION!r}. Bump both together (see GOVERNANCE.md)."
        )

    schemes = tuple(doc["schemes"])
    entities: list[EntityType] = []
    for raw in doc["entities"]:
        entities.append(
            EntityType(
                name=raw["name"],
                tier=Tier(raw["tier"]),
                identifier_class=IdentifierClass(raw["identifier_class"]),
                gdpr_special=bool(raw.get("gdpr_special", False)),
                crosswalk={k: list(v) for k, v in (raw.get("crosswalk") or {}).items()},
            )
        )
    return schemes, entities


SCHEMES, TAXONOMY = _load_taxonomy()

ENTITY_NAMES: list[str] = [e.name for e in TAXONOMY]
BY_NAME: dict[str, EntityType] = {e.name: e for e in TAXONOMY}


def bioes_labels() -> list[str]:
    """Full BIOES label space: O + {B,I,E,S}-<TYPE> for every entity type."""
    labels = ["O"]
    for name in ENTITY_NAMES:
        labels += [f"B-{name}", f"I-{name}", f"E-{name}", f"S-{name}"]
    return labels


def special_category_types() -> list[str]:
    """GDPR Art. 9 special-category entity types (higher-stakes leakage)."""
    return [e.name for e in TAXONOMY if e.gdpr_special]
