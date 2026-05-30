"""EuroPriv-Bench CLI."""

from __future__ import annotations

from datetime import datetime, timezone

import click

from . import __version__
from .adapters import BUILDERS, build
from .leaderboard import write_leaderboard
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
def run(suite: str, adapters: tuple[str, ...], out: str, limit: int | None) -> None:
    """Run one or more adapters across a suite and write a combined leaderboard."""
    specs = load_suite(suite)
    ts = datetime.now(timezone.utc).isoformat()
    results = []
    for name in adapters:
        model = build(name)
        for spec in specs:
            logger.info("running %s on %s", name, spec.name)
            results.append(run_spec(spec, model, timestamp=ts, limit=limit))
    path = write_leaderboard(results, out)
    click.echo(f"wrote {path}")


@cli.command()
def taxonomy() -> None:
    """Print the harmonized KP taxonomy summary and BIOES label count."""
    click.echo(f"{len(TAXONOMY)} entity types across tiers; {len(bioes_labels())} BIOES labels")
    click.echo(f"GDPR Art.9 special-category types: {', '.join(special_category_types()) or '-'}")
    for e in TAXONOMY:
        click.echo(f"  {e.name:18s} {e.tier.value:9s} {e.identifier_class.value}")


if __name__ == "__main__":
    cli()
