#!/usr/bin/env python3
"""RES-94 — realism / diversity gap: OUR template-splice synthetic vs Ai4Privacy LLM synthetic.

**This is NOT a synthetic→real drift number.** Ai4Privacy is *more-realistic SYNTHETIC* (an LLM
generator), NOT real data. Everything here is a **relative realism / diversity gap** between two
*synthetic* corpora — a diagnostic of how templated/narrow OUR generator is versus a stronger
synthetic baseline. A genuine synthetic→real drift number still needs TAB / real corpora (see
``analysis/synthetic_real_drift.py`` and the ECHR real-data work). Do not read any number here as
"closed the real gap."

Motivation
----------
Our own synthetic detection eval saturates (F1 = 1.000) because the corpus is template-spliced;
Ai4Privacy de-saturated it (RES-93). This script *measures the gap* so RES-95 (generator upgrade)
knows what to fix, and ranks the languages by how templated/narrow ours is.

What it computes, per intersecting language, as ``Δ = gap(ds-kp-general-{lang}, ai4privacy-{lang})``
-------------------------------------------------------------------------------------------------
1. **Embedding-centroid distance** — cosine distance between the two L2-normalized mean embeddings,
   with a document-resampling bootstrap 95% CI (sign-agnostic CI, same contract as the drift module).
2. **MAUVE-style divergence** — a self-contained quantize-then-divergence-frontier score over the
   joint embedding space (k-means bins; area under the mixture-KL frontier). Labelled **MAUVE-style**
   because the pip ``mauve`` package is not installed offline; the construction follows the published
   MAUVE definition (Pillutla et al. 2021) on a frozen offline encoder. 1 = identical, →0 = far.
3. **Diversity proxies** (the load-bearing "ours is templated" signal):
     * **type-token ratio (TTR)** — vocabulary richness;
     * **sentence-length variance** — structural monotony of length;
     * **template-repetition** — fraction of *unique document skeletons* (PII spans masked to their
       label placeholders, digits/whitespace normalized) and the **top-skeleton share**. A low unique
       ratio / high top-share = highly templated. This is the headline diversity signal.

Comparability contract (reused + minimally extended from ``synthetic_real_drift.py``)
-------------------------------------------------------------------------------------
* Same pinned-seed percentile bootstrap (``bootstrap_resamples``, ``ci_alpha``) and the bounded /
  symmetric distance philosophy (no raw KL on raw categories) as the drift module — imported, not
  re-implemented, so the two artifacts share one statistical contract.
* The drift module operates **dataset-vs-dataset on leaderboard scores**; here we extend the contract
  to **dataset-vs-dataset on text embeddings + corpus diversity**, which is the minimal extension the
  RES-94 question needs. The embedding distance + MAUVE are the embedding-distribution piece the
  drift module explicitly deferred (it was CPU/GPU-blocked there; this runs CPU-only here).
* Numbers are **computed, never hardcoded**; CPU-only embeddings (no GPU); honest labels throughout.

Offline-coverage honesty
------------------------
* Embedding model: the brief suggests multilingual-E5; **E5 is not in the offline cache**, so we use
  the cached multilingual ``microsoft/mdeberta-v3-base`` mean-pooled encoder as the offline
  substitute. The model id is pinned in the artifact. Swap to E5 by ``--embed-model`` when available.
* Ai4Privacy source: ``ai4privacy/pii-masking-openpii-1m`` — the verified-clean **CC-BY-4.0** open
  core (RES-93 verified + adopted exactly this tier; the harness already ingests it). The
  Llama-Community-licensed ``open-pii-masking-500k`` tier is **excluded by the program's license
  gate** and is **never** used here. The 1m parquet is not in the offline cache (only its README is),
  so this fetch needs network; we stream it row-by-row (``load_dataset(streaming=True)``) and stop as
  soon as each of the eight target languages has ``sample`` docs, never materializing the full 1.43M
  rows. If the fetch fails we STOP and report the traceback — no 500k fallback.
* Languages: OUR synthetic covers ro/en/pl/it/de/fr/es/nl; openpii-1m covers 23 EU languages
  **including ro and pl**, so all **eight** are scored — closing the ro/pl coverage gap the prior
  500k-tier run flagged. Coverage is still verified at load time (scored where present, flagged
  otherwise — never blocked).

Reproduce (europriv-bench venv; CPU; openpii-1m streamed over network, model from offline cache)::

    python analysis/synthetic_realism_gap.py --per-lang-sample 1500 --outdir analysis
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

# Reuse the drift module's pinned statistical contract (bootstrap + bounded distances) rather than
# re-implementing it: load it by path (it lives beside this file as a script, not an importable pkg).
_DRIFT_SPEC = importlib.util.spec_from_file_location(
    "synthetic_real_drift",
    Path(__file__).resolve().parent / "synthetic_real_drift.py",
)
srd = importlib.util.module_from_spec(_DRIFT_SPEC)
_DRIFT_SPEC.loader.exec_module(srd)

# Pinned reproducibility constants — inherit the drift module's so both artifacts share one contract.
BOOTSTRAP_SEED = srd.BOOTSTRAP_SEED
BOOTSTRAP_RESAMPLES = 2000  # centroid-distance bootstrap; lighter than the binomial one (CPU embeds)
CI_ALPHA = srd.CI_ALPHA  # 95% percentile CI
SAMPLE_SEED = 20260607  # pinned doc-subsampling seed (distinct from the bootstrap seed)

EMBED_MODEL = "microsoft/mdeberta-v3-base"  # offline multilingual substitute for E5 (pinned)
MAUVE_BINS = 25  # k-means quantization bins for the MAUVE-style frontier
MAUVE_GRID = 50  # mixing-weight grid resolution for the divergence frontier

OUR_DATASET = "klusai/ds-kp-general-{lang}-50k"
# The verified-clean CC-BY-4.0 open core (RES-93). NEVER the Llama-Community-License 500k tier.
AI4P_DATASET = "ai4privacy/pii-masking-openpii-1m"
AI4P_LICENSE = "CC-BY-4.0"

OUR_LANGS = ["ro", "en", "pl", "it", "de", "fr", "es", "nl"]
# All eight are present in pii-masking-openpii-1m's 23 EU languages (verified at load time, not
# assumed) — so ro and pl, uncovered by the prior 500k tier, are now scored.

HONEST_LABELS = {
    "comparison_kind": "relative-realism-and-diversity gap between TWO SYNTHETIC corpora",
    "NOT": "this is NOT a synthetic->real drift number; Ai4Privacy is more-realistic SYNTHETIC, "
    "not real. A real-data drift number still requires TAB / real corpora.",
    "ours": "ds-kp-general-{lang} — KlusAI template-splice synthetic (the saturating eval corpus)",
    "reference": "ai4privacy/pii-masking-openpii-1m — LLM-generated synthetic, verified-clean "
    "CC-BY-4.0 open core (RES-93); de-saturating baseline",
}


# --------------------------------------------------------------------------- #
# Corpus loading (offline HF cache; CPU; no model inference for text loading)
# --------------------------------------------------------------------------- #
def _offline_env() -> None:
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def load_our_rows(lang: str, sample: int, seed: int = SAMPLE_SEED) -> list[dict]:
    """Load OUR ds-kp-general-{lang} rows → [{text, spans}], deterministically subsampled."""
    _offline_env()
    from datasets import load_dataset

    ds = load_dataset(OUR_DATASET.format(lang=lang), split="train")
    rows = [{"text": r["text"], "spans": list(r["spans"])} for r in ds]
    return _subsample(rows, sample, seed)


def load_ai4p_by_lang(
    sample: int, langs: Sequence[str] = OUR_LANGS, seed: int = SAMPLE_SEED
) -> dict[str, list[dict]]:
    """Bucket pii-masking-openpii-1m by language → {lang: [{text, spans}]}, ``sample`` docs/lang.

    The 1m open core has ~1.43M rows across 23 EU languages, grouped by language. We stream it with
    ``load_dataset(..., streaming=True)`` and fill a per-language buffer of ``sample`` documents,
    stopping as soon as every target language is full — so we never materialize the whole dataset.
    Because the stream is grouped by language this reads sequentially through the target-language
    blocks; ``source_text`` is the unmasked document text we compare against ``ds-kp-general-{lang}``.

    Requires network (the 1m parquet is not in the offline cache — only its README is). If the fetch
    fails we raise — we never silently fall back to the Llama-Community-licensed 500k tier.

    ``privacy_mask`` carries ``label/start/end``; we normalize to our ``{label,start,end}`` span
    shape so the same skeleton/diversity code runs on both corpora.
    """
    # The dataset fetch needs network; do NOT force HF offline here (models stay offline-cached).
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    from datasets import load_dataset

    targets = set(langs)
    per = max(sample, 1)
    buckets: dict[str, list[dict]] = {lng: [] for lng in targets}

    try:
        ds = load_dataset(AI4P_DATASET, split="train", streaming=True)
    except Exception as exc:  # noqa: BLE001 — re-raise with the no-fallback contract spelled out.
        raise RuntimeError(
            f"Streaming fetch of {AI4P_DATASET} failed ({exc!r}). Refusing to fall back to the "
            "excluded Llama-Community-licensed 500k tier — STOP and report the traceback."
        ) from exc

    for row in ds:
        lng = row["language"]
        if lng in targets and len(buckets[lng]) < per:
            spans = [
                {"label": m["label"], "start": int(m["start"]), "end": int(m["end"])}
                for m in row["privacy_mask"]
            ]
            buckets[lng].append({"text": row["source_text"], "spans": spans})
        if all(len(buckets[lng]) >= per for lng in targets):
            break

    by_lang = {lng: rows for lng, rows in buckets.items() if rows}
    if not by_lang:
        raise RuntimeError(
            f"Fetched zero rows for target languages {sorted(targets)} from {AI4P_DATASET} — STOP "
            "and report. Refusing to fall back to the excluded 500k tier."
        )
    # Already capped at ``sample`` per language by the streaming loop; subsample is a no-op guard.
    return {lng: _subsample(rows, sample, seed) for lng, rows in by_lang.items()}


def _subsample(rows: list[dict], sample: int, seed: int) -> list[dict]:
    if sample <= 0 or sample >= len(rows):
        return rows
    rng = random.Random(seed)
    idx = sorted(rng.sample(range(len(rows)), sample))
    return [rows[i] for i in idx]


# --------------------------------------------------------------------------- #
# Diversity proxies (pure text/span stats — no model)
# --------------------------------------------------------------------------- #
_WORD_RE = re.compile(r"\w+", re.UNICODE)
_SENT_SPLIT_RE = re.compile(r"[.!?\n]+")
_DIGIT_RE = re.compile(r"\d")
_WS_RE = re.compile(r"\s+")


def type_token_ratio(rows: Sequence[dict]) -> float:
    """Corpus type-token ratio = |unique lowercased word types| / |word tokens| (higher = richer)."""
    types: set[str] = set()
    tokens = 0
    for r in rows:
        for w in _WORD_RE.findall(r["text"].lower()):
            types.add(w)
            tokens += 1
    return len(types) / tokens if tokens else 0.0


def sentence_length_variance(rows: Sequence[dict]) -> dict[str, float]:
    """Variance (and mean) of sentence length in words. Low variance = monotone/templated structure."""
    lengths: list[int] = []
    for r in rows:
        for sent in _SENT_SPLIT_RE.split(r["text"]):
            n = len(_WORD_RE.findall(sent))
            if n > 0:
                lengths.append(n)
    if not lengths:
        return {"mean": 0.0, "variance": 0.0, "n_sentences": 0}
    mean = sum(lengths) / len(lengths)
    var = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    return {"mean": mean, "variance": var, "n_sentences": len(lengths)}


def document_skeleton(row: dict) -> str:
    """Mask every PII span to ``[LABEL]``, normalize digits→0 and whitespace, → structural skeleton.

    Two documents that differ only in their spliced-in identifiers / numbers collapse to the same
    skeleton — so a template-splice generator produces few distinct skeletons, an LLM generator many.
    """
    text = row["text"]
    spans = sorted(row.get("spans", []), key=lambda s: int(s["start"]))
    out: list[str] = []
    cursor = 0
    for sp in spans:
        s, e = int(sp["start"]), int(sp["end"])
        if s < cursor or s > len(text):  # overlapping / out-of-range span: skip defensively
            continue
        out.append(text[cursor:s])
        out.append(f"[{sp['label']}]")
        cursor = max(cursor, e)
    out.append(text[cursor:])
    masked = "".join(out)
    masked = _DIGIT_RE.sub("0", masked)
    masked = _WS_RE.sub(" ", masked).strip().lower()
    return masked


def template_repetition(rows: Sequence[dict]) -> dict[str, float]:
    """Unique-skeleton ratio + top-skeleton share. Low ratio / high top-share = highly templated."""
    skeletons = [document_skeleton(r) for r in rows]
    n = len(skeletons)
    if n == 0:
        return {"n_docs": 0, "unique_skeletons": 0, "unique_ratio": 0.0, "top_skeleton_share": 0.0}
    counts = Counter(skeletons)
    top_share = counts.most_common(1)[0][1] / n
    return {
        "n_docs": n,
        "unique_skeletons": len(counts),
        "unique_ratio": len(counts) / n,  # 1.0 = every doc structurally unique
        "top_skeleton_share": top_share,  # fraction of docs sharing the single most common skeleton
    }


def diversity_proxies(rows: Sequence[dict]) -> dict:
    return {
        "type_token_ratio": type_token_ratio(rows),
        "sentence_length": sentence_length_variance(rows),
        "template_repetition": template_repetition(rows),
    }


# --------------------------------------------------------------------------- #
# Embeddings (CPU, offline, frozen encoder, mean-pooled + L2-normalized)
# --------------------------------------------------------------------------- #
def embed_corpus(texts: Sequence[str], model_name: str, batch_size: int = 32, max_len: int = 128):
    """Mean-pool the frozen encoder's last hidden state, L2-normalize. Returns an (n, d) numpy array."""
    _offline_env()
    import numpy as np
    import torch
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(max(1, os.cpu_count() or 1))
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()
    out: list = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = list(texts[i : i + batch_size])
            enc = tok(batch, return_tensors="pt", padding=True, truncation=True, max_length=max_len)
            hidden = model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).type_as(hidden)
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            out.append(pooled.cpu().numpy())
    return np.vstack(out)


