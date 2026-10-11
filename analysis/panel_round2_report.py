"""Offline round-2 gate report, including separate supplemental Codex statistics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from analysis.panel_report import CODEX, bootstrap, evaluate, fmt
from analysis.panel_round2 import frozen
from europriv_bench.metrics import wilson_interval
from europriv_bench.panel import LABELS, MODELS, candidates, digest
from europriv_bench.panel_api import atomic_json
from europriv_bench.panel_round2_api import RetryBudgetClient


def rate(flagged, n):
    return {
        "flagged": flagged,
        "n": n,
        "ci95": [max(0.0, min(1.0, x)) for x in wilson_interval(flagged, n)] if n else None,
    }


def stats_with_artifacts(rows, annotations, models):
    result = bootstrap(rows, annotations, models=models)
    result["artifacts_per_judge"] = {
        m: rate(sum(bool(annotations[m][r["id"]]["artifacts"]) for r in rows), len(rows)) for m in models
    }
    return result


def codex_annotations(out, config, rows, manifest):
    metadata = manifest["configs"][config]
    path = out / metadata["annotations_file"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
        raise ValueError("Frozen Codex annotations changed")
    records = [json.loads(line) for line in path.read_text().splitlines()]
    indexed = {r["id"]: r for r in rows}
    if len(records) != 300 or {a["id"] for a in records} != set(indexed):
        raise ValueError("Codex coverage mismatch")
    for annotation in records:
        row = indexed[annotation["id"]]
        if (
            annotation["config"] != config
            or annotation["stratum"] != row["stratum"]
            or annotation["text_sha256"] != hashlib.sha256(row["text"].encode()).hexdigest()
        ):
            raise ValueError("Codex source mismatch")
        end = 0
        for span in annotation["spans"]:
            if (
                not end <= span["start"] < span["end"] <= len(row["text"])
                or row["text"][span["start"] : span["end"]] != span["text"]
                or span["label"] not in LABELS
            ):
                raise ValueError("Invalid Codex span")
            end = span["end"]
        if any(type(annotation[k]) is not int or not 1 <= annotation[k] <= 5 for k in ("fluency", "naturalness")):
            raise ValueError("Invalid rating")
    return {a["id"]: a for a in records}


def generate(scratch, out):
    samples = json.loads((scratch / "samples.json").read_text())
    population = json.loads((scratch / "populations.json").read_text())
    frozen_state = {**frozen(), "sample_sha256": digest(samples)}
    if json.loads((scratch / "frozen.json").read_text()) != frozen_state:
        raise ValueError("Frozen protocol or sample mismatch")
    stage_a = json.loads((scratch / "stage-a.json").read_text())
    if any(stage_a[k] != v for k, v in frozen_state.items()):
        raise ValueError("Stage A provenance mismatch")
    stage_b_path = scratch / "stage-b.json"
    stage_b = json.loads(stage_b_path.read_text()) if stage_b_path.exists() else {}
    if stage_b and any(stage_b[k] != v for k, v in frozen_state.items()):
        raise ValueError("Stage B provenance mismatch")
    manifest = json.loads((out / "round2-codex-manifest.json").read_text())
    if manifest["protocol_sha256"] != frozen_state["protocol_sha256"]:
        raise ValueError("Codex protocol mismatch")
    client = RetryBudgetClient(scratch / "cache", frozen_state["protocol_sha256"], offline=True)
    atomic_json(out / "round2-execution.json", client.evidence())
    atomic_json(out / "round2-sample-manifest.json", json.loads((scratch / "sample-manifest.json").read_text()))
    # Preserve judgments for review without duplicating raw source documents or API identifiers.
    atomic_json(
        out / "round2-panel-annotations.json",
        {
            "protocol_sha256": frozen_state["protocol_sha256"],
            "sample_sha256": digest(samples),
            "stage_a": stage_a["annotations"],
            "stage_b": stage_b.get("annotations", {}),
            "errors": stage_a["errors"] + stage_b.get("errors", []),
        },
    )
    for config, rows in samples.items():
        annotations = stage_a["annotations"][config]
        reviews = stage_b.get("annotations", {}).get(config, {})
        panel, disagreements, overlays = evaluate(
            config, population[config], rows, annotations, reviews, stage_a["errors"]
        )
        panel["seed"] = 7712
        panel["inference_seed"] = 77
        panel["scope"] = "Only complete external cases; incomplete coverage cannot establish any config-wide pass"
        panel["decode"]["ci95"] = rate(panel["decode"]["consistent"], panel["decode"]["subjects"])["ci95"]
        panel["artifacts"] = rate(panel["artifacts"]["flagged"], panel["artifacts"]["n"])
        for field in ("dob", "sex"):
            n = panel["decode"][f"explicit_{field}_subjects"]
            passed = panel["decode"][f"explicit_{field}_consistent"]
            panel["decode"][f"explicit_{field}_ci95"] = rate(passed, n)["ci95"]
        codex = codex_annotations(out, config, rows, manifest)
        codex_stats = {"overall": stats_with_artifacts(rows, {CODEX: codex}, (CODEX,)), "by_type": {}}
        panel["by_type"] = {}
        for kind in ("contract", "clinical", "admin", "declaration"):
            subset = [r for r in rows if r["stratum"] == kind]
            codex_stats["by_type"][kind] = stats_with_artifacts(subset, {CODEX: codex}, (CODEX,))
            full = [r for r in subset if all(r["id"] in annotations[m] for m in MODELS)]
            panel["by_type"][kind] = stats_with_artifacts(full, annotations, MODELS)
        codex_changes = [
            {"id": r["id"], "stratum": r["stratum"], "proposals": candidates(r, [codex[r["id"]]])}
            for r in rows
            if candidates(r, [codex[r["id"]]])
        ]
        result = {
            "protocol_sha256": frozen_state["protocol_sha256"],
            "sample_sha256": digest(samples),
            "source_commit": manifest["source_commit"],
            "panel": panel,
            "codex": codex_stats,
            "codex_disagreements": codex_changes,
            "codex_role": "Supplemental single judge; no replacement of panel or majority adjudication",
        }
        atomic_json(out / f"{config}-round2-results.json", result)
        atomic_json(scratch / f"{config}-round2-overlay.json", overlays)
        with (out / f"{config}-round2-disagreements.csv").open("w") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "kind", "model", "start", "end", "text", "details"])
            writer.writeheader()
            for d in disagreements:
                writer.writerow(
                    {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in d.items()}
                )
            for d in codex_changes:
                for proposal in d["proposals"]:
                    writer.writerow(
                        {
                            "id": d["id"],
                            "kind": "codex_single_judge_hypothesis",
                            "model": CODEX,
                            "start": proposal["start"],
                            "end": proposal["end"],
                            "text": proposal["text"],
                            "details": json.dumps(proposal, ensure_ascii=False),
                        }
                    )
            for a in codex.values():
                for artifact in a["artifacts"]:
                    writer.writerow({"id": a["id"], "kind": "codex_artifact", "model": CODEX, "details": artifact})
        lines = [
            f"# {config}: independent round-2 report",
            "",
            f"Status: **{panel['config_status']}**. External panel incomplete; no promotion.",
            "",
            "[Frozen protocol](round2-protocol.md) · [Reproduction and spend ledger summary](round2-runbook.md).",
            "",
            "Source: klusai/klusai-datasets commit `" + manifest["source_commit"] + "`, CC-BY-4.0.",
            "Frozen reserved sample: 300 documents, 75/type, seed 7712; population 1,500.",
            "One generation seed/language; one sampling seed; no repeated inference seeds.",
            "CIs: 2,000 stratified document bootstrap draws, seed 7701; proportions use Wilson 95%.",
            "",
            "## Required external panel",
            "",
            "Mistral upstream shared-pool HTTP 429s exhausted six attempts on RO batch 2.",
            "Same-model provider fallback was enabled. No model substitution. Stage B did not run.",
            "Valid A documents: " + ", ".join(f"{m}: {n}/300" for m, n in panel["valid_per_model"].items()) + ".",
            "Partial statistics below describe only the returned cases, not the full config.",
            "",
            "| External statistic | n | Estimate [95% CI] |",
            "|---|---:|---|",
        ]
        for metric, value in panel["alpha"].items():
            lines.append(f"| Alpha: {metric} | {panel['n']} | {fmt(value['estimate'], value['ci95'])} |")
        for model, values in panel["ratings"].items():
            for metric, value in values.items():
                lines.append(f"| {model}: {metric} | {panel['n']} | {fmt(value['median'], value['ci95'])} |")
        if not panel["n"]:
            lines.append("| Agreement, ratings, majority artifacts | 0 | unavailable |")
        else:
            ar = panel["artifacts"]
            lines.append(f"| Majority artifacts | {ar['n']} | {ar['flagged']}/{ar['n']}; {ar['ci95']} |")
        lines += [
            "",
            "Gate diagnostics (partial-case passes do not override failed completeness): "
            + ", ".join(f"{k}={'pass' if v else 'fail/unverified'}" for k, v in panel["gates"].items())
            + ".",
            "",
            "| Document type | Complete external n / 75 |",
            "|---|---:|",
        ]
        for kind, value in panel["by_type"].items():
            lines.append(f"| {kind} | {value['n']} |")
        lines += [
            "",
            "## Supplemental blind Codex review",
            "",
            "The author self-review was not read and does not count. Codex annotations/ratings were",
            "frozen before gold comparison or reading external judgments. Review used raw prose",
            "variants plus all 600 document slot rows, with code transcribing selected spans.",
            "This is one shared session with template-assisted transcription, not isolated per-document judgments.",
            "",
            "| Type | n | Codex–gold alpha [95% CI] | Fluency median [95% CI] | Naturalness median [95% CI] | Artifact docs [Wilson CI] |",
            "|---|---:|---|---|---|---|",
        ]
        for kind, value in [("overall", codex_stats["overall"]), *codex_stats["by_type"].items()]:
            alpha, ratings, artifacts = (
                value["alpha"][CODEX],
                value["ratings"][CODEX],
                value["artifacts_per_judge"][CODEX],
            )
            lines.append(
                f"| {kind} | {value['n']} | {fmt(alpha['estimate'], alpha['ci95'])} | "
                f"{fmt(ratings['fluency']['median'], ratings['fluency']['ci95'])} | "
                f"{fmt(ratings['naturalness']['median'], ratings['naturalness']['ci95'])} | "
                f"{artifacts['flagged']}/{artifacts['n']} {artifacts['ci95']} |"
            )
        lines += [
            "",
            "Codex flags clinical under-specification: assessments refer to monitoring or improvement",
            "without individual measurements/treatment details. Contracts form coherent short agreements.",
            f"Codex differs from gold on {len(codex_changes)} clinical documents: named medical centers",
            "as FACILITY rather than ORG_PARTY, and doctors as PROVIDER rather than PERSON; RO also",
            "differs on facility boundaries. These are single-judge hypotheses, not majority-approved repairs.",
            "No gold overlay was applied and no model score was copied onto changed gold.",
            "",
            "## Harness identifier audit",
            "",
        ]
        d = panel["decode"]
        lines += [
            f"Across all 1,500 documents: {d['consistent']}/{d['subjects']} unique document/ID subjects",
            f"pass checksum, known DOB/sex and raw-ID NATIONAL_ID coverage; Wilson CI {d['ci95']}.",
            f"Explicit clinical DOB: {d['explicit_dob_subjects']} subjects; sex: {d['explicit_sex_subjects']} subjects.",
            f"Consistent DOB: {d['explicit_dob_consistent']}; sex: {d['explicit_sex_consistent']}; "
            f"respective Wilson CIs {d['explicit_dob_ci95']} and {d['explicit_sex_ci95']}.",
            "No independent stated sex outside clinical rows or birth-county field was assumed.",
            "",
            "## Limits and disposition",
            "",
            "Keep dev: missing external judgments and missing three-family adjudication prevent validation.",
            "No human/native-speaker review, legal/clinical certification, registry/address/bank lookup,",
            "real-record representativeness, unseen-template generalization or model-performance win verified.",
            "The holdout separates documents, not authored templates. CIs condition on this family and judges;",
            "degenerate alpha/median CIs reflect identical within-type span counts and repeated ratings,",
            "not certainty about population quality. No independent per-document model contexts were used for Codex.",
            "Agreement is not accuracy, human IAA, privacy certification or proof against linkability.",
            "No v1–v2 improvement claim: independent CI-disjoint held-out delta was not established.",
            "",
        ]
        (out / f"{config}-round2-report.md").write_text("\n".join(lines))
        print(
            config, "status", panel["config_status"], "Codex alpha", codex_stats["overall"]["alpha"][CODEX], flush=True
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("docs/validation"))
    args = parser.parse_args()
    generate(args.scratch, args.out)
