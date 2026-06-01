"""Phase 1: crosswalk inversion, native→KP mapping, and gold-row conversion."""

import pytest

from europriv_bench.crosswalk import entities_to_kp_bioes, kp_entities_to_bioes, mapped_labels, to_kp
from europriv_bench.runner import _rows_to_gold


def test_crosswalk_maps_native_labels_to_kp():
    # OpenAI privacy-filter native labels.
    assert to_kp("openai", "private_person") == "PERSON"
    assert to_kp("openai", "private_email") == "EMAIL"
    # AI4Privacy native labels collapse onto KP types.
    assert to_kp("ai4privacy", "GIVENNAME") == "PERSON"
    assert to_kp("ai4privacy", "SURNAME") == "PERSON"
    # Unknown / unmapped → None (dropped, not guessed).
    assert to_kp("openai", "not_a_label") is None
    assert to_kp("nonexistent_scheme", "x") is None
    # tabularisai scheme (XLM-R baseline): national IDs + Art.9 handling.
    assert to_kp("tabularisai", "PASSPORT_NUMBER") == "NATIONAL_ID"
    assert to_kp("tabularisai", "PHONE_NUMBER") == "PHONE"
    assert to_kp("tabularisai", "ETHNICITY") is None  # GDPR Art.9 — deferred, not mis-mapped


def test_mapped_labels_reports_coverage():
    m = mapped_labels("ai4privacy")
    assert m["EMAIL"] == "EMAIL" and m["TELEPHONENUM"] == "PHONE"


def test_kp_entities_to_bioes_direct():
    # GLiNER path: entities already carry KP labels (no scheme crosswalk).
    text = "Ion Popescu plata"
    tags = kp_entities_to_bioes(text, [{"start": 0, "end": 11, "label": "PERSON"}])
    assert tags == ["B-PERSON", "E-PERSON", "O"]


def test_entities_to_kp_bioes_maps_and_drops_unmapped():
    text = "Email harry@hogwarts.edu now"  # tokens: Email, harry@hogwarts.edu, now
    ents = [
        {"label": "private_email", "start": 6, "end": 24},  # → EMAIL
        {"label": "mystery", "start": 0, "end": 5},          # unmapped → dropped
    ]
    tags = entities_to_kp_bioes(text, ents, "openai")
    assert tags == ["O", "S-EMAIL", "O"]


def test_rows_to_gold_builds_validated_tags():
    rows = [
        {"text": "Ion Popescu scrie", "spans": [{"start": 0, "end": 11, "label": "PERSON"}]},
        {"text": "fara pii aici", "spans": []},
    ]
    texts, gold = _rows_to_gold(rows)
    assert texts[0] == "Ion Popescu scrie"
    assert gold[0] == ["B-PERSON", "E-PERSON", "O"]
    assert gold[1] == ["O", "O", "O"]


def test_rows_to_gold_rejects_malformed_span():
    bad = [{"text": "a b", "spans": [{"start": 99, "end": 100, "label": "PERSON"}]}]
    with pytest.raises(ValueError):
        _rows_to_gold(bad)
