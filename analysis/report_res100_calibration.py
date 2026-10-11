"""Import verified comparator receipts and report the complete calibrated seed matrix."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from analysis.calibrate_res100 import COMPARATORS, ESTATE, evaluate, read, validate_freeze
from analysis.report_res100 import import_receipts, paired
from analysis.score_res100 import ROOT, digest, row_digest, write
from europriv_bench.gateway_operator import delete_intervals


def import_comparators(scratch):
    validate_freeze(scratch)
    suite = scratch / "test"
    configs = read(suite / "availability.json")["configs"]
    missing = []
    for config in configs:
        frozen = read(suite / "gold" / f"{config}.json")
        for name in COMPARATORS:
            target = suite / "results" / f"{name}--{config}.json"
            if target.exists():
                continue
            if config.startswith("gateway-") and name != "base":
                source = ESTATE / "res126" / f"{name}-{config.removeprefix('gateway-')}.predictions.json"
                saved = read(source)
                if saved["identity"]["data"]["data_sha256"] != frozen["dataset"]["data_sha256"]:
                    raise ValueError("Prior gateway test gold changed")
                if len(saved["coverage"]) != len(frozen["rows"]):
                    raise ValueError("Incomplete gateway comparator")
                import hashlib

                for row, spans, rec in zip(frozen["rows"], saved["coverage"], saved["receipts"], strict=True):
                    if hashlib.sha256(row["text"].encode()).hexdigest() != rec["input_sha256"]:
                        raise ValueError("Gateway comparator input identity mismatch")
                    if rec["spans"] != spans:
                        raise ValueError("Gateway receipt coverage mismatch")
                    if name != "shield":
                        output = delete_intervals(row["text"], spans)
                        if hashlib.sha256(output.encode()).hexdigest() != rec["output_sha256"]:
                            raise ValueError("Gateway comparator operator receipt mismatch")
                imported = {"identity": {**saved["identity"], "gold_sha256": frozen["rows_sha256"],
                                         "source_receipt_sha256": digest(source),
                                         "source": "RES-126 exact operator replay; original runtime retained"},
                            "receipts": [{"intervals": coverage} for coverage in saved["coverage"]]}
                write(suite / "raw" / f"{name}--{config}.json", imported)
                evaluate(scratch, "test", name, config)
            elif name == "base":
                prior = ESTATE / "res100-score"
                source = prior / "results" / f"base--{config}.json"
                if not source.exists():
                    missing.append([name, config])
                    continue
                result = read(source)
                if result["row"]["inference_provenance"]["gold_sha256"] != row_digest(frozen["rows"]):
                    raise ValueError("Base comparator ordered gold mismatch")
                if result["row"]["prediction_sha256"] != digest(prior / "predictions" / f"base--{config}.json"):
                    raise ValueError("Base comparator receipt changed")
                write(target, result)
            else:
                oldname = "560m-tab-s0" if name == "560m-tab" else name
                result, reason = import_receipts(suite, ESTATE / "res125", config, oldname)
                if result is None:
                    missing.append([name, config, reason])
                else:
                    write(target, result)
    write(scratch / "missing-comparators.json", missing)
    print(f"Missing comparator runs: {missing}", flush=True)


def gates(candidate, other, endpoint="all"):
    comparison = paired(candidate, other)
    a, b = (r["row"]["scores"]["residual_leakage_v2"] for r in (candidate, other))
    delta = comparison["deltas"][f"v2_{endpoint}"]["ci95"]
    utility = comparison["deltas"]["over_redaction"]["ci95"]
    comparison["numerical_gates"] = {
        "disjoint_wilson": bool(a[f"{endpoint}_available"] and b[f"{endpoint}_available"]
                                and a[f"{endpoint}_leak_rate_ci_high"] < b[f"{endpoint}_leak_rate_ci_low"]),
        "paired_privacy": bool(delta and delta[1] < 0),
        "no_worse_utility": bool(utility and utility[1] <= 0),
    }
    comparison["verdict"] = "not established"
    if utility and utility[0] > 0:
        comparison["verdict"] = "loss: over-redaction regression"
    elif delta and delta[0] > 0 and a[f"{endpoint}_leak_rate_ci_low"] > b[f"{endpoint}_leak_rate_ci_high"]:
        comparison["verdict"] = "loss: residual-leak regression"
    return comparison


def report(scratch):
    freeze = validate_freeze(scratch)
    suite = scratch / "test"
    configs = read(suite / "availability.json")["configs"]
    comparisons, rows, spread = [], [], {}
    for config in configs:
        candidates = [read(suite / "results" / f"seed{s}--{config}.json") for s in range(3)]
        baselines = {name: read(suite / "results" / f"{name}--{config}.json") for name in COMPARATORS}
        spread[config] = {}
        for endpoint in ("all", "direct", "quasi", "unspecified"):
            values = [c["row"]["scores"]["residual_leakage_v2"][f"{endpoint}_leak_rate"] for c in candidates]
            available = all(c["row"]["scores"]["residual_leakage_v2"][f"{endpoint}_available"] for c in candidates)
            spread[config][endpoint] = {"available": available, "min": min(values) if available else None,
                                        "max": max(values) if available else None,
                                        "std": float(np.std(values, ddof=1)) if available else None}
        for candidate in candidates:
            row = candidate["row"]
            rows.append(row)
            record = {"config": config, "seed": row["training_seed"], "n_clusters": row["n"],
                      "scores": row["scores"], "comparisons": {}}
            for name, other in baselines.items():
                result = gates(candidate, other)
                if config == "tab-echr-legal-en-v1":
                    result["secondary_TAB_DIRECT"] = gates(candidate, other, "direct")
                result["comparator_scores"] = other["row"]["scores"]
                result["comparator_provenance"] = other["row"]["inference_provenance"]
                result["legacy_zero_floor"] = "not applicable"
                if config in {"ro-realskeleton-v1", "pl-realskeleton-v1"}:
                    anchor = row["scores"]["national_id_leakage"]
                    result["legacy_zero_floor"] = ("unavailable" if not anchor["decode_bearing_total"] else
                                                    "loss" if anchor["leak_rate"] > 0 else "tie; no equivalence claim")
                    if result["legacy_zero_floor"] == "loss":
                        result["verdict"] = "loss: legacy zero-floor regression"
                record["comparisons"][name] = result
            comparisons.append(record)
    numerical = {}
    for config in configs:
        numerical[config] = {name: all(all(r["comparisons"][name]["numerical_gates"].values())
                                      and r["comparisons"][name]["legacy_zero_floor"] not in {"loss", "unavailable"}
                                      for r in comparisons if r["config"] == config) for name in COMPARATORS}
    losses = [dict(config=r["config"], seed=r["seed"], comparator=n, verdict=c["verdict"])
              for r in comparisons for n, c in r["comparisons"].items() if c["verdict"].startswith("loss")]
    result = {"issue": "RES-100", "calibration_freeze": freeze, "candidate_seeds": [0, 1, 2], "seed_count": 3,
              "availability": read(suite / "availability.json"), "comparisons": comparisons,
              "seed_spread": spread, "all_three_seed_numerical_gates": numerical, "losses": losses,
              "verdict": "loss" if losses else "not established",
              "not_verified": ["native review and source/subject/scenario-family/translation disjointness",
                               "reviewed independent held-out challenge", "empirical attacker re-identification",
                               "semantic utility", "gateway deployment equivalence and CPU load/SLO"],
              "uncertainty": {"bootstrap_resamples": 2000, "rng_seed": 100, "confidence": .95,
                              "unit": "document/conversation; seeds never pooled"}}
    board = read(ROOT / "baselines/leaderboard.json")
    for seed in range(3):
        subset = [row for row in rows if row["training_seed"] == seed]
        if len(subset) != len(configs):
            raise ValueError("Refusing incomplete calibrated seed splice")
        key = f"kp-deid-moe-res100-calibrated::klusai/kp-deid-moe-res100-calibrated-seed{seed}"
        board["entries"][key] = subset
    write(ROOT / "baselines/leaderboard.json", board)
    write(ROOT / "analysis/res100-calibrated-comparison.json", result)
    write(ROOT / "analysis/res100-calibration-record.json", freeze)
    write(scratch / "comparison.json", result)
    lines = ["# RES-100 calibrated three-seed results", "", f"Verdict: **{result['verdict']}**.", "",
             f"Frozen dev thresholds: `{freeze['thresholds']}`. Three independent training seeds; no pooling.", "",
             "Leak: 95% Wilson subject intervals. Utility: 95% document/conversation bootstrap intervals.",
             "Paired deltas against all five comparators and seed spread are in the JSON comparison artifact.", "",
             "| Config | Seed | Clusters | Subjects | Leak % [95% CI] | Non-PII removed % [95% CI] |",
             "|---|---:|---:|---:|---:|---:|"]
    for record in comparisons:
        s = record["scores"]["residual_leakage_v2"]
        u = record["scores"]["over_redaction"]
        interval = u["ci95"]
        utility = f"{100*u['rate']:.3f} [{100*interval[0]:.3f}, {100*interval[1]:.3f}]" if interval else "unavailable"
        lines.append(f"| {record['config']} | {record['seed']} | {record['n_clusters']} | {s['all_subjects_total']} | "
                     f"{100*s['all_leak_rate']:.2f} [{100*s['all_leak_rate_ci_low']:.2f}, "
                     f"{100*s['all_leak_rate_ci_high']:.2f}] | {utility} |")
    lines.extend(["", "No contract win is established: review/disjointness and service/load gates remain unverified.",
                  "Gateway test partitions retain dev status; OpenPII retains its actual validation split.",
                  "Historical uncalibrated rows are retained. Every reported score comes from the harness."])
    (ROOT / "docs/res100-calibrated-results.md").write_text("\n".join(lines) + "\n")
    print(f"Spliced {len(rows)} calibrated rows; verdict={result['verdict']}", flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, default=ESTATE / "res100-cal")
    parser.add_argument("--import-comparators", action="store_true")
    args = parser.parse_args()
    (import_comparators if args.import_comparators else report)(args.scratch)
