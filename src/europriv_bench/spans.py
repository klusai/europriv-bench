"""Character-span ↔ BIOES token-label alignment + integrity validation.

Lives here (beside the taxonomy) because alignment produces tags in the taxonomy's BIOES
label space — the two are inseparable and must not drift. klusai-datasets and klusai-models
import these instead of carrying their own copies, so dataset gold labels, model label maps,
and benchmark scoring all use one byte-identical label space.

PII gold annotations arrive as character spans ``(start, end, label)``; models are scored on
BIOES token tags. The most common dataset bug is an off-by-one/misaligned span that silently
corrupts F1, so we fail loudly instead. Tokenization is whitespace-based with offsets; a
model-specific tokenizer can be substituted by passing pre-computed ``(token, start, end)``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    start: int   # char offset, inclusive
    end: int     # char offset, exclusive
    label: str   # KP entity type, e.g. "PERSON"


def whitespace_tokens(text: str) -> list[tuple[str, int, int]]:
    """Tokenize on whitespace, returning (token, start, end) char offsets."""
    tokens: list[tuple[str, int, int]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        j = i
        while j < n and not text[j].isspace():
            j += 1
        tokens.append((text[i:j], i, j))
        i = j
    return tokens


def char_spans_to_bioes(text: str, spans: list[Span]) -> list[str]:
    """Convert character spans to per-token BIOES tags over whitespace tokens.

    A token belongs to a span if it overlaps it. Raises ValueError on overlapping spans.
    """
    spans = sorted(spans, key=lambda s: s.start)
    for a, b in zip(spans, spans[1:]):
        if b.start < a.end:
            raise ValueError(f"overlapping spans: {a} and {b}")

    toks = whitespace_tokens(text)
    tags = ["O"] * len(toks)
    for sp in spans:
        member = [idx for idx, (_, ts, te) in enumerate(toks) if ts < sp.end and te > sp.start]
        if not member:
            raise ValueError(f"span {sp} aligns to no token (off-by-one?) in: {text!r}")
        if len(member) == 1:
            tags[member[0]] = f"S-{sp.label}"
        else:
            tags[member[0]] = f"B-{sp.label}"
            tags[member[-1]] = f"E-{sp.label}"
            for idx in member[1:-1]:
                tags[idx] = f"I-{sp.label}"
    return tags


def validate_bioes(tags: list[str]) -> None:
    """Validate BIOES tag-sequence well-formedness. Raises ValueError on malformed transitions."""
    prev_inside = False  # are we mid-entity (after B or I)?
    prev_type = None
    for i, tag in enumerate(tags):
        if tag == "O":
            if prev_inside:
                raise ValueError(f"entity not closed before O at position {i}: {tags}")
            prev_inside, prev_type = False, None
            continue
        kind, _, etype = tag.partition("-")
        if kind not in {"B", "I", "E", "S"} or not etype:
            raise ValueError(f"malformed tag {tag!r} at position {i}")
        if kind in {"B", "S"} and prev_inside:
            raise ValueError(f"new entity {tag!r} started before previous closed at {i}: {tags}")
        if kind in {"I", "E"}:
            if not prev_inside or etype != prev_type:
                raise ValueError(f"{tag!r} at {i} not preceded by matching B/I: {tags}")
        prev_inside = kind in {"B", "I"}
        prev_type = etype if prev_inside else None
    if prev_inside:
        raise ValueError(f"sequence ends mid-entity: {tags}")
