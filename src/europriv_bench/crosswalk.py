"""Invert the taxonomy crosswalk: native scheme label → harmonized KP label.

Both consumers need this and must agree:
  * dataset curation (klusai-datasets) maps source labels (e.g. AI4Privacy ``GIVENNAME``) to KP;
  * model adapters (europriv-bench) map a model's native output (e.g. privacy-filter
    ``private_person``) to KP.

Building it here, from the single taxonomy definition, guarantees both use one mapping.
Conflicts (one native label claimed by two KP types in the same scheme) raise at import — fail
loud rather than silently mis-map.
"""

from __future__ import annotations

from collections.abc import Sequence

from .spans import labels_to_bioes, whitespace_tokens
from .taxonomy import SCHEMES, TAXONOMY


def _build_index() -> dict[str, dict[str, str]]:
    idx: dict[str, dict[str, str]] = {s: {} for s in SCHEMES}
    for entity in TAXONOMY:
        for scheme, natives in entity.crosswalk.items():
            bucket = idx.setdefault(scheme, {})
            for native in natives:
                if native in bucket and bucket[native] != entity.name:
                    raise ValueError(
                        f"crosswalk conflict for {scheme}:{native} → {bucket[native]} and {entity.name}"
                    )
                bucket[native] = entity.name
    return idx


_INDEX = _build_index()


def to_kp(scheme: str, native_label: str) -> str | None:
    """Map a native label in ``scheme`` to its KP entity type, or None if unmapped."""
    return _INDEX.get(scheme, {}).get(native_label)


def mapped_labels(scheme: str) -> dict[str, str]:
    """Full native→KP map for a scheme (e.g. to report coverage / unmapped labels)."""
    return dict(_INDEX.get(scheme, {}))


def entities_to_kp_bioes(text: str, entities: Sequence[dict], scheme: str) -> list[str]:
    """Convert native entity spans to KP-labeled BIOES tags over ``text``.

    ``entities``: dicts with ``label`` (native scheme label), ``start``, ``end`` (char offsets).
    Native labels with no KP mapping are dropped (use ``mapped_labels`` to audit coverage).

    This is the *prediction* path: models emit fragmented/overlapping spans, so it's tolerant
    (per-token first-label-wins → BIOES) and never raises. Gold curation uses the strict
    ``char_spans_to_bioes`` instead. Both produce tags in the same KP label space.
    """
    toks = whitespace_tokens(text)
    token_labels: list[str | None] = [None] * len(toks)
    for e in entities:
        kp = to_kp(scheme, e["label"])
        if kp is None:
            continue
        for i, (_, ts, te) in enumerate(toks):
            if ts < e["end"] and te > e["start"] and token_labels[i] is None:
                token_labels[i] = kp
    return labels_to_bioes(token_labels)
