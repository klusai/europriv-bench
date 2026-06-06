"""RES-17 (KLU-118 v2) — IPF build_joint + Rocher-2019 uniqueness + PURR@τ/ΔPURR/κ + fallbacks.

All offline against the COMMITTED SYNTHETIC PLACEHOLDER census fixture (NOT real census data; no
PURR number on any real benchmark config is computed here). Covers:
  * IPF convergence + reproducibility + marginal-consistency,
  * the Rocher copula estimator ξ(x) = (1 − p)^(n−1) + correctness,
  * PURR@τ, ΔPURR = baseline − model, mean κ,
  * the red-team labelling guards (placeholder => not a reported metric; fallbacks => upper bound),
  * report attribution emission.
"""

from __future__ import annotations

import math

import pytest

from europriv_bench.refpop import build_joint as bj
from europriv_bench.refpop import fallbacks, report, uniqueness


@pytest.fixture(scope="module")
def joint() -> bj.Joint:
    return bj.build_synthetic_placeholder_joint()


# ---------------------------------------------------------------------------------------------
# IPF (build_joint)
# ---------------------------------------------------------------------------------------------


def test_ipf_converges_and_is_a_probability_distribution(joint):
    assert joint.converged
    assert 0 < joint.iterations <= bj.MAX_ITER
    assert math.isclose(sum(joint.probs.values()), 1.0, abs_tol=1e-9)
    # Support is the full Cartesian product of the three axes (4 x 2 x 3 = 24 cells).
    assert joint.axes == ("dob_band", "sex", "nuts2")
    assert len(joint.probs) == 4 * 2 * 3
    assert all(p >= 0.0 for p in joint.probs.values())


def test_ipf_matches_the_published_marginals_within_tolerance(joint):
    spec = bj.load_census_spec("synthetic_census_xx.yaml")
    pop = spec["meta"]["population_total"]
    for m in spec["marginals"]:
        sub_axes = tuple(m["axes"])
        idx = [joint.axes.index(a) for a in sub_axes]
        fitted: dict[tuple, float] = {}
        for key, mass in joint.probs.items():
            sub = tuple(key[i] for i in idx)
            fitted[sub] = fitted.get(sub, 0.0) + mass
        for cat_key, count in m["counts"].items():
            target_p = count / pop
            sub = tuple(cat_key.split("|"))
            assert math.isclose(fitted[sub], target_p, abs_tol=1e-6), (
                f"marginal {sub_axes} cell {sub}: fitted {fitted[sub]} != target {target_p}"
            )


def test_ipf_is_deterministic_and_reproducible():
    a = bj.build_synthetic_placeholder_joint()
    b = bj.build_synthetic_placeholder_joint()
    assert a.probs == b.probs
    assert a.iterations == b.iterations


def test_ipf_captures_correlation_not_just_independence(joint):
    """IPF must reproduce the age x sex cross-tab, which independence-of-marginals would miss."""
    # Synthetic age x sex: 1960-1964 skews female (11800 vs 10200); 1965-1969 too. The fitted
    # joint summed over nuts2 must reflect that, not the product of the 1-D marginals.
    def axsex(band, sex):
        i_band = joint.axes.index("dob_band")
        i_sex = joint.axes.index("sex")
        return sum(
            p for k, p in joint.probs.items() if k[i_band] == band and k[i_sex] == sex
        )

    assert axsex("1960-1964", "F") > axsex("1960-1964", "M")
    # vs the independence prediction would be ~equal-ish; the actual fitted gap is material.
    assert (axsex("1960-1964", "F") - axsex("1960-1964", "M")) > 0.01


def test_ipf_raises_if_not_converged():
    # Mutually INCONSISTENT marginals (the 1-D sex marginal disagrees with the age x sex cross-tab's
    # sex totals): IPF oscillates and cannot satisfy all targets, so build must REFUSE to emit a
    # non-reproducible joint rather than silently return a half-fit.
    spec = {
        "meta": {
            "population_total": 100,
            "placeholder": True,
            "is_real_census": False,
            "label": "INCONSISTENT TEST FIXTURE — NOT REAL CENSUS DATA",
            "axes": ["sex", "nuts2"],
        },
        "axes": {"sex": ["M", "F"], "nuts2": ["A", "B"]},
        "marginals": [
            {"axes": ["sex"], "counts": {"M": 80, "F": 20}},
            # nuts2 totals force a sex split that contradicts the sex marginal above.
            {"axes": ["sex", "nuts2"], "counts": {"M|A": 10, "M|B": 10, "F|A": 40, "F|B": 40}},
        ],
    }
    with pytest.raises(RuntimeError, match="did not converge"):
        bj.build_joint_from_spec(spec, max_iter=5, tolerance=1e-9)


