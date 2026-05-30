"""Romanian CNP (Cod Numeric Personal) — deterministic validation + decode.

The CNP is a 13-digit national identifier: ``S AA LL ZZ JJ NNN C``
  S    sex + century (1/3/5/7 male, 2/4/6/8 female; 9 = unspecified/foreign)
  AA   year (last two digits)
  LL   month, ZZ day
  JJ   county code (01–46 counties + Bucharest sectors; 51/52 Călărași/Giurgiu)
  NNN  sequence, C mod-11 checksum

Why this lives in the benchmark harness: a CNP is the sharpest demonstration of the
re-identification thesis — an *un-redacted* CNP is a **deterministic** disclosure of date of
birth + sex + county. The leakage metric (metrics.cnp_leakage) decodes exactly these. KlusAI's
RO data generators (klusai-datasets) import these helpers so generated CNPs are checksum-valid
and decode consistently — one source of truth.

Sources: vimishor/cnp-spec; Romanian Law 190/2018 art. 4 (national identification numbers).
"""

from __future__ import annotations

from dataclasses import dataclass

# Per-position weights; control digit = (Σ dᵢ·wᵢ) mod 11, with 10 → 1.
_WEIGHTS = (2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9)

# Century implied by the S (first) digit. 7/8/9 do not encode a century (resident foreigners /
# unspecified) → birth year is ambiguous across centuries.
_CENTURY = {1: 1900, 2: 1900, 3: 1800, 4: 1800, 5: 2000, 6: 2000}


@dataclass(frozen=True)
class CNPInfo:
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
    total = sum(int(d) * w for d, w in zip(first12, _WEIGHTS))
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
    century = _CENTURY.get(sd)

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


def _plausible_date(year: int, month: int, day: int) -> bool:
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return False
    days = [31, 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return day <= days[month - 1]
