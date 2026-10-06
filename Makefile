PYTHON ?= python3

.PHONY: test check
test:
	$(PYTHON) scripts/check.py

check: test
