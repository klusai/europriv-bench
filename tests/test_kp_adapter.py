"""Contract test for the KP-model adapter (KLU-17).

KP `kp-*` finetunes are trained directly on the harmonized KP taxonomy, so their predicted
labels are already KP entity types — no native→KP crosswalk applies. This guards that invariant:
a KP-labelled span fed through the adapter's mapping path (``kp_entities_to_bioes``, the same
seam the live pipeline uses) round-trips *unchanged* — the label survives, and the BIOES output
carries exactly that KP type. If someone ever routes KP output through a native crosswalk, an
unmapped/renamed label would surface here.
"""

from __future__ import annotations

from europriv_bench.adapters import BUILDERS, KpModelAdapter
from europriv_bench.crosswalk import kp_entities_to_bioes
from europriv_bench.spans import validate_bioes
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
