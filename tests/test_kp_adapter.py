"""Contract test for the KP-model adapter (KLU-17).

KP `kp-*` finetunes are trained directly on the harmonized KP taxonomy, so their predicted
labels are already KP entity types — no native→KP crosswalk applies. This guards that invariant:
a KP-labelled span fed through the adapter's mapping path (``kp_entities_to_bioes``, the same
seam the live pipeline uses) round-trips *unchanged* — the label survives, and the BIOES output
carries exactly that KP type. If someone ever routes KP output through a native crosswalk, an
unmapped/renamed label would surface here.
"""

from __future__ import annotations

from europriv_bench.adapters import BUILDERS, KpModelAdapter, PredictedSpan
from europriv_bench.crosswalk import kp_entities_to_bioes
from europriv_bench.spans import Span, char_spans_to_bioes, validate_bioes
from europriv_bench.taxonomy import bioes_labels


def test_kp_adapter_registered():
    assert BUILDERS["kp-model"] is KpModelAdapter
    a = KpModelAdapter()
    assert a.name == "kp-model"
    assert a.model_id == "klusai/kp-deid-mdeberta-280m"


def test_kp_labelled_span_roundtrips_unchanged():
    # The exact shape KpModelAdapter.predict_tags builds from a pipeline result, with a KP label.
    text = "Andrei Popescu CNP 5080417298732"
    kp_ents = [
        {"start": 0, "end": 14, "label": "PERSON"},
        {"start": 19, "end": 32, "label": "NATIONAL_ID"},
    ]
    tags = kp_entities_to_bioes(text, kp_ents)

    # Multi-token PERSON -> B-/E-PERSON; single-token NATIONAL_ID -> S-NATIONAL_ID. The KP labels
    # appear verbatim (no crosswalk renaming), and every emitted tag is in the KP BIOES space.
    assert tags == ["B-PERSON", "E-PERSON", "O", "S-NATIONAL_ID"]
    valid = set(bioes_labels())
    assert all(t in valid for t in tags)
    validate_bioes(tags)


def test_kp_label_is_not_remapped():
    # A KP type that is NOT any native scheme's source label still passes straight through —
    # proving the adapter does not (mistakenly) run a native->KP crosswalk on KP output.
    text = "x"
    tags = kp_entities_to_bioes(text, [{"start": 0, "end": 1, "label": "COMPANY_ID"}])
    assert tags == ["S-COMPANY_ID"]


class _FakePipe:
    """Stand-in for the transformers token-classification pipeline.

    Returns aggregation_strategy="simple"-shaped entities (``entity_group`` = KP type already,
    char ``start``/``end``, ``score``) so we can exercise ``predict_spans``'s real mapping +
    span-reconstruction + scoring path without downloading the HF model.
    """

    def __init__(self, ents: list[dict]) -> None:
        self._ents = ents

    def __call__(self, text: str) -> list[dict]:
        return self._ents


def _kp_adapter_with_pipe(ents: list[dict]) -> KpModelAdapter:
    a = KpModelAdapter()
    a._pipe = _FakePipe(ents)  # pre-seed the cache so _pipeline() returns the fake
    return a


def test_predict_spans_offsets_index_back_to_surface_text():
    # Two subword pieces for the same multi-token PERSON, plus a single-token NATIONAL_ID. The
    # whitespace-token grid groups the two PERSON pieces into one span spanning both tokens.
    text = "Ion Popescu CNP 5080417298732"
    ents = [
        {"entity_group": "PERSON", "start": 0, "end": 3, "score": 0.9},
        {"entity_group": "PERSON", "start": 4, "end": 11, "score": 0.7},
        {"entity_group": "NATIONAL_ID", "start": 16, "end": 29, "score": 0.95},
    ]
    spans = _kp_adapter_with_pipe(ents).predict_spans(text)

    assert all(isinstance(s, PredictedSpan) for s in spans)
    # Offset-correctness: char offsets slice back to the surface text.
    for s in spans:
        assert text[s.start : s.end] == s.text
    labels = [(s.label, s.start, s.end, s.text) for s in spans]
    assert labels == [
        ("PERSON", 0, 11, "Ion Popescu"),
        ("NATIONAL_ID", 16, 29, "5080417298732"),
    ]
    # Score is the mean over the pieces backing each span (two PERSON pieces -> mean of 0.9, 0.7).
    by_label = {s.label: s for s in spans}
    assert by_label["PERSON"].score == (0.9 + 0.7) / 2
    assert by_label["NATIONAL_ID"].score == 0.95


def test_predict_spans_is_consistent_with_predict_tags():
    # The BIOES sequence re-derived from predict_spans must equal what predict_tags produces for the
    # same input + same pipeline output — the spans ARE the leaderboard prediction, just richer.
    text = "Ion Popescu lives in Bucharest"
    ents = [
        {"entity_group": "PERSON", "start": 0, "end": 3, "score": 0.9},
        {"entity_group": "PERSON", "start": 4, "end": 11, "score": 0.7},
        {"entity_group": "ADDRESS", "start": 21, "end": 30, "score": 0.8},
    ]
    spans = _kp_adapter_with_pipe(ents).predict_spans(text)

    # predict_tags's mapping path on the SAME raw pipeline entities (entity_group -> label).
    kp_ents = [
        {"start": e["start"], "end": e["end"], "label": e["entity_group"]} for e in ents
    ]
    expected_tags = kp_entities_to_bioes(text, kp_ents)

    rederived = char_spans_to_bioes(text, [Span(s.start, s.end, s.label) for s in spans])
    assert rederived == expected_tags
    assert expected_tags == ["B-PERSON", "E-PERSON", "O", "O", "S-ADDRESS"]
