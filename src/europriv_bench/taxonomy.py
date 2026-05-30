"""The harmonized KlusAI Privacy (KP) entity taxonomy + BIOES label space + crosswalk.

This is *standardization*, not invention: every target scheme below is mature. The
contribution is one GDPR-aligned crosswalk that unifies them across general + legal +
clinical for European jurisdictions, plus explicit GDPR-Art.9 (special-category) and
direct-vs-quasi-identifier marking (à la TAB / MultiGraSCCo).

Entity tags use BIOES so the label space is directly compatible with `openai/privacy-filter`
(enabling head-to-head scoring).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# Bump whenever the entity set or BIOES label space changes. Stamped into eval specs and the
# leaderboard so dataset gold labels, model label maps, and scores are provably the same version.
TAXONOMY_VERSION = "0.1.0"


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


# --- Crosswalk source schemes we map onto -------------------------------------------------
SCHEMES = ("openai", "ai4privacy", "hipaa", "mapa", "openmed", "azure")


# --- The harmonized taxonomy (seed; extended in docs/taxonomy.md) -------------------------
# Kept deliberately small and auditable here; the full 50+ crosswalk lives in the doc and is
# loaded from a versioned YAML in a later phase.
TAXONOMY: list[EntityType] = [
    EntityType(
        "PERSON", Tier.CORE, IdentifierClass.DIRECT,
        crosswalk={
            "openai": ["private_person"],
            "ai4privacy": ["GIVENNAME", "SURNAME", "FIRSTNAME", "LASTNAME", "MIDDLENAME"],
            "hipaa": ["names"],
            "mapa": ["PERSON"],
            "openmed": ["FIRSTNAME", "LASTNAME", "MIDDLENAME", "PREFIX"],
        },
    ),
    EntityType(
        "ADDRESS", Tier.CORE, IdentifierClass.QUASI,
        crosswalk={
            "openai": ["private_address"],
            "ai4privacy": ["STREET", "CITY", "ZIPCODE", "BUILDINGNUM"],
            "hipaa": ["geographic_subdivisions"],
            "mapa": ["ADDRESS"],
            "openmed": [
                "STREET", "CITY", "ZIPCODE", "BUILDINGNUMBER", "COUNTY", "STATE",
                "SECONDARYADDRESS", "GPSCOORDINATES", "ORDINALDIRECTION",
            ],
        },
    ),
    EntityType(
        "EMAIL", Tier.CORE, IdentifierClass.DIRECT,
        crosswalk={"openai": ["private_email"], "ai4privacy": ["EMAIL"], "openmed": ["EMAIL"]},
    ),
    EntityType(
        "PHONE", Tier.CORE, IdentifierClass.DIRECT,
        crosswalk={"openai": ["private_phone"], "ai4privacy": ["TELEPHONENUM"], "openmed": ["PHONE"]},
    ),
    EntityType(
        "URL", Tier.CORE, IdentifierClass.QUASI,
        crosswalk={"openai": ["private_url"], "openmed": ["URL"]},
    ),
    EntityType(
        "DATE", Tier.CORE, IdentifierClass.QUASI,
        crosswalk={
            "openai": ["private_date"], "ai4privacy": ["DATE", "TIME"], "hipaa": ["dates"],
            "openmed": ["DATE", "DATEOFBIRTH", "TIME"],
        },
    ),
    EntityType(
        "ACCOUNT_ID", Tier.CORE, IdentifierClass.DIRECT,
        crosswalk={
            "openai": ["account_number"],
            "ai4privacy": [
                "ACCOUNTNUM", "IDCARDNUM", "TAXNUM", "SOCIALNUM", "PASSPORTNUM",
                "CREDITCARDNUMBER", "DRIVERLICENSENUM",
            ],
            "hipaa": ["account_numbers", "ssn"],  # medical_record_numbers → MRN (clinical-specific)
            "openmed": [
                "SSN", "IBAN", "BANKACCOUNT", "BIC", "CREDITCARD", "CREDITCARDISSUER", "CVV",
                "PIN", "MASKEDNUMBER", "ACCOUNTNAME", "BITCOINADDRESS", "ETHEREUMADDRESS",
                "LITECOINADDRESS", "VIN", "VRM", "IMEI", "MACADDRESS", "IPADDRESS",
                "USERNAME", "USERAGENT",
            ],
        },
    ),
    EntityType(
        "SECRET", Tier.CORE, IdentifierClass.DIRECT,
        crosswalk={"openai": ["secret"], "ai4privacy": ["PASSWORD"], "openmed": ["PASSWORD"]},
    ),
    # --- Clinical (PHI) ---
    EntityType(
        "MRN", Tier.CLINICAL, IdentifierClass.DIRECT,
        crosswalk={"hipaa": ["medical_record_numbers"]},
    ),
    EntityType(
        "HEALTH_CONDITION", Tier.CLINICAL, IdentifierClass.QUASI, gdpr_special=True,
        crosswalk={"openmed": ["DIAGNOSES", "MEDICATION"]},
    ),
    # PROVIDER/FACILITY are KP-native refinements: HIPAA "names" → PERSON and MAPA
    # "ORGANIZATION" → ORG_PARTY (the general owners); these finer types can't be recovered
    # from the flat source label, so they don't claim it (keeps native→KP a function).
    EntityType("PROVIDER", Tier.CLINICAL, IdentifierClass.QUASI, crosswalk={}),
    EntityType("FACILITY", Tier.CLINICAL, IdentifierClass.QUASI, crosswalk={}),
    # --- Legal quasi-identifiers ---
    EntityType("CASE_NUMBER", Tier.LEGAL, IdentifierClass.DIRECT, crosswalk={"mapa": ["AMOUNT"]}),
    EntityType("COURT", Tier.LEGAL, IdentifierClass.QUASI, crosswalk={}),
    EntityType("STATUTE_REF", Tier.LEGAL, IdentifierClass.QUASI, crosswalk={}),
    EntityType("ORG_PARTY", Tier.LEGAL, IdentifierClass.QUASI, crosswalk={"mapa": ["ORGANIZATION"]}),
]

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
