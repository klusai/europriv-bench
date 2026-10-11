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
    if row["dataset"].get("loader") == "gateway":
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
            "scope": (
                "Single-seed numerical evidence; aggregate seed gate assessed separately; review/disjointness unverified"
            ),
        }
    return result


def pct(value, interval):
    return (
        "unavailable" if interval is None else f"{100 * value:.2f} [{100 * interval[0]:.2f}, {100 * interval[1]:.2f}]"
    )


def seed_summary(records, seeds, version):
    """Require every seed on a fixed config/endpoint; never pool observations."""
    summary = {}
    for config in sorted({r["config"] for r in records}):
        selected = [r for r in records if r["config"] == config]
        if sorted(r["seed"] for r in selected) != seeds:
            raise ValueError(f"Incomplete or duplicate seed records: {config}")
        endpoints = ("all", "DIRECT") if config == "tab-echr-legal-en-v1" else ("all",)
        for endpoint in endpoints:
            passes = {}
            for name in COMPARATORS:
                results = [r["comparisons"][name] for r in selected]
                if endpoint == "DIRECT":
                    results = [r["secondary_TAB_DIRECT"] for r in results]
                passes[name] = len(seeds) >= 3 and all(
                    r["contracts"][version]["numerical_pass"] for r in results
                )
            summary[f"{config}/{endpoint}"] = passes
    return summary


