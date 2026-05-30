# Contributing — KlusAI Privacy program conventions

## Repo layout rule (applies across the program)

- **Distributable tools / libraries** → `src/` layout + `[project.scripts]` console entry
  point. Examples: `europriv-bench` (this repo, CLI `europriv`), `klusai-infra` (`kai`),
  `klu-bench`. These are pip-installed and imported by others.
- **Internal research / container repos** → flat top-level package + `scripts/` run as
  `python scripts/x.py` + `conf/`. Examples: `klusai-datasets`, `klusai-models`,
  `tinyfabulist-tf3`, `diacritics-finetuning-code`. They publish many HF artifacts; scripts
  are run from the repo root after `make install`.

## Import namespace

- Container repos use the **`klusai.privacy.*`** PEP 420 namespace
  (`klusai.privacy.datasets`, `klusai.privacy.models`, `klusai.privacy.sdk`) — no
  `__init__.py` at `klusai/` or `klusai/privacy/`.
- `europriv-bench` keeps its standalone import root `europriv_bench` (it is the
  independently-citable flagship) and is the **single source of truth** for the harmonized
  taxonomy (`europriv_bench.taxonomy`) and span alignment (`europriv_bench.spans`). Other
  repos import these — never copy them. A `TAXONOMY_VERSION` is stamped into every result.

## Quality bar

Python 3.13, ruff (line-length 120, E/F/I), `make check` (pytest + ruff) green before commit.
Metrics that aren't implemented yet must raise `NotImplementedError` — never report a fake number.
