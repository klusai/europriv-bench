"""RES-94 — realism/diversity-gap statistics (pure text/span + embedding-agnostic helpers).

Covers the load-bearing template-repetition skeleton, the diversity proxies (TTR,
sentence-length variance), the centroid cosine distance + its bootstrap-CI determinism, the
MAUVE-style score bounds, and the most-templated ranking. The HF corpus loader and the encoder
are NOT exercised here (those need the offline cache / model) — these stay unit-pure. The module is
loaded by path because ``analysis/`` ships scripts, not an importable package (same pattern as the
drift-module test).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

_SPEC = importlib.util.spec_from_file_location(
    "synthetic_realism_gap",
    Path(__file__).resolve().parent.parent / "analysis" / "synthetic_realism_gap.py",
)
srg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(srg)


# --------------------------------------------------------------------------- #
# document_skeleton + template_repetition (the headline "ours is templated" signal)
# --------------------------------------------------------------------------- #
def test_skeleton_collapses_docs_differing_only_in_identifiers():
    # Same template, different spliced name + number → identical skeleton.
    a = {"text": "Contract with Alice (ID 12345).",
         "spans": [{"start": 14, "end": 19, "label": "PERSON"},
                   {"start": 24, "end": 29, "label": "NATIONAL_ID"}]}
    b = {"text": "Contract with Bob (ID 98765).",
         "spans": [{"start": 14, "end": 17, "label": "PERSON"},
                   {"start": 22, "end": 27, "label": "NATIONAL_ID"}]}
    assert srg.document_skeleton(a) == srg.document_skeleton(b)


def test_skeleton_masks_label_and_normalizes_digits():
    row = {"text": "Pay 4521 to Jane", "spans": [{"start": 12, "end": 16, "label": "PERSON"}]}
    sk = srg.document_skeleton(row)
    assert "[person]" in sk
    assert "0000" in sk  # digits normalized to 0
    assert "4521" not in sk


def test_template_repetition_detects_templated_corpus():
    # 9 docs share one skeleton, 1 is unique → low unique ratio, high top-share.
    templated = [{"text": f"Hello {n}", "spans": [{"start": 6, "end": 6 + len(n), "label": "PERSON"}]}
                 for n in ["Al", "Bo", "Cy", "Di", "Ed", "Fi", "Gu", "Ha", "Iv"]]
    templated.append({"text": "A wholly different sentence entirely.", "spans": []})
    tr = srg.template_repetition(templated)
    assert tr["n_docs"] == 10
    assert tr["unique_ratio"] == pytest.approx(2 / 10)  # 2 distinct skeletons
    assert tr["top_skeleton_share"] == pytest.approx(9 / 10)


def test_template_repetition_all_unique():
    rows = [{"text": t, "spans": []} for t in ["alpha beta", "gamma delta epsilon", "zeta", "eta theta iota"]]
    tr = srg.template_repetition(rows)
    assert tr["unique_ratio"] == pytest.approx(1.0)


def test_skeleton_handles_overlapping_spans_defensively():
    # Overlapping / out-of-range spans must not crash; later overlap is skipped.
    row = {"text": "abcdef", "spans": [{"start": 0, "end": 4, "label": "X"},
                                        {"start": 2, "end": 5, "label": "Y"}]}
    sk = srg.document_skeleton(row)
    assert "[x]" in sk


# --------------------------------------------------------------------------- #
# type_token_ratio + sentence_length_variance
# --------------------------------------------------------------------------- #
def test_type_token_ratio_bounds():
    assert srg.type_token_ratio([{"text": "the the the", "spans": []}]) == pytest.approx(1 / 3)
    assert srg.type_token_ratio([{"text": "a b c d", "spans": []}]) == pytest.approx(1.0)
    assert srg.type_token_ratio([{"text": "", "spans": []}]) == 0.0


def test_sentence_length_variance_zero_for_uniform():
    rows = [{"text": "a b c. d e f. g h i.", "spans": []}]
    sv = srg.sentence_length_variance(rows)
    assert sv["mean"] == pytest.approx(3.0)
    assert sv["variance"] == pytest.approx(0.0)
    assert sv["n_sentences"] == 3


def test_sentence_length_variance_empty():
    assert srg.sentence_length_variance([{"text": "", "spans": []}])["variance"] == 0.0


# --------------------------------------------------------------------------- #
# centroid distance + bootstrap CI + MAUVE-style (embedding-agnostic: synthetic vectors)
# --------------------------------------------------------------------------- #
def test_centroid_distance_zero_for_identical_centroids():
    a = np.array([[1.0, 0.0], [0.0, 1.0]])
    b = np.array([[1.0, 0.0], [0.0, 1.0]])
    assert srg.centroid_cosine_distance(a, b) == pytest.approx(0.0, abs=1e-9)


def test_centroid_distance_larger_when_corpora_separate():
    a = np.array([[1.0, 0.0]] * 5)
    b = np.array([[0.0, 1.0]] * 5)  # orthogonal centroids → distance ~1
    assert srg.centroid_cosine_distance(a, b) == pytest.approx(1.0, abs=1e-9)


def test_bootstrap_centroid_ci_is_deterministic_and_brackets_point():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, (40, 8))
    b = rng.normal(0.5, 1, (40, 8))
    r1 = srg.bootstrap_centroid_distance_ci(a, b, resamples=300)
    r2 = srg.bootstrap_centroid_distance_ci(a, b, resamples=300)
    assert r1 == r2  # byte-identical → reproducible artifact
    assert r1["ci_low"] <= r1["point"] <= r1["ci_high"]


def test_mauve_style_high_for_identical_distributions():
    rng = np.random.default_rng(1)
    pts = rng.normal(0, 1, (80, 6))
    r = srg.mauve_style(pts, pts.copy(), bins=8, grid=20)
    assert 0.0 <= r["score"] <= 1.0
    assert r["score"] > 0.9  # same distribution → near 1


def test_mauve_style_lower_for_separated_distributions():
    rng = np.random.default_rng(2)
    a = rng.normal(0, 0.2, (80, 6))
    b = rng.normal(8.0, 0.2, (80, 6))  # far apart
    same = srg.mauve_style(a, a.copy(), bins=8, grid=20)["score"]
    far = srg.mauve_style(a, b, bins=8, grid=20)["score"]
    assert far < same


# --------------------------------------------------------------------------- #
# rank_most_templated
# --------------------------------------------------------------------------- #
def test_rank_orders_more_templated_language_first():
    def _lang(name, our_uniq, ai4p_uniq, our_top, ai4p_top, our_ttr, ai4p_ttr):
        return {
            "language": name,
            "embedding_centroid_distance": {"point": 0.1},
            "mauve_style": {"score": 0.5},
            "diversity": {
                "ours": {"template_repetition": {"unique_ratio": our_uniq, "top_skeleton_share": our_top}},
                "ai4privacy": {"template_repetition": {"unique_ratio": ai4p_uniq, "top_skeleton_share": ai4p_top}},
                "gaps": {
                    "unique_skeleton_ratio_delta": our_uniq - ai4p_uniq,
                    "top_skeleton_share_delta": our_top - ai4p_top,
                    "type_token_ratio_delta": our_ttr - ai4p_ttr,
                },
            },
        }

    very_templated = _lang("xx", our_uniq=0.05, ai4p_uniq=0.95, our_top=0.8, ai4p_top=0.01,
                           our_ttr=0.02, ai4p_ttr=0.40)
    diverse = _lang("yy", our_uniq=0.90, ai4p_uniq=0.92, our_top=0.02, ai4p_top=0.01,
                    our_ttr=0.38, ai4p_ttr=0.40)
    ranked = srg.rank_most_templated([diverse, very_templated])
    assert ranked[0]["language"] == "xx"
    assert ranked[0]["templated_score"] > ranked[1]["templated_score"]
