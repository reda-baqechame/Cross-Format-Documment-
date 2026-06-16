.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down dev migrate revision codegen test lint fmt seed backend-install web-install prod-up prod-down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Start all services (postgres, redis, minio, api, worker, web)
	$(COMPOSE) up --build

down: ## Stop all services
	$(COMPOSE) down

dev: ## Run API and web locally (no docker) — requires deps installed
	@echo "Run 'make backend-install' and 'make web-install' first if needed."
	$(COMPOSE) up -d postgres redis minio
	cd backend && uvicorn docos.main:app --reload --host 0.0.0.0 --port 8000 & \
	pnpm --filter @docos/web dev

backend-install: ## Install Python deps with uv
	cd backend && uv sync

web-install: ## Install JS deps with pnpm
	pnpm install

migrate: ## Apply database migrations
	cd backend && alembic upgrade head

revision: ## Create a new migration (usage: make revision m="message")
	cd backend && alembic revision --autogenerate -m "$(m)"

codegen: ## Generate TS types from the live OpenAPI schema (API must be running)
	pnpm run codegen

test: ## Run backend tests
	cd backend && pytest -q

lint: ## Lint backend (ruff + mypy)
	cd backend && ruff check src tests && mypy src

fmt: ## Format backend
	cd backend && ruff format src tests

seed: ## Load sample documents for local development
	cd backend && python -m docos.scripts.seed

prod-up: ## Build & start the production stack (migrations run on API start)
	$(COMPOSE) -f docker-compose.prod.yml up --build -d

prod-down: ## Stop the production stack
	$(COMPOSE) -f docker-compose.prod.yml down
