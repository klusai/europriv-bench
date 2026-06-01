"""Run an adapter against an eval spec and compute its metrics.

Flow: spec → load held-out gold (HF) → adapter task method → metrics.REGISTRY → result dict.
Gold data is pulled from HF at eval time and never committed (see .gitignore).

Every result row carries provenance (harness version, taxonomy version, dataset config/split,
model_id, optional timestamp) so a published/cited number traces back to an exact harness +
taxonomy + dataset revision.
"""

from __future__ import annotations

from collections.abc import Iterable

from . import __version__
from .adapters import BaseAdapter
from .leaderboard import DEFAULT_CONFIG_STATUS, classify_contamination
from .logger import get_logger
from .metrics import ALL_METRICS, REGISTRY, ROW_REGISTRY
from .spans import Span, char_spans_to_bioes, validate_bioes
from .spec import EvalSpec, Task
from .taxonomy import TAXONOMY_VERSION

logger = get_logger(__name__)


def _rows_to_gold(rows: Iterable[dict]) -> tuple[list[str], list[list[str]]]:
    """Convert benchmark rows ``{text, spans:[{start,end,label}]}`` → (texts, gold BIOES tags).

    Gold spans already carry KP labels (the curation step mapped them), so no crosswalk here.
    Every example is validated, so a malformed published row fails loudly.
    """
    texts: list[str] = []
    gold: list[list[str]] = []
    for r in rows:
        text = r["text"]
        spans = [Span(s["start"], s["end"], s["label"]) for s in r["spans"]]
        tags = char_spans_to_bioes(text, spans)
        validate_bioes(tags)
        texts.append(text)
        gold.append(tags)
    return texts, gold


def _load_gold_rows(spec: EvalSpec) -> list[dict]:
    """Load gold rows ``{text, spans}`` for a spec from HF (requires the `hf` extra: datasets)."""
    from datasets import load_dataset

    ds = load_dataset(spec.dataset.hf_id, spec.dataset.config, split=spec.dataset.split)
    return [dict(r) for r in ds]


def run_spec(
    spec: EvalSpec,
    adapter: BaseAdapter,
    gold: tuple[list[str], list[list[str]]] | None = None,
    rows: list[dict] | None = None,
    timestamp: str | None = None,
    limit: int | None = None,
) -> dict:
    """Score one adapter on one spec. Gold may be injected as ``rows`` (preferred) or ``gold``
    (texts, tag-seqs, for tag-only tests); else loaded from HF. Row-metrics (e.g. cnp_leakage)
    require ``rows``. ``limit`` caps examples (recorded for honesty)."""
    if spec.task is not Task.DETECTION:
        # The seam exists (BaseAdapter.anonymize/classify/leakage_probe); wiring lands in Phase 4.
        raise NotImplementedError(f"task {spec.task.value} lands in Phase 4; only DETECTION is wired")

    # Fail fast on a metric the spec names but the harness doesn't know (no silent skips).
    unknown = [k for k in spec.metrics if k not in ALL_METRICS]
    if unknown:
        raise KeyError(f"spec {spec.name!r} names unknown metrics {unknown}; known: {sorted(ALL_METRICS)}")

    if rows is None and gold is None:
        rows = _load_gold_rows(spec)
    if rows is not None:
        if limit is not None:
            rows = rows[:limit]
        texts, gold_tags = _rows_to_gold(rows)
    else:
        texts, gold_tags = gold
        if limit is not None:
            texts, gold_tags = texts[:limit], gold_tags[:limit]
    pred_tags = adapter.predict_tags(texts)

    # Fairness: score only the entity types the gold annotates. A model isn't penalized for
    # detecting categories this gold doesn't cover (it predicts them → masked to O, not FPs).
    # Applied identically to every adapter so the leaderboard is apples-to-apples.
    eval_labels = {t.split("-", 1)[1] for seq in gold_tags for t in seq if t != "O"}
    pred_tags = [
        [t if (t == "O" or t.split("-", 1)[1] in eval_labels) else "O" for t in seq]
        for seq in pred_tags
    ]

    scores: dict[str, dict] = {}
    for key in spec.metrics:
        if key in ROW_REGISTRY:
            if rows is None:
                raise ValueError(f"metric {key!r} needs gold rows; inject rows= or load from HF")
            scores[key] = ROW_REGISTRY[key](rows, pred_tags)
        else:
            scores[key] = REGISTRY[key](gold_tags, pred_tags)

    return {
        "spec": spec.name,
        "task": spec.task.value,
        "languages": spec.languages,
        "domain": spec.domain,
        "adapter": adapter.name,
        "model_id": adapter.model_id,
        "n": len(texts),
        "limit": limit,
        "eval_labels": sorted(eval_labels),
        "scores": scores,
        # schema-3 governance markers (per model, config). See leaderboard.py / GOVERNANCE.md.
        # contamination: in_distribution | clean_held_out | unknown (derived from adapter+config).
        # config_status: dev | citable-validated; defaults to dev until KLU-27 sign-off promotes it.
        "contamination": classify_contamination(adapter.name, spec.dataset.config),
        "config_status": DEFAULT_CONFIG_STATUS,
        # provenance
        "europriv_bench_version": __version__,
        "taxonomy_version": TAXONOMY_VERSION,
        "dataset": {"hf_id": spec.dataset.hf_id, "config": spec.dataset.config, "split": spec.dataset.split},
        "timestamp": timestamp,
    }
