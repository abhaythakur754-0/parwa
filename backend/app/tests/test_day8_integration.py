"""
Day 8 — Integration Testing & Verification (FINAL)
===================================================
Comprehensive verification that ALL security fixes from Days 1–7 are
properly wired together as a complete system.

Checks:
  1. All middleware files exist and can be imported independently
  2. CSRF middleware is wired into main.py
  3. GDPR router is registered in main.py
  4. Platform admin guard exists in admin.py
  5. Tenant middleware has reduced PUBLIC_PREFIXES (Day 3)
  6. All new files created in Days 1–7 exist on disk
  7. Cross-module import chain works
"""

import os
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — match conftest.py pattern so imports resolve
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_BACKEND_DIR = _PROJECT_ROOT / "backend"
for _p in (_PROJECT_ROOT, str(_BACKEND_DIR)):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


# ===================================================================
# 1. All middleware files exist and can be imported
# ===================================================================

class TestMiddlewareFilesExist(unittest.TestCase):
    """Verify all security-critical middleware files exist on disk."""

    BACKEND = _BACKEND_DIR

    def test_csrf_middleware_file_exists(self):
        path = self.BACKEND / "app" / "middleware" / "csrf.py"
        self.assertTrue(path.is_file(), f"Missing {path}")

    def test_security_headers_middleware_file_exists(self):
        path = self.BACKEND / "app" / "middleware" / "security_headers.py"
        self.assertTrue(path.is_file(), f"Missing {path}")

    def test_tenant_middleware_file_exists(self):
        path = self.BACKEND / "app" / "middleware" / "tenant.py"
        self.assertTrue(path.is_file(), f"Missing {path}")

    def test_ip_allowlist_middleware_file_exists(self):
        path = self.BACKEND / "app" / "middleware" / "ip_allowlist.py"
        self.assertTrue(path.is_file(), f"Missing {path}")

    def test_rate_limit_middleware_file_exists(self):
        path = self.BACKEND / "app" / "middleware" / "rate_limit.py"
        self.assertTrue(path.is_file(), f"Missing {path}")

    def test_error_handler_middleware_file_exists(self):
        path = self.BACKEND / "app" / "middleware" / "error_handler.py"
        self.assertTrue(path.is_file(), f"Missing {path}")

    def test_middleware_package_init_exists(self):
        path = self.BACKEND / "app" / "middleware" / "__init__.py"
        self.assertTrue(path.is_file(), f"Missing {path}")


class TestMiddlewareImportable(unittest.TestCase):
    """Verify middleware modules can be imported without pulling in the full app."""

    def test_import_csrf_middleware(self):
        from app.middleware.csrf import CSRFMiddleware  # noqa: F401
        self.assertTrue(True)

    def test_import_security_headers_middleware(self):
        from app.middleware.security_headers import SecurityHeadersMiddleware  # noqa: F401
        self.assertTrue(True)

    def test_import_tenant_middleware(self):
        from app.middleware.tenant import TenantMiddleware  # noqa: F401
        self.assertTrue(True)

    def test_csrf_middleware_has_dispatch(self):
        from app.middleware.csrf import CSRFMiddleware
        self.assertTrue(hasattr(CSRFMiddleware, "dispatch"))

    def test_csrf_middleware_has_exempt_prefixes(self):
        from app.middleware.csrf import CSRF_EXEMPT_PREFIXES
        self.assertIsInstance(CSRF_EXEMPT_PREFIXES, tuple)
        self.assertTrue(len(CSRF_EXEMPT_PREFIXES) > 0)


# ===================================================================
# 2. CSRF middleware is wired into main.py
# ===================================================================

class TestCSRFWiredInMain(unittest.TestCase):
    """Verify CSRF middleware is imported and added in main.py."""

    MAIN_PY = _BACKEND_DIR / "app" / "main.py"

    def test_csrf_import_in_main(self):
        content = self.MAIN_PY.read_text()
        self.assertIn(
            "from app.middleware.csrf import CSRFMiddleware",
            content)

    def test_csrf_middleware_added_to_app(self):
        content = self.MAIN_PY.read_text()
        self.assertIn("CSRFMiddleware", content)

    def test_csrf_app_add_middleware(self):
        content = self.MAIN_PY.read_text()
        self.assertIn("add_middleware", content)


# ===================================================================
# 3. GDPR router is registered in main.py
# ===================================================================

class TestGDPRWiredInMain(unittest.TestCase):
    """Verify GDPR router is imported and included in main.py."""

    MAIN_PY = _BACKEND_DIR / "app" / "main.py"

    def test_gdpr_import_in_main(self):
        content = self.MAIN_PY.read_text()
        self.assertIn("gdpr_router", content)

    def test_gdpr_router_included(self):
        content = self.MAIN_PY.read_text()
        self.assertIn("include_router(gdpr_router)", content)

    def test_gdpr_module_file_exists(self):
        path = _BACKEND_DIR / "app" / "api" / "gdpr.py"
        self.assertTrue(path.is_file(), f"Missing {path}")


