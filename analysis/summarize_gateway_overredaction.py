"""Validate an exhaustive DEV adjudication ledger and summarize with harness statistics."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from europriv_bench.gateway import LANGUAGES, paired_cluster_bootstrap, sha256
from europriv_bench.metrics import wilson_interval


def summarize(scratch, ledger):
    with ledger.open() as stream:
        annotations = list(csv.DictReader(stream, delimiter="\t"))
    by_id = {a["id"]: a for a in annotations}
    if len(by_id) != len(annotations):
        raise ValueError("Duplicate annotations")
    if any(a["class"] not in "abcd" or len(a["class"]) != 1 or not a["reason"] for a in annotations):
        raise ValueError("Invalid or unexplained annotation")
    result, seen, provenance = {}, set(), None
    for lang in LANGUAGES:
        errors = json.loads((scratch / f"{lang}.errors.json").read_text())
        utility = json.loads((scratch / f"{lang}.utility.json").read_text())
        identity = json.loads((scratch / f"{lang}.predictions.json").read_text())["identity"]
        current = {k: v for k, v in identity.items() if k != "ids"}
        if provenance is not None and current != provenance:
            raise ValueError("Cross-language provenance drift")
        provenance = current
        if identity["split"] != "dev" or any("/dev/" not in i for i in identity["ids"]):
            raise ValueError("Only DEV may be summarized")
        positions = {key: i for i, key in enumerate(identity["ids"])}
        counts = {key: [[0, den] for _, den in utility["counts"]] for key in "abcd"}
        for error in errors:
            if error["id"] in seen:
                raise ValueError("Duplicate error fragment")
            seen.add(error["id"])
            annotation = by_id[error["id"]]
            if int(annotation["characters"]) != error["characters"]:
                raise ValueError("Changed fragment character count")
            counts[annotation["class"]][positions[error["conversation"]]][0] += error["characters"]
        if sum(c[0] for group in counts.values() for c in group) != utility["score"]["removed_non_pii_characters"]:
            raise ValueError("Annotations do not partition harness utility loss")
        classes = {}
        for key in "abcd":
            selected = [e for e in errors if by_id[e["id"]]["class"] == key]
            classes[key] = {
                "fragments": len(selected), "share": len(selected) / len(errors) if errors else None,
                "share_wilson95": wilson_interval(len(selected), len(errors)) if errors else None,
                "characters": sum(e["characters"] for e in selected),
                "conversations": len({e["conversation"] for e in selected}),
                "utility_contribution": paired_cluster_bootstrap(counts[key], [[0, d] for _, d in counts[key]]),
                "reasons": dict(Counter(by_id[e["id"]]["reason"] for e in selected)),
            }
        families = Counter()
        for e in errors:
            families[e["family"]] += e["characters"]
        result[lang] = {
            "conversations": len(positions), "affected_conversations": len({e["conversation"] for e in errors}),
            "fragments": len(errors), "classes": classes, "harness_utility": utility["score"],
            "utility_ci": paired_cluster_bootstrap(utility["counts"], [[0, d] for _, d in utility["counts"]]),
            "family_error_characters": dict(families),
            "predictions_sha256": sha256(scratch / f"{lang}.predictions.json"),
            "errors_sha256": sha256(scratch / f"{lang}.errors.json"),
        }
    if seen != set(by_id):
        raise ValueError("Missing or extraneous annotations")
    return {"ledger_sha256": sha256(ledger), "training_seed_count": 1, "training_seed": 0,
            "bootstrap_seed": 126, "bootstrap_resamples": 2000,
            "review": "single Codex multilingual contextual adjudication; no independent native human review",
            "provenance": provenance, "languages": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(summarize(args.scratch, args.ledger), indent=2) + "\n")


if __name__ == "__main__":
    main()
