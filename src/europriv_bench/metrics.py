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

import math
from collections.abc import Callable, Sequence

from .national_id import get_validator
from .spans import whitespace_tokens

Tags = Sequence[Sequence[str]]  # list of per-token BIOES tag sequences

# Default two-sided z for a 95% normal-approximation confidence interval.
WILSON_Z_95 = 1.95996


def wilson_interval(successes: int, total: int, z: float = WILSON_Z_95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion ``successes/total``.

    Unlike the naive normal-approximation (Wald) interval, the Wilson interval stays inside
    ``[0, 1]`` and behaves sensibly for proportions near 0 or 1 and for small ``total`` — which is
    exactly the regime of leak-rate CIs (rare misses over ~1.5k items). Returns ``(low, high)``
    bounds; ``(0.0, 0.0)`` when ``total == 0``.
    """
    if total <= 0:
        return (0.0, 0.0)
    p = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denom
    half = (z / denom) * math.sqrt(p * (1.0 - p) / total + z2 / (4.0 * total * total))
    return (center - half, center + half)


def _leak_rate_stats(missed: int, total: int) -> dict[str, float]:
    """Shared leak-rate point estimate + Wilson CI (reused by CNP and future national-id leakage)."""
    low, high = wilson_interval(missed, total)
    return {
        "leak_rate": (missed / total) if total else 0.0,  # ↓ better
        "leak_rate_ci_low": low,
        "leak_rate_ci_high": high,
    }


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


# A span's country is read from its ``country`` key (ISO alpha-2); rows may set a row-level
# ``country`` default. When neither is present we fall back to RO — preserving the legacy
# CNP-only behavior of ``cnp_leakage`` for existing RO datasets that carry no country tag.
_DEFAULT_COUNTRY = "RO"


def _span_country(row: dict, sp: dict) -> str:
    return str(sp.get("country") or row.get("country") or _DEFAULT_COUNTRY).upper()


def _national_id_subjects(rows: Sequence[dict], pred_tags: Tags) -> dict[tuple[int, str, str], dict]:
    """Build the per-subject detection table shared by the leak metric and the prediction dump.

    Key: ``(document index, country, normalized value)`` — one distinct national-ID value within
    one document (KLU-49 per-subject semantics). A subject is **detected iff EVERY occurrence is
    detected** (a span is detected iff the model marks any of its whitespace tokens non-O), so it
    leaks iff ANY occurrence is left unredacted. Only spans whose country has a validator and that
    parse as *valid* national IDs become subjects. ``qi`` is the count of disclosed quasi-identifiers
    for a decode-bearing miss.
    """
    subjects: dict[tuple[int, str, str], dict] = {}

    for doc_idx, (row, pred) in enumerate(zip(rows, pred_tags)):
        toks = whitespace_tokens(row["text"])
        for sp in row.get("spans", []):
            cc = _span_country(row, sp)
            validator = get_validator(cc)
            if validator is None:
                continue
            raw = row["text"][sp["start"]:sp["end"]]
            info = validator.parse(raw)
            if not info.valid:
                continue
            members = [i for i, (_, ts, te) in enumerate(toks) if ts < sp["end"] and te > sp["start"]]
            detected = any(pred[i] != "O" for i in members if i < len(pred))

            # Normalize the value so the CNP field and the CASS "cod asigurat" field — same digits,
            # possibly different surrounding whitespace — collapse onto one subject.
            key = (doc_idx, cc, raw.strip())
            subj = subjects.get(key)
            if subj is None:
                subj = {
                    "country": cc,
                    "decode_bearing": validator.decode_bearing,
                    # A subject is detected only if EVERY occurrence is detected.
                    "detected": True,
                    "qi": len(info.disclosed_quasi_identifiers()),
                }
                subjects[key] = subj
            subj["detected"] = subj["detected"] and detected

    return subjects


def national_id_subject_detection(rows: Sequence[dict], pred_tags: Tags) -> list[dict]:
    """Per-subject national-ID detection outcomes for item-paired significance testing (McNemar).

    Returns one record per distinct subject ``(doc, country, normalized value)`` in deterministic
    (document, value) order:
      ``{"doc": int, "country": str, "value": str, "decode_bearing": bool, "detected": bool}``

    ``detected=False`` means the subject's national ID **leaked** (was left unredacted in at least
    one occurrence). This is the exact unit the re-id leak-rate is computed over, so a McNemar test
    pairing two models' ``detected`` flags subject-by-subject is consistent with the leaderboard
    leak-rate. Keys are stable across adapters (they depend only on the gold rows), so two dumps
    align row-for-row by ``(doc, country, value)``.
    """
    subjects = _national_id_subjects(rows, pred_tags)
    return [
        {
            "doc": key[0],
            "country": key[1],
            "value": key[2],
            "decode_bearing": subj["decode_bearing"],
            "detected": bool(subj["detected"]),
        }
        for key, subj in sorted(subjects.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2]))
    ]


def national_id_leakage(rows: Sequence[dict], pred_tags: Tags) -> dict[str, float]:
    """Country-dispatched re-identification leakage via missed national IDs (one re-id family).

    Each gold span is validated by its country's validator (``national_id.REGISTRY``, keyed by an
    ISO alpha-2 ``country`` on the span or row; default RO). A span is "detected" iff the model
    marks any of its whitespace tokens non-O (i.e. it would be redacted). This folds in
    ``cnp_leakage`` (RO) as one re-identification-risk family and cleanly separates two families
    on output:

      * **decode-bearing** (RO/CNP, PL/PESEL, IT/codice-fiscale) — a miss deterministically
        discloses quasi-identifiers (DOB/sex/place); we sum ``leaked_quasi_identifiers``.
      * **coverage-only** (ES/DNI-NIF) — detectable but no decodable quasi-identifier; we score
        detection coverage and **never** emit a re-identification number (its leaked-QI is 0 by
        construction).

    **Re-identification risk is per *distinct subject*, not per textual mention (KLU-49).** Real RO
    clinical documents legitimately repeat the same CNP value twice (the CNP field + the CASS "cod
    asigurat" field). Counting per textual span would double-count a single subject's national ID
    and inflate the denominator. So we dedup by ``(document, country, normalized value)``: a
    *subject* is one distinct ID value within one document, it is **protected iff ALL its
    occurrences are redacted**, and it **leaks iff ANY occurrence is left unredacted**. Counts,
    leak-rate and disclosed quasi-identifiers are all per-subject.

    Leak-rates carry 95% Wilson CIs via the shared ``_leak_rate_stats``. The headline ``leak_rate``
    is computed over the **decode-bearing** subset (the re-id-risk signal); coverage-only IDs get
    their own detection counters. Lower leak_rate is better.
    """
    # Per-subject aggregation (KLU-49). Shared with the prediction dump so the dumped per-subject
    # detected/leaked flags are computed by the exact same (doc, country, normalized value) logic.
    subjects = _national_id_subjects(rows, pred_tags)

    # Overall + per-family + per-country counters, now over distinct subjects.
    db_total = db_detected = leaked_qi = 0          # decode-bearing
    co_total = co_detected = 0                       # coverage-only
    per_country: dict[str, list[int]] = {}           # cc -> [total, detected]

    for subj in subjects.values():
        cc = subj["country"]
        detected = subj["detected"]
        counts = per_country.setdefault(cc, [0, 0])
        counts[0] += 1
        if detected:
            counts[1] += 1

        if subj["decode_bearing"]:
            db_total += 1
            if detected:
                db_detected += 1
            else:
                # Coverage-only subjects never reach here, so no re-id number is ever emitted.
                leaked_qi += subj["qi"]
        else:
            co_total += 1
            if detected:
                co_detected += 1

    db_missed = db_total - db_detected
    stats = _leak_rate_stats(db_missed, db_total)
    out = {
        # Decode-bearing re-identification-risk family (the headline leak-rate signal).
        "decode_bearing_total": float(db_total),
        "decode_bearing_detected": float(db_detected),
        "decode_bearing_missed": float(db_missed),
        "leak_rate": stats["leak_rate"],                            # ↓ better
        "leak_rate_ci_low": stats["leak_rate_ci_low"],              # 95% Wilson lower bound
        "leak_rate_ci_high": stats["leak_rate_ci_high"],            # 95% Wilson upper bound
        "detection_rate": (db_detected / db_total) if db_total else 0.0,  # ↑ better
        "leaked_quasi_identifiers": float(leaked_qi),
        # Coverage-only family — detection only, never a re-identification number.
        "coverage_only_total": float(co_total),
        "coverage_only_detected": float(co_detected),
        "coverage_only_detection_rate": (co_detected / co_total) if co_total else 0.0,  # ↑ better
    }
    # Per-country detection counters (cc_total / cc_detected) for both families.
    for cc, (tot, det) in sorted(per_country.items()):
        out[f"{cc.lower()}_total"] = float(tot)
        out[f"{cc.lower()}_detected"] = float(det)
    return out


def cnp_leakage(rows: Sequence[dict], pred_tags: Tags) -> dict[str, float]:
    """RO/CNP re-identification leakage — back-compat alias over ``national_id_leakage``.

    A CNP is a *deterministic* disclosure: a missed (un-redacted) valid CNP leaks DATE_OF_BIRTH
    (when the century is unambiguous) + SEX + COUNTY. This is now one country in the unified
    national-ID re-id-risk family; it scopes scoring to RO spans and preserves the historical
    ``cnp_*`` output keys (and Wilson-CI leak_rate) verbatim so existing RO callers, baselines and
    the leaderboard keep working unchanged. Lower is better.
    """
    ro_rows = [{**row, "country": "RO",
                "spans": [{**sp, "country": "RO"} for sp in row.get("spans", [])]}
               for row in rows]
    res = national_id_leakage(ro_rows, pred_tags)
    return {
        "cnp_total": res["decode_bearing_total"],
        "cnp_detected": res["decode_bearing_detected"],
        "cnp_missed": res["decode_bearing_missed"],
        "leak_rate": res["leak_rate"],                           # ↓ better
        "leak_rate_ci_low": res["leak_rate_ci_low"],             # 95% Wilson lower bound
        "leak_rate_ci_high": res["leak_rate_ci_high"],           # 95% Wilson upper bound
        "detection_rate": res["detection_rate"],                 # ↑ better
        "leaked_quasi_identifiers": res["leaked_quasi_identifiers"],
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
    "national_id_leakage": national_id_leakage,
    "cnp_leakage": cnp_leakage,  # back-compat alias scoped to RO (same re-id-risk family)
}

ALL_METRICS = set(REGISTRY) | set(ROW_REGISTRY)
