"""Compare complete gateway MoE seed suites under prospective v3 and historical v2."""

from __future__ import annotations

from pathlib import Path

from analysis.calibrate_res100 import read
from analysis.report_res100 import paired
from analysis.score_gateway_moe import COMPARATORS
from analysis.score_res100 import ROOT, digest, write
from europriv_bench.gateway_contract import utility_gate

ANCHORS = ("ro-realskeleton-v1", "pl-realskeleton-v1")


def comparison(candidate, other, endpoint="all"):
    result = paired(candidate, other)
    row = candidate["row"]
    if row["dataset"]["loader"] == "gateway":
        result["unit"] = "conversation"
    a, b = (item["row"]["scores"]["residual_leakage_v2"] for item in (candidate, other))
    delta = result["deltas"][f"v2_{endpoint}"]["ci95"]
    disjoint = bool(
        a[f"{endpoint}_available"]
        and b[f"{endpoint}_available"]
        and a[f"{endpoint}_leak_rate_ci_high"] < b[f"{endpoint}_leak_rate_ci_low"]
    )
    regression = bool(delta and delta[0] > 0 and a[f"{endpoint}_leak_rate_ci_low"] > b[f"{endpoint}_leak_rate_ci_high"])
    result["contracts"] = {}
    for version in (2, 3):
        utility = utility_gate(result["deltas"]["over_redaction"]["ci95"], contract_version=version)
        gates = {
            "disjoint_wilson": disjoint,
            "paired_privacy": bool(delta and delta[1] < 0),
            "utility_noninferiority": utility["pass"],
        }
        verdict = "not established"
        if regression:
            verdict = "loss: residual-leak regression"
        if utility["regression"]:
            verdict = "loss: over-redaction regression"
        result["contracts"][str(version)] = {
            "numerical_gates": gates,
            "numerical_pass": all(gates.values()),
            "utility": utility,
            "verdict": verdict,
            "scope": "Single-seed numerical evidence; review, disjointness and three-seed gates still required",
        }
    return result


def pct(value, interval):
    return (
        "unavailable" if interval is None else f"{100 * value:.2f} [{100 * interval[0]:.2f}, {100 * interval[1]:.2f}]"
    )


