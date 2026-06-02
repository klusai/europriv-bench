"""National-ID validators (RO/PL/IT decode-bearing, ES coverage-only) + leakage metrics."""

from europriv_bench.adapters import build
from europriv_bench.metrics import cnp_leakage, national_id_leakage, wilson_interval
from europriv_bench.national_id import (
    check_digit,
    get_validator,
    parse_cnp,
    parse_national_id,
    supported_countries,
    validate_cnp,
)
from europriv_bench.runner import run_spec
from europriv_bench.spec import EvalSpec

# Known-valid reference IDs (textbook samples; all carry valid checksums/control chars).
PESEL_M_1944 = "44051401359"   # 1944-05-14, male
CF_IT_M = "RSSMRA85T10A562S"   # 1985-12-10, male, Belfiore A562
DNI_ES = "12345678Z"           # canonical Spanish DNI (12345678 mod 23 → Z)


def _make_cnp(base12: str) -> str:
    return base12 + str(check_digit(base12))


def test_valid_cnp_decodes_dob_sex_county():
    cnp = _make_cnp("185071540001")  # S=1 (male,1900s) 85-07-15, county 40
    info = parse_cnp(cnp)
    assert info.valid and validate_cnp(cnp)
    assert info.sex == "M"
    assert info.birth_date == "1985-07-15"
    assert info.county_code == "40"
    assert info.century_known
    assert info.disclosed_quasi_identifiers() == {"DATE_OF_BIRTH", "SEX", "COUNTY"}


def test_female_2000s_and_checksum_rejection():
    cnp = _make_cnp("605031120007")  # S=6 (female, 2000s)
    info = parse_cnp(cnp)
    assert info.valid and info.sex == "F" and info.birth_date.startswith("2005-03-11")
    # Corrupt the check digit → invalid.
    assert not validate_cnp(cnp[:-1] + str((int(cnp[-1]) + 1) % 10))
    assert not validate_cnp("123")  # malformed length


def test_foreign_resident_century_ambiguous():
    cnp = _make_cnp("790051540001")  # S=7 → resident foreigner, century not encoded
    info = parse_cnp(cnp)
    assert info.valid and info.century_known is False
    assert info.birth_date is None
    # DOB not disclosed (ambiguous), but SEX + COUNTY still are.
    assert info.disclosed_quasi_identifiers() == {"SEX", "COUNTY"}


def test_cnp_leakage_counts_missed_as_disclosure():
    cnp = _make_cnp("185071540001")
    text = f"CNP {cnp} emis"  # tokens: ["CNP", "<cnp>", "emis"]
    rows = [{"text": text, "spans": [{"start": 4, "end": 4 + 13, "label": "NATIONAL_ID"}]}]

    missed = cnp_leakage(rows, [["O", "O", "O"]])               # model misses it
    assert missed["cnp_total"] == 1 and missed["cnp_missed"] == 1
    assert missed["leak_rate"] == 1.0
    assert missed["leaked_quasi_identifiers"] == 3              # DOB + SEX + COUNTY

    caught = cnp_leakage(rows, [["O", "S-NATIONAL_ID", "O"]])   # model redacts it
    assert caught["cnp_detected"] == 1 and caught["leak_rate"] == 0.0
    assert caught["leaked_quasi_identifiers"] == 0


def test_cnp_leakage_emits_wilson_ci_bracketing_point_estimate():
    cnp = _make_cnp("185071540001")
    text = f"CNP {cnp} emis"
    rows = [{"text": text, "spans": [{"start": 4, "end": 4 + 13, "label": "NATIONAL_ID"}]}]

    # One miss out of one → point leak_rate 1.0; the Wilson interval must bracket it.
    res = cnp_leakage(rows, [["O", "O", "O"]])
    assert "leak_rate_ci_low" in res and "leak_rate_ci_high" in res
    assert res["leak_rate_ci_low"] <= res["leak_rate"] <= res["leak_rate_ci_high"]
    assert 0.0 <= res["leak_rate_ci_low"] and res["leak_rate_ci_high"] <= 1.0


