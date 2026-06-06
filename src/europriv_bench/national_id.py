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
  DE  Steuer-IdNr (§ 139b Abgabenordnung); ISO 7064 MOD 11,10 check digit.
  FR  NIR / numéro de sécurité sociale (INSEE); 13-digit body, clé = 97 − (body mod 97).
  NL  BSN / burgerservicenummer (Rijksoverheid); 11-proef (elfproef) weighted-sum test.
  SE  personnummer (Skatteverket SKV 704); Luhn / ISO 7812 mod-10; sex digit, +60 day = samordningsnummer.
  CZ  rodné číslo (Zákon č. 133/2000 Sb. § 13); whole-number mod-11; female month +50, +20 overflow.
  DK  CPR-nummer (CPR-kontoret / Det Centrale Personregister); DDMMYY-SSSS, format + 7th-digit/YY
      century table — the mod-11 check was abolished in 2007 (NOT a hard checksum); sex = last-digit parity.
  FI  henkilötunnus (DVV / VRK); DDMMYY + century marker + ZZZ + mod-31 control char; sex = ZZZ parity.
  EE  isikukood (Estonian PPA / standard EVS); GYYMMDDSSSC; G = century+sex; ISO-7064-style two-pass
      mod-11 (weights 1..9,1 then 3..9,1,2,3; remainder 10 in BOTH passes → check digit 0).
  LT  asmens kodas (Gyventojų registras; standard RST 1185-91); GYYMMDDNNNC; SAME two-pass mod-11 and
      G century+sex encoding as EE (python-stdnum's lt.asmens reuses ee.ik.calc_check_digit verbatim).
  SI  EMŠO (Enotna matična številka občana; ex-YU JMBG, Zakon o matičnem registru / ZMatR-A); 13-digit
      DDMMYYY-RR-BBB-K — a RICHER surface than the Baltic family: it also discloses REGION OF BIRTH (RR)
      like the IT codice-fiscale's place. YYY = last 3 year digits (YYY>800 → 19YY/1900s, else 2000s —
      the ex-YU convention); RR = political region of birth (50–59 = Slovenia, only 50 used pre-2024);
      BBB = serial 000–499 male / 500–999 female; K = weighted mod-11 over the 12-digit body
      (7,6,5,4,3,2 repeated twice), control = 11−(Σ mod 11) with 10/11 → 0. Decodes SEX + DATE_OF_BIRTH
      + REGION_OF_BIRTH. COLLISION FOOTGUN: every ex-YU country shares the EMŠO/JMBG structure, so the
      validator is country-keyed and the RR region encodes the country — an SI EMŠO is validated as SI.
  SK  rodné číslo — the SAME identifier and SAME algorithm as CZ (Zákon č. 301/2000 Z. z. in Slovakia;
      historically the shared Czechoslovak Zákon č. 133/2000 Sb. scheme). SK REUSES the CZ decoder
      verbatim (``_parse_cz`` with country="SK") — no duplicate logic. Decodes SEX + DATE_OF_BIRTH.
      COLLISION FOOTGUN: a CZ and an SK rodné číslo are structurally indistinguishable; the registry is
      country-keyed and never auto-detects, so an SK number is decoded as SK and a CZ number as CZ — the
      dispatch is by the row/span ``country`` tag, never by the digits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from europriv_bench.belfiore import resolve_belfiore


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
#   ZZZZ    Belfiore code: place/comune of birth (national for Italy, ``Z…`` for abroad), resolved
#           to a named comune/country against the pinned ``belfiore`` snapshot (KLU-105)
#   C       mod-26 control letter over the 15 preceding chars (even/odd position tables)
# A missed codice fiscale deterministically discloses DATE_OF_BIRTH + SEX + PLACE_OF_BIRTH.
# Omocodia substitutes letters for digits in ALL the variable numeric fields on collision — year,
# day AND the three Belfiore numeric positions — so we reverse it across every numeric field
# (incl. the place code) before decoding, making the disclosed place-of-birth omocodia-invariant.

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


