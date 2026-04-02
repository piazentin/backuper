.PHONY: test test-implementation test-coverage lint lint-fix format lint-imports

test:
	python3 -m pytest test

test-implementation:
	python3 -m pytest test/implementation

test-coverage:
	python3 -m pytest test --cov=. --cov-report=term-missing

# All checks: formatting (Ruff), lint (Ruff), import boundaries (import-linter)
lint:
	python3 -m ruff format --check .
	python3 -m ruff check .
	lint-imports

# Apply Ruff formatting and auto-fixable lint fixes (does not run import-linter)
lint-fix:
	python3 -m ruff format .
	python3 -m ruff check --fix .

# Format sources only (same formatter as lint / lint-fix)
format:
	python3 -m ruff format .

lint-imports:
	lint-imports
