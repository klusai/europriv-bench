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


def newcombe_diff_ci(
    s1: int, n1: int, s2: int, n2: int, z: float = WILSON_Z_95
) -> tuple[float, float, float]:
    """Newcombe (1998) "method 10" hybrid-score CI for the difference of two INDEPENDENT proportions.

    Returns ``(diff, low, high)`` where ``diff = s1/n1 − s2/n2``. The interval combines each
    proportion's own Wilson score limits (which stay in ``[0, 1]`` and behave well near 0/1 and for
    small n) into a CI for the difference — exactly the regime of the KLU-101 per-family dissociation
    gap ``leak_rate(typed-detector) − leak_rate(protector)``, where the protector's leak is ≈0 and a
    naive Wald interval would understate the uncertainty. The dissociation "holds" for a family iff
    this CI excludes 0 (i.e. ``low > 0`` for a positive gap).

    Newcombe's construction: with Wilson limits ``(l1,u1)`` for p1 and ``(l2,u2)`` for p2,
        low  = (p1 − p2) − sqrt((p1 − l1)^2 + (u2 − p2)^2)
        high = (p1 − p2) + sqrt((u1 − p1)^2 + (p2 − l2)^2)
    """
    p1 = (s1 / n1) if n1 else 0.0
    p2 = (s2 / n2) if n2 else 0.0
    l1, u1 = wilson_interval(s1, n1, z)
    l2, u2 = wilson_interval(s2, n2, z)
    diff = p1 - p2
    low = diff - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    high = diff + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (diff, low, high)


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


# =============================================================================================
# KLU-118 v1 — the SECOND, non-token re-identification mechanism: name-in-context residual leak.
#
# CLAIM LANGUAGE (hard rule, from the design panel's red-team — docs/klu-118-qi-distinctiveness-
# design.md): this channel is a **"name-in-context leak" / "residual quasi-identifier
# distinctiveness"**, NEVER a "re-identification rate" on synthetic data. "Re-identification" is
# reserved for the deterministic national-ID anchor (``national_id_leakage``). A leaked PERSON full
# name left un-redacted on the POST-DETECTION RESIDUAL is a re-identifying signal that needs no
# reference-population model — but on synthetic documents it is a distinctiveness signal, not a
# population re-id. All outputs are config_status=dev and gated on KLU-27 before any headline use.
#
# Computed on the residual (the model's own redaction decision), NOT raw text: a name a detector
# would have removed cannot "leak". The unit is the SAME per-distinct-subject shape as the
# national-ID anchor — ``(doc, country, subject)`` — so the two channels are directly comparable,
# and we emit a 2×2 cross-tab per document (ID-leaked × name-leaked → both/either/neither) to show
# the channels are INDEPENDENT. A null/weak name-leak dissociation is an expected, valid finding
# (it would mean the dissociation is specific to structured, decode-bearing IDs) — reported as-is.
# =============================================================================================


def _person_name_subjects(rows: Sequence[dict], pred_tags: Tags) -> dict[tuple[int, str, str], dict]:
    """Per-distinct-subject PERSON-name residual-detection table, mirroring ``_national_id_subjects``.

    Key ``(document index, country, normalized name)`` — one distinct PERSON full-name value within
    one document. A subject is **detected iff EVERY occurrence is detected** (a span is detected iff
    the model marks any of its whitespace tokens non-O on the residual), so it **leaks iff ANY
    occurrence is left un-redacted** — exactly the per-subject (KLU-49) semantics the national-ID
    leak metric uses, so the two channels line up subject-for-subject and document-for-document.

    Only gold ``PERSON`` spans become subjects (the v1 name channel; direct identifiers other than
    the name and the IDs are out of scope here). The country tag is carried for unit-shape parity
    with the anchor; it does not gate which spans count (every country's names are in scope).
    """
    subjects: dict[tuple[int, str, str], dict] = {}
    for doc_idx, (row, pred) in enumerate(zip(rows, pred_tags)):
        toks = whitespace_tokens(row["text"])
        for sp in row.get("spans", []):
            if sp.get("label") != "PERSON":
                continue
            cc = _span_country(row, sp)
            raw = row["text"][sp["start"]:sp["end"]]
            name = " ".join(raw.split())  # normalize internal whitespace so repeats collapse to one subject
            if not name:
                continue
            members = [i for i, (_, ts, te) in enumerate(toks) if ts < sp["end"] and te > sp["start"]]
            detected = any(pred[i] != "O" for i in members if i < len(pred))
            key = (doc_idx, cc, name)
            subj = subjects.get(key)
            if subj is None:
                subj = {"doc": doc_idx, "country": cc, "name": name, "detected": True}
                subjects[key] = subj
            subj["detected"] = subj["detected"] and detected
    return subjects