def test_wilson_ci_reproduces_privacy_filter_ro_real_leak_rate():
    # privacy-filter on ro-realskeleton-v1: 16 leaked CNP *subjects* out of 1123 distinct subjects
    # (KLU-49 committed baseline counts — per-subject, after deduping the CASS "cod asigurat"
    # duplicate within each clinical doc). Point estimate ~1.4%; harness 95% Wilson CI ~0.9%-2.3%.
    missed, total = 16, 1123
    point = missed / total
    low, high = wilson_interval(missed, total)
    assert abs(point - 0.0142) < 0.001          # ~1.4%
    assert low < point < high                    # brackets the point estimate
    assert 0.008 < low < 0.010                   # lower ~0.9%
    assert 0.022 < high < 0.024                  # upper ~2.3%


def test_run_spec_wires_cnp_leakage_via_rows():
    cnp = _make_cnp("185071540001")
    rows = [{"text": f"CNP {cnp} emis", "spans": [{"start": 4, "end": 17, "label": "NATIONAL_ID"}]}]
    spec = EvalSpec.model_validate({
        "name": "ro-test", "task": "detection", "languages": ["ro"],
        "dataset": {"hf_id": "x", "config": "ro", "split": "test"},
        "metrics": ["entity_f1", "cnp_leakage"],
    })
    res = run_spec(spec, build("dummy"), rows=rows)   # dummy predicts all-O → leak
    assert res["scores"]["cnp_leakage"]["cnp_total"] == 1.0
    assert res["scores"]["cnp_leakage"]["leak_rate"] == 1.0
    assert res["scores"]["entity_f1"]["recall"] == 0.0


# --- Registry ----------------------------------------------------------------------------


def test_registry_exposes_all_countries_with_correct_families():
    assert supported_countries() == ["ES", "IT", "PL", "RO"]
    assert get_validator("ro").decode_bearing is True
    assert get_validator("PL").decode_bearing is True
    assert get_validator("it").decode_bearing is True
    assert get_validator("ES").decode_bearing is False
    assert get_validator("FR") is None
    # Unsupported country → invalid, no decode.
    assert parse_national_id("123", "FR").valid is False


# --- PL: PESEL (decode-bearing) ----------------------------------------------------------


def test_pesel_decodes_dob_and_sex():
    info = parse_national_id(PESEL_M_1944, "PL")
    assert info.valid and info.decode_bearing
    assert info.extra["sex"] == "M"
    assert info.extra["birth_date"] == "1944-05-14"
    assert info.disclosed_quasi_identifiers() == {"DATE_OF_BIRTH", "SEX"}


def test_pesel_century_from_month_offset_and_checksum_rejection():
    # 2000s births encode the century by +20 on the month field.
    info = parse_national_id("02211500029", "PL")  # 2002-01-15, female
    assert info.valid and info.extra["sex"] == "F"
    assert info.extra["birth_date"] == "2002-01-15"
    # Corrupt the checksum → invalid.
    assert not parse_national_id(PESEL_M_1944[:-1] + "8", "PL").valid


# --- IT: codice fiscale (decode-bearing, incl. place of birth) ---------------------------


def test_codice_fiscale_decodes_dob_sex_and_place():
    info = parse_national_id(CF_IT_M, "IT")
    assert info.valid and info.decode_bearing
    assert info.extra["sex"] == "M"
    assert info.extra["birth_month"] == 12 and info.extra["birth_day"] == 10
    assert info.extra["belfiore_code"] == "A562"
    assert info.disclosed_quasi_identifiers() == {"DATE_OF_BIRTH", "SEX", "PLACE_OF_BIRTH"}


def test_codice_fiscale_female_day_offset_and_control_letter_rejection():
    info = parse_national_id("RSSMRA85T50A562W", "IT")  # day 50 → female, day 10
    assert info.valid and info.extra["sex"] == "F" and info.extra["birth_day"] == 10
    # Corrupt the control letter → invalid.
    bad = CF_IT_M[:-1] + ("A" if CF_IT_M[-1] != "A" else "B")
    assert not parse_national_id(bad, "IT").valid


