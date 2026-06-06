#!/bin/bash
# ════════════════════════════════════════════════════════════════
# PARWA — Production Environment Validator
# Validates .env.prod before deployment to catch missing/placeholder values
# ════════════════════════════════════════════════════════════════

set -euo pipefail

ENV_FILE="${1:-.env.prod}"
ERRORS=0
WARNINGS=0

echo "═══════════════════════════════════════════"
echo " PARWA — Environment Validator"
echo " File: ${ENV_FILE}"
echo "═══════════════════════════════════════════"
echo ""

# ── Check file exists ──
if [ ! -f "${ENV_FILE}" ]; then
  echo "❌ FATAL: ${ENV_FILE} not found!"
  echo "   Copy .env.prod.example and fill in real values:"
  echo "   cp .env.prod.example ${ENV_FILE}"
  exit 1
fi

echo "✅ File exists"
echo ""

# ── Required variables (must be set, no placeholders) ──
REQUIRED_VARS=(
  "SECRET_KEY"
  "POSTGRES_USER"
  "POSTGRES_PASSWORD"
  "POSTGRES_DB"
  "REDIS_PASSWORD"
  "JWT_SECRET_KEY"
  "DATA_ENCRYPTION_KEY"
)

echo "── Required Variables ──"
for var in "${REQUIRED_VARS[@]}"; do
  value=$(grep -E "^${var}=" "${ENV_FILE}" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'")
  if [ -z "${value}" ]; then
    echo "  ❌ ${var} — MISSING"
    ERRORS=$((ERRORS + 1))
  elif echo "${value}" | grep -qi "CHANGE_ME\|your_.*_here\|placeholder\|xxx\|example"; then
    echo "  ❌ ${var} — PLACEHOLDER VALUE (must be changed)"
    ERRORS=$((ERRORS + 1))
  elif [ "${var}" = "SECRET_KEY" ] && [ "${#value}" -lt 32 ]; then
    echo "  ⚠️  ${var} — TOO SHORT (min 32 chars, got ${#value})"
    WARNINGS=$((WARNINGS + 1))
  elif [ "${var}" = "JWT_SECRET_KEY" ] && [ "${#value}" -lt 32 ]; then
    echo "  ⚠️  ${var} — TOO SHORT (min 32 chars, got ${#value})"
    WARNINGS=$((WARNINGS + 1))
  elif [ "${var}" = "DATA_ENCRYPTION_KEY" ] && [ "${#value}" -lt 32 ]; then
    echo "  ⚠️  ${var} — TOO SHORT (min 32 chars, got ${#value})"
    WARNINGS=$((WARNINGS + 1))
  else
    echo "  ✅ ${var} — set (${#value} chars)"
  fi
done
echo ""

# ── Recommended variables (should be set for production) ──
RECOMMENDED_VARS=(
  "GOOGLE_AI_API_KEY"
  "CORS_ORIGINS"
  "NEXT_PUBLIC_API_URL"
)

echo "── Recommended Variables ──"
for var in "${RECOMMENDED_VARS[@]}"; do
  value=$(grep -E "^${var}=" "${ENV_FILE}" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'")
  if [ -z "${value}" ] || echo "${value}" | grep -qi "your_.*_here\|placeholder"; then
    echo "  ⚠️  ${var} — NOT SET (recommended for production)"
    WARNINGS=$((WARNINGS + 1))
  else
    echo "  ✅ ${var} — set"
  fi
done
echo ""

# ── Optional service variables ──
OPTIONAL_VARS=(
  "PADDLE_CLIENT_TOKEN"
  "PADDLE_API_KEY"
  "PADDLE_WEBHOOK_SECRET"
  "TWILIO_ACCOUNT_SID"
  "TWILIO_AUTH_TOKEN"
  "BREVO_API_KEY"
  "SENTRY_DSN"
  "GOOGLE_CLIENT_ID"
  "GOOGLE_CLIENT_SECRET"
)

echo "── Optional Service Variables ──"
for var in "${OPTIONAL_VARS[@]}"; do
  value=$(grep -E "^${var}=" "${ENV_FILE}" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'")
  if [ -z "${value}" ] || echo "${value}" | grep -qi "your_.*_here\|placeholder"; then
    echo "  ⚪ ${var} — not configured"
  else
    echo "  ✅ ${var} — configured"
  fi
done
echo ""

# ── Security checks ──
echo "── Security Checks ──"

# Check ENVIRONMENT is production
env_val=$(grep -E "^ENVIRONMENT=" "${ENV_FILE}" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'")
if [ "${env_val}" != "production" ]; then
  echo "  ⚠️  ENVIRONMENT is '${env_val}' (should be 'production')"
  WARNINGS=$((WARNINGS + 1))
else
  echo "  ✅ ENVIRONMENT=production"
fi

# Check DEBUG is false
debug_val=$(grep -E "^DEBUG=" "${ENV_FILE}" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'")
if [ "${debug_val}" = "true" ]; then
  echo "  ❌ DEBUG=true (MUST be false in production)"
  ERRORS=$((ERRORS + 1))
else
  echo "  ✅ DEBUG=${debug_val}"
fi

# Check passwords are not default
pg_pass=$(grep -E "^POSTGRES_PASSWORD=" "${ENV_FILE}" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'")
if [ "${pg_pass}" = "parwa_dev" ] || [ "${pg_pass}" = "parwa" ]; then
  echo "  ❌ POSTGRES_PASSWORD is a default/dev value"
  ERRORS=$((ERRORS + 1))
else
  echo "  ✅ POSTGRES_PASSWORD is not default"
fi

echo ""

# ── Summary ──
echo "═══════════════════════════════════════════"
echo " RESULTS: ${ERRORS} errors, ${WARNINGS} warnings"
echo "═══════════════════════════════════════════"

if [ ${ERRORS} -gt 0 ]; then
  echo ""
  echo "❌ VALIDATION FAILED — Fix the errors above before deploying!"
  exit 1
elif [ ${WARNINGS} -gt 0 ]; then
  echo ""
  echo "⚠️  Validation passed with warnings. Review above."
  exit 0
else
  echo ""
  echo "✅ All checks passed! Ready for production deployment."
  exit 0
fi
