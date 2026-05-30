"""Metrics for EuroPriv-Bench.

Two families:
  * **Detection** — entity/token-level P/R/F1 (seqeval, strict BIOES). De-identification is
    recall-sensitive, so we also expose F2 (recall-weighted).
  * **Privacy & utility** — re-identification risk, PII-replay, membership-inference success,
    and utility-after-redaction. These are the *headline* differentiators (competitors report
    detection-F1 only). Implemented progressively; stubs raise NotImplementedError with the
    phase they land in, so the harness never silently reports a fake number.

Every metric is registered in ``REGISTRY`` keyed by the string used in eval specs.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

Tags = Sequence[Sequence[str]]  # list of per-token BIOES tag sequences


def _seqeval(y_true: Tags, y_pred: Tags):
    # Imported lazily so the module stays importable without the optional dep installed.
    from seqeval.metrics import f1_score, precision_score, recall_score
    from seqeval.scheme import IOBES  # seqeval's name for the BIOES scheme

    kwargs = dict(mode="strict", scheme=IOBES, zero_division=0)
    return (
        precision_score(y_true, y_pred, **kwargs),
        recall_score(y_true, y_pred, **kwargs),
        f1_score(y_true, y_pred, **kwargs),
    )


def entity_f1(y_true: Tags, y_pred: Tags) -> dict[str, float]:
    """Strict entity-level precision / recall / F1 (exact span + type match)."""
    p, r, f1 = _seqeval(y_true, y_pred)
    return {"precision": p, "recall": r, "f1": f1}


def entity_f2(y_true: Tags, y_pred: Tags) -> dict[str, float]:
    """Recall-weighted F-beta (beta=2) — missed PII costs more than over-redaction."""
    p, r, _ = _seqeval(y_true, y_pred)
    beta2 = 4.0
    denom = (beta2 * p) + r
    f2 = (1 + beta2) * p * r / denom if denom else 0.0
    return {"precision": p, "recall": r, "f2": f2}


def reidentification_risk(*args, **kwargs) -> dict[str, float]:
    """Residual re-identification risk after redaction (TAB-style). Lands in Phase 4."""
    raise NotImplementedError("reidentification_risk: scheduled for Phase 4 (privacy-utility track)")


def pii_replay(*args, **kwargs) -> dict[str, float]:
    """Count of real PII entities reappearing in generated/anonymized output. Phase 4."""
    raise NotImplementedError("pii_replay: scheduled for Phase 4 (anonymization track)")


def membership_inference(*args, **kwargs) -> dict[str, float]:
    """MIA success rate against a model trained on sensitive text (PrivLM-Bench style). Phase 4."""
    raise NotImplementedError("membership_inference: scheduled for Phase 4 (leakage track)")


def utility_after_redaction(*args, **kwargs) -> dict[str, float]:
    """Downstream-task utility + readability preserved after redaction. Phase 4."""
    raise NotImplementedError("utility_after_redaction: scheduled for Phase 4 (privacy-utility track)")


REGISTRY: dict[str, Callable] = {
    "entity_f1": entity_f1,
    "entity_f2": entity_f2,
    "reidentification_risk": reidentification_risk,
    "pii_replay": pii_replay,
    "membership_inference": membership_inference,
    "utility_after_redaction": utility_after_redaction,
}
