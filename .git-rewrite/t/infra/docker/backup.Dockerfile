# ────────────────────────────────────────────────────────────────────────
# PARWA Automated Backup Container (DEPLOY-01)
# Week 8 — Production Deployment
#
# Alpine-based container that runs pg_dump every 6 hours, keeps the last
# 7 backups (rotation), and exposes a health check endpoint.
#
# Build:
#   docker build -t parwa-backup -f backup.Dockerfile .
#
# Run (via docker-compose.prod.yml):
#   services:
#     backup:
#       build:
#         context: .
#         dockerfile: infra/docker/backup.Dockerfile
#       environment:
#         DATABASE_URL: postgresql://parwa:secret@postgres:5432/parwa
#         BACKUP_RETENTION_COUNT: "7"
#       volumes:
#         - backups:/backups
#       healthcheck:
#         test: ["CMD", "/usr/local/bin/healthcheck.sh"]
#         interval: 30m
#         timeout: 10s
#         retries: 3
# ────────────────────────────────────────────────────────────────────────
FROM alpine:3.19

LABEL maintainer="PARWA DevOps <devops@parwa.ai>"
LABEL description="Automated PostgreSQL backup with rotation"
LABEL version="1.0.0"

# Install postgresql-client and cron
RUN apk add --no-cache \
    postgresql16-client \
    curl \
    tzdata \
    && cp /usr/share/zoneinfo/UTC /etc/localtime \
    && echo "UTC" > /etc/timezone \
    && apk del tzdata

# Create backup directory and entrypoint
RUN mkdir -p /backups /usr/local/bin

# Copy scripts
COPY scripts/backup_entrypoint.sh /usr/local/bin/backup_entrypoint.sh
COPY infra/docker/healthcheck.sh /usr/local/bin/healthcheck.sh

# Make scripts executable
RUN chmod +x /usr/local/bin/backup_entrypoint.sh /usr/local/bin/healthcheck.sh

# Create crontab for backups every 6 hours (00:00, 06:00, 12:00, 18:00)
RUN echo "0 */6 * * * /usr/local/bin/run_backup.sh >> /var/log/backup.log 2>&1" \
    > /etc/crontabs/root

# Copy the single-backup runner script
COPY infra/docker/run_backup.sh /usr/local/bin/run_backup.sh
RUN chmod +x /usr/local/bin/run_backup.sh

# Volumes
VOLUME ["/backups"]

# Health check — verify last backup is less than 7 hours old
HEALTHCHECK --interval=30m --timeout=10s --retries=3 --start-period=5m \
    CMD /usr/local/bin/healthcheck.sh

# Entrypoint
ENTRYPOINT ["/usr/local/bin/backup_entrypoint.sh"]
