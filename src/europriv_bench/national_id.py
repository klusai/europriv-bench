"""National-ID validation/decode — a country-keyed validator registry.

Why this lives in the benchmark harness: a national ID is the sharpest demonstration of the
re-identification thesis — an *un-redacted* national ID is often a **deterministic** disclosure
of quasi-identifiers (date of birth, sex, place of birth). The leakage metric
(``metrics.national_id_leakage``) decodes exactly these. KlusAI's data generators
(klusai-datasets) import these helpers so generated IDs are checksum-valid and decode
consistently — one source of truth.

Validators split into two families:

  * **Decode-bearing** — a valid ID deterministically discloses quasi-identifiers, so a *miss*
    is a re-identification event. RO/CNP, PL/PESEL and IT/codice-fiscale are decode-bearing.
  * **Coverage-only** — the ID is detectable and checksum-validatable, but carries **no**
    decodable quasi-identifier (no embedded DOB/sex/place). We score *detection coverage* only
    and **never** emit a re-identification number. ES/DNI-NIF is coverage-only.

Each country exposes a :class:`Validator` in :data:`REGISTRY` keyed by ISO-3166 alpha-2 code.
Every validator returns an :class:`IDInfo`; decode-bearing ones populate quasi-identifiers,
coverage-only ones return ``quasi_identifiers=frozenset()`` by construction.

Sources:
  RO  vimishor/cnp-spec; Romanian Law 190/2018 art. 4.
  PL  PESEL spec (GUS); weighted mod-10 checksum, month-offset century encoding.
  IT  Agenzia delle Entrate codice-fiscale spec (DM 23/12/1976); omocodia, Belfiore codes.
  ES  DNI/NIF control-letter table (Orden del Ministerio del Interior).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class IDInfo:
    """Decode result for a national ID, regardless of country.

    ``country`` is the ISO alpha-2 code; ``decode_bearing`` records whether this ID *family*
    can disclose quasi-identifiers at all (a coverage-only ID is always ``False``). ``extra``
    carries country-specific decoded fields (e.g. ``birth_date``, ``county_code``,
    ``place_code``) for callers that want them; the leakage metric only needs
    :meth:`disclosed_quasi_identifiers`.
    """

    valid: bool
    country: str | None = None
    decode_bearing: bool = False
    quasi_identifiers: frozenset[str] = field(default_factory=frozenset)
    extra: dict[str, object] = field(default_factory=dict)

    def disclosed_quasi_identifiers(self) -> set[str]:
        """Quasi-identifiers a leaked (un-redacted) ID discloses (empty for coverage-only)."""
        if not self.valid:
            return set()
        return set(self.quasi_identifiers)


@dataclass(frozen=True)
class Validator:
    """A country's national-ID validator. ``parse`` decodes; the rest is metadata."""

    country: str          # ISO-3166 alpha-2
    name: str             # human label, e.g. "CNP", "PESEL", "codice fiscale", "DNI/NIF"
    decode_bearing: bool  # True → a miss leaks quasi-identifiers; False → coverage-only
    parse: Callable[[str], IDInfo]


# --- Shared helpers ----------------------------------------------------------------------


def _plausible_date(year: int, month: int, day: int) -> bool:
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return False
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return day <= days[month - 1]


# --- RO: CNP (Cod Numeric Personal) — decode-bearing -------------------------------------
#
# 13-digit identifier ``S AA LL ZZ JJ NNN C``:
#   S    sex + century (1/3/5/7 male, 2/4/6/8 female; 7/8/9 = resident foreigner/unspecified)
#   AA   year (last two digits), LL month, ZZ day
#   JJ   county code (01–46 counties + Bucharest sectors; 51/52 Călărași/Giurgiu)
#   NNN  sequence, C mod-11 checksum
# A missed CNP deterministically discloses DATE_OF_BIRTH (century unambiguous) + SEX + COUNTY.

_CNP_WEIGHTS = (2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9)
# 7/8/9 do not encode a century (resident foreigners / unspecified) → birth year ambiguous.
_CNP_CENTURY = {1: 1900, 2: 1900, 3: 1800, 4: 1800, 5: 2000, 6: 2000}