# --- ES: DNI/NIF (coverage-only — NEVER a re-id number) ----------------------------------


def test_dni_is_coverage_only_and_never_discloses_quasi_identifiers():
    info = parse_national_id(DNI_ES, "ES")
    assert info.valid
    assert info.decode_bearing is False
    # The whole point of coverage-only: a valid ES ID emits NO re-identification number.
    assert info.disclosed_quasi_identifiers() == set()
    assert info.quasi_identifiers == frozenset()
    # Wrong control letter → invalid.
    assert not parse_national_id("12345678A", "ES").valid


# --- national_id_leakage: country-dispatched ---------------------------------------------


def _single_id_rows(value: str, country: str, label: str = "NATIONAL_ID"):
    text = f"ID {value} x"  # tokens: ["ID", "<value>", "x"]
    span = {"start": 3, "end": 3 + len(value), "label": label, "country": country}
    return [{"text": text, "spans": [span]}]


def test_national_id_leakage_dispatches_per_country_decode_bearing():
    rows = _single_id_rows(CF_IT_M, "IT")
    missed = national_id_leakage(rows, [["O", "O", "O"]])
    assert missed["decode_bearing_total"] == 1.0 and missed["decode_bearing_missed"] == 1.0
    assert missed["leak_rate"] == 1.0
    assert missed["leaked_quasi_identifiers"] == 3.0  # DOB + SEX + PLACE_OF_BIRTH
    assert missed["it_total"] == 1.0 and missed["it_detected"] == 0.0

    caught = national_id_leakage(rows, [["O", "S-NATIONAL_ID", "O"]])
    assert caught["decode_bearing_detected"] == 1.0 and caught["leak_rate"] == 0.0
    assert caught["leaked_quasi_identifiers"] == 0.0


def test_national_id_leakage_coverage_only_never_emits_reid_number():
    rows = _single_id_rows(DNI_ES, "ES")
    # Even when MISSED, a coverage-only ID contributes ZERO quasi-identifiers and is not counted
    # in the decode-bearing re-id family — it never yields a re-identification number.
    missed = national_id_leakage(rows, [["O", "O", "O"]])
    assert missed["coverage_only_total"] == 1.0 and missed["coverage_only_detected"] == 0.0
    assert missed["decode_bearing_total"] == 0.0
    assert missed["leaked_quasi_identifiers"] == 0.0
    assert missed["es_total"] == 1.0


def test_national_id_leakage_emits_wilson_ci_over_decode_bearing():
    rows = _single_id_rows(PESEL_M_1944, "PL")
    res = national_id_leakage(rows, [["O", "O", "O"]])
    assert "leak_rate_ci_low" in res and "leak_rate_ci_high" in res
    assert res["leak_rate_ci_low"] <= res["leak_rate"] <= res["leak_rate_ci_high"]
    assert 0.0 <= res["leak_rate_ci_low"] and res["leak_rate_ci_high"] <= 1.0


def test_national_id_leakage_defaults_to_ro_when_country_absent():
    # Back-compat: a span with no country tag is validated as RO (legacy CNP behavior).
    cnp = _make_cnp("185071540001")
    rows = [{"text": f"CNP {cnp} emis", "spans": [{"start": 4, "end": 17, "label": "NATIONAL_ID"}]}]
    res = national_id_leakage(rows, [["O", "O", "O"]])
    assert res["decode_bearing_total"] == 1.0 and res["leak_rate"] == 1.0
    assert res["ro_total"] == 1.0


def test_cnp_leakage_alias_still_works_and_scopes_to_ro():
    cnp = _make_cnp("185071540001")
    rows = _single_id_rows(cnp, "RO")
    res = cnp_leakage(rows, [["O", "O", "O"]])
    # Historical cnp_* keys preserved verbatim.
    assert res["cnp_total"] == 1.0 and res["cnp_missed"] == 1.0
    assert res["leak_rate"] == 1.0
    assert res["leaked_quasi_identifiers"] == 3.0  # DOB + SEX + COUNTY
    assert "leak_rate_ci_low" in res and "leak_rate_ci_high" in res


