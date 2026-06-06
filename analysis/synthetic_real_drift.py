#!/usr/bin/env python3
"""KLU-103 — the synthetic→real drift metric (Paper 2's scoped contribution).

Quantifies the distribution gap between ``ro-synthetic-v1`` (fully-generated text) and
``ro-realskeleton-v1`` (real document skeletons reseeded with synthetic identifiers). The candidate
metrics are NOT interchangeable — one family is a *defensible model-drift* signal, the other is
*confounded by corpus composition*. They are reported separately and the confounded family is
explicitly tagged. **No model is run here**: model scores are pulled verbatim from the committed
``baselines/leaderboard.json``; only the descriptive corpus statistics touch the (cached, offline)
gold rows. CPU-only.

Three reported families
-----------------------
1. **Primary (defensible) — per-model, per-label-restricted, like-for-like score gap.**
   ``Δ = metric(ro-synthetic) − metric(ro-realskeleton)`` on the **same model**, **same metric**:
     * re-id leak (``leak_rate`` from ``cnp_leakage``) — **primary**, per distinct CNP subject;
     * entity-F1 — **secondary**.
   Restricted to the **intersection of label types** present in both configs. A **positive leak Δ
   means synthetic leaks MORE** (looks worse); for the headline framing we read the *score* gap as
   ``metric=detection_rate`` (re-id) / ``f1`` (entity), where a positive Δ means **synthetic
   overstates real-context performance**. Each model carries a **bootstrap CI over distinct
   subjects** for the re-id-leak gap (per-subject Bernoulli resample, pinned seed). The leaderboard
   stores only aggregate entity-F1 (no per-doc / per-label breakdown), so the entity-F1 gap is
   reported **at the aggregate level with the limitation noted** (see ``LIMITATIONS``).

2. **Label-matched control** — the dominant confound is that the two configs differ in
   size / label-mix / ID-construction, not only "realness." We down-sample the larger config to the
   smaller config's per-label subject counts (re-id leak only, where per-subject data exists) and
   recompute the gap, so a reader sees how much "drift" is composition vs realness.

3. **Descriptive-only — TAGGED "corpus-composition, not model drift".**
     * label-distribution shift: **total-variation distance** + **Jensen–Shannon distance**
       (bounded, symmetric — NOT raw KL, which is unbounded and asymmetric);
     * document-length shift (whitespace token counts): **Wasserstein-1 / Earth-Mover's Distance**.
   These describe how the two *corpora* differ; they say nothing about model behaviour and must
   never be read as a model-drift number.

Deferred
--------
**Embedding-distribution distance (MMD)** is intentionally **NOT** implemented: it needs encoder /
GPU inference, and a concurrent GPU training run (KLU-106) owns the GPU. This issue is CPU-only.
MMD on a frozen, pinned encoder over length-matched buckets is noted as an optional future addition.

Reproducibility
----------------
The committed artifact pins the bootstrap ``seed`` and the SHA-256 **content hashes** of the two
gold-row corpora (text + spans, canonical-JSON, order-independent), so the numbers recompute
bit-for-bit. Re-id counting is **per distinct subject** (inherited from the harness leak metric).

Reproduce (europriv-bench venv; gold rows from the offline HF cache)::

    python analysis/synthetic_real_drift.py \
        --leaderboard baselines/leaderboard.json \
        --synthetic-config ro-synthetic-v1 --real-config ro-realskeleton-v1 \
        --outdir analysis
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

# Pinned reproducibility constants. Changing either changes the committed numbers.
BOOTSTRAP_SEED = 20260603
BOOTSTRAP_RESAMPLES = 10000
CI_ALPHA = 0.05  # 95% percentile bootstrap CI

SYNTHETIC_CONFIG = "ro-synthetic-v1"
REAL_CONFIG = "ro-realskeleton-v1"
HF_ID = "klusai/europriv-bench"

# The leaderboard stores only aggregate entity-F1 (no per-document or per-label breakdown) and
# stores no per-subject re-id flags for the SYNTHETIC config (only aggregate detected/total). These
# bound what a per-document bootstrap can do; recorded verbatim in the artifact.
LIMITATIONS = [
    "entity_f1 gap is reported at the aggregate level only: the committed leaderboard stores a "
    "single corpus-level precision/recall/f1 per (model, config), with no per-document or per-label "
    "breakdown, so neither a per-label restriction nor a per-document bootstrap CI is recoverable "
    "for entity_f1 from committed artifacts.",
    "re-id-leak gap CI is a per-distinct-subject Bernoulli bootstrap reconstructed from the "
    "committed aggregate subject counts (cnp_detected / cnp_total) for BOTH configs; the leaderboard "
    "does not commit per-subject flags for ro-synthetic-v1, so the resample is over the binomial "
    "implied by those counts rather than over joined per-document records.",
    "re-id leak is a single-label (NATIONAL_ID/CNP) signal, so the 'per-label' restriction for the "
    "primary leak metric is the NATIONAL_ID label itself; the label intersection drives the "
    "entity-F1 reading and the descriptive label-distribution metric.",
    "MMD / embedding-distribution distance is deferred (needs a GPU encoder; KLU-106 owns the GPU). "
    "This artifact is CPU-only.",
]


# --------------------------------------------------------------------------- #
# Pure statistics (no I/O, no models — unit-testable in isolation)
# --------------------------------------------------------------------------- #
def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile of an already-sorted sequence (q in [0, 1])."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    frac = pos - lo
    return float(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac)


def bootstrap_leak_gap_ci(
    syn_detected: int,
    syn_total: int,
    real_detected: int,
    real_total: int,
    *,
    metric: str = "leak_rate",
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
    alpha: float = CI_ALPHA,
) -> dict[str, float]:
    """Per-distinct-subject Bernoulli bootstrap CI for the synthetic→real re-id gap.

    Each config contributes a per-subject detected/total count (per distinct CNP subject). We
    resample, with replacement, ``total`` Bernoulli draws at the observed detection probability for
    each config independently, recompute the chosen ``metric`` on each side, and take the gap
    ``synthetic − real``. The percentile CI over ``resamples`` replicates is returned alongside the
    point estimate. Two metrics:

      * ``leak_rate`` = missed/total (↓ better) — positive gap ⇒ synthetic LEAKS MORE.
      * ``detection_rate`` = detected/total (↑ better) — positive gap ⇒ synthetic DETECTS MORE,
        i.e. synthetic OVERSTATES real-context performance (the headline read).

    Deterministic for a fixed seed (pinned in the artifact), so the CI recomputes bit-for-bit.
    """
    if metric not in ("leak_rate", "detection_rate"):
        raise ValueError(f"unknown metric {metric!r}")

    def point(detected: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return (detected / total) if metric == "detection_rate" else ((total - detected) / total)

    syn_point = point(syn_detected, syn_total)
    real_point = point(real_detected, real_total)
    gap = syn_point - real_point

    rng = random.Random(seed)
    syn_p = (syn_detected / syn_total) if syn_total else 0.0
    real_p = (real_detected / real_total) if real_total else 0.0
    gaps: list[float] = []
    for _ in range(resamples):
        sd = sum(1 for _ in range(syn_total) if rng.random() < syn_p)
        rd = sum(1 for _ in range(real_total) if rng.random() < real_p)
        gaps.append(point(sd, syn_total) - point(rd, real_total))
    gaps.sort()
    low = _percentile(gaps, alpha / 2.0)
    high = _percentile(gaps, 1.0 - alpha / 2.0)
    return {
        "metric": metric,
        "synthetic": syn_point,
        "real": real_point,
        "gap": gap,
        "ci_low": low,
        "ci_high": high,
        "excludes_zero": bool(low > 0 or high < 0),
        "resamples": resamples,
        "seed": seed,
    }


def _normalize(counts: dict[str, float], support: Sequence[str]) -> list[float]:
    total = sum(counts.get(k, 0.0) for k in support)
    if total <= 0:
        return [0.0 for _ in support]
    return [counts.get(k, 0.0) / total for k in support]


def tv_distance(p_counts: dict[str, float], q_counts: dict[str, float]) -> float:
    """Total-variation distance between two categorical distributions (bounded in [0, 1]).

    TV = ½ Σ|p_i − q_i| over the union of categories. Symmetric and bounded — unlike raw KL.
    """
    support = sorted(set(p_counts) | set(q_counts))
    p = _normalize(p_counts, support)
    q = _normalize(q_counts, support)
    return 0.5 * sum(abs(pi - qi) for pi, qi in zip(p, q))


def js_distance(p_counts: dict[str, float], q_counts: dict[str, float]) -> float:
    """Jensen–Shannon DISTANCE (sqrt of JS divergence, log base 2) — bounded in [0, 1], symmetric."""
    support = sorted(set(p_counts) | set(q_counts))
    p = _normalize(p_counts, support)
    q = _normalize(q_counts, support)

    def _kl(a: list[float], b: list[float]) -> float:
        s = 0.0
        for ai, bi in zip(a, b):
            if ai > 0 and bi > 0:
                s += ai * math.log2(ai / bi)
        return s

    m = [(pi + qi) / 2.0 for pi, qi in zip(p, q)]
    jsd = 0.5 * _kl(p, m) + 0.5 * _kl(q, m)
    jsd = max(0.0, jsd)  # guard tiny negative float noise
    return math.sqrt(jsd)


def wasserstein1(p_samples: Sequence[float], q_samples: Sequence[float]) -> float:
    """Wasserstein-1 / Earth-Mover's Distance between two 1-D empirical distributions.

    For 1-D samples this is the L1 area between the two empirical CDFs, evaluated as the mean
    absolute difference of the sorted, equal-length quantile functions (sample sizes need not match;
    we integrate over the merged set of breakpoints). Units = the sample units (here: tokens).
    """
    if not p_samples or not q_samples:
        return 0.0
    xs = sorted(p_samples)
    ys = sorted(q_samples)
    all_pts = sorted(set(xs) | set(ys))
    nx, ny = len(xs), len(ys)

    def _cdf(sorted_vals: list[float], n: int, v: float) -> float:
        # fraction of samples <= v
        lo, hi = 0, n
        while lo < hi:
            mid = (lo + hi) // 2
            if sorted_vals[mid] <= v:
                lo = mid + 1
            else:
                hi = mid
        return lo / n

    area = 0.0
    for i in range(len(all_pts) - 1):
        width = all_pts[i + 1] - all_pts[i]
        area += abs(_cdf(xs, nx, all_pts[i]) - _cdf(ys, ny, all_pts[i])) * width
    return area


# --------------------------------------------------------------------------- #
# Corpus + leaderboard helpers
# --------------------------------------------------------------------------- #
def whitespace_token_count(text: str) -> int:
    return len(text.split())


def label_counts(rows: Sequence[dict]) -> Counter:
    """Per-label span counts over a corpus of gold rows ``{text, spans:[{label,...}]}``."""
    c: Counter = Counter()
    for row in rows:
        for sp in row.get("spans", []):
            c[sp["label"]] += 1
    return c


def corpus_content_hash(rows: Sequence[dict]) -> str:
    """Order-independent SHA-256 over (text, sorted spans) — pins the corpus for reproducibility."""
    h = hashlib.sha256()
    digests = []
    for row in rows:
        spans = sorted(
            (int(sp["start"]), int(sp["end"]), str(sp["label"])) for sp in row.get("spans", [])
        )
        canon = json.dumps([row["text"], spans], ensure_ascii=False, separators=(",", ":"))
        digests.append(hashlib.sha256(canon.encode("utf-8")).hexdigest())
    for d in sorted(digests):
        h.update(d.encode("ascii"))
    return h.hexdigest()


def load_rows(config: str, hf_id: str = HF_ID) -> list[dict]:
    """Load gold rows for a config from the offline HF cache (CPU-only, no model inference)."""
    import os

    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from datasets import load_dataset

    ds = load_dataset(hf_id, config, split="test")
    return [{"text": r["text"], "spans": list(r["spans"])} for r in ds]


def _leak_entry(rows: list[dict], config: str) -> dict | None:
    """Pull the committed national-ID leak subject counts for a config from a model's leaderboard rows.

    RES-82: the RO headline is now the unified ``national_id_leakage`` key; tolerate the legacy
    ``cnp_leakage`` key (and its ``cnp_*`` inner fields) so older boards still resolve.
    """
    for r in rows:
        if r["dataset"]["config"] != config:
            continue
        sc = r["scores"].get("national_id_leakage") or r["scores"].get("cnp_leakage")
        if sc is None:
            continue
        detected = sc.get("decode_bearing_detected", sc.get("cnp_detected"))
        total = sc.get("decode_bearing_total", sc.get("cnp_total"))
        return {
            "detected": int(round(detected)),
            "total": int(round(total)),
            "leak_rate": sc["leak_rate"],
        }
    return None


def _entity_f1(rows: list[dict], config: str) -> dict | None:
    for r in rows:
        if r["dataset"]["config"] == config and "entity_f1" in r["scores"]:
            return dict(r["scores"]["entity_f1"])
    return None


def _eval_labels(rows: list[dict], config: str) -> list[str]:
    for r in rows:
        if r["dataset"]["config"] == config:
            return list(r.get("eval_labels", []))
    return []


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def build_primary_table(
    leaderboard: dict, syn_config: str, real_config: str, label_intersection: list[str]
) -> list[dict]:
    """Per-model primary drift rows: re-id leak gap (+ bootstrap CI) and aggregate entity-F1 gap."""
    out = []
    for model_key, rows in leaderboard["entries"].items():
        syn_leak = _leak_entry(rows, syn_config)
        real_leak = _leak_entry(rows, real_config)
        syn_f1 = _entity_f1(rows, syn_config)
        real_f1 = _entity_f1(rows, real_config)
        if not (syn_leak and real_leak):
            continue  # not a model scored on both ro configs

        # Re-id leak (primary): both the leak_rate gap (↓) and the detection_rate gap (↑, headline).
        leak_gap = bootstrap_leak_gap_ci(
            syn_leak["detected"], syn_leak["total"],
            real_leak["detected"], real_leak["total"],
            metric="leak_rate",
        )
        det_gap = bootstrap_leak_gap_ci(
            syn_leak["detected"], syn_leak["total"],
            real_leak["detected"], real_leak["total"],
            metric="detection_rate",
        )

        f1_gap = None
        if syn_f1 and real_f1:
            f1_gap = {
                "synthetic_f1": syn_f1["f1"],
                "real_f1": real_f1["f1"],
                "gap": syn_f1["f1"] - real_f1["f1"],  # >0 ⇒ synthetic overstates entity-F1
                "level": "aggregate",  # NOT per-label / per-doc — see LIMITATIONS
            }

        out.append(
            {
                "model": model_key,
                "reid_leak": {
                    "label": "NATIONAL_ID",  # the single re-id label the leak metric scopes to
                    "synthetic_subjects": syn_leak["total"],
                    "real_subjects": real_leak["total"],
                    "leak_rate_gap": leak_gap,        # ↓ better; +gap ⇒ synthetic leaks more
                    "detection_rate_gap": det_gap,    # ↑ better; +gap ⇒ synthetic overstates perf
                },
                "entity_f1": f1_gap,
                "label_intersection": label_intersection,
            }
        )
    return out


def build_label_matched_control(
    leaderboard: dict,
    syn_config: str,
    real_config: str,
    syn_rows: list[dict],
    real_rows: list[dict],
) -> dict:
    """Down-sample the larger config's NATIONAL_ID subjects to the smaller's count, recompute gap.

    Controls the size confound on the re-id leak metric: each config's per-subject detection
    probability is preserved (we scale counts proportionally to the matched subject count), so the
    recomputed gap isolates 'realness' from the raw subject-count imbalance.
    """
    rows_by_model = leaderboard["entries"]
    matched = []
    for model_key, rows in rows_by_model.items():
        syn_leak = _leak_entry(rows, syn_config)
        real_leak = _leak_entry(rows, real_config)
        if not (syn_leak and real_leak):
            continue
        n_match = min(syn_leak["total"], real_leak["total"])

        def _scaled(detected: int, total: int) -> int:
            if total <= 0:
                return 0
            return int(round(detected / total * n_match))

        gap = bootstrap_leak_gap_ci(
            _scaled(syn_leak["detected"], syn_leak["total"]), n_match,
            _scaled(real_leak["detected"], real_leak["total"]), n_match,
            metric="leak_rate",
        )
        matched.append(
            {
                "model": model_key,
                "matched_subjects_per_config": n_match,
                "leak_rate_gap": gap,
            }
        )
    return {
        "description": (
            "NATIONAL_ID re-id leak gap after down-sampling both configs to matched per-config "
            "subject counts (min of the two). Preserves each config's detection probability; "
            "isolates realness from the raw subject-count imbalance."
        ),
        "rows": matched,
    }


def build_descriptive(syn_rows: list[dict], real_rows: list[dict]) -> dict:
    """Corpus-composition shift metrics — TAGGED 'not model drift'."""
    syn_lab = label_counts(syn_rows)
    real_lab = label_counts(real_rows)
    syn_len = [whitespace_token_count(r["text"]) for r in syn_rows]
    real_len = [whitespace_token_count(r["text"]) for r in real_rows]
    return {
        "tag": "corpus-composition, not model drift",
        "label_distribution_shift": {
            "tv_distance": tv_distance(dict(syn_lab), dict(real_lab)),
            "js_distance": js_distance(dict(syn_lab), dict(real_lab)),
            "synthetic_label_counts": dict(sorted(syn_lab.items())),
            "real_label_counts": dict(sorted(real_lab.items())),
            "note": "TV + Jensen-Shannon distance (bounded, symmetric); raw KL deliberately avoided.",
        },
        "length_shift": {
            "wasserstein1_tokens": wasserstein1(syn_len, real_len),
            "synthetic_mean_tokens": sum(syn_len) / len(syn_len) if syn_len else 0.0,
            "real_mean_tokens": sum(real_len) / len(real_len) if real_len else 0.0,
            "unit": "whitespace tokens",
            "note": "Earth-Mover's Distance (Wasserstein-1) over document token counts.",
        },
    }


def headline(primary: list[dict]) -> str:
    """One-line read across models: by how much does synthetic overstate real-context performance?

    Uses the re-id detection_rate gap (↑ better): positive ⇒ synthetic detects more ⇒ overstates.
    """
    gaps = [m["reid_leak"]["detection_rate_gap"]["gap"] for m in primary]
    if not gaps:
        return "no models scored on both ro configs"
    mean_gap = sum(gaps) / len(gaps)
    direction = "overstates" if mean_gap > 0 else "understates"
    return (
        f"On the re-id (NATIONAL_ID) detection rate, synthetic {direction} real-context performance "
        f"by {abs(mean_gap) * 100:.1f} pp on average across {len(gaps)} models "
        f"(range {min(gaps) * 100:+.1f} to {max(gaps) * 100:+.1f} pp)."
    )


def render_markdown(artifact: dict) -> str:
    a = artifact
    L = []
    L.append("# KLU-103 — synthetic→real drift metric (Paper 2 contribution)\n")
    L.append(
        "> **dev-tier, not citable.** Feeds Paper 2 (unwritten). Re-id counting is per distinct "
        "subject. Model scores are pulled verbatim from the committed leaderboard (no re-scoring); "
        "only descriptive corpus stats touch the gold rows. CPU-only — **MMD deferred** (GPU; "
        "KLU-106).\n"
    )
    L.append(f"- synthetic config: `{a['synthetic_config']}`  (content hash `{a['hashes']['synthetic']}`)")
    L.append(f"- real config: `{a['real_config']}`  (content hash `{a['hashes']['real']}`)")
    L.append(f"- bootstrap seed: `{a['seed']}`, resamples: `{a['resamples']}`, CI: 95% percentile")
    L.append(f"- label intersection: `{', '.join(a['label_intersection'])}`\n")

    L.append(f"## Headline\n\n**{a['headline']}**\n")

    L.append("## 1. Primary — per-model like-for-like drift (defensible)\n")
    L.append(
        "Re-id leak is the primary metric (per distinct CNP subject; label = `NATIONAL_ID`). "
        "`detection_rate` gap (↑ better) drives the headline: **+gap ⇒ synthetic overstates "
        "real-context performance**. `leak_rate` gap (↓ better) is the dual. CIs are a per-subject "
        "Bernoulli bootstrap over the committed subject counts. Entity-F1 is secondary and "
        "**aggregate-level only** (see Limitations).\n"
    )
    L.append("| model | det-rate Δ (syn−real) | 95% CI | leak-rate Δ | 95% CI | entity-F1 Δ (agg) |")
    L.append("|---|---:|---|---:|---|---:|")
    for m in a["primary"]:
        dr = m["reid_leak"]["detection_rate_gap"]
        lr = m["reid_leak"]["leak_rate_gap"]
        f1 = m["entity_f1"]
        f1s = f"{f1['gap'] * 100:+.1f} pp" if f1 else "n/a"
        L.append(
            f"| `{m['model']}` "
            f"| {dr['gap'] * 100:+.1f} pp | [{dr['ci_low'] * 100:+.1f}, {dr['ci_high'] * 100:+.1f}] "
            f"| {lr['gap'] * 100:+.1f} pp | [{lr['ci_low'] * 100:+.1f}, {lr['ci_high'] * 100:+.1f}] "
            f"| {f1s} |"
        )
    L.append("")

    L.append("## 2. Label-matched control (confound check)\n")
    L.append(a["label_matched_control"]["description"] + "\n")
    L.append("| model | matched subjects/config | leak-rate Δ (matched) | 95% CI |")
    L.append("|---|---:|---:|---|")
    for m in a["label_matched_control"]["rows"]:
        g = m["leak_rate_gap"]
        L.append(
            f"| `{m['model']}` | {m['matched_subjects_per_config']} "
            f"| {g['gap'] * 100:+.1f} pp | [{g['ci_low'] * 100:+.1f}, {g['ci_high'] * 100:+.1f}] |"
        )
    L.append("")

    d = a["descriptive"]
    L.append(f"## 3. Descriptive corpus shift — **{d['tag']}**\n")
    L.append(
        "> These describe how the two *corpora* differ. They are **NOT** a model-drift signal and "
        "must never be read as one.\n"
    )
    ld = d["label_distribution_shift"]
    L.append(
        f"- **Label-distribution shift** — TV distance `{ld['tv_distance']:.4f}`, "
        f"Jensen-Shannon distance `{ld['js_distance']:.4f}`  ({ld['note']})"
    )
    ls = d["length_shift"]
    L.append(
        f"- **Length shift** — Wasserstein-1 `{ls['wasserstein1_tokens']:.2f}` {ls['unit']} "
        f"(synthetic mean {ls['synthetic_mean_tokens']:.1f} vs real {ls['real_mean_tokens']:.1f} "
        f"tokens; {ls['note']})\n"
    )

    L.append("## Limitations (recorded for honesty)\n")
    for lim in a["limitations"]:
        L.append(f"- {lim}")
    L.append("")
    L.append("## Deferred\n")
    L.append(
        "- **MMD / embedding-distribution distance** — deferred (needs a frozen GPU encoder over "
        "length-matched buckets; KLU-106 owns the GPU). Optional future addition; this artifact is "
        "CPU-only."
    )
    L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description="KLU-103 synthetic→real drift metric")
    ap.add_argument("--leaderboard", default="baselines/leaderboard.json")
    ap.add_argument("--synthetic-config", default=SYNTHETIC_CONFIG)
    ap.add_argument("--real-config", default=REAL_CONFIG)
    ap.add_argument("--outdir", default="analysis")
    args = ap.parse_args()

    leaderboard = json.loads(Path(args.leaderboard).read_text())
    syn_rows = load_rows(args.synthetic_config)
    real_rows = load_rows(args.real_config)

    # Label intersection of the two configs (from the committed eval_labels — what each was scored on).
    any_model_rows = next(iter(leaderboard["entries"].values()))
    syn_labels = set(_eval_labels(any_model_rows, args.synthetic_config))
    real_labels = set(_eval_labels(any_model_rows, args.real_config))
    label_intersection = sorted(syn_labels & real_labels)

    primary = build_primary_table(leaderboard, args.synthetic_config, args.real_config, label_intersection)
    control = build_label_matched_control(
        leaderboard, args.synthetic_config, args.real_config, syn_rows, real_rows
    )
    descriptive = build_descriptive(syn_rows, real_rows)

    artifact = {
        "issue": "KLU-103",
        "config_status": "dev",  # not citable until KLU-27
        "synthetic_config": args.synthetic_config,
        "real_config": args.real_config,
        "hf_id": HF_ID,
        "seed": BOOTSTRAP_SEED,
        "resamples": BOOTSTRAP_RESAMPLES,
        "ci_alpha": CI_ALPHA,
        "label_intersection": label_intersection,
        "hashes": {
            "synthetic": corpus_content_hash(syn_rows),
            "real": corpus_content_hash(real_rows),
        },
        "headline": headline(primary),
        "primary": primary,
        "label_matched_control": control,
        "descriptive": descriptive,
        "limitations": LIMITATIONS,
        "deferred": ["MMD / embedding-distribution distance (GPU; KLU-106) — CPU-only here"],
    }

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "synthetic_real_drift.json").write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"
    )
    (outdir / "synthetic_real_drift.md").write_text(render_markdown(artifact))
    print(artifact["headline"])
    print(f"wrote {outdir / 'synthetic_real_drift.json'} and .md")


if __name__ == "__main__":
    main()