def centroid_cosine_distance(emb_a, emb_b) -> float:
    """Cosine distance between the two corpus mean embeddings (1 - cos sim of centroids), in [0, 2]."""
    import numpy as np

    ca = emb_a.mean(axis=0)
    cb = emb_b.mean(axis=0)
    denom = (np.linalg.norm(ca) * np.linalg.norm(cb)) or 1e-9
    return float(1.0 - (ca @ cb) / denom)


def bootstrap_centroid_distance_ci(
    emb_a,
    emb_b,
    *,
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
    alpha: float = CI_ALPHA,
) -> dict:
    """Document-resampling percentile CI for the centroid cosine distance (sign-agnostic CI).

    Resample documents with replacement on each side, recompute the centroid distance. Pinned seed →
    reproducible. Same percentile-CI contract as ``synthetic_real_drift.bootstrap_leak_gap_ci``.
    """
    import numpy as np

    point = centroid_cosine_distance(emb_a, emb_b)
    rng = np.random.default_rng(seed)
    na, nb = len(emb_a), len(emb_b)
    dists: list[float] = []
    for _ in range(resamples):
        sa = emb_a[rng.integers(0, na, na)]
        sb = emb_b[rng.integers(0, nb, nb)]
        dists.append(centroid_cosine_distance(sa, sb))
    dists.sort()
    return {
        "metric": "centroid_cosine_distance",
        "point": point,
        "ci_low": srd._percentile(dists, alpha / 2.0),
        "ci_high": srd._percentile(dists, 1.0 - alpha / 2.0),
        "resamples": resamples,
        "seed": seed,
        "note": "1 - cosine(mean(ours), mean(ai4privacy)); larger = corpora further apart.",
    }


