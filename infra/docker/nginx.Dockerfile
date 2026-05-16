# ════════════════════════════════════════════════════════════════
# PARWA — Nginx Production Dockerfile
# Reverse proxy for frontend and backend services
# Target: <50MB production image
# ════════════════════════════════════════════════════════════════

FROM nginx:1.25-alpine AS production

# Labels for image metadata
LABEL maintainer="PARWA Team"
LABEL version="1.0.0"
LABEL description="PARWA Nginx Reverse Proxy - Production"

# Install ca-certificates for TLS connections
RUN apk add --no-cache ca-certificates

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration
COPY infra/docker/nginx.conf /etc/nginx/nginx.conf
COPY infra/docker/nginx-default.conf /etc/nginx/conf.d/default.conf

# Copy SSL certificates (mounted in production) and generate DH params
RUN mkdir -p /etc/nginx/ssl && \
    openssl dhparam -out /etc/nginx/ssl/dhparam.pem 2048 && \
    chown -R nginx:nginx /etc/nginx/ssl

# Create log directories
RUN mkdir -p /var/log/nginx && \
    chown -R nginx:nginx /var/log/nginx

# Run as non-root nginx user
USER nginx

# Health check — verify both HTTP and HTTPS
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || wget --no-verbose --tries=1 --spider --no-check-certificate https://localhost:8443/health || exit 1

# Expose high ports (non-root can't bind 80/443)
EXPOSE 8080 8443

# Run nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
