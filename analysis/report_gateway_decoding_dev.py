"""Report the complete registered decoding grid, including infeasible selection."""

from analysis.calibrate_res100 import ESTATE, read
from analysis.report_gateway_moe import pct
from analysis.score_res100 import ROOT, digest, write
from europriv_bench.gateway_contract import utility_gate


def report(scratch=ESTATE / "decode-fix"):
    selection = read(scratch / "selection.json")
    if digest(scratch / "dev-grid.json") != selection["grid_sha256"]:
        raise ValueError("Dev grid differs from frozen selection")
    grid = read(scratch / "dev-grid.json")
    corrections = {
        "scope": "TAB dev only; frozen generic v2 replay metadata is retained, not used for selection",
        "bootstrap_unit": "document",
        "contamination": "unknown",
        "config_status": "real-external-gold",
        "split": "dev",
        "reason": "Generic BaseAdapter replay markers are not decoder training-lineage or gold-quality claims",
    }
    write(ROOT / "analysis/gateway-decoding-dev.json", {
        "selection": selection, "grid": grid, "metadata_corrections": corrections,
    })
    selected = selection["selected_rule"]
    lines = [
        "# Gateway boundary decoding: dev selection",
        "",
        f"Frozen selection: **{selected or 'no feasible candidate'}**. Training seed: **0**; seed count **1**.",
        "All three registered rules were scored on all 1,600 gateway DEV conversations (200 per language)",
        "and 126 TAB dev documents. Selection uses no test results. Wilson intervals describe identifier",
        "subjects; utility and paired delta intervals use 2,000 whole-document/conversation bootstrap draws, RNG 100.",
        "TAB's selection replay uses the v2 path; its clusters are documents, despite the generic replay",
        "helper's `bootstrap_unit=conversation` metadata in the dev grid. No rows or counts are changed.",
        "TAB also inherits generic `clean_held_out`/`dev` replay markers in that frozen grid. The correct",
        "interpretation is unknown model contamination and real-external-gold on the dev split. These",
        "markers were not selection inputs; `metadata_corrections` records this without changing the frozen grid.",
        "",
        "| Rule | Feasible configs / 9 | Macro all-subject leak % | Macro non-PII removed % |",
        "|---|---:|---:|---:|",
    ]
    for record in grid:
        lines.append(f"| {record['rule']} | {sum(c['feasible'] for c in record['configs'].values())} | "
                     f"{100 * record['macro_leak']:.2f} | {100 * record['macro_utility']:.2f} |")
    lines += [
        "",
        "Macro rates are the registered equal-config selection objective, not pooled independent n or a win claim.",
        "A single failing config/comparator excludes a candidate; the v3 utility upper-CI margin is +1.0 point.",
        "V2 reference requires upper CI <=0. Full per-comparator deltas and all subject slices are retained in",
        "[the aggregate dev grid](../analysis/gateway-decoding-dev.json). There are no three-seed/held-out verdicts.",
        "",
        "| Rule | Config | Clusters | Subjects | V2 leak % [95% Wilson CI] | Non-PII removed % [95% bootstrap CI] | V3 utility | V2 utility |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for record in grid:
        for config, item in record["configs"].items():
            row = item["row"]
            scores = row["scores"]
            leak, util = scores["residual_leakage_v2"], scores["over_redaction"]
            v2 = all(utility_gate(g["ci95"], contract_version=2)["pass"] for g in item["utility_gates"].values())
            lines.append(f"| {record['rule']} | {config} | {row['n']} | {int(leak['all_subjects_total'])} | "
                         f"{pct(leak['all_leak_rate'], [leak['all_leak_rate_ci_low'], leak['all_leak_rate_ci_high']])} | "
                         f"{pct(util['rate'], util['ci95'])} | {'pass' if item['feasible'] else 'fail'} | "
                         f"{'pass' if v2 else 'fail'} |")
    lines += [
        "",
        "| Rule | Config | Binding comparator (largest upper CI) | Utility delta pp [95% bootstrap CI] |",
        "|---|---|---|---:|",
    ]
    for record in grid:
        for config, item in record["configs"].items():
            if item["feasible"]:
                continue
            name, gate = max(item["utility_gates"].items(), key=lambda pair: pair[1]["ci95"][1])
            lines.append(f"| {record['rule']} | {config} | {name} | "
                         f"{pct(gate['candidate_minus_comparator'], gate['ci95'])} |")
    lines += [
        "",
        "The main sync before inference added the referenced DEV audit at `763604c`; the preregistration's",
        "absence observation refers specifically to the earlier first-check commit `4f5203f`.",
        "The fixed rules contain no learned merchant/status lists and no gold-derived country metadata.",
        "The optional national-ID country validator is covered by controls but is inactive for this evaluation:",
        "no independent deployment country context is available. IBAN/phone checks and Unicode boundaries are active.",
        "",
        "DEV receipt inspection exposes a limitation: simple aggregation can emit adjacent native spans with",
        "different BIOES prefixes. Normalizing their labels does not merge their intervals. This registered",
        "filter requires a complete word within each individual span, so it can discard pieces whose union",
        "previously protected a complete identifier. The whole-word-name unit control does not establish",
        "preservation for a name emitted as several fragments. No coalescing rule was added after test access.",
        "",
        "Unverified: independent native review; source/subject/scenario-family/translation disjointness;",
        "three independent seeds; deployment equivalence; semantic utility; CPU load/SLO; attacker re-identification.",
    ]
    if selected is None:
        lines += [
            "",
            "The original preregistered test path stopped because the constrained objective has no feasible solution.",
            "A disclosed [prospective diagnostic amendment](gateway-decoding-diagnostic.md), written after these",
            "dev outcomes and before test scoring, separately registers strict for the requested two-seed test matrix.",
            "That diagnostic does not change this infeasible selection or the original default-decoding results.",
        ]
    lines += [
        "",
        "## Reproduction",
        "",
        "Use Python 3.13 with the pinned local MoE environment from gateway-moe-scoring.md.",
        "Raw receipts/gold stay in estate/scratch/decode-fix; no downloads or training are required.",
        "The diagnostic command requires the committed amendment and a completed immutable dev selection.",
        "The dev command resumes interrupted inference; after selection is frozen, use the report command",
        "rather than regenerating the grid (timestamps are part of its hash).",
        "RES-125 inputs were subsequently moved to codespace-archive/2026-10-11/res125. A fresh dev capture",
        "requires making the original pinned inputs available at the documented paths; the already-frozen",
        "selection and test run resume from their verified local copies. Comparator receipt relocations are",
        "recorded in the diagnostic comparison JSON with both paths and unchanged SHA-256 hashes.",
        "",
        "```bash",
        "export PYTHONPATH=src:. HF_HUB_OFFLINE=1",
        "python -u analysis/score_gateway_decoding.py dev",
        "python -m analysis.report_gateway_decoding_dev",
        "python -u analysis/score_gateway_decoding_diagnostic.py --seeds 0 1 --splice",
        "```",
        "",
        "The adapter option is `Res100MoEAdapter(model_id, decoding_rule='strict', country=None)`.",
        "The historical adapter retains its 256-token default; the registered gateway scoring commands",
        "explicitly use the saved 512-token checkpoint pipeline. No default decoder behavior is changed.",
    ]
    (ROOT / "docs/gateway-decoding-dev-results.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    report()
