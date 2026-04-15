# ════════════════════════════════════════════════════════════════
# PARWA — PostgreSQL Production Dockerfile
# Based on official PostgreSQL image with custom config
# Target: <200MB
# ════════════════════════════════════════════════════════════════

FROM postgres:15-alpine AS production

# Labels for image metadata
LABEL maintainer="PARWA Team"
LABEL version="1.0.0"
LABEL description="PARWA PostgreSQL Database - Production"

# Set environment defaults
ENV POSTGRES_DB=parwa \
    POSTGRES_USER=parwa \
    PGDATA=/var/lib/postgresql/data/pgdata

# Copy initialization scripts
COPY database/seeds/*.sql /docker-entrypoint-initdb.d/

# Copy custom PostgreSQL configuration
COPY infra/docker/postgresql.conf /etc/postgresql/postgresql.conf
COPY infra/docker/pg_hba.conf /etc/postgresql/pg_hba.conf

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pg_isready -U $POSTGRES_USER -d $POSTGRES_DB || exit 1

# Expose PostgreSQL port
EXPOSE 5432

# Run with custom config
CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