def mauve_style(emb_a, emb_b, *, bins: int = MAUVE_BINS, grid: int = MAUVE_GRID, seed: int = BOOTSTRAP_SEED) -> dict:
    """Self-contained MAUVE-style score over the joint embedding space (Pillutla et al. 2021 form).

    Quantize the union of both corpora's embeddings into ``bins`` k-means clusters, form the two
    cluster histograms P (ours) and Q (ai4privacy), and integrate the divergence frontier: for a grid
    of mixing weights w, the mixture R_w = w·P + (1-w)·Q gives (KL(P‖R_w), KL(Q‖R_w)); MAUVE is the
    area under exp(-c·KL) traded off across w. 1 = identical distributions, →0 = far apart.

    Labelled **MAUVE-style** (not the pip ``mauve`` package, which is unavailable offline): same
    quantize→divergence-frontier construction, on a frozen offline encoder, CPU-only.
    """
    import numpy as np
    from sklearn.cluster import KMeans

    joint = np.vstack([emb_a, emb_b])
    k = min(bins, len(joint))
    km = KMeans(n_clusters=k, random_state=seed, n_init=10)
    labels = km.fit_predict(joint)
    la, lb = labels[: len(emb_a)], labels[len(emb_a) :]
    p = np.bincount(la, minlength=k).astype(float)
    q = np.bincount(lb, minlength=k).astype(float)
    p /= p.sum()
    q /= q.sum()

    def _kl(a, b):
        mask = a > 0
        return float(np.sum(a[mask] * np.log(a[mask] / np.clip(b[mask], 1e-12, None))))

    c = 5.0  # standard MAUVE scaling constant
    # Divergence frontier (Pillutla et al. 2021): for mixing weight w, R_w = w·P + (1-w)·Q; the
    # frontier point is (exp(-c·KL(Q‖R_w)), exp(-c·KL(P‖R_w))). As w sweeps 0→1, R_w moves Q→P and
    # the point sweeps a curve in [0,1]². MAUVE is the area under that curve, anchored to the axes at
    # (0,1) and (1,0) so the integral is a proper frontier (P=Q ⇒ curve hugs (1,1) ⇒ area→1; far
    # apart ⇒ curve pulled toward the origin ⇒ area→0).
    ws = np.linspace(0.0, 1.0, grid)
    xs, ys = [0.0], [1.0]  # axis anchor: all-Q mixture limit
    for w in ws:
        r = w * p + (1 - w) * q
        xs.append(math.exp(-c * _kl(q, r)))
        ys.append(math.exp(-c * _kl(p, r)))
    xs.append(1.0)  # axis anchor: all-P mixture limit
    ys.append(0.0)
    order = np.argsort(xs)
    xs = np.array(xs)[order]
    ys = np.array(ys)[order]
    area = float(np.trapezoid(ys, xs)) if hasattr(np, "trapezoid") else float(np.trapz(ys, xs))
    return {
        "metric": "mauve_style",
        "score": max(0.0, min(1.0, area)),
        "bins": k,
        "grid": grid,
        "c": c,
        "note": "MAUVE-style (quantize+divergence-frontier), self-contained offline; 1=identical, "
        "lower=further apart. NOT the pip `mauve` package.",
    }


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def score_language(lang: str, our_rows: list[dict], ai4p_rows: list[dict], embed_model: str) -> dict:
    """Full per-language gap: diversity proxies (both sides) + embedding centroid + MAUVE-style."""
    our_div = diversity_proxies(our_rows)
    ai4p_div = diversity_proxies(ai4p_rows)

    emb_ours = embed_corpus([r["text"] for r in our_rows], embed_model)
    emb_ai4p = embed_corpus([r["text"] for r in ai4p_rows], embed_model)
    centroid = bootstrap_centroid_distance_ci(emb_ours, emb_ai4p)
    mauve = mauve_style(emb_ours, emb_ai4p)

    return {
        "language": lang,
        "n_ours": len(our_rows),
        "n_ai4privacy": len(ai4p_rows),
        "embedding_centroid_distance": centroid,
        "mauve_style": mauve,
        "diversity": {
            "ours": our_div,
            "ai4privacy": ai4p_div,
            "gaps": {
                "type_token_ratio_delta": our_div["type_token_ratio"]
                - ai4p_div["type_token_ratio"],
                "sentence_length_variance_delta": our_div["sentence_length"]["variance"]
                - ai4p_div["sentence_length"]["variance"],
                "unique_skeleton_ratio_delta": our_div["template_repetition"]["unique_ratio"]
                - ai4p_div["template_repetition"]["unique_ratio"],
                "top_skeleton_share_delta": our_div["template_repetition"]["top_skeleton_share"]
                - ai4p_div["template_repetition"]["top_skeleton_share"],
                "note": "delta = ours - ai4privacy. Negative TTR/variance/unique-ratio + positive "
                "top-share => OURS is more templated/narrow.",
            },
        },
    }


