# ════════════════════════════════════════════════════════════════
# PARWA — Makefile for Docker-based Development & Production
# ════════════════════════════════════════════════════════════════
# Usage:
#   make dev          — Start development stack
#   make prod         — Start production stack
#   make build        — Build all images (dev)
#   make build-prod   — Build all production images
#   make stop         — Stop development stack
#   make stop-prod    — Stop production stack
#   make logs         — View development logs
#   make logs-prod    — View production logs
#   make health       — Check health of all services
#   make migrate      — Run database migrations
#   make shell        — Open a shell in the backend container
#   make psql         — Open PostgreSQL shell
#   make redis-cli    — Open Redis CLI
#   make clean        — Remove all containers, volumes, and images
#   make setup        — First-time setup (copy .env, build, start)
# ════════════════════════════════════════════════════════════════

.PHONY: dev prod build build-prod stop stop-prod logs logs-prod \
        health migrate shell psql redis-cli clean setup validate-env

# ── Configuration ──────────────────────────────────────────────
COMPOSE_DEV  = docker compose -f docker-compose.yml
COMPOSE_PROD = docker compose -f docker-compose.prod.yml

# ── Development ────────────────────────────────────────────────
dev: ## Start development stack
	@echo "🚀 Starting Parwa development stack..."
	$(COMPOSE_DEV) up -d
	@echo "✅ Development stack running at http://localhost:3000"
	@echo "   Backend API: http://localhost:8000"
	@echo "   API Docs:    http://localhost:8000/docs"

dev-build: ## Build and start development stack
	@echo "🔨 Building Parwa development images..."
	$(COMPOSE_DEV) build
	$(COMPOSE_DEV) up -d
	@echo "✅ Development stack running at http://localhost:3000"

# ── Production ─────────────────────────────────────────────────
prod: validate-env ## Start production stack (requires .env.prod)
	@echo "🚀 Starting Parwa production stack..."
	$(COMPOSE_PROD) up -d
	@echo "✅ Production stack started"
	@echo "   Nginx: http://localhost:80 → https://localhost:443"

prod-build: ## Build production images
	@echo "🔨 Building Parwa production images..."
	$(COMPOSE_PROD) build
	@echo "✅ Production images built"

# ── Build ──────────────────────────────────────────────────────
build: ## Build all development images
	$(COMPOSE_DEV) build

build-prod: ## Build all production images
	$(COMPOSE_PROD) build

# ── Stop ───────────────────────────────────────────────────────
stop: ## Stop development stack
	@echo "🛑 Stopping development stack..."
	$(COMPOSE_DEV) down

stop-prod: ## Stop production stack
	@echo "🛑 Stopping production stack..."
	$(COMPOSE_PROD) down

# ── Logs ───────────────────────────────────────────────────────
logs: ## View development logs (follow mode)
	$(COMPOSE_DEV) logs -f

logs-prod: ## View production logs (follow mode)
	$(COMPOSE_PROD) logs -f

logs-backend: ## View backend logs only
	$(COMPOSE_DEV) logs -f backend

# ── Health Checks ──────────────────────────────────────────────
health: ## Check health of all running services
	@echo "🏥 Checking service health..."
	@echo ""
	@echo "── Frontend ──"
	@curl -sf http://localhost:3000/api 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  ❌ Frontend not responding"
	@echo ""
	@echo "── Backend ──"
	@curl -sf http://localhost:8000/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  ❌ Backend not responding"
	@echo ""
	@echo "── Database ──"
	@docker exec parwa_db pg_isready -U parwa 2>/dev/null && echo "  ✅ PostgreSQL is ready" || echo "  ❌ PostgreSQL not ready"
	@echo ""
	@echo "── Redis ──"
	@docker exec parwa_redis redis-cli -a parwa_dev_redis ping 2>/dev/null | grep -q PONG && echo "  ✅ Redis is ready" || echo "  ❌ Redis not ready"

health-prod: ## Check health of all production services
	@echo "🏥 Checking production service health..."
	@curl -sf http://localhost:8000/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  ❌ Backend not responding (may be behind nginx)"
	@curl -sf http://localhost/health 2>/dev/null && echo "  ✅ Nginx is healthy" || echo "  ❌ Nginx not responding"

# ── Database ───────────────────────────────────────────────────
migrate: ## Run Alembic database migrations
	@echo "📦 Running database migrations..."
	docker exec parwa_backend bash -c "cd /app/backend && alembic upgrade head"

psql: ## Open PostgreSQL shell
	docker exec -it parwa_db psql -U parwa -d parwa_db

redis-cli: ## Open Redis CLI
	docker exec -it parwa_redis redis-cli -a parwa_dev_redis

# ── Shell ──────────────────────────────────────────────────────
shell: ## Open bash shell in backend container
	docker exec -it parwa_backend bash

shell-prod: ## Open bash shell in production backend container
	docker exec -it parwa_prod_backend bash

# ── Validation ─────────────────────────────────────────────────
validate-env: ## Validate production .env.prod exists and has required variables
	@if [ ! -f .env.prod ]; then \
		echo "❌ .env.prod not found! Copy .env.prod.example and fill in real values:"; \
		echo "   cp .env.prod.example .env.prod"; \
		exit 1; \
	fi
	@echo "🔍 Validating .env.prod..."
	@for var in SECRET_KEY POSTGRES_PASSWORD REDIS_PASSWORD JWT_SECRET_KEY; do \
		if grep -q "CHANGE_ME\|your_.*_here" .env.prod 2>/dev/null; then \
			echo "⚠️  WARNING: .env.prod contains placeholder values. Replace them before deploying!"; \
			exit 1; \
		fi; \
	done
	@echo "✅ .env.prod validation passed"

# ── Clean ──────────────────────────────────────────────────────
clean: ## Remove all containers, volumes, and images
	@echo "🧹 Cleaning up..."
	$(COMPOSE_DEV) down -v --rmi local 2>/dev/null || true
	$(COMPOSE_PROD) down -v --rmi local 2>/dev/null || true
	@echo "✅ Clean complete"

# ── Setup (First Time) ────────────────────────────────────────
setup: ## First-time setup: copy .env, build, and start
	@if [ ! -f .env ]; then \
		echo "📝 Creating .env from .env.example..."; \
		cp .env.example .env; \
		echo "⚠️  Edit .env with your API keys before starting!"; \
	else \
		echo "✅ .env already exists"; \
	fi
	@echo "🔨 Building Docker images..."
	$(COMPOSE_DEV) build
	@echo "🚀 Starting development stack..."
	$(COMPOSE_DEV) up -d
	@echo ""
	@echo "═══════════════════════════════════════════"
	@echo " PARWA is running!"
	@echo "═══════════════════════════════════════════"
	@echo " Frontend:  http://localhost:3000"
	@echo " Backend:   http://localhost:8000"
	@echo " API Docs:  http://localhost:8000/docs"
	@echo ""
	@echo " Run 'make health' to check service status"
	@echo " Run 'make logs' to view logs"
	@echo "═══════════════════════════════════════════"

# ── Help ───────────────────────────────────────────────────────
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
