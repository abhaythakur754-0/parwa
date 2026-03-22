# ════════════════════════════════════════════════════════════════
# PARWA — Background Worker Production Dockerfile
# Multi-stage build for minimal image size (<300MB)
# ════════════════════════════════════════════════════════════════

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

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

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Production - Minimal runtime image
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS production

# Labels for image metadata
LABEL maintainer="PARWA Team"
LABEL version="1.0.0"
LABEL description="PARWA Background Worker - Production"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# Install only runtime dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r parwa && useradd -r -g parwa parwa

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy only required source code (worker-specific)
COPY --chown=parwa:parwa backend/ ./backend/
COPY --chown=parwa:parwa shared/ ./shared/
COPY --chown=parwa:parwa variants/ ./variants/
COPY --chown=parwa:parwa database/ ./database/

# Switch to non-root user
USER parwa

# Health check for worker process
HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD pgrep -f "backend.worker" > /dev/null || exit 1

# Run the background worker
CMD ["python", "-m", "backend.worker.main"]
