"""KLU-103 — synthetic→real drift statistics (no models, no I/O).

Covers the pure stat helpers in ``analysis/synthetic_real_drift.py``: the per-subject Bernoulli
bootstrap gap CI (determinism + direction + zero-gap collapse), the bounded/symmetric distribution
distances (TV, Jensen-Shannon — explicitly NOT raw KL), the 1-D Wasserstein-1 / EMD, the
order-independent corpus content hash, and label counting. The corpus loader (HF cache) is not
exercised here — these stay unit-pure.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "synthetic_real_drift",
    Path(__file__).resolve().parent.parent / "analysis" / "synthetic_real_drift.py",
)
srd = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(srd)


# --------------------------------------------------------------------------- #
# bootstrap_leak_gap_ci
# --------------------------------------------------------------------------- #
def test_bootstrap_gap_is_deterministic_for_fixed_seed():
    a = srd.bootstrap_leak_gap_ci(900, 1000, 600, 1000, metric="detection_rate", resamples=2000)
    b = srd.bootstrap_leak_gap_ci(900, 1000, 600, 1000, metric="detection_rate", resamples=2000)
    assert a == b  # byte-identical → reproducible artifact


def test_detection_rate_gap_positive_when_synthetic_detects_more():
    # synthetic detects 90%, real 60% → synthetic OVERSTATES performance → positive det-rate gap.
    r = srd.bootstrap_leak_gap_ci(900, 1000, 600, 1000, metric="detection_rate", resamples=3000)
    assert r["gap"] == pytest.approx(0.30, abs=1e-9)
    assert r["ci_low"] > 0 and r["excludes_zero"]


def test_leak_rate_gap_is_the_dual_of_detection_rate_gap():
    det = srd.bootstrap_leak_gap_ci(900, 1000, 600, 1000, metric="detection_rate", resamples=1000)
    leak = srd.bootstrap_leak_gap_ci(900, 1000, 600, 1000, metric="leak_rate", resamples=1000)
    # leak_rate = 1 − detection_rate, so the gap flips sign.
    assert leak["gap"] == pytest.approx(-det["gap"], abs=1e-9)


def test_identical_inputs_give_zero_gap_and_degenerate_ci():
    r = srd.bootstrap_leak_gap_ci(1000, 1000, 1000, 1000, metric="detection_rate", resamples=500)
    # Both sides detect everything → no variance, gap and CI collapse to 0.
    assert r["gap"] == 0.0 and r["ci_low"] == 0.0 and r["ci_high"] == 0.0
    assert not r["excludes_zero"]


def test_unknown_metric_rejected():
    with pytest.raises(ValueError):
        srd.bootstrap_leak_gap_ci(1, 2, 1, 2, metric="bogus")


# --------------------------------------------------------------------------- #
# distribution distances
# --------------------------------------------------------------------------- #
def test_tv_and_js_zero_for_identical_distributions():
    p = {"A": 10, "B": 30, "C": 60}
    assert srd.tv_distance(p, dict(p)) == pytest.approx(0.0, abs=1e-12)
    assert srd.js_distance(p, dict(p)) == pytest.approx(0.0, abs=1e-9)


def test_tv_and_js_bounded_in_unit_interval_for_disjoint_support():
    # Disjoint support → maximal divergence: TV = 1, JS distance = 1 (log2 JS divergence = 1).
    p = {"A": 1}
    q = {"B": 1}
    assert srd.tv_distance(p, q) == pytest.approx(1.0, abs=1e-12)
    assert srd.js_distance(p, q) == pytest.approx(1.0, abs=1e-9)


def test_tv_is_symmetric():
    p = {"A": 1, "B": 3}
    q = {"A": 2, "B": 2, "C": 1}
    assert srd.tv_distance(p, q) == pytest.approx(srd.tv_distance(q, p))
    assert srd.js_distance(p, q) == pytest.approx(srd.js_distance(q, p))


# --------------------------------------------------------------------------- #
# wasserstein1 / EMD
# --------------------------------------------------------------------------- #
def test_wasserstein1_zero_for_identical_samples():
    xs = [1.0, 2.0, 3.0, 4.0]
    assert srd.wasserstein1(xs, list(xs)) == pytest.approx(0.0, abs=1e-12)


def test_wasserstein1_equals_constant_shift():
    # Shifting every point by +5 makes EMD exactly 5 (mass moves a constant distance).
    xs = [0.0, 1.0, 2.0, 3.0]
    ys = [5.0, 6.0, 7.0, 8.0]
    assert srd.wasserstein1(xs, ys) == pytest.approx(5.0, abs=1e-9)


def test_wasserstein1_matches_scipy_when_available():
    scipy_stats = pytest.importorskip("scipy.stats")
    xs = [1.0, 2.0, 2.0, 9.0, 4.0]
    ys = [3.0, 3.0, 5.0, 1.0]
    expected = scipy_stats.wasserstein_distance(xs, ys)
    assert srd.wasserstein1(xs, ys) == pytest.approx(expected, rel=1e-6)


# --------------------------------------------------------------------------- #
# corpus content hash + label counts
# --------------------------------------------------------------------------- #
def test_content_hash_is_order_independent_and_span_order_independent():
    rows_a = [
        {"text": "x", "spans": [{"start": 0, "end": 1, "label": "PERSON"}]},
        {"text": "y", "spans": [{"start": 2, "end": 3, "label": "EMAIL"}]},
    ]
    rows_b = [
        {"text": "y", "spans": [{"start": 2, "end": 3, "label": "EMAIL"}]},
        {"text": "x", "spans": [{"start": 0, "end": 1, "label": "PERSON"}]},
    ]
    assert srd.corpus_content_hash(rows_a) == srd.corpus_content_hash(rows_b)


def test_content_hash_changes_with_content():
    base = [{"text": "x", "spans": [{"start": 0, "end": 1, "label": "PERSON"}]}]
    changed = [{"text": "x", "spans": [{"start": 0, "end": 1, "label": "EMAIL"}]}]
    assert srd.corpus_content_hash(base) != srd.corpus_content_hash(changed)


def test_label_counts_aggregates_spans():
    rows = [
        {"text": "a", "spans": [{"label": "PERSON"}, {"label": "PERSON"}]},
        {"text": "b", "spans": [{"label": "EMAIL"}]},
    ]
    c = srd.label_counts(rows)
    assert c["PERSON"] == 2 and c["EMAIL"] == 1
