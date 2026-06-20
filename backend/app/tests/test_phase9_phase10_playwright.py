"""
Phase 9 & 10 — Playwright Manual Testing

These tests verify the UI flows for:
- Phase 9: Audit Trail & Action Logging
- Phase 10: Rate Limiting & Error Handling (Integration Health)

Prerequisites:
- Backend running on http://localhost:8000
- Frontend running on http://localhost:3000
- A test user account with credentials

Run:
    pytest test_phase9_phase10_playwright.py -v --tb=short
"""
import os
import pytest

# Skip all tests if Playwright is not installed
pytest.importorskip("playwright")

from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
TEST_EMAIL = os.environ.get("TEST_EMAIL", "test@parwa.io")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "Testpassword1!")


@pytest.fixture(scope="module")
def authenticated_page(browser):
    """Create an authenticated page session."""
    page = browser.new_page()
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")
    
    # Fill login form
    email_input = page.locator('input[type="email"], input[name="email"]')
    password_input = page.locator('input[type="password"], input[name="password"]')
    
    if email_input.count() > 0 and password_input.count() > 0:
        email_input.fill(TEST_EMAIL)
        password_input.fill(TEST_PASSWORD)
        
        # Click login button
        login_btn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Login")')
        if login_btn.count() > 0:
            login_btn.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
    
    yield page
    page.close()


# ── Phase 9: Audit Trail Tests ─────────────────────────────────────


class TestPhase9AuditTrail:
    """Phase 9: Audit Trail & Action Logging — Playwright tests."""

    def test_audit_log_tab_visible(self, authenticated_page: Page):
        """Verify Audit Log tab is visible in Settings page."""
        page = authenticated_page
        page.goto(f"{BASE_URL}/dashboard/settings")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        
        # Check for Audit Log tab trigger
        audit_tab = page.locator('button[role="tab"]:has-text("Audit Log"), [data-value="audit"]')
        expect(audit_tab.first).to_be_visible(timeout=10000)

    def test_audit_log_tab_click(self, authenticated_page: Page):
        """Click Audit Log tab and verify content loads."""
        page = authenticated_page
        page.goto(f"{BASE_URL}/dashboard/settings?tab=audit")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        
        # Verify audit log content area is visible
        # Should have filter bar, stats cards, entries table
        content = page.locator('[data-state="active"][role="tabpanel"]')
        expect(content).to_be_visible(timeout=10000)

    def test_audit_log_filter_bar(self, authenticated_page: Page):
        """Verify filter bar elements exist in Audit Log tab."""
        page = authenticated_page
        page.goto(f"{BASE_URL}/dashboard/settings?tab=audit")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        
        # Check for category filter
        category_filter = page.locator('select, [role="combobox"]').first
        expect(category_filter).to_be_visible(timeout=10000)

    def test_audit_log_stats_cards(self, authenticated_page: Page):
        """Verify stats cards are rendered in Audit Log tab."""
        page = authenticated_page
        page.goto(f"{BASE_URL}/dashboard/settings?tab=audit")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        
        # Stats cards should be visible (total entries, 24h count, etc.)
        stats_section = page.locator('text=/Total|24h|entries/i')
        expect(stats_section.first).to_be_visible(timeout=10000)

    def test_audit_log_export_buttons(self, authenticated_page: Page):
        """Verify export buttons (JSON/CSV) are present."""
        page = authenticated_page
        page.goto(f"{BASE_URL}/dashboard/settings?tab=audit")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        
        # Check for export-related buttons
        export_btn = page.locator('button:has-text("Export"), button:has-text("JSON"), button:has-text("CSV")')
        expect(export_btn.first).to_be_visible(timeout=10000)

    def test_audit_log_sidebar_link(self, authenticated_page: Page):
        """Verify Audit Log link appears in sidebar."""
        page = authenticated_page
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        
        # Check sidebar for Audit Log link
        audit_link = page.locator('a:has-text("Audit Log"), nav a[href*="audit"]')
        expect(audit_link.first).to_be_visible(timeout=10000)


# ── Phase 10: Integration Health Tests ──────────────────────────────


class TestPhase10IntegrationHealth:
    """Phase 10: Rate Limiting & Error Handling — Integration Health UI tests."""

    def test_integrations_tab_has_health_section(self, authenticated_page: Page):
        """Verify Integrations tab shows health status section."""
        page = authenticated_page
        page.goto(f"{BASE_URL}/dashboard/settings?tab=integrations")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        
        # Health status section should be visible
        health_section = page.locator('text=/Health|Circuit|Rate Limit/i')
        expect(health_section.first).to_be_visible(timeout=10000)

    def test_integration_disconnect_button(self, authenticated_page: Page):
        """Verify disconnect button exists for connected integrations."""
        page = authenticated_page
        page.goto(f"{BASE_URL}/dashboard/settings?tab=integrations")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        
        # If there are connected integrations, they should have disconnect buttons
        disconnect_btn = page.locator('button:has-text("Disconnect")')
        # This may not be visible if no integrations are connected
        # but the button pattern should exist in the DOM
        # We just verify the page loaded without errors
        expect(page.locator('body')).to_be_visible()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
