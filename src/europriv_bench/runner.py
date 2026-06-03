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
from .metrics import ALL_METRICS, ANON_MAP_REGISTRY, ANON_REGISTRY, REGISTRY, ROW_REGISTRY
from .spans import Span, char_spans_to_bioes, validate_bioes
from .spec import EvalSpec, Task
from .taxonomy import TAXONOMY_VERSION

logger = get_logger(__name__)


class ConfigUnavailableError(Exception):
    """The spec's dataset config isn't published on the resolved HF revision.

    This is the ONE failure a run is allowed to skip-and-continue (so the no-secrets submission CI
    stays green when a config like ``pl-realskeleton-v1`` hasn't been pushed yet). It is raised only
    for the genuinely-unavailable case — a missing repo/revision or a missing config name — so the
    run loop can catch *this* and let every other (real eval) exception propagate and fail loud.
    """


def _load_gold_rows(spec: EvalSpec) -> list[dict]:
    """Load gold rows ``{text, spans}`` for a spec from HF (requires the `hf` extra: datasets).

    Translates only the "config genuinely not published" failures into ``ConfigUnavailableError``;
    any other loader error (corrupt rows, network, schema drift) propagates unchanged so a real
    crash on an *available* config fails the run instead of being silently skipped.
    """
    from datasets import load_dataset
    from datasets.exceptions import DatasetNotFoundError

    cfg = spec.dataset.config
    try:
        ds = load_dataset(spec.dataset.hf_id, cfg, split=spec.dataset.split)
    except DatasetNotFoundError as e:
        # Repo or revision absent on the hub (DatasetNotFoundError ⊂ FileNotFoundError) → unavailable.
        raise ConfigUnavailableError(
            f"dataset {spec.dataset.hf_id!r} (config {cfg!r}) not found on the hub: {e}"
        ) from e
    except ValueError as e:
        # datasets surfaces an unknown *config* name (repo exists, config not published) as a bare
        # ValueError "BuilderConfig '<name>' not found. Available: [...]". Match precisely on that
        # signature + the requested config name so a real eval ValueError is NOT swallowed.
        msg = str(e)
        if cfg and f"BuilderConfig '{cfg}' not found" in msg:
            raise ConfigUnavailableError(
                f"config {cfg!r} not published for dataset {spec.dataset.hf_id!r}: {e}"
            ) from e
        raise
    return [dict(r) for r in ds]


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


def _run_anonymization(
    spec: EvalSpec,
    adapter: BaseAdapter,
    rows: list[dict] | None,
    texts: list[str],
    gold_tags: list[list[str]],
    timestamp: str | None,
    limit: int | None,
) -> dict:
    """Track C (KLU-104): score a redaction/pseudonymization adapter on its anonymized output.

    Two metric families:
      * ``ANON_REGISTRY`` (redaction_leakage / information_retention / structural_disruption) score
        the adapter's redacted text (``adapter.anonymize``) against the GOLD rows. The re-id leak is
        computed from gold offsets vs the output — never a detector re-run on the output.
      * ``ANON_MAP_REGISTRY`` (pseudonymization_consistency) scores the per-doc surrogate maps from
        ``adapter.pseudonymize``.

    Track C requires gold span values (offsets), so ``rows`` is mandatory. We ALSO compute the
    redactor's detection recall separately (entity_f1/entity_f2 over the SAME predict_tags the
    redaction masks), so a high post-redaction leak is attributable to recall failure vs masking
    policy (KLU-104). DETECTION scoring is untouched by this path.
    """
    if rows is None:
        raise ValueError("Track C (anonymization) metrics need gold rows; inject rows= or load from HF")

    scores: dict[str, dict] = {}
    needs_text = [k for k in spec.metrics if k in ANON_REGISTRY]
    needs_maps = [k for k in spec.metrics if k in ANON_MAP_REGISTRY]

    if needs_text:
        redacted = adapter.anonymize(texts)
        for key in needs_text:
            scores[key] = ANON_REGISTRY[key](rows, redacted)
    if needs_maps:
        mappings = adapter.pseudonymize(texts)
        for key in needs_maps:
            scores[key] = ANON_MAP_REGISTRY[key](rows, mappings)

    # Detection recall of the underlying redactor, reported SEPARATELY from the post-redaction leak
    # (KLU-104): same predict_tags + eval-label fairness mask as the DETECTION path, so recall here
    # is the recall that drives what anonymize() masks.
    pred_tags = adapter.predict_tags(texts)
    eval_labels = {t.split("-", 1)[1] for seq in gold_tags for t in seq if t != "O"}
    pred_tags = [
        [t if (t == "O" or t.split("-", 1)[1] in eval_labels) else "O" for t in seq]
        for seq in pred_tags
    ]
    scores["detection_recall"] = REGISTRY["entity_f2"](gold_tags, pred_tags)

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
        "contamination": classify_contamination(adapter.name, spec.dataset.config),
        "config_status": DEFAULT_CONFIG_STATUS,
        "europriv_bench_version": __version__,
        "taxonomy_version": TAXONOMY_VERSION,
        "dataset": {"hf_id": spec.dataset.hf_id, "config": spec.dataset.config, "split": spec.dataset.split},
        "timestamp": timestamp,
    }


