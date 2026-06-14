#!/usr/bin/env python3
"""
L-01 — RS256 Migration Preparation Script

Reads the current JWT configuration from backend/app/config.py and produces:
  1. A .env.rs256.example file with all required RS256 environment variables.
  2. A MIGRATION_NOTES.md documenting the step-by-step HS256 → RS256 migration.

This script is READ-ONLY — it never modifies existing source code.
Run it after generate_rsa_keys.py to bootstrap your RS256 migration.

Usage:
    python scripts/rs256_migration_prep.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "backend" / "app" / "config.py"
ENV_EXAMPLE_OUTPUT = PROJECT_ROOT / ".env.rs256.example"
MIGRATION_NOTES_OUTPUT = PROJECT_ROOT / "scripts" / "RS256_MIGRATION_NOTES.md"


# ---------------------------------------------------------------------------
# Config parser — lightweight, no imports from the app itself
# ---------------------------------------------------------------------------
def parse_jwt_config(config_path: Path) -> dict[str, str]:
    """Extract current JWT-related settings from config.py using regex.

    Returns a dict like:
        {
            "JWT_SECRET_KEY": "dev-jwt-secret-key-change-in-production",
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "15",
            "JWT_REFRESH_TOKEN_EXPIRE_DAYS": "7",
            "MAX_SESSIONS_PER_USER": "5",
        }
    """
    if not config_path.exists():
        print(
            f"WARNING: {config_path} not found — using defaults for migration docs.",
            file=sys.stderr,
        )
        return {
            "JWT_SECRET_KEY": "<your-current-hs256-secret>",
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "15",
            "JWT_REFRESH_TOKEN_EXPIRE_DAYS": "7",
            "MAX_SESSIONS_PER_USER": "5",
        }

    text = config_path.read_text(encoding="utf-8")

    # Pattern: VAR_NAME: type = "value"  or  VAR_NAME: type = numeric_value
    pattern = re.compile(
        r"^\s*(?P<name>JWT_\w+|MAX_SESSIONS_PER_USER)\s*:\s*\w+\s*=\s*(?P<value>.+?)$",
        re.MULTILINE,
    )

    findings: dict[str, str] = {}
    for m in pattern.finditer(text):
        name = m.group("name")
        value = m.group("value").strip().strip('"').strip("'")
        findings[name] = value

    return findings


# ---------------------------------------------------------------------------
# .env.rs256.example generator
# ---------------------------------------------------------------------------
def generate_env_example(jwt_config: dict[str, str], output_path: Path) -> None:
    """Write a .env.rs256.example with all RS256 variables filled in."""
    current_secret = jwt_config.get("JWT_SECRET_KEY", "<your-current-hs256-secret>")
    access_expire = jwt_config.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    refresh_expire = jwt_config.get("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
    max_sessions = jwt_config.get("MAX_SESSIONS_PER_USER", "5")

    # Check if keys already exist on disk
    secrets_dir = PROJECT_ROOT / "secrets"
    has_keys = (secrets_dir / "jwt_private_key.pem").exists()

    content = f"""\
# ─────────────────────────────────────────────────────────────────────────────
# RS256 JWT Configuration — PARWA L-01 Migration
# ─────────────────────────────────────────────────────────────────────────────
#
# Copy this file to .env and fill in the real values:
#   cp .env.rs256.example .env
#
# Generate keys first with:
#   python scripts/generate_rsa_keys.py
#
# ─────────────────────────────────────────────────────────────────────────────

# ── RS256 Algorithm ─────────────────────────────────────────────────────────
JWT_ALGORITHM=RS256

# ── Key file paths (used by the backend to load keys from disk) ─────────────
# These paths are relative to the project root (where the backend runs).
JWT_PRIVATE_KEY_PATH=secrets/jwt_private_key.pem
JWT_PUBLIC_KEY_PATH=secrets/jwt_public_key.pem

