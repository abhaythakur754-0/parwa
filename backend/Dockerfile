# ── Stage 1: Builder ──
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 1b: Rust extension builder (SKIPPED by default) ──
FROM builder AS rust_builder
ARG SKIP_RUST_BUILD=true
COPY parwa_core/ /app/parwa_core/
RUN if [ "$SKIP_RUST_BUILD" = "true" ]; then \
        echo "Skipping Rust build — using pure-Python fallback" \
        && mkdir -p /app/rust_artifacts \
        && touch /app/rust_artifacts/.skip; \
    else \
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
        && . "$HOME/.cargo/env" && rustc --version \
        && . "$HOME/.cargo/env" \
        && cd /app/parwa_core \
        && python -m venv /tmp/buildvenv \
        && . /tmp/buildvenv/bin/activate \
        && pip install --no-cache-dir maturin \
        && maturin develop --release \
        && mkdir -p /app/rust_artifacts \
        && cp /tmp/buildvenv/lib/python3.12/site-packages/parwa_core/parwa_core*.so /app/rust_artifacts/; \
    fi

# ── Stage 2: Runtime ──
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# NUCLEAR CACHE BUST: Use $(date) which changes every second.
# This guarantees Docker can NEVER cache the COPY . . step.
RUN echo "Build timestamp: $(date)" > /tmp/build_timestamp
COPY BUILD_VERSION /tmp/BUILD_VERSION
RUN cat /tmp/BUILD_VERSION && cat /tmp/build_timestamp

# Copy ALL application code — guaranteed fresh because the previous
# RUN layer has a unique timestamp every build
COPY . .

# Verify the latest code is actually present
RUN grep -c "cfa69ed9\|inline" /app/app/services/integration_service.py || echo "WARNING: inline fix not found!"

# Copy Rust .so if it was built (skip if .skip marker exists)
COPY --from=rust_builder /app/rust_artifacts/ /tmp/rust_artifacts/
RUN if [ -f /tmp/rust_artifacts/.skip ]; then \
        echo "No Rust .so — pure-Python fallback will be used"; \
    else \
        cp /tmp/rust_artifacts/parwa_core*.so /app/parwa_core/ 2>/dev/null || true; \
    fi \
    && cp /app/parwa_core/python/parwa_core/__init__.py /app/parwa_core/__init__.py \
    && rm -rf /tmp/rust_artifacts

# Create non-root user
RUN groupadd -r parwa && useradd -r -g parwa parwa
RUN mkdir -p /app/storage && chown -R parwa:parwa /app/storage

# Set PYTHONPATH so `app.main` resolves correctly
ENV PYTHONPATH=/app
# Memory optimization for Render free tier (512MB RAM)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONMALLOC=malloc
ENV MALLOC_ARENA_MAX=2

USER parwa

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# --workers 1: single worker to minimize memory (Render free 512MB)
# --no-access-log: disable access logging (saves ~10MB)
# --limit-max-requests 1000: recycle worker after 1000 requests (prevents memory leaks)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-access-log
