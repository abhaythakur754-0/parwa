/**
 * PARWA Usage Warning Modal + Auto-Renewal — Playwright Test
 *
 * Verifies the user's request:
 *   "we need to show that 80 % perecnrt usage in dashbrad there ok as pop
 *    or there in dashbrad we create a main notication there"
 *
 * Per CLAUDE.md Rule #5: "Never say it works unless you have PROVEN it works."
 * This test IS the proof.
 *
 * Scenarios:
 *   1. Usage < 80%  → modal does NOT appear
 *   2. Usage >= 80% → modal appears with correct percentage + tickets
 *   3. Usage >= 100% → modal shows "Plan Limit Reached" header
 *   4. Click "Remind me later" → modal closes + stays closed on reload
 *   5. Click "Upgrade plan" → navigates to /dashboard/billing
 *   6. Realtime `billing:renewal_reminder` event → modal appears with renewal info
 *   7. Realtime `billing:usage_warning` event → modal appears with usage info
 */

import { test, expect, Page, BrowserContext } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

// ── Mock data ──────────────────────────────────────────────────────────

const MOCK_USER = {
  id: 'test-user-1',
  email: 'test@parwa-test.io',
  full_name: 'Test User',
  is_verified: true,
  company_id: 'comp-1',
};

// ── Helpers ────────────────────────────────────────────────────────────

async function setAuthCookie(context: BrowserContext): Promise<void> {
  await context.addCookies([
    { name: 'parwa_at', value: 'mock-access-token', domain: 'localhost', path: '/' },
    { name: 'parwa_rt', value: 'mock-refresh-token', domain: 'localhost', path: '/' },
  ]);
}

async function installAuthMocks(
  page: Page,
  opts: {
    usagePercentage?: number;
    ticketsUsed?: number;
    ticketLimit?: number;
    hasSubscription?: boolean;
  } = {},
) {
  const {
    usagePercentage = 0,
    ticketsUsed = 0,
    ticketLimit = 2000,
    hasSubscription = true,
  } = opts;

  // CATCH-ALL MOCK — must be FIRST so specific mocks override it
  await page.route('**/api/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, data: null }),
    });
  });

  // Auth mocks
  await page.route('**/api/auth/me-proxy', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_USER),
    });
  });

  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_USER),
    });
  });

  // Subscription check — hasSubscription=true so user lands on /dashboard
  await page.route('**/api/ai/instances', async (route) => {
    const items = hasSubscription ? [{ id: 'v1', variant_type: 'parwa', status: 'active' }] : [];
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items, total: items.length }),
    });
  });

  // Onboarding completed — so dashboard renders
  await page.route('**/api/onboarding/state', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'completed', first_victory_completed: true }),
    });
  });

  // Billing usage — the KEY mock for this test
  await page.route('**/api/billing/usage', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        current_month: '2025-06',
        tickets_used: ticketsUsed,
        ticket_limit: ticketLimit,
        overage_tickets: Math.max(0, ticketsUsed - ticketLimit),
        overage_charges: '0.00',
        usage_percentage: usagePercentage,
      }),
    });
  });

  // Pre-seed localStorage so AuthContext thinks user is logged in
  await page.addInitScript((u) => {
    localStorage.setItem('parwa_user', JSON.stringify(u));
  }, MOCK_USER);
}

// ── Tests ──────────────────────────────────────────────────────────────

