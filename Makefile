.PHONY: test test-implementation test-coverage format format-check

test:
	python3 -m pytest test

test-implementation:
	python3 -m pytest test/implementation

test-coverage:
	python3 -m pytest test --cov=. --cov-report=term-missing

format:
	python3 -m black .

format-check:
	python3 -m black --check .
