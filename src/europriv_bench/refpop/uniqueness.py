"""RES-17 (KLU-118 v2) — population-uniqueness estimator + PURR@τ.

Implements the **Rocher–Hendrickx–de Montjoye (2019)** individual-uniqueness estimator and the
**Population-Uniqueness Re-id Rate (PURR@τ)** aggregate on top of a fitted reference-population
:class:`~europriv_bench.refpop.build_joint.Joint`.

Method (cite: Rocher, Hendrickx & de Montjoye, *Nature Communications* 10:3069, 2019; the method /
reference code is CC-BY-4.0):

  * For a residual QI tuple ``x``, ``p(x)`` is its probability under the reference joint.
  * In a population of ``n`` individuals drawn i.i.d. from the joint, the probability that an
    individual with signature ``x`` is **unique** (no one else shares ``x``) is
        ``ξ(x) = (1 − p(x))^(n − 1)``.
    Rocher 2019 write ``ξ = 1 − (1 − p)^(n-1)`` for the probability of *correctness* of a uniqueness
    claim under their Gaussian-copula model; we expose both — ``population_uniqueness(x)`` returns
    the probability the record is unique, and ``correctness`` is the κ companion below.
  * PURR@τ — the share of subjects whose population-uniqueness ``ξ(x) ≥ τ`` (default **τ=0.95**, the
    Rocher operating point with a calibrated ~5–6.7% FDR). Aggregated per subject with a Wilson CI,
    reusing the harness's ``metrics.wilson_interval``.
  * **ΔPURR = baseline − model** — the dissociation signal. Robust to the reference-population choice;
    this (and model *rankings*) is what you LEAD with. Absolute PURR is reference-conditional.
  * mean **κ** (re-id correctness) — a secondary scalar: the mean, over uniquely-flagged subjects, of
    the probability that a uniqueness claim is correct under the model.

The "Gaussian-copula" part of Rocher 2019 is the *fitting* of a continuous individual-uniqueness
surface to marginals + pairwise correlations when the full joint is unavailable. Here we already hold
a full IPF-fitted joint (which encodes the modelled correlations), so ``p(x)`` is read directly off
the joint; the copula machinery is the principled way to *obtain* such a ``p(x)`` and is cited as the
method we follow. ``fallbacks.py`` provides the strictly weaker marginal-independence approximation,
labelled an upper bound only.

HARD GUARDS (design-doc red-team — enforced here):
  * **Post-detection residual only** — the estimator takes an already-built residual ``qi_tuple``
    (what the model left un-redacted). It never sees raw text. (Building the residual is
    ``qi_enrich.residual_qi_rows``; this module only scores it.)
  * **Reference-conditional / placeholder labelling** — every result carries ``reference_label`` and
    ``placeholder`` straight from the :class:`Joint`, and ``reported_metric=False`` whenever the joint
    is a placeholder. A placeholder PURR is **internal sensitivity-analysis machinery, NOT a reported
    metric** (pending the census-calibrated generator).
  * **Lead with ΔPURR** — :func:`delta_purr` is the headline-shaped output; :func:`purr_at_tau`
    returns absolute PURR explicitly tagged ``reference_conditional=True``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..metrics import wilson_interval
from .build_joint import Joint

# Rocher 2019 calibrated operating point (their ~5–6.7% FDR regime).
DEFAULT_TAU = 0.95

# A residual QI tuple is the binned-value mapping built by qi_schema.build_qi_tuple.
QITuple = Mapping[str, object]

#: Loud label reused everywhere a placeholder result surfaces.
NOT_REPORTED_LABEL = (
    "internal sensitivity-analysis machinery, NOT a reported metric "
    "(pending census-calibrated generator)"
)


def _project(tuple_key: QITuple, axes: Sequence[str]) -> tuple[str, ...] | None:
    """Project a residual QI tuple onto the joint's axes; ``None`` if any axis is absent.

    A QI field absent from the residual (omitted, never fabricated — see ``qi_schema``) means we
    cannot place the subject in the joint's support, so the subject is *not scorable* against this
    reference (returned as un-scored rather than silently defaulted to a category).
    """
    out: list[str] = []
    for a in axes:
        v = tuple_key.get(a)
        if v is None:
            return None
        out.append(str(v))
    return tuple(out)


def population_uniqueness(joint: Joint, qi_tuple: QITuple) -> float | None:
    """Rocher 2019 individual uniqueness ``ξ(x) = (1 − p(x))^(n − 1)`` for one residual tuple.

    Returns the probability the record is **unique** in the reference population, or ``None`` if the
    tuple cannot be projected onto the joint's axes (un-scorable against this reference).
    """
    key = _project(qi_tuple, joint.axes)
    if key is None:
        return None
    p = joint.prob(key)
    if p <= 0.0:
        # Signature unseen in the reference support — treat as maximally distinctive (ξ→1) but
        # only within this reference's support; callers see it via the un-scored vs scored split.
        return 1.0
    n = max(joint.n, 2)
    return (1.0 - p) ** (n - 1)


def correctness(joint: Joint, qi_tuple: QITuple) -> float | None:
    """Rocher 2019 **correctness** of a uniqueness claim: ``1 − (1 − p(x))^(n − 1)``.

    This is the κ companion — the probability that, *given* we flagged the record as unique, the
    claim is right under the model. ``None`` when un-scorable.
    """
    xi = population_uniqueness(joint, qi_tuple)
    if xi is None:
        return None
    return 1.0 - xi


def score_rows(
    joint: Joint, rows: Sequence[Mapping[str, object]]
) -> list[dict[str, object]]:
    """Score per-subject residual rows (each carrying a ``qi_tuple``) against the reference joint.

    Returns one dict per row: ``{"qi_tuple", "xi", "correctness", "scorable"}``. Un-scorable rows
    (a QI field outside the joint's axes) carry ``scorable=False`` and ``xi=None``.
    """
    out: list[dict[str, object]] = []
    for row in rows:
        qi = row.get("qi_tuple") or row.get("quasi_identifiers") or {}
        xi = population_uniqueness(joint, qi)
        out.append(
            {
                "qi_tuple": dict(qi),
                "xi": xi,
                "correctness": (None if xi is None else 1.0 - xi),
                "scorable": xi is not None,
            }
        )
    return out


def purr_at_tau(
    joint: Joint,
    rows: Sequence[Mapping[str, object]],
    *,
    tau: float = DEFAULT_TAU,
) -> dict[str, object]:
    """Absolute **PURR@τ** for one set of residual rows against one reference joint.

    PURR@τ = (# subjects with ξ(x) ≥ τ) / (# scorable subjects), with a 95% Wilson CI. Tagged
    ``reference_conditional=True`` and — when the joint is a placeholder — ``reported_metric=False``
    with the ``NOT_REPORTED_LABEL``, because a placeholder absolute PURR is internal-only.

    Per the red-team rule, callers should LEAD with :func:`delta_purr`, not this absolute scalar.
    """
    scored = score_rows(joint, rows)
    scorable = [s for s in scored if s["scorable"]]
    n_scorable = len(scorable)
    unique = sum(1 for s in scorable if float(s["xi"]) >= tau)  # type: ignore[arg-type]
    purr = (unique / n_scorable) if n_scorable else 0.0
    low, high = wilson_interval(unique, n_scorable)
    # mean κ over the FLAGGED-unique subjects (re-id correctness of the claims we'd make).
    flagged = [s for s in scorable if float(s["xi"]) >= tau]  # type: ignore[arg-type]
    mean_kappa = (
        sum(float(s["correctness"]) for s in flagged) / len(flagged) if flagged else 0.0  # type: ignore[arg-type]
    )
    return {
        "tau": tau,
        "purr": purr,
        "purr_ci_low": low,
        "purr_ci_high": high,
        "n_subjects": len(scored),
        "n_scorable": n_scorable,
        "n_unscorable": len(scored) - n_scorable,
        "n_unique": unique,
        "mean_kappa": mean_kappa,
        "reference_label": joint.label,
        "reference_axes": list(joint.axes),
        "reference_population": joint.n,
        "placeholder": joint.placeholder,
        # A placeholder reference => this is NOT a reported metric (internal sensitivity only).
        "reported_metric": not joint.placeholder,
        "reference_conditional": True,
        "note": NOT_REPORTED_LABEL if joint.placeholder else "",
        "method": "Rocher, Hendrickx & de Montjoye 2019 (Nat. Commun. 10:3069); CC-BY-4.0",
    }


def delta_purr(
    joint: Joint,
    baseline_rows: Sequence[Mapping[str, object]],
    model_rows: Sequence[Mapping[str, object]],
    *,
    tau: float = DEFAULT_TAU,
) -> dict[str, object]:
    """**ΔPURR = PURR(baseline) − PURR(model)** — the headline-shaped dissociation signal.

    ``baseline_rows`` is the residual under a no-/weak-redaction reference (typically the raw-gold
    QI tuples, i.e. what an un-redacting baseline leaves); ``model_rows`` is the residual the model
    under test leaves. A positive ΔPURR means the model lowered population-uniqueness (good).

    ΔPURR (and model *rankings*) is robust to the reference-population choice — that is why it leads,
    while the two absolute PURRs are explicitly ``reference_conditional``. Carries the placeholder /
    not-reported flags through unchanged.
    """
    base = purr_at_tau(joint, baseline_rows, tau=tau)
    model = purr_at_tau(joint, model_rows, tau=tau)
    return {
        "tau": tau,
        "delta_purr": float(base["purr"]) - float(model["purr"]),
        "baseline_purr": base["purr"],
        "model_purr": model["purr"],
        "baseline": base,
        "model": model,
        "is_headline_shape": True,  # ΔPURR is the robust, lead-with output
        "placeholder": joint.placeholder,
        "reported_metric": not joint.placeholder,
        "note": NOT_REPORTED_LABEL if joint.placeholder else "",
        "method": "Rocher, Hendrickx & de Montjoye 2019 (Nat. Commun. 10:3069); CC-BY-4.0",
    }