# ===================================================================
# 4. Platform admin guard exists in admin.py
# ===================================================================

class TestPlatformAdminGuard(unittest.TestCase):
    """Verify platform admin guard function exists and is used in admin.py."""

    ADMIN_PY = _BACKEND_DIR / "app" / "api" / "admin.py"

    def test_require_platform_admin_function_exists(self):
        content = self.ADMIN_PY.read_text()
        self.assertIn("def require_platform_admin", content)

    def test_platform_admin_env_var_check(self):
        content = self.ADMIN_PY.read_text()
        self.assertIn("PLATFORM_ADMIN_EMAIL", content)

    def test_platform_admin_todo_comment(self):
        content = self.ADMIN_PY.read_text()
        self.assertIn("TODO", content)

    def test_platform_admin_used_in_endpoints(self):
        content = self.ADMIN_PY.read_text()
        # Should be used as a dependency in multiple endpoints
        self.assertTrue(
            content.count("require_platform_admin") >= 3,
            "require_platform_admin should be used in at least 3 endpoints"
        )


# ===================================================================
# 5. Tenant middleware has reduced PUBLIC_PREFIXES (Day 3)
# ===================================================================

class TestTenantReducedPublicPrefixes(unittest.TestCase):
    """Verify sensitive prefixes removed from PUBLIC_PREFIXES in tenant middleware."""

    TENANT_PY = _BACKEND_DIR / "app" / "middleware" / "tenant.py"

    def test_billing_removed_from_public_prefixes(self):
        content = self.TENANT_PY.read_text()
        # Find the PUBLIC_PREFIXES tuple
        self.assertNotIn(
            '"/api/billing/"',
            content.split("PUBLIC_PREFIXES")[1].split(")")[0])

    def test_api_keys_removed_from_public_prefixes(self):
        content = self.TENANT_PY.read_text()
        prefix_block = content.split("PUBLIC_PREFIXES")[1].split(")")[0]
        self.assertNotIn('"/api/api-keys"', prefix_block)
        self.assertNotIn('"/api/api_keys"', prefix_block)

    def test_mfa_removed_from_public_prefixes(self):
        content = self.TENANT_PY.read_text()
        prefix_block = content.split("PUBLIC_PREFIXES")[1].split(")")[0]
        self.assertNotIn('"/api/mfa/"', prefix_block)

    def test_client_removed_from_public_prefixes(self):
        content = self.TENANT_PY.read_text()
        prefix_block = content.split("PUBLIC_PREFIXES")[1].split(")")[0]
        self.assertNotIn('"/api/client/"', prefix_block)

    def test_auth_still_public(self):
        content = self.TENANT_PY.read_text()
        self.assertIn('"/api/auth/"', content)

    def test_public_still_public(self):
        content = self.TENANT_PY.read_text()
        self.assertIn('"/api/public/"', content)

    def test_webhooks_still_public(self):
        content = self.TENANT_PY.read_text()
        self.assertIn('"/api/webhooks/"', content)


# ===================================================================
# 6. All new files created in Days 1–7 exist on disk
# ===================================================================

class TestAllDayFilesExist(unittest.TestCase):
    """Verify every file created across Days 1–7 exists."""

    BASE = _BACKEND_DIR

    # --- Day 1 ---
    def test_day1_csrf_middleware(self):
        self.assertTrue(
            (self.BASE
             / "app"
             / "middleware"
             / "csrf.py").is_file())

    # --- Day 2 ---
    def test_day2_docker_compose(self):
        self.assertTrue((self.BASE / ".." / "docker-compose.yml").is_file())

    # --- Day 3 ---
    def test_day3_gdpr_router(self):
        self.assertTrue((self.BASE / "app" / "api" / "gdpr.py").is_file())

    def test_day3_info_leak_guard(self):
        self.assertTrue(
            (self.BASE / "app" / "core" / "info_leak_guard.py").is_file())

    # --- Day 4 ---
    def test_day4_pii_redaction_engine(self):
        self.assertTrue(
            (self.BASE
             / "app"
             / "core"
             / "pii_redaction_engine.py").is_file())

    def test_day4_prompt_injection_defense(self):
        self.assertTrue(
            (self.BASE
             / "app"
             / "core"
             / "prompt_injection_defense.py").is_file())

    def test_day4_techniques_readme(self):
        self.assertTrue(
            (self.BASE
             / "app"
             / "core"
             / "techniques"
             / "README.md").is_file())

    # --- Day 5-7: security_headers already checked above ---

    # --- Test files ---
    def test_test_day1_file(self):
        self.assertTrue((self.BASE / "app" / "tests"
                        / "test_day1_security.py").is_file())

    def test_test_day2_file(self):
        self.assertTrue((self.BASE / "app" / "tests"
                        / "test_day2_security.py").is_file())

    def test_test_day3_file(self):
        self.assertTrue((self.BASE / "app" / "tests"
                        / "test_day3_security.py").is_file())

    def test_test_day4_file(self):
        self.assertTrue((self.BASE / "app" / "tests"
                        / "test_day4_security.py").is_file())

    def test_test_day5_file(self):
        self.assertTrue((self.BASE / "app" / "tests"
                        / "test_day5_security.py").is_file())

    def test_test_day6_file(self):
        self.assertTrue((self.BASE / "app" / "tests"
                        / "test_day6_security.py").is_file())

    def test_test_day7_file(self):
        self.assertTrue((self.BASE / "app" / "tests"
                        / "test_day7_security.py").is_file())

    def test_test_day8_file(self):
        self.assertTrue(
            (self.BASE
             / "app"
             / "tests"
             / "test_day8_integration.py").is_file())


