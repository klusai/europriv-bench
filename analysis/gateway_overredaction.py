"""DEV-only seed-0 inference and exhaustive over-redaction inventory; local CPU only.

Run with PYTHONPATH=src python analysis/gateway_overredaction.py --scratch PATH.
Never loads a test split or existing unverified prediction cache.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path

from europriv_bench.adapters import Res100MoEAdapter
from europriv_bench.gateway import LANGUAGES, gateway_utility, load_gateway, sha256, utility_counts
from europriv_bench.spec import EvalSpec

DATA = Path("/Users/mihai/codespace/research-worktrees/res124")
MODEL = Path("/Users/mihai/codespace/research-artifacts/gateway/seed0/merged")


def write(path, value):
    temp = path.with_suffix(".partial")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def error_fragments(row, receipt):
    """Disjoint connected removed-minus-gold intervals; whitespace alone is not an error."""
    text = row["text"]
    removed, gold = bytearray(len(text)), bytearray(len(text))
    for start, end in receipt["intervals"]:
        removed[start:end] = b"\x01" * (end - start)
    for span in row["spans"]:
        gold[span["start"]:span["end"]] = b"\x01" * (span["end"] - span["start"])
    errors, start = [], None
    for i in range(len(text) + 1):
        active = i < len(text) and removed[i] and not gold[i]
        if active and start is None:
            start = i
        if not active and start is not None:
            end = i
            while start < end and text[start].isspace():
                start += 1
            while end > start and text[end - 1].isspace():
                end -= 1
            if start < end:
                parents = [s for s in receipt["native"] if s["start"] < end and s["end"] > start]
                overlaps = [s for s in row["spans"] if any(
                    p["start"] < s["end"] and p["end"] > s["start"] for p in parents
                )]
                errors.append({
                    "id": f"{row['id']}:{start}:{end}", "conversation": row["id"],
                    "language": row["language"], "family": row["family_id"],
                    "start": start, "end": end, "surface": text[start:end],
                    "characters": sum(not c.isspace() for c in text[start:end]),
                    "context": text[max(0, start - 130):min(len(text), end + 130)],
                    "parents": parents, "overlapping_gold": overlaps,
                    "retained": [s for s in row["retained_spans"] if s["start"] < end and s["end"] > start],
                })
            start = None
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", required=True, type=Path)
    args = parser.parse_args()
    if os.environ.get("EUROPRIV_GATEWAY_PATH") or os.environ.get("EUROPRIV_GATEWAY_MANIFEST"):
        raise ValueError("Unset gateway overrides: this audit pins DEV paths explicitly")
    args.scratch.mkdir(parents=True, exist_ok=True)
    import torch
    from transformers import pipeline

    torch.set_num_threads(4)
    torch.manual_seed(100)
    adapter = Res100MoEAdapter(str(MODEL), batch_size=16)
    # The gateway-trained checkpoint uses 512, unlike Res100MoEAdapter's legacy 256 default.
    adapter._pipe = pipeline(
        "token-classification", model=str(MODEL), aggregation_strategy="simple", device="cpu", dtype="float32",
    )
    if adapter._pipe.tokenizer.model_max_length != 512:
        raise ValueError("Gateway checkpoint tokenizer window drift")
    pin = {
        "checkpoint": str(MODEL), "files": {p.name: sha256(p) for p in sorted(MODEL.iterdir())},
        "packages": {k: importlib.metadata.version(k) for k in ("torch", "transformers")},
        "device": "cpu", "dtype": "float32", "threads": 4, "batch_size": 16,
        "window": 512, "stride": 64, "training_seed": 0, "inference_seed": 100,
        "adapter_sha256": sha256(Path(__file__).resolve().parents[1] / "src/europriv_bench/adapters.py"),
        "operator": "union of all native intervals; no threshold; simple aggregation",
    }
    training = json.loads((MODEL.parent / "training-manifest.json").read_text())
    if training["seed"] != 0 or training["max_length"] != 512:
        raise ValueError("Gateway training seed/window mismatch")
    for line in (MODEL.parent / "gw0.sha256").read_text().splitlines():
        expected, filename = line.split()
        if pin["files"].get(filename) != expected:
            raise ValueError(f"Checkpoint checksum mismatch: {filename}")
    for lang in LANGUAGES:
        spec = EvalSpec.from_yaml(f"evaluations/pii-detection-gateway-traffic-{lang}.yaml")
        spec.dataset.split = "dev"
        spec.dataset.local_path = str(DATA / "artifacts/gateway-traffic-v1/dev.jsonl")
        spec.dataset.manifest_path = str(DATA / "conf/gateway_traffic_manifest.yaml")
        rows = load_gateway(spec)
        assert len(rows) == 200 and all(r["split"] == "dev" for r in rows)
        identity = {**pin, "data": rows.source_metadata, "ids": [r["id"] for r in rows], "split": "dev"}
        target = args.scratch / f"{lang}.predictions.json"
        saved = json.loads(target.read_text()) if target.exists() else {"identity": identity, "receipts": []}
        if saved["identity"] != identity:
            raise ValueError("Prediction identity drift")
        for offset in range(len(saved["receipts"]), len(rows), 16):
            saved["receipts"].extend(adapter.predict_receipts([r["text"] for r in rows[offset:offset + 16]]))
            write(target, saved)
            print(f"{lang}: {len(saved['receipts'])}/{len(rows)}", flush=True)
        coverage = [r["intervals"] for r in saved["receipts"]]
        errors = [e for row, receipt in zip(rows, saved["receipts"], strict=True) for e in error_fragments(row, receipt)]
        score = gateway_utility(rows, coverage)
        assert sum(e["characters"] for e in errors) == score["removed_non_pii_characters"]
        write(args.scratch / f"{lang}.errors.json", errors)
        write(args.scratch / f"{lang}.utility.json", {"score": score, "counts": utility_counts(rows, coverage)})
        print(f"{lang}: {len(errors)} fragments; {score}", flush=True)


if __name__ == "__main__":
    main()
