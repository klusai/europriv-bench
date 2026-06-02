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
from concurrent.futures import ProcessPoolExecutor, as_completed

from .logger import get_logger
from .runner import ConfigUnavailableError

logger = get_logger("europriv.parallel")


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
    # Pre-warm the HF dataset cache in the main process: build each unique (hf_id, config, split)
    # once here so workers read fully-built arrow files instead of racing to build the same repo's
    # configs concurrently (that race silently dropped just-published configs).
    seen: set = set()
    for spec in specs:
        d = spec.dataset
        key = (d.hf_id, d.config, d.split)
        if key in seen:
            continue
        seen.add(key)
        try:
            from datasets import load_dataset
            load_dataset(d.hf_id, d.config, split=d.split)
        except Exception as e:  # pragma: no cover - network/dep dependent
            logger.warning("cache pre-warm failed for %s/%s: %s", d.hf_id, d.config, e)

    jobs = [
        (name, spec.model_dump(mode="json"), limit, timestamp, threads)
        for name in adapters
        for spec in specs
    ]
    results: list[dict] = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_run_job, job): job for job in jobs}
        for fut in as_completed(futures):
            name, spec_dict, *_ = futures[fut]
            try:
                results.append(fut.result())
            except ConfigUnavailableError as e:
                # ONLY an unpublished config is logged + skipped; every other exception (a real eval
                # crash on an available config) propagates and fails the run loudly (KLU-58).
                logger.warning("skipping unavailable config (adapter=%s spec=%s): %s",
                               name, spec_dict.get("name"), e)
    return results
