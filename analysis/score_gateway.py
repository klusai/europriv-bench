#!/usr/bin/env python3
"""Resumable local gateway scoring and paired contract evidence; no publication.

Example: PYTHONPATH=src python analysis/score_gateway.py --scratch /scratch/res126 \
    --label kp-280m --checkpoint /models/kp-280m
Use --adapter presidio or shield for comparators; --compare after all engines finish.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import random
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from europriv_bench.adapters import KpModelAdapter, PresidioAdapter, ShieldAdapter
from europriv_bench.gateway import (
    LANGUAGES,
    cluster_counts,
    load_gateway,
    paired_cluster_bootstrap,
    sha256,
    utility_counts,
)
from europriv_bench.gateway_contract import utility_gate
from europriv_bench.gateway_operator import GatewayDeletionAdapter
from europriv_bench.leaderboard import build_leaderboard
from europriv_bench.runner import run_spec
from europriv_bench.spec import EvalSpec


def write(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def model_pin(checkpoint):
    root = Path(checkpoint)
    files = sorted(p for p in root.iterdir() if p.is_file() and p.suffix in {".json", ".safetensors", ".bin", ".model", ".txt"})
    if not any(p.suffix in {".safetensors", ".bin"} for p in files):
        raise ValueError("local checkpoint has no weights")
    return {p.name: sha256(p) for p in files}


def code_pin():
    paths = [Path(__file__), *Path("src/europriv_bench").glob("*.py")]
    return {str(p.relative_to(Path.cwd()) if p.is_absolute() else p): sha256(p) for p in paths}


def controls(spec, adapter, rows, coverage):
    """Exact replay controls plus bounded, explicitly labelled corrupted-input inference."""
    rng = random.Random(126)
    shuffled = copy.deepcopy(rows)
    labels = [s["label"] for r in shuffled for s in r["spans"]]
    rng.shuffle(labels)
    for row in shuffled:
        for span in row["spans"]:
            span["label"] = labels.pop()
    shuffled_scores = run_spec(spec, adapter, rows=shuffled, redaction_spans=coverage)["scores"]
    shifted = copy.deepcopy(rows)
    for row in shifted:
        for span in row["spans"]:
            length = span["end"] - span["start"]
            # Preserve length and class but destroy original alignment; require non-whitespace support.
            start = rng.randrange(len(row["text"]) - length + 1)
            while not any(not ch.isspace() for ch in row["text"][start:start + length]):
                start = rng.randrange(len(row["text"]) - length + 1)
            span["start"] = start
            span["end"] = span["start"] + length
    subset = rows[:32]
    masked = []
    for row in subset:
        chars = list(row["text"])
        for span in row["spans"]:
            for i in range(span["start"], span["end"]):
                if not chars[i].isspace():
                    chars[i] = " "
        masked.append("".join(chars))
    masked_coverage = adapter.redaction_spans(masked)
    return {
        "seed": 126,
        "none": run_spec(spec, adapter, rows=rows, redaction_spans=[[] for _ in rows])["scores"],
        "full": run_spec(spec, adapter, rows=rows,
                         redaction_spans=[[(0, len(r["text"]))] for r in rows])["scores"],
        "shuffled_labels": shuffled_scores,
        "shuffled_positions": run_spec(spec, adapter, rows=shifted, redaction_spans=coverage)["scores"],
        "masked_input": {"n": len(subset), "selection": "first 32 per language, diagnostic only",
                         "scores": run_spec(spec, adapter, rows=subset, redaction_spans=masked_coverage)["scores"]},
    }


def compare(scratch, *, contract_version=1):
    utility_gate(None, contract_version=contract_version)
    records = [json.loads(p.read_text()) for p in sorted(scratch.glob("*.row.json"))]
    comparisons = []
    for language in LANGUAGES:
        group = {r["run_label"]: r for r in records if r["languages"] == [language]}
        for name in ("kp-280m", "560m-legal", "560m-tab"):
            for baseline in ("presidio", "shield"):
                if name not in group or baseline not in group:
                    continue
                a, b = group[name], group[baseline]
                if contract_version == 3 and a.get("run_pin", {}).get("contract_version") != 3:
                    raise ValueError("Contract v3 cannot relabel historical candidate evaluations")
                if a["dataset"]["data_sha256"] != b["dataset"]["data_sha256"]:
                    raise ValueError("comparison gold hashes differ")
                ac = json.loads((scratch / f"{name}-{language}.clusters.json").read_text())
                bc = json.loads((scratch / f"{baseline}-{language}.clusters.json").read_text())
                if ac["conversation_ids"] != bc["conversation_ids"]:
                    raise ValueError("comparison conversation identities differ")
                slices = {key: paired_cluster_bootstrap(ac[key], bc[key])
                          for key in ("all", "direct", "quasi", "unspecified", "utility")}
                sa, sb = a["scores"]["residual_leakage_v2"], b["scores"]["residual_leakage_v2"]
                utility = slices["utility"]
                utility_result = utility_gate(
                    [utility["ci_low"], utility["ci_high"]] if utility["available"] else None,
                    contract_version=contract_version,
                )
                comparisons.append({
                    "contract_version": contract_version, "utility_gate": utility_result,
                    "candidate": name, "comparator": baseline, "language": language, "slices": slices,
                    "wilson_disjoint": sa["all_leak_rate_ci_high"] < sb["all_leak_rate_ci_low"],
                    "paired_privacy_pass": slices["all"]["available"] and slices["all"]["ci_high"] < 0,
                    "utility_pass": utility_result["pass"],
                    "verdict": "not established: one training seed; dev gold; current operator anchors unverified",
                })
    write(scratch / "comparisons.json", comparisons)
    write(scratch / "gateway-leaderboard.json", build_leaderboard(records))
    print(f"completed rows={len(records)} comparisons={len(comparisons)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--label")
    parser.add_argument("--checkpoint")
    parser.add_argument("--adapter", choices=["kp", "presidio", "shield"], default="kp")
    parser.add_argument("--languages", nargs="+", choices=LANGUAGES, default=LANGUAGES)
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--contract-version", type=int, choices=(1, 2, 3), default=1,
                        help="Pin before scoring; v3 applies only to evaluations after its registration commit")
    args = parser.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=True)
    if args.compare:
        compare(args.scratch, contract_version=args.contract_version)
        return
    if not args.label or (args.adapter == "kp" and not args.checkpoint):
        parser.error("scoring needs --label and KP needs --checkpoint")
    if args.adapter == "kp":
        import torch

        torch.set_num_threads(8)
        torch.set_num_interop_threads(1)
        torch.manual_seed(126)
        adapter = GatewayDeletionAdapter(KpModelAdapter(args.checkpoint))
        weights = model_pin(args.checkpoint)
    elif args.adapter == "presidio":
        adapter = GatewayDeletionAdapter(PresidioAdapter())
        import en_core_web_lg

        weights = {str(p.relative_to(Path(en_core_web_lg.__file__).parent)): sha256(p)
                   for p in Path(en_core_web_lg.__file__).parent.rglob("*") if p.is_file() and "__pycache__" not in str(p)}
    else:
        adapter, weights = ShieldAdapter(), {}
    versions = {}
    for package in ("torch", "transformers", "presidio-analyzer", "spacy", "numpy", "en_core_web_lg"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    pin = {"weights": weights, "code": code_pin(), "versions": versions,
           "device": os.environ.get("EUROPRIV_DEVICE", "cpu"), "model_id": adapter.model_id,
           "harness_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()}
    if args.contract_version != 1:
        pin["contract_version"] = args.contract_version
    for language in args.languages:
        spec = EvalSpec.from_yaml(f"evaluations/pii-detection-gateway-traffic-{language}.yaml")
        rows = load_gateway(spec)
        adapter.prepare([language])
        identity = {**pin, "spec_sha256": sha256(f"evaluations/pii-detection-gateway-traffic-{language}.yaml"),
                    "data": rows.source_metadata, "n": len(rows), "provenance": adapter.provenance()}
        checkpoint = args.scratch / f"{args.label}-{language}.predictions.json"
        saved = json.loads(checkpoint.read_text()) if checkpoint.exists() else {
            "identity": identity, "coverage": [], "receipts": [],
        }
        if saved["identity"] != identity:
            raise ValueError(f"prediction pin drift: {checkpoint}")
        for offset in range(len(saved["coverage"]), len(rows), 16):
            texts = [r["text"] for r in rows[offset:offset + 16]]
            if isinstance(adapter, ShieldAdapter):
                responses = adapter.client.analyze(texts)
                spans = [[(item["start"], item["end"]) for item in response["items"]] for response in responses]
            else:
                spans = adapter.redaction_spans(texts)
            if len(spans) != len(texts):
                raise ValueError("missing prediction rows")
            saved["coverage"].extend(spans)
            if isinstance(adapter, GatewayDeletionAdapter):
                saved["receipts"].extend(adapter.receipts)
            else:
                # Preserve the SAME service response that supplied exact operator coverage.
                outputs = [response["text"] for response in responses]
                saved["receipts"].extend({"input_sha256": hashlib.sha256(t.encode()).hexdigest(),
                                          "output_sha256": hashlib.sha256(o.encode()).hexdigest(), "spans": s}
                                         for t, o, s in zip(texts, outputs, spans, strict=True))
            write(checkpoint, saved)
            print(f"{args.label}/{language}: {len(saved['coverage'])}/{len(rows)}", flush=True)
        coverage, dumps = saved["coverage"], []
        row = run_spec(spec, adapter, rows=rows, redaction_spans=coverage, dumps=dumps,
                       timestamp=datetime.now(UTC).isoformat())
        counts = {key: cluster_counts(rows, coverage, key) for key in ("all", "direct", "quasi", "unspecified")}
        counts["utility"] = utility_counts(rows, coverage)
        row["cluster_intervals"] = {key: paired_cluster_bootstrap(values, [[0, v[1]] for v in values])
                                    for key, values in counts.items()}
        row.update(run_label=args.label, config_status="dev", contamination="unknown", run_pin=copy.deepcopy(pin),
                   uncertainty={"training_seed_count": 1 if args.adapter == "kp" else 0,
                                "training_seed": 0 if args.adapter == "kp" else None,
                                "inference_runs": 1, "inference_seed": 126 if args.adapter == "kp" else None,
                                "bootstrap_seed": 126, "bootstrap_resamples": 2000})
        row["run_pin"].pop("weights")
        row["run_pin"]["weights_manifest_sha256"] = hashlib.sha256(json.dumps(weights, sort_keys=True).encode()).hexdigest()
        counts["conversation_ids"] = [r["id"] for r in rows]
        write(args.scratch / f"{args.label}-{language}.clusters.json", counts)
        write(args.scratch / f"{args.label}-{language}.subjects.json", dumps)
        write(args.scratch / f"{args.label}-{language}.row.json", row)
        control = controls(spec, adapter, rows, coverage)
        if control["shuffled_labels"] != row["scores"]:
            raise AssertionError("v2 must be invariant under label permutation with explicit entity IDs")
        write(args.scratch / f"{args.label}-{language}.controls.json", control)
        print(f"{args.label}/{language}: SCORED {row['scores']}", flush=True)


if __name__ == "__main__":
    main()
