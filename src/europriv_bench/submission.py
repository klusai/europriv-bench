"""Submission tooling — validate a third-party model card and check the reproduction gate.

This is the importable core behind the submission CI (KLU-16). The GitHub Actions workflow
(`.github/workflows/submission.yml`) shells out to the ``europriv submission ...`` commands
defined in ``main.py``; the same functions are exercised offline by the test suite and by
``make submission-check`` so the reproduction gate is verifiable without running CI.

Two responsibilities:

  * **Model-card validation** — a submission PR carries a filled model card (YAML). We assert
    the required fields are present and well-formed, including the contamination statement and a
    declared ``adapter`` that is one of ``adapters.BUILDERS``. No submitter code is trusted: the
    harness only ever instantiates a *built-in* adapter keyed by this declared scheme.
  * **Reproduction gate** — re-check a committed anchor result against ``leaderboard.json`` within
    a tolerance band. The anchor is privacy-filter English entity-F1 (taxonomy 0.2.0, n=1500,
    eval-label-fair mask): committed exactly at 0.4149, gate passes inside ±0.02, fails outside.
    This guards against silent drift in the harness, crosswalk, or committed baseline.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .adapters import BUILDERS

# --- Reproduction gate anchor ------------------------------------------------------------------
# privacy-filter / openai/privacy-filter on the public English config: the single number the
# gate reproduces. See leaderboard.json (privacy-filter::openai/privacy-filter, config "en").
REPRO_ADAPTER = "privacy-filter"
REPRO_MODEL_ID = "openai/privacy-filter"
REPRO_CONFIG = "en"
REPRO_TAXONOMY_VERSION = "0.2.0"
REPRO_N = 1500
REPRO_EXPECTED_F1 = 0.415  # documented anchor; committed value is 0.4149...
REPRO_TOLERANCE = 0.02

# Model-card required fields. A submission PR must fill every one of these.
REQUIRED_CARD_FIELDS = (
    # Public, version-pinned model/tool reference. For an HF model this is the revision-pinned id
    # ``org/model@<sha>``; for a non-HF orchestration tool (e.g. Presidio) it is the package pinned
    # to a release, ``org/tool@<version>``. Either way the ``@`` pins an immutable version so a row
    # stamps exactly what produced the score. (Field key kept as ``hf_model_id`` for compatibility.)
    "hf_model_id",
    "adapter",          # one of adapters.BUILDERS — the built-in scheme the harness calls
    "intended_use",
    "training_data",    # provenance + licensing of the training data
    "languages",        # ISO codes covered
    "domains",          # general | legal | clinical | ...
    "known_limitations",
    "contamination_statement",  # overlap (or not) with the held-out gold splits
)


class CardValidationError(ValueError):
    """Raised when a submitted model card is missing or malformed."""


def validate_model_card(card: dict) -> dict:
    """Validate a parsed model-card dict; return it unchanged on success.

    Enforces: every ``REQUIRED_CARD_FIELDS`` present and non-empty, the declared ``adapter`` is a
    known built-in (``adapters.BUILDERS``), and the HF id is revision-pinned (``@`` present) so a
    row stamps an immutable model revision rather than a moving tag.
    """
    if not isinstance(card, dict):
        raise CardValidationError("model card must be a mapping (YAML object)")

    missing = [f for f in REQUIRED_CARD_FIELDS if not card.get(f)]
    if missing:
        raise CardValidationError(f"model card missing required field(s): {', '.join(missing)}")

    adapter = card["adapter"]
    if adapter not in BUILDERS:
        raise CardValidationError(
            f"adapter {adapter!r} is not a built-in scheme; one of: {sorted(BUILDERS)}"
        )

    hf_id = str(card["hf_model_id"])
    if "@" not in hf_id:
        raise CardValidationError(
            f"hf_model_id {hf_id!r} must pin a version (HF model: org/model@<sha>; "
            f"non-HF tool: org/tool@<version>), not a moving tag"
        )

    return card


def validate_model_card_file(path: str | Path) -> dict:
    """Load and validate a model-card YAML file."""
    path = Path(path)
    if not path.exists():
        raise CardValidationError(f"model card not found: {path}")
    card = yaml.safe_load(path.read_text(encoding="utf-8"))
    return validate_model_card(card)


# --- Reproduction gate -------------------------------------------------------------------------


def _find_anchor_row(leaderboard: dict) -> dict:
    """Locate the privacy-filter English row in a leaderboard dict, or raise."""
    key = f"{REPRO_ADAPTER}::{REPRO_MODEL_ID}"
    rows = leaderboard.get("entries", {}).get(key)
    if not rows:
        raise CardValidationError(f"reproduction anchor entry {key!r} absent from leaderboard")
    for r in rows:
        if (r.get("dataset") or {}).get("config") == REPRO_CONFIG:
            return r
    raise CardValidationError(f"reproduction anchor config {REPRO_CONFIG!r} absent under {key!r}")


def check_reproduction(leaderboard: dict, tolerance: float = REPRO_TOLERANCE) -> tuple[bool, str]:
    """Check the committed anchor row reproduces the expected F1 within ``tolerance``.

    Returns ``(ok, message)``. ``ok`` is True iff the row's entity_f1 is within ``±tolerance`` of
    ``REPRO_EXPECTED_F1`` *and* the row's provenance (taxonomy version, n) matches the anchor —
    a drift in either pins or score fails the gate.
    """
    row = _find_anchor_row(leaderboard)
    f1 = (row.get("scores", {}).get("entity_f1") or {}).get("f1")
    if f1 is None:
        return False, "anchor row has no entity_f1 score"

    tax = row.get("taxonomy_version")
    if tax != REPRO_TAXONOMY_VERSION:
        return False, f"taxonomy_version drift: expected {REPRO_TAXONOMY_VERSION!r}, got {tax!r}"

    n = row.get("n")
    if n != REPRO_N:
        return False, f"n drift: expected {REPRO_N}, got {n}"

    delta = abs(f1 - REPRO_EXPECTED_F1)
    ok = delta <= tolerance
    band = f"{REPRO_EXPECTED_F1} ±{tolerance}"
    verdict = "PASS" if ok else "FAIL"
    return ok, (
        f"[{verdict}] {REPRO_ADAPTER}::{REPRO_MODEL_ID} ({REPRO_CONFIG}) "
        f"entity_f1={f1:.4f} vs {band} (|Δ|={delta:.4f})"
    )


def check_reproduction_file(
    path: str | Path = "baselines/leaderboard.json", tolerance: float = REPRO_TOLERANCE
) -> tuple[bool, str]:
    """Run the reproduction gate against a committed leaderboard JSON file."""
    lb = json.loads(Path(path).read_text(encoding="utf-8"))
    return check_reproduction(lb, tolerance=tolerance)
