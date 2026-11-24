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

# The custom shell entrypoint must not bypass the official image's privilege drop.
USER redis

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD REDISCLI_AUTH="${REDIS_PASSWORD:-}" redis-cli ping 2>/dev/null | grep -q PONG || exit 1

# Expose Redis port
EXPOSE 6379

# The startup script writes the password to a mode-0600 config file so it
# never appears in the Redis process arguments.
COPY infra/docker/redis-entrypoint.sh /usr/local/bin/redis-entrypoint.sh
RUN chmod 755 /usr/local/bin/redis-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/redis-entrypoint.sh"]
