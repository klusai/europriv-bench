"""Pinned Ai4Privacy validation slices, downloaded locally before reading parquet.

The Hub publishes one ``default`` config, not our language-specific eval identities.
Native labels use the canonical crosswalk; excluded labels are counted on each row.
"""

from __future__ import annotations

from collections import Counter

from .crosswalk import to_kp
from .logger import get_logger
from .spans import Span, char_spans_to_bioes, validate_bioes
from .spec import EvalSpec

logger = get_logger(__name__)


class OpenPIIRows(list):
    """Gold rows with an auditable record of source selection and tokenization exclusions."""

    source_metadata: dict


def map_openpii_row(row: dict) -> dict:
    text = row["source_text"]
    spans = []
    dropped = Counter()
    for mask in row["privacy_mask"]:
        start, end = int(mask["start"]), int(mask["end"])
        if not 0 <= start < end <= len(text) or text[start:end] != mask["value"]:
            raise ValueError(f"OpenPII span/value mismatch in uid={row['uid']!r}")
        label = to_kp("ai4privacy", mask["label"])
        if label is None:
            dropped[mask["label"]] += 1
        else:
            spans.append({"start": start, "end": end, "label": label})
    validate_bioes(char_spans_to_bioes(text, [Span(**span) for span in spans]))
    return {
        "text": text, "spans": spans, "language": row["language"], "uid": row["uid"],
        "unmapped_labels": dict(dropped),
    }


def load_openpii(spec: EvalSpec) -> list[dict]:
    """First max_rows validation documents per language, in pinned file/row order.

    Token collisions are excluded and counted as in the original RES-93 curation; no replacement
    candidates are drawn. Other malformed gold and short source slices fail loudly.
    """
    from huggingface_hub import hf_hub_download
    from pyarrow import parquet

    source = spec.dataset
    if (
        source.hf_id != "ai4privacy/pii-masking-openpii-1m"
        or source.config != "default"
        or source.split != "validation"
        or not source.revision
        or not source.files
        or not source.max_rows
        or len(spec.languages) != 1
    ):
        raise ValueError("OpenPII requires a pinned default/validation source, files, max_rows and one language")
    language = spec.languages[0]
    if source.eval_config != f"ai4privacy-openpii-{language}-v1":
        raise ValueError("OpenPII eval_config must match its language for contamination classification")
    candidates = []
    for filename in source.files:
        path = hf_hub_download(
            source.hf_id, filename, repo_type="dataset", revision=source.revision,
        )
        table = parquet.read_table(
            path, columns=["source_text", "privacy_mask", "language", "uid"],
            filters=[("language", "=", language)],
        )
        remaining = source.max_rows - len(candidates)
        candidates.extend(table.slice(0, remaining).to_pylist())
        if len(candidates) == source.max_rows:
            break
    if len(candidates) != source.max_rows:
        raise ValueError(f"OpenPII {language}: expected {source.max_rows} candidates, found {len(candidates)}")
    rows = OpenPIIRows()
    excluded = []
    dropped = Counter()
    for candidate in candidates:
        try:
            row = map_openpii_row(candidate)
        except ValueError as exc:
            if not str(exc).startswith("token collision:"):
                raise
            excluded.append(candidate["uid"])
            continue
        rows.append(row)
        dropped.update(row["unmapped_labels"])
    if not rows:
        raise ValueError(f"OpenPII {language}: no scoreable gold rows")
    rows.source_metadata = {"curation": {
        "candidate_rows": len(candidates), "kept_rows": len(rows),
        "excluded_token_collision_uids": excluded, "unmapped_labels_kept_rows": dict(dropped),
        "selection": "first max_rows per language in pinned file/row order; no replacement",
    }}
    logger.info(
        "OpenPII %s: %d/%d rows, %d token collisions excluded", language, len(rows), len(candidates), len(excluded),
    )
    return rows
