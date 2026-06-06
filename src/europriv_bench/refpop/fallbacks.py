"""RES-17 (KLU-118 v2) — WEAKER fallback uniqueness estimators (UPPER BOUNDS ONLY).

Two cheaper estimators for when a full IPF-fitted joint is unavailable. **Both are deliberately
weaker than the Rocher 2019 copula estimator in ``uniqueness.py`` and MUST be presented as upper
bounds only** — this is a hard design-doc red-team rule:

    "No uniqueness from independent marginals presented as meaningful (correlations matter; label
     it an upper bound only)."

Every result here carries ``estimator="..."``, ``upper_bound_only=True``, ``meaningful=False`` and a
loud ``warning`` string, so it is structurally impossible to surface one of these numbers as a
headline or to confuse it with the copula PURR.

1. **Marginal-independence** (``marginal_independence_uniqueness``): assumes the QI fields are
   independent, so ``p(x) = ∏ p_field(value)``. Because real QIs are positively correlated (older
   ages cluster in some regions, professions skew by sex, …), the independence product *over*-states
   how spread-out the population is and therefore *over*-states uniqueness — an UPPER BOUND on the
   true population-uniqueness, never the reported figure.

2. **In-sample** (``in_sample_uniqueness``): the within-corpus k=1 rate — the share of subjects whose
   residual QI tuple is unique **inside the evaluation corpus itself** (no population model at all).
   This is "sample distinctiveness, not population re-identification" (design-doc v1 language) and is
   an upper bound: a sample-unique record is usually NOT population-unique. It is the same notion the
   v1 ``metrics.k_anonymity_violation`` histogram reports, exposed here as a labelled scalar.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .build_joint import Joint

QITuple = Mapping[str, object]

_UPPER_BOUND_WARNING = (
    "UPPER BOUND ONLY — weaker than the Rocher-copula estimator; assumes away QI correlations / "
    "uses no population model. NOT meaningful as a re-identification figure; never a headline."
)


def _marginals(joint: Joint) -> dict[str, dict[str, float]]:
    """Per-axis marginal probabilities of the fitted joint (the independence factors)."""
    out: dict[str, dict[str, float]] = {a: {} for a in joint.axes}
    for key, mass in joint.probs.items():
        for axis, cat in zip(joint.axes, key, strict=True):
            out[axis][cat] = out[axis].get(cat, 0.0) + mass
    return out


def marginal_independence_uniqueness(
    joint: Joint, qi_tuple: QITuple
) -> dict[str, object]:
    """Independence-product uniqueness for one residual tuple — **upper bound only**.

    ``p_indep(x) = ∏ p_axis(value)``; ``ξ_upper = (1 − p_indep)^(n−1)``. Returns ``xi=None`` when the
    tuple cannot be projected onto the joint's axes.
    """
    marg = _marginals(joint)
    p = 1.0
    for axis in joint.axes:
        v = qi_tuple.get(axis)
        if v is None:
            return _wrap(None, joint)
        pv = marg[axis].get(str(v), 0.0)
        if pv <= 0.0:
            p = 0.0
            break
        p *= pv
    n = max(joint.n, 2)
    xi = 1.0 if p <= 0.0 else (1.0 - p) ** (n - 1)
    return _wrap(xi, joint)


def _wrap(xi: float | None, joint: Joint) -> dict[str, object]:
    return {
        "estimator": "marginal_independence",
        "xi_upper_bound": xi,
        "upper_bound_only": True,
        "meaningful": False,
        "reference_label": joint.label,
        "placeholder": joint.placeholder,
        "reported_metric": False,
        "warning": _UPPER_BOUND_WARNING,
    }


def in_sample_uniqueness(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Within-corpus k=1 rate — **upper bound only**, "sample distinctiveness, not re-identification".

    Groups subjects into equivalence classes by their full residual QI tuple and reports the share in
    a class of size 1. No population model is used; this OVER-states population re-identifiability.
    """
    classes: dict[tuple, int] = {}
    n = 0
    for row in rows:
        qi = row.get("qi_tuple") or row.get("quasi_identifiers") or {}
        if not qi:
            continue
        key = tuple(sorted((k, str(v)) for k, v in qi.items()))
        classes[key] = classes.get(key, 0) + 1
        n += 1
    n_unique = sum(1 for c in classes.values() if c == 1)
    rate = (n_unique / n) if n else 0.0
    return {
        "estimator": "in_sample_k1",
        "k1_rate_upper_bound": rate,
        "n_subjects": n,
        "n_unique": n_unique,
        "n_equivalence_classes": len(classes),
        "upper_bound_only": True,
        "meaningful": False,
        "reported_metric": False,
        "warning": (
            "UPPER BOUND ONLY — within-corpus sample distinctiveness, NOT population "
            "re-identification (design-doc v1 language). Never a headline number."
        ),
    }
