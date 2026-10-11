"""Preregistered dev selection and immutable test replay for gateway decoding."""

from __future__ import annotations

import argparse
import importlib.metadata
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from analysis.calibrate_res100 import COMPARATORS, ESTATE, freeze_gold, read, receipt
from analysis.report_res100 import paired
from analysis.score_gateway_moe import checkpoint, evaluate, freeze, immutable, import_comparators
from analysis.score_res100 import ROOT, digest, row_digest, write
from europriv_bench.decoding import RULES, postprocess_spans
from europriv_bench.gateway_contract import utility_gate

PROTOCOL = ROOT / "docs/gateway-decoding.md"
CHECKPOINTS = Path("/Users/mihai/codespace/research-artifacts/gateway")
NAME = "kp-deid-moe-gateway-decoded"


def source_pins():
    return {p: digest(ROOT / p) for p in (
        "docs/gateway-decoding.md", "analysis/score_gateway_decoding.py",
        "src/europriv_bench/decoding.py", "src/europriv_bench/adapters.py",
        "src/europriv_bench/national_id.py", "analysis/score_gateway_moe.py",
        "analysis/calibrate_res100.py", "analysis/score_res100.py",
    )}


def registration(scratch):
    pin = scratch / "registration.json"
    if not pin.exists():
        write(pin, {"registered_at": datetime.now(UTC).isoformat(), "sources": source_pins(),
                    "scoring_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                    "contract_commit": subprocess.check_output(
                        ["git", "log", "-1", "--format=%H", "--", "src/europriv_bench/gateway_contract.py"],
                        text=True).strip(), "contract_versions": [2, 3]})
    saved = read(pin)
    if saved["sources"] != source_pins():
        raise ValueError("Registered decoding sources changed")
    return saved


def predict_raw(folder, configs, seed, registration_record, *, replay=True):
    """Reuse verified default receipts or run resumable CPU inference, without scoring."""
    import torch
    from transformers import pipeline

    path = CHECKPOINTS / f"seed{seed}/merged"
    files = checkpoint(path, seed)
    packages = {k: importlib.metadata.version(k) for k in ("torch", "transformers", "peft", "numpy", "regex")}
    if any(packages[k] != v for k, v in {"torch": "2.12.0", "transformers": "5.10.2", "peft": "0.19.1"}.items()):
        raise ValueError("Runtime pin mismatch")
    identity = {"checkpoint": str(path), "files": files, "training_seed": seed,
                "training_manifest_sha256": digest(path.parent / "training-manifest.json"),
                "packages": packages, "device": "cpu", "dtype": "float32", "threads": 4,
                "batch_size": 16, "max_tokens": 512, "stride": 64, "threshold": 0,
                "aggregation": "simple; normalized BIOES", "registration": registration_record,
                "operator": "exact literal block union"}
    pipe = None
    torch.set_num_threads(4)
    torch.manual_seed(100)
    for config in configs:
        gold = read(folder / "gold" / f"{config}.json")
        if row_digest(gold["rows"]) != gold["rows_sha256"]:
            raise ValueError("Gold hash mismatch")
        ident = {**identity, "gold_sha256": gold["rows_sha256"]}
        target = folder / "raw" / f"seed{seed}--{config}.json"
        old = ESTATE / "gw-score/predictions" / target.name
        oldresult = ESTATE / "gw-score/results" / target.name
        if replay and old.exists() and oldresult.exists():
            original = read(old)
            scored = read(oldresult)["row"]
            if (scored["prediction_sha256"] != digest(old)
                    or original["identity"] != scored["inference_provenance"]
                    or original["identity"]["gold_sha256"] != gold["rows_sha256"]
                    or original["identity"]["files"] != files
                    or len(original["receipts"]) != len(gold["rows"])):
                raise ValueError("Default receipt replay identity mismatch")
            ident.update(replayed_from=str(old), replay_sha256=digest(old), original_identity=original["identity"])
            immutable(target, {"identity": ident, "receipts": original["receipts"]})
            print(f"REPLAY seed{seed}/{config}", flush=True)
            continue
        saved = read(target) if target.exists() else {"identity": ident, "receipts": []}
        if saved["identity"] != ident or len(saved["receipts"]) > len(gold["rows"]):
            raise ValueError("Raw resume identity mismatch")
        for offset in range(len(saved["receipts"]), len(gold["rows"]), 16):
            if pipe is None:
                pipe = pipeline("token-classification", model=str(path), device="cpu", dtype="float32",
                                aggregation_strategy="simple")
                if pipe.tokenizer.model_max_length != 512:
                    raise ValueError("Tokenizer window drift")
            texts = [r["text"] for r in gold["rows"][offset:offset + 16]]
            batches = pipe(texts, batch_size=16, stride=64)
            for text, entities in zip(texts, batches, strict=True):
                native = [{"label": e["entity_group"], "start": int(e["start"]), "end": int(e["end"]),
                           "score": float(e["score"])} for e in entities]
                saved["receipts"].append(receipt(text, native))
            write(target, saved)
            print(f"RAW seed{seed}/{config} {len(saved['receipts'])}/{len(gold['rows'])}", flush=True)