# --- KLU-49: per-subject dedup (re-identification risk is per distinct subject) ----------
#
# Real RO clinical docs repeat the SAME CNP twice (the CNP field + the CASS "cod asigurat"
# field). Re-id risk is per distinct subject: the same value in one document is ONE subject,
# protected iff every occurrence is redacted and leaking iff ANY occurrence is missed.


def _ro_clinical_row(cnp: str) -> dict:
    """A doc that emits the same CNP twice, like the real RO clinical skeleton (CNP + CASS)."""
    text = f"CNP {cnp} asigurat {cnp} fin"  # tokens: CNP, <cnp>, asigurat, <cnp>, fin
    a = len("CNP ")
    b = len(f"CNP {cnp} asigurat ")
    return {
        "text": text,
        "spans": [
            {"start": a, "end": a + 13, "label": "NATIONAL_ID"},
            {"start": b, "end": b + 13, "label": "NATIONAL_ID"},
        ],
    }


def test_duplicate_cnp_in_one_doc_counts_as_one_subject():
    cnp = _make_cnp("185071540001")
    rows = [_ro_clinical_row(cnp)]
    # Both occurrences redacted → one subject, detected, no leak.
    both = national_id_leakage(rows, [["O", "S-NATIONAL_ID", "O", "S-NATIONAL_ID", "O"]])
    assert both["decode_bearing_total"] == 1.0   # ONE subject, not two spans
    assert both["decode_bearing_detected"] == 1.0
    assert both["decode_bearing_missed"] == 0.0
    assert both["leak_rate"] == 0.0
    assert both["leaked_quasi_identifiers"] == 0.0
    assert both["ro_total"] == 1.0 and both["ro_detected"] == 1.0


def test_subject_leaks_if_any_occurrence_missed():
    cnp = _make_cnp("185071540001")
    rows = [_ro_clinical_row(cnp)]
    # First occurrence redacted, the CASS one missed → subject leaks (ANY occurrence missed).
    one = national_id_leakage(rows, [["O", "S-NATIONAL_ID", "O", "O", "O"]])
    assert one["decode_bearing_total"] == 1.0
    assert one["decode_bearing_missed"] == 1.0
    assert one["leak_rate"] == 1.0
    # Quasi-identifiers counted ONCE per leaked subject (not once per missed span).
    assert one["leaked_quasi_identifiers"] == 3.0  # DOB + SEX + COUNTY


def test_distinct_cnps_in_one_doc_count_as_distinct_subjects():
    cnp1 = _make_cnp("185071540001")
    cnp2 = _make_cnp("605031120007")  # a different subject
    text = f"CNP {cnp1} si {cnp2} fin"  # tokens: CNP, <cnp1>, si, <cnp2>, fin
    a = len("CNP ")
    b = len(f"CNP {cnp1} si ")
    rows = [{"text": text, "spans": [
        {"start": a, "end": a + 13, "label": "NATIONAL_ID"},
        {"start": b, "end": b + 13, "label": "NATIONAL_ID"},
    ]}]
    res = national_id_leakage(rows, [["O", "O", "O", "O", "O"]])
    assert res["decode_bearing_total"] == 2.0  # two distinct values → two subjects
    assert res["decode_bearing_missed"] == 2.0


def test_same_cnp_in_different_docs_counts_as_two_subjects():
    # Dedup is scoped per-document: the same value across two docs is two subjects at risk.
    cnp = _make_cnp("185071540001")
    rows = [_single_id_rows(cnp, "RO")[0], _single_id_rows(cnp, "RO")[0]]
    res = national_id_leakage(rows, [["O", "O", "O"], ["O", "O", "O"]])
    assert res["decode_bearing_total"] == 2.0
    assert res["decode_bearing_missed"] == 2.0


def test_cnp_leakage_alias_dedups_duplicate_cnp():
    cnp = _make_cnp("185071540001")
    rows = [_ro_clinical_row(cnp)]
    res = cnp_leakage(rows, [["O", "O", "O", "O", "O"]])  # both occurrences missed
    assert res["cnp_total"] == 1.0   # ONE subject despite two spans
    assert res["cnp_missed"] == 1.0
    assert res["leak_rate"] == 1.0
    assert res["leaked_quasi_identifiers"] == 3.0  # counted once per subject


