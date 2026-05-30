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

from .national_id import parse_cnp
from .spans import whitespace_tokens

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


def cnp_leakage(rows: Sequence[dict], pred_tags: Tags) -> dict[str, float]:
    """Re-identification leakage via missed Romanian CNPs (the RO headline metric).

    A CNP is a *deterministic* disclosure: a missed (un-redacted) valid CNP leaks DATE_OF_BIRTH
    (when the century is unambiguous) + SEX + COUNTY. This scores, over the gold CNPs, how many a
    model fails to detect and the total quasi-identifiers thereby leaked. Lower is better.

    ``rows``: gold rows ``{text, spans:[{start,end,label}]}``. ``pred_tags``: model BIOES tags
    per row over the same whitespace tokenization. A CNP is "detected" iff the model marks any of
    its tokens non-O (i.e. it would be redacted).
    """
    total = detected = leaked_qi = 0
    for row, pred in zip(rows, pred_tags):
        toks = whitespace_tokens(row["text"])
        for sp in row.get("spans", []):
            info = parse_cnp(row["text"][sp["start"]:sp["end"]])
            if not info.valid:
                continue
            total += 1
            members = [i for i, (_, ts, te) in enumerate(toks) if ts < sp["end"] and te > sp["start"]]
            if any(pred[i] != "O" for i in members if i < len(pred)):
                detected += 1
            else:
                leaked_qi += len(info.disclosed_quasi_identifiers())
    missed = total - detected
    return {
        "cnp_total": float(total),
        "cnp_detected": float(detected),
        "cnp_missed": float(missed),
        "leak_rate": (missed / total) if total else 0.0,        # ↓ better
        "detection_rate": (detected / total) if total else 0.0,  # ↑ better
        "leaked_quasi_identifiers": float(leaked_qi),
    }


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


# Tag-based metrics: called as fn(gold_tags, pred_tags).
REGISTRY: dict[str, Callable] = {
    "entity_f1": entity_f1,
    "entity_f2": entity_f2,
    "reidentification_risk": reidentification_risk,
    "pii_replay": pii_replay,
    "membership_inference": membership_inference,
    "utility_after_redaction": utility_after_redaction,
}

# Row-based metrics: called as fn(gold_rows, pred_tags) — need span values, not just tags.
ROW_REGISTRY: dict[str, Callable] = {
    "cnp_leakage": cnp_leakage,
}

ALL_METRICS = set(REGISTRY) | set(ROW_REGISTRY)
