# ════════════════════════════════════════════════════════════════
# PARWA — Background Worker Dockerfile (Redis Streams Consumer)
# Base Image: Python 3.11 Slim
# ════════════════════════════════════════════════════════════════

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app/

# Run the background worker loop
CMD ["python", "-m", "backend.worker.main"]
