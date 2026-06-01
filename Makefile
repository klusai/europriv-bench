.PHONY: help test lint check install run-baselines submission-check

VENV := .venv/bin/activate
RUN := source $(VENV) &&

help:
	@echo "Available targets:"
	@echo ""
	@echo "  Quality:"
	@echo "    make test          - Run tests with coverage"
	@echo "    make lint          - Run ruff linter"
	@echo "    make check         - Run tests + lint"
	@echo ""
	@echo "  Setup:"
	@echo "    make install       - Install europriv-bench in dev mode with dev deps"
	@echo ""
	@echo "  Benchmark:"
	@echo "    make run-baselines - Regenerate the baseline leaderboard"
	@echo ""
	@echo "  Submission CI (KLU-16):"
	@echo "    make submission-check - Reproduction gate vs committed leaderboard.json"

install:
	$(RUN) pip install -e '.[dev]'

test:
	$(RUN) coverage run -m pytest
	$(RUN) coverage report

lint:
	$(RUN) ruff check .

format:
	$(RUN) ruff format .

check: test lint

run-baselines:
	$(RUN) europriv run --suite evaluations --adapter dummy --out baselines/leaderboard.json

# Reproduction gate (KLU-16): the locally-runnable equivalent of the CI gate step. Asserts the
# committed privacy-filter English anchor (0.415 ±0.02) still holds against leaderboard.json.
submission-check:
	$(RUN) europriv submission reproduce --in baselines/leaderboard.json
