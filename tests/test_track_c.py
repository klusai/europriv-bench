"""KLU-104 — Track C (anonymization + downstream-utility) scaffolding.

Covers the four code-computed metrics, the redaction-baseline adapter seam, and that the runner
lifts NotImplementedError for ANONYMIZATION ONLY (DETECTION unchanged; CLASSIFICATION/LEAKAGE still
raise). All offline — no model backends, no HF.
"""

from __future__ import annotations

import pytest

from europriv_bench.adapters import MASK_TOKEN, BaseAdapter, _mask_spans
from europriv_bench.metrics import (
    information_retention,
    pseudonymization_consistency,
    redaction_leakage,
    structural_disruption,
)
from europriv_bench.national_id import check_digit
from europriv_bench.runner import run_spec
from europriv_bench.spec import DatasetRef, EvalSpec, Task


def _make_cnp(base12: str) -> str:
    return base12 + str(check_digit(base12))


CNP = _make_cnp("185071540001")  # valid RO CNP → DOB+SEX+COUNTY (3 QIs)
CNP2 = _make_cnp("605031120007")  # a second valid CNP


def _ro_row(text: str, spans: list[dict]) -> dict:
    return {"text": text, "country": "RO", "spans": spans}


# --------------------------------------------------------------------------- #
# redaction_leakage — computed from gold offsets vs the redacted output
# --------------------------------------------------------------------------- #
def test_redaction_leak_zero_when_value_fully_masked():
    text = f"CNP {CNP} aici"
    rows = [_ro_row(text, [{"start": 4, "end": 4 + len(CNP), "label": "NATIONAL_ID"}])]
    redacted = [f"CNP {MASK_TOKEN} aici"]
    res = redaction_leakage(rows, redacted)
    assert res["subjects_total"] == 1.0
    assert res["subjects_leaked"] == 0.0
    assert res["leak_rate"] == 0.0
    assert res["leaked_quasi_identifiers"] == 0.0


def test_redaction_leak_when_value_survives_verbatim():
    text = f"CNP {CNP} aici"
    rows = [_ro_row(text, [{"start": 4, "end": 4 + len(CNP), "label": "NATIONAL_ID"}])]
    redacted = [text]  # nothing masked → full survival
    res = redaction_leakage(rows, redacted)
    assert res["subjects_leaked"] == 1.0
    assert res["leak_rate"] == 1.0
    assert res["leaked_quasi_identifiers"] == 3.0  # DOB+SEX+COUNTY
    assert res["leak_rate_ci_low"] <= 1.0 <= res["leak_rate_ci_high"] + 1e-9


def test_partial_redaction_last4_is_a_leak():
    # Mask all but the last 4 digits — a partial redaction that still re-identifies → LEAK.
    text = f"CNP {CNP}."
    rows = [_ro_row(text, [{"start": 4, "end": 4 + len(CNP), "label": "NATIONAL_ID"}])]
    redacted = [f"CNP {MASK_TOKEN}{CNP[-4:]}."]
    res = redaction_leakage(rows, redacted)
    assert res["subjects_leaked"] == 1.0
    assert res["leak_rate"] == 1.0


def test_per_subject_dedup_repeated_cnp_is_one_subject():
    # Same CNP twice in one doc (CNP field + CASS field) → one subject (KLU-49).
    text = f"CNP {CNP} ... cod {CNP}"
    rows = [_ro_row(text, [
        {"start": 4, "end": 4 + len(CNP), "label": "NATIONAL_ID"},
        {"start": text.index(CNP, 5), "end": text.index(CNP, 5) + len(CNP), "label": "NATIONAL_ID"},
    ])]
    res = redaction_leakage(rows, [text])
    assert res["subjects_total"] == 1.0  # deduped