def _cf_place_code(field_chars: str) -> str | None:
    """Recover the canonical Belfiore code from the CF place field, reversing omocodia.

    The Belfiore field is one letter (``L`` for comuni, ``Z`` for foreign-born) followed by three
    numeric positions. Those three positions are *variable numeric positions*, so omocodia can
    substitute letters for their digits exactly as it does for the year/day. We therefore reverse
    omocodia on the three trailing positions so a base CF and its omocode resolve to the **same**
    comune/country (the place-of-birth quasi-identifier must be omocodia-invariant — KLU-105).
    Returns the canonical ``X###`` code, or ``None`` if the field is structurally invalid.
    """
    if len(field_chars) != 4 or not field_chars[0].isalpha():
        return None
    digits = _two_digit_field(field_chars[1:4])
    if digits is None:
        return None
    return f"{field_chars[0]}{digits:03d}"


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

    # Belfiore code: comune (national) or Z-prefixed foreign country. Reverse omocodia on its three
    # numeric positions so a base CF and its omocode disclose the SAME place-of-birth, then resolve
    # against the pinned Belfiore snapshot (KLU-105). The canonical (omocodia-reversed) code is the
    # one carried in ``extra`` and used for resolution, so place-of-birth is omocodia-invariant.
    belfiore_code = _cf_place_code(s[11:15])
    if belfiore_code is None:
        return IDInfo(valid=False, country="IT", decode_bearing=True)
    place = resolve_belfiore(belfiore_code)

    return IDInfo(
        valid=True, country="IT", decode_bearing=True,
        quasi_identifiers=frozenset({"DATE_OF_BIRTH", "SEX", "PLACE_OF_BIRTH"}),
        extra={"sex": sex, "birth_year_2digit": f"{yy:02d}",
               "birth_month": month, "birth_day": day,
               # Canonical (omocodia-reversed) Belfiore code + resolved place-of-birth. Foreign-born
               # CFs (Z-prefixed) resolve to a country (coarser disclosure); see belfiore module.
               "belfiore_code": belfiore_code,
               "place_of_birth": place.name,
               "place_kind": place.kind},
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


# --- DE: Steuer-IdNr (steuerliche Identifikationsnummer) — coverage-only -----------------
#
# 11-digit lifelong tax id (§ 139b Abgabenordnung). The 11th digit is an ISO 7064 MOD 11,10
# check digit over the leading 10 digits; the first digit is never zero. The German tax id
# carries **no** embedded DOB/sex/place — it is a pure serial. So this validator is
# COVERAGE-ONLY: we validate + detect but NEVER decode or emit any quasi-identifier.
#
# ISO 7064 MOD 11,10 check-digit algorithm (also used for the German USt-IdNr):
#   p = 10
#   for each digit d (left→right over the 10-digit body):
#       s = (d + p) mod 10;  if s == 0: s = 10;  p = (2*s) mod 11
#   check = (11 − p) mod 10
# Spec: ISO/IEC 7064:2003 MOD 11,10; § 139b AO. Cross-checked against the KLU-102 generator.


def _iso7064_mod11_10(body: str) -> int:
    """ISO 7064 MOD 11,10 check digit for a numeric ``body`` (German Steuer-IdNr scheme)."""
    p = 10
    for ch in body:
        s = (int(ch) + p) % 10
        s = s if s != 0 else 10
        p = (2 * s) % 11
    return (11 - p) % 10


def _parse_de(value: str) -> IDInfo:
    """Validate a German Steuer-IdNr. Coverage-only: never discloses quasi-identifiers."""
    if not isinstance(value, str):
        return IDInfo(valid=False, country="DE", decode_bearing=False)
    s = value.strip()
    if len(s) != 11 or not s.isdigit() or s[0] == "0":
        return IDInfo(valid=False, country="DE", decode_bearing=False)
    if _iso7064_mod11_10(s[:10]) != int(s[10]):
        return IDInfo(valid=False, country="DE", decode_bearing=False)
    # Valid + detectable, but carries no quasi-identifier → quasi_identifiers stays empty.
    return IDInfo(valid=True, country="DE", decode_bearing=False)


# --- FR: NIR / numéro de sécurité sociale (INSEE) — decode-bearing -----------------------
#
# 15-char identifier ``S YY MM DD/PP CC OOO KK`` (13-digit body + 2-digit control key):
#   S      sex: 1 = male, 2 = female (3/4/7/8 = registration-in-progress, no decodable sex)
#   YY     birth year (last two digits; century ambiguous — no century marker)
#   MM     birth month 01..12 (also 20–42 / 50–99 / 13 used for unknown-month registrations)
#   CC     département of birth: numeric 01–95 / 99 (born abroad) / 970+ (overseas), plus
#          Corsica as letters ``2A`` (Corse-du-Sud) and ``2B`` (Haute-Corse)
#   OOO    commune + order number
#   KK     control key = 97 − (13-digit body mod 97), 2 digits
# For the key, Corsica letters are substituted BEFORE the mod-97: 2A → 19, 2B → 18 (the only
# non-numeric positions). A missed NIR deterministically discloses SEX (when S∈{1,2}) and
# DATE_OF_BIRTH (when MM is a real month 01–12 — year+month, century-ambiguous like the IT CF).
# Spec: INSEE NIR definition; fr.wikipedia "Numéro de sécurité sociale en France".
# Cross-checked against the KLU-102 generator (which emits numeric départements only).

# Corsica département letters → numeric value used for the mod-97 control-key computation.
_NIR_CORSICA = {"A": "19", "B": "18"}


def _nir_key(body13: str) -> int:
    """Control key for a NIR: 97 − (13-digit numeric body mod 97). Body must be all digits."""
    return 97 - (int(body13) % 97)


def _nir_numeric_body(body13: str) -> str | None:
    """Map the 13-char NIR body to its numeric form for the key (Corsica 2A→19, 2B→18).

    Only the département field (positions 6–7, 0-based 5–6) may legitimately carry letters
    (``2A``/``2B``); every other position must already be a digit. Returns ``None`` if any
    other position is non-numeric.
    """
    chars = list(body13)
    # Département occupies 0-based indices 5–6; Corsica is "2A"/"2B". Replace the whole two-char
    # field with its numeric equivalent ("2A"→"19", "2B"→"18") before the mod-97 computation.
    if chars[5] == "2" and chars[6] in _NIR_CORSICA:
        repl = _NIR_CORSICA[chars[6]]
        chars[5], chars[6] = repl[0], repl[1]
    numeric = "".join(chars)
    return numeric if numeric.isdigit() else None


def _parse_fr(value: str) -> IDInfo:
    """Decode a French NIR. Returns ``IDInfo(valid=False)`` for anything malformed."""
    if not isinstance(value, str):
        return IDInfo(valid=False, country="FR", decode_bearing=True)
    s = value.strip().upper().replace(" ", "")
    if len(s) != 15:
        return IDInfo(valid=False, country="FR", decode_bearing=True)
    body, key = s[:13], s[13:15]
    if not key.isdigit():
        return IDInfo(valid=False, country="FR", decode_bearing=True)
    numeric_body = _nir_numeric_body(body)
    if numeric_body is None:
        return IDInfo(valid=False, country="FR", decode_bearing=True)
    if _nir_key(numeric_body) != int(key):
        return IDInfo(valid=False, country="FR", decode_bearing=True)

    # Decode quasi-identifiers from the (original) body. Sex only for the standard 1/2 codes.
    sex = {"1": "M", "2": "F"}.get(body[0])
    yy = int(body[1:3])
    mm = int(body[3:5])

    qi: set[str] = set()
    if sex is not None:
        qi.add("SEX")
    # DATE_OF_BIRTH only when the month field is a real calendar month (01–12); the unknown-month
    # registration codes (13, 20–42, 50–99) do not disclose a usable birth month.
    birth_year_month = None
    if 1 <= mm <= 12:
        qi.add("DATE_OF_BIRTH")
        birth_year_month = f"{yy:02d}-{mm:02d}"

    return IDInfo(
        valid=True, country="FR", decode_bearing=True,
        quasi_identifiers=frozenset(qi),
        extra={"sex": sex, "birth_year_2digit": f"{yy:02d}",
               "birth_month": mm if 1 <= mm <= 12 else None,
               "birth_year_month": birth_year_month,
               "department": body[5:7]},
    )


# --- SE: personnummer — decode-bearing ---------------------------------------------------
#
# 10-digit identifier ``YY MM DD - NNN C`` (the printed form is ``YYMMDD-NNNC``; a person who
# has turned 100 uses ``+`` instead of ``-``). A 12-digit form ``YYYYMMDD-NNNC`` also exists.
#   YYMMDD  birth date (2-digit year; the century is carried only by the separator, see below)
#   NNN     birth-number; its LAST digit (the 9th of the 10) encodes sex: odd -> male, even -> female
#   C       Luhn (mod-10) check digit over the first 9 digits, weights 2,1,2,1,2,1,2,1,2
# Separator: ``-`` while the holder is < 100, ``+`` once they have turned 100. So with a known
# "today" the separator disambiguates the century -- but a bare 10-digit string does NOT, exactly
# like the IT codice fiscale 2-digit year. We therefore disclose SEX + birth month/day (2-digit
# year), and only surface a full DATE_OF_BIRTH century when a 12-digit (4-digit-year) form is given.
# Samordningsnummer (coordination numbers) add 60 to the DAY field (61-91); they validate by the
# same Luhn and decode the same sex, but the day is offset -- we recover the real day (day-60).
# Spec: Skatteverket "Personnummer" (SKV 704); Luhn / ISO 7812 mod-10. Cross-checked vs the pack.

_SE_LUHN_WEIGHTS = (2, 1, 2, 1, 2, 1, 2, 1, 2)


def _se_luhn_check_digit(first9: str) -> int:
    """Luhn (mod-10) check digit over the 9-digit personnummer body (weights 2,1,2,...)."""
    total = 0
    for d, w in zip(first9, _SE_LUHN_WEIGHTS):
        prod = int(d) * w
        total += prod - 9 if prod > 9 else prod  # cast a two-digit product to its digit sum
    return (10 - (total % 10)) % 10


def _parse_se(value: str) -> IDInfo:
    """Decode a Swedish personnummer. Returns ``IDInfo(valid=False)`` for anything malformed.

    Accepts the 10-digit ``YYMMDD-NNNC`` / ``YYMMDDNNNC`` form and the 12-digit
    ``YYYYMMDD-NNNC`` form. Separators ``-``/``+`` are stripped before the Luhn check; the ``+``
    (holder >= 100) is recorded so callers can shift the century back if they wish.
    """
    if not isinstance(value, str):
        return IDInfo(valid=False, country="SE", decode_bearing=True)
    s = value.strip()
    plus_separator = "+" in s
    s = s.replace("-", "").replace("+", "").replace(" ", "")
    century_digits: str | None = None
    if len(s) == 12 and s.isdigit():
        century_digits, s = s[:2], s[2:]        # split off the explicit century (YYYY -> CC + YY)
    if len(s) != 10 or not s.isdigit():
        return IDInfo(valid=False, country="SE", decode_bearing=True)
    if _se_luhn_check_digit(s[:9]) != int(s[9]):
        return IDInfo(valid=False, country="SE", decode_bearing=True)

    yy, mm, dd = int(s[0:2]), int(s[2:4]), int(s[4:6])
    # Samordningsnummer (coordination number): the day field is offset by +60 (61-91 -> day-60).
    coordination = dd > 60
    real_day = dd - 60 if coordination else dd
    if not (1 <= mm <= 12 and 1 <= real_day <= 31):
        return IDInfo(valid=False, country="SE", decode_bearing=True)

    sex = "M" if int(s[8]) % 2 == 1 else "F"     # 9th digit (last of NNN) parity -> sex
    qi = {"SEX", "DATE_OF_BIRTH"}                 # month + day always disclosed; year 2-digit
    birth_date = None
    if century_digits is not None:                # 12-digit form: full, unambiguous DOB
        year = int(century_digits) * 100 + yy
        if not _plausible_date(year, mm, real_day):
            return IDInfo(valid=False, country="SE", decode_bearing=True)
        birth_date = f"{year:04d}-{mm:02d}-{real_day:02d}"

    return IDInfo(
        valid=True, country="SE", decode_bearing=True,
        quasi_identifiers=frozenset(qi),
        extra={"sex": sex, "birth_year_2digit": f"{yy:02d}",
               "birth_month": mm, "birth_day": real_day,
               "birth_date": birth_date,            # set only for the 12-digit (4-digit-year) form
               "coordination_number": coordination, "plus_separator": plus_separator},
    )


# --- CZ: rodne cislo (birth number) — decode-bearing -------------------------------------
#
# 9- or 10-digit identifier ``YY XX DD / SSS [C]``:
#   YY    birth year (last two digits)
#   XX    month with sex/overflow offsets:
#           01-12 male; +50 -> female (51-62); post-2004 serial-overflow adds +20 -> male 21-32,
#           female 71-82 (50 already applied). We strip the offsets to recover the real month.
#   DD    day of birth
#   SSS   serial; C the check digit (10-digit form only)
# Check digit (>= 1954, 10-digit): the whole 10-digit number is divisible by 11. Historical
# exception (numbers issued 1954-1985): if ``first9 % 11 == 10`` the check digit was written as 0,
# so ``...SSS0`` with ``first9 % 11 == 10`` is also accepted. Pre-1954 numbers are 9 digits with NO
# check digit (no mod-11 condition). Century: a 10-digit number with ``YY >= 54`` is 19YY, ``YY <= 53``
# is 20YY (the same convention the reference validators use); a 9-digit number is necessarily 19YY
# (pre-1954) so the year is unambiguous. A missed rodne cislo discloses DATE_OF_BIRTH + SEX.
# Spec: Zakon c. 133/2000 Sb. (o evidenci obyvatel) par. 13; cross-checked vs kub1x/rodnecislo.


def _cz_strip_month(mm_raw: int) -> tuple[int, str] | None:
    """Recover (real_month, sex) from a rodne-cislo month field, undoing the +50/+20/+70 offsets."""
    sex = "M"
    mm = mm_raw
    if 51 <= mm <= 62 or 71 <= mm <= 82:          # female (base +50, or +50+20 overflow)
        sex, mm = "F", mm - 50
    if 21 <= mm <= 32:                            # male serial-overflow (+20), applied post-2004
        mm -= 20
    if not (1 <= mm <= 12):
        return None
    return mm, sex


def _parse_cz(value: str, country: str = "CZ") -> IDInfo:
    """Decode a Czech/Slovak rodne cislo. Returns ``IDInfo(valid=False)`` for anything malformed.

    CZ and SK share the SAME rodné-číslo algorithm (the historical Czechoslovak scheme; CZ Zákon
    č. 133/2000 Sb. / SK Zákon č. 301/2000 Z. z.). ``country`` selects which the result is tagged
    as — the registry is country-keyed and never auto-detects, so the digits never decide whether a
    number is CZ or SK; the row/span ``country`` tag does. ``country`` ∈ {"CZ","SK"}.
    """
    if not isinstance(value, str):
        return IDInfo(valid=False, country=country, decode_bearing=True)
    s = value.strip().replace("/", "").replace(" ", "")
    if not s.isdigit() or len(s) not in (9, 10):
        return IDInfo(valid=False, country=country, decode_bearing=True)

    yy = int(s[0:2])
    stripped = _cz_strip_month(int(s[2:4]))
    if stripped is None:
        return IDInfo(valid=False, country=country, decode_bearing=True)
    month, sex = stripped
    day = int(s[4:6])

    if len(s) == 10:
        # >=1954: the whole 10-digit number is divisible by 11, with the 1954-1985 "remainder 10 ->
        # check digit 0" historical exception.
        n10 = int(s)
        if n10 % 11 != 0 and not (int(s[:9]) % 11 == 10 and s[9] == "0"):
            return IDInfo(valid=False, country=country, decode_bearing=True)
        year = 1900 + yy if yy >= 54 else 2000 + yy
    else:
        year = 1900 + yy                          # 9-digit form is pre-1954 -> unambiguously 19YY

    if not _plausible_date(year, month, day):
        return IDInfo(valid=False, country=country, decode_bearing=True)

    return IDInfo(
        valid=True, country=country, decode_bearing=True,
        quasi_identifiers=frozenset({"DATE_OF_BIRTH", "SEX"}),
        extra={"sex": sex, "birth_date": f"{year:04d}-{month:02d}-{day:02d}"},
    )


def _parse_sk(value: str) -> IDInfo:
    """Decode a Slovak rodné číslo — the SAME algorithm as CZ, tagged ``country="SK"`` (reuse, no dup)."""
    return _parse_cz(value, country="SK")


# --- DK: CPR-nummer (personnummer) — decode-bearing --------------------------------------
#
# 10-digit identifier ``DDMMYY-SSSS`` (the hyphen is cosmetic):
#   DDMMYY  birth date (2-digit year; the century is recovered from the 7th digit + the YY table)
#   SSSS    sequence number; its 7th digit (first of SSSS) encodes the century together with YY,
#           and its LAST digit (the 10th) encodes sex — odd → male, even → female.
# Century table (7th digit ``c7`` + 2-digit year ``yy``; this is the CPR-kontoret / Det Centrale
# Personregister convention, matching the public reference validators):
#   c7 in 0–3                        → 1900 + yy
#   c7 == 4 : yy < 37 → 2000+yy      else 1900+yy
#   c7 in 5–8 : yy < 58 → 2000+yy    else 1800+yy
#   c7 == 9 : yy < 37 → 2000+yy      else 1900+yy
# IMPORTANT: the historical **mod-11 checksum was officially abolished in 2007** (the day's
# sequence numbers ran out, so numbers issued since are NOT mod-11-valid). We therefore validate
# **format + a plausible date under the century table only — NOT a hard checksum** (validating a
# mod-11 here would reject the majority of post-2007 CPR numbers). A missed CPR deterministically
# discloses DATE_OF_BIRTH (century unambiguous via the table) + SEX.
# Spec: CPR-kontoret "Personnummeret"; mod-11 abolition 2007 (CPR Office notice); cross-checked vs
# the public reference validators (python-stdnum dk.cpr, R cprr). Cross-checked vs the pack.


def _dk_century(c7: int, yy: int) -> int:
    """Full birth century-base for a CPR 7th digit ``c7`` and 2-digit year ``yy`` (CPR-kontoret table)."""
    if c7 <= 3:
        return 1900
    if c7 == 4:
        return 2000 if yy < 37 else 1900
    if c7 <= 8:                      # 5–8
        return 2000 if yy < 58 else 1800
    return 2000 if yy < 37 else 1900  # c7 == 9


def _parse_dk(value: str) -> IDInfo:
    """Decode a Danish CPR-nummer. Format + century-table + plausible date (no mod-11 — abolished 2007)."""
    if not isinstance(value, str):
        return IDInfo(valid=False, country="DK", decode_bearing=True)
    s = value.strip().replace("-", "").replace(" ", "")
    if len(s) != 10 or not s.isdigit():
        return IDInfo(valid=False, country="DK", decode_bearing=True)

    dd, mm, yy = int(s[0:2]), int(s[2:4]), int(s[4:6])
    year = _dk_century(int(s[6]), yy) + yy
    if not _plausible_date(year, mm, dd):
        return IDInfo(valid=False, country="DK", decode_bearing=True)

    sex = "M" if int(s[9]) % 2 == 1 else "F"  # last digit parity → sex
    return IDInfo(
        valid=True, country="DK", decode_bearing=True,
        quasi_identifiers=frozenset({"DATE_OF_BIRTH", "SEX"}),
        extra={"sex": sex, "birth_date": f"{year:04d}-{mm:02d}-{dd:02d}"},
    )


# --- FI: henkilötunnus — decode-bearing --------------------------------------------------
#
# 11-char identifier ``DDMMYY C ZZZ Q``:
#   DDMMYY  birth date (2-digit year; the century is carried by the marker C, so DOB is unambiguous)
#   C       century marker:  '+' → 1800s;  '-','Y','X','W','V','U' → 1900s;  'A','B','C','D','E','F'
#           → 2000s. (The 2023 DVV reform added Y/X/W/V/U and B–F as additional separators so each
#           date/sex has more codes — the separator is now a *distinguishing* character.)
#   ZZZ     individual number (002–899 for residents); odd → male, even → female.
#   Q       control character = (int(DDMMYYZZZ) mod 31) indexed into the 31-char map
#           "0123456789ABCDEFHJKLMNPRSTUVWXY" (G/I/O/Q/Z omitted to avoid ambiguity).
# A missed henkilötunnus deterministically discloses DATE_OF_BIRTH (century known) + SEX.
# Spec: DVV/VRK "Personal identity code"; 2023 separator reform (Decree 128/2010 § 2, in force
# 2023-01-01). Cross-checked vs the public reference validators (python-stdnum fi.hetu). Cross-checked vs the pack.

_FI_CONTROL_MAP = "0123456789ABCDEFHJKLMNPRSTUVWXY"  # 31 chars; index = int(DDMMYYZZZ) % 31
_FI_CENTURY = {
    "+": 1800,
    "-": 1900, "Y": 1900, "X": 1900, "W": 1900, "V": 1900, "U": 1900,
    "A": 2000, "B": 2000, "C": 2000, "D": 2000, "E": 2000, "F": 2000,
}


def _fi_control_char(ddmmyyzzz: str) -> str:
    """FI control character for the 9-digit ``DDMMYYZZZ`` string (mod-31 indexed into the map)."""
    return _FI_CONTROL_MAP[int(ddmmyyzzz) % 31]


def _parse_fi(value: str) -> IDInfo:
    """Decode a Finnish henkilötunnus. Returns ``IDInfo(valid=False)`` for anything malformed."""
    if not isinstance(value, str):
        return IDInfo(valid=False, country="FI", decode_bearing=True)
    s = value.strip().upper()
    if len(s) != 11:
        return IDInfo(valid=False, country="FI", decode_bearing=True)
    date_digits, marker, individual, control = s[0:6], s[6], s[7:10], s[10]
    if not date_digits.isdigit() or not individual.isdigit():
        return IDInfo(valid=False, country="FI", decode_bearing=True)
    century = _FI_CENTURY.get(marker)
    if century is None:
        return IDInfo(valid=False, country="FI", decode_bearing=True)
    if _fi_control_char(date_digits + individual) != control:
        return IDInfo(valid=False, country="FI", decode_bearing=True)

    dd, mm, yy = int(s[0:2]), int(s[2:4]), int(s[4:6])
    year = century + yy
    if not _plausible_date(year, mm, dd):
        return IDInfo(valid=False, country="FI", decode_bearing=True)

    sex = "M" if int(individual) % 2 == 1 else "F"  # individual-number parity → sex
    return IDInfo(
        valid=True, country="FI", decode_bearing=True,
        quasi_identifiers=frozenset({"DATE_OF_BIRTH", "SEX"}),
        extra={"sex": sex, "birth_date": f"{year:04d}-{mm:02d}-{dd:02d}"},
    )


# --- EE / LT: isikukood / asmens kodas (Baltic family) — decode-bearing ------------------
#
# 11-digit identifier ``G YY MM DD NNN C``:
#   G     century + sex: odd → male, even → female; 1/2 → 1800s, 3/4 → 1900s, 5/6 → 2000s,
#         7/8 → 2100s. (LT uses 1–6 in practice; EE defines 7/8 too — we accept the full 1–8 range,
#         which is harmless for LT since such IDs do not yet exist.)
#   YYMMDD  birth date (century supplied by G → DOB is unambiguous, unlike the IT/SE 2-digit year)
#   NNN     serial (separates births on the same day; for EE the parity does NOT encode sex — sex is
#           in G — so we never read it; some LT sources tie serial parity to G but G is authoritative)
#   C       ISO-7064-style **two-pass mod-11** check digit (see ``_baltic_check_digit``)
# A missed isikukood / asmens kodas deterministically discloses DATE_OF_BIRTH (century known) + SEX.
#
# Two-pass mod-11 (verified vs python-stdnum ``ee.ik`` — LT's ``lt.asmens`` imports the SAME routine):
#   pass 1 weights = 1,2,3,4,5,6,7,8,9,1   (i.e. (i % 9) + 1 for i = 0..9)
#   pass 2 weights = 3,4,5,6,7,8,9,1,2,3   (i.e. ((i + 2) % 9) + 1 for i = 0..9)
#   check = (Σ d_i·w1_i) mod 11; if check == 10 → check = (Σ d_i·w2_i) mod 11; if STILL 10 → 0.
# (Equivalently: ``check % 10`` after the second pass, since only the 10-case differs.)
# COLLISION FOOTGUN (EE/LT/LV share this exact structure): the validators are keyed by ``country`` so
# an LV personal code is never decoded as an EE/LT subject — the registry never auto-detects country.

_BALTIC_W1 = tuple((i % 9) + 1 for i in range(10))        # 1,2,3,4,5,6,7,8,9,1
_BALTIC_W2 = tuple(((i + 2) % 9) + 1 for i in range(10))  # 3,4,5,6,7,8,9,1,2,3
# G (1st digit) → century base + sex. 0 is invalid (no century/sex). 9 is unassigned.
_BALTIC_CENTURY = {1: 1800, 2: 1800, 3: 1900, 4: 1900, 5: 2000, 6: 2000, 7: 2100, 8: 2100}


def _baltic_check_digit(first10: str) -> int:
    """Two-pass ISO-7064-style mod-11 check digit for the 10-digit Baltic (EE/LT) body."""
    check = sum(int(d) * w for d, w in zip(first10, _BALTIC_W1)) % 11
    if check == 10:
        check = sum(int(d) * w for d, w in zip(first10, _BALTIC_W2)) % 11
        if check == 10:
            check = 0
    return check


def _parse_baltic(value: str, country: str) -> IDInfo:
    """Decode an EE isikukood / LT asmens kodas (identical algorithm). ``country`` ∈ {"EE","LT"}."""
    if not isinstance(value, str):
        return IDInfo(valid=False, country=country, decode_bearing=True)
    s = value.strip()
    if len(s) != 11 or not s.isdigit():
        return IDInfo(valid=False, country=country, decode_bearing=True)
    if _baltic_check_digit(s[:10]) != int(s[10]):
        return IDInfo(valid=False, country=country, decode_bearing=True)

    g = int(s[0])
    century = _BALTIC_CENTURY.get(g)
    if century is None:                                   # G = 0 or 9 → no century/sex
        return IDInfo(valid=False, country=country, decode_bearing=True)
    sex = "M" if g % 2 == 1 else "F"                      # G parity → sex (NOT the serial)
    yy, mm, dd = int(s[1:3]), int(s[3:5]), int(s[5:7])
    year = century + yy
    if not _plausible_date(year, mm, dd):
        return IDInfo(valid=False, country=country, decode_bearing=True)

    return IDInfo(
        valid=True, country=country, decode_bearing=True,
        quasi_identifiers=frozenset({"DATE_OF_BIRTH", "SEX"}),
        extra={"sex": sex, "birth_date": f"{year:04d}-{mm:02d}-{dd:02d}"},
    )


def _parse_ee(value: str) -> IDInfo:
    """Decode an Estonian isikukood. Returns ``IDInfo(valid=False)`` for anything malformed."""
    return _parse_baltic(value, "EE")


def _parse_lt(value: str) -> IDInfo:
    """Decode a Lithuanian asmens kodas. Returns ``IDInfo(valid=False)`` for anything malformed."""
    return _parse_baltic(value, "LT")


# --- NL: BSN / burgerservicenummer — coverage-only ---------------------------------------
#
# 9-digit citizen-service number validated by the "11-proef" (elfproef): the weighted sum
#   9·d1 + 8·d2 + 7·d3 + 6·d4 + 5·d5 + 4·d6 + 3·d7 + 2·d8 + (−1)·d9
# must be a NON-ZERO multiple of 11. (8-digit historical BSNs are left-padded with a zero to
# 9 digits before the test.) The BSN carries **no** embedded DOB/sex/place — it is a pure
# serial. So this validator is COVERAGE-ONLY: validate + detect, never decode/emit a QI.
# Spec: Rijksoverheid BSN 11-proef. Cross-checked against the KLU-102 generator.

_BSN_WEIGHTS = (9, 8, 7, 6, 5, 4, 3, 2, -1)


def _bsn_weighted_sum(digits: str) -> int:
    return sum(int(d) * w for d, w in zip(digits, _BSN_WEIGHTS))


def _parse_nl(value: str) -> IDInfo:
    """Validate a Dutch BSN (11-proef). Coverage-only: never discloses quasi-identifiers."""
    if not isinstance(value, str):
        return IDInfo(valid=False, country="NL", decode_bearing=False)
    s = value.strip()
    if len(s) == 8 and s.isdigit():
        s = "0" + s  # historical 8-digit BSN: left-pad to 9 before the 11-proef
    if len(s) != 9 or not s.isdigit():
        return IDInfo(valid=False, country="NL", decode_bearing=False)
    total = _bsn_weighted_sum(s)
    if total == 0 or total % 11 != 0:
        return IDInfo(valid=False, country="NL", decode_bearing=False)
    # Valid + detectable, but carries no quasi-identifier → quasi_identifiers stays empty.
    return IDInfo(valid=True, country="NL", decode_bearing=False)


# --- SI: EMŠO (Enotna matična številka občana) — decode-bearing --------------------------
#
# 13-digit ex-YU JMBG ``DD MM YYY RR BBB K`` (Slovenia's EMŠO; Zakon o matičnem registru):
#   DDMMYYY  birth date — YYY is the LAST THREE year digits; the ex-YU century convention is
#            YYY > 800 → 1000+YYY (1900s), else 2000+YYY (2000s), so the full date is unambiguous.
#   RR       political REGION of birth (2 digits). 50–59 = Slovenia (only 50 used until 2024); other
#            ranges belong to the other ex-YU republics, so RR also encodes the country.
#   BBB      serial WITHIN region/date: 000–499 → male, 500–999 → female (sex lives in the serial).
#   K        weighted mod-11 check digit over the 12-digit body, weights 7,6,5,4,3,2 repeated twice:
#            m = 11 − (Σ w·d mod 11); K = m for m∈1..9, and K = 0 for m∈{10,11}.
# A missed EMŠO deterministically discloses DATE_OF_BIRTH + SEX + REGION_OF_BIRTH — a RICHER surface
# than the Baltic family (region of birth, like the IT codice-fiscale's place-of-birth).
# Spec: ex-YU JMBG / SI EMŠO definition (Wikipedia "Unique Master Citizen Number"; ZMatR); cross-checked
# vs the avramovic/JMBG and docs.rs ``jmbg`` reference implementations and the worked example
# 0101006500006 (1st male registered in Slovenia on 2006-01-01 → K=6). Cross-checked vs the pack.
# COLLISION FOOTGUN: every ex-YU country shares this exact structure; the validator is country-keyed
# (RR carries the country) and never auto-detects — an SI EMŠO is only ever decoded as SI.

_EMSO_WEIGHTS = (7, 6, 5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def _emso_check_digit(first12: str) -> int:
    """EMŠO/JMBG mod-11 check digit for the 12-digit body (m = 11 − Σw·d mod 11; 10/11 → 0)."""
    m = 11 - (sum(int(d) * w for d, w in zip(first12, _EMSO_WEIGHTS)) % 11)
    return 0 if m >= 10 else m


def _parse_si(value: str) -> IDInfo:
    """Decode a Slovenian EMŠO. Returns ``IDInfo(valid=False)`` for anything malformed."""
    if not isinstance(value, str):
        return IDInfo(valid=False, country="SI", decode_bearing=True)
    s = value.strip().replace(" ", "")
    if len(s) != 13 or not s.isdigit():
        return IDInfo(valid=False, country="SI", decode_bearing=True)
    if _emso_check_digit(s[:12]) != int(s[12]):
        return IDInfo(valid=False, country="SI", decode_bearing=True)

    dd, mm, yyy = int(s[0:2]), int(s[2:4]), int(s[4:7])
    region = s[7:9]
    serial = int(s[9:12])
    year = (1000 + yyy) if yyy > 800 else (2000 + yyy)   # ex-YU century convention
    if not _plausible_date(year, mm, dd):
        return IDInfo(valid=False, country="SI", decode_bearing=True)

    sex = "M" if serial < 500 else "F"                    # serial 000–499 male / 500–999 female
    return IDInfo(
        valid=True, country="SI", decode_bearing=True,
        quasi_identifiers=frozenset({"DATE_OF_BIRTH", "SEX", "REGION_OF_BIRTH"}),
        extra={"sex": sex, "birth_date": f"{year:04d}-{mm:02d}-{dd:02d}", "region_code": region},
    )


# --- Country-keyed registry --------------------------------------------------------------

REGISTRY: dict[str, Validator] = {
    "RO": Validator("RO", "CNP", decode_bearing=True, parse=_parse_ro),
    "PL": Validator("PL", "PESEL", decode_bearing=True, parse=_parse_pl),
    "IT": Validator("IT", "codice fiscale", decode_bearing=True, parse=_parse_it),
    "ES": Validator("ES", "DNI/NIF", decode_bearing=False, parse=_parse_es),
    "DE": Validator("DE", "Steuer-IdNr", decode_bearing=False, parse=_parse_de),
    "FR": Validator("FR", "NIR", decode_bearing=True, parse=_parse_fr),
    "NL": Validator("NL", "BSN", decode_bearing=False, parse=_parse_nl),
    "SE": Validator("SE", "personnummer", decode_bearing=True, parse=_parse_se),
    "CZ": Validator("CZ", "rodné číslo", decode_bearing=True, parse=_parse_cz),
    "DK": Validator("DK", "CPR-nummer", decode_bearing=True, parse=_parse_dk),
    "FI": Validator("FI", "henkilötunnus", decode_bearing=True, parse=_parse_fi),
    "EE": Validator("EE", "isikukood", decode_bearing=True, parse=_parse_ee),
    "LT": Validator("LT", "asmens kodas", decode_bearing=True, parse=_parse_lt),
    "SI": Validator("SI", "EMŠO", decode_bearing=True, parse=_parse_si),
    "SK": Validator("SK", "rodné číslo", decode_bearing=True, parse=_parse_sk),
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
