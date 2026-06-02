"""Contract test for the Presidio adapter (KLU-52) — the first third-party baseline.

Presidio is an orchestration tool (regex/checksum recognizers + a spaCy NER), not a single HF
model. Its adapter maps Presidio's native entity vocabulary onto the harmonized KP taxonomy and
feeds the same KP→BIOES seam GLiNER/kp-model use. These tests run offline (no AnalyzerEngine, no
spaCy model) — they guard the registration, the entity→KP map, and that the map's KP targets are
all real taxonomy types, so a future taxonomy bump that renames a type fails here.
"""

from __future__ import annotations

from europriv_bench.adapters import BUILDERS, PresidioAdapter
from europriv_bench.crosswalk import kp_entities_to_bioes
from europriv_bench.leaderboard import CLEAN_HELD_OUT, classify_contamination
from europriv_bench.spans import validate_bioes
from europriv_bench.taxonomy import ENTITY_NAMES, bioes_labels


def test_presidio_adapter_registered():
    assert BUILDERS["presidio"] is PresidioAdapter
    a = PresidioAdapter()
    assert a.name == "presidio"
    # Not an HF checkpoint — the model_id stamps the orchestration stack.
    assert "presidio-analyzer" in a.model_id


def test_presidio_kp_targets_are_real_taxonomy_types():
    # Every KP type the adapter maps Presidio entities onto must exist in the taxonomy.
    valid = set(ENTITY_NAMES)
    assert set(PresidioAdapter.PRESIDIO_TO_KP.values()) <= valid


def test_presidio_mapped_spans_roundtrip_to_kp_bioes():
    # The exact shape PresidioAdapter.predict_tags builds from an AnalyzerEngine result, after the
    # Presidio→KP map: a PERSON + an EMAIL_ADDRESS→EMAIL + a US_SSN→NATIONAL_ID.
    text = "Jane Doe jane@x.io 123-45-6789"
    kp_ents = [
        {"start": 0, "end": 8, "label": PresidioAdapter.PRESIDIO_TO_KP["PERSON"]},
        {"start": 9, "end": 18, "label": PresidioAdapter.PRESIDIO_TO_KP["EMAIL_ADDRESS"]},
        {"start": 19, "end": 30, "label": PresidioAdapter.PRESIDIO_TO_KP["US_SSN"]},
    ]
    tags = kp_entities_to_bioes(text, kp_ents)
    assert tags == ["B-PERSON", "E-PERSON", "S-EMAIL", "S-NATIONAL_ID"]
    valid = set(bioes_labels())
    assert all(t in valid for t in tags)
    validate_bioes(tags)


def test_presidio_is_clean_held_out_everywhere():
    # Rule-based: no training data of ours, so every config is a clean held-out test — including the
    # AI4Privacy general configs that the trained baselines (openmed/tabularisai) overlap with.
    for config in ("en", "de", "fr", "it", "es", "nl", "ro-synthetic-v1", "pl-realskeleton-v1"):
        assert classify_contamination("presidio", config) == CLEAN_HELD_OUT
