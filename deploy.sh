#!/bin/bash
# ════════════════════════════════════════════════════════════════
# PARWA — One-Click Deploy Script
# ════════════════════════════════════════════════════════════════
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh          ← Start everything (dev mode)
#   ./deploy.sh prod     ← Start production mode
#   ./deploy.sh stop     ← Stop everything
#   ./deploy.sh logs     ← View logs
#   ./deploy.sh clean    ← Remove all containers + volumes
# ════════════════════════════════════════════════════════════════

set -e

COMPOSE_FILE="docker-compose.yml"
COMPOSE_CMD="docker compose"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_banner() {
    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║           PARWA — AI Customer Support          ║"
    echo "║              Docker Deployment                  ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}ERROR: Docker is not installed!${NC}"
        echo "Install Docker first: https://docs.docker.com/get-docker/"
        exit 1
    fi
    if ! docker compose version &> /dev/null; then
        echo -e "${YELLOW}WARNING: docker compose v2 not found, trying docker-compose v1${NC}"
        COMPOSE_CMD="docker-compose"
    fi
}

check_env() {
    if [ ! -f .env ]; then
        echo -e "${RED}ERROR: .env file not found!${NC}"
        echo ""
        echo "Create it by copying the example:"
        echo "  cp .env.example .env"
        echo ""
        echo "Then fill in your API keys (minimum required):"
        echo "  - SECRET_KEY (any random 32+ chars)"
        echo "  - JWT_SECRET_KEY (any random 32+ chars)"
        echo "  - DATA_ENCRYPTION_KEY (EXACTLY 32 characters)"
        echo "  - GOOGLE_AI_API_KEY (for Jarvis AI to work)"
        echo ""
        exit 1
    fi
}

do_start() {
    print_banner
    check_docker
    check_env

    echo -e "${GREEN}Starting PARWA services...${NC}"
    echo ""

    $COMPOSE_CMD -f $COMPOSE_FILE build --parallel
    echo ""
    $COMPOSE_CMD -f $COMPOSE_FILE up -d

    echo ""
    echo -e "${GREEN}✅ PARWA is running!${NC}"
    echo ""
    echo "┌────────────────────────────────────────────────────┐"
    echo "│  Frontend:  http://localhost:3000                 │"
    echo "│  Backend:   http://localhost:8000                 │"
    echo "│  API Docs:  http://localhost:8000/docs            │"
    echo "│  Database:  localhost:5432                        │"
    echo "│  Redis:     localhost:6379                        │"
    echo "└────────────────────────────────────────────────────┘"
    echo ""
    echo "View logs:   ./deploy.sh logs"
    echo "Stop:        ./deploy.sh stop"
}

do_start_prod() {
    print_banner
    check_docker

    if [ ! -f .env.prod ]; then
        echo -e "${RED}ERROR: .env.prod file not found!${NC}"
        echo ""
        echo "Create it and fill in ALL values:"
        echo "  cp .env.example .env.prod"
        echo ""
        echo "Required values (will crash without):"
        echo "  - SECRET_KEY, JWT_SECRET_KEY, DATA_ENCRYPTION_KEY"
        echo "  - POSTGRES_PASSWORD, REDIS_PASSWORD"
        echo "  - GOOGLE_AI_API_KEY (or CEREBRAS_API_KEY / GROQ_API_KEY)"
        echo ""
        exit 1
    fi

    echo -e "${GREEN}Starting PARWA in PRODUCTION mode...${NC}"
    echo ""

    $COMPOSE_CMD -f docker-compose.prod.yml build --parallel
    echo ""
    $COMPOSE_CMD -f docker-compose.prod.yml up -d

    echo ""
    echo -e "${GREEN}✅ PARWA is running in PRODUCTION!${NC}"
    echo ""
    echo "┌────────────────────────────────────────────────────┐"
    echo "│  Frontend:  http://localhost:3000                 │"
    echo "│  Nginx:     http://localhost:80                   │"
    echo "└────────────────────────────────────────────────────┘"
}

do_stop() {
    echo -e "${YELLOW}Stopping PARWA...${NC}"
    $COMPOSE_CMD -f $COMPOSE_FILE down
    echo -e "${GREEN}Stopped.${NC}"
}

do_logs() {
    $COMPOSE_CMD -f $COMPOSE_FILE logs -f --tail=100
}

do_clean() {
    echo -e "${RED}⚠️  This will DELETE all containers, volumes, and data!${NC}"
    read -p "Are you sure? (type 'yes' to confirm): " confirm
    if [ "$confirm" = "yes" ]; then
        $COMPOSE_CMD -f $COMPOSE_FILE down -v --rmi all
        echo -e "${GREEN}Cleaned.${NC}"
    else
        echo "Cancelled."
    fi
}

# Main
case "${1:-start}" in
    start)
        do_start
        ;;
    prod)
        do_start_prod
        ;;
    stop)
        do_stop
        ;;
    logs)
        do_logs
        ;;
    clean)
        do_clean
        ;;
    *)
        echo "Usage: $0 {start|prod|stop|logs|clean}"
        exit 1
        ;;
esac
