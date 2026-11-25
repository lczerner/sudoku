# SPDX-License-Identifier: MIT
# Copyright 2026 Lukáš Czerner <lukas@czerner.cz>

PYTHON ?= python3
RUFF ?= ruff

.DEFAULT_GOAL := help
.PHONY: help test lint clean

help: ## Show this help
	@echo "Usage: make <target>"
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "} {printf "  %-6s %s\n", $$1, $$2}'

test: ## Run the test suite
	$(PYTHON) -m unittest

lint: ## Check the code with ruff
	$(RUFF) check .

clean: ## Remove caches and the default output sudoku.pdf
	rm -rf __pycache__ .ruff_cache
	rm -f sudoku.pdf
