"""RES-72/104: tab_reid_leakage — DIRECT/QUASI re-id leak rate on the post-detection residual."""
from europriv_bench.metrics import tab_reid_leakage
from europriv_bench.spans import whitespace_tokens

# "Mr John Smith sued Acme Ltd ." → tokens: Mr | John | Smith | sued | Acme | Ltd | .
TEXT = "Mr John Smith sued Acme Ltd ."
SPANS = [
    {"start": 3, "end": 13, "label": "PERSON", "identifier_type": "DIRECT", "entity_id": "e1"},
    {"start": 19, "end": 27, "label": "ORG_PARTY", "identifier_type": "QUASI", "entity_id": "e2"},
]
ROW = {"text": TEXT, "spans": SPANS}


def _tags(detected: bool) -> list[str]:
    # one tag per whitespace token; non-O everywhere if "detected", else all-O (everything leaks)
    return ["S-X" if detected else "O" for _ in whitespace_tokens(TEXT)]


def test_all_leaked_when_nothing_detected():
    m = tab_reid_leakage([ROW], [_tags(False)])
    assert m["direct_leak_rate"] == 1.0 and m["quasi_leak_rate"] == 1.0
    assert m["direct_subjects_total"] == 1.0 and m["quasi_subjects_total"] == 1.0


def test_none_leaked_when_all_detected():
    m = tab_reid_leakage([ROW], [_tags(True)])
    assert m["direct_leak_rate"] == 0.0 and m["quasi_leak_rate"] == 0.0


def test_split_by_identifier_type():
    # Detect the QUASI org tokens (Acme=idx4, Ltd=idx5) but not the DIRECT name → direct leaks, quasi not.
    tags = ["O", "O", "O", "O", "S-X", "S-X", "O"]
    m = tab_reid_leakage([ROW], [tags])
    assert m["direct_leak_rate"] == 1.0  # name un-redacted → re-id risk
    assert m["quasi_leak_rate"] == 0.0
    assert 0.0 <= m["all_leak_rate"] <= 1.0
