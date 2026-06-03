"""Pinned, versioned snapshot of Belfiore (Codice Catastale) → place-of-birth resolution.

The Belfiore code is the 4-char ``ZZZZ`` field of an Italian *codice fiscale* — it identifies the
**comune** (municipality) of birth for people born in Italy, or, for people born abroad, a
``Z``-prefixed **foreign-country** code. Because a leaked (un-redacted) codice fiscale therefore
discloses PLACE_OF_BIRTH, the leakage metric must resolve this code to the *actual* place; a raw
4-char string is not a quasi-identifier a human re-identifier reasons about.

**Why pinned / snapshotted (KLU-105).** Belfiore codes are NOT stable over time: when comuni merge,
split or are renamed, the Agenzia delle Entrate / ISTAT reassign or retire codes. Decoding against a
live table would make the benchmark non-reproducible and could silently change the disclosed
place-of-birth for an identical CF across runs. So we pin a **snapshot** with an explicit version and
``as-of`` date; the leak metric and the dataset generators both resolve against THIS table, and the
snapshot is bumped deliberately (never silently) when refreshed.

**Foreign-born scope (decided + documented, KLU-105).** A codice fiscale for a person born abroad
carries ``Z`` + a 3-digit country code (e.g. ``Z404`` = Cina/China). The CF then does **not** encode
a comune — only the *country* of birth. We resolve such codes to a country name and tag the resolved
place ``kind="foreign_country"``. For the re-identification leak this is still a PLACE_OF_BIRTH
disclosure (the QI is disclosed either way), but it is a **coarser** geographic disclosure than a
comune; callers that want the granularity can read ``BelfiorePlace.kind``. Unknown / unresolved codes
(comuni not in the snapshot, or retired codes) resolve to ``kind="unknown"`` with ``name=None`` — the
QI is still disclosed (the field is structurally a place code), we simply cannot name the place from
this snapshot.

This snapshot is intentionally small: it covers the comuni/countries the KlusAI synthetic generators
emit (so generated CFs resolve to a named place) plus a documented handful of the largest Italian
comuni and common foreign countries. It is a *resolution aid for the disclosure story*, NOT a claim
to be the complete national table.
"""

from __future__ import annotations

from dataclasses import dataclass

# Snapshot provenance — bump deliberately when the table is refreshed (never silently).
BELFIORE_SNAPSHOT_VERSION = "2024.1"
BELFIORE_SNAPSHOT_AS_OF = "2024-01-01"
BELFIORE_SNAPSHOT_SOURCE = (
    "Agenzia delle Entrate / ISTAT codici catastali (Belfiore). "
    "Pinned subset for EuroPriv-Bench reproducibility — see module docstring."
)

# --- Comuni (national place-of-birth). Code → comune name. -------------------------------
# These are the genuine codici catastali for the comuni the IT generators use, plus a few of the
# largest Italian comuni for coverage. Codes are uppercase ``L###`` form.
_COMUNI: dict[str, str] = {
    "H501": "Roma",
    "F205": "Milano",
    "F839": "Napoli",
    "L219": "Torino",
    "G273": "Palermo",
    "D969": "Genova",
    "A944": "Bologna",
    "D612": "Firenze",
    "L736": "Venezia",
    "C351": "Catania",
    "A662": "Bari",
    "L424": "Trieste",
}

# --- Foreign countries (Z-prefixed). Code → country name. --------------------------------
# A person born abroad gets ``Z`` + a 3-digit ISTAT country code instead of a comune. We resolve a
# documented subset; the *kind* is "foreign_country" so callers can distinguish the coarser
# (country-level) place-of-birth disclosure from a comune-level one.
_FOREIGN: dict[str, str] = {
    "Z100": "Albania",
    "Z112": "Germania",
    "Z114": "Regno Unito",
    "Z133": "Romania",
    "Z200": "Egitto",
    "Z210": "Marocco",
    "Z301": "Stati Uniti d'America",
    "Z330": "Brasile",
    "Z404": "Cina",
    "Z222": "India",
}


@dataclass(frozen=True)
class BelfiorePlace:
    """A resolved place-of-birth from a codice-fiscale Belfiore code.

    ``kind`` is one of ``"comune"`` (born in an Italian municipality), ``"foreign_country"`` (born
    abroad — only the country is encoded, a coarser disclosure), or ``"unknown"`` (a structurally
    valid place code not in this pinned snapshot — the QI is still disclosed, we just cannot name it).
    ``name`` is the comune/country name, or ``None`` when ``kind == "unknown"``.
    """

    code: str
    kind: str           # "comune" | "foreign_country" | "unknown"
    name: str | None


def resolve_belfiore(code: str) -> BelfiorePlace:
    """Resolve a (omocodia-reversed) 4-char Belfiore code to a place-of-birth against the snapshot.

    The caller MUST pass the omocodia-reversed code (digits restored), since omocodia can substitute
    letters into the 3 numeric positions of the Belfiore field — see ``national_id._cf_place_code``.
    """
    c = code.strip().upper()
    if c.startswith("Z"):
        return BelfiorePlace(code=c, kind="foreign_country", name=_FOREIGN.get(c))
    name = _COMUNI.get(c)
    if name is not None:
        return BelfiorePlace(code=c, kind="comune", name=name)
    return BelfiorePlace(code=c, kind="unknown", name=None)
