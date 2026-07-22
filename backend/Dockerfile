# ── Stage 1: Builder ──
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies (including Rust for parwa_core PyO3 module)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain for parwa_core build
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && . "$HOME/.cargo/env" && rustc --version

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 1b: Rust extension builder ──
FROM builder AS rust_builder
COPY parwa_core/ /app/parwa_core/
RUN . "$HOME/.cargo/env" \
    && cd /app/parwa_core \
    && python -m venv /tmp/buildvenv \
    && . /tmp/buildvenv/bin/activate \
    && pip install --no-cache-dir maturin \
    && maturin develop --release \
    && mkdir -p /app/rust_artifacts \
    && cp /tmp/buildvenv/lib/python3.12/site-packages/parwa_core/parwa_core*.so /app/rust_artifacts/

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

# Copy application code (from backend/ context)
COPY . .

# Copy Rust .so and set up proper Python package structure
# The __init__.py lives at parwa_core/python/parwa_core/__init__.py (maturin layout)
# but Python needs it at parwa_core/__init__.py since PYTHONPATH=/app
COPY --from=rust_builder /app/rust_artifacts/ /app/parwa_core/
RUN cp /app/parwa_core/python/parwa_core/__init__.py /app/parwa_core/__init__.py

# Create non-root user
RUN groupadd -r parwa && useradd -r -g parwa parwa
RUN mkdir -p /app/storage && chown -R parwa:parwa /app/storage

# Set PYTHONPATH so `app.main` resolves correctly
ENV PYTHONPATH=/app

USER parwa

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Single worker: avoids lifespan/middleware crashes with multiple workers
# Render free tier has 1 CPU, so 1 worker is appropriate
# Use PORT env var from Render (defaults to 8000)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}