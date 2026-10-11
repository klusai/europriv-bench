"""Gateway conversation loading, exact deletion operators and paired cluster inference.

The frozen coordinate space concatenates message text parts in message/part order,
with one newline between parts. One row is one conversation, including every turn.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import yaml

from .metrics import residual_subject_detection_v2

LANGUAGES = ("ro", "en", "de", "fr", "es", "it", "nl", "pl")


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class GatewayRows(list):
    source_metadata: dict


def flatten_conversation(row: dict) -> dict:
    if row["schema_version"] != "gateway-traffic-v1" or row["config_status"] != "dev":
        raise ValueError("gateway v1 requires the registered dev schema")
    pieces, fields, offsets = [], [], {}
    position = 0
    for mi, message in enumerate(row["messages"]):
        for pi, part in enumerate(message["parts"]):
            if part["type"] != "text":
                raise ValueError("unsupported gateway part; never silently bypass input")
            text = part["text"]
            offsets[mi, pi] = (position, text)
            fields.append({"message": mi, "part": pi, "start": position, "end": position + len(text)})
            pieces.append(text)
            position += len(text) + 1
    spans, retained = [], []
    for span in row["spans"]:
        base, text = offsets[span["message"], span["part"]]
        start, end = span["start"], span["end"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
            raise ValueError("invalid field-relative gateway offsets")
        if text[start:end] != span["text"]:
            raise ValueError("gateway span surface mismatch")
        if span["protection"] not in {"retain", "mask", "pseudonymize"}:
            raise ValueError("unknown gateway protection policy")
        if span["identifier_class"] not in {"DIRECT", "QUASI"}:
            raise ValueError("unknown gateway identifier class")
        converted = {**span, "start": base + start, "end": base + end,
                     "identifier_type": span["identifier_class"]}
        (retained if span["protection"] == "retain" else spans).append(converted)
    return {**row, "text": "\n".join(pieces), "spans": spans, "retained_spans": retained, "fields": fields}


def load_gateway(spec):
    """Local override first; otherwise pinned Hub JSONL/parquet, never streaming."""
    ref = spec.dataset
    local = os.environ.get("EUROPRIV_GATEWAY_PATH") or ref.local_path
    manifest_path = os.environ.get("EUROPRIV_GATEWAY_MANIFEST") or ref.manifest_path
    if local:
        root = Path(local)
        source = root / f"{ref.split}.jsonl" if root.is_dir() else root
        if not manifest_path:
            manifest_path = root / "manifest.yaml"
        manifest_path = Path(manifest_path)
    else:
        from huggingface_hub import hf_hub_download

        from .runner import ConfigUnavailableError

        if not ref.revision or not ref.files or not manifest_path:
            raise ConfigUnavailableError("gateway is unpublished: set EUROPRIV_GATEWAY_PATH and manifest override")
        source = Path(hf_hub_download(ref.hf_id, ref.files[0], repo_type="dataset", revision=ref.revision))
        manifest_path = Path(hf_hub_download(
            ref.hf_id, manifest_path, repo_type="dataset", revision=ref.revision,
        ))
    manifest = yaml.safe_load(manifest_path.read_text())
    if manifest["dataset"] != "gateway-traffic-v1" or manifest["config_status"] != "dev":
        raise ValueError("gateway manifest identity/status mismatch")
    if source.suffix == ".parquet":
        from pyarrow import parquet

        raw = parquet.read_table(source).to_pylist()
    else:
        raw = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    result = GatewayRows()
    seen = set()
    for row in raw:
        if row["id"] in seen or row["split"] != ref.split:
            raise ValueError("duplicate conversation or split mismatch")
        seen.add(row["id"])
        source_license = manifest["sources"][row["source_id"]]
        if not (source_license.get("permitted_train") and source_license.get("permitted_redistribute")
                and source_license.get("license") and source_license.get("url")):
            raise ValueError("source lacks trainable/redistributable licence and URL")
        if ref.split not in source_license["allowed_gateway_splits"]:
            raise ValueError("source is not admitted to the gateway split")
        if row["language"] in spec.languages:
            result.append(flatten_conversation(row))
    if not result:
        raise ValueError("gateway has no rows for requested languages")
    result.source_metadata = {
        "data_sha256": sha256(source), "manifest_sha256": sha256(manifest_path),
        "data_revision": manifest.get("data_revision"), "coordinate_policy": "message-part-order-newline-v1",
        "sources": manifest["sources"], "local_override": bool(local),
    }
    return result


def utility_counts(rows, coverage):
    # Reuse strict v2 bounds validation, including overlap/Unicode behavior.
    residual_subject_detection_v2(rows, coverage)
    output = []
    for row, spans in zip(rows, coverage, strict=True):
        removed, protected = bytearray(len(row["text"])), bytearray(len(row["text"]))
        for start, end in spans:
            removed[start:end] = b"\x01" * (end - start)
        for span in row["spans"]:
            protected[span["start"]:span["end"]] = b"\x01" * (span["end"] - span["start"])
        indices = [i for i, ch in enumerate(row["text"]) if not ch.isspace() and not protected[i]]
        output.append((sum(removed[i] for i in indices), len(indices)))
    return output


def gateway_utility(rows, coverage):
    counts = utility_counts(rows, coverage)
    removed, total = map(sum, zip(*counts)) if counts else (0, 0)
    return {"available": int(total > 0), "non_pii_characters": total, "removed_non_pii_characters": removed,
            "over_redaction_rate": removed / total if total else 0,
            "character_retention": 1 - removed / total if total else 0}


def cluster_counts(rows, coverage, group="all"):
    counts = [[0, 0] for _ in rows]
    for subject in residual_subject_detection_v2(rows, coverage):
        if group == "all" or subject["identifier_type"].lower() == group:
            counts[subject["doc"]][0] += subject["leaked"]
            counts[subject["doc"]][1] += 1
    return counts


def paired_cluster_bootstrap(candidate, comparator, *, seed=126, resamples=2000):
    """Ratio-of-sums delta with the SAME sampled conversation indexes for both engines.

    Input arrays contain (numerator, denominator) per conversation, including hard negatives.
    Empty-support resamples are unavailable and counted, never converted to measured zeros.
    """
    import numpy as np

    if resamples < 2000:
        raise ValueError("contract requires at least 2000 bootstrap resamples")
    a, b = np.asarray(candidate, dtype=float), np.asarray(comparator, dtype=float)
    if a.ndim != 2 or a.shape[1] != 2 or a.shape != b.shape or not len(a):
        raise ValueError("paired bootstrap requires aligned, nonempty conversation counts")
    if not np.array_equal(a[:, 1], b[:, 1]):
        raise ValueError("paired gold denominators differ")
    if np.any(a < 0) or np.any(b < 0) or np.any(a[:, 0] > a[:, 1]) or np.any(b[:, 0] > b[:, 1]):
        raise ValueError("invalid cluster counts")
    support = float(a[:, 1].sum())
    result = {"available": bool(support), "n": int(support), "clusters": len(a),
              "resamples": resamples, "seed": seed, "method": "paired conversation cluster percentile 95%"}
    if not support:
        return {**result, "delta": None, "ci_low": None, "ci_high": None, "valid_resamples": 0}
    rng, values = np.random.default_rng(seed), []
    for _ in range(resamples):
        indexes = rng.integers(len(a), size=len(a))
        sa, sb = a[indexes].sum(axis=0), b[indexes].sum(axis=0)
        if sa[1]:
            values.append(sa[0] / sa[1] - sb[0] / sb[1])
    return {**result, "delta": float((a[:, 0].sum() - b[:, 0].sum()) / support),
            "ci_low": float(np.quantile(values, .025)), "ci_high": float(np.quantile(values, .975)),
            "valid_resamples": len(values)}
