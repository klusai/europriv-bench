"""KLU-118 v1 — the FROZEN, VERSIONED quasi-identifier (QI) schema + binning rules.

This is the schema the within-corpus k-anonymity-violation diagnostic
(``metrics.k_anonymity_violation``) keys equivalence classes on. It is **versioned**: the version
string is part of the dataset/diagnostic version string, because the bins must match between the
eval QIs and (in v2) the census tables, or the lookup is meaningless (design-doc "QI schema"
section). Bump ``QI_SCHEMA_VERSION`` whenever a field or a binning rule changes.

v1 fields (binned VALUES, never raw text):
  * ``dob_band``     — DOB -> 5-year age band label "YYYY-YYYY" (year-of-birth band; coarse on purpose).
  * ``sex``          — "M" | "F".
  * ``nuts2``        — locality -> NUTS-2 region code (e.g. RO12); derived from the CNP county.
  * ``nationality``  — ISO-ish nationality token (only when gold supplies it; v1 RO gold does not).
  * ``isco_major``   — profession -> ISCO-08 major group (1 digit; only when gold supplies a profession).
  * ``rare_condition`` — boolean flag: gold carries a HEALTH_CONDITION span (special-category, Art. 9).

DESIGN RULES (binding):
  * Direct identifiers (name, the national IDs, email, phone, account/case numbers) are NOT QIs.
    The name has its OWN v1 channel (``name_in_context_leakage``).
  * A field that is ABSENT from gold is OMITTED from the tuple — never fabricated, never defaulted.
  * Binning is deterministic and pure (no RNG, no clock): the same gold -> the same tuple, always.
  * The 5-year band is on YEAR OF BIRTH (a band edge derived from DOB), so it is robust to the
    unknown "as-of" date; this is a within-corpus distinctiveness key, not an age computation.
"""

from __future__ import annotations

QI_SCHEMA_VERSION = "qi-v1"

# The frozen v1 field order (also the order reported in the diagnostic's schema echo).
QI_FIELDS: tuple[str, ...] = (
    "dob_band",
    "sex",
    "nuts2",
    "nationality",
    "isco_major",
    "rare_condition",
)

# 5-year year-of-birth band width (years). Coarse on purpose: a within-corpus distinctiveness key
# must not itself be near-unique, and v2 census joints are published in 5-year bands.
_DOB_BAND_WIDTH = 5


def dob_to_band(birth_date: str | None) -> str | None:
    """Map an ISO ``YYYY-MM-DD`` birth date to a 5-year year-of-birth band label ``"YYYY-YYYY"``.

    Returns ``None`` when the date is absent or the year is unparseable (-> field OMITTED). The
    band is closed-open on year-of-birth: e.g. 1968 -> ``"1965-1969"`` with width 5 anchored on
    multiples of the width.
    """
    if not birth_date or not isinstance(birth_date, str):
        return None
    try:
        year = int(birth_date[:4])
    except (ValueError, TypeError):
        return None
    lo = (year // _DOB_BAND_WIDTH) * _DOB_BAND_WIDTH
    return f"{lo:04d}-{lo + _DOB_BAND_WIDTH - 1:04d}"


def build_qi_tuple(fields: dict[str, object]) -> dict[str, object]:
    """Assemble a residual QI tuple from already-derived field values, in the frozen field order.

    Only keys present in ``QI_FIELDS`` with a NON-``None`` value are kept — an absent QI field is
    OMITTED (never fabricated). ``rare_condition`` is kept only when ``True`` (its absence, i.e. no
    health span surviving on the residual, is "no special-category QI", which we represent by
    omission so it cannot silently fabricate a "False" QI that splits equivalence classes).
    """
    out: dict[str, object] = {}
    for key in QI_FIELDS:
        if key not in fields:
            continue
        val = fields[key]
        if val is None:
            continue
        if key == "rare_condition" and not val:
            continue
        out[key] = val
    return out