def rank_most_templated(per_lang: list[dict]) -> list[dict]:
    """Rank languages by how templated/narrow OURS is vs Ai4Privacy → the RES-95 actionable input.

    Composite templated-ness score (higher = ours is more templated relative to Ai4Privacy):
      + (ai4p_unique_ratio - our_unique_ratio)   [ours repeats structures more]
      + (our_top_share - ai4p_top_share)          [one skeleton dominates ours]
      + (ai4p_ttr - our_ttr)                       [ours has poorer vocabulary]
    Each term is naturally in a comparable [-1, 1]-ish range; we report the components too.
    """
    ranked = []
    for r in per_lang:
        g = r["diversity"]["gaps"]
        score = (
            (-g["unique_skeleton_ratio_delta"])
            + g["top_skeleton_share_delta"]
            + (-g["type_token_ratio_delta"])
        )
        ranked.append(
            {
                "language": r["language"],
                "templated_score": score,
                "components": {
                    "unique_ratio_deficit": -g["unique_skeleton_ratio_delta"],
                    "top_skeleton_share_excess": g["top_skeleton_share_delta"],
                    "ttr_deficit": -g["type_token_ratio_delta"],
                },
                "our_unique_ratio": r["diversity"]["ours"]["template_repetition"]["unique_ratio"],
                "ai4p_unique_ratio": r["diversity"]["ai4privacy"]["template_repetition"][
                    "unique_ratio"
                ],
                "centroid_distance": r["embedding_centroid_distance"]["point"],
                "mauve_style": r["mauve_style"]["score"],
            }
        )
    ranked.sort(key=lambda x: x["templated_score"], reverse=True)
    return ranked


