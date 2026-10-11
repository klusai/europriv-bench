"""Versioned utility gate; passing it alone never establishes a gateway win."""

from collections.abc import Sequence
from math import isfinite


def utility_gate(ci95: Sequence[float] | None, *, contract_version: int) -> dict:
    """Evaluate candidate-minus-comparator rate CIs, separately per config/seed.

    Versions 1 and 2 preserve the historical zero margin. Version 3 is prospective
    only: callers must pin it before evaluation, never relabel historical results.
    Missing support fails the gate without asserting measured inferiority.
    """
    if type(contract_version) is not int or contract_version not in (1, 2, 3):
        raise ValueError(f"Unsupported gateway contract version: {contract_version!r}")
    margin = 0.01 if contract_version == 3 else 0.0
    if ci95 is not None and (len(ci95) != 2 or not all(isfinite(v) for v in ci95) or not -1 <= ci95[0] <= ci95[1] <= 1):
        raise ValueError("Utility delta requires a finite ordered 95% rate CI within [-1, 1]")
    return {
        "contract_version": contract_version,
        "margin": margin,
        "ci95": list(ci95) if ci95 is not None else None,
        "pass": ci95 is not None and ci95[1] <= margin,
        "regression": ci95 is not None and ci95[0] > margin,
    }
