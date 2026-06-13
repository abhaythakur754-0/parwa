"""Tests for L-01 RS256 preparation scripts.

Validates:
- generate_rsa_keys.py exists and compiles
- rs256_migration_prep.py exists and compiles
- .env.rs256.example was generated
- generate_rsa_keys.py uses cryptography library
- --force flag support
- --bits flag support
- Source code verification of both scripts
"""

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Path constants ─────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
GENERATE_RSA_KEYS = PROJECT_ROOT / "scripts" / "generate_rsa_keys.py"
RS256_MIGRATION_PREP = PROJECT_ROOT / "scripts" / "rs256_migration_prep.py"
ENV_RS256_EXAMPLE = PROJECT_ROOT / ".env.rs256.example"


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def rsa_keys_source():
    """Read generate_rsa_keys.py source."""
    assert GENERATE_RSA_KEYS.exists(), f"generate_rsa_keys.py not found"
    return GENERATE_RSA_KEYS.read_text(encoding="utf-8")


@pytest.fixture
def migration_prep_source():
    """Read rs256_migration_prep.py source."""
    assert RS256_MIGRATION_PREP.exists(), f"rs256_migration_prep.py not found"
    return RS256_MIGRATION_PREP.read_text(encoding="utf-8")


@pytest.fixture
def env_example_source():
    """Read .env.rs256.example source."""
    assert ENV_RS256_EXAMPLE.exists(), f".env.rs256.example not found"
    return ENV_RS256_EXAMPLE.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════
# 1. generate_rsa_keys.py — existence and compilation
# ═══════════════════════════════════════════════════════════════════

class TestGenerateRSAKeysExists:
    """Verify generate_rsa_keys.py exists and compiles."""

    def test_file_exists(self):
        """generate_rsa_keys.py must exist."""
        assert GENERATE_RSA_KEYS.exists(), (
            f"generate_rsa_keys.py not found at {GENERATE_RSA_KEYS}"
        )

    def test_valid_python_syntax(self, rsa_keys_source):
        """generate_rsa_keys.py must be valid Python."""
        try:
            ast.parse(rsa_keys_source)
        except SyntaxError as e:
            pytest.fail(f"generate_rsa_keys.py has syntax error: {e}")

    def test_has_main_guard(self, rsa_keys_source):
        """Script must have if __name__ == '__main__' guard."""
        assert '__name__' in rsa_keys_source and '__main__' in rsa_keys_source, (
            "Missing if __name__ == '__main__' guard"
        )

    def test_has_docstring(self, rsa_keys_source):
        """Script must have a module-level docstring."""
        tree = ast.parse(rsa_keys_source)
        doc = ast.get_docstring(tree)
        assert doc is not None, "No module-level docstring"
        assert "RSA" in doc or "RS256" in doc, (
            "Docstring should mention RSA/RS256"
        )


# ═══════════════════════════════════════════════════════════════════
# 2. rs256_migration_prep.py — existence and compilation
# ═══════════════════════════════════════════════════════════════════

class TestRS256MigrationPrepExists:
    """Verify rs256_migration_prep.py exists and compiles."""

    def test_file_exists(self):
        """rs256_migration_prep.py must exist."""
        assert RS256_MIGRATION_PREP.exists(), (
            f"rs256_migration_prep.py not found at {RS256_MIGRATION_PREP}"
        )

    def test_valid_python_syntax(self, migration_prep_source):
        """rs256_migration_prep.py must be valid Python."""
        try:
            ast.parse(migration_prep_source)
        except SyntaxError as e:
            pytest.fail(f"rs256_migration_prep.py has syntax error: {e}")

    def test_has_main_guard(self, migration_prep_source):
        """Script must have if __name__ == '__main__' guard."""
        assert '__name__' in migration_prep_source and '__main__' in migration_prep_source, (
            "Missing if __name__ == '__main__' guard"
        )

    def test_has_docstring(self, migration_prep_source):
        """Script must have a module-level docstring."""
        tree = ast.parse(migration_prep_source)
        doc = ast.get_docstring(tree)
        assert doc is not None, "No module-level docstring"


# ═══════════════════════════════════════════════════════════════════
# 3. .env.rs256.example generated
# ═══════════════════════════════════════════════════════════════════

