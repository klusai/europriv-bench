"""Availability-only continuation of the frozen RES-77 v2 panel; no new sample."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
from pathlib import Path

from analysis import panel_round2 as prior
from analysis.panel_validation import parse_response
from europriv_bench.panel import digest, validate_annotation
from europriv_bench.panel_api import atomic_json

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/validation"
MODELS = ("deepseek/deepseek-v4.1-flash", "google/gemini-2.5-flash", "qwen/qwen3-235b-a22b-2507")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen():
    return {
        **prior.frozen(),
        "protocol_sha256": sha(DOCS / "round3-protocol.md"),
        "model_manifest_sha256": sha(DOCS / "round3-model-manifest.json"),
        "prior_annotations_sha256": sha(DOCS / "round2-panel-annotations.json"),
        "models": list(MODELS),
    }


def request(model, payload, stage):
    result = prior.request(model, payload, stage)
    if model == MODELS[0]:
        manifest = json.loads((DOCS / "round3-model-manifest.json").read_text())
        result["provider"].pop("sort", None)
        result["provider"]["order"] = manifest["preferred_endpoints"]
    return result


def carry_forward(previous, samples):
    """Accept old judgments only when raw, valid, same-sample evidence reproduces them."""
    evidence = json.loads((DOCS / "round2-panel-annotations.json").read_text())
    if evidence["sample_sha256"] != digest(samples):
        raise ValueError("Prior sample changed")
    initial = {c: {m: {} for m in MODELS} for c in samples}
    for path in (previous / "cache").glob("*.json"):
        record = json.loads(path.read_text())
        if "response" not in record or record["request"]["model"] not in MODELS[1:]:
            continue
        model = record["request"]["model"]
        parsed = parse_response(record["response"])
        for config, rows in samples.items():
            batch = rows[:5]
            payload = [{"id": r["id"], "language": r["language"], "text": r["text"]} for r in batch]
            if record["request"] != prior.request(model, payload, "a"):
                continue
            if set(parsed) != {r["id"] for r in batch}:
                raise ValueError("Prior response coverage mismatch")
            for row in batch:
                value = validate_annotation(row, parsed[row["id"]])
                if value != evidence["stage_a"][config][model][row["id"]]:
                    raise ValueError("Prior raw judgment mismatch")
                initial[config][model][row["id"]] = value
    if any(initial[c][m] != evidence["stage_a"][c][m] for c in samples for m in MODELS[1:]):
        raise ValueError("Missing raw evidence for prior judgments")
    return initial


def prepare(source, scratch, previous):
    if (scratch / "frozen.json").exists() or (scratch / "cache/ledger.json").exists():
        raise ValueError("Already prepared; preserve frozen files and liabilities")
    prior.prepare(source, scratch)
    samples = json.loads((scratch / "samples.json").read_text())
    initial = carry_forward(previous, samples)
    ledger = json.loads((previous / "cache/ledger.json").read_text())
    execution = json.loads((DOCS / "round2-execution.json").read_text())
    if digest(ledger) != execution["ledger_sha256"]:
        raise ValueError("Prior ledger changed; reconcile before continuing")
    (scratch / "cache").mkdir(exist_ok=True)
    atomic_json(scratch / "cache/ledger.json", ledger)
    atomic_json(scratch / "carried-annotations.json", initial)
    atomic_json(scratch / "frozen.json", {**frozen(), "sample_sha256": digest(samples)})
    atomic_json(
        scratch / "continuation.json",
        {
            "prior_ledger_sha256": digest(ledger),
            "carried_annotations_sha256": digest(initial),
            "carried_counts": {c: {m: len(v) for m, v in a.items()} for c, a in initial.items()},
        },
    )


def run(scratch, stage, offline=False):
    initial = json.loads((scratch / "carried-annotations.json").read_text())
    evidence = json.loads((DOCS / "round2-panel-annotations.json").read_text())
    expected = {
        c: {m: evidence["stage_a"][c][m] if m in MODELS[1:] else {} for m in MODELS} for c in evidence["stage_a"]
    }
    if initial != expected:
        raise ValueError("Carried annotations changed")
    prior.run(
        scratch,
        stage,
        offline,
        models=MODELS,
        freeze=frozen,
        request_builder=request,
        initial=initial if stage == "a" else None,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--stage", choices=["prepare", "a", "b"], required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=True)
    with (args.scratch / "panel.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.stage == "prepare":
            prepare(args.source, args.scratch, args.previous)
        else:
            run(args.scratch, args.stage, args.offline)


if __name__ == "__main__":
    main()
