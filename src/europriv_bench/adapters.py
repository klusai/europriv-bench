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

from .crosswalk import entities_to_kp_bioes, kp_entities_to_bioes


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
        import os

        self.model_id = model_id
        self.scheme = scheme
        self._pipe = None
        # Batching is the dominant speedup (~4x at 32 on CPU) — far more than device choice.
        self._batch_size = int(os.environ.get("EUROPRIV_BATCH_SIZE", "32"))

    def _pipeline(self):  # pragma: no cover - requires the `hf` extra + model download
        if self._pipe is None:
            import os

            import torch
            from transformers import pipeline

            # Device: CUDA when present (DO GPU droplets); else CPU. MPS is *intentionally not*
            # auto-selected — measured ~3x SLOWER than CPU for this MoE (routing ops fall back off
            # Metal and thrash transfers). Force it with EUROPRIV_DEVICE=mps if ever desired.
            device = os.environ.get("EUROPRIV_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
            if device == "mps":
                os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
            self._pipe = pipeline(
                "token-classification",
                model=self.model_id,
                aggregation_strategy="simple",
                device=device,
            )
        return self._pipe

    def predict_tags(self, texts: Sequence[str]) -> list[list[str]]:
        pipe = self._pipeline()  # pragma: no cover - needs model
        texts = list(texts)  # pragma: no cover
        results = pipe(texts, batch_size=self._batch_size)  # pragma: no cover - batched inference
        out = []  # pragma: no cover
        for text, ents in zip(texts, results):  # pragma: no cover
            mapped = [
                {"label": e["entity_group"], "start": int(e["start"]), "end": int(e["end"])}
                for e in ents
            ]
            out.append(entities_to_kp_bioes(text, mapped, self.scheme))
        return out


class OpenMedAdapter(PrivacyFilterAdapter):
    """OpenMed/privacy-filter-multilingual — a 54-category finetune of privacy-filter (scheme=openmed)."""

    name = "openmed"

    def __init__(self) -> None:
        super().__init__(model_id="OpenMed/privacy-filter-multilingual", scheme="openmed")


class TabularisaiAdapter(PrivacyFilterAdapter):
    """tabularisai/eu-pii-safeguard — XLM-R token classifier, 42 types, 26 EU langs (scheme=tabularisai).

    The pipeline adapter is arch-agnostic; this just fixes the model id + label scheme.
    """

    name = "tabularisai"

    def __init__(self) -> None:
        super().__init__(model_id="tabularisai/eu-pii-safeguard", scheme="tabularisai")


class GLiNERAdapter(BaseAdapter):
    """GLiNER zero-shot NER (urchade/gliner_multi_pii-v1). Requires the `gliner` extra.

    Architecturally distinct from the token-classifiers: we *prompt* it with natural-language
    labels and it returns spans for them. We prompt with phrasings of the KP types and map the
    returned label straight back to KP — so no native→KP crosswalk scheme is needed.
    """

    name = "gliner"
    model_id = "urchade/gliner_multi_pii-v1"

    # prompt label -> KP type. Phrasing matters for zero-shot recall.
    LABEL_TO_KP = {
        "person": "PERSON", "full name": "PERSON",
        "address": "ADDRESS", "city": "ADDRESS", "postal code": "ADDRESS",
        "email": "EMAIL", "phone number": "PHONE", "url": "URL",
        "date": "DATE", "date of birth": "DATE",
        "account number": "ACCOUNT_ID", "credit card number": "ACCOUNT_ID", "iban": "ACCOUNT_ID",
        "ip address": "ACCOUNT_ID", "username": "ACCOUNT_ID",
        "password": "SECRET",
        "national identification number": "NATIONAL_ID", "passport number": "NATIONAL_ID",
        "driver license number": "NATIONAL_ID",
        "company": "ORG_PARTY",
    }

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self._model = None
        self._labels = sorted(self.LABEL_TO_KP)

    def _load(self):  # pragma: no cover - requires the `gliner` extra + model download
        if self._model is None:
            from gliner import GLiNER
            self._model = GLiNER.from_pretrained(self.model_id)
        return self._model

    def predict_tags(self, texts: Sequence[str]) -> list[list[str]]:
        model = self._load()  # pragma: no cover - needs model
        out = []  # pragma: no cover
        for text in texts:  # pragma: no cover
            kp_ents = [
                {"start": e["start"], "end": e["end"], "label": self.LABEL_TO_KP[e["label"]]}
                for e in model.predict_entities(text, self._labels, threshold=self.threshold)
                if e["label"] in self.LABEL_TO_KP
            ]
            out.append(kp_entities_to_bioes(text, kp_ents))
        return out


class KpModelAdapter(BaseAdapter):
    """KlusAI `kp-*` token-classification finetunes (e.g. ``klusai/kp-deid-mdeberta-280m``).

    Unlike the baselines wrapped by ``PrivacyFilterAdapter`` (which emit a *native* scheme that a
    crosswalk must translate), KP models are trained directly on the harmonized KP taxonomy: their
    ``id2label`` already carries KP entity types (``PERSON``, ``NATIONAL_ID``, ...). So we follow the
    GLiNER pattern and map the model's spans straight back via ``kp_entities_to_bioes`` — no
    native→KP ``scheme`` and no ``crosswalk.py`` touch. Requires the `hf` extra.

    ``aggregation_strategy="simple"`` re-groups subword pieces into spans whose ``entity_group`` is
    the KP type (BIOES head prefixes stripped by the pipeline), giving char offsets to align.
    """

    name = "kp-model"

    def __init__(self, model_id: str = "klusai/kp-deid-mdeberta-280m") -> None:
        import os

        self.model_id = model_id
        self._pipe = None
        self._batch_size = int(os.environ.get("EUROPRIV_BATCH_SIZE", "32"))

    def _pipeline(self):  # pragma: no cover - requires the `hf` extra + model download
        if self._pipe is None:
            import os

            import torch
            from transformers import pipeline

            device = os.environ.get("EUROPRIV_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
            if device == "mps":
                os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
            self._pipe = pipeline(
                "token-classification",
                model=self.model_id,
                aggregation_strategy="simple",
                device=device,
            )
        return self._pipe

    def predict_tags(self, texts: Sequence[str]) -> list[list[str]]:
        pipe = self._pipeline()  # pragma: no cover - needs model
        texts = list(texts)  # pragma: no cover
        results = pipe(texts, batch_size=self._batch_size)  # pragma: no cover - batched inference
        out = []  # pragma: no cover
        for text, ents in zip(texts, results):  # pragma: no cover
            kp_ents = [
                {"start": int(e["start"]), "end": int(e["end"]), "label": e["entity_group"]}
                for e in ents
            ]
            out.append(kp_entities_to_bioes(text, kp_ents))
        return out


# Builder registry: adapter key (CLI --adapter) -> zero-arg factory.
BUILDERS: dict[str, type[BaseAdapter]] = {
    "dummy": DummyAdapter,
    "privacy-filter": PrivacyFilterAdapter,
    "openmed": OpenMedAdapter,
    "tabularisai": TabularisaiAdapter,
    "gliner": GLiNERAdapter,
    "kp-model": KpModelAdapter,
}


def build(name: str) -> BaseAdapter:
    if name not in BUILDERS:
        raise KeyError(f"unknown adapter {name!r}; known: {sorted(BUILDERS)}")
    return BUILDERS[name]()
