"""Audit fragments must partition exactly the harness's utility numerator."""

from analysis.gateway_overredaction import error_fragments
from europriv_bench.gateway import gateway_utility


def test_union_subtraction_unicode_and_whitespace():
    row = {
        "id": "dev/1", "language": "pl", "family_id": "family/1", "text": "Żan  Kowal, kod 42",
        "spans": [{"start": 0, "end": 10, "label": "PERSON"}], "retained_spans": [],
    }
    receipt = {
        "intervals": [[0, 11], [9, 11], [11, 12], [16, 18]],
        "native": [{"start": 0, "end": 11, "label": "PERSON"},
                   {"start": 9, "end": 11, "label": "PERSON"},
                   {"start": 11, "end": 12, "label": "PERSON"},
                   {"start": 16, "end": 18, "label": "PHONE"}],
    }
    errors = error_fragments(row, receipt)
    assert [e["surface"] for e in errors] == [",", "42"]
    assert len(errors[0]["overlapping_gold"]) == 1
    assert not errors[1]["overlapping_gold"]
    score = gateway_utility([row], [receipt["intervals"]])
    assert sum(e["characters"] for e in errors) == score["removed_non_pii_characters"] == 3
