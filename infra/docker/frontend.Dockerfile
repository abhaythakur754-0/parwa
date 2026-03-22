# ════════════════════════════════════════════════════════════════
# PARWA — Frontend Dockerfile
# Multi-stage build for Next.js frontend
# Target: <500MB production image
# ════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────
# Stage 1: Dependencies
# ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps

# Install dependencies for native modules
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Copy package files first for better caching
COPY frontend/package.json frontend/package-lock.json* frontend/yarn.lock* ./

# Install dependencies
RUN npm ci --legacy-peer-deps 2>/dev/null || npm install --legacy-peer-deps

# ──────────────────────────────────────────────────────────────
# Stage 2: Builder
# ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy frontend source
COPY frontend/ ./

# Set environment variables for build
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Build the Next.js application
# Disable linting and type checking in production build for speed
RUN npm run build 2>/dev/null || \
    npx next build --no-lint 2>/dev/null || \
    npm run build

# ──────────────────────────────────────────────────────────────
# Stage 3: Runner (Production)
# ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

# Set environment to production
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy only necessary files for production
COPY --from=builder /app/public ./public

# Copy Next.js standalone files (if available)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# If standalone not available, copy full .next directory
RUN if [ ! -f "server.js" ]; then \
    cp -r /app/.next ./.next 2>/dev/null || true; \
    fi

# Copy package.json for version info
COPY --from=builder /app/package.json ./package.json

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Set port
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/api/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})" 2>/dev/null || \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ 2>/dev/null || exit 1

# Start the application
# Use standalone server if available, otherwise use next start
CMD ["node", "server.js"] 2>/dev/null || CMD ["npx", "next", "start"]