def decoded_result(folder, config, seed, rule, *, dev=False):
    gold = read(folder / "gold" / f"{config}.json")
    rawpath = folder / "raw" / f"seed{seed}--{config}.json"
    raw = read(rawpath)
    if raw["identity"]["gold_sha256"] != row_digest(gold["rows"]) or len(raw["receipts"]) != len(gold["rows"]):
        raise ValueError("Incomplete/mismatched raw receipts")
    receipts = [receipt(r["text"], postprocess_spans(r["text"], p["native"], rule=rule))
                for r, p in zip(gold["rows"], raw["receipts"], strict=True)]
    identity = {**raw["identity"], "decoding_rule": rule, "decoder_sha256": digest(ROOT / "src/europriv_bench/decoding.py"),
                "raw_receipt_sha256": digest(rawpath), "protocol_sha256": digest(PROTOCOL)}
    if dev:
        # Selection uses v2/utility only, including TAB; the gateway evaluation path
        # supplies the same cluster counts without unnecessary legacy metrics.
        gold = {**gold, "spec": {**gold["spec"], "dataset": {**gold["spec"]["dataset"], "loader": "gateway"},
                                "metrics": ["residual_leakage_v2", "gateway_utility"]}}
    result = evaluate(gold, receipts, NAME, seed, identity)
    result["row"].update(model_id=f"klusai/kp-deid-moe-gateway-decoded-seed{seed}", contract_version=3,
                          decoding_rule=rule)
    return result, {"identity": identity, "receipts": receipts}


def select_rule(grid):
    feasible = [r for r in grid if r["feasible"]]
    if not feasible:
        return None
    return min(feasible, key=lambda r: (r["macro_leak"], r["macro_utility"], RULES.index(r["rule"])))["rule"]


def dev(scratch):
    reg = registration(scratch)
    freeze_gold(scratch, "dev")
    folder = scratch / "dev"
    configs = read(folder / "availability.json")["configs"]
    predict_raw(folder, configs, 0, reg, replay=False)
    refs = {}
    for config in configs:
        refs[config] = {}
        for name in COMPARATORS:
            source = ESTATE / "res100-cal/dev/results" / f"{name}--{config}.json"
            other = read(source)
            rawpath = ESTATE / "res100-cal/dev/raw" / source.name
            if digest(rawpath) != other["row"]["inference_provenance"]["raw_receipt_sha256"]:
                raise ValueError("Dev comparator receipt changed")
            immutable(folder / "comparators" / source.name, other)
            refs[config][name] = other
    grid = []
    for rule in RULES:
        record = {"rule": rule, "feasible": True, "configs": {}}
        for config in configs:
            result, _ = decoded_result(folder, config, 0, rule, dev=True)
            gates = {}
            for name, other in refs[config].items():
                delta = paired(result, other)["deltas"]["over_redaction"]
                gates[name] = {**delta, **utility_gate(delta["ci95"], contract_version=3)}
            feasible = all(g["pass"] for g in gates.values())
            record["feasible"] &= feasible
            record["configs"][config] = {"row": result["row"], "utility_gates": gates, "feasible": feasible}
            print(f"DEV {rule}/{config}: feasible={feasible}", flush=True)
        record["macro_leak"] = float(np.mean([r["row"]["scores"]["residual_leakage_v2"]["all_leak_rate"]
                                               for r in record["configs"].values()]))
        record["macro_utility"] = float(np.mean([r["row"]["scores"]["over_redaction"]["rate"]
                                                  for r in record["configs"].values()]))
        grid.append(record)
        write(scratch / "dev-grid.json", grid)
    selected = select_rule(grid)
    pins = {str(p.relative_to(scratch)): digest(p) for sub in ("dev/gold", "dev/raw", "dev/comparators")
            for p in sorted((scratch / sub).glob("*.json"))}
    frozen = {"selected_rule": selected, "registration": reg, "pins": pins,
              "grid_sha256": digest(scratch / "dev-grid.json"), "selection_seed": 0}
    immutable(scratch / "selection.json", frozen)
    write(ROOT / "analysis/gateway-decoding-dev.json", {"selection": frozen, "grid": grid})
    print(f"SELECTED {selected!r}", flush=True)


def test(scratch, seeds, splice):
    reg = registration(scratch)
    selected = read(scratch / "selection.json")
    if selected["registration"] != reg or selected["grid_sha256"] != digest(scratch / "dev-grid.json"):
        raise ValueError("Selection drift")
    for path, sha in selected["pins"].items():
        if digest(scratch / path) != sha:
            raise ValueError(f"Selection evidence drift: {path}")
    rule = selected["selected_rule"]
    if rule is None:
        raise ValueError("No feasible dev decoder: test scoring is not authorized by the preregistration")
    folder = scratch / "test"
    configs = freeze(folder)
    immutable(folder / "contract-pin.json", {"commit": reg["contract_commit"],
                                             "sha256": digest(ROOT / "src/europriv_bench/gateway_contract.py")})
    for seed in seeds:
        predict_raw(folder, configs, seed, reg)
        for config in configs:
            result, predictions = decoded_result(folder, config, seed, rule)
            target = folder / "predictions" / f"seed{seed}--{config}.json"
            immutable(target, predictions)
            result["row"].update(prediction_sha256=digest(target), contamination="unknown",
                                  contamination_note="RES-100 + gateway train; disjointness unaudited")
            write(folder / "results" / target.name, result)
            print(f"SCORED seed{seed}/{config}", flush=True)
    import_comparators(folder, configs)
    from analysis.report_gateway_moe import report

    report(folder, splice=splice, decoded=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("dev", "test"))
    parser.add_argument("--scratch", type=Path, default=ESTATE / "decode-fix")
    parser.add_argument("--seeds", nargs="+", type=int, default=[0])
    parser.add_argument("--splice", action="store_true")
    args = parser.parse_args()
    if args.phase == "dev":
        dev(args.scratch)
    else:
        test(args.scratch, args.seeds, args.splice)


if __name__ == "__main__":
    main()
