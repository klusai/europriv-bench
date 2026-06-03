"""KLU-118 v1 — name-in-context residual leak + k-anonymity-violation diagnostic.

Covers the second (non-token) re-identification channel and its claim-language / unit-shape parity
with the national-ID anchor, the 2x2 cross-tab, and the k-anon skip-and-report. All offline (no
model backends, no HF) — the metric is fed gold rows + BIOES prediction tags directly.
"""

from __future__ import annotations

from europriv_bench.metrics import (
    ROW_REGISTRY,
    k_anonymity_violation,
    name_in_context_leakage,
)
from europriv_bench.national_id import check_digit
from europriv_bench.runner import run_spec
from europriv_bench.spans import char_spans_to_bioes
from europriv_bench.spec import DatasetRef, EvalSpec, Task


def _make_cnp(base12: str) -> str:
    return base12 + str(check_digit(base12))


CNP = _make_cnp("185071540001")  # valid RO CNP → decode-bearing anchor


def _pred_for(row: dict, detect: set[str]) -> list[str]:
    """Prediction tags: detect (mark non-O) every span whose label is in ``detect``, else all O."""
    spans = [s for s in row["spans"] if s["label"] in detect]
    if not spans:
        from europriv_bench.spans import whitespace_tokens

        return ["O"] * len(whitespace_tokens(row["text"]))
    from europriv_bench.spans import Span

    return char_spans_to_bioes(row["text"], [Span(s["start"], s["end"], s["label"]) for s in spans])


def _ro_row(text: str, spans: list[dict]) -> dict:
    return {"text": text, "country": "RO", "spans": spans}


# --------------------------------------------------------------------------- #
# name_in_context_leakage — per-subject residual leak
# --------------------------------------------------------------------------- #
def test_name_leak_when_name_unredacted_on_residual():
    text = "Pacient Ion Popescu"
    row = _ro_row(text, [{"start": 8, "end": 19, "label": "PERSON"}])
    pred = _pred_for(row, detect=set())  # nothing redacted → name survives
    res = name_in_context_leakage([row], [pred])
    assert res["name_subjects_total"] == 1.0
    assert res["name_subjects_leaked"] == 1.0
    assert res["name_leak_rate"] == 1.0
    assert res["name_leak_rate_ci_low"] <= 1.0 <= res["name_leak_rate_ci_high"] + 1e-9


def test_no_name_leak_when_name_redacted():
    text = "Pacient Ion Popescu"
    row = _ro_row(text, [{"start": 8, "end": 19, "label": "PERSON"}])
    pred = _pred_for(row, detect={"PERSON"})  # name redacted → no leak
    res = name_in_context_leakage([row], [pred])
    assert res["name_subjects_leaked"] == 0.0
    assert res["name_leak_rate"] == 0.0


def test_name_subject_dedup_repeated_name_is_one_subject():
    # Same name twice in one doc → one subject (KLU-49 per-subject parity with the anchor).
    text = "Medic Ion Popescu ... pacient Ion Popescu"
    s1 = text.index("Ion Popescu")
    s2 = text.index("Ion Popescu", s1 + 1)
    row = _ro_row(text, [
        {"start": s1, "end": s1 + 11, "label": "PERSON"},
        {"start": s2, "end": s2 + 11, "label": "PERSON"},
    ])
    pred = _pred_for(row, detect=set())
    res = name_in_context_leakage([row], [pred])
    assert res["name_subjects_total"] == 1.0  # deduped to one subject


def test_name_leaks_iff_any_occurrence_survives():
    # One occurrence redacted, the other not → the subject still leaks (ANY occurrence un-redacted).
    text = "Ion Popescu si din nou Ion Popescu"
    s1 = text.index("Ion Popescu")
    s2 = text.index("Ion Popescu", s1 + 1)
    row = _ro_row(text, [
        {"start": s1, "end": s1 + 11, "label": "PERSON"},
        {"start": s2, "end": s2 + 11, "label": "PERSON"},
    ])
    from europriv_bench.spans import Span

    # Redact only the FIRST occurrence.
    pred = char_spans_to_bioes(text, [Span(s1, s1 + 11, "PERSON")])
    res = name_in_context_leakage([row], [pred])
    assert res["name_subjects_leaked"] == 1.0  # second occurrence survived → leak


def test_distinct_names_are_distinct_subjects():
    text = "Dr. Bogdan Radu trateaza pe Elena Ionescu"
    b = text.index("Bogdan Radu")
    e = text.index("Elena Ionescu")
    row = _ro_row(text, [
        {"start": b, "end": b + 11, "label": "PERSON"},
        {"start": e, "end": e + 13, "label": "PERSON"},
    ])
    pred = _pred_for(row, detect=set())
    res = name_in_context_leakage([row], [pred])
    assert res["name_subjects_total"] == 2.0
    assert res["name_subjects_leaked"] == 2.0


def test_only_person_spans_count_not_other_types():
    text = "CNP 123 are diagnostic gripa"
    row = _ro_row(text, [
        {"start": 12, "end": 22, "label": "HEALTH_CONDITION"},
        {"start": 23, "end": 28, "label": "DATE"},
    ])
    pred = _pred_for(row, detect=set())
    res = name_in_context_leakage([row], [pred])
    assert res["name_subjects_total"] == 0.0  # no PERSON spans → no name subjects


# --------------------------------------------------------------------------- #
# 2x2 cross-tab vs the national-ID anchor (channel independence)
# --------------------------------------------------------------------------- #
def _doc_both_channels(detect: set[str]) -> dict:
    text = f"Pacient Ion Popescu CNP {CNP}"
    p = text.index("Ion Popescu")
    c = text.index(CNP)
    row = _ro_row(text, [
        {"start": p, "end": p + 11, "label": "PERSON"},
        {"start": c, "end": c + len(CNP), "label": "NATIONAL_ID"},
    ])
    return {"row": row, "pred": _pred_for(row, detect=detect)}


