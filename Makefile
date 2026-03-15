.PHONY: dev down build test lint format migrate seed reset logs help

# ── Default ────────────────────────────────────────────────────────
.DEFAULT_GOAL := help

# ── Development ────────────────────────────────────────────────────
dev: ## Start the full local stack (all 5 services)
	docker-compose up

dev-build: ## Build images and start the full local stack
	docker-compose up --build

down: ## Stop all containers
	docker-compose down

build: ## Build all Docker images
	docker-compose build

reset: ## ⚠️  Destroy all containers AND volumes (data loss!)
	docker-compose down -v

logs: ## Tail logs from all containers
	docker-compose logs -f

logs-backend: ## Tail backend logs only
	docker-compose logs -f backend

logs-worker: ## Tail worker logs only
	docker-compose logs -f worker

# ── Database ───────────────────────────────────────────────────────
migrate: ## Run all Alembic migrations (alembic upgrade head)
	docker-compose exec backend alembic upgrade head

migrate-rollback: ## Roll back last migration
	docker-compose exec backend alembic downgrade -1

seed: ## Seed the database with sample data
	docker-compose exec backend python infra/scripts/seed_db.py

reset-dev: ## Reset DB and re-seed (dev only)
	docker-compose exec backend bash infra/scripts/reset_dev.sh

# ── Testing ────────────────────────────────────────────────────────
test: ## Run all unit tests with verbose output
	docker-compose exec backend pytest tests/unit/ -v

test-coverage: ## Run unit tests with coverage report (target >80%)
	docker-compose exec backend pytest tests/unit/ --cov=shared --cov=backend --cov-report=term-missing

test-integration: ## Run the Day 6 weekly integration test
	docker-compose exec backend pytest tests/integration/ -v

test-e2e: ## Run end-to-end tests
	docker-compose exec backend pytest tests/e2e/ -v

test-security: ## Run security and RLS tests
	docker-compose exec backend pytest tests/security/ -v

test-all: ## Run ALL tests (unit + integration + e2e + security)
	docker-compose exec backend pytest tests/ -v

# ── Code Quality ───────────────────────────────────────────────────
lint: ## Run ruff linter + mypy type checker
	docker-compose exec backend ruff check . && mypy .

format: ## Auto-format code with black + isort
	docker-compose exec backend black . && isort .

# ── Utilities ──────────────────────────────────────────────────────
shell-backend: ## Open a shell in the backend container
	docker-compose exec backend bash

shell-db: ## Open psql in the database container
	docker-compose exec db psql -U parwa parwa_db

# ── Help ───────────────────────────────────────────────────────────
help: ## Show this help message
	@echo ""
	@echo "PARWA — Make Commands"
	@echo "════════════════════════════════════════"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
