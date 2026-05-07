# ════════════════════════════════════════════════════════════════
# PARWA — Frontend Dockerfile (Next.js 16)
# Multi-stage build supporting both dev and production modes
# Context: project root (./)
# ════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────
# Stage 1: Dependencies
# ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps

RUN apk add --no-cache libc6-compat openssl

WORKDIR /app

COPY package.json package-lock.json* bun.lock* ./

RUN npm ci --legacy-peer-deps 2>/dev/null || npm install --legacy-peer-deps

# ──────────────────────────────────────────────────────────────
# Stage 2: Builder
# ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY package.json ./

COPY src/ ./src/
COPY public/ ./public/
COPY next.config.mjs ./
COPY tailwind.config.mts ./
COPY tsconfig.json ./
COPY components.json ./
COPY postcss.config.mjs ./

ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

RUN npm run build

# ──────────────────────────────────────────────────────────────
# Stage 3: Runner (Production)
# ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder /app/package.json ./package.json

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]

# ──────────────────────────────────────────────────────────────
# Stage 3b: Dev Runner (for docker-compose dev mode)
# ──────────────────────────────────────────────────────────────
FROM deps AS dev

WORKDIR /app

# Copy all source for dev hot-reload
COPY . .

ENV NODE_ENV=development

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["npm", "run", "dev"]
