"""Romanian CNP validation/decode + the cnp_leakage re-identification metric."""

from europriv_bench.metrics import cnp_leakage
from europriv_bench.national_id import check_digit, parse_cnp, validate_cnp


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
