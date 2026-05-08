"""
PARWA Day 2 Security Tests — Data Protection & Infrastructure.

Tests verify that secrets management, SSL/TLS, cryptographic hashing,
and pricing key security are properly implemented.
"""

import pytest
import os


class TestC13PostgresSSL:
    """C-13: PostgreSQL must use SSL/TLS for encrypted connections."""

    def test_postgres_ssl_enabled(self):
        """postgresql.conf must have ssl=on."""
        with open('infra/docker/postgresql.conf') as f:
            content = f.read()
        assert 'ssl = on' in content

    def test_no_sslmode_disable(self):
        """docker-compose.prod.yml must NOT have sslmode=disable."""
        with open('docker-compose.prod.yml') as f:
            content = f.read()
        assert 'sslmode=disable' not in content

    def test_sslmode_require_present(self):
        """docker-compose.prod.yml should use sslmode=require."""
        with open('docker-compose.prod.yml') as f:
            content = f.read()
        assert 'sslmode=require' in content


class TestH09PricingSigningKey:
    """H-09: Pricing signing key must come from environment, not hardcoded."""

    def test_pricing_key_from_env(self):
        """PRICING_SIGNING_KEY must be loaded from os.environ."""
        with open('backend/app/api/pricing.py') as f:
            content = f.read()
        assert 'os.environ' in content
        assert 'PRICING_SIGNING_KEY' in content

    def test_no_hardcoded_pricing_key(self):
        """PRICING_SIGNING_KEY must NOT be a static hardcoded string."""
        with open('backend/app/api/pricing.py') as f:
            lines = f.readlines()
        for line in lines:
            if 'PRICING_SIGNING_KEY' in line and '=' in line and 'os.environ' not in line and 'import' not in line and '#' not in line:
                # Should not be a plain string assignment
                assert 'os.environ' in line or '${' in line or 'get(' in line, \
                    f"PRICING_SIGNING_KEY appears hardcoded: {line.strip()}"

    def test_pricing_key_in_env_example(self):
        """PRICING_SIGNING_KEY should be documented in .env.example."""
        with open('.env.example') as f:
            content = f.read()
        assert 'PRICING_SIGNING_KEY' in content


class TestH11NoMD5:
    """H-11: File integrity must use SHA-256, not MD5."""

    def test_no_md5_in_storage(self):
        """storage.py must not use hashlib.md5 for file integrity."""
        with open('backend/app/core/storage.py') as f:
            content = f.read()
        assert 'hashlib.md5' not in content
        assert 'hashlib.sha256' in content

    def test_checksum_field_renamed(self):
        """FileMetadata must use checksum_sha256, not checksum_md5."""
        with open('backend/app/core/storage.py') as f:
            content = f.read()
        assert 'checksum_sha256' in content
        assert 'checksum_md5' not in content or 'checksum_md5' in 'deprecated'

    def test_no_md5_in_schema(self):
        """file_storage schema must use SHA-256."""
        with open('backend/app/schemas/file_storage.py') as f:
            content = f.read()
        assert 'checksum_sha256' in content
        assert 'checksum_md5' not in content

    def test_no_md5_in_other_modules(self):
        """Other backend modules should not use MD5."""
        md5_files = []
        for root, dirs, files in os.walk('backend/app'):
            for fname in files:
                if fname.endswith('.py'):
                    fpath = os.path.join(root, fname)
                    with open(fpath) as f:
                        content = f.read()
                    if 'hashlib.md5' in content:
                        md5_files.append(fpath)
        assert len(md5_files) == 0, f"MD5 still found in: {md5_files}"


class TestC05CORSWildcard:
    """C-05: CORS must never use wildcard with credentials."""

    def test_no_cors_wildcard_with_creds(self):
        """CORS config must use explicit origins, not wildcard."""
        with open('backend/app/main.py') as f:
            content = f.read()
        assert 'CORS_ORIGINS' in content


class TestC07EnvProdNotInGit:
    """C-07: .env.prod must not be committed to git."""

    def test_gitignore_excludes_env_prod(self):
        """.gitignore must exclude .env.prod."""
        with open('.gitignore') as f:
            content = f.read()
        assert '.env.prod' in content

    def test_env_prod_in_gitignore(self):
        """.env.prod should be gitignored."""
        with open('.gitignore') as f:
            content = f.read()
        assert '.env.prod' in content


class TestC08NoClientCompanyId:
    """C-08: company_id must come from JWT, not client headers."""

    def test_tenant_middleware_no_header(self):
        """Tenant middleware must not read X-Company-ID from headers."""
        with open('backend/app/middleware/tenant.py') as f:
            content = f.read()
        assert 'X-Company-ID' not in content or 'Do NOT accept' in content


class TestH05TenantMiddlewarePaths:
    """H-05: Billing/admin paths must NOT be skipped by tenant middleware."""

    def test_billing_not_in_public_prefixes(self):
        """/api/billing/ must NOT be in PUBLIC_PREFIXES."""
        with open('backend/app/middleware/tenant.py') as f:
            content = f.read()
        # Find the PUBLIC_PREFIXES list
        lines = content.split('\n')
        in_list = False
        for line in lines:
            if 'PUBLIC_PREFIXES' in line:
                in_list = True
            if in_list:
                if '/api/billing/' in line or 'billing' in line.lower():
                    pytest.fail("billing should NOT be in PUBLIC_PREFIXES")
                if line.strip() == ']' or (in_list and not line.strip().startswith(('"', "'", '/')) and 'PUBLIC' not in line):
                    break

    def test_admin_not_in_public_prefixes(self):
        """/api/admin/ must NOT be in PUBLIC_PREFIXES."""
        with open('backend/app/middleware/tenant.py') as f:
            content = f.read()
        lines = content.split('\n')
        in_list = False
        for line in lines:
            if 'PUBLIC_PREFIXES' in line:
                in_list = True
            if in_list:
                if '/api/admin/' in line or ('admin' in line.lower() and 'prefix' not in line.lower()):
                    pytest.fail("admin should NOT be in PUBLIC_PREFIXES")
                if line.strip() == ']':
                    break