# --- Per-subject prediction dump (KLU-53: item-paired McNemar) ---------------------------------
# The dump must use the EXACT same per-subject (doc, country, value) unit as the leak metric so a
# McNemar pairing of two models' detected/leaked flags is consistent with the leaderboard leak-rate.


def test_subject_detection_dump_dedups_and_matches_metric():
    from europriv_bench.metrics import national_id_subject_detection

    cnp = _make_cnp("185071540001")
    rows = [_ro_clinical_row(cnp)]  # same CNP twice in one doc → ONE subject
    # First occurrence redacted, the CASS one missed → subject leaks (ANY occurrence missed).
    pred = [["O", "S-NATIONAL_ID", "O", "O", "O"]]
    subs = national_id_subject_detection(rows, pred)
    assert len(subs) == 1                       # deduped to one subject
    s = subs[0]
    assert s["doc"] == 0 and s["country"] == "RO" and s["value"] == cnp
    assert s["decode_bearing"] is True
    assert s["detected"] is False               # leaked (consistent with leak_rate==1.0)
    # And it agrees with the metric on the same input.
    assert national_id_leakage(rows, pred)["leak_rate"] == 1.0


def test_subject_detection_dump_keys_align_across_models():
    from europriv_bench.metrics import national_id_subject_detection

    cnp1 = _make_cnp("185071540001")
    cnp2 = _make_cnp("605031120007")
    text = f"CNP {cnp1} si {cnp2} fin"
    a = len("CNP ")
    b = len(f"CNP {cnp1} si ")
    rows = [{"text": text, "spans": [
        {"start": a, "end": a + 13, "label": "NATIONAL_ID"},
        {"start": b, "end": b + 13, "label": "NATIONAL_ID"},
    ]}]
    # Model A detects neither; model B detects only the first → keys identical, flags differ.
    a_subs = national_id_subject_detection(rows, [["O", "O", "O", "O", "O"]])
    b_subs = national_id_subject_detection(rows, [["O", "S-NATIONAL_ID", "O", "O", "O"]])

    def keys(ss):
        return [(s["doc"], s["country"], s["value"]) for s in ss]

    assert keys(a_subs) == keys(b_subs)          # gold-derived keys align row-for-row
    assert [s["detected"] for s in a_subs] == [False, False]
    assert [s["detected"] for s in b_subs] == [True, False]


def test_run_spec_emits_dump_when_sink_provided():
    cnp = _make_cnp("185071540001")
    rows = [{"text": f"CNP {cnp} emis", "spans": [{"start": 4, "end": 17, "label": "NATIONAL_ID"}]}]
    spec = EvalSpec.model_validate({
        "name": "ro-test", "task": "detection", "languages": ["ro"],
        "dataset": {"hf_id": "x", "config": "ro-realskeleton-v1", "split": "test"},
        "metrics": ["entity_f1", "cnp_leakage"],
    })
    dumps: list[dict] = []
    run_spec(spec, build("dummy"), rows=rows, dumps=dumps)
    assert len(dumps) == 1
    d = dumps[0]
    assert d["adapter"] == "dummy" and d["dataset"]["config"] == "ro-realskeleton-v1"
    assert len(d["subjects"]) == 1
    assert d["subjects"][0]["detected"] is False   # dummy predicts all-O → leak


def test_run_spec_no_dump_without_sink():
    # Back-compat: callers that don't pass dumps= get the unchanged single-dict return.
    cnp = _make_cnp("185071540001")
    rows = [{"text": f"CNP {cnp} emis", "spans": [{"start": 4, "end": 17, "label": "NATIONAL_ID"}]}]
    spec = EvalSpec.model_validate({
        "name": "ro-test", "task": "detection", "languages": ["ro"],
        "dataset": {"hf_id": "x", "config": "ro", "split": "test"},
        "metrics": ["cnp_leakage"],
    })
    res = run_spec(spec, build("dummy"), rows=rows)
    assert "scores" in res  # plain dict, no crash