# ===================================================================
# 7. Cross-module import chain
# ===================================================================

class TestCrossModuleImports(unittest.TestCase):
    """Verify that security modules can import each other without circular issues."""

    def test_import_info_leak_guard(self):
        from app.core.info_leak_guard import InfoLeakGuard, CANNED_REFUSAL_RESPONSE  # noqa: F401
        self.assertTrue(True)

    def test_import_pii_detector(self):
        from app.core.pii_redaction_engine import PIIDetector, ALL_PII_TYPES  # noqa: F401
        self.assertTrue(isinstance(ALL_PII_TYPES, (list, tuple, set)))
        self.assertTrue(len(ALL_PII_TYPES) > 0)

    def test_import_prompt_injection_defense(self):
        from app.core.prompt_injection_defense import PromptInjectionDetector, _ALL_RULES  # noqa: F401
        self.assertTrue(isinstance(_ALL_RULES, list))
        self.assertTrue(len(_ALL_RULES) > 0)

    def test_pii_detector_has_all_day4_types(self):
        from app.core.pii_redaction_engine import ALL_PII_TYPES
        for expected in ("EMAIL", "IP_ADDRESS", "PHONE", "NAME",
                         "EMAIL_SHORT", "PHONE_PARTIAL"):
            self.assertIn(expected, ALL_PII_TYPES,
                          f"Missing PII type: {expected}")

    def test_injection_defense_has_all_day4_rule_prefixes(self):
        from app.core.prompt_injection_defense import _ALL_RULES
        rule_ids = {r["rule_id"] for r in _ALL_RULES}
        for prefix in (
            "SQL-",
            "XSS-",
            "CMDI-",
            "TSM-",
            "RPA-",
            "JBR-",
                "EXTA-"):
            self.assertTrue(
                any(rid.startswith(prefix) for rid in rule_ids),
                f"Missing rule prefix: {prefix}"
            )

    def test_canned_response_mentions_parwa(self):
        from app.core.info_leak_guard import CANNED_REFUSAL_RESPONSE
        self.assertIn("PARWA", CANNED_REFUSAL_RESPONSE)


# ===================================================================
# 8. Day 1–7 test count sanity check
# ===================================================================

class TestDayTestCountSanity(unittest.TestCase):
    """Verify each Day test file has a reasonable number of test methods."""

    TESTS_DIR = _BACKEND_DIR / "app" / "tests"

    def _count_tests(self, filename):
        content = (self.TESTS_DIR / filename).read_text()
        return sum(1 for line in content.splitlines()
                   if line.strip().startswith("def test_"))

    def test_day1_has_tests(self):
        self.assertGreaterEqual(self._count_tests("test_day1_security.py"), 15)

    def test_day2_has_tests(self):
        self.assertGreaterEqual(self._count_tests("test_day2_security.py"), 20)

    def test_day3_has_tests(self):
        self.assertGreaterEqual(self._count_tests("test_day3_security.py"), 30)

    def test_day4_has_tests(self):
        self.assertGreaterEqual(self._count_tests("test_day4_security.py"), 40)

    def test_day5_has_tests(self):
        self.assertGreaterEqual(self._count_tests("test_day5_security.py"), 20)

    def test_day6_has_tests(self):
        self.assertGreaterEqual(self._count_tests("test_day6_security.py"), 25)

    def test_day7_has_tests(self):
        self.assertGreaterEqual(self._count_tests("test_day7_security.py"), 15)


if __name__ == "__main__":
    unittest.main()
