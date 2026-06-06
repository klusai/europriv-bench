"""KLU-118 v1 — deterministic, ADDITIVE residual-QI enrichment for ``ro-realskeleton-v1`` gold.

Turns on the already-implemented ``metrics.k_anonymity_violation`` diagnostic by giving each
per-subject row a binned ``qi_tuple`` (the frozen ``qi_schema`` shape) DERIVED from data ALREADY in
gold. No documents are regenerated, no spans changed, no RNG drawn — this is a pure read-only pass
over the existing gold spans + the model's prediction tags.

How each QI field is derived (RO ``ro-realskeleton-v1``):
  * ``dob_band`` / ``sex`` / ``nuts2`` — from the subject's CNP, decoded by the EXISTING
    ``national_id`` machinery (``parse_cnp``): SEX + DOB (-> 5-yr band) + county (-> NUTS-2 via the
    vendored crosswalk). These are exactly the quasi-identifiers a leaked CNP discloses.
  * ``rare_condition`` — True iff the document carries a surviving ``HEALTH_CONDITION`` span
    (special-category / GDPR Art. 9). Health spans are doc-level (one patient per medical letter).
  * ``nationality`` / ``isco_major`` — ABSENT from this gold (no nationality field; no profession
    label in the taxonomy) -> OMITTED, never fabricated.

POST-DETECTION RESIDUAL (design-doc hard rule — "always the post-detection residual"): a QI field is
included ONLY if the span that discloses it SURVIVED the model's redaction (was left un-redacted). If
the model redacted the CNP, the CNP-borne QIs (dob_band/sex/nuts2) are removed for that subject; if
it redacted every HEALTH_CONDITION span, ``rare_condition`` is dropped. The enriched ``qi_tuple`` is
therefore the residual an attacker can still read, never the raw-gold QI set.

Unit shape: ONE enriched row per distinct subject ``(doc, CNP value)`` — the same per-subject
semantics as the national-ID anchor (KLU-49). Subjects with no surviving QI field at all are dropped
(an empty equivalence-class key is not informative).
"""

from __future__ import annotations

from collections.abc import Sequence

from .national_id import parse_cnp
from .qi_schema import build_qi_tuple, dob_to_band
from .refpop import ro_county_to_nuts2
from .spans import whitespace_tokens

# v1 enrichment is RO-CNP specific; the diagnostic skip-and-reports for other corpora until their
# decoders/crosswalks are wired (kept honest per the design doc).
_RO = "RO"


def _span_detected(text: str, sp: dict, pred: Sequence[str], toks: list) -> bool:
    """True iff the model marked ANY whitespace token overlapping ``sp`` non-O (i.e. redacted it).

    Mirrors the residual-detection rule used by ``_national_id_subjects`` /
    ``_person_name_subjects`` so the QI residual lines up subject-for-subject with the leak metrics.
    """
    members = [i for i, (_, ts, te) in enumerate(toks) if ts < sp["end"] and te > sp["start"]]
    return any(pred[i] != "O" for i in members if i < len(pred))


def residual_qi_rows(
    rows: Sequence[dict], pred_tags: Sequence[Sequence[str]], country: str = _RO
) -> list[dict]:
    """Build per-subject rows carrying a residual ``qi_tuple`` for the k-anon diagnostic.

    Returns one row ``{"qi_tuple": {...}}`` per distinct subject ``(doc, CNP value)`` whose residual
    QI tuple is non-empty. Deterministic and pure: same (rows, pred_tags) -> same output. Only the
    RO/CNP corpus is enriched in v1; an unsupported ``country`` yields ``[]`` (-> skip-and-report).
    """
    if country.upper() != _RO:
        return []

    out: list[dict] = []
    for doc_idx, row in enumerate(rows):
        pred = pred_tags[doc_idx] if doc_idx < len(pred_tags) else []
        toks = whitespace_tokens(row["text"])

        # Doc-level rare-condition: True iff ANY HEALTH_CONDITION span survives the residual.
        health_survives = any(
            sp.get("label") == "HEALTH_CONDITION" and not _span_detected(row["text"], sp, pred, toks)
            for sp in row.get("spans", [])
        )

        # Per distinct CNP value: decode once; the residual is "did this CNP survive?". Dedupe so a
        # CNP repeated as "cod asigurat" is one subject (matching _national_id_subjects).
        seen: dict[str, dict] = {}
        for sp in row.get("spans", []):
            if sp.get("label") != "NATIONAL_ID":
                continue
            raw = row["text"][sp["start"]:sp["end"]].strip()
            info = parse_cnp(raw)
            if not info.valid:
                continue
            survived = not _span_detected(row["text"], sp, pred, toks)
            entry = seen.get(raw)
            if entry is None:
                seen[raw] = {"info": info, "survived": survived}
            else:
                # Subject's CNP is disclosed iff ANY occurrence survived (ANY-occurrence leak rule).
                entry["survived"] = entry["survived"] or survived

        for _value, entry in seen.items():
            info = entry["info"]
            cnp_survived = entry["survived"]
            fields: dict[str, object] = {}
            if cnp_survived:
                # CNP-borne QIs only when the CNP itself survived the redaction (residual).
                if info.century_known:
                    fields["dob_band"] = dob_to_band(info.birth_date)
                fields["sex"] = info.sex
                fields["nuts2"] = ro_county_to_nuts2(info.county_code)
            # rare_condition is a doc-level special-category flag (its own surviving health span).
            fields["rare_condition"] = health_survives
            qi = build_qi_tuple(fields)
            if qi:
                out.append({"qi_tuple": qi})
    return out
