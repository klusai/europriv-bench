"""Complete the requested test matrix with the prospectively amended dev-rejected rule."""

from __future__ import annotations

import argparse
import subprocess
from datetime import UTC, datetime

from analysis.calibrate_res100 import ESTATE, read
from analysis.report_gateway_moe import report
from analysis.score_gateway_decoding import decoded_result, predict_raw, registration
from analysis.score_gateway_moe import freeze, immutable, import_comparators
from analysis.score_res100 import ROOT, digest, write

AMENDMENT = ROOT / "docs/gateway-decoding-diagnostic.md"


def validate_selection(scratch):
    reg = registration(scratch)
    selected = read(scratch / "selection.json")
    if selected["selected_rule"] is not None:
        raise ValueError("Diagnostic exception applies only to infeasible dev selection")
    if selected["registration"] != reg or selected["grid_sha256"] != digest(scratch / "dev-grid.json"):
        raise ValueError("Selection drift")
    for path, sha in selected["pins"].items():
        if digest(scratch / path) != sha:
            raise ValueError(f"Selection evidence drift: {path}")
    committed = subprocess.check_output(
        ["git", "show", "HEAD:docs/gateway-decoding-diagnostic.md"], cwd=ROOT)
    if committed != AMENDMENT.read_bytes():
        raise ValueError("Commit diagnostic amendment before test scoring")
    return reg


def run(scratch, seeds, splice):
    reg = validate_selection(scratch)
    folder = scratch / "test"
    pinpath = folder / "diagnostic-registration.json"
    current = {"rule": "strict", "status": "diagnostic; dev-rejected",
               "dev_selection_feasible": False, "amendment_sha256": digest(AMENDMENT),
               "selection_sha256": digest(scratch / "selection.json"), "source_sha256": digest(__file__)}
    if pinpath.exists():
        diagnostic = read(pinpath)
        if any(diagnostic[k] != value for k, value in current.items()):
            raise ValueError("Diagnostic registration drift")
    else:
        diagnostic = {**current, "registered_at": datetime.now(UTC).isoformat(),
                      "registration_commit": subprocess.check_output(
                          ["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip()}
        immutable(pinpath, diagnostic)
    configs = freeze(folder)
    immutable(folder / "contract-pin.json", {"commit": reg["contract_commit"],
                                             "sha256": digest(ROOT / "src/europriv_bench/gateway_contract.py")})
    for seed in seeds:
        predict_raw(folder, configs, seed, {**reg, "diagnostic": diagnostic})
        for config in configs:
            result, predictions = decoded_result(folder, config, seed, "strict")
            target = folder / "predictions" / f"seed{seed}--{config}.json"
            immutable(target, predictions)
            result["row"].update(prediction_sha256=digest(target), contamination="unknown",
                                  contamination_note="RES-100 + gateway train; disjointness unaudited",
                                  diagnostic=diagnostic, dev_selection_feasible=False)
            if config == "ro-synthetic-v1":
                result["row"].update(contamination="in_distribution",
                                      contamination_note="RO synthetic training-family overlap")
            write(folder / "results" / target.name, result)
            print(f"SCORED DIAGNOSTIC seed{seed}/{config}", flush=True)
    import_comparators(folder, configs)
    report(folder, splice=splice, decoded=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1])
    parser.add_argument("--splice", action="store_true")
    args = parser.parse_args()
    run(ESTATE / "decode-fix", args.seeds, args.splice)


if __name__ == "__main__":
    main()
