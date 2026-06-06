"""KLU-118 reference-population / crosswalk module — vendored, checksummed, license-gated.

v1 scope is intentionally narrow: the only vendored artifact is the **RO county -> NUTS-2**
crosswalk used by the within-corpus k-anonymity diagnostic's locality QI field. NO census
population, microdata, or population-uniqueness estimator is vendored here — that is the v2 PURR
work, which is blocked on a census-calibrated generator (see
``docs/klu-118-qi-distinctiveness-design.md``).

Every vendored file is declared in ``manifest.yaml`` with a license on the allowlist
(``CC-BY-4.0``, ``CC-BY-3.0``, ``EU-2011/833``, ``ROU-OGL``) and a recorded SHA-256. The
license-gate test verifies both, so the build fails on an off-allowlist license or a checksum drift.
"""

from __future__ import annotations

import csv
import hashlib
from functools import lru_cache
from importlib import resources

import yaml

ALLOWLIST = frozenset({"CC-BY-4.0", "CC-BY-3.0", "EU-2011/833", "ROU-OGL"})


@lru_cache(maxsize=1)
def load_manifest() -> dict:
    """Parsed ``manifest.yaml`` (the source registry + license allowlist)."""
    text = resources.files("europriv_bench.refpop").joinpath("manifest.yaml").read_text(
        encoding="utf-8"
    )
    return yaml.safe_load(text)


def _read_source_bytes(rel_path: str) -> bytes:
    parts = rel_path.split("/")
    res = resources.files("europriv_bench.refpop")
    for p in parts:
        res = res.joinpath(p)
    return res.read_bytes()


def file_sha256(rel_path: str) -> str:
    """SHA-256 of a vendored file, addressed relative to the ``refpop`` package."""
    return hashlib.sha256(_read_source_bytes(rel_path)).hexdigest()


@lru_cache(maxsize=1)
def load_ro_county_nuts2() -> dict[str, dict[str, str]]:
    """RO CNP county-code (``JJ``) -> ``{county_name, nuts2_code, nuts2_name}``.

    Loaded from the vendored crosswalk (comment lines starting with ``#`` are skipped). The CNP
    county code is a zero-padded two-digit string (e.g. ``"05"``), matching ``CNPInfo.county_code``.
    """
    raw = _read_source_bytes("crosswalks/ro_county_nuts2.csv").decode("utf-8")
    lines = [ln for ln in raw.splitlines() if ln and not ln.lstrip().startswith("#")]
    reader = csv.DictReader(lines)
    out: dict[str, dict[str, str]] = {}
    for row in reader:
        out[row["jj_code"]] = {
            "county_name": row["county_name"],
            "nuts2_code": row["nuts2_code"],
            "nuts2_name": row["nuts2_name"],
        }
    return out


def ro_county_to_nuts2(county_code: str | None) -> str | None:
    """Map a CNP county code (``JJ``) to its NUTS-2 region code, or ``None`` if unmapped."""
    if not county_code:
        return None
    entry = load_ro_county_nuts2().get(str(county_code))
    return entry["nuts2_code"] if entry else None
