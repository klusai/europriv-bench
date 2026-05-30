"""Parallel evaluation across CPU cores — the real M3-Ultra speedup for this benchmark.

Empirically (openai/privacy-filter on an M3 Ultra): the model is small (50M active params, short
sequences), so neither MPS nor MLX beats CPU, and PyTorch's default 28 BLAS threads are SLOWER
than 4 (thread contention on tiny ops: 4→0.041, 28→0.083 s/ex). The win is to run many
*thread-capped* (adapter × spec) jobs concurrently: ~7 workers × 4 threads saturates the 28 cores,
each job at its fastest. (Large models / training are a different story — that's where the GPU and
MLX earn their keep.)

Each job loads its own model in a fresh process (spawn), so thread caps are set before torch imports.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor


def _run_job(payload: tuple) -> dict:
    adapter_name, spec_dict, limit, timestamp, threads = payload
    # Cap BLAS threads BEFORE torch is imported (smaller is faster for this workload).
    os.environ["OMP_NUM_THREADS"] = str(threads)
    os.environ["MKL_NUM_THREADS"] = str(threads)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import torch

    torch.set_num_threads(threads)
    from .adapters import build
    from .runner import run_spec
    from .spec import EvalSpec

    spec = EvalSpec.model_validate(spec_dict)
    return run_spec(spec, build(adapter_name), timestamp=timestamp, limit=limit)


def run_jobs(
    adapters: list[str],
    specs: list,
    limit: int | None,
    timestamp: str,
    workers: int,
    threads: int,
) -> list[dict]:
    """Run every (adapter × spec) job across a process pool. Returns result dicts (order-agnostic)."""
    jobs = [
        (name, spec.model_dump(mode="json"), limit, timestamp, threads)
        for name in adapters
        for spec in specs
    ]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(_run_job, jobs))