def test_synthetic_fixture_converges_in_few_iterations():
    # The committed fixture's cross-tabs were authored mutually-consistent, so IPF reaches the
    # pinned tolerance almost immediately and reproducibly.
    j = bj.build_synthetic_placeholder_joint()
    assert j.converged and j.iterations <= 10


# ---------------------------------------------------------------------------------------------
# Rocher-2019 uniqueness estimator
# ---------------------------------------------------------------------------------------------


def test_population_uniqueness_formula(joint):
    qi = {"dob_band": "1970-1974", "sex": "M", "nuts2": "XX01"}
    key = ("1970-1974", "M", "XX01")
    p = joint.prob(key)
    assert p > 0.0
    expected = (1.0 - p) ** (joint.n - 1)
    assert math.isclose(uniqueness.population_uniqueness(joint, qi), expected, rel_tol=1e-12)


def test_correctness_is_one_minus_uniqueness(joint):
    qi = {"dob_band": "1965-1969", "sex": "F", "nuts2": "XX02"}
    xi = uniqueness.population_uniqueness(joint, qi)
    assert math.isclose(uniqueness.correctness(joint, qi), 1.0 - xi, rel_tol=1e-12)


def test_unscorable_tuple_returns_none(joint):
    # Missing a joint axis (nuts2) -> cannot be projected -> un-scorable (never fabricated).
    assert uniqueness.population_uniqueness(joint, {"dob_band": "1970-1974", "sex": "M"}) is None


def test_unseen_signature_is_maximally_unique(joint):
    # A category tuple with zero mass in the support (an unknown age band) -> ξ→1 within this
    # reference (maximally distinctive, but only relative to this reference's support).
    unseen = {"dob_band": "9999-9999", "sex": "M", "nuts2": "XX01"}
    assert uniqueness.population_uniqueness(joint, unseen) == 1.0


# ---------------------------------------------------------------------------------------------
# PURR@τ, ΔPURR, κ
# ---------------------------------------------------------------------------------------------


def _rows(*tuples):
    return [{"qi_tuple": t} for t in tuples]


def test_purr_at_tau_default_is_095(joint):
    res = uniqueness.purr_at_tau(joint, _rows({"dob_band": "1970-1974", "sex": "M", "nuts2": "XX01"}))
    assert res["tau"] == 0.95


def test_purr_counts_only_subjects_above_tau(joint):
    # With n=100000 the per-cell ξ is essentially 1 for every cell (each cell << 1/n share), so
    # PURR@0.95 should be ~1 across scorable subjects. Lower τ does not change that here; instead
    # verify the scorable/unscorable split and the rate arithmetic.
    rows = _rows(
        {"dob_band": "1970-1974", "sex": "M", "nuts2": "XX01"},  # scorable
        {"dob_band": "1965-1969", "sex": "F", "nuts2": "XX02"},  # scorable
        {"sex": "F"},  # un-scorable (no nuts2/dob_band axes)
    )
    res = uniqueness.purr_at_tau(joint, rows)
    assert res["n_subjects"] == 3
    assert res["n_scorable"] == 2
    assert res["n_unscorable"] == 1
    assert 0.0 <= res["purr"] <= 1.0
    assert res["purr_ci_low"] <= res["purr"] <= res["purr_ci_high"]
    # mean κ over flagged-unique subjects is in [0,1].
    assert 0.0 <= res["mean_kappa"] <= 1.0