def report(scratch: Path, *, splice=False, decoded=False):
    adapter = "kp-deid-moe-gateway-decoded" if decoded else "kp-deid-moe-gateway"
    artifact = "gateway-decoding" if decoded else "gateway-moe"
    diagnostic_path = scratch / "diagnostic-registration.json"
    diagnostic = read(diagnostic_path) if decoded and diagnostic_path.exists() else None
    execution_path = scratch.parent / "runtime-concurrency.json"
    execution = read(execution_path) if diagnostic and execution_path.exists() else None
    description = ("dev-rejected strict decoding (diagnostic)" if diagnostic else
                   "dev-selected boundary decoding" if decoded else "default operating point")
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
            if diagnostic and (row.get("diagnostic") != diagnostic or row.get("dev_selection_feasible") is not False):
                raise ValueError("Decoded diagnostic row lost its infeasible-selection provenance")
            if "national_id_leakage" in row["scores"]:
                row["legacy_availability"] = {
                    "national_id_leakage": row["scores"]["national_id_leakage"]["decode_bearing_total"] > 0,
                    "name_in_context_leakage": row["scores"]["name_in_context_leakage"]["name_subjects_total"] > 0,
                }
                if "tab_reid_leakage" in row["scores"]:
                    row["legacy_availability"]["tab_reid_leakage"] = (
                        row["scores"]["tab_reid_leakage"]["all_subjects_total"] > 0
                    )
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
                "legacy_availability": row.get("legacy_availability"),
                "metric_unavailability": row.get("metric_unavailability"),
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
            "three_seed_numerical_passes": seed_summary(records, seeds, version),
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
    relocated = len({
        item["replay_evidence"]["original_path"]
        for record in records for item in record["comparisons"].values()
        if "original_path" in item["replay_evidence"]
    })
    output = {
        "candidate": f"gateway-trained MoE; {description}",
        **({"diagnostic": diagnostic, "dev_selection_feasible": False} if diagnostic else {}),
        **({"execution": execution} if execution else {}),
        **({"byte_verified_relocated_receipts": relocated} if relocated else {}),
        "seeds": seeds,
        "seed_count": len(seeds),
        "contract_pin": read(scratch / "contract-pin.json"),
        "availability": availability,
        "report_source_sha256": digest(__file__),
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
        board["entries"][f"{adapter}::klusai/{adapter}-seed{seed}"] = [
            r for r in rows if r["training_seed"] == seed
        ]
    write(board_path, board)
    write(ROOT / f"analysis/{artifact}-comparison.json", output)
    lines = [
        f"# Gateway-trained MoE: {description}",
        "",
        f"Contract v3: **{contracts['3']['verdict']}**. Contract v2: **{contracts['2']['verdict']}**.",
        "",
        *(["Dev selection was infeasible. This is the prospectively amended strict-rule diagnostic,",
           "not a feasible selection or a contract win; see [the amendment](gateway-decoding-diagnostic.md)",
           "and [all dev results](gateway-decoding-dev-results.md).", ""] if diagnostic else []),
        *(["Remaining seed-1 inference used two local CPU workers on disjoint configs, four threads each;",
           "earlier inference was sequential. Model, batches, windows and decoding stayed fixed.",
           "This scheduling change supplies no latency or SLO evidence.", ""] if execution else []),
        *(["Seed 2 extends the same frozen strict diagnostic by replaying verified default CPU receipts.",
           "No decoder selection or new inference was performed for this extension; its registration is",
           "recorded in the comparison JSON under `execution.seed2_extension`.", ""]
          if execution and "seed2_extension" in execution else []),
        *([f"{relocated} comparator receipt paths had moved during scratch archiving. Exact original SHA-256",
           "matches were verified in the archive or preserved copies; scores were unchanged. The comparison",
           "JSON records both original and resolved evidence paths.", ""] if relocated else []),
        f"Training seeds: {seeds}; seed count {len(seeds)}. CPU fp32, saved 512-token window, no threshold tuning.",
        "Leak CIs are 95% Wilson; F1 and utility CIs are 2,000-cluster bootstrap, RNG seed 100.",
        f"Paired candidate-minus-comparator CIs and both verdicts: `analysis/{artifact}-comparison.json`.",
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
    lines += [
        "",
        "## Legacy national-ID zero floors",
        "",
        "Any observed leak fails the frozen anchor under both contracts. Document counts are listed above.",
        "",
        "| Config | Seed | ID subjects | Missed | Legacy leak % [95% Wilson CI] | Zero-floor gate |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for seed, configs_scores in anchors.items():
        for config, item in configs_scores.items():
            s = item["scores"]
            interval = pct(s["leak_rate"], [s["leak_rate_ci_low"], s["leak_rate_ci_high"]])
            lines.append(
                f"| {config} | {seed} | {int(s['decode_bearing_total'])} | {int(s['decode_bearing_missed'])} | "
                f"{interval} | {'PASS' if item['pass'] else 'FAIL'} |"
            )
    lines += [
        "",
        "## TAB DIRECT endpoint",
        "",
        "The separately registered DIRECT endpoint uses the same documents and its own subject denominator.",
        "",
        "| Seed | Documents | DIRECT subjects | V2 DIRECT leak % [95% Wilson CI] |",
        "|---|---:|---:|---:|",
    ]
    for r in records:
        if r["config"] == "tab-echr-legal-en-v1":
            s = r["scores"]["residual_leakage_v2"]
            interval = [s["direct_leak_rate_ci_low"], s["direct_leak_rate_ci_high"]] if s["direct_available"] else None
            lines.append(
                f"| {r['seed']} | {r['n_clusters']} | {int(s['direct_subjects_total'])} | "
                f"{pct(s['direct_leak_rate'], interval)} |"
            )
    lines += [
        "",
        "## Training-seed spread",
        "",
        "Min–max of per-seed point estimates, in percent; these ranges are not confidence intervals.",
        "The per-seed CIs and denominators are above. Repeated gold is never pooled across seeds.",
        "",
        "| Config | Seeds | F1 % range | V2 all leak % range | Non-PII removed % range |",
        "|---|---:|---:|---:|---:|",
    ]
    for config in configs:
        selected = [r["scores"] for r in records if r["config"] == config]
        values = [
            [s["entity_f1"]["f1"] for s in selected if "entity_f1" in s],
            [s["residual_leakage_v2"]["all_leak_rate"] for s in selected if s["residual_leakage_v2"]["all_available"]],
            [s["over_redaction"]["rate"] for s in selected],
        ]
        ranges = [
            f"{100 * min(v):.2f}–{100 * max(v):.2f}"
            if len(v) == len(seeds) and all(x is not None for x in v)
            else "unavailable"
            for v in values
        ]
        lines.append(f"| {config} | {len(seeds)} | " + " | ".join(ranges) + " |")
    lines += [
        "",
        "## Three-seed numerical gate",
        "",
        f"Seed-count requirement: {'met' if len(seeds) >= 3 else 'not met'} ({len(seeds)} training seeds).",
        "Each listed comparator passes disjoint Wilson privacy, paired privacy and utility gates on",
        "the same endpoint for every seed. An empty cell is shown as none; this is not a contract win.",
        "Legacy zero floors are reported above; native review and held-out disjointness remain unverified.",
        "",
        "| Config / endpoint | V2 passing comparators (all seeds) | V3 passing comparators (all seeds) |",
        "|---|---|---|",
    ]
    for endpoint in contracts["3"]["three_seed_numerical_passes"]:
        passing = [
            ", ".join(name for name, passed in contracts[v]["three_seed_numerical_passes"][endpoint].items() if passed)
            or "none"
            for v in ("2", "3")
        ]
        lines.append(f"| {endpoint} | " + " | ".join(passing) + " |")
    lines += [
        "",
        "## Paired anchor and worst-language comparisons",
        "",
        "All deltas below are candidate minus comparator in percentage points (95% cluster bootstrap).",
        "TAB uses its separately registered DIRECT endpoint; other rows use all identifier subjects.",
        "The worst gateway language is descriptive, not a selected replacement for the eight-language matrix.",
        "Numerical pass counts are not contract wins; review/disjointness requirements remain.",
        "",
        "| Config / endpoint | Seed | Comparator | Leak delta [95% CI] | Utility delta [95% CI] | V2 numerical pass | V3 numerical pass |",
        "|---|---:|---|---:|---:|---|---|",
    ]
    for r in records:
        if r["config"] not in {*ANCHORS, "tab-echr-legal-en-v1", worst[str(r["seed"])]}:
            continue
        direct = r["config"] == "tab-echr-legal-en-v1"
        for name, item in r["comparisons"].items():
            item = item["secondary_TAB_DIRECT"] if direct else item
            delta = item["deltas"]["v2_direct" if direct else "v2_all"]
            utility = item["deltas"]["over_redaction"]
            lines.append(
                f"| {r['config']}/{'DIRECT' if direct else 'all'} | {r['seed']} | {name} | "
                f"{pct(delta['candidate_minus_comparator'], delta['ci95'])} | "
                f"{pct(utility['candidate_minus_comparator'], utility['ci95'])} | "
                f"{item['contracts']['2']['numerical_pass']} | {item['contracts']['3']['numerical_pass']} |"
            )
    (ROOT / f"docs/{artifact}-results.md").write_text("\n".join(lines) + "\n")
    return output
