"""Build RES-100 main-row comparisons and receipt-paired CIs, then splice complete seeds."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from analysis.score_res100 import RESAMPLES, RNG_SEED, ROOT, ci, digest, row_digest, samples, score, write

HISTORICAL = {
    "base": "privacy-filter::openai/privacy-filter",
    "kp-280m": "kp-model::klusai/kp-deid-mdeberta-280m",
    "560m-legal": "kp-model::klusai/kp-deid-xlmr-560m-legal",
    "presidio": "presidio::presidio-analyzer+en_core_web_lg",
}


def paired(candidate, comparator):
    if (
        candidate["row"]["inference_provenance"]["gold_sha256"]
        != comparator["row"]["inference_provenance"]["gold_sha256"]
    ):
        raise ValueError("Cannot pair different ordered gold")
    n = candidate["row"]["n"]
    indices = np.random.default_rng(RNG_SEED).integers(n, size=(RESAMPLES, n))
    out = {}
    for key, counts in candidate["counts"].items():
        if key not in comparator["counts"]:
            continue
        other = comparator["counts"][key]
        if len(counts) != len(other) or len(counts) != n:
            raise ValueError("Cannot pair different document counts")
        if not np.array_equal(np.asarray(counts)[:, 1], np.asarray(other)[:, 1]):
            raise ValueError("Cannot pair different gold denominators")
        f1 = key == "entity_f1"
        values = samples(counts, indices, f1) - samples(other, indices, f1)
        point = samples(counts, np.arange(n)[None, :], f1)[0] - samples(other, np.arange(n)[None, :], f1)[0]
        out[key] = {"candidate_minus_comparator": float(point) if np.isfinite(point) else None, "ci95": ci(values)}
    return {"n_clusters": n, "resamples": RESAMPLES, "rng_seed": RNG_SEED, "unit": "document", "deltas": out}


def import_receipts(scratch, source, config, name):
    short = config.removesuffix("-v1")
    gp, pp = source / "gold" / f"{short}.json", source / "predictions" / f"{name}--{short}.json"
    if not gp.exists() or not pp.exists():
        return None, "missing RES-125 gold or receipts"
    frozen = json.loads((scratch / "gold" / f"{config}.json").read_text())
    gold_bytes, pred_bytes = gp.read_bytes(), pp.read_bytes()
    oldgold, oldpred = json.loads(gold_bytes), json.loads(pred_bytes)
    gold_hash, pred_hash = hashlib.sha256(gold_bytes).hexdigest(), hashlib.sha256(pred_bytes).hexdigest()
    if oldpred["identity"]["gold_sha256"] != gold_hash:
        raise ValueError(f"Invalid comparator gold hash: {pp}")
    if row_digest(oldgold["rows"]) != frozen["rows_sha256"]:
        return None, "ordered gold differs"
    receipts = oldpred["receipts"]
    if len(receipts) != len(frozen["rows"]):
        return None, f"incomplete comparator receipts ({len(receipts)}/{len(frozen['rows'])})"
    for row, receipt in zip(frozen["rows"], receipts, strict=True):
        if name == "shield":
            native = receipt["native"]
            expected = [[item["start"], item["end"]] for item in native["items"]]
            if receipt["intervals"] != expected or "text" not in native:
                raise ValueError("Shield native receipt mismatch")
        else:
            covered = bytearray(len(row["text"]))
            for start, end in receipt["intervals"]:
                if not 0 <= start < end <= len(covered):
                    raise ValueError("Invalid comparator operator offsets")
                covered[start:end] = b"\x01" * (end - start)
            output = "".join("█" if covered[i] else c for i, c in enumerate(row["text"]))
            if output != receipt["output"]:
                raise ValueError("Comparator output differs from exact coverage")
    identity = {
        **oldpred["identity"],
        "gold_sha256": frozen["rows_sha256"],
        "source_receipt_sha256": pred_hash,
        "source_gold_sha256": gold_hash,
        "source": "RES-125 local rerun; separate from historical main aggregate row",
        "decoding_caveat": "Historical KP simple aggregation did not normalize remaining E/S label prefixes",
    }
    result, counts = score(frozen, receipts, name, name, oldpred["identity"].get("training_seed"), identity)
    return {"row": result, "counts": counts}, None


def replay_result(scratch, result, key, config):
    """Re-score immutable receipts so added summary statistics never require new inference."""
    old = result["row"]
    path = scratch / "predictions" / f"{key}--{config}.json"
    if old["prediction_sha256"] != digest(path):
        raise ValueError(f"Receipts changed after scoring: {path}")
    saved = json.loads(path.read_text())
    frozen = json.loads((scratch / "gold" / f"{config}.json").read_text())
    if row_digest(frozen["rows"]) != old["inference_provenance"]["gold_sha256"]:
        raise ValueError(f"Gold changed after scoring: {config}")
    if saved["identity"] != old["inference_provenance"]:
        raise ValueError(f"Receipt identity differs from scored identity: {path}")
    row, counts = score(
        frozen, saved["receipts"], old["model_id"], old["adapter"], old["training_seed"], old["inference_provenance"]
    )
    row["prediction_sha256"] = old["prediction_sha256"]
    result.update(row=row, counts=counts)
    return result


def report(scratch: Path, receipt_source: Path | None = None, *, splice: bool = True):
    board = json.loads((ROOT / "baselines/leaderboard.json").read_text())
    availability = json.loads((scratch / "availability.json").read_text())
    configs = availability["configs"]
    historic_keys = {**HISTORICAL, "shield": next(k for k in board["entries"] if k.startswith("shield::"))}
    candidates = [json.loads(p.read_text()) for p in sorted((scratch / "results").glob("seed*--*.json"))]
    comparisons = []
    reruns = {}
    for candidate in candidates:
        row = candidate["row"]
        config = row["dataset"].get("eval_config", row["dataset"]["config"])
        replay_result(scratch, candidate, f"seed{row['training_seed']}", config)
        row = candidate["row"]
        row["legacy_availability"] = {
            "national_id_leakage": row["scores"]["national_id_leakage"]["decode_bearing_total"] > 0,
            "name_in_context_leakage": row["scores"]["name_in_context_leakage"]["name_subjects_total"] > 0,
        }
        if "tab_reid_leakage" in row["scores"]:
            row["legacy_availability"]["tab_reid_leakage"] = row["scores"]["tab_reid_leakage"]["all_subjects_total"] > 0
        record = {
            "model_id": row["model_id"],
            "training_seed": row["training_seed"],
            "config": config,
            "n_documents": row["n"],
            "scores": row["scores"],
            "seed_scope": "single-seed",
            "historical_main": {},
            "paired_reruns": {},
        }
        for name, key in historic_keys.items():
            match = [
                r for r in board["entries"][key] if r["dataset"].get("eval_config", r["dataset"]["config"]) == config
            ]
            record["historical_main"][name] = {
                "row": match[0] if match else None,
                "status": "historical aggregate only; paired CI unavailable" if match else "missing main row",
                "protocol_match": "unverified: historical truncation, label decoding and gold revision may differ",
            }
        for name in ("base", "kp-280m", "560m-tab-s0", "560m-tab-s1", "560m-tab-s2", "presidio", "shield"):
            cache_key = (name, config)
            if cache_key not in reruns:
                if name == "base":
                    path = scratch / "results" / f"base--{config}.json"
                    reruns[cache_key] = (
                        (replay_result(scratch, json.loads(path.read_text()), "base", config), None)
                        if path.exists()
                        else (None, "base not scored")
                    )
                elif receipt_source:
                    reruns[cache_key] = import_receipts(scratch, receipt_source, config, name)
                else:
                    reruns[cache_key] = None, "no comparator receipt source supplied"
            other, reason = reruns[cache_key]
            if other is None:
                record["paired_reruns"][name] = {"status": "unverified", "reason": reason}
                continue
            comparison = paired(candidate, other)
            comparison.update(
                comparator_scores=other["row"]["scores"], comparator_provenance=other["row"]["inference_provenance"]
            )
            a, b = row["scores"]["residual_leakage_v2"], other["row"]["scores"]["residual_leakage_v2"]
            delta = comparison["deltas"]["v2_all"]["ci95"]
            utility = comparison["deltas"]["over_redaction"]["ci95"]
            comparison["single_seed_gates"] = {
                "disjoint_wilson": bool(
                    a["all_available"] and b["all_available"] and a["all_leak_rate_ci_high"] < b["all_leak_rate_ci_low"]
                ),
                "paired_leak": bool(delta and delta[1] < 0),
                "no_worse_utility": bool(utility and utility[1] <= 0),
            }
            comparison["status"] = "unverified"
            comparison["reason"] = "three candidate seeds and reviewed held-out/disjointness gates not established"
            if a["all_leak_rate_ci_low"] > b["all_leak_rate_ci_high"] and delta and delta[0] > 0:
                comparison.update(
                    status="loss", reason="single-seed v2 regression: disjoint Wilson and positive paired CI"
                )
            if utility and utility[0] > 0:
                comparison.update(status="loss", reason="over-redaction regression: positive paired CI")
            comparison["legacy_zero_floor"] = "not applicable"
            if config in {"ro-realskeleton-v1", "pl-realskeleton-v1"}:
                ca, cb = row["scores"]["national_id_leakage"], other["row"]["scores"]["national_id_leakage"]
                if ca["decode_bearing_total"] and cb["decode_bearing_total"]:
                    if ca["leak_rate"] == cb["leak_rate"] == 0:
                        comparison["legacy_zero_floor"] = "tie (no equivalence claim)"
                    elif ca["leak_rate"] > 0 and cb["leak_rate"] == 0:
                        comparison.update(status="loss", reason="legacy zero-floor regression")
                        comparison["legacy_zero_floor"] = "loss"
            record["paired_reruns"][name] = comparison
        comparisons.append(record)
    seeds = sorted({r["row"]["training_seed"] for r in candidates})
    required_anchors = {(seed, config) for seed in seeds for config in ("ro-realskeleton-v1", "pl-realskeleton-v1")}
    measured_anchors = {
        (r["training_seed"], r["config"])
        for r in comparisons
        if r["config"] in {"ro-realskeleton-v1", "pl-realskeleton-v1"}
        and r["scores"]["national_id_leakage"]["decode_bearing_total"] > 0
    }
    anchors_complete = bool(required_anchors) and required_anchors == measured_anchors
    regressions = [
        r
        for r in comparisons
        if r["config"] in {"ro-realskeleton-v1", "pl-realskeleton-v1"}
        and r["scores"]["national_id_leakage"]["leak_rate"] > 0
    ]
    measured_losses = [
        {
            "config": record["config"],
            "seed": record["training_seed"],
            "comparator": name,
            "reason": comparison["reason"],
        }
        for record in comparisons
        for name, comparison in record["paired_reruns"].items()
        if comparison["status"] == "loss"
    ]
    utility_losses = [r for r in measured_losses if "over-redaction" in r["reason"]]
    worst = {}
    for item in candidates:
        row = item["row"]
        language = ",".join(row["languages"])
        key = f"seed{row['training_seed']}:{language}"
        value = row["scores"]["residual_leakage_v2"]["all_leak_rate"]
        if key not in worst or value > worst[key]["rate"]:
            worst[key] = {"config": row["dataset"].get("eval_config", row["dataset"]["config"]), "rate": value}
    result = {
        "issue": "RES-100",
        "protocol_sha256": digest(ROOT / "docs/res100-scoring-protocol.json"),
        "candidate_seeds": seeds,
        "seed_count": len(seeds),
        "availability": availability,
        "verdict": "loss" if regressions or measured_losses else "unverified",
        "reason": (
            "measured single-seed regression(s); gateway-wide evidence is also incomplete"
            if regressions or measured_losses
            else "gateway acceptance gates not established"
        ),
        "measured_losses": measured_losses,
        "claims": "Harness scores only; no gateway, latency, multi-seed or empirical re-identification claim",
        "source_sha256": {
            name: digest(ROOT / name)
            for name in (
                "src/europriv_bench/runner.py",
                "src/europriv_bench/leaderboard.py",
                "src/europriv_bench/metrics.py",
                "src/europriv_bench/crosswalk.py",
                "src/europriv_bench/conf/taxonomy.yaml",
                "analysis/report_res100.py",
            )
        },
        "comparisons": comparisons,
        "worst_config_per_language": worst,
        "acceptance_lines": {
            "1_three_seeds_disjoint_wilson": {
                "verdict": "unverified",
                "available_seeds": len(seeds),
                "reason": "three-seed and reviewed held-out gates not established",
            },
            "2_paired_document_bootstrap": {
                "verdict": "unverified",
                "reason": "per-comparison CIs recorded; complete coverage not established",
            },
            "3_no_worse_utility_and_zero_floors": {
                "verdict": "loss" if regressions or utility_losses else "unverified",
                "legacy_anchors": "loss" if regressions else "tie" if anchors_complete else "unverified",
                "utility_regressions": utility_losses,
            },
            "4_all_languages_reviewed_held_out": {
                "verdict": "unverified",
                "reason": "review and source/subject disjointness not established",
            },
            "latency_load": {"verdict": "unverified", "reason": "not measured"},
        },
        "missing_tab_baseline_note": "Main has 560m-legal rows, not a separately identified TAB-trained 560m entry. Explicit TAB-trained seed receipts are reported as RES-125 reruns.",
        "not_verified": [
            "three candidate training seeds",
            "reviewed harder held-out gold and training/eval disjointness",
            "all comparator/config receipt coverage",
            "historical protocol equivalence",
            "gateway CPU load/SLO",
        ],
    }
    write(scratch / "comparison.json", result)
    if splice:
        for seed in seeds:
            subset = [r["row"] for r in candidates if r["row"]["training_seed"] == seed]
            actual = {r["dataset"].get("eval_config", r["dataset"]["config"]) for r in subset}
            if actual != set(configs):
                raise ValueError(f"Refusing partial leaderboard splice: seed{seed}, missing {set(configs) - actual}")
            key = f"kp-deid-moe-res100::klusai/kp-deid-moe-res100-seed{seed}"
            board["entries"][key] = sorted(subset, key=lambda r: (r["spec"], r["dataset"].get("eval_config", "")))
        board["entries"] = dict(sorted(board["entries"].items()))
        write(ROOT / "baselines/leaderboard.json", board)
        write(ROOT / "analysis/res100-comparison.json", result)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--receipt-source", type=Path)
    parser.add_argument("--no-splice", action="store_true")
    args = parser.parse_args()
    report(args.scratch, args.receipt_source, splice=not args.no_splice)