// Skip in CI (no server running)
const isCI = process.env.CI === 'true';
const describeOrSkip = isCI ? test.describe.skip : test.describe;
describeOrSkip('Usage Warning Modal — 80% plan limit popup', () => {
  test.beforeEach(async ({ context }) => {
    await setAuthCookie(context);
  });

  test('1. Usage below 80% → modal does NOT appear', async ({ page }) => {
    await installAuthMocks(page, {
      usagePercentage: 45.5,
      ticketsUsed: 900,
      ticketLimit: 2000,
    });
    await page.goto(`${BASE_URL}/dashboard`);

    // Give the modal a moment to potentially appear
    await page.waitForTimeout(1500);

    const modal = page.locator('[data-testid="usage-warning-modal"]');
    await expect(modal).not.toBeVisible();
  });

  test('2. Usage at 80% → modal appears with correct numbers', async ({ page }) => {
    await installAuthMocks(page, {
      usagePercentage: 82.5,
      ticketsUsed: 1650,
      ticketLimit: 2000,
    });
    await page.goto(`${BASE_URL}/dashboard`);

    // Modal should appear
    const modal = page.locator('[data-testid="usage-warning-modal"]');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Verify the percentage is displayed
    const pct = page.locator('[data-testid="usage-percentage"]');
    await expect(pct).toBeVisible();
    await expect(pct).toContainText('82.5');

    // Verify ticket counts are shown
    await expect(modal).toContainText('1,650');
    await expect(modal).toContainText('2,000');

    // Verify title indicates "Approaching Plan Limit"
    await expect(modal).toContainText('Approaching Plan Limit');
  });

  test('3. Usage at 100%+ → modal shows "Plan Limit Reached"', async ({ page }) => {
    await installAuthMocks(page, {
      usagePercentage: 110.0,
      ticketsUsed: 2200,
      ticketLimit: 2000,
    });
    await page.goto(`${BASE_URL}/dashboard`);

    const modal = page.locator('[data-testid="usage-warning-modal"]');
    await expect(modal).toBeVisible({ timeout: 5000 });

    await expect(modal).toContainText('Plan Limit Reached');
  });

  test('4. Click "Remind me later" → modal closes and stays closed on reload', async ({ page }) => {
    await installAuthMocks(page, {
      usagePercentage: 85,
      ticketsUsed: 1700,
      ticketLimit: 2000,
    });
    await page.goto(`${BASE_URL}/dashboard`);

    const modal = page.locator('[data-testid="usage-warning-modal"]');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Click dismiss
    await page.locator('[data-testid="usage-warning-dismiss"]').click();
    await expect(modal).not.toBeVisible({ timeout: 2000 });

    // Reload page — modal should stay dismissed (sessionStorage)
    await page.reload();
    await page.waitForTimeout(1500);
    await expect(modal).not.toBeVisible();
  });

  test('5. Click "Upgrade plan" → navigates to /dashboard/billing', async ({ page }) => {
    await installAuthMocks(page, {
      usagePercentage: 85,
      ticketsUsed: 1700,
      ticketLimit: 2000,
    });
    await page.goto(`${BASE_URL}/dashboard`);

    const modal = page.locator('[data-testid="usage-warning-modal"]');
    await expect(modal).toBeVisible({ timeout: 5000 });

    await page.locator('[data-testid="usage-warning-upgrade"]').click();

    // Should navigate to /dashboard/billing
    await expect(page).toHaveURL(/\/dashboard\/billing/, { timeout: 5000 });
  });

  test('6. Realtime billing:renewal_reminder event → modal appears with renewal info', async ({ page }) => {
    // Even with usage < 80%, a renewal_reminder event should pop the modal
    await installAuthMocks(page, {
      usagePercentage: 30,
      ticketsUsed: 600,
      ticketLimit: 2000,
    });
    await page.goto(`${BASE_URL}/dashboard`);

    // Wait for any initial usage-check to complete
    await page.waitForTimeout(1500);
    const modal = page.locator('[data-testid="usage-warning-modal"]');
    await expect(modal).not.toBeVisible();

    // Dispatch a realtime renewal_reminder event
    await page.evaluate(() => {
      const detail = {
        event_type: 'billing:renewal_reminder',
        variant: 'growth',
        renewal_date: '2025-07-01',
        amount: '2499.00',
        message: 'Your growth plan renews on 2025-07-01. $2499.00 will be charged.',
      };
      window.dispatchEvent(new CustomEvent('parwa:billing-event', { detail }));
    });

    await expect(modal).toBeVisible({ timeout: 3000 });
    await expect(modal).toContainText('Subscription Renewing Soon');
    await expect(modal).toContainText('2025-07-01');
    await expect(modal).toContainText('2499.00');
  });

  test('7. Realtime billing:usage_warning event → modal appears with usage info', async ({ page }) => {
    // Start with usage < 80%
    await installAuthMocks(page, {
      usagePercentage: 50,
      ticketsUsed: 1000,
      ticketLimit: 2000,
    });
    await page.goto(`${BASE_URL}/dashboard`);

    await page.waitForTimeout(1500);
    const modal = page.locator('[data-testid="usage-warning-modal"]');
    await expect(modal).not.toBeVisible();

    // Backend just emitted a usage_warning (e.g. daily check at 09:00 UTC)
    await page.evaluate(() => {
      const detail = {
        event_type: 'billing:usage_warning',
        usage_percentage: 87.5,
        tickets_used: 1750,
        ticket_limit: 2000,
      };
      window.dispatchEvent(new CustomEvent('parwa:billing-event', { detail }));
    });

    await expect(modal).toBeVisible({ timeout: 3000 });
    await expect(modal).toContainText('87.5');
    await expect(modal).toContainText('Approaching Plan Limit');
  });
});
