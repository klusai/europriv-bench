"""RES-17 (KLU-118 v2) — deterministic offline Iterative Proportional Fitting (IPF).

Fits a per-country **sparse joint distribution** over (a subset of) the frozen ``qi-v1`` QI schema
from published census **cross-tabulations** (lower-dimensional hypercubes), exactly the shape a real
census ships. The fitted joint is the *denominator* the population-uniqueness estimator
(``uniqueness.py``) reads.

IPF (a.k.a. raking / Deming–Stephan): start from a uniform joint and repeatedly rescale it so that
each of its marginals matches the corresponding published target marginal, cycling over the targets
until every marginal agrees to within a pinned tolerance. The fixed point is the maximum-entropy
joint consistent with all the supplied cross-tabs — i.e. it preserves the *correlations* the
cross-tabs encode and assumes independence only where the data is silent.

DETERMINISM (binding — design-doc "deterministic offline ``build_joint.py`` (IPF, pinned tolerance)"):
  * No RNG, no clock, no network. Pure function of (axes, marginals, tolerance, max_iter).
  * Category vocabularies and axis order are taken verbatim from the fixture; cell iteration is in a
    fixed lexicographic order so the same input always yields byte-identical output.
  * ``TOLERANCE`` and ``MAX_ITER`` are module constants (pinned), overridable only for tests.

SCOPE GUARD (RES-17): the only census input wired here is a COMMITTED SYNTHETIC PLACEHOLDER fixture
(``fixtures/synthetic_census_xx.yaml``), clearly labelled "NOT real census data". This module does
NOT fetch or download anything. Vendoring the real Eurostat 2021 Census Hub hypercubes is a DEFERRED
follow-up, gated on the census-calibrated generator (see the design doc).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources

import yaml

# Pinned IPF stopping rule. The tolerance is the max absolute deviation, over every target-marginal
# cell, between the fitted joint's marginal and the target (both normalised to probabilities). 1e-10
# is far tighter than any downstream use needs but makes the fixed point reproducible to ~machine
# precision across platforms; MAX_ITER is a safety cap (convergence on these small joints is <50 it).
TOLERANCE = 1e-10
MAX_ITER = 1000


@dataclass(frozen=True)
class Joint:
    """A fitted sparse joint over a tuple of QI axes.

    ``axes`` is the ordered field tuple (a subset of ``qi_schema.QI_FIELDS``); ``probs`` maps a
    full category tuple (in ``axes`` order) -> probability mass (sums to 1). ``n`` is the reference
    population head-count (the census total) — the population size the Rocher uniqueness estimator
    needs. ``placeholder`` is True iff this joint was fitted from the synthetic placeholder fixture
    (propagated into every downstream label so a placeholder can never masquerade as real).
    """

    axes: tuple[str, ...]
    probs: Mapping[tuple[str, ...], float]
    n: int
    placeholder: bool
    label: str
    iterations: int
    converged: bool

    def prob(self, key: tuple[str, ...]) -> float:
        """Probability mass for a full category tuple (0.0 if outside the support)."""
        return float(self.probs.get(tuple(key), 0.0))


def _normalise(counts: Mapping[str, float]) -> dict[str, float]:
    total = float(sum(counts.values()))
    if total <= 0:
        raise ValueError("marginal counts sum to a non-positive total")
    return {k: v / total for k, v in counts.items()}


def _marginal_of(
    joint: dict[tuple[str, ...], float],
    axes: Sequence[str],
    sub_axes: Sequence[str],
) -> dict[tuple[str, ...], float]:
    """Collapse a full joint down to the marginal over ``sub_axes`` (a subset of ``axes``)."""
    idx = [axes.index(a) for a in sub_axes]
    out: dict[tuple[str, ...], float] = {}
    for key, mass in joint.items():
        sub = tuple(key[i] for i in idx)
        out[sub] = out.get(sub, 0.0) + mass
    return out


def fit_ipf(
    axes: Sequence[str],
    categories: Mapping[str, Sequence[str]],
    marginals: Sequence[Mapping],
    *,
    tolerance: float = TOLERANCE,
    max_iter: int = MAX_ITER,
) -> tuple[dict[tuple[str, ...], float], int, bool]:
    """Run IPF; return ``(probs, iterations, converged)``.

    ``marginals`` is a list of ``{"axes": [...], "counts": {"cat|cat": n, ...}}`` targets (the
    published cross-tabs). The result ``probs`` is a dense-over-support dict (every category tuple
    in the Cartesian product of ``categories``) summing to 1.
    """
    axes = tuple(axes)
    # Pre-normalise each target marginal to a probability table keyed by sub-tuple.
    targets: list[tuple[tuple[str, ...], dict[tuple[str, ...], float]]] = []
    for m in marginals:
        sub_axes = tuple(m["axes"])
        probs = _normalise({k: float(v) for k, v in m["counts"].items()})
        keyed = {tuple(k.split("|")): p for k, p in probs.items()}
        targets.append((sub_axes, keyed))

    # Uniform seed over the full Cartesian support (deterministic lexicographic cell order).
    support = list(itertools.product(*[list(categories[a]) for a in axes]))
    if not support:
        raise ValueError("empty support — every axis needs at least one category")
    joint = {cell: 1.0 / len(support) for cell in support}

    converged = False
    iterations = 0
    for iterations in range(1, max_iter + 1):
        # One full IPF sweep: rescale the joint to each target marginal in turn.
        for sub_axes, target in targets:
            idx = [axes.index(a) for a in sub_axes]
            current = _marginal_of(joint, axes, sub_axes)
            for cell in joint:
                sub = tuple(cell[i] for i in idx)
                cur = current.get(sub, 0.0)
                tgt = target.get(sub, 0.0)
                if cur > 0.0:
                    joint[cell] *= tgt / cur
                # If cur == 0 (mass fled the cell) it stays 0; targets here never strand mass.
        # Convergence is measured AFTER the full sweep, across EVERY target marginal — earlier
        # rescalings are perturbed by later ones, so the only sound stopping rule re-checks all of
        # them at sweep end (a per-target check inside the loop would stop optimistically early).
        max_dev = 0.0
        for sub_axes, target in targets:
            updated = _marginal_of(joint, axes, sub_axes)
            for sub, tgt in target.items():
                max_dev = max(max_dev, abs(updated.get(sub, 0.0) - tgt))
        if max_dev <= tolerance:
            converged = True
            break

    # Renormalise to kill any accumulated floating drift (sum should already be ~1).
    total = sum(joint.values())
    joint = {cell: mass / total for cell, mass in joint.items()}
    return joint, iterations, converged


def build_joint_from_spec(
    spec: Mapping,
    *,
    tolerance: float = TOLERANCE,
    max_iter: int = MAX_ITER,
) -> Joint:
    """Build a :class:`Joint` from an already-parsed census-fixture mapping (see the YAML schema)."""
    meta = spec["meta"]
    axes = tuple(meta["axes"])
    categories = {a: list(spec["axes"][a]) for a in axes}
    probs, iterations, converged = fit_ipf(
        axes, categories, spec["marginals"], tolerance=tolerance, max_iter=max_iter
    )
    if not converged:
        raise RuntimeError(
            f"IPF did not converge within {max_iter} iterations (tolerance {tolerance:g}); "
            "refusing to emit a non-reproducible joint"
        )
    placeholder = bool(meta.get("placeholder", False)) or not bool(meta.get("is_real_census", False))
    label = str(meta.get("label", "")) or (
        "ILLUSTRATIVE PLACEHOLDER — NOT REAL CENSUS DATA" if placeholder else ""
    )
    return Joint(
        axes=axes,
        probs=probs,
        n=int(meta["population_total"]),
        placeholder=placeholder,
        label=label,
        iterations=iterations,
        converged=converged,
    )


def load_census_spec(filename: str) -> dict:
    """Parse a vendored census-fixture YAML from the ``refpop/fixtures`` package dir."""
    text = (
        resources.files("europriv_bench.refpop")
        .joinpath("fixtures")
        .joinpath(filename)
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)


def build_synthetic_placeholder_joint(
    *, tolerance: float = TOLERANCE, max_iter: int = MAX_ITER
) -> Joint:
    """Build the joint from the COMMITTED SYNTHETIC PLACEHOLDER census fixture.

    Convenience entry point for tests and the runnable example. The returned :class:`Joint` has
    ``placeholder=True`` and a loud ``label`` — every downstream report propagates both so a
    placeholder can never be mistaken for a calibrated reference population.
    """
    spec = load_census_spec("synthetic_census_xx.yaml")
    joint = build_joint_from_spec(spec, tolerance=tolerance, max_iter=max_iter)
    if not joint.placeholder:
        # Defensive: the synthetic fixture MUST always be flagged placeholder.
        raise RuntimeError("synthetic placeholder fixture is not flagged placeholder — refusing")
    return joint


def joint_entropy_bits(joint: Joint) -> float:
    """Shannon entropy (bits) of the fitted joint — a quick sanity scalar for tests/diagnostics."""
    return -sum(p * math.log2(p) for p in joint.probs.values() if p > 0.0)
