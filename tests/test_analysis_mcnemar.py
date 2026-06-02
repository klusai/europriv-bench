"""KLU-53 — McNemar / exact-binomial logic in the analysis script.

These cover the *statistics* (no matplotlib needed): the 2x2 discordant counting, the exact
two-sided binomial p-value, and the verdict wording. The figure renderer is exercised separately
only when matplotlib is installed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "pareto_dissociation",
    Path(__file__).resolve().parent.parent / "analysis" / "pareto_dissociation.py",
)
pd = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pd)


def _dump(adapter: str, flags: dict[tuple[int, str, str], bool]) -> dict:
    return {
        "adapter": adapter,
        "subjects": [
            {"doc": k[0], "country": k[1], "value": k[2], "decode_bearing": True, "detected": v}
            for k, v in flags.items()
        ],
    }


def test_mcnemar_counts_discordant_pairs_directionally():
    keys = [(i, "RO", str(i)) for i in range(5)]
    # A (kp-deid) protects ALL; B protects only the first → b=4 (A protects, B leaks), c=0.
    a = _dump("kp-model", {k: True for k in keys})
    b = _dump("gliner", {keys[0]: True, **{k: False for k in keys[1:]}})
    res = pd.mcnemar(a, b)
    assert res["n_shared_subjects"] == 5
    assert res["discordant_b_A_protects_B_leaks"] == 4
    assert res["discordant_c_B_protects_A_leaks"] == 0
    assert res["table"]["both_detected"] == 1
    assert res["a_leaked"] == 0 and res["b_leaked"] == 4


def test_exact_binomial_symmetric_and_extremes():
    # All-discordant in one direction is the most significant; equal split is non-significant.
    assert pd._exact_binomial_two_sided(0, 0) == 1.0
    assert pd._exact_binomial_two_sided(10, 10) == pytest.approx(1.0, abs=1e-9)
    p_lopsided = pd._exact_binomial_two_sided(10, 0)
    assert p_lopsided == pytest.approx(2 * 0.5 ** 10, rel=1e-6)
    # Symmetry: (b, c) and (c, b) give the same two-sided p.
    assert pd._exact_binomial_two_sided(7, 2) == pytest.approx(pd._exact_binomial_two_sided(2, 7))


def test_exact_binomial_matches_scipy_when_available():
    scipy_stats = pytest.importorskip("scipy.stats")
    for b, c in [(3, 1), (8, 2), (15, 4), (0, 6)]:
        n, k = b + c, min(b, c)
        expected = scipy_stats.binomtest(k, n, 0.5, alternative="two-sided").pvalue
        assert pd._exact_binomial_two_sided(b, c) == pytest.approx(expected, rel=1e-9)


def test_verdict_significant_vs_not():
    big = pd.mcnemar(
        _dump("kp-model", {(i, "RO", str(i)): True for i in range(30)}),
        _dump("gliner", {(i, "RO", str(i)): False for i in range(30)}),
    )
    big["verdict"] = pd._verdict(big)
    assert "SIGNIFICANT" in big["verdict"] and "kp-model" in big["verdict"]

    keys = [(i, "RO", str(i)) for i in range(4)]
    tie = pd.mcnemar(
        _dump("kp-model", {keys[0]: True, keys[1]: True, keys[2]: False, keys[3]: False}),
        _dump("presidio", {keys[0]: True, keys[1]: False, keys[2]: True, keys[3]: False}),
    )
    tie["verdict"] = pd._verdict(tie)
    assert "NOT significant" in tie["verdict"]


def test_pareto_bad_frontier_excludes_dominated_and_includes_zero_leak():
    pts = [
        {"adapter": "gliner", "f1": 0.85, "leak_rate": 0.30},
        {"adapter": "tabularisai", "f1": 0.75, "leak_rate": 0.35},  # dominated: lower F1, higher leak
        {"adapter": "kp-model", "f1": 0.74, "leak_rate": 0.0},      # off-frontier: 0 leak
    ]
    frontier = {p["adapter"] for p in pd.pareto_bad_frontier(pts)}
    assert "gliner" in frontier        # highest F1, nothing beats it on both axes
    assert "kp-model" in frontier      # 0 leak → not dominated
    assert "tabularisai" not in frontier