def test_leak_computed_from_gold_not_a_redetect():
    # The output contains an UNRELATED valid-looking CNP, but the gold value WAS masked → no leak.
    # Proves the metric reads the gold value, not whatever a detector would find in the output.
    text = f"CNP {CNP}"
    rows = [_ro_row(text, [{"start": 4, "end": 4 + len(CNP), "label": "NATIONAL_ID"}])]
    redacted = [f"CNP {MASK_TOKEN} (alt {CNP2})"]
    res = redaction_leakage(rows, redacted)
    assert res["subjects_leaked"] == 0.0  # gold CNP masked → no leak despite CNP2 in output


# --------------------------------------------------------------------------- #
# pseudonymization_consistency — bijection rate
# --------------------------------------------------------------------------- #
def test_bijection_perfect():
    maps = [{"Ion Popescu": "PERSON_1", "Maria": "PERSON_2"},
            {"Ion Popescu": "PERSON_1"}]
    res = pseudonymization_consistency([{}, {}], maps)
    assert res["in_doc_bijection_rate"] == 1.0
    assert res["cross_doc_bijection_rate"] == 1.0


def test_bijection_breaks_when_one_entity_gets_two_surrogates_cross_doc():
    # "Ion" → PERSON_1 in doc1 but PERSON_9 in doc2: cross-doc not injective on the source.
    maps = [{"Ion": "PERSON_1"}, {"Ion": "PERSON_9"}]
    res = pseudonymization_consistency([{}, {}], maps)
    assert res["cross_doc_bijection_rate"] == 0.0
    assert res["in_doc_bijection_rate"] == 1.0  # each doc is internally consistent


def test_bijection_breaks_on_surrogate_collision():
    # Two distinct entities collapse onto ONE surrogate → not injective on the target.
    maps = [{"Ion": "X", "Maria": "X"}]
    res = pseudonymization_consistency([{}], maps)
    assert res["in_doc_bijection_rate"] == 0.0


def test_bijection_empty_is_one():
    res = pseudonymization_consistency([], [])
    assert res["in_doc_bijection_rate"] == 1.0
    assert res["cross_doc_bijection_rate"] == 1.0


# --------------------------------------------------------------------------- #
# information_retention — non-PII tokens preserved
# --------------------------------------------------------------------------- #
def test_information_retention_full_when_only_pii_masked():
    text = "Pacientul Ion Popescu are febra"
    rows = [{"text": text, "spans": [{"start": 10, "end": 21, "label": "PERSON"}]}]  # "Ion Popescu"
    redacted = [f"Pacientul {MASK_TOKEN} are febra"]
    res = information_retention(rows, redacted)
    # 3 non-PII tokens: Pacientul, are, febra — all retained.
    assert res["non_pii_tokens"] == 3.0
    assert res["information_retention"] == 1.0
    assert res["is_proxy"] == 1.0


def test_information_retention_drops_when_context_rewritten():
    text = "Pacientul Ion are febra"
    rows = [{"text": text, "spans": [{"start": 10, "end": 13, "label": "PERSON"}]}]  # "Ion"
    redacted = [f"{MASK_TOKEN}"]  # everything dropped
    res = information_retention(rows, redacted)
    assert res["information_retention"] == 0.0  # no non-PII token survived


# --------------------------------------------------------------------------- #
# structural_disruption — language-neutral
# --------------------------------------------------------------------------- #
def test_structural_disruption_counts_masks():
    rows = [{"text": "a b c d", "spans": []}]
    redacted = [f"a {MASK_TOKEN} c {MASK_TOKEN}"]
    res = structural_disruption(rows, redacted)
    assert res["mask_tokens"] == 2.0
    assert res["output_tokens"] == 4.0
    assert res["mask_token_ratio"] == 0.5
    assert res["length_delta_ratio"] == 0.0  # same token count
    assert res["is_proxy"] == 1.0


def test_structural_disruption_zero_when_unchanged():
    rows = [{"text": "a b c", "spans": []}]
    res = structural_disruption(rows, ["a b c"])
    assert res["mask_token_ratio"] == 0.0
    assert res["length_delta_ratio"] == 0.0


