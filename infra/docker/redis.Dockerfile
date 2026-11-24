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

# Copy configuration and startup script before dropping privileges.
COPY infra/docker/redis.conf /usr/local/etc/redis/redis.conf
COPY infra/docker/redis-entrypoint.sh /usr/local/bin/redis-entrypoint.sh

# Prepare writable paths and executable entrypoint as root.
RUN mkdir -p /data && chown redis:redis /data && chmod 755 /usr/local/bin/redis-entrypoint.sh

# Redis and its entrypoint run unprivileged.
USER redis

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD REDISCLI_AUTH="${REDIS_PASSWORD:-}" redis-cli ping 2>/dev/null | grep -q PONG || exit 1

EXPOSE 6379

ENTRYPOINT ["/usr/local/bin/redis-entrypoint.sh"]
