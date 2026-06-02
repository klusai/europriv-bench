"""Contract tests for the GLiNER2 and spaCy adapters (KLU-108) — the 2nd + 3rd third-party
systems landed on the board via the no-secrets submission CI.

Both are external systems trained on NONE of the EuroPriv-Bench gold:
  * GLiNER2 (``fastino/gliner2-base-v1``, Fastino, Apache-2.0) — a schema-based IE model, distinct
    from the original GLiNER. Prompted with KP-type phrasings; returned labels map back to KP.
  * spaCy (``en_core_web_lg``, MIT, OntoNotes-trained) — statistical NER; its OntoNotes types map
    onto the KP taxonomy.

These run offline (no model download): they guard registration, the entity→KP maps, that the maps'
KP targets are real taxonomy types (so a taxonomy rename fails here), and the clean_held_out
contamination marker that the honest-labelling acceptance requires.
"""

from __future__ import annotations

from europriv_bench.adapters import BUILDERS, GLiNER2Adapter, SpacyAdapter
from europriv_bench.crosswalk import kp_entities_to_bioes
from europriv_bench.leaderboard import CLEAN_HELD_OUT, classify_contamination
from europriv_bench.spans import validate_bioes
from europriv_bench.taxonomy import ENTITY_NAMES, bioes_labels

_VALID_KP = set(ENTITY_NAMES)
_VALID_BIOES = set(bioes_labels())


# --- GLiNER2 ----------------------------------------------------------------------------------


def test_gliner2_adapter_registered():
    assert BUILDERS["gliner2"] is GLiNER2Adapter
    a = GLiNER2Adapter()
    assert a.name == "gliner2"
    assert a.model_id == "fastino/gliner2-base-v1"


def test_gliner2_kp_targets_are_real_taxonomy_types():
    assert set(GLiNER2Adapter.LABEL_TO_KP.values()) <= _VALID_KP


def test_gliner2_mapped_spans_roundtrip_to_kp_bioes():
    # The shape GLiNER2Adapter.predict_tags builds after the prompt-label→KP map: a person, an
    # email, and a national identification number.
    text = "Jane Doe jane@x.io 123-45-6789"
    kp_ents = [
        {"start": 0, "end": 8, "label": GLiNER2Adapter.LABEL_TO_KP["person"]},
        {"start": 9, "end": 18, "label": GLiNER2Adapter.LABEL_TO_KP["email"]},
        {"start": 19, "end": 30, "label": GLiNER2Adapter.LABEL_TO_KP["national identification number"]},
    ]
    tags = kp_entities_to_bioes(text, kp_ents)
    assert tags == ["B-PERSON", "E-PERSON", "S-EMAIL", "S-NATIONAL_ID"]
    validate_bioes(tags)
    assert all(t in _VALID_BIOES for t in tags)


def test_gliner2_is_clean_held_out_everywhere():
    for config in ("en", "de", "fr", "it", "es", "nl", "ro-synthetic-v1", "pl-realskeleton-v1"):
        assert classify_contamination("gliner2", config) == CLEAN_HELD_OUT


# --- spaCy ------------------------------------------------------------------------------------


def test_spacy_adapter_registered():
    assert BUILDERS["spacy"] is SpacyAdapter
    a = SpacyAdapter()
    assert a.name == "spacy"
    assert "en_core_web_lg" in a.model_id


def test_spacy_kp_targets_are_real_taxonomy_types():
    assert set(SpacyAdapter.SPACY_TO_KP.values()) <= _VALID_KP


def test_spacy_mapped_spans_roundtrip_to_kp_bioes():
    # The shape SpacyAdapter.predict_tags builds after the OntoNotes→KP map: PERSON, GPE→ADDRESS,
    # ORG→ORG_PARTY.
    text = "Jane Doe Paris Acme"
    kp_ents = [
        {"start": 0, "end": 8, "label": SpacyAdapter.SPACY_TO_KP["PERSON"]},
        {"start": 9, "end": 14, "label": SpacyAdapter.SPACY_TO_KP["GPE"]},
        {"start": 15, "end": 19, "label": SpacyAdapter.SPACY_TO_KP["ORG"]},
    ]
    tags = kp_entities_to_bioes(text, kp_ents)
    assert tags == ["B-PERSON", "E-PERSON", "S-ADDRESS", "S-ORG_PARTY"]
    validate_bioes(tags)
    assert all(t in _VALID_BIOES for t in tags)


def test_spacy_is_clean_held_out_everywhere():
    for config in ("en", "de", "fr", "it", "es", "nl", "ro-synthetic-v1", "pl-realskeleton-v1"):
        assert classify_contamination("spacy", config) == CLEAN_HELD_OUT