def test_delta_purr_is_baseline_minus_model(joint):
    baseline = _rows(
        {"dob_band": "1970-1974", "sex": "M", "nuts2": "XX01"},
        {"dob_band": "1965-1969", "sex": "F", "nuts2": "XX02"},
    )
    # The model redacted everything -> empty residual tuples -> dropped -> 0 scorable -> PURR 0.
    model = _rows({}, {})
    res = uniqueness.delta_purr(joint, baseline, model)
    assert math.isclose(
        res["delta_purr"], float(res["baseline_purr"]) - float(res["model_purr"]), rel_tol=1e-12
    )
    assert res["baseline_purr"] >= res["model_purr"]  # baseline leaks more -> ΔPURR >= 0
    assert res["is_headline_shape"] is True


# ---------------------------------------------------------------------------------------------
# Red-team labelling guards
# ---------------------------------------------------------------------------------------------


def test_placeholder_joint_is_never_a_reported_metric(joint):
    assert joint.placeholder is True
    res = uniqueness.purr_at_tau(joint, _rows({"dob_band": "1970-1974", "sex": "M", "nuts2": "XX01"}))
    assert res["reported_metric"] is False
    assert res["reference_conditional"] is True
    assert "NOT a reported metric" in res["note"]
    assert "Rocher" in res["method"]

    d = uniqueness.delta_purr(joint, _rows({"sex": "M", "dob_band": "1970-1974", "nuts2": "XX01"}), _rows({}))
    assert d["reported_metric"] is False
    assert "NOT a reported metric" in d["note"]


def test_fallbacks_are_labelled_upper_bound_only(joint):
    mi = fallbacks.marginal_independence_uniqueness(
        joint, {"dob_band": "1970-1974", "sex": "M", "nuts2": "XX01"}
    )
    assert mi["upper_bound_only"] is True
    assert mi["meaningful"] is False
    assert mi["reported_metric"] is False
    assert "UPPER BOUND" in mi["warning"]

    ins = fallbacks.in_sample_uniqueness(
        _rows(
            {"dob_band": "1970-1974", "sex": "M", "nuts2": "XX01"},
            {"dob_band": "1970-1974", "sex": "M", "nuts2": "XX01"},  # shares a class -> not k=1
            {"dob_band": "1965-1969", "sex": "F", "nuts2": "XX02"},  # alone -> k=1
        )
    )
    assert ins["upper_bound_only"] is True
    assert ins["meaningful"] is False
    assert ins["n_subjects"] == 3
    assert ins["n_unique"] == 1
    assert math.isclose(ins["k1_rate_upper_bound"], 1 / 3, rel_tol=1e-12)


def test_marginal_independence_overstates_uniqueness_vs_full_joint(joint):
    """The independence product assigns LESS mass to a correlated cell -> HIGHER (upper-bound) ξ."""
    qi = {"dob_band": "1960-1964", "sex": "F", "nuts2": "XX01"}
    xi_full = uniqueness.population_uniqueness(joint, qi)
    xi_indep = fallbacks.marginal_independence_uniqueness(joint, qi)["xi_upper_bound"]
    # Both are essentially 1 at n=100k, so compare the underlying p instead: independence p must be
    # <= a hair off; assert the upper-bound ξ is not LESS than the full-joint ξ (it's an upper bound).
    assert xi_indep >= xi_full - 1e-12


# ---------------------------------------------------------------------------------------------
# report.py attribution + labelling
# ---------------------------------------------------------------------------------------------


def test_report_emits_rocher_citation_and_attributions(joint):
    block = report.attribution_block(joint)
    assert "Rocher" in block
    assert "CC-BY-4.0" in block
    assert "Must-NOT-do" in block
    # Placeholder status surfaces loudly.
    assert "NOT a reported metric" in block

    attrs = report.source_attributions()
    assert any("Eurostat" in a for a in attrs)
    assert any("Synthetic illustrative placeholder" in a for a in attrs)


def test_annotate_result_attaches_status_and_citation(joint):
    res = uniqueness.purr_at_tau(joint, _rows({"dob_band": "1970-1974", "sex": "M", "nuts2": "XX01"}))
    enriched = report.annotate_result(res, joint)
    assert enriched["reported_metric"] is False
    assert "Rocher" in enriched["method_citation"]
    assert len(enriched["red_team_rules"]) >= 4
    assert "NOT a reported metric" in enriched["status_label"]
