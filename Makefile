.PHONY: help install lint typecheck security test test-unit test-integration test-e2e test-load coverage docs docs-serve build clean

PY ?= python
PIP ?= $(PY) -m pip

help:  ## Show this help.
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  %-22s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install:  ## Install in editable mode with all extras.
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[test,lint,docs]"

lint:  ## Run ruff.
	ruff check src tests

typecheck:  ## Run pyright in strict mode.
	pyright

security:  ## Run bandit.
	bandit -r src -c pyproject.toml

test-unit:  ## Run unit tests only.
	pytest tests/unit -m unit

test-integration:  ## Run integration tests (requires Docker).
	pytest tests/integration -m integration

test-e2e:  ## Run end-to-end tests (requires Docker).
	pytest tests/e2e -m e2e

test-load:  ## Run load tests (requires Docker).
	pytest tests/load -m load

test:  ## Run unit tests with coverage.
	pytest tests/unit --cov=langchain_rabbitmq --cov-report=term-missing

coverage:  ## Generate coverage HTML report.
	pytest tests/unit --cov=langchain_rabbitmq --cov-report=html
	@echo "Open htmlcov/index.html"

docs:  ## Build the MkDocs site.
	mkdocs build --strict

docs-serve:  ## Serve docs locally with hot reload.
	mkdocs serve

build:  ## Build sdist and wheel.
	$(PY) -m build

clean:  ## Remove build artefacts.
	rm -rf build dist *.egg-info site htmlcov .pytest_cache .ruff_cache .pyright .coverage coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