def report(scratch: Path, *, splice=False):
    availability = read(scratch / "availability.json")
    configs = availability["configs"]
    files = sorted((scratch / "results").glob("seed*--*.json"))
    seeds = sorted({int(p.name.split("--")[0][4:]) for p in files})
    if not seeds:
        raise ValueError("No scored seeds")
    rows, records = [], []
    for seed in seeds:
        for config in configs:
            path = scratch / "results" / f"seed{seed}--{config}.json"
            if not path.exists():
                raise ValueError(f"Refusing incomplete seed suite: {seed}/{config}")
            candidate = read(path)
            row = candidate["row"]
            predictions = scratch / "predictions" / f"seed{seed}--{config}.json"
            if digest(predictions) != row["prediction_sha256"]:
                raise ValueError("Candidate prediction receipt changed")
            saved = read(predictions)
            if saved["identity"] != row["inference_provenance"] or len(saved["receipts"]) != row["n"]:
                raise ValueError("Candidate prediction identity/count mismatch")
            record = {
                "seed": seed,
                "config": config,
                "n_clusters": row["n"],
                "scores": row["scores"],
                "comparisons": {},
            }
            for name in COMPARATORS:
                other = read(scratch / "comparators" / f"{name}--{config}.json")
                evidence = other["replay_evidence"]
                if digest(evidence["path"]) != evidence["sha256"]:
                    raise ValueError("Comparator source changed")
                result = comparison(candidate, other)
                if config == "tab-echr-legal-en-v1":
                    result["secondary_TAB_DIRECT"] = comparison(candidate, other, "direct")
                result.update(
                    comparator_scores=other["row"]["scores"],
                    comparator_provenance=other["row"]["inference_provenance"],
                    replay_evidence=evidence,
                )
                record["comparisons"][name] = result
            rows.append(row)
            records.append(record)
            print(f"PAIRED seed{seed}/{config}", flush=True)
    anchors = {}
    for seed in seeds:
        anchors[str(seed)] = {}
        for config in ANCHORS:
            scores = next(r for r in records if r["seed"] == seed and r["config"] == config)["scores"]
            legacy = scores["national_id_leakage"]
            anchors[str(seed)][config] = {
                "pass": bool(legacy["decode_bearing_total"] and legacy["leak_rate"] == 0),
                "scores": legacy,
                "interpretation": "Zero is a scoped tie, never a privacy win or equivalence",
            }
    anchor_pass = all(item["pass"] for seed in anchors.values() for item in seed.values())
    contracts = {}
    for version in ("2", "3"):
        losses = [
            {
                "seed": r["seed"],
                "config": r["config"],
                "comparator": name,
                "verdict": c["contracts"][version]["verdict"],
            }
            for r in records
            for name, c in r["comparisons"].items()
            if c["contracts"][version]["verdict"].startswith("loss")
        ]
        contracts[version] = {
            "verdict": "loss" if losses or not anchor_pass else "not established",
            "losses": losses,
            "utility_margin": 0.01 if version == "3" else 0,
            "three_seeds": len(seeds) >= 3,
            "legacy_zero_floors": anchor_pass,
            "numerical_passes": {
                config: {
                    name: all(
                        r["comparisons"][name]["contracts"][version]["numerical_pass"]
                        for r in records
                        if r["config"] == config
                    )
                    for name in COMPARATORS
                }
                for config in configs
            },
            "reviewed_held_out_and_disjointness": "not established",
            "gateway_load_SLO": "not measured",
        }
    worst = {
        str(seed): max(
            (r for r in records if r["seed"] == seed and r["config"].startswith("gateway-")),
            key=lambda r: r["scores"]["residual_leakage_v2"]["all_leak_rate"],
        )["config"]
        for seed in seeds
    }
    output = {
        "candidate": "gateway-trained MoE; default operating point",
        "seeds": seeds,
        "seed_count": len(seeds),
        "contract_pin": read(scratch / "contract-pin.json"),
        "availability": availability,
        "contracts": contracts,
        "legacy_anchors": anchors,
        "comparisons": records,
        "worst_gateway_language": worst,
        "uncertainty": {
            "resamples": 2000,
            "rng_seed": 100,
            "confidence": 0.95,
            "unit": "document/conversation",
            "seed_pooling": False,
        },
        "not_verified": [
            "three independent seeds" if len(seeds) < 3 else "independent training lineage audit",
            "native review and source/subject/scenario-family/translation disjointness",
            "reviewed held-out challenge",
            "service deployment equivalence and CPU load/SLO",
            "semantic utility",
            "empirical attacker re-identification",
        ],
    }
    write(scratch / "comparison.json", output)
    if not splice:
        return output
    board_path = ROOT / "baselines/leaderboard.json"
    board = read(board_path)
    for seed in seeds:
        board["entries"][f"kp-deid-moe-gateway::klusai/kp-deid-moe-gateway-seed{seed}"] = [
            r for r in rows if r["training_seed"] == seed
        ]
    write(board_path, board)
    write(ROOT / "analysis/gateway-moe-comparison.json", output)
    lines = [
        "# Gateway-trained MoE: default operating point",
        "",
        f"Contract v3: **{contracts['3']['verdict']}**. Contract v2: **{contracts['2']['verdict']}**.",
        "",
        f"Training seeds: {seeds}; seed count {len(seeds)}. CPU fp32, saved 512-token window, no threshold tuning.",
        "Leak CIs are 95% Wilson; F1 and utility CIs are 2,000-cluster bootstrap, RNG seed 100.",
        "Paired candidate-minus-comparator CIs and both verdicts: `analysis/gateway-moe-comparison.json`.",
        "",
        "| Config | Seed | Clusters | Subjects | F1 % [95% CI] | V2 leak % [95% CI] | Non-PII removed % [95% CI] |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in records:
        s = r["scores"]["residual_leakage_v2"]
        u = r["scores"]["over_redaction"]
        f = r["scores"].get("entity_f1")
        f1 = pct(f["f1"], f["ci95"]) if f else "unavailable"
        lines.append(
            f"| {r['config']} | {r['seed']} | {r['n_clusters']} | {int(s['all_subjects_total'])} | {f1} | "
            f"{pct(s['all_leak_rate'], [s['all_leak_rate_ci_low'], s['all_leak_rate_ci_high']])} | "
            f"{pct(u['rate'], u['ci95'])} |"
        )
    lines += [
        "",
        f"RO/PL legacy zero floors: {'PASS' if anchor_pass else 'FAIL'}. "
        "All legacy metrics and their Wilson/bootstrap intervals remain in the aggregate artifact.",
        f"Worst gateway language by all-identifier leakage: {worst}.",
        "",
        "Gateway synthetic test stays dev; its overlapping/token-colliding annotations do not support legacy F1/",
        "leakage, so those metrics are unavailable. OpenPII retains validation split. Italian/legal real-skeleton",
        "are unavailable at the frozen source revision. No gold is dropped or relabelled to manufacture scores.",
        "",
        "Comparators retain original runtime, truncation and operators. RES-100 seed0 uses its raw default",
        "predictions before calibration. The TAB comparator is res104-tab-seed0, not 560m-legal.",
        "Base/RES-100 use 256-token windows; candidate uses its saved default of 512. Shield is distinct from Presidio.",
        "",
        "No overall win is established. Unverified: " + "; ".join(output["not_verified"]) + ".",
    ]
    (ROOT / "docs/gateway-moe-results.md").write_text("\n".join(lines) + "\n")
    return output
