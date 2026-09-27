#!/usr/bin/env python3
"""
L-01 — RSA Key Pair Generator for JWT RS256 Signing

Generates an RSA key pair suitable for JWT RS256 signing/verification.
Private key is saved to secrets/jwt_private_key.pem (chmod 600).
Public key  is saved to secrets/jwt_public_key.pem  (chmod 644).

Usage:
    python scripts/generate_rsa_keys.py                  # 2048-bit, refuse overwrite
    python scripts/generate_rsa_keys.py --bits 4096      # 4096-bit keys
    python scripts/generate_rsa_keys.py --force          # overwrite existing keys

Requirements:
    pip install cryptography
"""

from __future__ import annotations

import argparse
import base64
import os
import stat
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Guard: cryptography must be available
# ---------------------------------------------------------------------------
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    print(
        "ERROR: 'cryptography' package is required.\n"
        "  Install it with:  pip install cryptography",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = PROJECT_ROOT / "secrets"
PRIVATE_KEY_PATH = SECRETS_DIR / "jwt_private_key.pem"
PUBLIC_KEY_PATH = SECRETS_DIR / "jwt_public_key.pem"

DEFAULT_BITS = 2048


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def check_gitignore() -> bool:
    """Verify that `secrets/` is listed in the project .gitignore."""
    gitignore_path = PROJECT_ROOT / ".gitignore"
    if not gitignore_path.exists():
        print(
            "WARNING: No .gitignore found at project root. "
            "Add 'secrets/' to .gitignore before committing.",
            file=sys.stderr,
        )
        return False

    content = gitignore_path.read_text(encoding="utf-8")
    # Check for exact entry or glob that covers 'secrets/'
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "secrets/" or stripped == "secrets":
            return True

    print(
        "WARNING: 'secrets/' is NOT in .gitignore. "
        "Add it now to prevent accidental key leakage:\n"
        '  echo "secrets/" >> .gitignore',
        file=sys.stderr,
    )
    return False


def generate_key_pair(bits: int):
    """Generate an RSA private key with the given key size."""
    print(f"Generating {bits}-bit RSA key pair …")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=bits,
    )
    return private_key


def write_pem_files(private_key, force: bool) -> None:
    """Serialize and write the private & public PEM files."""
    # Check for existing files
    if not force:
        for label, path in [
            ("Private key", PRIVATE_KEY_PATH),
            ("Public key", PUBLIC_KEY_PATH),
        ]:
            if path.exists():
                print(
                    f"ERROR: {label} already exists at {path}.\n"
                    "  Use --force to overwrite, or back up the existing key first.",
                    file=sys.stderr,
                )
                sys.exit(1)

    # Create secrets/ directory if it doesn't exist
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    # Serialize private key (no passphrase — for server-side signing)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Serialize public key
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Write files
    PRIVATE_KEY_PATH.write_bytes(private_pem)
    PUBLIC_KEY_PATH.write_bytes(public_pem)

    # Set permissions
    PRIVATE_KEY_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    PUBLIC_KEY_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)  # 0o644

    print(f"  Private key → {PRIVATE_KEY_PATH.relative_to(PROJECT_ROOT)}  (permissions: 600)")
    print(f"  Public key  → {PUBLIC_KEY_PATH.relative_to(PROJECT_ROOT)}  (permissions: 644)")

    return public_key


def print_base64_public_key(public_key) -> None:
    """Print the public key in base64 (single line) for env-var config."""
    pub_pem_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    b64 = base64.b64encode(pub_pem_bytes).decode("ascii")

    print("\n" + "=" * 70)
    print("PUBLIC KEY (base64 — paste into JWT_PUBLIC_KEY_BASE64 env var):")
    print("=" * 70)
    # Print in 76-char wrapped lines for readability
    for i in range(0, len(b64), 76):
        print(b64[i : i + 76])
    print("=" * 70)

    # Also print private key base64 (for JWT_PRIVATE_KEY_BASE64 env var)
    print("\n" + "=" * 70)
    print("PRIVATE KEY (base64 — paste into JWT_PRIVATE_KEY_BASE64 env var):")
    print("=" * 70)
    print("  ⚠  Guard this value carefully — it can sign JWTs as any user!")
    private_key_bytes = PRIVATE_KEY_PATH.read_bytes()
    priv_b64 = base64.b64encode(private_key_bytes).decode("ascii")
    for i in range(0, len(priv_b64), 76):
        print(priv_b64[i : i + 76])
    print("=" * 70)


def print_security_warning() -> None:
    """Print a prominent security warning."""
    print(
        "\n"
        "╔══════════════════════════════════════════════════════════════════╗\n"
        "║  ⚠  SECURITY WARNING                                           ║\n"
        "║                                                                ║\n"
        "║  • NEVER commit the private key or secrets/ directory to git.  ║\n"
        "║  • Store keys in a secrets manager (Vault, AWS SM, GCP KMS).   ║\n"
        "║  • Rotate keys immediately if they are ever leaked.           ║\n"
        "║  • In production, load keys from env vars, not filesystem.    ║\n"
        "║  • Use --bits 4096 for production-grade security.             ║\n"
        "╚══════════════════════════════════════════════════════════════════╝",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate RSA key pair for JWT RS256 signing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/generate_rsa_keys.py\n"
            "  python scripts/generate_rsa_keys.py --bits 4096\n"
            "  python scripts/generate_rsa_keys.py --force\n"
        ),
    )
    parser.add_argument(
        "--bits",
        type=int,
        default=DEFAULT_BITS,
        choices=[2048, 4096],
        help=f"RSA key size in bits (default: {DEFAULT_BITS}). Use 4096 for production.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing key files without prompting.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    # 1. Verify .gitignore
    check_gitignore()

    # 2. Generate key pair
    private_key = generate_key_pair(bits=args.bits)

    # 3. Write PEM files
    public_key = write_pem_files(private_key, force=args.force)

    # 4. Print base64 representations
    print_base64_public_key(public_key)

    # 5. Print security warning
    print_security_warning()

    print(f"\n✅ RSA-{args.bits} key pair generated successfully.")


if __name__ == "__main__":
    main()
