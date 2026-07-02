# ==================================================================
# Enterprise Analytics Platform — developer entrypoints
# ==================================================================
.DEFAULT_GOAL := help
SHELL := /bin/bash
PY := python

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------- Environment ----------
.PHONY: setup
setup: ## Create venv and install all extras + dev tooling
	$(PY) -m venv .venv
	. .venv/bin/activate && pip install -U pip && pip install -e ".[spark,quality,api,app,ml,transform,dev]"
	. .venv/bin/activate && pre-commit install

.PHONY: env
env: ## Copy .env.example to .env if missing
	@test -f .env || cp .env.example .env && echo ".env ready"

# ---------- Quality gates ----------
.PHONY: fmt
fmt: ## Auto-format with black + ruff
	black src tests
	ruff check --fix src tests

.PHONY: lint
lint: ## Lint (ruff + black --check + mypy)
	ruff check src tests
	black --check src tests
	mypy src

.PHONY: test
test: ## Run pytest with coverage
	pytest

.PHONY: test-unit
test-unit: ## Run only unit tests
	pytest -m unit

# ---------- Pipeline ----------
.PHONY: ingest
ingest: ## Download + ingest raw Olist CSVs
	eap ingest run

.PHONY: spark
spark: ## Run Spark transformation jobs (CSV -> Parquet)
	eap spark run-all

.PHONY: warehouse
warehouse: ## Build the star schema warehouse (DuckDB)
	eap warehouse build

.PHONY: quality
quality: ## Run Great Expectations validation suites
	eap quality validate

.PHONY: dbt
dbt: ## Run dbt build (run + test) against DuckDB
	cd dbt/olist && dbt deps && dbt build

.PHONY: pipeline
pipeline: ingest spark warehouse dbt quality ## Full local pipeline end-to-end

# ---------- Services ----------
.PHONY: api
api: ## Start the FastAPI service
	uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

.PHONY: app
app: ## Start the Streamlit dashboard
	streamlit run streamlit/app.py

# ---------- Docker ----------
.PHONY: up
up: ## docker compose up (build + detached)
	docker compose up -d --build

.PHONY: down
down: ## docker compose down (keep volumes)
	docker compose down

.PHONY: clean
clean: ## Remove caches and generated artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	rm -rf dbt/olist/target dbt/olist/logs dbt/olist/dbt_packages
