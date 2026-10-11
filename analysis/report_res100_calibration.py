"""Import verified comparator receipts and report the complete calibrated seed matrix."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from analysis.calibrate_res100 import COMPARATORS, ESTATE, evaluate, read, receipt, select, validate_freeze
from analysis.report_res100 import import_receipts, paired
from analysis.score_res100 import GROUPS, ROOT, digest, row_digest, subject_counts, utility_counts, write
from europriv_bench import metrics
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
                imported = {
                    "identity": {
                        **saved["identity"],
                        "gold_sha256": frozen["rows_sha256"],
                        "source_receipt_sha256": digest(source),
                        "source": "RES-126 exact operator replay; original runtime retained",
                    },
                    "receipts": [{"intervals": coverage} for coverage in saved["coverage"]],
                }
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
    if candidate["row"].get("dataset", {}).get("loader") == "gateway":
        comparison["unit"] = "conversation"
    a, b = (r["row"]["scores"]["residual_leakage_v2"] for r in (candidate, other))
    delta = comparison["deltas"][f"v2_{endpoint}"]["ci95"]
    utility = comparison["deltas"]["over_redaction"]["ci95"]
    comparison["numerical_gates"] = {
        "disjoint_wilson": bool(
            a[f"{endpoint}_available"]
            and b[f"{endpoint}_available"]
            and a[f"{endpoint}_leak_rate_ci_high"] < b[f"{endpoint}_leak_rate_ci_low"]
        ),
        "paired_privacy": bool(delta and delta[1] < 0),
        "no_worse_utility": bool(utility and utility[1] <= 0),
    }
    comparison["verdict"] = "not established"
    if utility and utility[0] > 0:
        comparison["verdict"] = "loss: over-redaction regression"
    elif delta and delta[0] > 0 and a[f"{endpoint}_leak_rate_ci_low"] > b[f"{endpoint}_leak_rate_ci_high"]:
        comparison["verdict"] = "loss: residual-leak regression"
    return comparison


def export_operator_receipts(scratch, name, config, candidate):
    """Replay the frozen pure operator; verify scored coverage and cluster counts."""
    suite = scratch / "test"
    frozen = read(suite / "gold" / f"{config}.json")
    raw_path = suite / "raw" / f"{name}--{config}.json"
    row = candidate["row"]
    identity = row["inference_provenance"]
    if digest(raw_path) != identity["raw_receipt_sha256"]:
        raise ValueError("Raw detector receipts changed after scoring")
    raw = read(raw_path)
    if row_digest(frozen["rows"]) != identity["gold_sha256"]:
        raise ValueError("Operator replay gold changed")
    receipts = [
        receipt(r["text"], p["native"], identity["threshold"])
        for r, p in zip(frozen["rows"], raw["receipts"], strict=True)
    ]
    coverage = [r["intervals"] for r in receipts]
    if metrics.residual_leakage_v2(frozen["rows"], coverage) != row["scores"]["residual_leakage_v2"]:
        raise ValueError("Replayed calibrated operator disagrees with scored residual leakage")
    subjects = metrics.residual_subject_detection_v2(frozen["rows"], coverage)
    counts = {f"v2_{group}": subject_counts(subjects, len(receipts), group) for group in GROUPS}
    counts["over_redaction"] = [utility_counts(r, spans) for r, spans in zip(frozen["rows"], coverage, strict=True)]
    if any(candidate["counts"][key] != value for key, value in counts.items()):
        raise ValueError("Replayed operator cluster counts differ from paired-score inputs")
    target = suite / "predictions" / f"{name}--{config}.json"
    write(
        target,
        {
            "identity": identity,
            "calibration_freeze_sha256": row["calibration_freeze_sha256"],
            "operator": "frozen native confidence filter then exact literal block union",
            "export_method": "deterministic local operator replay; no new inference or selection",
            "receipts": receipts,
        },
    )
    row["calibrated_prediction_sha256"] = digest(target)


def report(scratch):
    freeze = validate_freeze(scratch)
    for name, threshold in freeze["thresholds"].items():
        grid_path = scratch / f"dev-grid-{name}.json"
        if digest(grid_path) != freeze["grids"][name] or select(read(grid_path)) != threshold:
            raise ValueError("Frozen threshold or dev grid changed after selection")
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
            spread[config][endpoint] = {
                "available": available,
                "min": min(values) if available else None,
                "max": max(values) if available else None,
                "std": float(np.std(values, ddof=1)) if available else None,
            }
        for candidate in candidates:
            row = candidate["row"]
            seed_name = f"seed{row['training_seed']}"
            dev = read(scratch / "dev/raw" / f"{seed_name}--tab-echr-legal-en-v1.json")["identity"]
            identity = row["inference_provenance"]
            for key in ("files", "device", "dtype", "threads", "batch_size", "packages", "adapter_sha256"):
                if identity[key] != dev[key]:
                    raise ValueError(f"Candidate dev/test inference drift: {seed_name}/{key}")
            if identity["threshold"] != freeze["thresholds"][seed_name]:
                raise ValueError("Candidate threshold differs from frozen calibration")
            if config == "ro-synthetic-v1":
                row["contamination"] = "in_distribution"
                row["contamination_note"] = (
                    "Same RES-100 checkpoint: RO synthetic training-family overlap is known; "
                    "calibration does not change contamination status"
                )
            if "national_id_leakage" in row["scores"]:
                row["legacy_availability"] = {
                    "national_id_leakage": row["scores"]["national_id_leakage"]["decode_bearing_total"] > 0,
                    "name_in_context_leakage": row["scores"]["name_in_context_leakage"]["name_subjects_total"] > 0,
                }
                if "tab_reid_leakage" in row["scores"]:
                    row["legacy_availability"]["tab_reid_leakage"] = (
                        row["scores"]["tab_reid_leakage"]["all_subjects_total"] > 0
                    )
            export_operator_receipts(scratch, seed_name, config, candidate)
            write(suite / "results" / f"{seed_name}--{config}.json", candidate)
            rows.append(row)
            record = {
                "config": config,
                "seed": row["training_seed"],
                "n_clusters": row["n"],
                "scores": row["scores"],
                "comparisons": {},
            }
            for name, other in baselines.items():
                result = gates(candidate, other)
                if config == "tab-echr-legal-en-v1":
                    result["secondary_TAB_DIRECT"] = gates(candidate, other, "direct")
                result["comparator_scores"] = other["row"]["scores"]
                result["comparator_provenance"] = other["row"]["inference_provenance"]
                result["legacy_zero_floor"] = "not applicable"
                if config in {"ro-realskeleton-v1", "pl-realskeleton-v1"}:
                    anchor = row["scores"]["national_id_leakage"]
                    result["legacy_zero_floor"] = (
                        "unavailable"
                        if not anchor["decode_bearing_total"]
                        else "loss"
                        if anchor["leak_rate"] > 0
                        else "tie; no equivalence claim"
                    )
                    if result["legacy_zero_floor"] == "loss":
                        result["verdict"] = "loss: legacy zero-floor regression"
                record["comparisons"][name] = result
            comparisons.append(record)
    for config in configs:
        group = [r for r in comparisons if r["config"] == config]
        for metric in ("over_redaction", "entity_f1"):
            field = "rate" if metric == "over_redaction" else "f1"
            values = [r["scores"][metric][field] for r in group if metric in r["scores"]]
            if len(values) == 3 and all(value is not None for value in values):
                spread[config][metric] = {"min": min(values), "max": max(values), "std": float(np.std(values, ddof=1))}
    worst_gateway = {}
    for seed in range(3):
        group = [r for r in comparisons if r["seed"] == seed and r["config"].startswith("gateway-")]
        worst = max(group, key=lambda r: r["scores"]["residual_leakage_v2"]["all_leak_rate"])
        worst_gateway[str(seed)] = {
            "config": worst["config"],
            "n_clusters": worst["n_clusters"],
            "scores": worst["scores"],
        }
    numerical = {}
    for config in configs:
        numerical[config] = {
            name: all(
                all(r["comparisons"][name]["numerical_gates"].values())
                and r["comparisons"][name]["legacy_zero_floor"] not in {"loss", "unavailable"}
                for r in comparisons
                if r["config"] == config
            )
            for name in COMPARATORS
        }
    secondary_tab = {
        name: all(
            all(r["comparisons"][name]["secondary_TAB_DIRECT"]["numerical_gates"].values())
            for r in comparisons
            if r["config"] == "tab-echr-legal-en-v1"
        )
        for name in COMPARATORS
    }
    losses = [
        dict(config=r["config"], seed=r["seed"], comparator=n, verdict=c["verdict"])
        for r in comparisons
        for n, c in r["comparisons"].items()
        if c["verdict"].startswith("loss")
    ]
    anchors = [r for r in comparisons if r["config"] in {"ro-realskeleton-v1", "pl-realskeleton-v1"}]
    anchors_pass = len(anchors) == 6 and all(
        r["scores"]["national_id_leakage"]["decode_bearing_total"] > 0
        and r["scores"]["national_id_leakage"]["leak_rate"] == 0
        for r in anchors
    )
    result = {
        "issue": "RES-100",
        "calibration_freeze": freeze,
        "runtime_provenance": read(scratch / "runtime-provenance.json"),
        "candidate_seeds": [0, 1, 2],
        "seed_count": 3,
        "report_source_sha256": digest(__file__),
        "availability": read(suite / "availability.json"),
        "comparisons": comparisons,
        "seed_spread": spread,
        "worst_gateway_language_per_seed": worst_gateway,
        "seed_spread_scope": "Three trained and individually dev-calibrated checkpoints; not pure fixed-threshold training variance",
        "all_three_seed_numerical_gates": numerical,
        "all_three_seed_TAB_DIRECT_numerical_gates": secondary_tab,
        "legacy_zero_floor_pass_all_seeds": anchors_pass,
        "numerical_gate_scope": "Leak/utility only; neither array overrides global zero-floor or review gates",
        "losses": losses,
        "verdict": "loss" if losses else "not established",
        "not_verified": [
            "native review and source/subject/scenario-family/translation disjointness",
            "reviewed independent held-out challenge",
            "empirical attacker re-identification",
            "semantic utility",
            "gateway deployment equivalence and CPU load/SLO",
        ],
        "contract_lines": {
            "three_seeds": "complete: independent seeds 0/1/2; no best-seed selection",
            "disjoint_wilson_and_paired_leak": "per-config/per-comparator/per-seed gates reported",
            "utility_and_legacy_zero_floors": "per-config/per-comparator/per-seed gates reported",
            "all_eight_gateway_languages": "complete language rows; review/disjointness unverified",
            "reviewed_held_out": "not established",
            "service_load_SLO": "not measured",
        },
        "uncertainty": {
            "bootstrap_resamples": 2000,
            "rng_seed": 100,
            "confidence": 0.95,
            "unit": "document/conversation; seeds never pooled",
        },
    }
    board = read(ROOT / "baselines/leaderboard.json")
    for seed in range(3):
        subset = [row for row in rows if row["training_seed"] == seed]
        if len(subset) != len(configs):
            raise ValueError("Refusing incomplete calibrated seed splice")
        key = f"kp-deid-moe-res100-calibrated::klusai/kp-deid-moe-res100-calibrated-seed{seed}"
        board["entries"][key] = subset
    write(ROOT / "baselines/leaderboard.json", board)
    write(ROOT / "analysis/res100-calibrated-comparison.json", result)
    write(
        ROOT / "analysis/res100-calibration-record.json",
        {
            **freeze,
            "dev_grids": {name: read(scratch / f"dev-grid-{name}.json") for name in freeze["thresholds"]},
        },
    )
    write(scratch / "comparison.json", result)
    write(scratch / "missing-comparators.json", [])
    lines = [
        "# RES-100 calibrated three-seed results",
        "",
        f"Verdict: **{result['verdict']}**.",
        "",
        f"Frozen dev thresholds: `{freeze['thresholds']}`. Three independent training seeds; no pooling.",
        "",
        "Leak: 95% Wilson subject intervals. Utility: 95% document/conversation bootstrap intervals.",
        "Paired deltas against all five comparators and seed spread are in the JSON comparison artifact.",
        "",
        "| Config | Seed | Clusters | Subjects | Leak % [95% CI] | Non-PII removed % [95% CI] |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for record in comparisons:
        s = record["scores"]["residual_leakage_v2"]
        u = record["scores"]["over_redaction"]
        interval = u["ci95"]
        utility = (
            f"{100 * u['rate']:.3f} [{100 * interval[0]:.3f}, {100 * interval[1]:.3f}]" if interval else "unavailable"
        )
        lines.append(
            f"| {record['config']} | {record['seed']} | {record['n_clusters']} | {s['all_subjects_total']} | "
            f"{100 * s['all_leak_rate']:.2f} [{100 * s['all_leak_rate_ci_low']:.2f}, "
            f"{100 * s['all_leak_rate_ci_high']:.2f}] | {utility} |"
        )
    lines.extend(
        [
            "",
            "No contract win is established: review/disjointness and service/load gates remain unverified.",
            f"Legacy RO/PL zero floors across all three seeds: {'pass' if anchors_pass else 'FAIL'}.",
            "Gateway test partitions retain dev status; OpenPII retains its actual validation split.",
            "Historical uncalibrated rows are retained. Every reported score comes from the harness.",
        ]
    )
    lines.extend(
        [
            "",
            "## Spread across the three calibrated seeds",
            "",
            "Ranges and sample standard deviations describe three independently trained, individually",
            "dev-calibrated pipelines. They are not CIs or pure fixed-threshold training variance.",
            "",
            "| Config | All-leak range % | SD, percentage points | Utility range % |",
            "|---|---:|---:|---:|",
        ]
    )
    for config in configs:
        leak = spread[config]["all"]
        utility = spread[config]["over_redaction"]
        interval = f"{100 * leak['min']:.2f}–{100 * leak['max']:.2f}" if leak["available"] else "unavailable"
        deviation = f"{100 * leak['std']:.2f}" if leak["available"] else "unavailable"
        lines.append(f"| {config} | {interval} | {deviation} | {100 * utility['min']:.3f}–{100 * utility['max']:.3f} |")
    lines.extend(
        [
            "",
            "## TAB DIRECT secondary endpoint",
            "",
            "TAB has 127 document clusters and 264 DIRECT identifier subjects per seed.",
            "These endpoint results do not override the legacy zero-floor failures or the other contract gates.",
            "",
            "| Seed | DIRECT leak % [95% Wilson] | Entity F1 [95% bootstrap] |",
            "|---|---:|---:|",
        ]
    )
    for record in comparisons:
        if record["config"] != "tab-echr-legal-en-v1":
            continue
        leak = record["scores"]["residual_leakage_v2"]
        f1 = record["scores"]["entity_f1"]
        lines.append(
            f"| {record['seed']} | {100 * leak['direct_leak_rate']:.2f} "
            f"[{100 * leak['direct_leak_rate_ci_low']:.2f}, {100 * leak['direct_leak_rate_ci_high']:.2f}] | "
            f"{f1['f1']:.3f} [{f1['ci95'][0]:.3f}, {f1['ci95'][1]:.3f}] |"
        )
    (ROOT / "docs/res100-calibrated-results.md").write_text("\n".join(lines) + "\n")
    print(f"Spliced {len(rows)} calibrated rows; verdict={result['verdict']}", flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, default=ESTATE / "res100-cal")
    parser.add_argument("--import-comparators", action="store_true")
    args = parser.parse_args()
    (import_comparators if args.import_comparators else report)(args.scratch)
