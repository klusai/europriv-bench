"""KLU-118 v1 — residual-QI enrichment (turns on the k-anonymity-violation diagnostic).

Verifies the deterministic, additive enrichment pass: CNP → SEX + DOB-band + county→NUTS-2, the
post-detection residual gating (a redacted CNP drops its QIs), the rare-condition health flag, and
that absent fields are OMITTED (never fabricated).
"""

from __future__ import annotations

from europriv_bench.national_id import check_digit
from europriv_bench.qi_enrich import residual_qi_rows
from europriv_bench.qi_schema import QI_SCHEMA_VERSION, build_qi_tuple, dob_to_band
from europriv_bench.spans import Span, char_spans_to_bioes, whitespace_tokens


def _cnp(base12: str) -> str:
    return base12 + str(check_digit(base12))


# A female, born 1968-02-19 (S=2 → 1900s, F), county 16 (Dolj → RO41).
CNP_F_DOLJ = _cnp("268021916521")
# A male, born 1985-07-15, county 40 (Bucuresti → RO32).
CNP_M_BUC = _cnp("185071540001")


def _row(text: str, spans: list[dict]) -> dict:
    return {"text": text, "country": "RO", "spans": spans}


def _all_o(text: str) -> list[str]:
    return ["O"] * len(whitespace_tokens(text))


def test_schema_version_is_frozen():
    assert QI_SCHEMA_VERSION == "qi-v1"


def test_dob_to_band_5yr():
    assert dob_to_band("1968-02-19") == "1965-1969"
    assert dob_to_band("1985-07-15") == "1985-1989"
    assert dob_to_band(None) is None
    assert dob_to_band("bad") is None


def test_build_qi_tuple_omits_absent_and_false_rare():
    t = build_qi_tuple({"sex": "M", "nuts2": None, "rare_condition": False})
    assert t == {"sex": "M"}  # None omitted; rare_condition False omitted (never fabricated)
    t2 = build_qi_tuple({"sex": "F", "rare_condition": True})
    assert t2 == {"sex": "F", "rare_condition": True}


def test_cnp_derives_sex_dob_nuts2_when_surviving():
    text = f"Pacient X CNP {CNP_F_DOLJ} domiciliu Dolj"
    c = text.index(CNP_F_DOLJ)
    row = _row(text, [{"start": c, "end": c + 13, "label": "NATIONAL_ID"}])
    out = residual_qi_rows([row], [_all_o(text)])
    assert len(out) == 1
    assert out[0]["qi_tuple"] == {"dob_band": "1965-1969", "sex": "F", "nuts2": "RO41"}


def test_redacted_cnp_drops_its_qis_on_residual():
    # Model redacts the CNP → its disclosed QIs must NOT appear (post-detection residual).
    text = f"Pacient X CNP {CNP_F_DOLJ}"
    c = text.index(CNP_F_DOLJ)
    row = _row(text, [{"start": c, "end": c + 13, "label": "NATIONAL_ID"}])
    pred = char_spans_to_bioes(text, [Span(c, c + 13, "NATIONAL_ID")])
    out = residual_qi_rows([row], [pred])
    assert out == []  # CNP redacted, no other QI → no equivalence-class key (subject dropped)


def test_rare_condition_flag_from_surviving_health_span():
    text = f"Pacient X CNP {CNP_M_BUC} diagnostic gripa"
    c = text.index(CNP_M_BUC)
    h = text.index("gripa")
    row = _row(text, [
        {"start": c, "end": c + 13, "label": "NATIONAL_ID"},
        {"start": h, "end": h + 5, "label": "HEALTH_CONDITION"},
    ])
    out = residual_qi_rows([row], [_all_o(text)])
    assert out[0]["qi_tuple"]["rare_condition"] is True


def test_redacted_health_span_drops_rare_condition():
    text = f"Pacient X CNP {CNP_M_BUC} diagnostic gripa"
    c = text.index(CNP_M_BUC)
    h = text.index("gripa")
    row = _row(text, [
        {"start": c, "end": c + 13, "label": "NATIONAL_ID"},
        {"start": h, "end": h + 5, "label": "HEALTH_CONDITION"},
    ])
    pred = char_spans_to_bioes(text, [Span(h, h + 5, "HEALTH_CONDITION")])  # only health redacted
    out = residual_qi_rows([row], [pred])
    assert "rare_condition" not in out[0]["qi_tuple"]  # health redacted → flag dropped
    assert out[0]["qi_tuple"]["sex"] == "M"            # CNP survived → its QIs remain


def test_duplicate_cnp_value_is_one_subject():
    # CNP repeated as "cod asigurat" → one subject (ANY-occurrence survival rule).
    text = f"CNP {CNP_M_BUC} ... Cod asigurat {CNP_M_BUC}"
    c1 = text.index(CNP_M_BUC)
    c2 = text.index(CNP_M_BUC, c1 + 1)
    row = _row(text, [
        {"start": c1, "end": c1 + 13, "label": "NATIONAL_ID"},
        {"start": c2, "end": c2 + 13, "label": "NATIONAL_ID"},
    ])
    out = residual_qi_rows([row], [_all_o(text)])
    assert len(out) == 1  # deduped to one subject


def test_invalid_cnp_is_not_a_subject():
    text = "CNP 0000000000000"
    row = _row(text, [{"start": 4, "end": 17, "label": "NATIONAL_ID"}])
    out = residual_qi_rows([row], [_all_o(text)])
    assert out == []  # invalid CNP → never fabricated into a QI subject


def test_non_ro_country_skips():
    text = f"CNP {CNP_M_BUC}"
    row = {"text": text, "country": "PL", "spans": [
        {"start": 4, "end": 17, "label": "NATIONAL_ID"}]}
    assert residual_qi_rows([row], [_all_o(text)], country="PL") == []


def test_determinism():
    text = f"CNP {CNP_F_DOLJ}"
    c = text.index(CNP_F_DOLJ)
    row = _row(text, [{"start": c, "end": c + 13, "label": "NATIONAL_ID"}])
    a = residual_qi_rows([row], [_all_o(text)])
    b = residual_qi_rows([row], [_all_o(text)])
    assert a == b
