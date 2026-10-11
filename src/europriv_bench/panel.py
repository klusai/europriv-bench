"""RES-77 exact-span LLM-panel audit statistics; never human validation."""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter, defaultdict

from .national_id import REGISTRY
from .taxonomy import TAXONOMY

SEED = 77
MODELS = ("mistralai/mistral-large-2512", "google/gemini-2.5-flash", "qwen/qwen3-235b-a22b-2507")
LABELS = {e.name for e in TAXONOMY}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def stratum(row: dict) -> str:
    if row["domain"] == "admin":
        return "admin"
    heading = row["text"].splitlines()[0]
    if heading.startswith(("SCRISOARE", "KARTA")):
        return "clinical"
    if heading.startswith(("CONTRACT", "UMOWA")):
        return "contract"
    if heading.startswith(("DECLARAȚIE", "OŚWIADCZENIE")):
        return "declaration"
    raise ValueError(f"Unknown stratum: {heading}")


def sample_rows(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[stratum(row)].append(i)
    if set(groups) != {"admin", "clinical", "contract", "declaration"}:
        raise ValueError("Expected four strata")
    rng = random.Random(SEED)
    result = []
    for group, indices in sorted(groups.items()):
        for i in sorted(rng.sample(indices, 75)):
            result.append({**rows[i], "id": str(i), "stratum": group, "sha256": digest(rows[i]["text"])})
    return result


def span_set(spans: list[dict]) -> set[tuple[int, int, str]]:
    return {(s["start"], s["end"], s["label"]) for s in spans}


def align(text: str, spans: list[dict]) -> list[dict]:
    """Exact Unicode matching; occurrence makes repeated identifiers unambiguous."""
    result = []
    for s in spans:
        value, occurrence, label = s["text"], s["occurrence"], s["label"]
        if not value or label not in LABELS or type(occurrence) is not int or occurrence < 1:
            raise ValueError("Invalid annotation")
        matches = list(re.finditer(re.escape(value), text))
        if occurrence > len(matches):
            raise ValueError(f"Unalignable annotation: {value!r}, occurrence {occurrence}")
        match = matches[occurrence - 1]
        result.append({"start": match.start(), "end": match.end(), "label": label})
    result.sort(key=lambda s: (s["start"], s["end"], s["label"]))
    if any(a["end"] > b["start"] for a, b in zip(result, result[1:])):
        raise ValueError("Overlapping/duplicate annotations")
    return result


def validate_annotation(row: dict, output: dict) -> dict:
    for rating in ("fluency", "naturalness"):
        if type(output[rating]) is not int or not 1 <= output[rating] <= 5:
            raise ValueError("Ratings must be integers 1..5")
    if not isinstance(output["artifacts"], list) or any(not isinstance(a, str) for a in output["artifacts"]):
        raise ValueError("Artifacts must be strings")
    return {**output, "spans": align(row["text"], output["spans"])}


def candidates(row: dict, annotations: list[dict]) -> list[dict]:
    gold = span_set(row["spans"])
    differences = set().union(*(gold ^ span_set(a["spans"]) for a in annotations))
    return [
        {
            "id": str(i),
            "operation": "remove" if s in gold else "add",
            "start": s[0],
            "end": s[1],
            "label": s[2],
            "text": row["text"][s[0] : s[1]],
        }
        for i, s in enumerate(sorted(differences))
    ]


def alpha_counts(raters: list[dict[tuple, str]], units: list[tuple]) -> tuple[float, Counter]:
    """Nominal coincidence counts; constant rater count, no missing observations."""
    counts = Counter()
    disagreement = 0.0
    m = len(raters)
    if m < 2:
        return disagreement, counts  # A single judge cannot supply panel agreement.
    for unit in units:
        c = Counter(r.get(unit, "ABSENT") for r in raters)
        counts.update(c)
        disagreement += (m * m - sum(n * n for n in c.values())) / (m - 1)
    return disagreement, counts


def alpha_from_counts(disagreement: float, counts: Counter) -> float | None:
    n = counts.total()
    if n < 2:
        return None
    expected = (n * n - sum(c * c for c in counts.values())) / (n - 1)
    return 1 - disagreement / expected if expected else None


def alpha_documents(rows: list[dict], annotations: dict, models: tuple[str, ...] = MODELS) -> list[dict]:
    result = []
    for row in rows:
        raters = [
            {(s["start"], s["end"]): s["label"] for s in spans}
            for spans in [row["spans"], *(annotations[m][row["id"]]["spans"] for m in models)]
        ]
        units = sorted(set().union(*(r.keys() for r in raters)))
        result.append(
            {
                "stratum": row["stratum"],
                "panel": alpha_counts(raters[1:], units),
                **{m: alpha_counts([raters[0], raters[i + 1]], units) for i, m in enumerate(models)},
            }
        )
    return result


def decode_audit(rows: list[dict], country: str) -> dict:
    subjects, explicit_dob, failures = 0, 0, []
    pattern = r"(?<!\d)\d{" + ("13" if country == "RO" else "11") + r"}(?!\d)"
    for i, row in enumerate(rows):
        text = row["text"]
        matches = list(re.finditer(pattern, text))
        seen = set()
        for match in matches:
            value = match.group()
            reasons = []
            info = REGISTRY[country].parse(value)
            if not info.valid or not info.extra.get("birth_date") or not info.extra.get("sex"):
                reasons.append("invalid checksum or unknown DOB/sex")
            if not any(
                s["label"] == "NATIONAL_ID" and s["start"] <= match.start() and s["end"] >= match.end()
                for s in row["spans"]
            ):
                reasons.append("raw ID lacks NATIONAL_ID gold coverage")
            if row["domain"] == "clinical":
                dob = re.search(r"(?:Data nașterii|Data urodzenia):\s*(\d{2})\.(\d{2})\.(\d{4})", text)
                if dob:
                    if value not in seen:
                        explicit_dob += 1
                    stated = f"{dob[3]}-{dob[2]}-{dob[1]}"
                    if info.extra.get("birth_date") != stated:
                        reasons.append("explicit DOB mismatch")
                else:
                    reasons.append("clinical DOB field missing")
            sex = re.search(r"(?:Sex|Płeć):\s*(M|F|K)\b", text, re.I)
            if sex and info.extra.get("sex") != ("F" if sex[1].upper() in {"F", "K"} else "M"):
                reasons.append("explicit sex mismatch")
            if value not in seen:
                subjects += 1
            seen.add(value)
            if reasons:
                failures.append({"id": str(i), "value": value, "start": match.start(), "reasons": reasons})
    failed_subjects = len({(f["id"], f["value"]) for f in failures})
    return {
        "subjects": subjects,
        "consistent": subjects - failed_subjects,
        "explicit_dob_subjects": explicit_dob,
        "failures": failures,
        "pass": subjects > 0 and not failures,
    }
