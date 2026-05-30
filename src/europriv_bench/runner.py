"""Run an adapter against an eval spec and compute its metrics.

Flow: spec → load held-out gold (HF) → adapter task method → metrics.REGISTRY → result dict.
Gold data is pulled from HF at eval time and never committed (see .gitignore).

Every result row carries provenance (harness version, taxonomy version, dataset config/split,
model_id, optional timestamp) so a published/cited number traces back to an exact harness +
taxonomy + dataset revision.
"""

from __future__ import annotations

from . import __version__
from .adapters import BaseAdapter
from .logger import get_logger
from .metrics import REGISTRY
from .spec import EvalSpec, Task
from .taxonomy import TAXONOMY_VERSION

logger = get_logger(__name__)


def _load_gold(spec: EvalSpec) -> tuple[list[str], list[list[str]]]:
    """Load (texts, gold BIOES tag-sequences) for a detection spec from HF.

    Stubbed until the benchmark dataset is published (Phase 1). Tests inject gold directly.
    """
    raise NotImplementedError(
        f"_load_gold: publish {spec.dataset.hf_id} (Phase 1), then load via datasets.load_dataset"
    )


def run_spec(
    spec: EvalSpec,
    adapter: BaseAdapter,
    gold: tuple[list[str], list[list[str]]] | None = None,
    timestamp: str | None = None,
) -> dict:
    """Score one adapter on one spec. ``gold`` may be injected (tests); else loaded from HF.

    Only DETECTION is wired in v0.1; other tasks raise via the adapter's task method.
    """
    if spec.task is not Task.DETECTION:
        # The seam exists (BaseAdapter.anonymize/classify/leakage_probe); wiring lands in Phase 4.
        raise NotImplementedError(f"task {spec.task.value} lands in Phase 4; only DETECTION is wired")

    # Fail fast on a metric the spec names but the harness doesn't know (no silent skips).
    unknown = [k for k in spec.metrics if k not in REGISTRY]
    if unknown:
        raise KeyError(f"spec {spec.name!r} names unknown metrics {unknown}; known: {sorted(REGISTRY)}")

    texts, gold_tags = gold if gold is not None else _load_gold(spec)
    pred_tags = adapter.predict_tags(texts)

    scores = {key: REGISTRY[key](gold_tags, pred_tags) for key in spec.metrics}

    return {
        "spec": spec.name,
        "task": spec.task.value,
        "languages": spec.languages,
        "domain": spec.domain,
        "adapter": adapter.name,
        "model_id": adapter.model_id,
        "n": len(texts),
        "scores": scores,
        # provenance
        "europriv_bench_version": __version__,
        "taxonomy_version": TAXONOMY_VERSION,
        "dataset": {"hf_id": spec.dataset.hf_id, "config": spec.dataset.config, "split": spec.dataset.split},
        "timestamp": timestamp,
    }
