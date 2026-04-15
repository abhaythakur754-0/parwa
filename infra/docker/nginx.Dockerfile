# ════════════════════════════════════════════════════════════════
# PARWA — Nginx Production Dockerfile
# Reverse proxy for frontend and backend services
# Target: <50MB production image
# ════════════════════════════════════════════════════════════════

FROM nginx:alpine AS production

# Labels for image metadata
LABEL maintainer="PARWA Team"
LABEL version="1.0.0"
LABEL description="PARWA Nginx Reverse Proxy - Production"

# Install curl for health checks
RUN apk add --no-cache curl

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration
COPY infra/docker/nginx.conf /etc/nginx/nginx.conf
COPY infra/docker/nginx-default.conf /etc/nginx/conf.d/default.conf

# Copy SSL certificates (mounted in production)
RUN mkdir -p /etc/nginx/ssl

# Create log directories
RUN mkdir -p /var/log/nginx && \
    chown -R nginx:nginx /var/log/nginx

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Expose ports
EXPOSE 80 443

# Run nginx in foreground as non-root user
USER nginx
CMD ["nginx", "-g", "daemon off;"]
