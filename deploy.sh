#!/bin/bash
# ════════════════════════════════════════════════════════════════
# PARWA — One-Click Deploy Script
# ════════════════════════════════════════════════════════════════
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh              ← Start everything (dev mode)
#   ./deploy.sh prod         ← Start production mode
#   ./deploy.sh build        ← Build images only (no deploy)
#   ./deploy.sh build prod   ← Build production images only
#   ./deploy.sh deploy       ← Deploy already-built images (dev)
#   ./deploy.sh deploy prod  ← Deploy already-built images (prod)
#   ./deploy.sh rollback     ← Rollback to previous deployment
#   ./deploy.sh stop         ← Stop everything
#   ./deploy.sh stop prod    ← Stop production stack
#   ./deploy.sh logs         ← View logs
#   ./deploy.sh logs prod    ← View production logs
#   ./deploy.sh clean        ← Remove all containers + volumes
#   ./deploy.sh health       ← Run post-deploy health checks
#
# Zero-downtime deployment:
#   For rolling updates without downtime, deploy with replicas > 1
#   in docker-compose.prod.yml. Docker Swarm / K8s will drain old
#   containers as new ones become healthy. This script saves image
#   tags before each deploy to enable instant rollback.
# ════════════════════════════════════════════════════════════════

set -euo pipefail                       # #198: upgraded from set -e

COMPOSE_FILE_DEV="docker-compose.yml"
COMPOSE_FILE_PROD="docker-compose.prod.yml"
COMPOSE_FILE="${COMPOSE_FILE_DEV}"
COMPOSE_CMD="docker compose"
MODE="dev"

# #197: Rollback file — stores previous image tags before each deploy
ROLLBACK_FILE="/tmp/parwa_previous_images.txt"

# #200: Git SHA for image tagging
get_git_sha() {
    if git rev-parse --short HEAD &>/dev/null; then
        echo "$(git rev-parse --short HEAD)"
    else
        echo "unknown"
    fi
}

# #197: Save currently running image tags for rollback
save_current_images() {
    local compose_file="${1:-${COMPOSE_FILE_DEV}}"
    echo -e "${YELLOW}Saving current image tags for rollback...${NC}"
    "${COMPOSE_CMD}" -f "${compose_file}" images 2>/dev/null | awk 'NR>1 {print $1 ":" $2}' > "${ROLLBACK_FILE}" || true
    if [ -s "${ROLLBACK_FILE}" ]; then
        echo -e "${GREEN}Saved to ${ROLLBACK_FILE}${NC}"
    else
        echo -e "${YELLOW}No previous images found (first deploy?)${NC}"
    fi
}

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
    local env_file="${1:-.env}"
    if [ ! -f "${env_file}" ]; then
        echo -e "${RED}ERROR: ${env_file} file not found!${NC}"
        echo ""
        echo "Create it by copying the example:"
        echo "  cp .env.example ${env_file}"
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

# #196: Post-deploy health check
health_check() {
    echo -e "${GREEN}Running post-deploy health checks...${NC}"
    local failures=0
    local compose_file="${1:-${COMPOSE_FILE_DEV}}"

    # Wait for services to start
    echo "Waiting 10 seconds for services to initialize..."
    sleep 10

    # Check backend
    if curl -sf -o /dev/null --max-time 5 http://localhost:8000/health 2>/dev/null; then
        echo -e "  ${GREEN}Backend: OK${NC}"
    else
        echo -e "  ${RED}Backend: FAILED${NC}"
        failures=$((failures + 1))
    fi

    # Check frontend
    if curl -sf -o /dev/null --max-time 5 http://localhost:3000 2>/dev/null; then
        echo -e "  ${GREEN}Frontend: OK${NC}"
    else
        echo -e "  ${RED}Frontend: FAILED${NC}"
        failures=$((failures + 1))
    fi

    if [[ ${failures} -gt 0 ]]; then
        echo -e "${RED}${failures} health check(s) FAILED!${NC}"
        echo "Check logs: ${COMPOSE_CMD} -f ${compose_file} logs"
        return 1
    else
        echo -e "${GREEN}All health checks passed!${NC}"
        return 0
    fi
}

