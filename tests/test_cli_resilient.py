"""The submission CI runs `europriv run --suite evaluations --adapter <x>` serially (workers=1).

A spec whose dataset config isn't published on the public HF revision must be SKIPPED with a
warning, not crash the whole run — otherwise the no-secrets submission CI (KLU-52) goes red for
every external submission. This guards that the serial CLI path tolerates a per-spec failure and
still writes the rows for the specs that succeeded (mirroring the parallel path).
"""

from __future__ import annotations

import json

from click.testing import CliRunner

import europriv_bench.main as main


def test_run_skips_unavailable_spec(tmp_path, monkeypatch):
    out = tmp_path / "lb.json"

    def fake_run_spec(spec, model, **kwargs):
        # Simulate one config being absent from the published dataset.
        if spec.dataset.config == "pl-realskeleton-v1":
            raise ValueError("BuilderConfig 'pl-realskeleton-v1' not found")
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
