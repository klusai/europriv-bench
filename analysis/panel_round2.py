"""RES-77 v2 pinned local preparation and serial cached three-family panel.

Use --stage prepare --source FINAL_BUILD, then --stage a / --stage b.
Raw text for blind session review is in scratch/blind-{ro,pl}.jsonl.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

from analysis.panel_validation import ANNOTATE, REVIEW, SYSTEM, parse_response, request_for
from europriv_bench.panel import MODELS, candidates, digest, stratum, validate_annotation
from europriv_bench.panel_api import atomic_json
from europriv_bench.panel_round2_api import RetryBudgetClient

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/validation/round2-protocol.md"
SOURCE_COMMIT = "79c7a91c47be20c8d214b05b09c2850fe8049037"
HASHES = {
    "ro": (
        "cf320aebb7fd53c68ebb16e18116cbe0fea1f4e9f6cd8f0cc7d16e49b4daa470",
        "3b03b17125a643d5c1118ff476e61df704dd1458f2a1f9dc53140c3b21ab7bb7",
    ),
    "pl": (
        "bcb99ae771c20e11f2dd77f4cd27560bb97a67d82a7c8240bc834eedef835e29",
        "1fdcf3ee0ba4c3b7d87c16d4be353acc4ddb60bce1fec8fa4a6e84f5c2ea593a",
    ),
}


def frozen():
    return {
        "protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        "system": SYSTEM,
        "annotate": ANNOTATE,
        "review": REVIEW,
        "models": list(MODELS),
    }


def request(model, payload, stage):
    result = request_for(model, payload, stage)
    preferred = (
        ["mistral"]
        if model.startswith("mistralai/")
        else (["google", "google-ai-studio"] if model.startswith("google/") else ["nebius"])
    )
    result["provider"].pop("only", None)
    result["provider"].update(order=preferred, allow_fallbacks=True)
    return result


def prepare(source, scratch):
    samples, populations, manifest = {}, {}, {}
    for lang, expected in HASHES.items():
        config = f"{lang}-realskeleton-v2"
        paths = [source / config / name for name in ("heldout-review.jsonl", "test.jsonl")]
        if tuple(hashlib.sha256(p.read_bytes()).hexdigest() for p in paths) != expected:
            raise ValueError("Frozen source hashes mismatch")
        held, population = [[json.loads(line) for line in p.read_text().splitlines()] for p in paths]
        if len(population) != 1500 or len(held) != 300:
            raise ValueError("Frozen source sizes mismatch")
        # Independently reproduce exclusion/reservation without opening self-review data.
        review_rng, held_rng = random.Random(7711), random.Random(7712)
        reserved = []
        for kind in ("admin", "clinical", "contract", "declaration"):
            indices = [i for i, row in enumerate(population) if stratum(row) == kind]
            excluded = set(review_rng.sample(indices, 25))
            reserved.extend(sorted(held_rng.sample([i for i in indices if i not in excluded], 75)))
        if [r["source_index"] for r in held] != reserved:
            raise ValueError("Reserved sample is not independent of author review")
        rows = []
        for row in held:
            if (
                row["text"] != population[row["source_index"]]["text"]
                or row["spans"] != population[row["source_index"]]["spans"]
                or row["text_sha256"] != hashlib.sha256(row["text"].encode()).hexdigest()
            ):
                raise ValueError("Held-out source row mismatch")
            rows.append({**row, "id": str(row["source_index"]), "sha256": digest(row["text"])})
        samples[config], populations[config] = rows, population
        manifest[config] = {
            "source_commit": SOURCE_COMMIT,
            "license": "CC-BY-4.0",
            "source_url": "https://github.com/klusai/klusai-datasets",
            "heldout_sha256": expected[0],
            "population_sha256": expected[1],
            "strata": dict(Counter(r["stratum"] for r in rows)),
            "samples": [{k: r[k] for k in ("id", "stratum", "sha256", "text_sha256")} for r in rows],
        }
        blind = [{k: r[k] for k in ("id", "language", "stratum", "text", "text_sha256")} for r in rows]
        (scratch / f"blind-{lang}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in blind))
    atomic_json(scratch / "samples.json", samples)
    atomic_json(scratch / "populations.json", populations)
    atomic_json(scratch / "sample-manifest.json", manifest)
    atomic_json(scratch / "frozen.json", {**frozen(), "sample_sha256": digest(samples)})
    print("Prepared 300/language, author-review exclusion verified; blind files omit gold", flush=True)


def run(scratch, stage, offline=False):
    samples = json.loads((scratch / "samples.json").read_text())
    expected = {**frozen(), "sample_sha256": digest(samples)}
    if json.loads((scratch / "frozen.json").read_text()) != expected:
        raise ValueError("Frozen protocol/prompts/sample changed")
    client = RetryBudgetClient(scratch / "cache", expected["protocol_sha256"], offline)
    output_path = scratch / f"stage-{stage}.json"
    output = {c: {m: {} for m in MODELS} for c in samples}
    errors, proposals = [], {}
    a = json.loads((scratch / "stage-a.json").read_text())["annotations"] if stage == "b" else None
    if a is not None:
        if any(set(a[c][m]) != {r["id"] for r in rows} for c, rows in samples.items() for m in MODELS):
            raise ValueError("Stage B requires all 300 valid A outputs per family/language")
        proposals = {
            c: {r["id"]: candidates(r, [a[c][m][r["id"]] for m in MODELS]) for r in rows} for c, rows in samples.items()
        }
        atomic_json(scratch / "candidates.json", proposals)
    try:
        for c, rows in samples.items():
            for start in range(0, len(rows), 5):
                batch = rows[start : start + 5]
                for model in MODELS:
                    payload = [{"id": r["id"], "language": r["language"], "text": r["text"]} for r in batch]
                    if stage == "b":
                        payload = [
                            {"id": r["id"], "text": r["text"], "gold": r["spans"], "candidates": proposals[c][r["id"]]}
                            for r in batch
                        ]
                    raw = client.complete(request(model, payload, stage))
                    try:
                        parsed = parse_response(raw)
                        if set(parsed) != {r["id"] for r in batch}:
                            raise ValueError("Missing/extra document IDs")
                        for r in batch:
                            result = parsed[r["id"]]
                            try:
                                if stage == "a":
                                    result = validate_annotation(r, result)
                                else:
                                    votes = result["votes"]
                                    if (
                                        len(votes) != len(proposals[c][r["id"]])
                                        or {v["id"] for v in votes} != {p["id"] for p in proposals[c][r["id"]]}
                                        or any(
                                            type(v["approve"]) is not bool or not isinstance(v["reason"], str)
                                            for v in votes
                                        )
                                    ):
                                        raise ValueError("Invalid review votes")
                                output[c][model][r["id"]] = result
                            except (KeyError, TypeError, ValueError) as exc:
                                errors.append({"config": c, "model": model, "id": r["id"], "error": str(exc)})
                    except (KeyError, TypeError, ValueError) as exc:
                        errors.extend({"config": c, "model": model, "id": r["id"], "error": str(exc)} for r in batch)
                    atomic_json(
                        output_path, {**expected, "annotations": output, "errors": errors, "spend": client.evidence()}
                    )
                    print(
                        f"{stage} {c} batch={start // 5 + 1}/60 model={model} errors={len(errors)} "
                        f"spend={client.evidence()}",
                        flush=True,
                    )
    finally:
        atomic_json(output_path, {**expected, "annotations": output, "errors": errors, "spend": client.evidence()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--stage", choices=["prepare", "a", "b"], required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=True)
    with (args.scratch / "panel.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.stage == "prepare":
            if (args.scratch / "frozen.json").exists():
                raise ValueError("Already prepared; preserve frozen files")
            prepare(args.source, args.scratch)
        else:
            run(args.scratch, args.stage, args.offline)


if __name__ == "__main__":
    main()