do_start() {
    print_banner
    check_docker
    check_env ".env"
    MODE="dev"

    echo -e "${GREEN}Starting PARWA services...${NC}"
    echo ""

    "${COMPOSE_CMD}" -f "${COMPOSE_FILE_DEV}" build --parallel
    echo ""
    "${COMPOSE_CMD}" -f "${COMPOSE_FILE_DEV}" up -d

    # #196: Run health check after deployment
    health_check "${COMPOSE_FILE_DEV}" || true

    echo ""
    echo -e "${GREEN}PARWA is running!${NC}"
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
    check_env ".env.prod"
    MODE="prod"

    echo -e "${GREEN}Starting PARWA in PRODUCTION mode...${NC}"
    echo ""

    "${COMPOSE_CMD}" -f "${COMPOSE_FILE_PROD}" build --parallel
    echo ""
    "${COMPOSE_CMD}" -f "${COMPOSE_FILE_PROD}" up -d

    # #196: Run health check after deployment
    health_check "${COMPOSE_FILE_PROD}" || true

    echo ""
    echo -e "${GREEN}PARWA is running in PRODUCTION!${NC}"
    echo ""
    echo "┌────────────────────────────────────────────────────┐"
    echo "│  Frontend:  http://localhost:3000                 │"
    echo "│  Nginx:     http://localhost:80                   │"
    echo "└────────────────────────────────────────────────────┘"
}

# #195: Fixed stop/logs/clean to support production compose file
do_stop() {
    local file="${COMPOSE_FILE_DEV}"
    if [[ "${2:-}" == "prod" ]] || [[ "${MODE}" == "prod" ]]; then
        file="${COMPOSE_FILE_PROD}"
    fi
    echo -e "${YELLOW}Stopping PARWA...${NC}"
    "${COMPOSE_CMD}" -f "${file}" down
    echo -e "${GREEN}Stopped.${NC}"
}

do_logs() {
    local file="${COMPOSE_FILE_DEV}"
    if [[ "${2:-}" == "prod" ]] || [[ "${MODE}" == "prod" ]]; then
        file="${COMPOSE_FILE_PROD}"
    fi
    "${COMPOSE_CMD}" -f "${file}" logs -f --tail=100
}

do_clean() {
    local file="${COMPOSE_FILE_DEV}"
    if [[ "${2:-}" == "prod" ]] || [[ "${MODE}" == "prod" ]]; then
        file="${COMPOSE_FILE_PROD}"
    fi
    echo -e "${RED}This will DELETE all containers, volumes, and data!${NC}"
    read -p "Are you sure? (type 'yes' to confirm): " confirm
    if [ "${confirm}" = "yes" ]; then
        "${COMPOSE_CMD}" -f "${file}" down -v --rmi all
        echo -e "${GREEN}Cleaned.${NC}"
    else
        echo "Cancelled."
    fi
}

# #200: Build images only (no deploy) — separates build from deploy step
do_build() {
    print_banner
    check_docker

    local file="${COMPOSE_FILE_DEV}"
    local env_file=".env"
    if [[ "${2:-}" == "prod" ]]; then
        file="${COMPOSE_FILE_PROD}"
        env_file=".env.prod"
        MODE="prod"
    fi
    check_env "${env_file}"

    local git_sha
    git_sha="$(get_git_sha)"

    echo -e "${GREEN}Building PARWA images...${NC}"
    echo -e "  Git SHA: ${git_sha}"
    echo ""

    # Build images with both :latest and :<git-sha> tags
    VERSION="${git_sha}" "${COMPOSE_CMD}" -f "${file}" build --parallel
    echo ""

    # Also tag with :latest for convenience
    echo -e "${YELLOW}Tagging images with :latest...${NC}"
    for img in parwa/backend parwa/worker parwa/mcp parwa/frontend; do
        if docker image inspect "${img}:${git_sha}" &>/dev/null; then
            docker tag "${img}:${git_sha}" "${img}:latest" 2>/dev/null || true
        fi
    done

    echo ""
    echo -e "${GREEN}Build complete!${NC}"
    echo "  Images tagged: :${git_sha} and :latest"
    echo ""
    echo "Deploy with: ./deploy.sh deploy${MODE:+ $MODE}"
}