def name_in_context_leakage(rows: Sequence[dict], pred_tags: Tags) -> dict[str, float]:
    """Name-in-context residual leak — the KLU-118 v1 second (non-token) re-identification channel.

    NOT a "re-identification rate": this is a **name-in-context leak / residual quasi-identifier
    distinctiveness** signal (claim-language rule, KLU-118 design doc). For each distinct PERSON
    subject ``(doc, country, normalized name)`` (same unit shape as the national-ID anchor), the
    subject **leaks** iff its full name is left un-redacted on the POST-DETECTION RESIDUAL (the model
    marked none of an occurrence's whitespace tokens; a leak iff ANY occurrence survives). Computed
    on the residual, never raw text — a name detection would have removed cannot leak.

    Returns the per-subject **name-leak rate** (↓ better) with a 95% Wilson CI (shared
    ``_leak_rate_stats``), and a per-document **2×2 cross-tab vs the national-ID anchor** to show the
    two channels are independent. A document is *id_leaked* iff any decode-bearing national-ID subject
    in it leaked, *name_leaked* iff any PERSON subject in it leaked; the cross-tab counts documents
    that carry BOTH channels (so the comparison is apples-to-apples) into
    ``both`` / ``id_only`` / ``name_only`` / ``neither``. A null/weak result (the name channel does
    NOT reproduce the structured-ID dissociation) is an expected, reportable finding.
    """
    name_subjects = _person_name_subjects(rows, pred_tags)
    total = len(name_subjects)
    leaked = sum(1 for s in name_subjects.values() if not s["detected"])
    stats = _leak_rate_stats(leaked, total)

    # Per-document 2×2 cross-tab vs the deterministic national-ID anchor. Only documents that carry
    # BOTH a (decode-bearing) national-ID subject AND a PERSON subject enter the cross-tab, so the
    # channels are compared on the same individuals' documents.
    id_subjects = _national_id_subjects(rows, pred_tags)
    id_leaked_doc: dict[int, bool] = {}
    for (doc_idx, _cc, _v), subj in id_subjects.items():
        if subj["decode_bearing"]:
            id_leaked_doc[doc_idx] = id_leaked_doc.get(doc_idx, False) or (not subj["detected"])
    name_leaked_doc: dict[int, bool] = {}
    for (doc_idx, _cc, _n), subj in name_subjects.items():
        name_leaked_doc[doc_idx] = name_leaked_doc.get(doc_idx, False) or (not subj["detected"])

    both = id_only = name_only = neither = 0
    for doc_idx in id_leaked_doc.keys() & name_leaked_doc.keys():
        idl = id_leaked_doc[doc_idx]
        nml = name_leaked_doc[doc_idx]
        if idl and nml:
            both += 1
        elif idl and not nml:
            id_only += 1
        elif nml and not idl:
            name_only += 1
        else:
            neither += 1

    return {
        "name_subjects_total": float(total),
        "name_subjects_leaked": float(leaked),
        # NB: a name-in-context leak rate, NOT a re-identification rate (synthetic distinctiveness).
        "name_leak_rate": stats["leak_rate"],                  # ↓ better
        "name_leak_rate_ci_low": stats["leak_rate_ci_low"],    # 95% Wilson lower bound
        "name_leak_rate_ci_high": stats["leak_rate_ci_high"],  # 95% Wilson upper bound
        # 2×2 cross-tab vs the national-ID anchor (per document carrying BOTH channels): the channels
        # are INDEPENDENT iff name leaks are not concentrated in the same docs as ID leaks.
        "xtab_docs": float(both + id_only + name_only + neither),
        "xtab_both_leaked": float(both),
        "xtab_id_only_leaked": float(id_only),
        "xtab_name_only_leaked": float(name_only),
        "xtab_neither_leaked": float(neither),
    }