# --------------------------------------------------------------------------- #
# _mask_spans helper
# --------------------------------------------------------------------------- #
def test_mask_spans_merges_overlapping_and_preserves_context():
    text = "hello world foo"
    out = _mask_spans(text, [(0, 5), (6, 11)])
    assert out == f"{MASK_TOKEN} {MASK_TOKEN} foo"


def test_mask_spans_empty_is_identity():
    assert _mask_spans("abc", []) == "abc"


# --------------------------------------------------------------------------- #
# Redaction-baseline adapter seam (default anonymize/pseudonymize on BaseAdapter)
# --------------------------------------------------------------------------- #
class _StubDetector(BaseAdapter):
    """Detects only the literal token 'Ion' as PERSON (a deliberately leaky redactor)."""

    name = "stub"
    model_id = "stub"

    def predict_tags(self, texts):
        out = []
        for t in texts:
            out.append(["S-PERSON" if tok == "Ion" else "O" for tok in t.split()])
        return out


def test_default_anonymize_masks_detected_spans():
    a = _StubDetector()
    red = a.anonymize(["Ion Popescu vine"])
    assert red == [f"{MASK_TOKEN} Popescu vine"]  # only the detected token masked


def test_default_pseudonymize_stable_surrogate():
    a = _StubDetector()
    maps = a.pseudonymize(["Ion vine", "Ion pleaca"])
    assert maps[0]["Ion"] == maps[1]["Ion"]  # same surrogate across docs (cross-doc consistent)


# --------------------------------------------------------------------------- #
# Runner gating: ANONYMIZATION lifted; DETECTION unchanged; others still raise
# --------------------------------------------------------------------------- #
def _spec(task: Task, metrics: list[str]) -> EvalSpec:
    return EvalSpec(name="t", task=task, languages=["ro"], domain="legal",
                    dataset=DatasetRef(hf_id="x", config="ro-realskeleton-v1"), metrics=metrics)


def test_runner_runs_anonymization_track_end_to_end():
    rows = [_ro_row(f"Pacientul Ion are CNP {CNP}",
                    [{"start": 10, "end": 13, "label": "PERSON"},
                     {"start": 22, "end": 22 + len(CNP), "label": "NATIONAL_ID"}])]
    spec = _spec(Task.ANONYMIZATION,
                 ["redaction_leakage", "pseudonymization_consistency",
                  "information_retention", "structural_disruption"])
    res = run_spec(spec, _StubDetector(), rows=rows)
    assert res["task"] == "anonymization"
    assert res["config_status"] == "dev"  # Track C launches dev-only
    # Stub misses the CNP → it survives → leak; detection recall reported separately.
    assert res["scores"]["redaction_leakage"]["leak_rate"] == 1.0
    assert "detection_recall" in res["scores"]
    assert set(res["scores"]) >= {
        "redaction_leakage", "pseudonymization_consistency",
        "information_retention", "structural_disruption", "detection_recall",
    }


def test_runner_detection_still_works_unchanged():
    rows = [_ro_row("Ion vine", [{"start": 0, "end": 3, "label": "PERSON"}])]
    res = run_spec(_spec(Task.DETECTION, ["entity_f1"]), _StubDetector(), rows=rows)
    assert res["task"] == "detection"
    assert res["scores"]["entity_f1"]["recall"] == 1.0


def test_runner_other_tasks_still_raise():
    for task in (Task.CLASSIFICATION, Task.LEAKAGE):
        with pytest.raises(NotImplementedError):
            run_spec(_spec(task, []), _StubDetector(),
                     gold=(["x"], [["O"]]))


def test_anonymization_needs_rows():
    spec = _spec(Task.ANONYMIZATION, ["redaction_leakage"])
    with pytest.raises(ValueError):
        run_spec(spec, _StubDetector(), gold=(["x"], [["O"]]))
