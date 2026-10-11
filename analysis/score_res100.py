"""RES-100 CPU scoring. Re-run the same command to resume and discover seed1/seed2.

All gold and predictions are pinned in scratch; only aggregate artifacts enter git.
No GPU, training, service launch, publication or remote mutation is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from europriv_bench import metrics
from europriv_bench.adapters import BaseAdapter, Res100MoEAdapter, _mask_spans
from europriv_bench.runner import _rows_to_gold, run_spec
from europriv_bench.spec import EvalSpec

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ("all", "direct", "quasi", "unspecified")
REVISION = "58faa4fa572cd8064818a6e1f8ca6e361b959c00"
BASE_REVISION = "7ffa9a043d54d1be65afb281eddf0ffbe629385b"
RNG_SEED = 100
RESAMPLES = 2000


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".partial")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temp.replace(path)


def row_digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def entity_counts(gold, pred):
    from seqeval.scheme import IOBES, Entities

    counts = []
    for true, guessed in zip(gold, pred, strict=True):
        actual = {(e.tag, e.start, e.end) for e in Entities([true], IOBES).entities[0]}
        found = {(e.tag, e.start, e.end) for e in Entities([guessed], IOBES).entities[0]}
        counts.append([len(actual & found), len(actual), len(found)])
    return counts


def utility_counts(row, intervals):
    text = row["text"]
    _mask_spans(text, intervals)
    covered, protected = bytearray(len(text)), bytearray(len(text))
    for start, end in intervals:
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
            raise ValueError("Invalid operator interval")
        covered[start:end] = b"\x01" * (end - start)
    for span in row["spans"]:
        protected[span["start"] : span["end"]] = b"\x01" * (span["end"] - span["start"])
    eligible = [i for i, c in enumerate(text) if not c.isspace() and not protected[i]]
    return [sum(covered[i] for i in eligible), len(eligible)]


def subject_counts(subjects, n, group="all"):
    counts = np.zeros((n, 2), dtype=int)
    for subject in subjects:
        if group == "all" or subject.get("identifier_type", "").lower() == group:
            counts[subject["doc"]] += [not subject["detected"], 1]
    return counts.tolist()


def samples(counts, indices, f1=False):
    totals = np.asarray(counts)[indices].sum(axis=1)
    numerator = 2 * totals[:, 0] if f1 else totals[:, 0]
    denominator = totals[:, 1] + totals[:, 2] if f1 else totals[:, 1]
    return np.divide(numerator, denominator, out=np.full(len(indices), np.nan), where=denominator != 0)


def ci(values):
    return np.quantile(values, [0.025, 0.975]).tolist() if np.isfinite(values).all() else None


def freeze(scratch):
    from huggingface_hub import HfApi, hf_hub_download
    from pyarrow import parquet

    from europriv_bench.openpii import load_openpii

    files = HfApi().list_repo_files("klusai/europriv-bench", repo_type="dataset", revision=REVISION)
    unavailable = []
    configs = []
    for path in sorted((ROOT / "evaluations").glob("pii-detection-*.yaml")):
        spec = EvalSpec.from_yaml(path)
        config = spec.dataset.identity
        filename = f"{spec.dataset.config}/test-00000-of-00001.parquet"
        if spec.dataset.loader == "datasets" and filename not in files:
            unavailable.append({"config": config, "reason": "not published at pinned Hub revision"})
            continue
        configs.append(config)
        target = scratch / "gold" / f"{config}.json"
        if target.exists():
            frozen = json.loads(target.read_text())
            if frozen["spec_sha256"] != digest(path):
                raise ValueError(f"Spec changed: {path}")
            continue
        if spec.dataset.loader == "ai4privacy-openpii":
            rows = load_openpii(spec)
            provenance = {**spec.dataset.provenance(), **rows.source_metadata}
        else:
            source = hf_hub_download(spec.dataset.hf_id, filename, repo_type="dataset", revision=REVISION)
            rows = parquet.read_table(source).to_pylist()
            provenance = {**spec.dataset.provenance(), "revision": REVISION, "parquet_sha256": digest(source)}
        _rows_to_gold(rows)
        write(
            target,
            {
                "spec": spec.model_dump(mode="json"),
                "spec_sha256": digest(path),
                "dataset": provenance,
                "rows_sha256": row_digest(rows),
                "rows": rows,
            },
        )
        print(f"FROZEN {config} n={len(rows)}", flush=True)
    published = {p.split("/")[0] for p in files if p.endswith(".parquet")}
    if published - set(configs):
        raise ValueError(f"Published configs lack specs: {published - set(configs)}")
    write(scratch / "availability.json", {"configs": configs, "unavailable": unavailable})
    return configs


def score(frozen, receipts, model_id, name, seed, identity):
    rows = frozen["rows"]
    if len(receipts) != len(rows):
        raise ValueError("Incomplete receipts")
    spec = EvalSpec.model_validate(frozen["spec"])
    spec.metrics = list(
        dict.fromkeys([*spec.metrics, "national_id_leakage", "name_in_context_leakage", "residual_leakage_v2"])
    )
    if "tab_reid_leakage" in spec.metrics:
        spec.metrics.append("tab_reid_leakage_v2")
    adapter = BaseAdapter()
    adapter.name, adapter.model_id = name, model_id
    adapter.predict_tags = lambda texts: [r["tags"] for r in receipts]
    intervals = [r["intervals"] for r in receipts]
    result = run_spec(spec, adapter, rows=rows, redaction_spans=intervals, timestamp=datetime.now(UTC).isoformat())
    result["dataset"] = frozen["dataset"]
    _, gold = _rows_to_gold(rows)
    labels = set(result["eval_labels"])
    pred = [[t if t == "O" or t.split("-", 1)[1] in labels else "O" for t in r["tags"]] for r in receipts]
    counts = {
        "entity_f1": entity_counts(gold, pred),
        "over_redaction": [utility_counts(r, s) for r, s in zip(rows, intervals, strict=True)],
    }
    subjects = metrics.residual_subject_detection_v2(rows, intervals)
    for group in GROUPS:
        counts[f"v2_{group}"] = subject_counts(subjects, len(rows), group)
    units = [s for s in metrics.national_id_subject_detection(rows, pred) if s["decode_bearing"]]
    counts["legacy_national_id"] = subject_counts(units, len(rows))
    counts["legacy_name"] = subject_counts(list(metrics._person_name_subjects(rows, pred).values()), len(rows))
    if "tab_reid_leakage" in spec.metrics:
        for group in ("all", "direct", "quasi"):
            counts[f"legacy_{group}"] = subject_counts(metrics.tab_reid_subject_detection(rows, pred), len(rows), group)
    indices = np.random.default_rng(RNG_SEED).integers(len(rows), size=(RESAMPLES, len(rows)))
    bootstrap = {k: ci(samples(c, indices, k == "entity_f1")) for k, c in counts.items()}
    result["scores"]["entity_f1"]["ci95"] = bootstrap["entity_f1"]
    totals = np.asarray(counts["entity_f1"]).sum(axis=0)
    expected = 2 * totals[0] / (totals[1] + totals[2]) if totals[1] + totals[2] else 0
    if abs(result["scores"]["entity_f1"]["f1"] - expected) > 1e-12:
        raise ValueError("F1 sufficient statistics disagree with harness")
    removed, total = np.asarray(counts["over_redaction"]).sum(axis=0)
    result["scores"]["over_redaction"] = {
        "removed_nonpii_characters": int(removed),
        "nonpii_characters": int(total),
        "rate": float(removed / total) if total else None,
        "available": bool(total),
        "ci95": bootstrap["over_redaction"],
    }
    result.update(
        training_seed=seed,
        seed_count=1 if seed is not None else 0,
        seed_scope="single-seed" if seed is not None else "one baseline inference run",
        inference_provenance=identity,
        bootstrap_ci95=bootstrap,
        uncertainty={
            "bootstrap_unit": "document",
            "resamples": RESAMPLES,
            "rng_seed": RNG_SEED,
            "confidence": 0.95,
            "leakage": "harness Wilson subject-count intervals",
        },
    )
    if name == "kp-deid-moe-res100":
        # Eight-language KP + TAB train; do not inherit the old RO/EN/PL-only family assertion.
        result["contamination_note"] = (
            "KP eight-language + TAB train; evaluation subject/source disjointness not audited"
        )
    return result, counts


def predict(scratch, configs, model_path, seed, threads, batch_size, is_base=False):
    name = "privacy-filter" if is_base else "kp-deid-moe-res100"
    key = "base" if is_base else f"seed{seed}"
    model_id = "openai/privacy-filter" if is_base else f"klusai/kp-deid-moe-res100-seed{seed}"
    identity = {
        "checkpoint": str(model_path),
        "files": {p.name: digest(p) for p in sorted(model_path.iterdir()) if p.suffix in {".json", ".safetensors"}},
        "device": "cpu",
        "threads": threads,
        "batch_size": batch_size,
        "dtype": "float32",
        "max_tokens": 256,
        "stride": 64,
        "aggregation": "simple; strip remaining BIOES prefixes",
        "operator": "literal block replacement of unioned native intervals; all labels; no threshold",
        "packages": {k: importlib.metadata.version(k) for k in ("torch", "transformers")},
        "adapter_sha256": digest(ROOT / "src/europriv_bench/adapters.py"),
        "training_seed": seed,
        "base_revision": BASE_REVISION,
    }
    if not is_base:
        manifest = model_path.parent / "training-manifest.json"
        identity["training_manifest_sha256"] = digest(manifest)
        training = json.loads(manifest.read_text())
        if training["seed"] != seed:
            raise ValueError("Training seed does not match checkpoint directory")
    adapter = Res100MoEAdapter(str(model_path), scheme="openai" if is_base else "kp", batch_size=batch_size)
    if is_base:
        # Base config declares bf16; candidate export is fp32. Pin the matched runtime explicitly.
        from transformers import pipeline

        adapter._pipe = pipeline(
            "token-classification", model=str(model_path), aggregation_strategy="simple", device="cpu", dtype="float32"
        )
        adapter._pipe.tokenizer.model_max_length = 256
    for config in configs:
        frozen = json.loads((scratch / "gold" / f"{config}.json").read_text())
        ident = {**identity, "gold_sha256": frozen["rows_sha256"]}
        target = scratch / "predictions" / f"{key}--{config}.json"
        saved = json.loads(target.read_text()) if target.exists() else {"identity": ident, "receipts": []}
        if saved["identity"] != ident:
            raise ValueError(f"Stale receipt identity: {target}")
        receipts = saved["receipts"]
        for offset in range(len(receipts), len(frozen["rows"]), batch_size):
            texts = [r["text"] for r in frozen["rows"][offset : offset + batch_size]]
            receipts.extend(adapter.predict_receipts(texts))
            write(target, saved)
            print(f"{key} {config} {len(receipts)}/{len(frozen['rows'])}", flush=True)
        for row, receipt in zip(frozen["rows"], receipts, strict=True):
            if _mask_spans(row["text"], receipt["intervals"]) != receipt["output"]:
                raise ValueError("Operator output differs from receipt")
        result, counts = score(frozen, receipts, model_id, name, seed, ident)
        result["prediction_sha256"] = digest(target)
        write(scratch / "results" / f"{key}--{config}.json", {"row": result, "counts": counts})
        print(
            f"SCORED {key} {config} F1={result['scores']['entity_f1']['f1']:.4f} "
            f"v2={result['scores']['residual_leakage_v2']['all_leak_rate']:.4f}",
            flush=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--checkpoints", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--configs", nargs="+")
    parser.add_argument("--base", action="store_true", help="Also rescore pinned base with the identical operator")
    parser.add_argument("--only-base", action="store_true", help="Score base independently of candidate seeds")
    parser.add_argument("--receipt-source", type=Path, help="Optional RES-125 scratch with comparator receipts")
    parser.add_argument("--splice", action="store_true", help="Write comparisons and splice only complete seeds")
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    import torch

    expected = {"transformers": "5.10.2", "torch": "2.12.0", "peft": "0.19.1"}
    actual = {name: importlib.metadata.version(name) for name in expected}
    if actual != expected:
        raise ValueError(f"Use the klusai-models moe-extra runtime: expected {expected}, got {actual}")
    torch.set_num_threads(args.threads)
    torch.manual_seed(RNG_SEED)
    configs = freeze(args.scratch)
    if args.configs:
        if set(args.configs) - set(configs):
            raise ValueError("Requested config is not available")
        configs = args.configs
    # Score saturated regression anchors and real TAB first; never select a best checkpoint.
    priority = {c: i for i, c in enumerate(("ro-realskeleton-v1", "pl-realskeleton-v1", "tab-echr-legal-en-v1"))}
    configs.sort(key=lambda c: (priority.get(c, 100), c))
    if args.freeze_only:
        return
    for directory in [] if args.only_base else sorted(args.checkpoints.glob("seed[0-9]*")):
        if (directory / "merged/model.safetensors").exists():
            predict(args.scratch, configs, directory / "merged", int(directory.name[4:]), args.threads, args.batch_size)
    if args.base or args.only_base:
        from huggingface_hub import snapshot_download

        model = Path(
            snapshot_download(
                "openai/privacy-filter",
                revision=BASE_REVISION,
                allow_patterns=["config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors"],
            )
        )
        predict(args.scratch, configs, model, None, args.threads, args.batch_size, is_base=True)
    if args.splice:
        from analysis.report_res100 import report

        report(args.scratch, args.receipt_source)
    print("Scoring complete. Results and resumable receipts retained in scratch.", flush=True)


if __name__ == "__main__":
    main()