@dataclass(frozen=True)
class CNPInfo:
    """Backward-compatible RO/CNP decode result (preserved public shape).

    Retained verbatim so existing RO callers (and ``cnp_leakage``) keep working unchanged.
    New code can use the country-keyed registry returning :class:`IDInfo` instead.
    """

    valid: bool
    sex: str | None = None            # "M" | "F"
    birth_date: str | None = None     # ISO "YYYY-MM-DD"; None if century ambiguous/invalid
    county_code: str | None = None    # "JJ" (01–52; 41–46 = Bucharest sectors)
    century_known: bool = False

    def disclosed_quasi_identifiers(self) -> set[str]:
        """Quasi-identifiers a leaked (un-redacted) CNP discloses."""
        if not self.valid:
            return set()
        qi = {"SEX", "COUNTY"}            # always decodable
        if self.century_known:
            qi.add("DATE_OF_BIRTH")       # DOB only when the century is unambiguous
        return qi


def check_digit(first12: str) -> int:
    """Compute the CNP control digit for the first 12 digits."""
    total = sum(int(d) * w for d, w in zip(first12, _CNP_WEIGHTS))
    rem = total % 11
    return 1 if rem == 10 else rem


def validate_cnp(value: str) -> bool:
    """True iff ``value`` is a structurally valid CNP (13 digits, plausible date, valid checksum)."""
    return parse_cnp(value).valid


def parse_cnp(value: str) -> CNPInfo:
    """Decode a CNP. Returns ``CNPInfo(valid=False)`` for anything malformed."""
    if not isinstance(value, str):
        return CNPInfo(valid=False)
    s = value.strip()
    if len(s) != 13 or not s.isdigit():
        return CNPInfo(valid=False)
    if check_digit(s[:12]) != int(s[12]):
        return CNPInfo(valid=False)

    sd = int(s[0])
    if sd == 0:
        return CNPInfo(valid=False)
    sex = "M" if sd % 2 == 1 else "F"
    yy, mm, dd = int(s[1:3]), int(s[3:5]), int(s[5:7])
    county = s[7:9]
    century = _CNP_CENTURY.get(sd)

    birth_date = None
    if century is not None:
        year = century + yy
        if not _plausible_date(year, mm, dd):
            return CNPInfo(valid=False)
        birth_date = f"{year:04d}-{mm:02d}-{dd:02d}"
    else:
        # Century ambiguous (S=7/8/9): still require month/day to be in range.
        if not (1 <= mm <= 12 and 1 <= dd <= 31):
            return CNPInfo(valid=False)

    return CNPInfo(
        valid=True, sex=sex, birth_date=birth_date,
        county_code=county, century_known=century is not None,
    )


def _parse_ro(value: str) -> IDInfo:
    """Registry adapter for RO/CNP → :class:`IDInfo` (delegates to :func:`parse_cnp`)."""
    cnp = parse_cnp(value)
    if not cnp.valid:
        return IDInfo(valid=False, country="RO", decode_bearing=True)
    return IDInfo(
        valid=True, country="RO", decode_bearing=True,
        quasi_identifiers=frozenset(cnp.disclosed_quasi_identifiers()),
        extra={
            "sex": cnp.sex, "birth_date": cnp.birth_date,
            "county_code": cnp.county_code, "century_known": cnp.century_known,
        },
    )


# --- PL: PESEL — decode-bearing ----------------------------------------------------------
#
# 11-digit identifier ``YY MM DD NNN S C``:
#   YYMMDD  birth date; the MONTH field carries the century:
#           month +0  → 1900s, +20 → 2000s, +40 → 2100s, +60 → 2200s, +80 → 1800s
#   NNN     serial, S sex digit (the 10th, index 9): odd → male, even → female
#   C       weighted mod-10 checksum
# A missed PESEL deterministically discloses DATE_OF_BIRTH + SEX (no place-of-birth encoding).

_PESEL_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
_PESEL_CENTURY = {0: 1900, 20: 2000, 40: 2100, 60: 2200, 80: 1800}


def _pesel_check_digit(first10: str) -> int:
    total = sum(int(d) * w for d, w in zip(first10, _PESEL_WEIGHTS))
    return (10 - (total % 10)) % 10


def _parse_pl(value: str) -> IDInfo:
    """Decode a Polish PESEL. Returns ``IDInfo(valid=False)`` for anything malformed."""
    if not isinstance(value, str):
        return IDInfo(valid=False, country="PL", decode_bearing=True)
    s = value.strip()
    if len(s) != 11 or not s.isdigit():
        return IDInfo(valid=False, country="PL", decode_bearing=True)
    if _pesel_check_digit(s[:10]) != int(s[10]):
        return IDInfo(valid=False, country="PL", decode_bearing=True)

    yy = int(s[0:2])
    mm_raw, dd = int(s[2:4]), int(s[4:6])
    century = _PESEL_CENTURY.get(mm_raw - (mm_raw % 20))
    if century is None:
        return IDInfo(valid=False, country="PL", decode_bearing=True)
    month = mm_raw % 20
    year = century + yy
    if not _plausible_date(year, month, dd):
        return IDInfo(valid=False, country="PL", decode_bearing=True)

    sex = "M" if int(s[9]) % 2 == 1 else "F"
    return IDInfo(
        valid=True, country="PL", decode_bearing=True,
        quasi_identifiers=frozenset({"DATE_OF_BIRTH", "SEX"}),
        extra={"sex": sex, "birth_date": f"{year:04d}-{month:02d}-{dd:02d}"},
    )