# --- KLU-118 v1 scope item 2: k-anonymity-violation diagnostic over the residual QI tuple ----
#
# This is an EXPLORATORY diagnostic, NEVER a headline number, and labelled "sample distinctiveness,
# not population re-identification" (design-doc hard rule). It needs a residual QI TUPLE per subject
# — binned quasi-identifier VALUES per the frozen v1 QI schema (DOB/age band, sex, locality/NUTS,
# nationality, profession/ISCO, rare-condition flag; see the design doc's schema.py). The current
# gold carries only entity-type SPANS ``{start, end, label}`` (e.g. DATE/ADDRESS/HEALTH_CONDITION),
# NOT binned QI values typed to that schema, so an equivalence-class key cannot be formed without
# fabricating QIs. Per the design doc we SKIP-AND-REPORT cleanly rather than invent QIs.


_KANON_UNAVAILABLE_REASON = (
    "QI diagnostic unavailable: gold lacks QI tagging. The k-anonymity-violation diagnostic needs a "
    "residual quasi-identifier TUPLE per subject (binned QI values typed to the frozen v1 QI schema: "
    "DOB/age band, sex, locality/NUTS, nationality, profession/ISCO, rare-condition flag). The "
    "current gold carries only entity-type spans {start,end,label}, not binned QI values, so no "
    "equivalence-class key can be formed without fabricating QIs. Follow-up: tag QI values in gold "
    "(KLU-122 / the reference-population work) before enabling this diagnostic."
)


def _gold_has_qi_tuples(rows: Sequence[dict]) -> bool:
    """True iff gold rows carry a per-subject quasi-identifier TUPLE (binned QI values, not spans).

    We look for an explicit ``qi`` mapping on a span or a row-level ``qi_tuple``/``quasi_identifiers``
    field — the shape the k-anon equivalence-class key would be built from. Entity-type spans alone
    (``{start, end, label}``) do NOT qualify: a ``DATE`` or ``ADDRESS`` label is not a binned QI value
    typed to the frozen schema. Returns False for today's gold (→ skip-and-report).
    """
    for row in rows:
        if isinstance(row.get("qi_tuple"), dict) or isinstance(row.get("quasi_identifiers"), dict):
            return True
        for sp in row.get("spans", []):
            if isinstance(sp.get("qi"), dict):
                return True
    return False


def k_anonymity_violation(rows: Sequence[dict], pred_tags: Tags | None = None) -> dict[str, object]:
    """k-anonymity-violation diagnostic over the residual QI tuple — EXPLORATORY, NEVER a headline.

    LABEL (hard rule): this measures **"sample distinctiveness, not population re-identification."**
    When gold carries binned QI tuples it would report the **within-corpus equivalence-class-size
    distribution** (a histogram, never a single scalar) plus the k=1 and k<5 violation rates over the
    POST-DETECTION RESIDUAL QI tuple. The current gold lacks QI tagging (see ``_gold_has_qi_tuples``),
    so this **skip-and-reports** cleanly with ``available=False`` and a reason, rather than fabricating
    QIs. ``pred_tags`` is accepted for signature parity with the residual computation (unused on skip).
    """
    if not _gold_has_qi_tuples(rows):
        return {
            "available": False,
            "reason": _KANON_UNAVAILABLE_REASON,
            "label": "sample distinctiveness, not population re-identification",
        }
    # Gold DOES carry QI tuples → build the within-corpus equivalence-class-size distribution over the
    # residual QI tuple. (Reached only once QI tagging lands; kept minimal + dependency-free.)
    from collections import Counter

    classes: Counter[tuple] = Counter()
    for row in rows:
        qi = row.get("qi_tuple") or row.get("quasi_identifiers") or {}
        classes[tuple(sorted(qi.items()))] += 1
    sizes = sorted(classes.values())
    n = sum(sizes)
    size_hist: dict[int, int] = {}
    for s in sizes:
        size_hist[s] = size_hist.get(s, 0) + 1
    k1 = sum(c for c in sizes if c == 1)
    klt5 = sum(c for c in sizes if c < 5)
    return {
        "available": True,
        "label": "sample distinctiveness, not population re-identification",
        # The required distribution — emitted instead of a single headline scalar.
        "equivalence_class_size_histogram": {int(k): int(v) for k, v in sorted(size_hist.items())},
        "n_subjects": int(n),
        "n_equivalence_classes": int(len(classes)),
        "k1_violation_rate": (k1 / n) if n else 0.0,      # fraction of subjects in a unique (k=1) class
        "klt5_violation_rate": (klt5 / n) if n else 0.0,  # fraction of subjects in a k<5 class
    }


