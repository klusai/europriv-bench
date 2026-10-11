"""Score gateway-trained MoE defaults on pinned gold; resume and discover new seeds.

CPU only. Raw gold/receipts remain in scratch. No model selection or publication.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from analysis.calibrate_res100 import ESTATE, GATEWAY, read, receipt
from analysis.score_res100 import (
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
from europriv_bench.adapters import BaseAdapter, _mask_spans
from europriv_bench.gateway import load_gateway
from europriv_bench.runner import run_spec
from europriv_bench.spec import EvalSpec

PROTOCOL = ROOT / "docs/gateway-moe-scoring.md"
COMPARATORS = ("base", "res100-seed0", "kp-280m", "560m-tab", "presidio", "shield")


def immutable(path, value):
    if path.exists() and read(path) != value:
        raise ValueError(f"Frozen identity changed: {path}")
    write(path, value)


def freeze(scratch):
    prior = ESTATE / "res100-cal/test"
    availability = read(prior / "availability.json")
    for config in availability["configs"]:
        frozen = read(prior / "gold" / f"{config}.json")
        if row_digest(frozen["rows"]) != frozen["rows_sha256"]:
            raise ValueError("Prior ordered gold hash mismatch")
        if config.startswith("gateway-"):
            spec = EvalSpec.from_yaml(ROOT / f"evaluations/pii-detection-gateway-traffic-{config[8:]}.yaml")
            spec.dataset.local_path = str(GATEWAY / "artifacts/gateway-traffic-v1")
            spec.dataset.manifest_path = str(GATEWAY / "conf/gateway_traffic_manifest.yaml")
            rows = load_gateway(spec)
            if (
                row_digest(rows) != frozen["rows_sha256"]
                or rows.source_metadata["data_sha256"] != frozen["dataset"]["data_sha256"]
            ):
                raise ValueError("Local gateway override differs from pinned comparator gold")
        immutable(scratch / "gold" / f"{config}.json", frozen)
    immutable(scratch / "availability.json", availability)
    return availability["configs"]


def evaluate(frozen, receipts, name, seed, identity):
    rows = frozen["rows"]
    if len(receipts) != len(rows) or identity["gold_sha256"] != row_digest(rows):
        raise ValueError("Incomplete or mismatched receipts")
    intervals = [r["intervals"] for r in receipts]
    if frozen["spec"]["dataset"]["loader"] == "gateway":
        spec = EvalSpec.model_validate(frozen["spec"])
        row = run_spec(
            spec, BaseAdapter(), rows=rows, redaction_spans=intervals, timestamp=datetime.now(UTC).isoformat()
        )
        subjects = metrics.residual_subject_detection_v2(rows, intervals)
        counts = {f"v2_{g}": subject_counts(subjects, len(rows), g) for g in GROUPS}
        counts["over_redaction"] = [utility_counts(r, s) for r, s in zip(rows, intervals, strict=True)]
        indices = np.random.default_rng(RNG_SEED).integers(len(rows), size=(RESAMPLES, len(rows)))
        cis = {k: ci(samples(c, indices)) for k, c in counts.items()}
        removed, total = np.asarray(counts["over_redaction"]).sum(axis=0)
        row["scores"]["over_redaction"] = {
            "rate": float(removed / total) if total else None,
            "ci95": cis["over_redaction"],
            "nonpii_characters": int(total),
            "removed_nonpii_characters": int(removed),
            "available": bool(total),
        }
        row.update(
            training_seed=seed,
            seed_count=1 if seed is not None else 0,
            inference_provenance=identity,
            bootstrap_ci95=cis,
            config_status="dev",
        )
        row["dataset"] = frozen["dataset"]
        row["metric_unavailability"] = {
            "entity_f1_and_legacy": "Gateway gold has whitespace-token collisions; registered v2-only spec retained"
        }
    else:
        row, counts = score(frozen, receipts, name, name, seed, identity)
    row.update(
        adapter=name,
        model_id=name,
        uncertainty={
            "confidence": 0.95,
            "resamples": RESAMPLES,
            "rng_seed": RNG_SEED,
            "bootstrap_unit": "conversation" if frozen["spec"]["dataset"]["loader"] == "gateway" else "document",
            "leakage": "harness Wilson subject-count intervals",
        },
    )
    return {"row": row, "counts": counts}


def checkpoint(path, seed):
    manifests = list(path.parent.glob("*.sha256"))
    if len(manifests) != 1:
        raise ValueError("Checkpoint requires one SHA manifest; unfinished transfers are not scoreable")
    files = {p.name: digest(p) for p in sorted(path.iterdir()) if p.suffix in {".json", ".safetensors"}}
    for line in manifests[0].read_text().splitlines():
        expected, filename = line.split()
        if files.get(filename) != expected:
            raise ValueError(f"Checkpoint checksum mismatch: {filename}")
    training = read(path.parent / "training-manifest.json")
    if training["seed"] != seed or training["max_length"] != 512:
        raise ValueError("Unexpected training seed or window length")
    if read(path / "tokenizer_config.json")["model_max_length"] != 512:
        raise ValueError("Checkpoint default tokenizer window differs from protocol")
    return files


def predict(scratch, configs, path, seed, contract_commit):
    import torch
    from transformers import pipeline

    packages = {k: importlib.metadata.version(k) for k in ("torch", "transformers", "peft", "numpy")}
    if any(packages[k] != v for k, v in {"torch": "2.12.0", "transformers": "5.10.2", "peft": "0.19.1"}.items()):
        raise ValueError(f"Runtime pin mismatch: {packages}")
    torch.set_num_threads(4)
    torch.manual_seed(RNG_SEED)
    identity = {
        "checkpoint": str(path),
        "files": checkpoint(path, seed),
        "training_seed": seed,
        "training_manifest_sha256": digest(path.parent / "training-manifest.json"),
        "protocol_sha256": digest(PROTOCOL),
        "source_sha256": digest(__file__),
        "receipt_source_sha256": digest(ROOT / "analysis/calibrate_res100.py"),
        "adapter_sha256": digest(ROOT / "src/europriv_bench/adapters.py"),
        "device": "cpu",
        "dtype": "float32",
        "threads": 4,
        "batch_size": 16,
        "max_tokens": 512,
        "stride": 64,
        "threshold": 0,
        "aggregation": "simple; normalize remaining BIOES label prefixes",
        "operator": "exact literal block union; all native labels; no threshold tuning",
        "packages": packages,
        "prospective_contract_commit": contract_commit,
        "run_registration": read(scratch / "run-registration.json"),
    }
    pipe = None
    for config in configs:
        frozen = read(scratch / "gold" / f"{config}.json")
        ident = {**identity, "gold_sha256": frozen["rows_sha256"]}
        target = scratch / "predictions" / f"seed{seed}--{config}.json"
        saved = read(target) if target.exists() else {"identity": ident, "receipts": []}
        if saved["identity"] != ident:
            raise ValueError(f"Prediction identity drift: {target}")
        rows = frozen["rows"]
        for offset in range(len(saved["receipts"]), len(rows), 16):
            if pipe is None:
                pipe = pipeline(
                    "token-classification",
                    model=str(path),
                    device="cpu",
                    dtype="float32",
                    aggregation_strategy="simple",
                )
                if pipe.tokenizer.model_max_length != 512:
                    raise ValueError("Runtime tokenizer default drift")
            texts = [r["text"] for r in rows[offset : offset + 16]]
            batches = pipe(texts, batch_size=16, stride=64)
            entities = [
                [
                    {
                        "label": e["entity_group"],
                        "start": int(e["start"]),
                        "end": int(e["end"]),
                        "score": float(e["score"]),
                    }
                    for e in batch
                ]
                for batch in batches
            ]
            saved["receipts"].extend(receipt(t, es) for t, es in zip(texts, entities, strict=True))
            write(target, saved)
            print(f"seed{seed}/{config} {len(saved['receipts'])}/{len(rows)}", flush=True)
        for row, rec in zip(rows, saved["receipts"], strict=True):
            if rec["output"] != _mask_spans(row["text"], rec["intervals"]):
                raise ValueError("Operator receipt output mismatch")
        name = "kp-deid-moe-gateway"
        result = evaluate(frozen, saved["receipts"], name, seed, ident)
        result["row"].update(
            model_id=f"klusai/kp-deid-moe-gateway-seed{seed}",
            prediction_sha256=digest(target),
            contamination="unknown",
            contamination_note="RES-100 corpus + gateway train; source/subject disjointness unaudited",
        )
        if config == "ro-synthetic-v1":
            result["row"].update(
                contamination="in_distribution", contamination_note="RO synthetic training-family overlap"
            )
        write(scratch / "results" / f"seed{seed}--{config}.json", result)
        print(f"SCORED seed{seed}/{config}", flush=True)


def import_comparators(scratch, configs):
    """Replay original operator receipts; never substitute calibrated RES-100 predictions."""
    for config in configs:
        frozen = read(scratch / "gold" / f"{config}.json")
        for name in COMPARATORS:
            target = scratch / "comparators" / f"{name}--{config}.json"
            if target.exists():
                continue
            prior = ESTATE / "res100-cal/test"
            if name == "res100-seed0":
                source = prior / "raw" / f"seed0--{config}.json"
                saved = read(source)
                scored = read(prior / "results" / f"seed0--{config}.json")
                if digest(source) != scored["row"]["inference_provenance"]["raw_receipt_sha256"]:
                    raise ValueError("RES-100 raw receipt changed")
                # Raw native detections are before the calibrated confidence filter.
                receipts = [
                    receipt(r["text"], p["native"], threshold=0)
                    for r, p in zip(frozen["rows"], saved["receipts"], strict=True)
                ]
                identity = {
                    **saved["identity"],
                    "threshold": 0,
                    "source": "RES-100 seed0 raw detections replayed at default threshold 0",
                }
                result = evaluate(frozen, receipts, "kp-deid-moe-res100", 0, identity)
            else:
                result = read(prior / "results" / f"{name}--{config}.json")
                identity = result["row"]["inference_provenance"]
                if "raw_receipt_sha256" in identity:
                    source = prior / "raw" / f"{name}--{config}.json"
                    expected = identity["raw_receipt_sha256"]
                elif "prediction_sha256" in result["row"]:
                    source = ESTATE / "res100-score/predictions" / f"base--{config}.json"
                    expected = result["row"]["prediction_sha256"]
                else:
                    oldname = "560m-tab-s0" if name == "560m-tab" else name
                    source = ESTATE / "res125/predictions" / f"{oldname}--{config.removesuffix('-v1')}.json"
                    expected = identity["source_receipt_sha256"]
                if digest(source) != expected:
                    raise ValueError(f"Comparator receipt changed: {source}")
            if identity["gold_sha256"] != frozen["rows_sha256"]:
                raise ValueError("Comparator ordered gold mismatch")
            result["replay_evidence"] = {"path": str(source), "sha256": digest(source)}
            write(target, result)
        print(f"COMPARATORS {config}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, default=ESTATE / "gw-score")
    parser.add_argument("--checkpoints", type=Path, default=Path("/Users/mihai/codespace/research-artifacts/gateway"))
    parser.add_argument("--seeds", nargs="+", type=int)
    parser.add_argument("--configs", nargs="+")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--splice", action="store_true")
    args = parser.parse_args()
    configs = freeze(args.scratch)
    if args.prepare_only:
        return
    contract_path = ROOT / "src/europriv_bench/gateway_contract.py"
    if not contract_path.exists():
        raise ValueError("Merge the committed prospective contract v3 before inference")
    commit = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", str(contract_path)], text=True).strip()
    if not commit:
        raise ValueError("Contract v3 must be committed before inference")
    immutable(args.scratch / "contract-pin.json", {"commit": commit, "sha256": digest(contract_path)})
    registration = args.scratch / "run-registration.json"
    if not registration.exists():
        write(
            registration,
            {
                "evaluation_started_at": datetime.now(UTC).isoformat(),
                "scoring_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "contract_commit": commit,
                "contract_versions": [2, 3],
            },
        )
    if args.configs:
        if set(args.configs) - set(configs):
            raise ValueError("Unknown configs")
        configs = args.configs
    priority = {c: i for i, c in enumerate(("ro-realskeleton-v1", "pl-realskeleton-v1", "tab-echr-legal-en-v1"))}
    configs.sort(key=lambda c: (priority.get(c, 100), c))
    if not args.report_only:
        paths = sorted(args.checkpoints.glob("seed[0-9]*/merged"))
        if args.seeds is not None:
            paths = [args.checkpoints / f"seed{s}/merged" for s in args.seeds]
        if not paths:
            raise ValueError("No checkpoints found")
        for path in paths:
            predict(args.scratch, configs, path, int(path.parent.name[4:]), commit)
        import_comparators(args.scratch, configs)
    if args.splice or args.report_only:
        from analysis.report_gateway_moe import report

        report(args.scratch, splice=args.splice)


if __name__ == "__main__":
    main()
