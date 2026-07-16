# CSFloat Tracker — task runner
# Windows users: run these via Git Bash, or use the commands inside each target directly.

PY := .venv/bin/python
ifeq ($(OS),Windows_NT)
PY := .venv/Scripts/python.exe
endif

.PHONY: help setup dev serve test lint fmt build itemdb docker clean

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

setup: ## Create venv, install backend (editable) + frontend deps
	uv venv .venv
	uv pip install -e ".[dev]" --python .venv
	cd frontend && npm install

dev: ## Run backend (:8422) and frontend dev server (:5180) together
	$(PY) -m uvicorn --factory csfloat_tracker.server.app:create_app --port 8422 --app-dir src --reload & \
	cd frontend && npm run dev

serve: ## Run the production app (serves built frontend)
	$(PY) -m csfloat_tracker.cli serve

test: ## Run the Python test suite with coverage
	$(PY) -m pytest --cov --cov-report=term-missing

lint: ## Ruff + TypeScript typecheck
	$(PY) -m ruff check src tests scripts
	cd frontend && npm run lint

fmt: ## Auto-fix lint issues
	$(PY) -m ruff check src tests scripts --fix

build: ## Build the frontend and the Python wheel
	cd frontend && npm run build
	uv build

itemdb: ## Regenerate data/cs2_items.json from the live CSFloat schema
	$(PY) scripts/generate_itemdb.py

docker: ## Build and start via docker compose
	docker compose up --build

clean: ## Remove build artifacts
	rm -rf dist build frontend/dist .pytest_cache .ruff_cache htmlcov .coverage