# =============================================================================================
# Track C — anonymization + downstream-utility (KLU-104).
#
# These score an adapter's *redacted text output* (one string per doc), NOT BIOES tags. The unit
# of measurement is the same per-distinct-subject (doc, country, normalized value) the detection
# leak metric uses, but the leak is read **from the gold offsets against the redacted text** — we
# never re-run a detector on the output (that would conflate redactor recall with auditor recall;
# KLU-104). Every number here is computed by code in this module with the formula in its docstring;
# the two utility/readability numbers are explicitly labelled reproducible *proxies*, not ratings.
# At launch the track ships config_status=dev (leaderboard default) and Presidio-as-redactor is a
# *baseline*, never a ranked winner.
# =============================================================================================

# Minimum surviving-fragment length (chars) that counts as a leak. A redactor that leaves the
# last-4 of a CNP/PESEL/CF un-masked still re-identifies (those digits narrow the subject), so a
# partial survival is a leak. We require ≥4 surviving consecutive characters of the gold value so a
# coincidental single shared digit elsewhere in the doc is not miscounted; 4 is the canonical
# "last-4" disclosure unit. Whitespace inside the value is ignored when matching.
_MIN_LEAK_FRAGMENT = 4


def _value_survives(redacted: str, value: str, min_fragment: int = _MIN_LEAK_FRAGMENT) -> bool:
    """True iff a re-identifying fragment of gold ``value`` survives verbatim in ``redacted`` text.

    Whitespace is stripped from both sides so a reformatted-but-unmasked value still counts. A
    *partial* survival is a leak: any contiguous run of ``min_fragment`` non-space characters of the
    value that appears in the (whitespace-stripped) output is a leak (e.g. an un-masked last-4 of a
    national ID). For short values (< ``min_fragment`` chars) the whole value must survive.
    """
    v = "".join(value.split())
    if not v:
        return False
    hay = "".join(redacted.split())
    k = min(min_fragment, len(v))
    # Slide a length-k window over the gold value; a leak if any window survives in the output.
    return any(v[i : i + k] in hay for i in range(0, len(v) - k + 1))


def _quasi_identifier_subjects(rows: Sequence[dict]) -> dict[tuple[int, str, str], dict]:
    """Per-distinct-subject quasi-identifier table built from GOLD offsets only (no model output).

    Key ``(doc index, country, normalized value)`` — one distinct national-ID value within one
    document, matching the detection leak metric's per-subject semantics (KLU-49). Only spans whose
    country has a validator and that parse as *valid*, decode-bearing national IDs become subjects
    (a leaked coverage-only ID discloses no quasi-identifier by construction, so it carries no re-id
    weight). ``qi`` is the count of quasi-identifiers a leak of this subject would disclose.
    """
    subjects: dict[tuple[int, str, str], dict] = {}
    for doc_idx, row in enumerate(rows):
        for sp in row.get("spans", []):
            cc = _span_country(row, sp)
            validator = get_validator(cc)
            if validator is None or not validator.decode_bearing:
                continue
            raw = row["text"][sp["start"]:sp["end"]]
            info = validator.parse(raw)
            if not info.valid:
                continue
            key = (doc_idx, cc, raw.strip())
            if key not in subjects:
                subjects[key] = {"country": cc, "value": raw.strip(),
                                 "qi": len(info.disclosed_quasi_identifiers())}
    return subjects


