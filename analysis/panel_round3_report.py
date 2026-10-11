"""Offline round-three agreement, per-type uncertainty, and fail-closed status."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from analysis.panel_report import evaluate, fmt
from analysis.panel_round2 import HASHES, SOURCE_COMMIT
from analysis.panel_round2_report import rate, stats_with_artifacts
from analysis.panel_round3 import DOCS, MODELS, frozen
from europriv_bench.panel import decode_audit, digest, stratum
from europriv_bench.panel_api import atomic_json
from europriv_bench.panel_round2_api import RetryBudgetClient

KINDS = ("admin", "clinical", "contract", "declaration")


def decode_with_ci(rows, config):
    result = decode_audit(rows, config[:2].upper())
    result["ci95"] = rate(result["consistent"], result["subjects"])["ci95"]
    for field in ("dob", "sex"):
        result[f"explicit_{field}_ci95"] = rate(
            result[f"explicit_{field}_consistent"], result[f"explicit_{field}_subjects"]
        )["ci95"]
    return result


def summary(rows, annotations):
    full = [r for r in rows if all(r["id"] in annotations[m] for m in MODELS)]
    stats = stats_with_artifacts(full, annotations, MODELS)
    stats["sampled_n"] = len(rows)
    stats["valid_per_model"] = {m: sum(r["id"] in annotations[m] for r in rows) for m in MODELS}
    stats["artifacts"] = rate(
        sum(sum(bool(annotations[m][r["id"]]["artifacts"]) for m in MODELS) >= 2 for r in full), len(full)
    )
    return stats


def markdown(config, result, execution):
    panel = result["panel"]
    lines = [
        f"# {config}: round-3 external panel",
        "",
        f"Status: **{panel['config_status']}**. All frozen gates must pass for promotion.",
        "",
        "[Preregistration](round3-protocol.md) · [Model selection](round3-model-manifest.json) · "
        "[Reproduction](round3-runbook.md).",
        "",
        f"Data revision: `{SOURCE_COMMIT}` ([datasets PR #23](https://github.com/klusai/klusai-datasets/pull/23)); "
        "CC-BY-4.0 authored synthetic data. Same round-2 holdout: 300/config, 75/type; population 1,500/config.",
        "Sampling seed 7712; generation seed 2026101277 (RO) / 2026101278 (PL); inference seed 77.",
        "One seed per component/language; no repeated-seed inference. 95% CIs: 2,000 document-cluster",
        "bootstrap draws, stratified overall, seed 7701; Wilson intervals for proportions.",
        "",
        "DeepSeek replaces Mistral for availability only. Gemini/Qwen each reuse five frozen RO outputs.",
        "Codex remains supplemental; its prior review is not counted as a required external seat.",
        "Round-2 scores were already known. No new sample, changed prompts, or selected retries.",
        "",
        "| Gate | Result |",
        "|---|---|",
        *[f"| {k} | {'pass' if v else 'fail/unverified'} |" for k, v in panel["gates"].items()],
        "",
        f"Majority-approved gold operations: {panel['majority_gold_errors']}; "
        f"unresolved conflicts: {panel['edit_conflicts']}. These counts need complete B to establish no errors.",
        "Stage-B valid documents: " + ", ".join(f"{m}: {n}" for m, n in panel["valid_reviews_per_model"].items()) + ".",
        "Malformed completed outputs remain missing; no repair/retry of their judgments.",
        "Stage-A/B validation errors: " + json.dumps(panel["execution_errors"], ensure_ascii=False) + ".",
        "",
        "| Type | Complete n / sampled n | DeepSeek / Gemini / Qwen valid A | Majority artifacts [Wilson 95% CI] |",
        "|---|---:|---|---|",
    ]
    groups = [("overall", panel), *panel["by_type"].items()]
    for kind, value in groups:
        ar = value["artifacts"]
        lines.append(
            f"| {kind} | {value['n']} / {value['sampled_n']} | "
            + " / ".join(str(value["valid_per_model"][m]) for m in MODELS)
            + f" | {ar['flagged']}/{ar['n']} {ar['ci95']} |"
        )
    lines += [
        "",
        "Statistics below use only documents with all three valid external outputs. Partial-case",
        "estimates cannot establish a config-wide pass. No complete cases means unavailable CIs.",
        "",
        "| Type | n | Statistic / judge | Estimate [95% CI] |",
        "|---|---:|---|---|",
    ]
    for kind, value in groups:
        if not value["n"]:
            lines.append(f"| {kind} | 0 | Agreement / fluency / naturalness | unavailable |")
        for model, v in value["alpha"].items():
            lines.append(f"| {kind} | {value['n']} | alpha: {model} | {fmt(v['estimate'], v['ci95'])} |")
        for model, ratings in value["ratings"].items():
            for metric, v in ratings.items():
                lines.append(f"| {kind} | {value['n']} | {metric}: {model} | {fmt(v['median'], v['ci95'])} |")
    lines += [
        "",
        "| Population type | ID consistency | Wilson 95% CI | Explicit DOB / sex consistent |",
        "|---|---|---|---|",
    ]
    for kind, d in [("overall", panel["decode"]), *panel["decode_by_type"].items()]:
        lines.append(
            f"| {kind} | {d['consistent']}/{d['subjects']} | {d['ci95']} | "
            f"{d['explicit_dob_consistent']}/{d['explicit_dob_subjects']} / "
            f"{d['explicit_sex_consistent']}/{d['explicit_sex_subjects']} |"
        )
    lines += [
        "",
        "Decode includes checksum, known DOB/sex, raw national-ID gold coverage and explicit clinical fields.",
        "Per-field Wilson CIs and exhaustive disagreements are in the companion JSON/CSV. Absent independent",
        "fields outside clinical records are not invented. No registry or address/bank lookup was performed.",
        "",
        f"Cumulative round-2+3 usage.cost: ${execution['actual_usd']:.8f}; "
        f"unknown-cost reservations: ${execution['reserved_usd']:.8f}; "
        f"conservative liability: ${execution['known_plus_reserved_usd']:.8f} / $25.",
        "Prior liabilities are retained; failed requests are not assumed free. See round3-execution.json.",
        "Transport stop: "
        + "; ".join(
            f"HTTP {e['http_status']} from {e['provider']} for {e['model']}" for e in execution["transport_errors"]
        )
        + ". Full sanitized fallback trail and raw-error hash are in round3-execution.json.",
        "",
        "Limitations: shared authored templates and correlated model errors; bootstrap CIs condition on",
        "these judges/template family and do not measure unseen-template or model-family uncertainty.",
        "No human/native-speaker validation, clinical/legal certification, privacy guarantee, real-world",
        "representativeness, or CI-disjoint model-performance win was verified. Agreement is not accuracy",
        "or human IAA. The supplemental Codex review used shared template-assisted context (round 2).",
        "No gold edits or publication. Failed/incomplete gates keep dev, never citable-validated.",
        "",
    ]
    return "\n".join(lines)


def generate(scratch, out):
    out.mkdir(parents=True, exist_ok=True)
    samples = json.loads((scratch / "samples.json").read_text())
    populations = json.loads((scratch / "populations.json").read_text())
    for config, rows in populations.items():
        raw = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode()
        if hashlib.sha256(raw).hexdigest() != HASHES[config[:2]][1]:
            raise ValueError("Population differs from pinned data revision")
    expected = {**frozen(), "sample_sha256": digest(samples)}
    if json.loads((scratch / "frozen.json").read_text()) != expected:
        raise ValueError("Frozen protocol/sample mismatch")
    stages = {}
    for stage in ("a", "b"):
        path = scratch / f"stage-{stage}.json"
        stages[stage] = json.loads(path.read_text()) if path.exists() else {}
        if stages[stage] and any(stages[stage][k] != v for k, v in expected.items()):
            raise ValueError("Stage provenance mismatch")
    if not stages["a"]:
        raise ValueError("Stage A has not run")
    execution = RetryBudgetClient(scratch / "cache", expected["protocol_sha256"], offline=True).evidence()
    execution["inherited_round2"] = json.loads((DOCS / "round2-execution.json").read_text())
    execution["new_round3_actual_usd"] = execution["actual_usd"] - execution["inherited_round2"]["actual_usd"]
    execution["new_round3_attempts"] = execution["attempts"] - execution["inherited_round2"]["attempts"]
    execution["new_round3_rate_limited_attempts"] = (
        execution["rate_limited_attempts"] - execution["inherited_round2"]["rate_limited_attempts"]
    )
    execution["successful_response_providers"] = {}
    execution["transport_errors"] = []
    for path in (scratch / "cache").glob("*.json"):
        data = json.loads(path.read_text())
        if "http_status" in data:
            error = json.loads(data["body"]).get("error", {})
            metadata = error.get("metadata", {})
            execution["transport_errors"].append(
                {
                    "file": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "model": data["request"]["model"],
                    "http_status": data["http_status"],
                    "retry_after": data.get("retry_after"),
                    "message": error.get("message"),
                    "provider": metadata.get("provider_name"),
                    "previous_errors": [
                        {k: e.get(k) for k in ("code", "provider_name")} for e in metadata.get("previous_errors", [])
                    ],
                }
            )
        if "response" in data:
            execution["successful_response_providers"].setdefault(data["request"]["model"], set()).add(
                data["response"].get("provider", "unreported")
            )
    execution["successful_response_providers"] = {
        m: sorted(v) for m, v in execution["successful_response_providers"].items()
    }
    atomic_json(out / "round3-execution.json", execution)
    atomic_json(out / "round3-sample-manifest.json", json.loads((scratch / "sample-manifest.json").read_text()))
    errors = stages["a"]["errors"] + stages["b"].get("errors", [])
    atomic_json(
        out / "round3-panel-annotations.json",
        {
            **expected,
            "stage_a": stages["a"]["annotations"],
            "stage_b": stages["b"].get("annotations", {}),
            "errors": errors,
            "continuation": json.loads((scratch / "continuation.json").read_text()),
        },
    )
    for config, rows in samples.items():
        annotations = stages["a"]["annotations"][config]
        reviews = stages["b"].get("annotations", {}).get(config, {})
        panel, disagreements, overlays = evaluate(
            config, populations[config], rows, annotations, reviews, errors, models=MODELS
        )
        panel["valid_reviews_per_model"] = {m: len(reviews.get(m, {})) for m in MODELS}
        panel.update(summary(rows, annotations))
        panel.update(seed=7712, inference_seed=77, seed_count=1)
        panel["by_type"] = {k: summary([r for r in rows if r["stratum"] == k], annotations) for k in KINDS}
        panel["decode"] = decode_with_ci(populations[config], config)
        panel["decode_by_type"] = {
            k: decode_with_ci([r for r in populations[config] if stratum(r) == k], config) for k in KINDS
        }
        result = {**expected, "source_commit": SOURCE_COMMIT, "panel": panel}
        atomic_json(out / f"{config}-round3-results.json", result)
        atomic_json(scratch / f"{config}-round3-overlay.json", overlays)
        with (out / f"{config}-round3-disagreements.csv").open("w") as f:
            writer = csv.DictWriter(
                f, fieldnames=["id", "kind", "model", "start", "end", "text", "details"], lineterminator="\n"
            )
            writer.writeheader()
            for row in disagreements:
                writer.writerow(
                    {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()}
                )
        (out / f"{config}-round3-report.md").write_text(markdown(config, result, execution))
        print(config, panel["config_status"], panel["valid_per_model"], panel["gates"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("docs/validation"))
    args = parser.parse_args()
    generate(args.scratch, args.out)
