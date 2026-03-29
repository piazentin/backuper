.PHONY: test test-coverage test-all

test:
	python3 -m pytest test/implementation

test-coverage:
	python3 -m pytest test/implementation --cov=backuper/implementation --cov-report=term-missing

test-all:
	python3 -m pytest test
