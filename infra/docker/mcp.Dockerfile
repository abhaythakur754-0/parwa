# ════════════════════════════════════════════════════════════════
# PARWA — MCP Server Production Dockerfile
# Multi-stage build for minimal image size (<300MB)
#
# Build context is the REPO ROOT:
#   docker build -f infra/docker/mcp.Dockerfile .
# The MCP server delegates to backend modules (app.core.external_tool_bus,
# app.services.voice_channel_service, database.*) so backend/ and its
# requirements are included — same python base as backend/Dockerfile.
# ════════════════════════════════════════════════════════════════

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /install

# Install Python dependencies (shared with the backend)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Production - Minimal runtime image
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS production

# Labels for image metadata
LABEL maintainer="PARWA Team"
LABEL version="1.0.0"
LABEL description="PARWA MCP Server - Production"

# Set environment variables
# /app/backend on PYTHONPATH so `app.*` and `database.*` imports resolve
# (mcp_server/integrations/external_tool_bus.py and voice_server.py import them)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app:/app/backend \
    PATH="/usr/local/bin:$PATH"

# Install only runtime dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r parwa && useradd -r -g parwa parwa

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Set working directory
WORKDIR /app

# Copy the MCP server and the backend modules it delegates to
COPY --chown=parwa:parwa mcp_server/ ./mcp_server/
COPY --chown=parwa:parwa backend/ ./backend/

# Switch to non-root user
USER parwa

# Expose MCP server port
EXPOSE 8080

# Health check for MCP server
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the MCP server
CMD ["python", "-m", "mcp_server.main"]
