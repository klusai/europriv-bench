"""KLU-118 reference-population / crosswalk module — vendored, checksummed, license-gated.

v1 vendored the **RO county -> NUTS-2** crosswalk used by the within-corpus k-anonymity diagnostic's
locality QI field. RES-17 adds the **v2 PURR machinery** (built + tested against a COMMITTED
SYNTHETIC PLACEHOLDER census fixture only — NOT real census data, NOT for any reported number):

  * ``build_joint`` — deterministic offline Iterative Proportional Fitting from census cross-tabs ->
    a sparse per-country joint over the frozen ``qi-v1`` schema (pinned tolerance, reproducible).
  * ``uniqueness`` — the Rocher–Hendrickx–de Montjoye (2019) population-uniqueness estimator, with
    **PURR@τ** (default τ=0.95), **ΔPURR = baseline − model**, and mean **κ** (re-id correctness).
  * ``fallbacks`` — marginal-independence + in-sample estimators, BOTH labelled weaker / upper-bound.
  * ``report`` — auto-emits the required source attributions + the status / red-team labels.

Until a census-calibrated generator lands, the PURR machinery is **internal sensitivity-analysis
machinery, NOT a reported metric**; vendoring the real Eurostat 2021 Census Hub hypercubes and
running PURR on a real benchmark config are DEFERRED follow-ups (see
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