def render_markdown(artifact: dict) -> str:
    a = artifact
    L: list[str] = []
    L.append(f"# RES-94 — synthetic realism / diversity gap (ours vs Ai4Privacy)  ·  {a['date']}\n")
    L.append(
        "> **RELATIVE-REALISM / DIVERSITY GAP between TWO SYNTHETIC corpora — NOT a "
        "synthetic→real drift number.** Ai4Privacy is *more-realistic SYNTHETIC* (an LLM generator), "
        "**not real data**; a real-data drift number still needs TAB / real corpora. Do not read any "
        "number here as 'closed the real gap'. dev-tier diagnostic; feeds RES-95.\n"
    )
    L.append(f"- ours: `{a['our_dataset']}` (template-splice synthetic, the saturating eval corpus)")
    L.append(
        f"- reference: `{a['ai4privacy_dataset']}` "
        f"({a.get('ai4privacy_license', 'CC-BY-4.0')}) — Ai4Privacy LLM synthetic, verified-clean "
        "open core (RES-93); the Llama-Community-licensed 500k tier is excluded and NOT used"
    )
    L.append(f"- embedding model: `{a['embed_model']}`  ({a['embed_model_note']})")
    L.append(
        f"- bootstrap seed `{a['seed']}`, resamples `{a['resamples']}`, 95% percentile CI; "
        f"per-language sample `{a['per_lang_sample']}` docs/side (subsample seed `{a['sample_seed']}`)"
    )
    L.append(f"- intersecting languages scored: `{', '.join(a['scored_languages'])}`")
    if a["uncovered_languages"]:
        L.append(
            f"- **uncovered (flagged, honest coverage):** `{', '.join(a['uncovered_languages'])}` "
            "— no Ai4Privacy counterpart in the cached release; not scored.\n"
        )
    else:
        L.append("")

    L.append("## Ranked: how templated/narrow OURS is vs Ai4Privacy (the RES-95 input)\n")
    L.append(
        "Higher `templated_score` = ours is more templated/narrow relative to Ai4Privacy "
        "(unique-skeleton deficit + top-skeleton-share excess + TTR deficit).\n"
    )
    L.append("| rank | lang | templated score | our unique-skel ratio | ai4p unique-skel ratio | centroid dist | MAUVE-style |")
    L.append("|---:|---|---:|---:|---:|---:|---:|")
    for i, r in enumerate(a["ranked_most_templated"], 1):
        L.append(
            f"| {i} | `{r['language']}` | {r['templated_score']:+.3f} "
            f"| {r['our_unique_ratio']:.3f} | {r['ai4p_unique_ratio']:.3f} "
            f"| {r['centroid_distance']:.4f} | {r['mauve_style']:.3f} |"
        )
    L.append("")

    L.append("## Per-language realism / diversity gap (with 95% CIs)\n")
    L.append(
        "| lang | centroid dist | 95% CI | MAUVE-style | TTR ours/ai4p | sent-len var ours/ai4p | "
        "template-repetition: unique-ratio ours/ai4p (top-share) |"
    )
    L.append("|---|---:|---|---:|---|---|---|")
    for r in a["per_language"]:
        cd = r["embedding_centroid_distance"]
        do, da = r["diversity"]["ours"], r["diversity"]["ai4privacy"]
        tr_o = do["template_repetition"]
        tr_a = da["template_repetition"]
        L.append(
            f"| `{r['language']}` "
            f"| {cd['point']:.4f} | [{cd['ci_low']:.4f}, {cd['ci_high']:.4f}] "
            f"| {r['mauve_style']['score']:.3f} "
            f"| {do['type_token_ratio']:.4f} / {da['type_token_ratio']:.4f} "
            f"| {do['sentence_length']['variance']:.1f} / {da['sentence_length']['variance']:.1f} "
            f"| {tr_o['unique_ratio']:.3f} / {tr_a['unique_ratio']:.3f} "
            f"(top {tr_o['top_skeleton_share']:.3f} / {tr_a['top_skeleton_share']:.3f}) |"
        )
    L.append("")

    L.append("## Template-repetition — the load-bearing 'ours is templated' signal\n")
    L.append(
        "Document skeletons mask every PII span to its `[LABEL]` placeholder and normalize "
        "digits/whitespace, so two docs differing only in spliced identifiers collapse to one "
        "skeleton. A template-splice generator yields few distinct skeletons (low unique-ratio, high "
        "top-share); an LLM generator yields many.\n"
    )
    for r in a["per_language"]:
        tr_o = r["diversity"]["ours"]["template_repetition"]
        tr_a = r["diversity"]["ai4privacy"]["template_repetition"]
        L.append(
            f"- `{r['language']}`: **ours** {tr_o['unique_skeletons']}/{tr_o['n_docs']} unique "
            f"(ratio {tr_o['unique_ratio']:.3f}, top-share {tr_o['top_skeleton_share']:.3f}) "
            f"vs **Ai4Privacy** {tr_a['unique_skeletons']}/{tr_a['n_docs']} unique "
            f"(ratio {tr_a['unique_ratio']:.3f}, top-share {tr_a['top_skeleton_share']:.3f})"
        )
    L.append("")

    L.append("## Honest framing & limitations\n")
    for k, v in a["honest_labels"].items():
        L.append(f"- **{k}**: {v}")
    for lim in a["limitations"]:
        L.append(f"- {lim}")
    L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description="RES-94 synthetic realism/diversity gap (ours vs Ai4Privacy)")
    ap.add_argument("--per-lang-sample", type=int, default=1500,
                    help="docs sampled per side per language (deterministic; CPU embedding budget)")
    ap.add_argument("--embed-model", default=EMBED_MODEL)
    ap.add_argument("--outdir", default="analysis")
    ap.add_argument("--date", default="2026-06-07")
    args = ap.parse_args()

    ai4p_by_lang = load_ai4p_by_lang(args.per_lang_sample)
    ai4p_langs = set(ai4p_by_lang)

    scored_langs = [lng for lng in OUR_LANGS if lng in ai4p_langs]
    uncovered = [lng for lng in OUR_LANGS if lng not in ai4p_langs]

    per_language: list[dict] = []
    for lang in scored_langs:
        our_rows = load_our_rows(lang, args.per_lang_sample)
        print(f"[score] {lang}: ours n={len(our_rows)}, ai4p n={len(ai4p_by_lang[lang])} ...")
        per_language.append(
            score_language(lang, our_rows, ai4p_by_lang[lang], args.embed_model)
        )

    ranked = rank_most_templated(per_language)

    artifact = {
        "issue": "RES-94",
        "date": args.date,
        "config_status": "dev",
        "comparison": "relative-realism-and-diversity gap (ours vs Ai4Privacy) — NOT synthetic->real drift",
        "our_dataset": OUR_DATASET,
        "ai4privacy_dataset": AI4P_DATASET,
        "ai4privacy_license": AI4P_LICENSE,
        "ai4privacy_source_note": "pii-masking-openpii-1m (CC-BY-4.0) — verified-clean open core "
        "(RES-93). The Llama-Community-licensed 500k tier is excluded by the license gate; not used.",
        "embed_model": args.embed_model,
        "embed_model_note": "offline multilingual substitute for multilingual-E5 "
        "(E5 not in offline cache); mean-pooled, L2-normalized, CPU-only.",
        "seed": BOOTSTRAP_SEED,
        "sample_seed": SAMPLE_SEED,
        "resamples": BOOTSTRAP_RESAMPLES,
        "ci_alpha": CI_ALPHA,
        "per_lang_sample": args.per_lang_sample,
        "scored_languages": scored_langs,
        "uncovered_languages": uncovered,
        "honest_labels": HONEST_LABELS,
        "ranked_most_templated": ranked,
        "per_language": per_language,
        "contract_reuse": "Reuses synthetic_real_drift.py's pinned percentile-bootstrap + bounded "
        "distance contract (imported, not re-implemented); extends it from leaderboard-score "
        "dataset comparison to text-embedding + diversity dataset comparison (the embedding piece "
        "the drift module deferred). CPU-only.",
        "limitations": [
            "Ai4Privacy source is ai4privacy/pii-masking-openpii-1m (CC-BY-4.0) — the verified-clean "
            "open core (RES-93). The Llama-Community-licensed 500k tier is excluded by the license "
            "gate and is never used. The 1m dataset is streamed over network row-by-row (only its "
            "README is cached); the stream stops once each target language has sample docs.",
            "Embedding model is microsoft/mdeberta-v3-base, the offline multilingual substitute for "
            "multilingual-E5 (not cached). Absolute embedding distances are encoder-dependent; the "
            "language RANKING and the diversity proxies are the robust, encoder-independent signals.",
            "All eight of our languages (incl. ro and pl) have an openpii-1m counterpart and are "
            "scored — the prior ro/pl coverage gap is closed.",
            "MAUVE-style is a self-contained quantize+divergence-frontier implementation (the pip "
            "`mauve` package is unavailable offline); same construction, frozen offline encoder.",
            "All numbers are computed here at run time; nothing is hardcoded. CPU-only.",
        ],
    }

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "synthetic_realism_gap.json").write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"
    )
    (outdir / "synthetic_realism_gap.md").write_text(render_markdown(artifact))
    print("\n=== ranked most-templated (ours vs Ai4Privacy) ===")
    for i, r in enumerate(ranked, 1):
        print(f"  {i}. {r['language']}: templated_score={r['templated_score']:+.3f} "
              f"(our unique-ratio {r['our_unique_ratio']:.3f} vs ai4p {r['ai4p_unique_ratio']:.3f})")
    print(f"wrote {outdir / 'synthetic_realism_gap.json'} and .md")


if __name__ == "__main__":
    main()
