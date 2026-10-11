#!/usr/bin/env python3
"""Score the pinned Shield HTTP baseline; checkpoint tags per batch for resumable local runs.

Existing published benchmark sources only. Download single-file parquet without streaming.
Outputs stay under --scratch; splice reviewed, completed rows into the board separately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from europriv_bench.adapters import ShieldAdapter
from europriv_bench.runner import _rows_to_gold, run_spec
from europriv_bench.spec import EvalSpec

CONFIGS = ("tab-echr-legal-en", "en", "ro-realskeleton", "pl-realskeleton", "de", "es", "fr", "it", "nl")


def detection_intervals(gold: list[list[str]], pred: list[list[str]]) -> dict:
    """Paired document bootstrap of the harness's micro F1/F2; seed 122, 2,000 resamples."""
    import numpy as np
    from seqeval.scheme import IOBES, Entities

    counts = []
    for true, guessed in zip(gold, pred, strict=True):
        actual = {(e.tag, e.start, e.end) for e in Entities([true], IOBES).entities[0]}
        found = {(e.tag, e.start, e.end) for e in Entities([guessed], IOBES).entities[0]}
        counts.append((len(actual & found), len(actual), len(found)))
    counts = np.array(counts)
    rng = np.random.default_rng(122)
    totals = counts[rng.integers(len(counts), size=(2000, len(counts)))].sum(axis=1)
    result = {}
    for name, beta2 in (("entity_f1", 1), ("entity_f2", 4)):
        denominator = beta2 * totals[:, 1] + totals[:, 2]
        values = np.divide((1 + beta2) * totals[:, 0], denominator, out=np.zeros(2000), where=denominator != 0)
        total = counts.sum(axis=0)
        point = (1 + beta2) * total[0] / (beta2 * total[1] + total[2]) if total[1] + total[2] else 0
        result[name] = {
            "point": float(point),
            "ci_low": float(np.quantile(values, 0.025)),
            "ci_high": float(np.quantile(values, 0.975)),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--revision", required=True, help="Immutable europriv-bench dataset commit")
    parser.add_argument("--configs", nargs="+", default=list(CONFIGS), choices=CONFIGS)
    args = parser.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import hf_hub_download
    from pyarrow import parquet

    for config in args.configs:
        spec = EvalSpec.from_yaml(f"evaluations/pii-detection-{config}.yaml")
        adapter = ShieldAdapter()
        adapter.prepare(spec.languages)
        source = hf_hub_download(
            spec.dataset.hf_id,
            f"{spec.dataset.config}/test-00000-of-00001.parquet",
            repo_type="dataset",
            revision=args.revision,
        )
        rows = parquet.read_table(source).to_pylist()
        texts, gold = _rows_to_gold(rows)
        identity = {
            "model_id": adapter.model_id,
            "dataset_revision": args.revision,
            "parquet_sha256": hashlib.sha256(Path(source).read_bytes()).hexdigest(),
            "config": config,
            "n": len(rows),
        }
        checkpoint = args.scratch / f"{config}.predictions.json"
        saved = json.loads(checkpoint.read_text()) if checkpoint.exists() else {**identity, "tags": []}
        if any(saved[key] != value for key, value in identity.items()):
            raise ValueError(f"Checkpoint identity mismatch: {checkpoint}")
        tags = saved["tags"]
        for offset in range(len(tags), len(texts), 16):
            tags.extend(adapter.predict_tags(texts[offset : offset + 16]))
            temp = checkpoint.with_suffix(".tmp")
            temp.write_text(json.dumps(saved))
            temp.replace(checkpoint)
            print(f"{config}: {len(tags)}/{len(texts)}", flush=True)
        # Score saved predictions through the real runner, with its common eval-label mask.
        adapter.predict_tags = lambda inputs: tags
        row = run_spec(spec, adapter, rows=rows, timestamp=datetime.now(UTC).isoformat())
        eval_labels = set(row["eval_labels"])
        masked = [[t if t == "O" or t.split("-", 1)[1] in eval_labels else "O" for t in seq] for seq in tags]
        for metric, ci in detection_intervals(gold, masked).items():
            point_key = "f1" if metric == "entity_f1" else "f2"
            assert abs(row["scores"][metric][point_key] - ci.pop("point")) < 1e-12
            row["scores"][metric].update(ci)
        row["dataset"].update(revision=args.revision, parquet_sha256=identity["parquet_sha256"])
        row["uncertainty"] = {
            "detection": "paired document bootstrap percentile 95%",
            "bootstrap_seed": 122,
            "bootstrap_resamples": 2000,
            "inference_runs": 1,
            "controlled_inference_seed_count": 0,
            "inference_seed": None,
            "leakage": "harness Wilson 95%; see each metric denominator",
        }
        result = args.scratch / f"{config}.row.json"
        result.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n")
        print(f"{config}: scored n={row['n']} F1={row['scores']['entity_f1']['f1']:.6f}", flush=True)


if __name__ == "__main__":
    main()
