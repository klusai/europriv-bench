#!/usr/bin/env python3
"""KLU-104 — Track C redaction baseline on ro-realskeleton-v1: detection recall vs post-redaction leak.

The Track-C scaffolding's first measurement: run a Presidio/regex (or any detector-backed) redaction
BASELINE on the EXISTING ro-realskeleton-v1 config and report, side by side, the four Track-C
metrics PLUS the redactor's detection recall — the latter reported **separately** from the
post-redaction re-identification leak so a high leak is attributable to a recall failure (the
detector missed the span) vs a masking-policy failure (the span was found but only partly masked).

The re-id leak is computed from GOLD OFFSETS against the redacted text (``metrics.redaction_leakage``)
— never by re-running a detector on the output. Presidio is a baseline here, NOT a ranked winner.

Inputs
------
* ``--rows`` JSON: gold rows ``{text, spans, country, ...}`` for ro-realskeleton-v1, generated
  locally from klusai-datasets so the repos stay decoupled (europriv-bench never imports the dataset
  package). Each row should carry ``country='RO'`` (the CNP validator default is RO anyway). Falls
  back to loading the HF config when ``--rows`` is omitted.

Reproduce (CPU-light; run serial/foreground)::

    python analysis/redaction_baseline.py \
        --rows analysis/ro_realskeleton_rows.json \
        --adapter presidio --adapter dummy \
        --outdir analysis
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CONFIG = "ro-realskeleton-v1"
COUNTRY = "RO"


def _load_rows(rows_path: Path | None) -> list[dict]:
    if rows_path is not None:
        return json.loads(rows_path.read_text(encoding="utf-8"))
    from datasets import load_dataset

    ds = load_dataset("klusai/europriv-bench", CONFIG, split="test")
    return [dict(r) for r in ds]


def _score(rows: list[dict], adapters: list[str]) -> dict[str, dict]:
    """Score every adapter on the RO rows via the Track-C anonymization spec → adapter -> metrics."""
    from europriv_bench.adapters import build
    from europriv_bench.runner import run_spec
    from europriv_bench.spec import DatasetRef, EvalSpec, Task

    spec = EvalSpec(
        name="anonymization-ro-realskeleton",
        task=Task.ANONYMIZATION,
        languages=["ro"],
        domain="legal",
        dataset=DatasetRef(hf_id="klusai/europriv-bench", config=CONFIG, split="test"),
        metrics=[
            "redaction_leakage",
            "pseudonymization_consistency",
            "information_retention",
            "structural_disruption",
        ],
    )
    out: dict[str, dict] = {}
    for name in adapters:
        model = build(name)
        res = run_spec(spec, model, rows=rows)
        s = res["scores"]
        leak = s["redaction_leakage"]
        pseudo = s["pseudonymization_consistency"]
        ret = s["information_retention"]
        disrupt = s["structural_disruption"]
        recall = s["detection_recall"]  # reported SEPARATELY from the leak
        out[name] = {
            "adapter": name,
            "model_id": res["model_id"],
            # detection recall (separate) — the recall that drives what the redactor masks.
            "detection_recall": recall["recall"],
            "detection_f2": recall["f2"],
            # post-redaction re-identification leak (from gold offsets).
            "redaction_leak_rate": leak["leak_rate"],
            "redaction_leak_ci_low": leak["leak_rate_ci_low"],
            "redaction_leak_ci_high": leak["leak_rate_ci_high"],
            "subjects_leaked": int(leak["subjects_leaked"]),
            "subjects_total": int(leak["subjects_total"]),
            "leaked_quasi_identifiers": int(leak["leaked_quasi_identifiers"]),
            # pseudonymization bijection.
            "in_doc_bijection_rate": pseudo["in_doc_bijection_rate"],
            "cross_doc_bijection_rate": pseudo["cross_doc_bijection_rate"],
            # utility + structural-disruption proxies.
            "information_retention": ret["information_retention"],
            "mask_token_ratio": disrupt["mask_token_ratio"],
            "length_delta_ratio": disrupt["length_delta_ratio"],
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, default=None,
                    help="Local RO gold rows JSON. Omit to load the HF config.")
    ap.add_argument("--adapter", dest="adapters", action="append", default=None,
                    help="Adapter(s) to score as redaction baselines; repeatable. Default: presidio, dummy.")
    ap.add_argument("--outdir", type=Path, default=Path("analysis"))
    args = ap.parse_args()

    adapters = args.adapters or ["presidio", "dummy"]
    rows = _load_rows(args.rows)
    models = _score(rows, adapters)

    payload = {"config": CONFIG, "country": COUNTRY, "n_docs": len(rows),
               "track": "C-anonymization", "config_status": "dev", "models": models}
    args.outdir.mkdir(parents=True, exist_ok=True)
    out_json = args.outdir / "redaction_baseline.json"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        f"# Track C redaction baseline — `{CONFIG}` (KLU-104)",
        "",
        "`config_status=dev` — measurable, code-computed metrics, NOT a citable validated result. "
        "Presidio is a **baseline**, not a ranked winner. The post-redaction re-identification leak "
        "is computed from **gold offsets** against the redacted text (not a detector re-run), and "
        "detection recall is reported **separately** so a high leak is attributable to recall "
        "failure (span missed) vs masking policy (span found, partly masked).",
        "",
        "| adapter | detection recall | post-redaction leak (95% Wilson CI) | leaked subjects | "
        "in-doc bijection | cross-doc bijection | info-retention (proxy) | mask-token ratio |",
        "|---|---:|:--:|---:|---:|---:|---:|---:|",
    ]
    for name in adapters:
        m = models[name]
        lines.append(
            f"| {name} | {m['detection_recall']:.3f} "
            f"| {m['redaction_leak_rate']:.3f} "
            f"[{m['redaction_leak_ci_low']:.3f}, {m['redaction_leak_ci_high']:.3f}] "
            f"| {m['subjects_leaked']}/{m['subjects_total']} "
            f"| {m['in_doc_bijection_rate']:.3f} | {m['cross_doc_bijection_rate']:.3f} "
            f"| {m['information_retention']:.3f} | {m['mask_token_ratio']:.3f} |"
        )
    out_md = args.outdir / "redaction_baseline.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {out_json} and {out_md}")
    for name in adapters:
        m = models[name]
        print(f"{name}: detection_recall={m['detection_recall']:.3f}  "
              f"post_redaction_leak={m['redaction_leak_rate']:.3f} "
              f"({m['subjects_leaked']}/{m['subjects_total']})")


if __name__ == "__main__":
    main()
