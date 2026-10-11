"""Positive and negative controls for Unicode boundary decoding and exact operators."""

import pytest

from europriv_bench.adapters import Res100MoEAdapter
from europriv_bench.decoding import MIN_LENGTH, postprocess_spans, structured_validity, word_units


def span(start, end, label="PERSON"):
    return {"start": start, "end": end, "label": label}


@pytest.mark.parametrize("rule", ["strict", "inward", "anchored"])
@pytest.mark.parametrize("text,start,end", [("A4-Papier", 0, 1), ("etichette", 4, 9),
                                           ("Skłodowskiej-Curie", 12, 14)])
def test_fragments_are_dropped_before_expansion(rule, text, start, end):
    assert postprocess_spans(text, [span(start, end)], rule=rule) == []


@pytest.mark.parametrize("text", ["Ana", "Li", "O’Connor", "Łukasz", "Ana\u0301", "中文"])
@pytest.mark.parametrize("rule", ["strict", "inward", "anchored"])
def test_whole_word_names_survive(text, rule):
    entity = span(0, len(text))
    assert postprocess_spans(text, [entity], rule=rule) == [entity]


def test_unicode_and_mixed_fragment_snap_modes():
    assert word_units("Ana\u0301 O’Connor") == [(0, 4), (5, 13)]
    text = "kwota zgodna"
    entity = span(2, 12)
    assert postprocess_spans(text, [entity], rule="strict") == []
    assert postprocess_spans(text, [entity], rule="inward") == [span(6, 12)]
    assert postprocess_spans(text, [entity], rule="anchored") == [span(0, 12)]
    assert entity == span(2, 12)
    assert postprocess_spans("Ana\u0301", [span(0, 3)], rule="anchored") == []
    assert postprocess_spans("  Ana  ", [span(0, 7)], rule="strict") == [span(2, 5)]


def test_minimums_and_structured_validation(monkeypatch):
    assert postprocess_spans("A", [span(0, 1)], rule="strict") == []
    assert structured_validity("GB82 WEST 1234 5698 7654 32", "ACCOUNT_ID") == (True, True)
    assert structured_validity("GB83 WEST 1234 5698 7654 32", "ACCOUNT_ID") == (False, False)
    assert structured_validity("GB82 X", "ACCOUNT_ID") == (False, False)
    assert structured_validity("+40 (721) 123-456", "PHONE") == (True, False)
    assert structured_validity("123-45", "PHONE") == (False, False)
    assert structured_validity("call 123456789", "PHONE") == (False, False)
    assert structured_validity("1800101221144", "NATIONAL_ID", "RO") == (True, True)
    assert structured_validity("1800101221145", "NATIONAL_ID", "RO") == (False, False)
    assert structured_validity("unknown", "NATIONAL_ID") == (True, False)
    monkeypatch.setitem(MIN_LENGTH, "NATIONAL_ID", 99)
    entity = span(0, 13, "NATIONAL_ID")
    assert postprocess_spans("1800101221144", [entity], rule="strict", country="RO") == [entity]
    assert postprocess_spans("1800101221145", [entity], rule="strict", country="RO") == []


@pytest.mark.parametrize("entity", [span(-1, 2), span(0, 9), span(2, 2), span(True, 2)])
def test_invalid_offsets_fail(entity):
    with pytest.raises(ValueError, match="offsets"):
        postprocess_spans("Ana", [entity], rule="strict")


def test_adapter_tags_and_exact_operator_share_decoded_spans():
    text = "Ana etichette"
    adapter = Res100MoEAdapter("local", decoding_rule="strict")
    adapter._pipe = lambda texts, **kwargs: [[
        {"entity_group": "S-PERSON", "start": 0, "end": 3},
        {"entity_group": "S-PERSON", "start": 8, "end": 13},
    ] for _ in texts]
    rec = adapter.predict_receipts([text])[0]
    assert rec["intervals"] == [[0, 3]]
    assert rec["output"] == "█ etichette"
    assert rec["tags"] == ["S-PERSON", "O"]
    assert len(rec["raw_native"]) == 2
    adapter.decoding_rule = None
    assert adapter.predict_receipts([text])[0]["intervals"] == [[0, 3], [8, 13]]


def test_dev_selection_requires_feasibility_and_uses_registered_ties():
    from analysis.score_gateway_decoding import select_rule

    grid = [
        {"rule": "anchored", "feasible": False, "macro_leak": 0, "macro_utility": 0},
        {"rule": "inward", "feasible": True, "macro_leak": .2, "macro_utility": .001},
        {"rule": "strict", "feasible": True, "macro_leak": .2, "macro_utility": .001},
    ]
    assert select_rule(grid) == "strict"
    assert select_rule(grid[:1]) is None
