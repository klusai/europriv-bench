"""Tests for the submission CI core (KLU-16): model-card validation + reproduction gate.

These run offline (no model download, no network) so ``make check`` validates the reproduction
gate against the committed ``baselines/leaderboard.json`` without invoking GitHub Actions.
"""

import json
from pathlib import Path

import pytest

from europriv_bench.submission import (
    REPRO_ADAPTER,
    REPRO_EXPECTED_F1,
    REPRO_MODEL_ID,
    CardValidationError,
    check_reproduction,
    check_reproduction_file,
    validate_model_card,
)

ROOT = Path(__file__).resolve().parents[1]


def _good_card() -> dict:
    return {
        "hf_model_id": "org/model@0123456789abcdef0123456789abcdef01234567",
        "adapter": "privacy-filter",
        "intended_use": "PII detection over EU general text.",
        "training_data": "Some open corpus, CC-BY-4.0.",
        "languages": ["en", "de"],
        "domains": ["general"],
        "known_limitations": "Weak on legal domain.",
        "contamination_statement": "No overlap with the held-out gold splits.",
    }


# --- model-card validation ---------------------------------------------------------------------


def test_valid_card_passes():
    assert validate_model_card(_good_card())["adapter"] == "privacy-filter"


@pytest.mark.parametrize("field", [
    "hf_model_id", "adapter", "intended_use", "training_data",
    "languages", "domains", "known_limitations", "contamination_statement",
])
def test_missing_required_field_fails(field):
    card = _good_card()
    del card[field]
    with pytest.raises(CardValidationError, match="missing required"):
        validate_model_card(card)


def test_unknown_adapter_rejected():
    card = _good_card()
    card["adapter"] = "definitely-not-a-builtin"
    with pytest.raises(CardValidationError, match="not a built-in"):
        validate_model_card(card)


def test_unpinned_revision_rejected():
    card = _good_card()
    card["hf_model_id"] = "org/model"  # no @<sha>
    with pytest.raises(CardValidationError, match="pin a revision"):
        validate_model_card(card)


def test_shipped_template_card_validates():
    """The model-card stub shipped in .github/ must itself pass validation (a working example)."""
    from europriv_bench.submission import validate_model_card_file

    path = ROOT / ".github" / "MODEL_CARD_TEMPLATE.yaml"
    assert validate_model_card_file(path)["adapter"] in {
        "privacy-filter", "openmed", "tabularisai", "gliner", "kp-model", "dummy",
    }


# --- reproduction gate -------------------------------------------------------------------------


def _lb_with_f1(f1: float, *, n: int = 1500, tax: str = "0.2.0") -> dict:
    return {
        "schema": 3,
        "entries": {
            f"{REPRO_ADAPTER}::{REPRO_MODEL_ID}": [
                {"spec": "PII Detection — English (general)", "n": n, "taxonomy_version": tax,
                 "dataset": {"config": "en"}, "scores": {"entity_f1": {"f1": f1}}}
            ]
        },
    }


def test_gate_passes_at_committed_anchor():
    ok, msg = check_reproduction(_lb_with_f1(0.4149))
    assert ok, msg


def test_gate_passes_inside_band():
    assert check_reproduction(_lb_with_f1(REPRO_EXPECTED_F1 + 0.019))[0]
    assert check_reproduction(_lb_with_f1(REPRO_EXPECTED_F1 - 0.019))[0]


def test_gate_fails_outside_band():
    ok, msg = check_reproduction(_lb_with_f1(REPRO_EXPECTED_F1 + 0.05))
    assert not ok and "FAIL" in msg


def test_gate_fails_on_taxonomy_drift():
    ok, msg = check_reproduction(_lb_with_f1(0.4149, tax="0.3.0"))
    assert not ok and "taxonomy_version drift" in msg


def test_gate_fails_on_n_drift():
    ok, msg = check_reproduction(_lb_with_f1(0.4149, n=100))
    assert not ok and "n drift" in msg


def test_gate_against_committed_leaderboard_passes():
    """The real committed baseline must pass the gate — this is the offline CI-equivalent."""
    ok, msg = check_reproduction_file(ROOT / "baselines" / "leaderboard.json")
    assert ok, msg
    # Cross-check: the committed value really is ~0.4149.
    lb = json.loads((ROOT / "baselines" / "leaderboard.json").read_text())
    f1 = lb["entries"][f"{REPRO_ADAPTER}::{REPRO_MODEL_ID}"]
    f1 = next(r for r in f1 if r["dataset"]["config"] == "en")["scores"]["entity_f1"]["f1"]
    assert abs(f1 - 0.4149) < 1e-3
