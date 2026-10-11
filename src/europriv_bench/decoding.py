"""Deterministic, opt-in gateway span decoding; no gold or language heuristics."""

from __future__ import annotations

import regex

from .national_id import get_validator

RULES = ("strict", "inward", "anchored")
MIN_LENGTH = {
    "PERSON": 2, "ADDRESS": 2, "ORG_PARTY": 2, "DATE": 2, "EMAIL": 5,
    "PHONE": 7, "URL": 4, "NATIONAL_ID": 3, "ACCOUNT_ID": 3,
    "COMPANY_ID": 3, "CASE_NUMBER": 3,
}


def word_units(text: str) -> list[tuple[int, int]]:
    """Unicode default word segmentation, retaining letters/numbers and combining marks."""
    boundaries = sorted({0, len(text), *(m.start() for m in regex.finditer(r"\b", text, regex.WORD))})
    return [(a, b) for a, b in zip(boundaries, boundaries[1:]) if regex.search(r"[\p{L}\p{N}]", text[a:b])]


def structured_validity(value: str, label: str, country: str | None = None) -> tuple[bool, bool]:
    """Return (admissible, checksum exemption); unknown formats remain admissible."""
    if label == "NATIONAL_ID" and (validator := get_validator(country)) is not None:
        valid = validator.parse(value).valid
        # Danish CPR has no current checksum; do not grant it the checksum exemption.
        return valid, valid and country.upper() != "DK"
    if label == "ACCOUNT_ID":
        compact = "".join(value.split()).upper()
        if regex.match(r"[A-Z]{2}[0-9]{2}", compact):
            if not regex.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}", compact):
                return False, False
            numeric = "".join(str(ord(c) - 55) if c.isalpha() else c for c in compact[4:] + compact[:4])
            valid = int(numeric) % 97 == 1
            return valid, valid
    if label == "PHONE":
        valid = bool(regex.fullmatch(r"\+?[\p{Nd}\s()./\-]+", value))
        return valid and 7 <= sum(c.isdecimal() for c in value) <= 15, False
    return True, False


def postprocess_spans(text: str, spans: list[dict], *, rule: str, country: str | None = None) -> list[dict]:
    """Require a complete unit, snap/reject edge fragments, then validate label length/format.

    Country is explicit deployment context, never inferred from annotations or text.
    Extra receipt fields (including confidence) are retained; inputs are not mutated.
    """
    if rule not in RULES:
        raise ValueError(f"Unknown decoding rule: {rule}")
    units = word_units(text)
    output = []
    for span in spans:
        start, end = span["start"], span["end"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
            raise ValueError("Invalid decoding offsets")
        while start < end and text[start].isspace():
            start += 1
        while start < end and text[end - 1].isspace():
            end -= 1
        whole = [(a, b) for a, b in units if start <= a and b <= end]
        if not whole:
            continue
        partial = [(a, b) for a, b in units if a < end and b > start and not (start <= a and b <= end)]
        if partial:
            if rule == "strict":
                continue
            if rule == "inward":
                if any(a < start < b for a, b in partial):
                    start = whole[0][0]
                if any(a < end < b for a, b in partial):
                    end = whole[-1][1]
            else:
                start = min(start, *(a for a, _ in partial))
                end = max(end, *(b for _, b in partial))
        value = text[start:end]
        valid, exempt = structured_validity(value, span["label"], country)
        if valid and (exempt or sum(not c.isspace() for c in value) >= MIN_LENGTH.get(span["label"], 2)):
            output.append({**span, "start": start, "end": end})
    return output
