"""The harmonized KlusAI Privacy (KP) entity taxonomy + BIOES label space + crosswalk.

This is *standardization*, not invention: every target scheme below is mature. The
contribution is one GDPR-aligned crosswalk that unifies them across general + legal +
clinical for European jurisdictions, plus explicit GDPR-Art.9 (special-category) and
direct-vs-quasi-identifier marking (à la TAB / MultiGraSCCo).

Entity tags use BIOES so the label space is directly compatible with `openai/privacy-filter`
(enabling head-to-head scoring).

The crosswalk is **not** hand-coded here: it is the single, versioned source of truth in
the package-bundled ``europriv_bench/conf/taxonomy.yaml``, loaded once at import.
``TAXONOMY_VERSION`` below is the in-code anchor; the YAML must echo the same ``version``
or import fails loud (see GOVERNANCE.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from importlib import resources
from importlib.resources.abc import Traversable

import yaml

# Bump whenever the entity set or BIOES label space changes. Stamped into eval specs and the
# leaderboard so dataset gold labels, model label maps, and scores are provably the same version.
# MUST equal `version` in europriv_bench/conf/taxonomy.yaml — the loader fails loud on mismatch.
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


# --- Single source of truth: europriv_bench/conf/taxonomy.yaml ----------------------------
# The YAML lives *inside* the package (src/europriv_bench/conf/), so it travels with the wheel
# and is resolvable via importlib.resources in both editable and installed/zipped contexts.
# This is the single source of truth consumed by klusai-datasets/-models through the public API
# (bioes_labels(), to_kp(), …); do NOT fork it.
_CONF_PKG = "europriv_bench.conf"
_CONF_NAME = "taxonomy.yaml"


def _locate_conf() -> Traversable:
    """Resolve the package-bundled taxonomy YAML.

    Returns an ``importlib.resources`` Traversable (a ``Path`` for unpacked installs, a
    zip-backed resource otherwise). It exposes ``.name``/``open()`` like a path, so callers
    that only read the file work unchanged across editable and wheel installs.
    """
    resource = resources.files(_CONF_PKG) / _CONF_NAME
    if not resource.is_file():
        raise FileNotFoundError(
            f"taxonomy config {_CONF_NAME!r} not found in package {_CONF_PKG!r} "
            f"(is it bundled? see [tool.setuptools.package-data] in pyproject.toml)"
        )
    return resource


def _load_taxonomy() -> tuple[tuple[str, ...], list[EntityType]]:
    with _locate_conf().open(encoding="utf-8") as f:
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
