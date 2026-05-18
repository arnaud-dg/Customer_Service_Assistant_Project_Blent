.PHONY: help install install-dev test test-cov lint format check clean run-notebook

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install production dependencies
	uv sync --no-dev

install-dev:  ## Install all dependencies including dev
	uv sync --all-extras
	pre-commit install

test:  ## Run the test suite
	uv run pytest

test-cov:  ## Run tests with coverage report
	uv run pytest --cov=src --cov-report=term-missing --cov-report=html

lint:  ## Check code quality
	uv run ruff check .
	uv run mypy src

format:  ## Auto-format code
	uv run ruff format .
	uv run ruff check . --fix

check: lint test  ## Run all checks (lint + test)

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .ipynb_checkpoints -exec rm -rf {} +

run-notebook:  ## Launch Jupyter Lab
	uv run jupyter lab