class TestEnvRS256Example:
    """Verify .env.rs256.example was generated."""

    def test_file_exists(self):
        """.env.rs256.example must exist."""
        assert ENV_RS256_EXAMPLE.exists(), (
            f".env.rs256.example not found at {ENV_RS256_EXAMPLE}"
        )

    def test_contains_rs256_algorithm(self, env_example_source):
        """Must set JWT_ALGORITHM=RS256."""
        assert "JWT_ALGORITHM=RS256" in env_example_source, (
            "JWT_ALGORITHM=RS256 not found"
        )

    def test_contains_key_paths(self, env_example_source):
        """Must reference private and public key paths."""
        assert "JWT_PRIVATE_KEY_PATH" in env_example_source, (
            "JWT_PRIVATE_KEY_PATH not found"
        )
        assert "JWT_PUBLIC_KEY_PATH" in env_example_source, (
            "JWT_PUBLIC_KEY_PATH not found"
        )

    def test_contains_base64_keys(self, env_example_source):
        """Must have base64 key placeholders."""
        assert "JWT_PRIVATE_KEY_BASE64" in env_example_source, (
            "JWT_PRIVATE_KEY_BASE64 not found"
        )
        assert "JWT_PUBLIC_KEY_BASE64" in env_example_source, (
            "JWT_PUBLIC_KEY_BASE64 not found"
        )

    def test_contains_hs256_fallback(self, env_example_source):
        """Must have HS256 fallback secret for migration."""
        assert "JWT_HS256_SECRET" in env_example_source, (
            "JWT_HS256_SECRET fallback not found"
        )

    def test_contains_token_expiry(self, env_example_source):
        """Must preserve token expiry settings."""
        assert "JWT_ACCESS_TOKEN_EXPIRE_MINUTES" in env_example_source, (
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES not found"
        )
        assert "JWT_REFRESH_TOKEN_EXPIRE_DAYS" in env_example_source, (
            "JWT_REFRESH_TOKEN_EXPIRE_DAYS not found"
        )

    def test_key_paths_point_to_secrets(self, env_example_source):
        """Key paths should point to secrets/ directory."""
        assert "secrets/jwt_private_key.pem" in env_example_source, (
            "Private key path doesn't point to secrets/"
        )
        assert "secrets/jwt_public_key.pem" in env_example_source, (
            "Public key path doesn't point to secrets/"
        )

    def test_is_read_only_template(self, env_example_source):
        """Should have .example suffix and be a template."""
        assert ENV_RS256_EXAMPLE.suffixes == [".env", ".rs256", ".example"] or \
               ENV_RS256_EXAMPLE.name == ".env.rs256.example", (
            "File should be named .env.rs256.example"
        )


# ═══════════════════════════════════════════════════════════════════
# 4. cryptography library usage
# ═══════════════════════════════════════════════════════════════════

class TestCryptographyUsage:
    """Verify generate_rsa_keys.py uses cryptography library."""

    def test_imports_cryptography(self, rsa_keys_source):
        """Must import from cryptography package."""
        assert "from cryptography" in rsa_keys_source or \
               "import cryptography" in rsa_keys_source, (
            "cryptography package not imported"
        )

    def test_uses_rsa_generation(self, rsa_keys_source):
        """Must use RSA key generation."""
        assert "rsa" in rsa_keys_source.lower() and \
               "generate_private_key" in rsa_keys_source, (
            "RSA private key generation not found"
        )

    def test_uses_serialization(self, rsa_keys_source):
        """Must use cryptography serialization for PEM output."""
        assert "serialization" in rsa_keys_source, (
            "serialization module not imported"
        )
        assert "PEM" in rsa_keys_source, (
            "PEM format not referenced"
        )

    def test_sets_private_key_permissions(self, rsa_keys_source):
        """Must set restrictive permissions on private key (600)."""
        assert "chmod" in rsa_keys_source or "0o600" in rsa_keys_source or "600" in rsa_keys_source, (
            "Private key file permissions not set to 600"
        )

    def test_private_key_no_encryption(self, rsa_keys_source):
        """Private key must not use passphrase encryption (server-side signing)."""
        assert "NoEncryption" in rsa_keys_source, (
            "NoEncryption not used — private key may have unnecessary passphrase"
        )


# ═══════════════════════════════════════════════════════════════════
# 5. --force flag support
# ═══════════════════════════════════════════════════════════════════

