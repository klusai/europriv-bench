"""Dev-only RES-100 calibration and immutable, resumable CPU evaluation.

Raw predictions, gold and receipts live in scratch. See docs/res100-calibration.md.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from analysis.score_res100 import (
    BASE_REVISION,
    GROUPS,
    RESAMPLES,
    RNG_SEED,
    ROOT,
    ci,
    digest,
    row_digest,
    samples,
    score,
    subject_counts,
    utility_counts,
    write,
)
from europriv_bench import metrics
from europriv_bench.adapters import BaseAdapter, PresidioAdapter, ShieldAdapter, _mask_spans, kp_entities_to_bioes
from europriv_bench.crosswalk import to_kp
from europriv_bench.gateway import LANGUAGES, load_gateway
from europriv_bench.runner import run_spec
from europriv_bench.spec import EvalSpec

PROTOCOL = ROOT / "docs/res100-calibration.md"
GRID = [0, .5, .6, .7, .8, .85, .9, .95, .97, .98, .99, .995, .999, .9999, 1.000001]
COMPARATORS = ["base", "kp-280m", "560m-tab", "presidio", "shield"]
ESTATE = Path("/Users/mihai/codespace/rb-gtm-2026-10/estate/scratch")
ARTIFACTS = Path("/Users/mihai/codespace/research-artifacts/res100")
GATEWAY = Path("/Users/mihai/codespace/research-worktrees/res124")


def read(path):
    return json.loads(Path(path).read_text())


def freeze_gold(scratch, split):
    if split == "test":
        validate_freeze(scratch)
        # Reuse pinned original gold, never stream single parquet files.
        prior = ESTATE / "res100-score"
        available = read(prior / "availability.json")
        for config in available["configs"]:
            frozen = read(prior / "gold" / f"{config}.json")
            if row_digest(frozen["rows"]) != frozen["rows_sha256"]:
                raise ValueError("Prior gold hash mismatch")
            save_gold(scratch, split, config, frozen)
    else:
        available = {"configs": ["tab-echr-legal-en-v1"], "unavailable": [
            "general configs: no published dev split", "OpenPII validation: reserved evaluation set"]}
        path = ESTATE / "res125/tab-data/dev.jsonl"
        if digest(path) != "267d01bfc90c0814747720840c07f6b54e69738040756fc972c9e164ecfcfa7e":
            raise ValueError("TAB dev identity changed")
        spec = EvalSpec.from_yaml(ROOT / "evaluations/pii-detection-tab-echr-legal-en.yaml")
        spec.dataset.split = "dev"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        frozen = {"spec": spec.model_dump(mode="json"), "rows": rows, "rows_sha256": row_digest(rows),
                  "dataset": {**spec.dataset.provenance(), "source_sha256": digest(path),
                              "source_manifest_sha256": digest(ESTATE / "res125/tab-manifest.json")}}
        save_gold(scratch, split, spec.dataset.identity, frozen)
    for language in LANGUAGES:
        spec = EvalSpec.from_yaml(ROOT / f"evaluations/pii-detection-gateway-traffic-{language}.yaml")
        spec.dataset.split = split
        spec.dataset.local_path = str(GATEWAY / "artifacts/gateway-traffic-v1")
        spec.dataset.manifest_path = str(GATEWAY / "conf/gateway_traffic_manifest.yaml")
        rows = load_gateway(spec)
        frozen = {"spec": spec.model_dump(mode="json"), "rows": list(rows), "rows_sha256": row_digest(rows),
                  "dataset": {**spec.dataset.provenance(), **rows.source_metadata}}
        config = f"gateway-{language}"
        save_gold(scratch, split, config, frozen)
        available["configs"].append(config)
    write(scratch / split / "availability.json", available)


def save_gold(scratch, split, config, frozen):
    path = scratch / split / "gold" / f"{config}.json"
    if path.exists() and read(path) != frozen:
        raise ValueError(f"Gold drift: {path}")
    write(path, frozen)
    print(f"FROZEN {split}/{config}: {len(frozen['rows'])}", flush=True)


def receipt(text, entities, threshold=0, scheme="kp", normalize=True):
    native, mapped = [], []
    for item in entities:
        if (type(item["start"]) is not int or type(item["end"]) is not int
                or not 0 <= item["start"] < item["end"] <= len(text)):
            raise ValueError("Invalid native character offsets")
        if not np.isfinite(item["score"]) or not 0 <= item["score"] <= 1:
            raise ValueError("Invalid span confidence")
        if item["score"] < threshold:
            continue
        label = item["label"]
        if normalize and label[:2] in {"B-", "I-", "E-", "S-"}:
            label = label[2:]
        span = {"start": item["start"], "end": item["end"], "label": label, "score": item["score"]}
        native.append(span)
        kp = label if scheme == "kp" else to_kp(scheme, label)
        if kp is not None:
            mapped.append({**span, "label": kp})
    intervals = [[e["start"], e["end"]] for e in native]
    return {"native": native, "tags": kp_entities_to_bioes(text, mapped), "intervals": intervals,
            "output": _mask_spans(text, intervals)}


def model_path(name):
    if name.startswith("seed"):
        path = ARTIFACTS / name / "merged"
        manifests = list(path.parent.glob("*.sha256"))
        if len(manifests) != 1:
            raise ValueError("Expected one checkpoint checksum manifest")
        expected = manifests[0].read_text().splitlines()
        for line in expected:
            value, filename = line.split()
            if digest(path / filename) != value:
                raise ValueError(f"Checkpoint hash mismatch: {name}/{filename}")
        if read(path.parent / "training-manifest.json")["seed"] != int(name[4:]):
            raise ValueError("Training seed mismatch")
        return path
    if name == "kp-280m":
        return Path("/Users/mihai/codespace/klusai-models/runs/kp-deid-mdeberta-280m")
    if name == "560m-tab":
        return ESTATE / "res125/runs/res104-tab-seed0"
    from huggingface_hub import snapshot_download

    return Path(snapshot_download("openai/privacy-filter", revision=BASE_REVISION,
                                  allow_patterns=["*.json", "model.safetensors"]))


def predict(scratch, split, name, configs=None):
    import torch

    torch.set_num_threads(4)
    torch.manual_seed(RNG_SEED)
    frozen_thresholds = validate_freeze(scratch) if split == "test" else None
    config_names = configs or read(scratch / split / "availability.json")["configs"]
    ident = {"protocol_sha256": digest(PROTOCOL), "source_sha256": digest(__file__),
             "adapter_sha256": digest(ROOT / "src/europriv_bench/adapters.py"),
             "device": "cpu", "dtype": "float32", "threads": 4, "batch_size": 16,
             "packages": {k: importlib.metadata.version(k) for k in ("torch", "transformers", "numpy")}}
    if ident["packages"]["torch"] != "2.12.0" or ident["packages"]["transformers"] != "5.10.2":
        raise ValueError("Runtime pin mismatch")
    adapter = pipe = None
    if name == "presidio":
        adapter = PresidioAdapter()
        ident.update(threshold=0, language="en", entities=adapter._entities,
                     packages={**ident["packages"], **{k: importlib.metadata.version(k)
                                                      for k in ("spacy", "presidio-analyzer", "en_core_web_lg")}})
    elif name == "shield":
        pin = read(scratch / "shield-pin.json")
        adapter = ShieldAdapter(base_url="http://127.0.0.1:11449", pin=pin)
        ident.update(service_pin_sha256=adapter.client.pin_sha256)
    else:
        path = model_path(name)
        ident.update(checkpoint=str(path), files={p.name: digest(p) for p in sorted(path.iterdir())
                                                 if p.suffix in {".json", ".safetensors", ".model"}})
        from transformers import pipeline

        pipe = pipeline("token-classification", model=str(path), device="cpu", dtype="float32",
                        aggregation_strategy="simple")
        pipe.tokenizer.model_max_length = 256 if name == "base" or name.startswith("seed") else 512
    for config in config_names:
        frozen = read(scratch / split / "gold" / f"{config}.json")
        rows = frozen["rows"]
        stride = 64 if config.startswith("gateway-") or name == "base" or name.startswith("seed") else 0
        identity = {**ident, "gold_sha256": frozen["rows_sha256"], "stride": stride,
                    "max_tokens": pipe.tokenizer.model_max_length if pipe else None,
                    "operator": "native Shield replace" if name == "shield" else "exact literal block union"}
        path = scratch / split / "raw" / f"{name}--{config}.json"
        saved = read(path) if path.exists() else {"identity": identity, "receipts": []}
        if saved["identity"] != identity:
            raise ValueError(f"Prediction pin drift: {path}")
        if name == "shield":
            adapter.prepare(frozen["spec"]["languages"])
        for offset in range(len(saved["receipts"]), len(rows), 16):
            texts = [r["text"] for r in rows[offset:offset + 16]]
            if pipe:
                batches = pipe(texts, batch_size=16, **({"stride": stride} if stride else {}))
                batches = [[{"label": e["entity_group"], "start": int(e["start"]), "end": int(e["end"]),
                             "score": float(e["score"])} for e in entities] for entities in batches]
                additions = [receipt(t, es, scheme="openai" if name == "base" else "kp",
                                     normalize=name.startswith("seed") or name == "base")
                             for t, es in zip(texts, batches, strict=True)]
            elif name == "presidio":
                additions = []
                for text in texts:
                    entities = adapter._analyzer().analyze(text=text, language="en", entities=adapter._entities,
                                                           score_threshold=0)
                    additions.append(receipt(text, [{"start": int(e.start), "end": int(e.end),
                                                      "label": adapter.PRESIDIO_TO_KP[e.entity_type],
                                                      "score": float(e.score)} for e in entities]))
            else:
                additions = []
                for text, response in zip(texts, adapter.client.analyze(texts), strict=True):
                    entities = [{"start": e["start"], "end": e["end"],
                                 "label": adapter.SHIELD_TO_KP[e["entity_type"]]}
                                for e in response["items"] if e["entity_type"] in adapter.SHIELD_TO_KP]
                    additions.append({"native": response, "tags": kp_entities_to_bioes(text, entities),
                                      "intervals": [[e["start"], e["end"]] for e in response["items"]],
                                      "provenance": adapter.provenance()})
            saved["receipts"].extend(additions)
            write(path, saved)
            print(f"{split}/{name}/{config} {len(saved['receipts'])}/{len(rows)}", flush=True)
        threshold = frozen_thresholds["thresholds"][name] if frozen_thresholds and name.startswith("seed") else 0
        if split == "test" or not name.startswith("seed"):
            evaluate(scratch, split, name, config, threshold)


def evaluate(scratch, split, name, config, threshold=0):
    frozen = read(scratch / split / "gold" / f"{config}.json")
    path = scratch / split / "raw" / f"{name}--{config}.json"
    saved = read(path)
    rows = frozen["rows"]
    if len(saved["receipts"]) != len(rows) or saved["identity"]["gold_sha256"] != row_digest(rows):
        raise ValueError("Incomplete or mismatched receipts")
    receipts = saved["receipts"]
    if name.startswith("seed"):
        receipts = [receipt(r["text"], p["native"], threshold) for r, p in zip(rows, receipts, strict=True)]
    intervals = [r["intervals"] for r in receipts]
    seed = int(name[4:]) if name.startswith("seed") else 0 if name in {"kp-280m", "560m-tab"} else None
    identity = {**saved["identity"], "threshold": threshold, "raw_receipt_sha256": digest(path)}
    if config.startswith("gateway-"):
        spec = EvalSpec.model_validate(frozen["spec"])
        adapter = BaseAdapter()
        adapter.name, adapter.model_id = name, name
        row = run_spec(spec, adapter, rows=rows, redaction_spans=intervals, timestamp=datetime.now(UTC).isoformat())
        subjects = metrics.residual_subject_detection_v2(rows, intervals)
        counts = {f"v2_{g}": subject_counts(subjects, len(rows), g) for g in GROUPS}
        counts["over_redaction"] = [utility_counts(r, s) for r, s in zip(rows, intervals, strict=True)]
        indices = np.random.default_rng(RNG_SEED).integers(len(rows), size=(RESAMPLES, len(rows)))
        cis = {k: ci(samples(c, indices)) for k, c in counts.items()}
        removed, total = np.asarray(counts["over_redaction"]).sum(axis=0)
        row["scores"]["over_redaction"] = {"rate": float(removed / total) if total else None,
                                          "ci95": cis["over_redaction"], "nonpii_characters": int(total),
                                          "removed_nonpii_characters": int(removed), "available": bool(total)}
        row.update(training_seed=seed, seed_count=1 if seed is not None else 0,
                   inference_provenance=identity, bootstrap_ci95=cis, config_status="dev")
        row["dataset"] = frozen["dataset"]
    else:
        row, counts = score(frozen, receipts, name, name, seed, identity)
    if name.startswith("seed"):
        row.update(adapter="kp-deid-moe-res100-calibrated", model_id=f"klusai/kp-deid-moe-res100-calibrated-{name}",
                   contamination="unknown", contamination_note="Training/eval subject/source disjointness unaudited")
    row["calibration_protocol_sha256"] = digest(PROTOCOL)
    if split == "test":
        row["calibration_freeze_sha256"] = digest(scratch / "calibration-freeze.json")
    result = {"row": row, "counts": counts}
    write(scratch / split / "results" / f"{name}--{config}.json", result)
    return result


def select(grid):
    feasible = [item for item in grid if item["feasible"]]
    if not feasible:
        raise ValueError("No feasible operating point")
    return min(feasible, key=lambda x: (x["macro_leak"], x["macro_utility"], x["threshold"]))["threshold"]


def calibrate(scratch):
    if (scratch / "calibration-freeze.json").exists():
        return validate_freeze(scratch)
    configs = read(scratch / "dev/availability.json")["configs"]
    references = {c: {n: read(scratch / "dev/results" / f"{n}--{c}.json") for n in COMPARATORS} for c in configs}
    grids, thresholds = {}, {}
    for name in ("seed0", "seed1", "seed2"):
        grid = []
        for threshold in GRID:
            record = {"threshold": threshold, "configs": {}, "feasible": True}
            for config in configs:
                frozen = read(scratch / "dev/gold" / f"{config}.json")
                raw = read(scratch / "dev/raw" / f"{name}--{config}.json")
                if len(raw["receipts"]) != len(frozen["rows"]) or raw["identity"]["gold_sha256"] != frozen["rows_sha256"]:
                    raise ValueError("Incomplete dev predictions")
                coverage = [receipt(r["text"], p["native"], threshold)["intervals"]
                            for r, p in zip(frozen["rows"], raw["receipts"], strict=True)]
                spec = EvalSpec.model_validate(frozen["spec"])
                spec.metrics = ["residual_leakage_v2", "gateway_utility"]
                scores = run_spec(spec, BaseAdapter(), rows=frozen["rows"], redaction_spans=coverage)["scores"]
                bounds = []
                for baseline in references[config].values():
                    if baseline["row"]["inference_provenance"]["gold_sha256"] != frozen["rows_sha256"]:
                        raise ValueError("Dev comparator gold mismatch")
                    bounds.append(baseline["row"]["scores"]["over_redaction"]["rate"])
                utility = scores["gateway_utility"]["over_redaction_rate"]
                passed = all(bound is not None and utility <= bound for bound in bounds)
                record["feasible"] &= passed
                record["configs"][config] = {"scores": scores, "utility_bound": min(bounds), "feasible": passed}
            record["macro_leak"] = float(np.mean([c["scores"]["residual_leakage_v2"]["all_leak_rate"]
                                                  for c in record["configs"].values()]))
            record["macro_utility"] = float(np.mean([c["scores"]["gateway_utility"]["over_redaction_rate"]
                                                     for c in record["configs"].values()]))
            grid.append(record)
            write(scratch / f"dev-grid-{name}.json", grid)
            print(f"GRID {name} {threshold}: feasible={record['feasible']} leak={record['macro_leak']}", flush=True)
        grids[name], thresholds[name] = grid, select(grid)
    pins = {str(p.relative_to(scratch)): digest(p) for folder in ("dev/gold", "dev/raw", "dev/results")
            for p in sorted((scratch / folder).glob("*.json"))}
    frozen = {"thresholds": thresholds, "protocol_sha256": digest(PROTOCOL), "source_sha256": digest(__file__),
              "frozen_at": datetime.now(UTC).isoformat(), "pins": pins,
              "grids": {name: digest(scratch / f"dev-grid-{name}.json") for name in grids}}
    write(scratch / "calibration-freeze.json", frozen)
    print(f"FROZEN THRESHOLDS {thresholds}", flush=True)
    return frozen


def validate_freeze(scratch):
    frozen = read(scratch / "calibration-freeze.json")
    if frozen["protocol_sha256"] != digest(PROTOCOL):
        raise ValueError("Calibration protocol changed after freeze")
    for name, value in frozen["pins"].items():
        if digest(scratch / name) != value:
            raise ValueError(f"Calibration evidence changed: {name}")
    return frozen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "predict", "calibrate", "report"])
    parser.add_argument("--scratch", type=Path, default=ESTATE / "res100-cal")
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--name", choices=[*COMPARATORS, "seed0", "seed1", "seed2"])
    parser.add_argument("--configs", nargs="+")
    args = parser.parse_args()
    if args.action == "freeze":
        freeze_gold(args.scratch, args.split)
    elif args.action == "predict":
        predict(args.scratch, args.split, args.name, args.configs)
    elif args.action == "calibrate":
        calibrate(args.scratch)
    else:
        from analysis.report_res100_calibration import report

        report(args.scratch)


if __name__ == "__main__":
    main()
