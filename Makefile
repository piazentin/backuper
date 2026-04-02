PYTHON ?= python3
VENV := .venv
VENV_BIN := $(VENV)/bin
# All requirements files in repo root (e.g. requirements-dev.txt); add more as needed
REQUIREMENTS := $(sort $(wildcard requirements*.txt))

# Prefer .venv only when its interpreter is runnable (broken symlinks — e.g. after moving Python — are ignored)
PY := $(shell if [ -x "$(VENV_BIN)/python" ]; then echo "$(VENV_BIN)/python"; else echo "$(PYTHON)"; fi)
LINT_IMPORTS := $(shell if [ -x "$(VENV_BIN)/lint-imports" ]; then echo "$(VENV_BIN)/lint-imports"; else echo "lint-imports"; fi)

.PHONY: setup install venv test test-implementation test-coverage lint lint-fix format lint-imports

# Ensure a working venv, then pip-install every requirements*.txt
setup:
	@if [ ! -x "$(VENV_BIN)/python" ]; then \
		echo "Creating $(VENV) with $(PYTHON)..."; \
		rm -rf "$(VENV)"; \
		$(PYTHON) -m venv "$(VENV)"; \
	fi
	$(VENV_BIN)/pip install --upgrade pip
	@if [ -z "$(REQUIREMENTS)" ]; then \
		echo "No requirements*.txt found in repo root; nothing to install."; \
		exit 1; \
	fi
	@set -e; for f in $(REQUIREMENTS); do \
		echo "Installing $$f..."; \
		$(VENV_BIN)/pip install -r "$$f"; \
	done

install: setup

# Only ensures .venv exists (no pip install)
venv:
	@if [ ! -x "$(VENV_BIN)/python" ]; then \
		echo "Creating $(VENV) with $(PYTHON)..."; \
		rm -rf "$(VENV)"; \
		$(PYTHON) -m venv "$(VENV)"; \
	fi

test:
	$(PY) -m pytest test

test-implementation:
	$(PY) -m pytest test/implementation

test-coverage:
	$(PY) -m pytest test --cov=. --cov-report=term-missing

# All checks: formatting (Ruff), lint (Ruff), import boundaries (import-linter)
lint:
	$(PY) -m ruff format --check .
	$(PY) -m ruff check .
	$(LINT_IMPORTS)

# Apply Ruff formatting and auto-fixable lint fixes (does not run import-linter)
lint-fix:
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

# Format sources only (same formatter as lint / lint-fix)
format:
	$(PY) -m ruff format .

lint-imports:
	$(LINT_IMPORTS)