def test_xtab_both_leaked():
    d = _doc_both_channels(detect=set())  # neither redacted → both channels leak
    res = name_in_context_leakage([d["row"]], [d["pred"]])
    assert res["xtab_docs"] == 1.0
    assert res["xtab_both_leaked"] == 1.0


def test_xtab_name_only_leaked_when_id_redacted():
    d = _doc_both_channels(detect={"NATIONAL_ID"})  # ID redacted, name survives
    res = name_in_context_leakage([d["row"]], [d["pred"]])
    assert res["xtab_name_only_leaked"] == 1.0
    assert res["xtab_both_leaked"] == 0.0


def test_xtab_id_only_leaked_when_name_redacted():
    d = _doc_both_channels(detect={"PERSON"})  # name redacted, ID survives
    res = name_in_context_leakage([d["row"]], [d["pred"]])
    assert res["xtab_id_only_leaked"] == 1.0


def test_xtab_neither_when_both_redacted():
    d = _doc_both_channels(detect={"PERSON", "NATIONAL_ID"})
    res = name_in_context_leakage([d["row"]], [d["pred"]])
    assert res["xtab_neither_leaked"] == 1.0


def test_xtab_only_counts_docs_with_both_channels():
    # A name-only doc (no national ID) must NOT enter the cross-tab.
    text = "Pacient Ion Popescu"
    row = _ro_row(text, [{"start": 8, "end": 19, "label": "PERSON"}])
    pred = _pred_for(row, detect=set())
    res = name_in_context_leakage([row], [pred])
    assert res["name_subjects_leaked"] == 1.0
    assert res["xtab_docs"] == 0.0  # no national-ID channel → excluded from the cross-tab


# --------------------------------------------------------------------------- #
# k_anonymity_violation — skip-and-report on today's gold; computes when QIs exist
# --------------------------------------------------------------------------- #
def test_kanon_skip_and_reports_when_gold_lacks_qi_tuples():
    rows = [_ro_row("Pacient Ion Popescu", [{"start": 8, "end": 19, "label": "PERSON"}])]
    res = k_anonymity_violation(rows)
    assert res["available"] is False
    assert "QI diagnostic unavailable" in res["reason"]
    assert res["label"] == "sample distinctiveness, not population re-identification"
    # No fabricated QI numbers leak out.
    assert "k1_violation_rate" not in res


def test_kanon_computes_distribution_when_qi_tuples_present():
    # Two subjects share one QI tuple (a class of size 2); one is unique (k=1).
    rows = [
        {"text": "a", "spans": [], "qi_tuple": {"sex": "M", "age_band": "30-34"}},
        {"text": "b", "spans": [], "qi_tuple": {"sex": "M", "age_band": "30-34"}},
        {"text": "c", "spans": [], "qi_tuple": {"sex": "F", "age_band": "60-64"}},
    ]
    res = k_anonymity_violation(rows)
    assert res["available"] is True
    assert res["n_subjects"] == 3
    assert res["n_equivalence_classes"] == 2
    assert res["equivalence_class_size_histogram"] == {1: 1, 2: 1}
    assert abs(res["k1_violation_rate"] - (1 / 3)) < 1e-9
    assert res["klt5_violation_rate"] == 1.0  # all classes have size < 5
    assert res["label"] == "sample distinctiveness, not population re-identification"


def test_kanon_never_emits_a_single_headline_scalar():
    rows = [{"text": "a", "spans": [], "qi_tuple": {"sex": "M"}}]
    res = k_anonymity_violation(rows)
    # The required distribution is present (not just one number).
    assert "equivalence_class_size_histogram" in res


# --------------------------------------------------------------------------- #
# Registry + runner wiring
# --------------------------------------------------------------------------- #
def test_metrics_registered_as_row_metrics():
    assert "name_in_context_leakage" in ROW_REGISTRY
    assert "k_anonymity_violation" in ROW_REGISTRY


def test_runner_wires_name_channel_on_detection_track():
    text = f"Pacient Ion Popescu CNP {CNP}"
    p = text.index("Ion Popescu")
    c = text.index(CNP)
    rows = [_ro_row(text, [
        {"start": p, "end": p + 11, "label": "PERSON"},
        {"start": c, "end": c + len(CNP), "label": "NATIONAL_ID"},
    ])]
    spec = EvalSpec(
        name="qi", task=Task.DETECTION, languages=["ro"], domain="legal",
        dataset=DatasetRef(hf_id="x", config="ro-realskeleton-v1"),
        metrics=["entity_f1", "national_id_leakage", "name_in_context_leakage",
                 "k_anonymity_violation"],
    )

    from europriv_bench.adapters import BaseAdapter

    class _NullDetector(BaseAdapter):
        name = "null"
        model_id = "null"

        def predict_tags(self, texts):
            from europriv_bench.spans import whitespace_tokens

            return [["O"] * len(whitespace_tokens(t)) for t in texts]

    res = run_spec(spec, _NullDetector(), rows=rows)
    assert res["config_status"] == "dev"
    scores = res["scores"]
    # Null detector redacts nothing → both channels leak.
    assert scores["name_in_context_leakage"]["name_leak_rate"] == 1.0
    assert scores["name_in_context_leakage"]["xtab_both_leaked"] == 1.0
    assert scores["national_id_leakage"]["leak_rate"] == 1.0
    # k-anon skip-and-reports on this (QI-less) gold.
    assert scores["k_anonymity_violation"]["available"] is False