# ── Base64-encoded keys (alternative to file paths, for container / env-only deploys) ──
# Run:  python scripts/generate_rsa_keys.py   to generate and print these values.
JWT_PRIVATE_KEY_BASE64=<base64-encoded-private-key>
JWT_PUBLIC_KEY_BASE64=<base64-encoded-public-key>

# ── HS256 fallback secret (keep during migration) ───────────────────────────
# The current HS256 secret — kept so existing HS256 tokens remain valid
# during the dual-algorithm transition period. Remove after full migration.
JWT_HS256_SECRET={current_secret}

# ── Token expiry (unchanged from HS256 config) ──────────────────────────────
JWT_ACCESS_TOKEN_EXPIRE_MINUTES={access_expire}
JWT_REFRESH_TOKEN_EXPIRE_DAYS={refresh_expire}
MAX_SESSIONS_PER_USER={max_sessions}
"""
    output_path.write_text(content, encoding="utf-8")
    print(f"  ✅ Wrote  {output_path.relative_to(PROJECT_ROOT)}")
    print(f"     ({'keys detected on disk' if has_keys else 'no keys on disk yet — run generate_rsa_keys.py first'})")


# ---------------------------------------------------------------------------
# Migration notes generator
# ---------------------------------------------------------------------------
def generate_migration_notes(jwt_config: dict[str, str], output_path: Path) -> None:
    """Write a detailed migration guide from HS256 to RS256."""
    current_secret_display = jwt_config.get(
        "JWT_SECRET_KEY", "<your-current-hs256-secret>"
    )
    # Mask the secret for display if it looks like a real value
    if current_secret_display.startswith("dev-"):
        secret_display = current_secret_display
    else:
        secret_display = current_secret_display[:8] + "…" + "*" * 20

    content = f"""\
# RS256 Migration Guide — PARWA L-01

> **Goal:** Migrate JWT signing from symmetric HS256 to asymmetric RS256.
> **Prerequisite:** RSA key pair generated via `scripts/generate_rsa_keys.py`.
> **Status:** Preparation only — no code changes yet.

---

## Current State (HS256)

The application currently signs JWTs with a shared secret (`JWT_SECRET_KEY`):

```
JWT_SECRET_KEY = {secret_display}
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = {jwt_config.get('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', '15')}
JWT_REFRESH_TOKEN_EXPIRE_DAYS = {jwt_config.get('JWT_REFRESH_TOKEN_EXPIRE_DAYS', '7')}
```

All services that verify tokens must share the same secret. This is
acceptable for a monolith but becomes a liability with microservices or
third-party token consumers.

## Target State (RS256)

- **Private key** signs tokens (backend only).
- **Public key** verifies tokens (any service or consumer).
- No shared secret needed for verification.

---

## Migration Steps (Week 6 Full Migration)

### Phase 1 — Key Generation (L-01, Current)

1. **Generate RSA key pair:**
   ```bash
   python scripts/generate_rsa_keys.py --bits 4096
   ```

2. **Store keys securely:**
   - Option A: File-based — `secrets/jwt_private_key.pem` (chmod 600)
   - Option B: Env vars — `JWT_PRIVATE_KEY_BASE64` / `JWT_PUBLIC_KEY_BASE64`
   - Option C: Secrets manager (Vault / AWS SM / GCP KMS) — for production

3. **Copy the example env file:**
   ```bash
   cp .env.rs256.example .env
   # Edit .env and fill in the base64 values from step 1
   ```

4. **Verify `secrets/` is in `.gitignore`** (already confirmed ✓).

### Phase 2 — Dual-Algorithm Support

5. **Add RS256 fields to `backend/app/config.py`:**
   ```python
   JWT_ALGORITHM: str = "HS256"  # Default to HS256 during migration
   JWT_PRIVATE_KEY_PATH: str = ""
   JWT_PUBLIC_KEY_PATH: str = ""
   JWT_PRIVATE_KEY_BASE64: str = ""
   JWT_PUBLIC_KEY_BASE64: str = ""
   JWT_HS256_SECRET: str = ""  # Fallback for existing tokens
   ```