# --- IT: codice fiscale — decode-bearing -------------------------------------------------
#
# 16-char alphanumeric: ``SSS NNN YY M DD ZZZZ C`` (3 surname + 3 name consonant-codes, then):
#   YY      birth year (last two digits)
#   M       birth-month letter (A..T per a fixed table)
#   DD      day; +40 for females (so day 41–71 → female, day−40)
#   ZZZZ    Belfiore code: place/comune of birth (national for Italy, ``Z…`` for abroad)
#   C       mod-26 control letter over the 15 preceding chars (even/odd position tables)
# A missed codice fiscale deterministically discloses DATE_OF_BIRTH + SEX + PLACE_OF_BIRTH.
# (Omocodia substitutes letters for digits in the numeric fields on collision; we decode it.)

_CF_MONTHS = {  # month-letter → 1..12
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "H": 6,
    "L": 7, "M": 8, "P": 9, "R": 10, "S": 11, "T": 12,
}
# Omocodia: when a numeric position collides, digits are replaced by letters in this order:
#   0→L 1→M 2→N 3→P 4→Q 5→R 6→S 7→T 8→U 9→V. Reverse map to recover the digit.
_CF_OMOCODIA = {"L": "0", "M": "1", "N": "2", "P": "3", "Q": "4",
                "R": "5", "S": "6", "T": "7", "U": "8", "V": "9"}
_CF_ODD = {  # control-letter table, odd positions (1-indexed)
    "0": 1, "1": 0, "2": 5, "3": 7, "4": 9, "5": 13, "6": 15, "7": 17, "8": 19, "9": 21,
    "A": 1, "B": 0, "C": 5, "D": 7, "E": 9, "F": 13, "G": 15, "H": 17, "I": 19, "J": 21,
    "K": 2, "L": 4, "M": 18, "N": 20, "O": 11, "P": 3, "Q": 6, "R": 8, "S": 12, "T": 14,
    "U": 16, "V": 10, "W": 22, "X": 25, "Y": 24, "Z": 23,
}
_CF_EVEN = {  # control-letter table, even positions (1-indexed)
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6, "H": 7, "I": 8, "J": 9,
    "K": 10, "L": 11, "M": 12, "N": 13, "O": 14, "P": 15, "Q": 16, "R": 17, "S": 18,
    "T": 19, "U": 20, "V": 21, "W": 22, "X": 23, "Y": 24, "Z": 25,
}


def _cf_digit(ch: str) -> int | None:
    """Recover a digit from a codice-fiscale numeric position, applying omocodia substitution."""
    if ch.isdigit():
        return int(ch)
    sub = _CF_OMOCODIA.get(ch)
    return int(sub) if sub is not None else None


def _cf_control_letter(first15: str) -> str:
    total = 0
    for i, ch in enumerate(first15):
        # Positions are 1-indexed in the spec: odd table for chars 1,3,5,…; even for 2,4,6,…
        total += _CF_ODD[ch] if i % 2 == 0 else _CF_EVEN[ch]
    return chr(ord("A") + total % 26)