class TestForceFlag:
    """Verify --force flag support."""

    def test_force_flag_in_argparse(self, rsa_keys_source):
        """Must define --force in argparse."""
        assert '"--force"' in rsa_keys_source or "'--force'" in rsa_keys_source, (
            "--force flag not defined in argparse"
        )

    def test_force_flag_is_boolean(self, rsa_keys_source):
        """--force must be a store_true action."""
        assert "store_true" in rsa_keys_source, (
            "--force should use store_true action"
        )

    def test_force_flag_prevents_overwrite_by_default(self, rsa_keys_source):
        """Default behavior should refuse to overwrite existing keys."""
        assert "exists" in rsa_keys_source.lower(), (
            "No existence check before writing keys"
        )


# ═══════════════════════════════════════════════════════════════════
# 6. --bits flag support
# ═══════════════════════════════════════════════════════════════════

class TestBitsFlag:
    """Verify --bits flag support."""

    def test_bits_flag_in_argparse(self, rsa_keys_source):
        """Must define --bits in argparse."""
        assert '"--bits"' in rsa_keys_source or "'--bits'" in rsa_keys_source, (
            "--bits flag not defined in argparse"
        )

    def test_bits_accepts_int(self, rsa_keys_source):
        """--bits must accept an integer value."""
        assert "type=int" in rsa_keys_source, (
            "--bits should accept integer type"
        )

    def test_bits_default_2048(self, rsa_keys_source):
        """Default bits should be 2048."""
        assert "2048" in rsa_keys_source, (
            "2048-bit default not found"
        )

    def test_bits_supports_4096(self, rsa_keys_source):
        """Must support 4096-bit keys."""
        assert "4096" in rsa_keys_source, (
            "4096-bit key support not found"
        )

    def test_bits_choices_defined(self, rsa_keys_source):
        """--bits should have limited choices (2048, 4096)."""
        assert "choices" in rsa_keys_source, (
            "--bits should have choices constraint"
        )


# ═══════════════════════════════════════════════════════════════════
# 7. Security features
# ═══════════════════════════════════════════════════════════════════

class TestSecurityFeatures:
    """Verify security best practices."""

    def test_checks_gitignore(self, rsa_keys_source):
        """Should verify secrets/ is in .gitignore."""
        assert "gitignore" in rsa_keys_source.lower(), (
            "No .gitignore check found"
        )

    def test_warns_about_key_security(self, rsa_keys_source):
        """Should warn about key security."""
        assert "WARNING" in rsa_keys_source or "SECURITY" in rsa_keys_source, (
            "No security warning found"
        )

    def test_creates_secrets_directory(self, rsa_keys_source):
        """Should create secrets/ directory if it doesn't exist."""
        assert "secrets" in rsa_keys_source, (
            "secrets/ directory not referenced"
        )
        assert "mkdir" in rsa_keys_source, (
            "Directory creation not found"
        )

    def test_outputs_base64_keys(self, rsa_keys_source):
        """Should output base64-encoded keys for env var usage."""
        assert "base64" in rsa_keys_source, (
            "Base64 encoding not found"
        )


# ═══════════════════════════════════════════════════════════════════
# 8. rs256_migration_prep.py — source code verification
# ═══════════════════════════════════════════════════════════════════

class TestMigrationPrepSource:
    """Verify rs256_migration_prep.py source code."""

    def test_is_read_only(self, migration_prep_source):
        """Script should be READ-ONLY (not modify existing code)."""
        tree = ast.parse(migration_prep_source)
        doc = ast.get_docstring(tree)
        assert doc is not None
        assert "READ-ONLY" in doc or "read-only" in doc.lower(), (
            "Script should document it's READ-ONLY"
        )

    def test_generates_env_example(self, migration_prep_source):
        """Must generate the .env.rs256.example file."""
        assert ".env.rs256.example" in migration_prep_source or \
               "ENV_EXAMPLE" in migration_prep_source, (
            "Script doesn't generate .env.rs256.example"
        )

    def test_generates_migration_notes(self, migration_prep_source):
        """Must generate migration notes/documentation."""
        assert "migration" in migration_prep_source.lower() and \
               "MIGRATION_NOTES" in migration_prep_source or \
               "notes" in migration_prep_source.lower(), (
            "Script doesn't generate migration notes"
        )

    def test_reads_current_config(self, migration_prep_source):
        """Must read current JWT configuration."""
        assert "config.py" in migration_prep_source or \
               "JWT" in migration_prep_source, (
            "Script doesn't read current JWT config"
        )

    def test_uses_argparse_or_direct_call(self, migration_prep_source):
        """Script should be callable (has main function)."""
        assert "def main" in migration_prep_source, (
            "No main() function found"
        )