# #200: Deploy already-built images only (no build)
do_deploy() {
    print_banner
    check_docker

    local file="${COMPOSE_FILE_DEV}"
    local env_file=".env"
    if [[ "${2:-}" == "prod" ]]; then
        file="${COMPOSE_FILE_PROD}"
        env_file=".env.prod"
        MODE="prod"
    fi
    check_env "${env_file}"

    # #197: Save current images before deploying (for rollback)
    save_current_images "${file}"

    echo -e "${GREEN}Deploying PARWA services...${NC}"
    echo ""

    # #199: Zero-downtime — use --no-build to deploy pre-built images only
    "${COMPOSE_CMD}" -f "${file}" up -d --no-build

    # Run health check after deployment
    health_check "${file}" || true

    echo ""
    echo -e "${GREEN}PARWA deployed!${NC}"
    echo ""
    echo "Rollback:  ./deploy.sh rollback${MODE:+ $MODE}"
}

# #197: Rollback to previous image deployment
do_rollback() {
    print_banner
    check_docker

    local file="${COMPOSE_FILE_DEV}"
    if [[ "${2:-}" == "prod" ]] || [[ "${MODE}" == "prod" ]]; then
        file="${COMPOSE_FILE_PROD}"
    fi

    if [ ! -f "${ROLLBACK_FILE}" ]; then
        echo -e "${RED}ERROR: No rollback data found at ${ROLLBACK_FILE}${NC}"
        echo "This means no previous deployment was recorded. Cannot rollback."
        exit 1
    fi

    if [ ! -s "${ROLLBACK_FILE}" ]; then
        echo -e "${RED}ERROR: Rollback file is empty at ${ROLLBACK_FILE}${NC}"
        echo "No previous image tags recorded. Cannot rollback."
        exit 1
    fi

    echo -e "${RED}ROLLBACK: Reverting to previous images...${NC}"
    echo ""
    echo "Previous images:"
    while IFS= read -r img; do
        echo "  - ${img}"
    done < "${ROLLBACK_FILE}"
    echo ""

    read -p "Confirm rollback? (type 'yes' to confirm): " confirm
    if [ "${confirm}" != "yes" ]; then
        echo "Rollback cancelled."
        return 0
    fi

    # Re-tag previous images and restart
    while IFS= read -r img; do
        local name="${img%%:*}"
        local tag="${img##*:}"
        if docker image inspect "${img}" &>/dev/null; then
            echo -e "  ${GREEN}Re-tagging ${img} → ${name}:latest${NC}"
            docker tag "${img}" "${name}:latest" 2>/dev/null || true
        else
            echo -e "  ${YELLOW}WARNING: Image ${img} not found locally, skipping${NC}"
        fi
    done < "${ROLLBACK_FILE}"

    echo ""
    echo -e "${GREEN}Restarting with previous images...${NC}"
    "${COMPOSE_CMD}" -f "${file}" up -d --no-build

    # Run health check after rollback
    health_check "${file}" || true

    echo ""
    echo -e "${GREEN}Rollback complete!${NC}"
}

# Main
case "${1:-start}" in
    start)
        do_start "$@"
        ;;
    prod)
        do_start_prod "$@"
        ;;
    build)
        do_build "$@"
        ;;
    deploy)
        do_deploy "$@"
        ;;
    rollback)
        do_rollback "$@"
        ;;
    stop)
        do_stop "$@"
        ;;
    logs)
        do_logs "$@"
        ;;
    clean)
        do_clean "$@"
        ;;
    health)
        health_check "${2:-${COMPOSE_FILE_DEV}}"
        ;;
    *)
        echo "Usage: $0 {start|prod|build [prod]|deploy [prod]|rollback [prod]|stop [prod]|logs [prod]|clean [prod]|health}"
        exit 1
        ;;
esac