def redaction_leakage(rows: Sequence[dict], redacted: Sequence[str]) -> dict[str, float]:
    """Re-identification leak AFTER redaction, computed from gold offsets vs the redacted output.

    For each distinct decode-bearing subject ``(doc, country, normalized value)`` (KLU-49 dedup),
    the subject **leaks** iff a re-identifying fragment of its gold quasi-identifier value survives
    verbatim in that document's redacted text (``_value_survives`` — a partial survival such as an
    un-masked last-4 of a CNP counts as a leak). This is computed **purely from the gold span values
    against the output string**, never by re-running a detector on the output, so a high leak is
    attributable to the redactor's masking, not to an auditor's recall.

    Returns the per-subject leak-rate (↓ better) with a 95% Wilson CI, leaked-subject and
    leaked-quasi-identifier counts. ``redacted[i]`` is the anonymized text for ``rows[i]``.
    """
    subjects = _quasi_identifier_subjects(rows)
    total = len(subjects)
    leaked = leaked_qi = 0
    for (doc_idx, _cc, value), subj in subjects.items():
        out = redacted[doc_idx] if doc_idx < len(redacted) else ""
        if _value_survives(out, value):
            leaked += 1
            leaked_qi += subj["qi"]
    stats = _leak_rate_stats(leaked, total)
    return {
        "subjects_total": float(total),
        "subjects_leaked": float(leaked),
        "leak_rate": stats["leak_rate"],                  # ↓ better
        "leak_rate_ci_low": stats["leak_rate_ci_low"],    # 95% Wilson lower bound
        "leak_rate_ci_high": stats["leak_rate_ci_high"],  # 95% Wilson upper bound
        "leaked_quasi_identifiers": float(leaked_qi),
    }


def pseudonymization_consistency(
    rows: Sequence[dict], mappings: Sequence[dict[str, str]]
) -> dict[str, float]:
    """Measurable surrogate **bijection rate** for a pseudonymizer (each entity ↔ one surrogate).

    ``mappings[i]`` is the per-doc map ``{normalized source entity value -> surrogate}`` the
    pseudonymizer used for ``rows[i]``. Entity resolution is by normalized value (whitespace
    stripped), matching the leak metric's subject keying. The bijection rate is the fraction of
    distinct source entities that satisfy BOTH directions of a bijection:

      * **injective on the source** — every occurrence of the entity maps to exactly ONE surrogate
        (no inconsistent rewrites), AND
      * **injective on the target** — that surrogate is NOT reused for any OTHER distinct entity
        (no surrogate collision).

    Reported at two scopes (KLU-104 "state in-doc vs cross-doc"):
      * ``in_doc`` — bijection checked within each document independently, averaged over entities.
      * ``cross_doc`` — the same entity value must map to one stable surrogate across ALL documents
        (a stricter consistency a real pipeline needs for joinability), no surrogate shared across
        entities corpus-wide.

    Both are pure proportions (↑ better). An empty corpus yields rate 1.0 vacuously.
    """
    def _bijection_rate(scope_maps: Sequence[dict[str, str]]) -> tuple[int, int]:
        # entity -> set of surrogates seen; surrogate -> set of entities seen.
        ent_to_surr: dict[str, set[str]] = {}
        surr_to_ent: dict[str, set[str]] = {}
        for m in scope_maps:
            for ent, surr in m.items():
                e = "".join(ent.split())
                ent_to_surr.setdefault(e, set()).add(surr)
                surr_to_ent.setdefault(surr, set()).add(e)
        good = 0
        for e, surrs in ent_to_surr.items():
            injective_source = len(surrs) == 1
            # The single surrogate (if injective) must map back to only this entity.
            injective_target = injective_source and len(surr_to_ent[next(iter(surrs))]) == 1
            if injective_source and injective_target:
                good += 1
        return good, len(ent_to_surr)

    # in-doc: average the per-doc bijection rate over docs that contain ≥1 entity.
    in_good = in_total = 0
    for m in mappings:
        g, t = _bijection_rate([m])
        in_good += g
        in_total += t
    cross_good, cross_total = _bijection_rate(list(mappings))
    return {
        "in_doc_bijection_rate": (in_good / in_total) if in_total else 1.0,    # ↑ better
        "in_doc_entities": float(in_total),
        "cross_doc_bijection_rate": (cross_good / cross_total) if cross_total else 1.0,  # ↑ better
        "cross_doc_entities": float(cross_total),
    }


