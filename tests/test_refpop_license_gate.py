"""KLU-118 — CI license-gate + checksum verification for vendored refpop crosswalks.

The build MUST fail if any vendored source carries a license that is not on the allowlist
(CC-BY-4.0, CC-BY-3.0, EU-2011/833, ROU-OGL), or if a file's on-disk SHA-256 drifts from the
checksum recorded in the manifest. This is the design-doc's "CI license-gate" rule.
"""

from __future__ import annotations

from europriv_bench.refpop import (
    ALLOWLIST,
    file_sha256,
    load_manifest,
    ro_county_to_nuts2,
)


def test_manifest_allowlist_matches_module_allowlist():
    manifest = load_manifest()
    assert set(manifest["allowlist"]) == set(ALLOWLIST)


def test_every_vendored_source_is_on_the_license_allowlist():
    manifest = load_manifest()
    for src in manifest["sources"]:
        for comp in src["components"]:
            assert comp["license"] in ALLOWLIST, (
                f"source {src['id']} component license {comp['license']!r} is OFF the allowlist"
            )


def test_every_vendored_source_has_an_attribution():
    manifest = load_manifest()
    for src in manifest["sources"]:
        for comp in src["components"]:
            assert comp.get("attribution", "").strip(), f"{src['id']} missing attribution"


def test_vendored_checksums_match_on_disk():
    manifest = load_manifest()
    for src in manifest["sources"]:
        assert file_sha256(src["path"]) == src["sha256"], (
            f"checksum drift for {src['id']} ({src['path']}) — re-vendor + update the manifest"
        )


def test_ro_county_nuts2_crosswalk_loads_and_maps():
    assert ro_county_to_nuts2("16") == "RO41"   # Dolj → Sud-Vest Oltenia
    assert ro_county_to_nuts2("40") == "RO32"   # Bucuresti → Bucuresti-Ilfov
    assert ro_county_to_nuts2("32") == "RO12"   # Sibiu → Centru
    assert ro_county_to_nuts2(None) is None
    assert ro_county_to_nuts2("99") is None     # unmapped code → None (never fabricated)


# --- RES-17: the new synthetic census fixture is gated like any vendored file ----------------


def _source(src_id: str) -> dict:
    for src in load_manifest()["sources"]:
        if src["id"] == src_id:
            return src
    raise AssertionError(f"source {src_id!r} not on the manifest")


def test_synthetic_census_fixture_is_on_the_manifest_and_checksummed():
    src = _source("synthetic_census_xx")
    # The allowlist mechanism is intact: the synthetic fixture's license is on the allowlist...
    for comp in src["components"]:
        assert comp["license"] in ALLOWLIST
    # ...and its committed checksum matches on disk (re-vendor + bump on drift).
    assert file_sha256(src["path"]) == src["sha256"]


def test_synthetic_census_fixture_is_flagged_placeholder_everywhere():
    """A placeholder must be loudly labelled in the manifest AND inside the file's own meta block."""
    src = _source("synthetic_census_xx")
    assert src.get("placeholder") is True
    assert "PLACEHOLDER" in src["role"].upper()

    from europriv_bench.refpop.build_joint import load_census_spec

    spec = load_census_spec("synthetic_census_xx.yaml")
    meta = spec["meta"]
    assert meta["placeholder"] is True
    assert meta["is_real_census"] is False
    assert "NOT REAL CENSUS DATA" in meta["label"].upper()
