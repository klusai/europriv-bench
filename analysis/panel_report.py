"""Offline RES-77 statistics, majority overlays and exhaustive disagreements.

python analysis/panel_report.py --scratch /path/to/scratch --out docs/validation
Requires the optional panel extra (numpy); no paid API calls.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from europriv_bench.metrics import wilson_interval
from europriv_bench.panel import LABELS, MODELS, alpha_documents, candidates, decode_audit, digest, span_set, stratum
from europriv_bench.panel_api import BudgetClient, atomic_json

ROOT = Path(__file__).resolve().parents[1]
CODEX = "openai/codex-session"


def interval(values) -> list[float] | None:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return np.quantile(values, [0.025, 0.975]).tolist() if len(values) else None


def bootstrap(rows, annotations, models=MODELS) -> dict:
    """Stratified document-cluster bootstrap, shared resamples for all alpha/ratings."""
    if not rows:
        return {"n": 0, "alpha": {}, "ratings": {}, "bootstrap_replicates": 2000}
    documents = alpha_documents(rows, annotations, models=models)
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[row["stratum"]].append(i)
    rng = np.random.default_rng(7701)
    resamples = np.concatenate(
        [rng.choice(indices, (2000, len(indices))) for _, indices in sorted(groups.items())], axis=1
    )
    stats = {"n": len(rows), "alpha": {}, "ratings": {}, "bootstrap_replicates": 2000}
    for metric in ("panel", *models):
        labels = sorted(set().union(*(d[metric][1].keys() for d in documents)))
        counts = np.array([[d[metric][1][label] for label in labels] for d in documents], dtype=float)
        disagreements = np.array([d[metric][0] for d in documents])

        def calculate(c, disagreement):
            total = c.sum(axis=-1)
            with np.errstate(divide="ignore", invalid="ignore"):
                expected = (total * total - (c * c).sum(axis=-1)) / (total - 1)
                return 1 - disagreement / expected

        point = float(calculate(counts.sum(axis=0), disagreements.sum()))
        draws = calculate(counts[resamples].sum(axis=1), disagreements[resamples].sum(axis=1))
        stats["alpha"][metric] = {
            "estimate": point if np.isfinite(point) else None,
            "ci95": interval(draws),
            "defined_bootstraps": int(np.isfinite(draws).sum()),
        }
    for model in models:
        stats["ratings"][model] = {}
        for metric in ("fluency", "naturalness"):
            values = np.array([annotations[model][r["id"]][metric] for r in rows])
            stats["ratings"][model][metric] = {
                "median": float(np.median(values)),
                "ci95": interval(np.median(values[resamples], axis=1)),
            }
    return stats


def adjudicate(row, proposals, reviews):
    """Only unanimous availability + >=2 approvals; preserve conflicting originals."""
    votes = {m: {v["id"]: v for v in reviews.get(m, {}).get(row["id"], {}).get("votes", [])} for m in MODELS}
    approved, records = [], []
    complete = all(set(votes[m]) == {p["id"] for p in proposals} for m in MODELS)
    for proposal in proposals:
        choices = [votes[m].get(proposal["id"]) for m in MODELS]
        majority = all(v is not None for v in choices) and sum(v["approve"] for v in choices) >= 2
        if majority:
            approved.append(proposal)
        records.append({**proposal, "majority": majority, "votes": dict(zip(MODELS, choices))})
    spans = span_set(row["spans"])
    for p in approved:
        item = (p["start"], p["end"], p["label"])
        if p["operation"] == "remove":
            spans.discard(item)
        else:
            spans.add(item)
    ordered = sorted(spans)
    conflict = any(a[1] > b[0] for a, b in zip(ordered, ordered[1:]))
    overlay = None
    if approved and complete and not conflict:
        overlay = {
            "id": row["id"],
            "text_sha256": row["sha256"],
            "original_spans": row["spans"],
            "spans": [{"start": s, "end": e, "label": label} for s, e, label in ordered],
            "basis": "LLM majority hypothesis; requires fresh held-out validation",
        }
    return {
        "complete": complete,
        "approved": len(approved),
        "conflict": conflict,
        "records": records,
        "overlay": overlay,
    }


def evaluate(config, population, rows, annotations, reviews, errors):
    full = [r for r in rows if all(r["id"] in annotations.get(m, {}) for m in MODELS)]
    stats = bootstrap(full, annotations)
    discrepancies, overlays, approved, conflicts = [], [], 0, 0
    b_complete = len(full) == 300
    for row in rows:
        row_id = row["id"]
        present = [m for m in MODELS if row_id in annotations.get(m, {})]
        for model in MODELS:
            if model not in present:
                reason = next(
                    (e["error"] for e in errors if e["config"] == config and e["model"] == model and e["id"] == row_id),
                    "No valid stage-A output",
                )
                discrepancies.append({"id": row_id, "kind": "missing_annotation", "model": model, "details": reason})
        # Include partial-case disagreements without misrepresenting them as complete-case alpha.
        raters = {
            "gold": {(s["start"], s["end"]): s["label"] for s in row["spans"]},
            **{m: {(s["start"], s["end"]): s["label"] for s in annotations[m][row_id]["spans"]} for m in present},
        }
        for start, end in sorted(set().union(*(r.keys() for r in raters.values()))):
            labels = {m: r.get((start, end), "ABSENT") for m, r in raters.items()}
            if len(set(labels.values())) > 1:
                discrepancies.append(
                    {
                        "id": row_id,
                        "kind": "span",
                        "start": start,
                        "end": end,
                        "text": row["text"][start:end],
                        "details": labels,
                    }
                )
        for rating in ("fluency", "naturalness"):
            values = {m: annotations[m][row_id][rating] for m in present}
            if len(set(values.values())) > 1:
                discrepancies.append({"id": row_id, "kind": rating, "details": values})
        for model in present:
            for artifact in annotations[model][row_id]["artifacts"]:
                discrepancies.append({"id": row_id, "kind": "artifact", "model": model, "details": artifact})
        if len(present) == 3:
            ps = candidates(row, [annotations[m][row_id] for m in MODELS])
            adj = adjudicate(row, ps, reviews)
            b_complete &= adj["complete"]
            approved += adj["approved"]
            conflicts += adj["conflict"]
            if adj["overlay"]:
                overlays.append(adj["overlay"])
            for record in adj["records"]:
                discrepancies.append(
                    {
                        "id": row_id,
                        "kind": "gold_review",
                        "start": record["start"],
                        "end": record["end"],
                        "text": record["text"],
                        "details": record,
                    }
                )
    decode = decode_audit(population, config[:2].upper())
    for failure in decode["failures"]:
        discrepancies.append({"id": failure["id"], "kind": "decode", "details": failure})
    decode["ci95"] = list(wilson_interval(decode["consistent"], decode["subjects"]))
    artifacts = sum(sum(bool(annotations[m][r["id"]]["artifacts"]) for m in MODELS) >= 2 for r in full)
    stats.update(
        execution_errors=dict(Counter(e["error"] for e in errors if e["config"] == config)),
        config=config,
        sampled_n=len(rows),
        population_n=len(population),
        strata=dict(Counter(r["stratum"] for r in rows)),
        population_strata=dict(Counter(stratum(r) for r in population)),
        seed=77,
        seed_count=1,
        decode=decode,
        majority_gold_errors=approved,
        edit_conflicts=conflicts,
        valid_per_model={m: len(annotations.get(m, {})) for m in MODELS},
        artifacts={
            "n": len(full),
            "flagged": artifacts,
            "ci95": list(wilson_interval(artifacts, len(full))) if full else None,
        },
    )
    sample_ok = (
        len(rows) == 300
        and len({r["id"] for r in rows}) == 300
        and Counter(r["stratum"] for r in rows) == dict.fromkeys(("admin", "clinical", "contract", "declaration"), 75)
        and all(r["stratum"] == stratum(r) and r["sha256"] == digest(r["text"]) for r in rows)
    )
    gates = {
        "sample": sample_ok,
        "complete": len(full) == 300 and b_complete,
        "agreement": len(stats["alpha"]) == 4
        and all(a["estimate"] is not None and a["estimate"] >= 0.8 for a in stats["alpha"].values()),
        "ratings": bool(full) and all(v["median"] >= 4 for m in stats["ratings"].values() for v in m.values()),
        "artifacts": bool(full) and artifacts / len(full) <= 0.05,
        "decode": decode["pass"],
        "gold_errors": approved == 0 and conflicts == 0 and b_complete,
    }
    stats.update(
        gates=gates, passed=all(gates.values()), config_status="panel-validated" if all(gates.values()) else "dev"
    )
    return stats, discrepancies, overlays


def fmt(value, ci=None):
    if value is None:
        return "unavailable"
    return f"{value:.4f}" + (f" [{ci[0]:.4f}, {ci[1]:.4f}]" if ci else "")


def load_codex(path, rows, config, manifest):
    """Fail closed on changed source, judgments, offsets, or incomplete review operations."""
    metadata = manifest["configs"][config]
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["annotations_file_sha256"]:
        raise ValueError("Codex annotation file hash mismatch")
    records = [json.loads(line) for line in path.read_text().splitlines()]
    indexed = {r["id"]: r for r in rows}
    if len(records) != len(indexed) or {a["id"] for a in records} != set(indexed):
        raise ValueError("Codex sample coverage mismatch")
    frozen = []
    for a in records:
        row = indexed[a["id"]]
        text = row["text"]
        if (
            a["config"] != config
            or a["reviewer"] != CODEX
            or a["source_revision"] != manifest["source_revision"]
            or a["stratum"] != row["stratum"]
            or a["text_sha256"] != row["sha256"]
            or row["sha256"] != digest(text)
            or a["raw_utf8_sha256"] != hashlib.sha256(text.encode()).hexdigest()
        ):
            raise ValueError("Codex source mismatch")
        for metric in ("fluency", "naturalness"):
            if type(a[metric]) is not int or not 1 <= a[metric] <= 5:
                raise ValueError("Invalid Codex rating")
        if not isinstance(a["reason"], str) or not a["reason"].strip():
            raise ValueError("Missing Codex rating reason")
        if not isinstance(a["artifacts"], list) or any(not isinstance(x, str) for x in a["artifacts"]):
            raise ValueError("Invalid Codex artifacts")
        end = 0
        for span in a["spans"]:
            start, stop = span["start"], span["end"]
            if (
                type(start) is not int
                or type(stop) is not int
                or not end <= start < stop <= len(text)
                or span["label"] not in LABELS
                or text[start:stop] != span["text"]
            ):
                raise ValueError("Invalid Codex span/offset")
            end = stop
        stage_a = {k: v for k, v in a.items() if k not in {"stage_a_sha256", "gold_errors"}}
        stage_a["gold_review_status"] = "pending_after_A_freeze"
        if digest(stage_a) != a["stage_a_sha256"]:
            raise ValueError("Codex stage A changed after freeze")
        frozen.append(stage_a)
        proposals = candidates(row, [a])
        if len(proposals) != len(a["gold_errors"]):
            raise ValueError("Incomplete Codex gold review")
        for proposal, vote in zip(proposals, a["gold_errors"]):
            if any(vote[k] != v for k, v in proposal.items()) or type(vote["approve"]) is not bool:
                raise ValueError("Codex review does not match candidate")
            if not isinstance(vote["reason"], str) or not vote["reason"].strip():
                raise ValueError("Codex review reason missing")
    frozen_bytes = "".join(json.dumps(a, ensure_ascii=False) + "\n" for a in frozen).encode()
    if (
        digest(frozen) != metadata["stage_a_payload_sha256"]
        or hashlib.sha256(frozen_bytes).hexdigest() != metadata["stage_a_file_sha256"]
    ):
        raise ValueError("Codex frozen file/payload mismatch")
    return {a["id"]: a for a in records}


def supplemental(rows, annotations, codex):
    """Descriptive added-judge audit; never substitutes for frozen judges or B votes."""
    combined = {**annotations, CODEX: codex}
    models = (*MODELS, CODEX)
    full = [r for r in rows if all(r["id"] in combined.get(m, {}) for m in models)]
    single = bootstrap(rows, {CODEX: codex}, models=(CODEX,))
    flagged = sum(bool(a["artifacts"]) for a in codex.values())
    affected = sum(any(v["approve"] for v in a["gold_errors"]) for a in codex.values())
    operations = sum(v["approve"] for a in codex.values() for v in a["gold_errors"])
    discrepancies = []
    for row in rows:
        a = codex[row["id"]]
        raters = {"gold": row["spans"], CODEX: a["spans"]}
        raters.update({m: annotations[m][row["id"]]["spans"] for m in MODELS if row["id"] in annotations.get(m, {})})
        labels = {m: {(s["start"], s["end"]): s["label"] for s in spans} for m, spans in raters.items()}
        for start, end in sorted(set().union(*(r.keys() for r in labels.values()))):
            choices = {m: r.get((start, end), "ABSENT") for m, r in labels.items()}
            if len(set(choices.values())) > 1:
                discrepancies.append(
                    dict(
                        id=row["id"],
                        kind="supplemental_span",
                        model=CODEX,
                        start=start,
                        end=end,
                        text=row["text"][start:end],
                        details=choices,
                    )
                )
        for artifact in a["artifacts"]:
            discrepancies.append(dict(id=row["id"], kind="supplemental_artifact", model=CODEX, details=artifact))
        for vote in a["gold_errors"]:
            discrepancies.append(
                dict(
                    id=row["id"],
                    kind="supplemental_gold_review",
                    model=CODEX,
                    start=vote["start"],
                    end=vote["end"],
                    text=vote["text"],
                    details=vote,
                )
            )
        for metric in ("fluency", "naturalness"):
            values = {m: combined[m][row["id"]][metric] for m in models if row["id"] in combined.get(m, {})}
            if len(set(values.values())) > 1:
                discrepancies.append(dict(id=row["id"], kind="supplemental_" + metric, details=values))
    ratings = single["ratings"][CODEX]
    alpha = single["alpha"][CODEX]
    return {
        "judge": CODEX,
        "n": len(rows),
        "models": models,
        "valid_per_model": {m: sum(r["id"] in combined.get(m, {}) for r in rows) for m in models},
        "codex_vs_gold": single,
        "expanded_panel": bootstrap(full, combined, models=models),
        "by_stratum": {
            group: bootstrap([r for r in rows if r["stratum"] == group], {CODEX: codex}, models=(CODEX,))
            for group in sorted({r["stratum"] for r in rows})
        },
        "artifacts": {"n": len(rows), "flagged": flagged, "ci95": list(wilson_interval(flagged, len(rows)))},
        "gold_hypotheses": {
            "documents": affected,
            "operations": operations,
            "ci95_documents": list(wilson_interval(affected, len(rows))),
            "majority_adjudicated": False,
        },
        "descriptive_checks": {
            "codex_alpha_ge_080": alpha["estimate"] is not None and alpha["estimate"] >= 0.8,
            "codex_medians_ge_4": all(v["median"] >= 4 for v in ratings.values()),
            "codex_artifacts_le_005": flagged / len(rows) <= 0.05,
            "no_codex_gold_hypotheses": operations == 0,
        },
        "changes_frozen_verdict": False,
    }, discrepancies


def supplemental_markdown(s, config):
    single = s["codex_vs_gold"]
    alpha, ratings = single["alpha"][CODEX], single["ratings"][CODEX]
    art, gold = s["artifacts"], s["gold_hypotheses"]
    lang = config[:2]
    lines = [
        "",
        "## Codex session follow-up (supplemental)",
        "",
        f"Codex read all {s['n']} raw sampled documents, froze A, then compared gold. "
        "This adds one session judge, with no additional paid API calls; it does not replace a frozen judge.",
        f"[Annotations](codex-annotations-{lang}.jsonl), [provenance](codex-review-manifest.json), "
        "[method and limitations](codex-review.md), [Romanian generator fixes](codex-ro-quality-fixes.md).",
        "",
        "| Comparison | n | Alpha [95% CI] | Fluency [95% CI] | Naturalness [95% CI] |",
        "|---|---:|---|---|---|",
        f"| Codex vs gold | {s['n']} | {fmt(alpha['estimate'], alpha['ci95'])} | "
        f"{fmt(ratings['fluency']['median'], ratings['fluency']['ci95'])} | "
        f"{fmt(ratings['naturalness']['median'], ratings['naturalness']['ci95'])} |",
        f"| Expanded four-judge panel | {s['expanded_panel']['n']} | "
        + fmt(
            s["expanded_panel"]["alpha"].get("panel", {}).get("estimate"),
            s["expanded_panel"]["alpha"].get("panel", {}).get("ci95"),
        )
        + " | — | — |",
        "",
        "| Codex stratum | n | Alpha [95% CI] | Fluency [95% CI] | Naturalness [95% CI] |",
        "|---|---:|---|---|---|",
    ]
    for group, stats in s["by_stratum"].items():
        a, r = stats["alpha"][CODEX], stats["ratings"][CODEX]
        lines.append(
            f"| {group} | {stats['n']} | {fmt(a['estimate'], a['ci95'])} | "
            f"{fmt(r['fluency']['median'], r['fluency']['ci95'])} | "
            f"{fmt(r['naturalness']['median'], r['naturalness']['ci95'])} |"
        )
    lines += [
        "",
        "Codex-vs-gold uses their exact-span union; missing judges are not ABSENT votes. "
        "Expanded-panel statistics require all four judges and the union of gold plus those four. "
        "A single available judge cannot define panel-vs-panel alpha.",
        "Sampling seed 77 (one seed); 2,000 stratified document-cluster bootstrap draws, seed 7701. "
        "Degenerate CIs reflect identical span/label counts within template strata, not certainty across judges or genres.",
        f"Codex artifact flags: {art['flagged']}/{art['n']}; Wilson 95% CI "
        f"{fmt(art['flagged'] / art['n'], art['ci95'])}. This is not a majority artifact rate.",
        f"Gold-error hypotheses: {gold['documents']}/{s['n']} documents "
        f"(Wilson 95% CI {fmt(gold['documents'] / s['n'], gold['ci95_documents'])}), "
        f"{gold['operations']} add/remove operations. These are single-judge votes, not approved repairs.",
        "Hospitals: ORG_PARTY → FACILITY; treating physicians: PERSON → PROVIDER. "
        "Boundaries agree. The contextual clinical refinements follow KP 0.2.0; adjudication is outstanding.",
        "**Verdict remains NOT VALIDATED (`dev`).** The original three-family completeness and review "
        "requirements remain unmet; supplemental descriptive checks cannot change the frozen gates. "
        "No dataset regeneration, accepted gold overlay, or model rescoring occurred.",
        "",
    ]
    return "\n".join(lines)


def markdown(stats, provenance, spend):
    config = stats["config"]
    lines = [
        f"# {config}: autonomous LLM-panel audit",
        "",
        f"**Outcome: {'PASS' if stats['passed'] else 'NOT VALIDATED'}; config_status={stats['config_status']}.**",
        "This is an autonomous LLM-panel audit, never native-speaker review or human validation.",
        "",
        "Protocol: [pre-registration](panel-protocol.md), committed before paid inference.",
        f"Source: `klusai/europriv-bench`, revision `{provenance['revision']}`, test split, CC-BY-4.0.",
        f"Protocol SHA256: `{provenance['protocol_sha256']}`.",
        f"Sample manifest SHA256: `{provenance['sample_manifest_sha256']}`.",
        f"Population n={stats['population_n']}; sampled n={stats['sampled_n']}; complete three-judge n={stats['n']}.",
        "Sampling seed=77; seed count=1. Bootstrap seed=7701, 2,000 stratified document resamples when defined.",
        "",
        "| Stratum | Population | Sample |",
        "|---|---:|---:|",
    ]
    for group, n in stats["strata"].items():
        lines.append(f"| {group} | {stats['population_strata'][group]} | {n} |")
    lines += [
        "",
        "| Judge / comparison | Valid n | Exact-span alpha [95% CI] | Fluency median [95% CI] | Naturalness median [95% CI] |",
        "|---|---:|---|---|---|",
    ]
    for model in MODELS:
        a = stats["alpha"].get(model, {})
        ratings = stats["ratings"].get(model, {})
        f, n = ratings.get("fluency", {}), ratings.get("naturalness", {})
        lines.append(
            f"| {model} vs gold | {stats['valid_per_model'][model]} | {fmt(a.get('estimate'), a.get('ci95'))} | "
            f"{fmt(f.get('median'), f.get('ci95'))} | {fmt(n.get('median'), n.get('ci95'))} |"
        )
    a = stats["alpha"].get("panel", {})
    lines += [
        f"| Panel vs panel | {stats['n']} | {fmt(a.get('estimate'), a.get('ci95'))} | — | — |",
        "",
        "Alpha uses exact-boundary union units and KP/ABSENT nominal categories, not token accuracy or alpha-U.",
        "CIs are stratified document-cluster percentile bootstrap CIs; no intervals are fabricated for missing judgments.",
    ]
    d, art = stats["decode"], stats["artifacts"]
    lines += [
        "",
        f"Full-population ID consistency: {d['consistent']}/{d['subjects']} distinct document/ID subjects; "
        f"Wilson 95% CI {fmt(d['consistent'] / d['subjects'] if d['subjects'] else None, d['ci95'])}.",
        f"Explicit clinical DOB comparisons: {d['explicit_dob_subjects']} subjects. Checks include checksum, "
        "known DOB/sex and gold NATIONAL_ID coverage. Independent sex/county fields were not available; "
        "name-based sex or address-based birthplace consistency was not inferred.",
        f"Majority artifact flags: {art['flagged']}/{art['n']} complete documents; "
        f"Wilson 95% CI {fmt(art['flagged'] / art['n'] if art['n'] else None, art['ci95'])}.",
        f"Majority-approved gold operations: {stats['majority_gold_errors']}; conflicting documents: {stats['edit_conflicts']}.",
        "Zero approved operations with missing judgments is **not evidence that the gold is correct**.",
        "",
        "| Pre-registered gate | Pass |",
        "|---|---|",
    ]
    lines += [f"| {gate} | {'yes' if passed else 'no'} |" for gate, passed in stats["gates"].items()]
    lines += [
        "",
        "## Execution and spend",
        "",
        "Execution diagnostics (counts are missing document/judge annotations, not API requests): "
        + json.dumps(stats["execution_errors"], ensure_ascii=False)
        + ".",
        f"Shared ledger records {spend['attempts']} attempted API requests and "
        f"{spend['unknown_cost_requests']} unresolved request costs. "
        "Unresolved costs prevent further paid calls under the frozen protocol. "
        "See [execution record](panel-execution.json) for the initial attempt; missing judgments "
        "prevent a complete linguistic or annotation-quality verdict.",
        "",
        f"Shared RO+PL ledger: confirmed response costs ${spend['actual_usd']:.6f}; "
        f"outstanding worst-case reservations ${spend['reserved_usd']:.6f}; cap $25.",
        f"Responses carrying usage.cost: {spend['responses']}. These shared totals must not be added across reports.",
        f"See [{config}-disagreements.csv]({config}-disagreements.csv) for every observed disagreement, "
        "artifact, review vote, decode failure and missing annotation. Local raw responses, request ledger, "
        "sample texts and logs stay in scratch; the committed sample manifest identifies source rows/hashes.",
        "",
        "## Corrections and leaderboard",
        "",
        "Approved nonconflicting operations are exported to a local source-hashed overlay. The original "
        "revision and its audit result are preserved. No published dataset is mutated or promoted by this script.",
        "No gold correction is established without the required votes. If no overlay exists, no leaderboard "
        "row has affected gold and no rescore is warranted. An overlay requires harness rescoring and a new "
        "held-out protocol before any promotion; original scores cannot be copied to repaired gold.",
        "",
        "## Limitations",
        "",
        "LLMs can share systematic errors and favor synthetic prose; different model families do not imply "
        "independent errors. Agreement is neither human IAA nor evidence of native competence, privacy, "
        "real-world representativeness or absence of linkability. One sampling seed and one authored template "
        "family limit generalization; document bootstrap CIs omit model and template-family uncertainty. "
        "Missing frozen-judge outputs prevent a complete panel conclusion. No model-performance win, human "
        "review, clinical correctness, or real-world privacy guarantee was verified.",
        "",
    ]
    result = "\n".join(lines)
    if "codex_supplement" in stats:
        result += supplemental_markdown(stats["codex_supplement"], config)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--codex-dir", type=Path, help="Optional frozen session annotations; never changes original gates"
    )
    parser.add_argument(
        "--overlay-out", type=Path, help="Write overlays here instead of the original execution scratch"
    )
    args = parser.parse_args()
    scratch, out = args.scratch, args.out
    out.mkdir(parents=True, exist_ok=True)
    samples = json.loads((scratch / "samples.json").read_text())
    manifest = json.loads((scratch / "sample-manifest.json").read_text())
    stage_a = json.loads((scratch / "stage-a.json").read_text())
    stage_b = json.loads((scratch / "stage-b.json").read_text()) if (scratch / "stage-b.json").exists() else {}
    expected_protocol = hashlib.sha256((ROOT / "docs/validation/panel-protocol.md").read_bytes()).hexdigest()
    if stage_a["protocol_sha256"] != expected_protocol or stage_a["sample_sha256"] != digest(samples):
        raise ValueError("Protocol/sample mismatch: cannot score changed inputs")
    if stage_b and any(stage_b[k] != stage_a[k] for k in ("protocol_sha256", "sample_sha256")):
        raise ValueError("Stage-B provenance differs from stage A")
    provenance = {
        "revision": manifest["revision"],
        "protocol_sha256": stage_a["protocol_sha256"],
        "sample_manifest_sha256": hashlib.sha256((scratch / "sample-manifest.json").read_bytes()).hexdigest(),
    }
    codex_manifest = None
    if args.codex_dir:
        codex_manifest = json.loads((args.codex_dir / "codex-review-manifest.json").read_text())
        for key, value in provenance.items():
            if codex_manifest["source_revision" if key == "revision" else key] != value:
                raise ValueError("Codex protocol/sample/revision differs from frozen run")
    spend = BudgetClient(scratch / "cache", stage_a["protocol_sha256"], offline=True).totals()
    atomic_json(out / "panel-sample-manifest.json", manifest)
    results = {}
    for config, rows in samples.items():
        population = json.loads((scratch / f"{config}-rows.json").read_text())
        stats, discrepancies, overlays = evaluate(
            config,
            population,
            rows,
            stage_a["annotations"][config],
            stage_b.get("annotations", {}).get(config, {}),
            stage_a["errors"],
        )
        for error in stage_b.get("errors", []):
            if error["config"] == config:
                discrepancies.append(
                    {"id": error["id"], "kind": "missing_review", "model": error["model"], "details": error["error"]}
                )
        stats.update(provenance=provenance, shared_spend=spend, stage_b_run=bool(stage_b))
        if codex_manifest:
            path = args.codex_dir / codex_manifest["configs"][config]["annotations_file"]
            codex = load_codex(path, rows, config, codex_manifest)
            supplement, extra = supplemental(rows, stage_a["annotations"][config], codex)
            supplement["provenance"] = codex_manifest["configs"][config]
            stats["codex_supplement"] = supplement
            discrepancies.extend(extra)
        atomic_json(out / f"{config}-panel-results.json", stats)
        atomic_json((args.overlay_out or scratch) / f"{config}-gold-overlay.json", overlays)
        with (out / f"{config}-disagreements.csv").open("w", newline="") as f:
            writer = csv.DictWriter(
                f, lineterminator="\n", fieldnames=["id", "kind", "model", "start", "end", "text", "details"]
            )
            writer.writeheader()
            for d in discrepancies:
                writer.writerow(
                    {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in d.items()}
                )
        (out / f"{config}-panel-report.md").write_text(markdown(stats, provenance, spend))
        results[config] = {"n": stats["n"], "gates": stats["gates"], "config_status": stats["config_status"]}
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
