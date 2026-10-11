#!/usr/bin/env python3
"""Splice a complete five-engine gateway run, preserving every existing anchor row."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from europriv_bench.gateway import LANGUAGES
from europriv_bench.leaderboard import build_leaderboard

LABELS = {"kp-280m", "560m-legal", "560m-tab", "presidio", "shield"}


def splice(board, rows):
    expected = {(label, lang) for label in LABELS for lang in LANGUAGES}
    actual = {(row["run_label"], row["languages"][0]) for row in rows}
    if actual != expected or len(rows) != len(expected):
        raise ValueError("refusing partial/duplicate gateway matrix")
    if any(row["config_status"] != "dev" or row["n"] != 1000 or row["limit"] is not None for row in rows):
        raise ValueError("gateway rows must be complete, 1000-conversation dev rows")
    if len({row["dataset"]["data_sha256"] for row in rows}) != 1:
        raise ValueError("gateway gold hash mismatch")
    retained = [row for group in board["entries"].values() for row in group
                if row["dataset"].get("config") != "gateway-traffic-v1"]
    result = copy.deepcopy(board)
    result["entries"] = {key: [row for row in group if row["dataset"].get("config") != "gateway-traffic-v1"]
                         for key, group in result["entries"].items()}
    for key, group in build_leaderboard(rows)["entries"].items():
        result["entries"].setdefault(key, []).extend(group)
    # Compare canonical serialized rows, including every old score/provenance field.
    after = [row for group in result["entries"].values() for row in group
             if row["dataset"].get("config") != "gateway-traffic-v1"]
    assert sorted(json.dumps(r, sort_keys=True) for r in retained) == sorted(json.dumps(r, sort_keys=True) for r in after)
    return result


def report(rows, comparisons):
    lines = ["# Gateway full-PII dev results — RES-126", "",
             "Synthetic, unreviewed `gateway-traffic-v1`, data revision 4. Each row scores 1,000",
             "conversations and 4,506 identifier subjects (4,266 DIRECT, 240 QUASI; UNSPECIFIED",
             "has no support). Each KP checkpoint: training seed 0 only; each baseline: one inference run.",
             "95% Wilson intervals below are descriptive subject intervals. Paired conversation",
             "cluster intervals (2,000 resamples, seed 126) are in `baselines/gateway-comparisons.json`.",
             "Negative utility deltas favor the candidate. Character retention is a proxy, not semantic utility.", "",
             "| Engine | Language | Leak % [95% Wilson] | Non-PII removed % [95% cluster CI] |", "|---|---|---:|---:|"]
    for row in sorted(rows, key=lambda r: (r["run_label"], r["languages"][0])):
        s, u = row["scores"]["residual_leakage_v2"], row["cluster_intervals"]["utility"]
        lines.append(f"| {row['run_label']} | {row['languages'][0]} | {100*s['all_leak_rate']:.2f} "
                     f"[{100*s['all_leak_rate_ci_low']:.2f}, {100*s['all_leak_rate_ci_high']:.2f}] | "
                     f"{100*u['delta']:.2f} [{100*u['ci_low']:.2f}, {100*u['ci_high']:.2f}] |")
    lines += ["", "| Candidate vs comparator | Disjoint Wilson languages / 8 | Paired privacy pass / 8 | Utility pass / 8 |",
              "|---|---:|---:|---:|"]
    for candidate in sorted(LABELS - {"presidio", "shield"}):
        for baseline in ("presidio", "shield"):
            group = [c for c in comparisons if c["candidate"] == candidate and c["comparator"] == baseline]
            assert len(group) == 8
            lines.append(f"| {candidate} vs {baseline} | {sum(c['wilson_disjoint'] for c in group)} | "
                         f"{sum(c['paired_privacy_pass'] for c in group)} | {sum(c['utility_pass'] for c in group)} |")
    lines += ["", "| Contract line | Verdict and evidence |", "|---|---|",
              "| §1 full-conversation v2 coverage | Implemented and tested; gold-defined identifier subjects, cross-turn IDs, exact Unicode intervals. |",
              "| §1 Wilson/support/sensitivity slices | Reported for all eight languages; UNSPECIFIED unavailable, never a measured zero. |",
              "| §2 operators and replay | KP/Presidio local deletion receipts; Shield pinned service replace receipts. KP deployment equivalence unverified. |",
              "| §2 corruption controls | No-mask, full-mask, label permutation, shuffled positions on full test; masked-input diagnostic n=32/language/engine. |",
              "| §3.1 disjoint Wilson | Per-language checks above; insufficient alone for acceptance. |",
              "| §3.1 three independent training seeds | Not established: one seed per KP checkpoint. |",
              "| §3.2 paired conversation bootstrap | Reported for all/sensitivity slices and utility, 2,000 resamples, seed 126. |",
              "| §3.3 no-worse over-redaction | Per-language checks above; no pooled-average substitute. |",
              "| §3.3 RO/PL zero floors; TAB anchor | Historical specifications and all existing board rows retained byte-for-byte as canonical JSON; new operators not rescored on anchors. |",
              "| §3.4 all eight languages and worst language | Full 5×8 dev matrix; no gateway-wide acceptance. |",
              "| §3.4 reviewed gold and disjointness | Not established: native review and semantic family/subject/translation review pending. |",
              "| §4 p95 and CI <=250 ms | Not measured. No service/load trial in this quality run. |",
              "| §4 >=15 successful req/s at 16 offered | Not measured. |",
              "| §4 errors/timeouts/refusals <=0.1% | Not measured under load. Quality inference failures fail closed. |",
              "| §4 1,000 ms deadline/cancel | Not measured. |",
              "| §4 zero bypass/truncation | Full-input overflow operator implemented; deployed gateway behavior unverified. |",
              "| §4 three trials and time-block CIs | Not run. |",
              "| §4 long lane, interference, fallback | Not verified. |", "",
              "No scoped privacy win or production acceptance is established. Dataset publication, native review,",
              "three-seed verification, current-operator anchor scoring, semantic utility and deployment/load testing remain open.", "",
              "| Engine | Worst-language residual leak |", "|---|---|"]
    for label in sorted(LABELS):
        row = max((r for r in rows if r["run_label"] == label), key=lambda r: r["scores"]["residual_leakage_v2"]["all_leak_rate"])
        s = row["scores"]["residual_leakage_v2"]
        lines.append(f"| {label} | {row['languages'][0]}: {100*s['all_leak_rate']:.2f}% "
                     f"[{100*s['all_leak_rate_ci_low']:.2f}, {100*s['all_leak_rate_ci_high']:.2f}], n=4,506 |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scratch", type=Path, required=True)
    args = ap.parse_args()
    rows = [json.loads(p.read_text()) for p in sorted(args.scratch.glob("*.row.json"))]
    comparisons = json.loads((args.scratch / "comparisons.json").read_text())
    board_path = Path("baselines/leaderboard.json")
    board = splice(json.loads(board_path.read_text()), rows)
    result_doc = report(rows, comparisons)
    board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n")
    Path("baselines/gateway-comparisons.json").write_text(json.dumps(comparisons, indent=2) + "\n")
    Path("docs/gateway-evaluation-results.md").write_text(result_doc)
    controls = {}
    for row in rows:
        key = f"{row['run_label']}-{row['languages'][0]}"
        controls[key] = json.loads((args.scratch / f"{key}.controls.json").read_text())
    Path("baselines/gateway-controls.json").write_text(json.dumps(controls, indent=2) + "\n")


if __name__ == "__main__":
    main()
