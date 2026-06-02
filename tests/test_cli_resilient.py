"""The submission CI runs `europriv run --suite evaluations --adapter <x>` serially (workers=1).

A spec whose dataset config isn't published on the public HF revision must be SKIPPED with a
warning, not crash the whole run — otherwise the no-secrets submission CI (KLU-52) goes red for
every external submission. But that skip must be NARROW (KLU-58): a genuine eval crash on an
*available* config must FAIL LOUD, not be silently swallowed. These tests guard both halves for
the serial CLI path and the parallel `run_jobs` path.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

import europriv_bench.main as main
import europriv_bench.parallel as parallel
from europriv_bench.runner import ConfigUnavailableError, _load_gold_rows
from europriv_bench.spec import DatasetRef, EvalSpec, Task


def test_run_skips_unavailable_spec(tmp_path, monkeypatch):
    """An unpublished config is skipped with a warning; the reachable configs still get scored."""
    out = tmp_path / "lb.json"

    def fake_run_spec(spec, model, **kwargs):
        # Simulate one config being absent from the published dataset (the narrow, allowed skip).
        if spec.dataset.config == "pl-realskeleton-v1":
            raise ConfigUnavailableError("config 'pl-realskeleton-v1' not published")
        # Everything else: a minimal valid row (don't touch HF/models in a unit test).
        return {
            "spec": spec.name,
            "adapter": model.name,
            "model_id": model.model_id,
            "dataset": {"hf_id": spec.dataset.hf_id, "config": spec.dataset.config,
                        "split": spec.dataset.split},
            "scores": {},
            "n": 0,
        }

    monkeypatch.setattr(main, "run_spec", fake_run_spec)

    result = CliRunner().invoke(
        main.cli, ["run", "--suite", "evaluations", "--adapter", "dummy", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output

    board = json.loads(out.read_text())
    configs = {r["dataset"]["config"] for rows in board["entries"].values() for r in rows}
    # The unavailable config is absent; the reachable ones survived.
    assert "pl-realskeleton-v1" not in configs
    assert {"en", "de", "ro-synthetic-v1"} <= configs


def test_run_fails_loud_on_real_eval_error(tmp_path, monkeypatch):
    """A genuine eval crash on an AVAILABLE config must fail the whole run, not be skipped.

    Regression guard for KLU-58: the old broad `except Exception` would have logged-and-skipped
    this, silently dropping a row and hiding a real bug.
    """
    out = tmp_path / "lb.json"

    def fake_run_spec(spec, model, **kwargs):
        # A real bug surfacing on a perfectly available config (e.g. a metric/shape error).
        if spec.dataset.config == "en":
            raise ValueError("predicted tag sequence length != gold length")
        return {
            "spec": spec.name, "adapter": model.name, "model_id": model.model_id,
            "dataset": {"hf_id": spec.dataset.hf_id, "config": spec.dataset.config,
                        "split": spec.dataset.split},
            "scores": {}, "n": 0,
        }

    monkeypatch.setattr(main, "run_spec", fake_run_spec)

    result = CliRunner().invoke(
        main.cli, ["run", "--suite", "evaluations", "--adapter", "dummy", "--out", str(out)]
    )
    # Non-zero exit and the underlying error propagated (not swallowed); no leaderboard written.
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert not out.exists()


def test_parallel_skips_unavailable_spec(monkeypatch):
    """run_jobs skips ONLY the unavailable config and returns rows for the rest."""
    specs = [
        EvalSpec(name="ok", task=Task.DETECTION, dataset=DatasetRef(hf_id="x", config="en")),
        EvalSpec(name="gone", task=Task.DETECTION,
                 dataset=DatasetRef(hf_id="x", config="pl-realskeleton-v1")),
    ]

    def fake_submit(self, fn, job):
        # Stand in for the process pool: run the job body inline so we can assert behavior without
        # spawning workers, while still exercising run_jobs' result-collection branching.
        class _Fut:
            def __init__(self, payload):
                name, spec_dict, *_ = payload
                self._payload = payload
                self._cfg = spec_dict["dataset"]["config"]

            def result(self):
                if self._cfg == "pl-realskeleton-v1":
                    raise ConfigUnavailableError("config 'pl-realskeleton-v1' not published")
                return {"dataset": {"config": self._cfg}}

        return _Fut(job)

    # Neutralize the best-effort cache pre-warm (it does `from datasets import load_dataset`).
    monkeypatch.setattr("datasets.load_dataset", lambda *a, **k: None, raising=False)
    monkeypatch.setattr("concurrent.futures.ProcessPoolExecutor.submit", fake_submit)
    # as_completed must just yield the futures we created.
    monkeypatch.setattr(parallel, "as_completed", lambda futures: list(futures))

    results = parallel.run_jobs(["dummy"], specs, None, "ts", workers=2, threads=4)
    configs = {r["dataset"]["config"] for r in results}
    assert configs == {"en"}


def test_parallel_fails_loud_on_real_eval_error(monkeypatch):
    """run_jobs re-raises a genuine eval crash on an available config (KLU-58)."""
    specs = [EvalSpec(name="ok", task=Task.DETECTION,
                      dataset=DatasetRef(hf_id="x", config="en"))]

    def fake_submit(self, fn, job):
        class _Fut:
            def result(self):
                raise ValueError("predicted tag sequence length != gold length")

        return _Fut()

    monkeypatch.setattr("datasets.load_dataset", lambda *a, **k: None, raising=False)
    monkeypatch.setattr("concurrent.futures.ProcessPoolExecutor.submit", fake_submit)
    monkeypatch.setattr(parallel, "as_completed", lambda futures: list(futures))

    with pytest.raises(ValueError, match="tag sequence length"):
        parallel.run_jobs(["dummy"], specs, None, "ts", workers=1, threads=4)


# --- the discriminator itself: only the genuine "config not published" case is translated ---

def _spec(config="pl-realskeleton-v1"):
    return EvalSpec(name="s", task=Task.DETECTION,
                    dataset=DatasetRef(hf_id="klusai/europriv-bench", config=config))


def test_load_gold_rows_translates_missing_config_to_unavailable(monkeypatch):
    """datasets raises a bare ValueError "BuilderConfig '<cfg>' not found" for an unpublished
    config → translated to ConfigUnavailableError (the allowed skip)."""
    def boom(hf_id, config, split):
        raise ValueError(
            f"BuilderConfig '{config}' not found. Available: ['en', 'de', 'ro-synthetic-v1']"
        )

    monkeypatch.setattr("datasets.load_dataset", boom)
    with pytest.raises(ConfigUnavailableError):
        _load_gold_rows(_spec())


def test_load_gold_rows_translates_missing_dataset_to_unavailable(monkeypatch):
    """A missing repo/revision (DatasetNotFoundError) is also treated as unavailable."""
    from datasets.exceptions import DatasetNotFoundError

    def boom(hf_id, config, split):
        raise DatasetNotFoundError(f"Dataset '{hf_id}' doesn't exist on the Hub")

    monkeypatch.setattr("datasets.load_dataset", boom)
    with pytest.raises(ConfigUnavailableError):
        _load_gold_rows(_spec())


def test_load_gold_rows_propagates_real_value_error(monkeypatch):
    """A ValueError that is NOT the missing-config signature is a real error → propagates as-is,
    NOT swallowed as ConfigUnavailableError."""
    def boom(hf_id, config, split):
        raise ValueError("corrupt arrow shard: schema mismatch in column 'spans'")

    monkeypatch.setattr("datasets.load_dataset", boom)
    with pytest.raises(ValueError) as ei:
        _load_gold_rows(_spec())
    assert not isinstance(ei.value, ConfigUnavailableError)


def test_load_gold_rows_propagates_unrelated_exception(monkeypatch):
    """Any non-ValueError loader failure (network, etc.) propagates untouched."""
    def boom(hf_id, config, split):
        raise RuntimeError("connection reset")

    monkeypatch.setattr("datasets.load_dataset", boom)
    with pytest.raises(RuntimeError):
        _load_gold_rows(_spec())
