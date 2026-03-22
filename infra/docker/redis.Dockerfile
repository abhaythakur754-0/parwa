# ════════════════════════════════════════════════════════════════
# PARWA — Redis Production Configuration
# Based on official Redis image with custom config
# Target: <50MB
# ════════════════════════════════════════════════════════════════

FROM redis:7-alpine AS production

# Labels for image metadata
LABEL maintainer="PARWA Team"
LABEL version="1.0.0"
LABEL description="PARWA Redis Cache - Production"

# Copy custom Redis configuration
COPY infra/docker/redis.conf /usr/local/etc/redis/redis.conf

# Create data directory with proper permissions
RUN mkdir -p /data && chown redis:redis /data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD redis-cli ping | grep -q PONG || exit 1

# Expose Redis port
EXPOSE 6379

# Run with custom config
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