def _non_pii_token_mask(text: str, spans: Sequence[dict]) -> list[bool]:
    """Per-whitespace-token mask: True for tokens that overlap NO gold PII span (the non-PII tokens)."""
    toks = whitespace_tokens(text)
    is_pii = [False] * len(toks)
    for sp in spans:
        for idx, (_, ts, te) in enumerate(toks):
            if ts < sp["end"] and te > sp["start"]:
                is_pii[idx] = True
    return [not p for p in is_pii]


def information_retention(rows: Sequence[dict], redacted: Sequence[str]) -> dict[str, float]:
    """Utility-after-redaction PROXY: fraction of NON-PII tokens preserved unchanged (↑ better).

    A reproducible, code-computed utility proxy (NOT a downstream-task score and NOT a subjective
    rating): of every whitespace token in the gold text that overlaps no gold PII span, what
    fraction appears unchanged (as a whitespace token) in the redacted output? A redactor that only
    touches PII keeps this near 1.0; one that rewrites or drops surrounding context lowers it. This
    is a *proxy* for downstream utility — labelled as such — because token preservation correlates
    with, but does not measure, task performance on the redacted text.

    Formula: ``retained = |{non-PII gold tokens whose surface string is still present in the output
    token multiset}| / |non-PII gold tokens|``, matched by multiset so duplicates are consumed once.
    """
    retained = total = 0
    for i, row in enumerate(rows):
        text = row["text"]
        toks = whitespace_tokens(text)
        keep = _non_pii_token_mask(text, row.get("spans", []))
        out = redacted[i] if i < len(redacted) else ""
        # Multiset of output token surface strings, consumed once per match.
        out_counts: dict[str, int] = {}
        for tok, _, _ in whitespace_tokens(out):
            out_counts[tok] = out_counts.get(tok, 0) + 1
        for (tok, _, _), is_keep in zip(toks, keep):
            if not is_keep:
                continue
            total += 1
            if out_counts.get(tok, 0) > 0:
                retained += 1
                out_counts[tok] -= 1
    return {
        "information_retention": (retained / total) if total else 1.0,  # ↑ better (proxy)
        "non_pii_tokens": float(total),
        "non_pii_tokens_retained": float(retained),
        "is_proxy": 1.0,  # explicit: a reproducible proxy for downstream utility, not a task score
    }


