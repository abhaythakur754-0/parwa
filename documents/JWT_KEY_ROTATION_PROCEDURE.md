# PARWA — JWT Key Rotation Procedure

## Overview

PARWA uses HMAC-SHA256 (HS256) symmetric JWT signing. The signing key is configured via the `JWT_SECRET_KEY` environment variable. When a key compromise is suspected (leak, employee departure, security incident), the key must be rotated immediately.

## Mechanism (Implemented in `backend/app/core/auth.py`)

PARWA supports **seamless key rotation** via the `JWT_PREVIOUS_KEYS` environment variable:

- **Current key** (`JWT_SECRET_KEY`): Used to sign all new tokens.
- **Previous keys** (`JWT_PREVIOUS_KEYS`): JSON array of old signing keys. Tokens signed with any previous key will still verify successfully until they naturally expire (15 minutes for access tokens, 7 days for refresh tokens).
- New tokens are **always** signed with the current `JWT_SECRET_KEY`.

## Rotation Steps

### 1. Generate a New Key

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2. Update Environment Variables

Add the **current** key to the previous keys list, then set the new key:

```bash
# Example: current key is KEY_OLD, new key is KEY_NEW
export JWT_PREVIOUS_KEYS='["KEY_OLD"]'
export JWT_SECRET_KEY='KEY_NEW'
```

### 3. Deploy

Deploy the updated environment to all backend instances. Since `JWT_PREVIOUS_KEYS` accepts the old key, all existing tokens remain valid during the rolling deployment.

### 4. Wait for Token Expiry

- Access tokens expire in 15 minutes (configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`).
- Refresh tokens expire in 7 days.
- After the maximum refresh token lifetime (7 days), remove the old key from `JWT_PREVIOUS_KEYS`.

### 5. Clean Up Previous Keys

```bash
# After 7 days, remove old keys
export JWT_PREVIOUS_KEYS='[]'
```

## Emergency Rotation (Suspected Compromise)

If a key compromise is confirmed:

1. Rotate the key immediately (steps 1-2 above).
2. **Optionally invalidate all sessions** by clearing the refresh token store or by rotating the `REFRESH_TOKEN_PEPPER` (this forces all users to re-authenticate).
3. Notify the security team and document the incident.

## Verification

After rotation, verify:

```bash
# Check that the current key is active
curl -s http://localhost:8000/health | python3 -m json.tool

# Verify previous keys are loaded (ops endpoint)
curl -s http://localhost:8000/api/auth/debug/jwt-keys  # if available
```

## Configuration Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET_KEY` | Yes | Current HMAC signing key (min 32 chars) |
| `JWT_PREVIOUS_KEYS` | No | JSON array of previous signing keys for rotation |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No (default: 15) | Access token lifetime |
| `REFRESH_TOKEN_PEPPER` | Yes (production) | Pepper for refresh token hashing |

## Security Notes

- Never commit JWT secrets to version control.
- Use a secrets manager (AWS Secrets Manager, HashiCorp Vault) in production.
- Rotate keys at least every 90 days as a security best practice.
- The `jti` (JWT ID) claim on each token enables individual token blacklisting via Redis.
