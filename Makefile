UV ?= uv

.PHONY: sync setup install unit integration test test-coverage lint lint-fix format lint-imports

# Install project + dev dependencies from uv.lock
sync setup install:
	$(UV) sync --group dev

unit:
	$(UV) run python -m pytest test/unit

integration:
	$(UV) run python -m pytest test/integration

test:
	$(UV) run python -m pytest test/unit test/integration

test-coverage:
	$(UV) run python -m pytest test/unit test/integration --cov=. --cov-report=term-missing

lint:
	$(UV) run ruff format --check .
	$(UV) run ruff check .
	$(UV) run lint-imports

lint-fix:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

format:
	$(UV) run ruff format .

lint-imports:
	$(UV) run lint-imports
