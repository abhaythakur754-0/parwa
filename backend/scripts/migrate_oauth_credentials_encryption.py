"""One-time, idempotent migration of legacy OAuth credentials to Fernet encryption.

Run from the backend directory:
    python scripts/migrate_oauth_credentials_encryption.py          # dry run
    python scripts/migrate_oauth_credentials_encryption.py --apply   # persist

The script never prints credential values. It rolls back by default and aborts
the entire transaction if it encounters an unreadable or suspicious value.
Take a database backup before using --apply.
"""
from __future__ import annotations

import argparse
from typing import Callable, Optional, Tuple


def migrate_oauth_token_value(
    value: Optional[str],
    decrypt: Callable[[str], Optional[str]],
    encrypt: Callable[[str], Optional[str]],
) -> Tuple[Optional[str], bool]:
    """Return an encrypted value and whether it was migrated.

    Fernet tokens use the stable `gAAAAA` URL-safe token prefix. If a value
    has that prefix but cannot be decrypted, treat it as corruption/key
    mismatch and fail closed instead of encrypting ciphertext a second time.
    """
    if not value:
        return value, False

    plaintext = decrypt(value)
    if plaintext is not None:
        return value, False

    if value.startswith("gAAAAA"):
        raise RuntimeError("Existing Fernet-looking OAuth token cannot be decrypted")

    encrypted = encrypt(value)
    if not encrypted:
        raise RuntimeError("OAuth token encryption returned an empty value")
    return encrypted, True


def run_migration(apply: bool = False) -> dict:
    from app.services.integration_service import IntegrationService
    from database.base import SessionLocal
    from database.models.core import OAuthAccount
    from database.models.integration import Integration
    from shared.utils.token_encryption import decrypt_token, encrypt_token

    db = SessionLocal()
    counts = {
        "oauth_accounts_scanned": 0,
        "oauth_token_fields_migrated": 0,
        "integrations_scanned": 0,
        "integration_rows_migrated": 0,
    }
    service = IntegrationService(db)
    try:
        for account in db.query(OAuthAccount).yield_per(200):
            counts["oauth_accounts_scanned"] += 1
            for field in ("access_token", "refresh_token"):
                current = getattr(account, field)
                updated, migrated = migrate_oauth_token_value(
                    current, decrypt_token, encrypt_token
                )
                if migrated:
                    setattr(account, field, updated)
                    counts["oauth_token_fields_migrated"] += 1

        for integration in db.query(Integration).yield_per(200):
            if not integration.credentials_encrypted:
                continue
            counts["integrations_scanned"] += 1
            before = integration.credentials_encrypted
            credentials = service._load_credentials(integration)
            if credentials is None:
                raise RuntimeError(
                    f"Integration {integration.id} credentials are unreadable; "
                    "no migration changes were committed."
                )
            if integration.credentials_encrypted != before:
                counts["integration_rows_migrated"] += 1

        if apply:
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    counts["mode"] = "apply" if apply else "dry-run"
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the migration. Without this flag, all changes are rolled back.",
    )
    args = parser.parse_args()
    counts = run_migration(apply=args.apply)
    print("OAuth credential encryption migration summary:")
    for key, value in counts.items():
        print(f"  {key}: {value}")
    if not args.apply:
        print("Dry run only. Re-run with --apply after reviewing counts and taking a backup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