6. **Update the auth service** to support both algorithms:
   - **Signing:** Use RS256 private key when `JWT_ALGORITHM=RS256`.
   - **Verification:** Try RS256 first, fall back to HS256 for legacy tokens.
   - Emit a deprecation log when an HS256 token is validated.

### Phase 3 — Token Rotation

7. **Force re-login after a configurable grace period** (e.g., 7 days).
   - All new tokens will be RS256-signed.
   - HS256 tokens naturally expire within `JWT_REFRESH_TOKEN_EXPIRE_DAYS`.

8. **Monitor** for remaining HS256 token validations in logs.
   - When count drops to zero, remove the HS256 fallback.

### Phase 4 — Cleanup

9. **Remove HS256 support:**
   - Delete `JWT_HS256_SECRET` and the HS256 fallback path.
   - Set `JWT_ALGORITHM=RS256` as the only supported value.
   - Update tests that relied on HS256.

10. **Rotate keys periodically** — see `documents/JWT_KEY_ROTATION_PROCEDURE.md`.

---

## Files Modified During Migration (Future)

| File | Change |
|------|--------|
| `backend/app/config.py` | Add RS256 env vars, algorithm field |
| `backend/app/core/auth.py` | Dual-algorithm sign/verify logic |
| `backend/app/services/auth_service.py` | Pass algorithm + key to PyJWT |
| `.env` | New RS256 env vars |
| `tests/unit/test_auth_jwt.py` | RS256 test cases |

## Files Created During L-01 (Now)

| File | Purpose |
|------|---------|
| `scripts/generate_rsa_keys.py` | RSA key pair generator |
| `scripts/rs256_migration_prep.py` | This preparation script |
| `.env.rs256.example` | Example env var template |
| `scripts/RS256_MIGRATION_NOTES.md` | This migration guide |

---

## Security Checklist

- [ ] `secrets/` in `.gitignore` ✓
- [ ] Private key file permissions set to 600
- [ ] Keys stored in secrets manager (production)
- [ ] No keys committed to version control
- [ ] Key rotation procedure documented
- [ ] HS256 fallback has a deprecation timeline

---

*Generated by `scripts/rs256_migration_prep.py`*
"""

    output_path.write_text(content, encoding="utf-8")
    print(f"  ✅ Wrote  {output_path.relative_to(PROJECT_ROOT)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 70)
    print("L-01 — RS256 Migration Preparation")
    print("=" * 70)

    # 1. Parse current config
    print(f"\n📖 Reading JWT config from {CONFIG_PATH.relative_to(PROJECT_ROOT)} …")
    jwt_config = parse_jwt_config(CONFIG_PATH)

    print("  Current JWT settings found:")
    for key, value in sorted(jwt_config.items()):
        # Truncate secrets for display
        if "SECRET" in key and len(value) > 20:
            display = value[:12] + "…" + "*" * 16
        else:
            display = value
        print(f"    {key} = {display}")

    # 2. Generate .env.rs256.example
    print(f"\n📝 Generating .env.rs256.example …")
    generate_env_example(jwt_config, ENV_EXAMPLE_OUTPUT)

    # 3. Generate migration notes
    print(f"\n📝 Generating migration notes …")
    generate_migration_notes(jwt_config, MIGRATION_NOTES_OUTPUT)

    print(
        "\n" + "=" * 70
    )
    print("✅ Preparation complete. Next steps:")
    print("  1. Run:  python scripts/generate_rsa_keys.py --bits 4096")
    print("  2. Copy:  cp .env.rs256.example .env")
    print("  3. Edit .env and fill in the base64 key values")
    print("  4. Read:  scripts/RS256_MIGRATION_NOTES.md")
    print("=" * 70
    )


if __name__ == "__main__":
    main()
