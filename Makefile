UV ?= uv

# Minimum line coverage for `make test-coverage` (pytest-cov `--cov-fail-under`). Override locally or in CI, e.g. `COVERAGE_FAIL_UNDER=85 make test-coverage`.
COVERAGE_FAIL_UNDER ?= 90

# Extra goals after `backup` are forwarded to the CLI, e.g.
#   make backup update ../source /path/to/backup-root
# Paths with spaces are not supported (Make splits on whitespace).
BACKUPER_PASS_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
ifneq ($(strip $(BACKUPER_PASS_ARGS)),)
$(eval $(BACKUPER_PASS_ARGS):;@:)
endif

.PHONY: sync setup install unit integration test test-coverage lint lint-fix format lint-imports backup

# Install project + dev dependencies from uv.lock
sync setup install:
	$(UV) sync --group dev

# Sync dev env then run the CLI (same as: uv sync --group dev && uv run backuper …)
backup:
	$(UV) sync --group dev && $(UV) run backuper $(BACKUPER_PASS_ARGS)

unit:
	$(UV) run python -m pytest test/unit

integration:
	$(UV) run python -m pytest test/integration

test:
	$(UV) run python -m pytest test/unit test/integration test/scripts

test-coverage:
	$(UV) run python -m pytest test/unit test/integration test/scripts --cov=. --cov-report=term-missing --cov-fail-under=$(COVERAGE_FAIL_UNDER)

lint:
	$(UV) run ruff format --check .
	$(UV) run ruff check .
	$(UV) run mypy -p backuper --explicit-package-bases
	$(UV) run lint-imports

lint-fix:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

format:
	$(UV) run ruff format .

lint-imports:
	$(UV) run lint-imports