def structural_disruption(rows: Sequence[dict], redacted: Sequence[str]) -> dict[str, float]:
    """Readability PROXY — a LANGUAGE-NEUTRAL structural-disruption measure (↓ less disruptive).

    Flesch-Kincaid is English-tuned and INVALID for de/fr/es/it/nl/ro (syllable/word-length
    heuristics don't transfer), so we deliberately do NOT use a readability formula. Instead we
    report a cross-lingual structural measure of how much redaction fragments the text:

      * ``mask_token_ratio`` — fraction of output whitespace tokens that are mask placeholders
        (a token consisting only of redaction characters: ``*``, ``█``, ``<...>``, ``[...]``, ``X``
        runs, or ``REDACTED``-style ALL-CAPS placeholders). More masks = more disruption.
      * ``length_delta_ratio`` — ``|len(out_tokens) − len(in_tokens)| / max(len(in_tokens), 1)``,
        averaged over docs: how much the token count changed (fragmentation/expansion of spans).

    Both are pure structural counts over whitespace tokens — no per-language linguistic model — so
    they are valid across every EuroPriv-Bench language. Lower means the redaction disturbed the
    document's structure less. NOTE (cross-lingual caveat): this measures *structural* disruption,
    not human-perceived readability, which no single index captures validly across languages.
    """
    import re

    # A token is a mask placeholder iff, after stripping bracketing, it is non-empty and made up
    # only of redaction glyphs / is an ALL-CAPS placeholder word like REDACTED / MASK / PII.
    _mask_word = {"REDACTED", "MASK", "MASKED", "PII", "ANONYMIZED", "HIDDEN", "REMOVED"}

    def _is_mask(tok: str) -> bool:
        core = tok.strip("[](){}<>").strip()
        if not core:
            return False
        if core.upper() in _mask_word:
            return True
        # A run of the full-block placeholder (the harness MASK_TOKEN █) is a mask at any length.
        if re.fullmatch(r"█+", core):
            return True
        # Other redaction glyph runs (asterisk, hash, X/x, underscore, hyphen) need ≥2 chars so a
        # stray single '-' or 'x' in ordinary text is not miscounted as a mask.
        return bool(re.fullmatch(r"[*#_\-xX]+", core)) and len(core) >= 2

    mask_tokens = out_tokens_total = 0
    length_delta_sum = 0.0
    for i, row in enumerate(rows):
        in_n = len(whitespace_tokens(row["text"]))
        out = redacted[i] if i < len(redacted) else ""
        out_toks = whitespace_tokens(out)
        out_tokens_total += len(out_toks)
        mask_tokens += sum(1 for tok, _, _ in out_toks if _is_mask(tok))
        length_delta_sum += abs(len(out_toks) - in_n) / max(in_n, 1)
    n_docs = len(rows)
    return {
        "mask_token_ratio": (mask_tokens / out_tokens_total) if out_tokens_total else 0.0,  # ↓
        "length_delta_ratio": (length_delta_sum / n_docs) if n_docs else 0.0,               # ↓
        "mask_tokens": float(mask_tokens),
        "output_tokens": float(out_tokens_total),
        "is_proxy": 1.0,  # language-neutral structural proxy; NOT a readability index (see docstring)
    }


def membership_inference(*args, **kwargs) -> dict[str, float]:
    """MIA success rate against a model trained on sensitive text (PrivLM-Bench style). Phase 4."""
    raise NotImplementedError("membership_inference: scheduled for Phase 4 (leakage track)")


# Tag-based metrics: called as fn(gold_tags, pred_tags).
REGISTRY: dict[str, Callable] = {
    "entity_f1": entity_f1,
    "entity_f2": entity_f2,
    "membership_inference": membership_inference,
}

# Row-based metrics: called as fn(gold_rows, pred_tags) — need span values, not just tags.
ROW_REGISTRY: dict[str, Callable] = {
    "national_id_leakage": national_id_leakage,
    "cnp_leakage": cnp_leakage,  # back-compat alias scoped to RO (same re-id-risk family)
    # KLU-118 v1 — name-in-context residual leak (the second, non-token re-id channel) + the
    # exploratory k-anonymity-violation diagnostic. Both take (rows, pred_tags); k_anonymity_violation
    # skip-and-reports when gold lacks QI tuples. Computed on the POST-DETECTION RESIDUAL.
    "name_in_context_leakage": name_in_context_leakage,
    "k_anonymity_violation": k_anonymity_violation,
}

# Track-C anonymization metrics: called as fn(gold_rows, redacted_texts) — score the adapter's
# redacted output string per doc (KLU-104). Re-id leak is computed from gold offsets, NOT a detector
# re-run on the output. Pseudonymization consistency takes per-doc surrogate maps instead of text;
# the runner passes them through when the adapter emits them (see ANON_MAP_REGISTRY).
ANON_REGISTRY: dict[str, Callable] = {
    "redaction_leakage": redaction_leakage,
    "information_retention": information_retention,
    "structural_disruption": structural_disruption,
}

# Track-C metrics scored over per-doc surrogate maps (not the redacted text).
ANON_MAP_REGISTRY: dict[str, Callable] = {
    "pseudonymization_consistency": pseudonymization_consistency,
}

ALL_METRICS = set(REGISTRY) | set(ROW_REGISTRY) | set(ANON_REGISTRY) | set(ANON_MAP_REGISTRY)
