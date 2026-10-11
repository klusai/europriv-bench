"""Explicit local deletion operators for gateway v2; never expand BIOES coverage.

These are benchmark operators, not claims about deployed KP service policy. Full
input is screened with tokenizer overflow windows, and original character offsets
are retained. Every returned interval is actually deleted; receipts bind output.
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence

from .adapters import BaseAdapter, KpModelAdapter, PresidioAdapter


def delete_intervals(text, spans):
    removed = bytearray(len(text))
    for start, end in spans:
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
            raise ValueError("invalid deletion interval")
        removed[start:end] = b"\x01" * (end - start)
    return "".join(ch for i, ch in enumerate(text) if not removed[i])


class GatewayDeletionAdapter(BaseAdapter):
    def __init__(self, detector):
        if not isinstance(detector, (KpModelAdapter, PresidioAdapter)):
            raise TypeError("gateway deletion requires KP or stock Presidio")
        self.detector = detector
        self.name, self.model_id = detector.name, detector.model_id
        self.receipts = []

    def redaction_spans(self, texts: Sequence[str]):
        texts = list(texts)
        if isinstance(self.detector, KpModelAdapter):
            pipe = self.detector._pipeline()
            if not pipe.tokenizer.is_fast or pipe.model.config.max_position_embeddings < 512:
                raise ValueError("full-input operator requires bounded fast tokenizer overflow windows")
            pipe.tokenizer.model_max_length = 512
            results = pipe(texts, batch_size=self.detector._batch_size, stride=64)
            coverage = [[(int(e["start"]), int(e["end"])) for e in ents] for ents in results]
        else:
            engine = self.detector._analyzer()
            coverage = [[(int(r.start), int(r.end)) for r in engine.analyze(
                text=text, language=self.detector.language, entities=self.detector._entities,
                score_threshold=self.detector.score_threshold,
            )] for text in texts]
        self.receipts = []
        for text, spans in zip(texts, coverage, strict=True):
            output = delete_intervals(text, spans)
            self.receipts.append({
                "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
                "spans": spans, "operator": "delete-exact-union-v1",
            })
        return coverage

    def provenance(self):
        return {"operator_provenance": {
            "operator": "delete-exact-union-v1", "coverage": "raw-detector-character-offsets",
            "label_fairness_filter": False, "replacement_copies_source": False,
            "aggregation": "simple" if isinstance(self.detector, KpModelAdapter) else None,
            "window_tokens": 512 if isinstance(self.detector, KpModelAdapter) else None,
            "overflow_stride": 64 if isinstance(self.detector, KpModelAdapter) else None,
            "entities": self.detector._entities if isinstance(self.detector, PresidioAdapter) else "all-model-labels",
            "threshold": self.detector.score_threshold if isinstance(self.detector, PresidioAdapter) else None,
            "language": "en" if isinstance(self.detector, PresidioAdapter) else "multilingual",
            "deployment_equivalence": "not verified",
        }}
