#!/usr/bin/env python3
"""RES-101: resumable local scoring of the published OpenPII validation slices.

PYTHONPATH=src python analysis/score_openpii.py --scratch /path/to/scratch --device mps
Writes predictions/results under scratch; never publishes or overwrites a board.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from datetime import UTC, datetime
from pathlib import Path

from score_shield_leaderboard import detection_intervals

from europriv_bench.adapters import KpModelAdapter, PresidioAdapter
from europriv_bench.runner import _load_gold_rows, _rows_to_gold, run_spec
from europriv_bench.spec import EvalSpec

MODELS = {
    "kp-280m": "klusai/kp-deid-mdeberta-280m",
    "560m-legal": "klusai/kp-deid-xlmr-560m-legal",
    "presidio": "presidio-analyzer+en_core_web_lg",
}


def write_json(path: Path, value) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temp.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu", "mps"], default="cpu")
    parser.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    args = parser.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=True)

    import torch
    from huggingface_hub import HfApi, snapshot_download
    from transformers import pipeline

    torch.set_num_threads(4)
    torch.manual_seed(101)
    packages = {
        name: importlib.metadata.version(name)
        for name in ["torch", "transformers", "presidio-analyzer", "spacy", "en_core_web_lg"]
    }
    specs = [EvalSpec.from_yaml(path) for path in sorted(Path("evaluations").glob("*openpii*.yaml"))]
    gold = {spec.dataset.identity: _load_gold_rows(spec) for spec in specs}
    pins_path = args.scratch / "model-pins.json"
    pins = json.loads(pins_path.read_text()) if pins_path.exists() else {}
    results_path = args.scratch / "results.json"
    results = json.loads(results_path.read_text()) if results_path.exists() else []
    for name in args.models:
        model_id = MODELS[name]
        if name == "presidio":
            adapter = PresidioAdapter()
            revision = None
        else:
            if name not in pins:
                pins[name] = HfApi().model_info(model_id).sha
                write_json(pins_path, pins)
            revision = pins[name]
            snapshot = snapshot_download(model_id, revision=revision)
            adapter = KpModelAdapter(model_id)
            adapter._batch_size = 16
            adapter._pipe = pipeline(
                "token-classification", model=snapshot, aggregation_strategy="simple",
                device=args.device, dtype=torch.float32,
            )
        predict = adapter.predict_tags
        for spec in specs:
            rows = gold[spec.dataset.identity]
            texts, tags = _rows_to_gold(rows)
            identity = {
                "model_id": model_id, "model_revision": revision,
                "dataset": {**spec.dataset.provenance(), **rows.source_metadata},
                "gold_sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
                "n": len(rows), "packages": packages, "inference_seed": 101,
                "device": "cpu" if name == "presidio" else args.device, "batch_size": 16,
            }
            checkpoint = args.scratch / f"{name}-{spec.languages[0]}.predictions.json"
            saved = json.loads(checkpoint.read_text()) if checkpoint.exists() else {**identity, "tags": []}
            if any(saved[key] != value for key, value in identity.items()):
                raise ValueError(f"Checkpoint identity mismatch: {checkpoint}")
            predictions = saved["tags"]
            if len(predictions) > len(texts):
                raise ValueError(f"Checkpoint longer than gold: {checkpoint}")
            for offset in range(len(predictions), len(texts), 16):
                batch = predict(texts[offset:offset + 16])
                if len(batch) != len(texts[offset:offset + 16]):
                    raise ValueError("Adapter returned a different number of predictions")
                predictions.extend(batch)
                write_json(checkpoint, saved)
                print(f"{name} {spec.languages[0]}: {len(predictions)}/{len(texts)}", flush=True)
            adapter.predict_tags = lambda inputs: predictions
            result = run_spec(spec, adapter, rows=rows, timestamp=datetime.now(UTC).isoformat())
            labels = set(result["eval_labels"])
            masked = [[t if t == "O" or t.split("-", 1)[1] in labels else "O" for t in seq] for seq in predictions]
            for metric, ci in detection_intervals(tags, masked).items():
                point_key = "f1" if metric == "entity_f1" else "f2"
                assert abs(result["scores"][metric][point_key] - ci.pop("point")) < 1e-12
                result["scores"][metric].update(ci)
            result["model_revision"] = revision
            result["dataset"]["gold_sha256"] = identity["gold_sha256"]
            result["runtime"] = {k: identity[k] for k in ["device", "packages", "batch_size", "inference_seed"]}
            result["uncertainty"] = {
                "method": "document bootstrap, percentile 95%", "resamples": 2000,
                "bootstrap_seed": 122, "inference_seed_count": 1,
                "training_seed_count": None,
                "note": "One fixed checkpoint per model; no multi-seed training comparison.",
            }
            results = [r for r in results if not (
                r["model_id"] == model_id and r["dataset"]["eval_config"] == spec.dataset.identity
            )]
            results.append(result)
            write_json(results_path, results)
            print(
                f"SCORED {name} {spec.languages[0]} {result['scores']['entity_f1']} {result['contamination']}",
                flush=True,
            )
        del predict, adapter
        if args.device == "mps":
            torch.mps.empty_cache()


if __name__ == "__main__":
    main()