def run_spec(
    spec: EvalSpec,
    adapter: BaseAdapter,
    gold: tuple[list[str], list[list[str]]] | None = None,
    rows: list[dict] | None = None,
    timestamp: str | None = None,
    limit: int | None = None,
    dumps: list[dict] | None = None,
) -> dict:
    """Score one adapter on one spec. Gold may be injected as ``rows`` (preferred) or ``gold``
    (texts, tag-seqs, for tag-only tests); else loaded from HF. Row-metrics (e.g. cnp_leakage)
    require ``rows``. ``limit`` caps examples (recorded for honesty).

    When ``dumps`` is provided, a per-subject national-ID detection record (KLU-53, for item-paired
    McNemar significance) is appended to it: ``{adapter, model_id, spec, dataset, n, subjects:[...]}``
    where each subject carries its ``detected``/``leaked`` flag under the exact same per-subject
    ``(doc, country, normalized value)`` semantics as the re-id leak-rate. Requires ``rows`` (the
    span values), so it is emitted only for row-metric specs run against real gold."""
    # Track gating: DETECTION (the original v0 path, unchanged) and ANONYMIZATION (Track C, KLU-104)
    # are wired. CLASSIFICATION/LEAKAGE still raise — the seam exists but is not implemented, so the
    # harness never silently reports a fake number. Lifting ANONYMIZATION does NOT touch DETECTION.
    if spec.task not in (Task.DETECTION, Task.ANONYMIZATION):
        raise NotImplementedError(
            f"task {spec.task.value} not wired; only DETECTION and ANONYMIZATION (Track C) are"
        )

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

    if spec.task is Task.ANONYMIZATION:
        return _run_anonymization(spec, adapter, rows, texts, gold_tags, timestamp, limit)

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

    # KLU-53: per-subject national-ID detection dump for item-paired McNemar significance. Emitted
    # only when requested AND the spec actually scores a national-ID re-id metric on real rows —
    # uses the SAME masked pred_tags fed to the metric, so the dumped flags match the leak-rate.
    if dumps is not None and rows is not None and (
        "cnp_leakage" in spec.metrics or "national_id_leakage" in spec.metrics
    ):
        from .metrics import national_id_subject_detection

        dumps.append({
            "adapter": adapter.name,
            "model_id": adapter.model_id,
            "spec": spec.name,
            "dataset": {"hf_id": spec.dataset.hf_id, "config": spec.dataset.config,
                        "split": spec.dataset.split},
            "n": len(texts),
            "limit": limit,
            "subjects": national_id_subject_detection(rows, pred_tags),
        })

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