def _parse_it(value: str) -> IDInfo:
    """Decode an Italian codice fiscale. Returns ``IDInfo(valid=False)`` for anything malformed."""
    if not isinstance(value, str):
        return IDInfo(valid=False, country="IT", decode_bearing=True)
    s = value.strip().upper()
    if len(s) != 16 or not s.isalnum() or not s.isascii():
        return IDInfo(valid=False, country="IT", decode_bearing=True)
    if not s[:15].isalnum() or _cf_control_letter(s[:15]) != s[15]:
        return IDInfo(valid=False, country="IT", decode_bearing=True)

    # Surname (0..2) + name (3..5) consonant codes must be letters.
    if not s[0:6].isalpha():
        return IDInfo(valid=False, country="IT", decode_bearing=True)

    yy = _two_digit_field(s[6:8])
    if yy is None:
        return IDInfo(valid=False, country="IT", decode_bearing=True)
    month = _CF_MONTHS.get(s[8])
    if month is None:
        return IDInfo(valid=False, country="IT", decode_bearing=True)
    day = _two_digit_field(s[9:11])
    if day is None:
        return IDInfo(valid=False, country="IT", decode_bearing=True)

    sex = "F" if day > 40 else "M"
    if sex == "F":
        day -= 40
    # Year century is ambiguous (only 2 digits, no century marker) → DOB month/day/sex still
    # disclosed; we surface a 2-digit year. Require a plausible day for the month (leap-agnostic:
    # allow Feb 29 since century is unknown).
    if not (1 <= day <= 31) or day > [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]:
        return IDInfo(valid=False, country="IT", decode_bearing=True)

    place_code = s[11:15]  # Belfiore code: comune (national) or Z-prefixed foreign country
    if not (place_code[0].isalpha() and _two_digit_field(place_code[1:4]) is not None):
        return IDInfo(valid=False, country="IT", decode_bearing=True)

    return IDInfo(
        valid=True, country="IT", decode_bearing=True,
        quasi_identifiers=frozenset({"DATE_OF_BIRTH", "SEX", "PLACE_OF_BIRTH"}),
        extra={"sex": sex, "birth_year_2digit": f"{yy:02d}",
               "birth_month": month, "birth_day": day, "belfiore_code": place_code},
    )


def _two_digit_field(field_chars: str) -> int | None:
    """Decode a codice-fiscale numeric field (1+ chars), applying omocodia; None if invalid."""
    digits = ""
    for ch in field_chars:
        d = _cf_digit(ch)
        if d is None:
            return None
        digits += str(d)
    return int(digits)


# --- ES: DNI / NIF — coverage-only -------------------------------------------------------
#
# 8 digits + 1 control letter (NIF prepends a letter for foreigners/entities, but the
# canonical DNI is 8 digits + letter). The control letter is digits mod 23 indexed into a
# fixed table. The Spanish DNI carries **no** embedded DOB/sex/place — it is a pure serial
# number. So this validator is COVERAGE-ONLY: we validate + detect, but NEVER decode or emit
# any quasi-identifier (``disclosed_quasi_identifiers()`` is always empty by construction).

_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


def _parse_es(value: str) -> IDInfo:
    """Validate a Spanish DNI/NIF. Coverage-only: never discloses quasi-identifiers."""
    if not isinstance(value, str):
        return IDInfo(valid=False, country="ES", decode_bearing=False)
    s = value.strip().upper().replace("-", "")
    # DNI: 8 digits + letter. NIF foreigner/legal-entity prefix (X/Y/Z/K/L/M…) is normalized
    # to its numeric equivalent for the checksum (X→0, Y→1, Z→2); other prefixes unsupported.
    prefix_map = {"X": "0", "Y": "1", "Z": "2"}
    body = s
    if s[:1] in prefix_map:
        body = prefix_map[s[0]] + s[1:]
    if len(body) != 9 or not body[:8].isdigit() or not body[8].isalpha():
        return IDInfo(valid=False, country="ES", decode_bearing=False)
    if _DNI_LETTERS[int(body[:8]) % 23] != body[8]:
        return IDInfo(valid=False, country="ES", decode_bearing=False)
    # Valid + detectable, but carries no quasi-identifier → quasi_identifiers stays empty.
    return IDInfo(valid=True, country="ES", decode_bearing=False)


# --- Country-keyed registry --------------------------------------------------------------

REGISTRY: dict[str, Validator] = {
    "RO": Validator("RO", "CNP", decode_bearing=True, parse=_parse_ro),
    "PL": Validator("PL", "PESEL", decode_bearing=True, parse=_parse_pl),
    "IT": Validator("IT", "codice fiscale", decode_bearing=True, parse=_parse_it),
    "ES": Validator("ES", "DNI/NIF", decode_bearing=False, parse=_parse_es),
}


def supported_countries() -> list[str]:
    """ISO alpha-2 codes with a registered national-ID validator."""
    return sorted(REGISTRY)


def get_validator(country: str) -> Validator | None:
    """Return the validator for an ISO alpha-2 country code, or None if unsupported."""
    return REGISTRY.get(country.upper()) if isinstance(country, str) else None


def parse_national_id(value: str, country: str) -> IDInfo:
    """Decode ``value`` using the validator for ``country`` (ISO alpha-2).

    Returns ``IDInfo(valid=False)`` for an unsupported country or a malformed ID. Decode-bearing
    countries populate quasi-identifiers; coverage-only countries never do.
    """
    v = get_validator(country)
    if v is None:
        return IDInfo(valid=False, country=country.upper() if isinstance(country, str) else None)
    return v.parse(value)
