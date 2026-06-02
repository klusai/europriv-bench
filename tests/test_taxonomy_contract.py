"""Contract tests for the externalized taxonomy (the bundled taxonomy.yaml is the source of truth).

These guard the governance invariants in GOVERNANCE.md:
  * the YAML version stays in sync with TAXONOMY_VERSION (loader fails loud otherwise);
  * the loaded label space is exactly bioes_labels();
  * the native→KP crosswalk round-trips as before (every declared source label maps back);
  * the YAML is bundled *inside the package* so it travels with the wheel (KLU-43).
"""

from __future__ import annotations

from importlib import resources

import pytest
import yaml

from europriv_bench import taxonomy as tax
from europriv_bench.crosswalk import mapped_labels, to_kp


def _conf_doc() -> dict:
    # Read via the same importlib.resources handle the loader uses — works for editable
    # and zip/wheel installs alike.
    with tax._locate_conf().open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_yaml_is_the_source_loaded():
    # The module loaded from the bundled taxonomy.yaml, not a hardcoded list.
    assert tax._locate_conf().name == "taxonomy.yaml"


def test_taxonomy_yaml_is_bundled_in_the_package():
    # KLU-43: the YAML must be a *package resource* (src/europriv_bench/conf/taxonomy.yaml),
    # not merely a file somewhere up the source tree. This is what guarantees it ships in the
    # wheel and resolves for `pip install`ed users. Under the old, unbundled setup (YAML in a
    # top-level conf/ outside src/, resolved by walking the source tree), this would fail:
    # importlib.resources would not find it inside the installed package.
    resource = resources.files("europriv_bench.conf") / "taxonomy.yaml"
    assert resource.is_file(), (
        "taxonomy.yaml is not bundled inside the europriv_bench package — a wheel install "
        "would be unable to load the taxonomy"
    )
    # It loads and carries the version, purely through the package-resource API (no source tree).
    doc = yaml.safe_load(resource.read_text(encoding="utf-8"))
    assert doc["version"] == tax.TAXONOMY_VERSION


def test_version_in_sync():
    assert _conf_doc()["version"] == tax.TAXONOMY_VERSION


def test_version_mismatch_fails_loud(monkeypatch):
    # Simulate a drifted in-code anchor; reloading must raise, not silently accept.
    monkeypatch.setattr(tax, "TAXONOMY_VERSION", "9.9.9-bogus")
    with pytest.raises(ValueError, match="version mismatch"):
        tax._load_taxonomy()


def test_label_space_matches_bioes():
    doc = _conf_doc()
    names = [e["name"] for e in doc["entities"]]
    expected = ["O"]
    for n in names:
        expected += [f"B-{n}", f"I-{n}", f"E-{n}", f"S-{n}"]
    assert tax.bioes_labels() == expected
    assert tax.ENTITY_NAMES == names
    assert len(tax.bioes_labels()) == 1 + 4 * len(names)


def test_schemes_match_yaml():
    assert list(tax.SCHEMES) == list(_conf_doc()["schemes"])


def test_crosswalk_roundtrips():
    # Every native label declared in the YAML must invert back to its KP entity type,
    # for every scheme — the native→KP map is a faithful inverse of the crosswalk.
    doc = _conf_doc()
    seen = 0
    for entity in doc["entities"]:
        for scheme, natives in (entity.get("crosswalk") or {}).items():
            for native in natives:
                assert to_kp(scheme, native) == entity["name"]
                seen += 1
    assert seen > 0
    # mapped_labels is the per-scheme view of the same inverse.
    for scheme in tax.SCHEMES:
        for native, kp in mapped_labels(scheme).items():
            assert to_kp(scheme, native) == kp


def test_special_category_from_yaml():
    doc = _conf_doc()
    expected = [e["name"] for e in doc["entities"] if e.get("gdpr_special")]
    assert tax.special_category_types() == expected
