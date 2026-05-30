"""Model adapters — the seam that lets EuroPriv-Bench score *any* system uniformly.

Each adapter wraps a model/tool (openai/privacy-filter, OpenMed, GLiNER, Presidio, a KlusAI
`kp-*` model, ...) and maps its native output onto the harmonized KP label space so results
are comparable. Heavy backends are imported lazily so the harness core stays light.

The four benchmark task families each need a different call shape, so ``BaseAdapter`` declares
one method per task — all default to NotImplementedError. Only detection is wired in v0.1; the
others raise until their phase, which keeps the seam explicit (Phase 4 is an *extension*, not a
rework of the Protocol/runner).

To add a baseline: subclass ``BaseAdapter``, set ``name``/``model_id``, implement the task
method(s), register it in ``BUILDERS``.
"""

from __future__ import annotations

from collections.abc import Sequence


class BaseAdapter:
    """Base for all adapters. ``name`` = family/tool; ``model_id`` = the specific checkpoint."""

    name: str = "base"
    model_id: str = "base"

    def predict_tags(self, texts: Sequence[str]) -> list[list[str]]:
        """DETECTION: return a BIOES tag sequence (KP label space) per input text."""
        raise NotImplementedError(f"{self.name}: detection not implemented")

    def anonymize(self, texts: Sequence[str]) -> list[str]:
        """ANONYMIZATION: return redacted/pseudonymized text per input. Phase 4."""
        raise NotImplementedError(f"{self.name}: anonymization lands in Phase 4")

    def classify(self, texts: Sequence[str]) -> list[str]:
        """CLASSIFICATION: return a document-level privacy/sensitivity label per input. Phase 4."""
        raise NotImplementedError(f"{self.name}: classification lands in Phase 4")

    def leakage_probe(self, texts: Sequence[str]) -> list[float]:
        """LEAKAGE: return a per-record membership/re-identification score. Phase 4."""
        raise NotImplementedError(f"{self.name}: leakage probe lands in Phase 4")


class DummyAdapter(BaseAdapter):
    """Predicts all-O. Lets the harness run end-to-end before any model is wired up."""

    name = "dummy"
    model_id = "dummy"

    def predict_tags(self, texts: Sequence[str]) -> list[list[str]]:
        return [["O"] * len(t.split()) for t in texts]


class PrivacyFilterAdapter(BaseAdapter):
    """openai/privacy-filter (and OpenMed/KlusAI finetunes). Requires the `hf` extra.

    Maps the model's native entity types onto KP labels via the taxonomy crosswalk.
    """

    name = "privacy-filter"

    def __init__(self, model_id: str = "openai/privacy-filter", scheme: str = "openai") -> None:
        self.model_id = model_id
        self.scheme = scheme

    def predict_tags(self, texts: Sequence[str]) -> list[list[str]]:  # pragma: no cover - needs GPU/model
        raise NotImplementedError(
            "PrivacyFilterAdapter: install the `hf` extra and wire the token-classification "
            "pipeline in Phase 1. Use the crosswalk in taxonomy.py to map native labels → KP."
        )


# Builder registry: adapter key (CLI --adapter) -> zero-arg factory.
BUILDERS: dict[str, type[BaseAdapter]] = {
    "dummy": DummyAdapter,
    "privacy-filter": PrivacyFilterAdapter,
}


def build(name: str) -> BaseAdapter:
    if name not in BUILDERS:
        raise KeyError(f"unknown adapter {name!r}; known: {sorted(BUILDERS)}")
    return BUILDERS[name]()
