"""EuroPriv-Bench CLI."""

from __future__ import annotations

from datetime import datetime, timezone

import click

from . import __version__
from .adapters import BUILDERS, build
from .leaderboard import format_leaderboard, write_leaderboard
from .logger import get_logger
from .runner import run_spec
from .spec import load_suite
from .taxonomy import TAXONOMY, bioes_labels, special_category_types

logger = get_logger("europriv")


@click.group()
@click.version_option(__version__)
def cli() -> None:
    """EuroPriv-Bench — unified pan-European de-identification benchmark."""


@cli.command(name="list")
@click.option("--suite", default="evaluations", help="Directory of eval specs.")
def list_specs(suite: str) -> None:
    """List and validate every eval spec in a suite."""
    for spec in load_suite(suite):
        langs = ",".join(spec.languages) or "-"
        click.echo(f"{spec.name:40s} task={spec.task.value:14s} domain={spec.domain:8s} langs={langs}")


@cli.command()
@click.option("--suite", default="evaluations", help="Directory of eval specs.")
@click.option("--adapter", "adapters", multiple=True, type=click.Choice(sorted(BUILDERS)),
              default=("dummy",), help="Model adapter(s); repeatable for a comparative leaderboard.")
@click.option("--out", default="baselines/leaderboard.json", help="Leaderboard output path.")
@click.option("--limit", type=int, default=None, help="Cap examples per spec (fast iteration).")
@click.option("--workers", type=int, default=1, help="Parallel worker processes over (adapter × spec) jobs.")
@click.option("--threads", type=int, default=4, help="BLAS threads per worker (4 is fastest for this MoE).")
@click.option("--dump-predictions", "dump_predictions", default=None,
              help="Write per-subject national-ID detection records (for item-paired McNemar, KLU-53) "
                   "to this JSON, alongside the leaderboard. Serial path only (requires --workers 1).")
def run(suite: str, adapters: tuple[str, ...], out: str, limit: int | None, workers: int, threads: int,
        dump_predictions: str | None) -> None:
    """Run one or more adapters across a suite and write a combined leaderboard.

    On a many-core Mac (M3 Ultra), use --workers ~7 --threads 4 to saturate cores: this model is
    small, so parallel thread-capped CPU jobs beat both default-threaded CPU and the GPU.
    """
    specs = load_suite(suite)
    ts = datetime.now(timezone.utc).isoformat()
    if workers > 1:
        if dump_predictions:
            raise click.ClickException("--dump-predictions requires the serial path (use --workers 1)")
        from .parallel import run_jobs
        logger.info("running %d adapter(s) × %d spec(s) on %d workers × %d threads",
                    len(adapters), len(specs), workers, threads)
        results = run_jobs(list(adapters), specs, limit, ts, workers, threads)
    else:
        try:
            import torch
            torch.set_num_threads(threads)  # default 28 is slower than 4 for this workload
        except ImportError:
            pass
        results = []
        dumps: list[dict] | None = [] if dump_predictions else None
        for name in adapters:
            model = build(name)
            for spec in specs:
                logger.info("running %s on %s", name, spec.name)
                try:
                    results.append(run_spec(spec, model, timestamp=ts, limit=limit, dumps=dumps))
                except Exception as e:
                    # A spec whose dataset config isn't published on the public HF revision (or any
                    # other per-spec failure) is logged + skipped, never aborting the whole run —
                    # mirroring the parallel path. This keeps the no-secrets submission CI green:
                    # an external adapter is still scored on every config that IS reachable.
                    logger.error("skipping spec %r for adapter %r: %s", spec.name, name, e)
        if dump_predictions is not None:
            import json
            from pathlib import Path
            dp = Path(dump_predictions)
            dp.parent.mkdir(parents=True, exist_ok=True)
            dp.write_text(json.dumps({"timestamp": ts, "dumps": dumps}, ensure_ascii=False, indent=2),
                          encoding="utf-8")
            click.echo(f"wrote predictions dump {dp}")
    path = write_leaderboard(results, out)
    click.echo(f"wrote {path}")


@cli.command()
@click.option("--in", "path", default="baselines/leaderboard.json", help="Leaderboard JSON to render.")
def leaderboard(path: str) -> None:
    """Pretty-print a leaderboard JSON (detection F1/F2 + CNP leakage)."""
    import json
    from pathlib import Path
    click.echo(format_leaderboard(json.loads(Path(path).read_text(encoding="utf-8"))))


@cli.group()
def submission() -> None:
    """Submission-CI helpers (KLU-16): validate a model card, run the reproduction gate."""


@submission.command(name="validate-card")
@click.argument("path", type=click.Path(exists=True))
def submission_validate_card(path: str) -> None:
    """Validate a submitted model-card YAML against the required-field schema."""
    from .submission import CardValidationError, validate_model_card_file

    try:
        card = validate_model_card_file(path)
    except CardValidationError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"model card OK: {card['hf_model_id']} via adapter {card['adapter']!r}")


@submission.command(name="reproduce")
@click.option("--in", "path", default="baselines/leaderboard.json", help="Leaderboard JSON to gate.")
@click.option("--tolerance", type=float, default=None, help="Override the ±band (default 0.02).")
def submission_reproduce(path: str, tolerance: float | None) -> None:
    """Reproduction gate: assert the committed anchor row is within the tolerance band."""
    from .submission import REPRO_TOLERANCE, check_reproduction_file

    ok, msg = check_reproduction_file(path, tolerance=tolerance if tolerance is not None else REPRO_TOLERANCE)
    click.echo(msg)
    if not ok:
        raise click.ClickException("reproduction gate FAILED")


@cli.command()
def taxonomy() -> None:
    """Print the harmonized KP taxonomy summary and BIOES label count."""
    click.echo(f"{len(TAXONOMY)} entity types across tiers; {len(bioes_labels())} BIOES labels")
    click.echo(f"GDPR Art.9 special-category types: {', '.join(special_category_types()) or '-'}")
    for e in TAXONOMY:
        click.echo(f"  {e.name:18s} {e.tier.value:9s} {e.identifier_class.value}")


if __name__ == "__main__":
    cli()
