"""Eval-spec schema (YAML → pydantic), modeled on klu-bench's YAML evaluation files.

One spec describes a single benchmark task: which held-out dataset, which task family, and
which metrics to compute. Specs live under ``evaluations/`` and are versioned with the repo.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class Task(str, Enum):
    DETECTION = "detection"            # PII/PHI token classification (entity F1)
    ANONYMIZATION = "anonymization"    # redaction / pseudonymization quality + utility
    CLASSIFICATION = "classification"  # document-level privacy/sensitivity
    LEAKAGE = "leakage"                # membership-inference / re-identification risk


class DatasetRef(BaseModel):
    """A held-out gold dataset, pulled from HF at eval time (never committed)."""

    hf_id: str                          # e.g. "klusai/europriv-bench"
    config: str | None = None           # HF dataset config (per lang/domain)
    split: str = "test"
    license: str | None = None          # recorded for the openly-redistributable guarantee
    loader: Literal["datasets", "ai4privacy-openpii", "gateway"] = "datasets"
    local_path: str | None = None
    manifest_path: str | None = None
    eval_config: str | None = None      # stable eval identity when distinct from the HF config
    revision: str | None = None
    files: list[str] = Field(default_factory=list)
    max_rows: int | None = Field(default=None, gt=0)

    @property
    def identity(self) -> str | None:
        return self.eval_config or self.config

    def provenance(self) -> dict:
        result = {"hf_id": self.hf_id, "config": self.config, "split": self.split}
        if self.loader != "datasets":
            result.update(self.model_dump(exclude_none=True))
        return result


class EvalSpec(BaseModel):
    name: str
    version: int = 1
    task: Task
    languages: list[str] = Field(default_factory=list)  # ISO codes, e.g. ["ro", "de"]
    domain: str = "general"                              # general | legal | clinical
    dataset: DatasetRef
    metrics: list[str] = Field(default_factory=list)     # metric keys from metrics.py
    description: str | None = None

    @classmethod
    def from_yaml(cls, path: str | Path) -> "EvalSpec":
        with open(path, encoding="utf-8") as f:
            return cls.model_validate(yaml.safe_load(f))


def load_suite(directory: str | Path) -> list[EvalSpec]:
    """Load and validate every ``*.yaml`` spec in a directory."""
    directory = Path(directory)
    return [EvalSpec.from_yaml(p) for p in sorted(directory.glob("*.yaml"))]
