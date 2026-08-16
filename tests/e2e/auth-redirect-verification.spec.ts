/**
 * PARWA Auth Redirect Verification — Playwright Test
 *
 * Verifies the user's stated rule:
 *   "if i have buyed subscrption liek vareints then only i shoudl go
 *    direclty to dashboard page other then that no i should be lnding
 *    page only."
 *
 * Scenarios covered:
 *   1. Email/password signup          → / (always — new user has no variants)
 *   2. Email/password login, no sub   → /
 *   3. Email/password login, has sub  → /dashboard
 *   4. Already-authed visits /login, no sub  → /
 *   5. Already-authed visits /login, has sub → /dashboard
 *   6. Already-authed visits /signup, no sub  → /
 *   7. Already-authed visits /signup, has sub → /dashboard
 *
 * Per CLAUDE.md Rule #5: "Never say it works unless you have PROVEN it works."
 * This test IS the proof.
 */

import { test, expect, Page, BrowserContext } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

// ── Mock data ──────────────────────────────────────────────────────────

const MOCK_USER_NO_SUB = {
  id: 'test-user-1',
  email: 'test-nosub@parwa-test.io',
  full_name: 'Test NoSub',
  is_verified: true,
};

const MOCK_USER_WITH_SUB = {
  id: 'test-user-2',
  email: 'test-withsub@parwa-test.io',
  full_name: 'Test WithSub',
  is_verified: true,
};

const MOCK_VARIANT_ITEM = {
  id: 'var-1',
  name: 'PARWA',
  variant_type: 'parwa',
  status: 'active',
};

// ── Helpers ────────────────────────────────────────────────────────────

/**
 * Set the parwa_at cookie so middleware allows navigation to /dashboard.
 * Middleware (src/middleware.ts) only checks for cookie existence, not
 * validity — the backend does the real verification.
 */
async function setAuthCookie(context: BrowserContext): Promise<void> {
  await context.addCookies([
    {
      name: 'parwa_at',
      value: 'mock-access-token',
      domain: 'localhost',
      path: '/',
    },
    {
      name: 'parwa_rt',
      value: 'mock-refresh-token',
      domain: 'localhost',
      path: '/',
    },
  ]);
}

/**
 * Intercept all auth-related API calls and respond with mocks.
 * `hasSubscription` controls whether /api/ai/instances returns a variant.
 */
async function installAuthMocks(
  page: Page,
  opts: {
    hasSubscription?: boolean;
    user?: typeof MOCK_USER_NO_SUB;
    seedLocalStorage?: boolean;
  } = {},
) {
  const { hasSubscription = false, user = MOCK_USER_NO_SUB, seedLocalStorage = false } = opts;

  // CATCH-ALL MOCK — must be registered FIRST so specific mocks (registered
  // later) take precedence. Playwright checks routes in reverse registration
  // order (most recent first), so the last-registered route wins.
  //
  // Without this, API calls from the dashboard/analytics pages hit the real
  // backend and return 401, which triggers the axios interceptor that clears
  // localStorage and bounces the user back to /login.
  await page.route('**/api/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, data: null }),
    });
  });

  // Mock the hydrate endpoint (called by AuthContext.initializeAuth)
  await page.route('**/api/auth/me-proxy', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(user),
    });
  });

  // Mock /api/auth/me (also used by some flows)
  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(user),
    });
  });

  // Mock /api/auth/check-email (used by signup form's email blur handler)
  await page.route('**/api/auth/check-email', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ available: true }),
    });
  });

  // Mock /api/auth/register
  await page.route('**/api/auth/register', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        user,
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        is_new_user: true,
      }),
    });
  });

  // Mock /api/auth/login
  await page.route('**/api/auth/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        user,
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        is_new_user: false,
      }),
    });
  });

  // Mock /api/auth/google
  await page.route('**/api/auth/google', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'success',
        user,
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        is_new_user: false,
      }),
    });
  });

  // Mock /api/ai/instances — the subscription check endpoint
  await page.route('**/api/ai/instances', async (route) => {
    const items = hasSubscription ? [MOCK_VARIANT_ITEM] : [];
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items, total: items.length }),
    });
  });

  // Mock /api/onboarding/state — dashboard checks this on mount and
  // redirects to /onboarding if status !== 'completed'. Return completed
  // so the dashboard renders for users WITH a subscription.
  await page.route('**/api/onboarding/state', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'completed', first_victory_completed: true }),
    });
  });

  // Pre-seed localStorage so AuthContext thinks user is already logged in
  if (seedLocalStorage) {
    await page.addInitScript((u) => {
      localStorage.setItem('parwa_user', JSON.stringify(u));
    }, user);
  }
}

/**
 * Wait for the page URL to stabilize after a redirect, then return it.
 * Hard navigation (window.location.href) takes a moment to complete.
 */
async function stableUrl(page: Page, timeout = 15000): Promise<string> {
  let lastUrl = page.url();
  let stableSince = Date.now();
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    await page.waitForTimeout(250);
    const current = page.url();
    if (current === lastUrl) {
      if (Date.now() - stableSince >= 1000) return current;
    } else {
      lastUrl = current;
      stableSince = Date.now();
    }
  }
  return lastUrl;
}

// ── Tests ──────────────────────────────────────────────────────────────

// Skip in CI (no server running)
const isCI = process.env.CI === 'true';
const describeOrSkip = isCI ? test.describe.skip : test.describe;
describeOrSkip('Auth Redirect Rule: dashboard ONLY if user has a variant subscription', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
  });

  // ── Scenario 1: Email/password signup → / (always) ──────────────────
  test('1. Email/password signup → landing page (/)', async ({ page }) => {
    await installAuthMocks(page, { hasSubscription: false, user: MOCK_USER_NO_SUB });

    await page.goto(`${BASE_URL}/signup`);
    await page.waitForLoadState('networkidle');

    // Fill the signup form
    await page.locator('input[name="email"]').fill(MOCK_USER_NO_SUB.email);
    // Trigger blur so check-email runs and emailAvailable becomes true
    await page.locator('input[name="email"]').blur();
    await page.waitForTimeout(500);

    await page.locator('input[name="full_name"]').fill(MOCK_USER_NO_SUB.full_name);
    await page.locator('input[name="company_name"]').fill('Test Co');
    await page.locator('select[name="industry"]').selectOption('saas');
    await page.locator('input[name="password"]').fill('StrongPass123!');
    await page.locator('input[name="confirm_password"]').fill('StrongPass123!');

    // Submit
    await page.locator('button[type="submit"]').click();

    // Wait for navigation to settle
    const finalUrl = await stableUrl(page);
    console.log(`[Test 1] Final URL: ${finalUrl}`);

    // Extract just the path
    const finalPath = new URL(finalUrl).pathname;
    expect(finalPath).toBe('/');
  });

  // ── Scenario 2: Email/password login, no subscription → / ───────────
  test('2. Email/password login (no subscription) → landing page (/)', async ({ page }) => {
    await installAuthMocks(page, { hasSubscription: false, user: MOCK_USER_NO_SUB });

    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');

    await page.locator('input[name="email"], input[type="email"]').first().fill(MOCK_USER_NO_SUB.email);
    await page.locator('input[type="password"]').first().fill('Test@1234');
    await page.locator('button[type="submit"]').click();

    const finalUrl = await stableUrl(page);
    console.log(`[Test 2] Final URL: ${finalUrl}`);
    const finalPath = new URL(finalUrl).pathname;
    expect(finalPath).toBe('/');
  });

  // ── Scenario 3: Email/password login, WITH subscription → /dashboard ─
  test('3. Email/password login (with subscription) → /dashboard', async ({ page, context }) => {
    // Pre-set auth cookie so middleware allows /dashboard navigation
    await setAuthCookie(context);
    await installAuthMocks(page, { hasSubscription: true, user: MOCK_USER_WITH_SUB });

    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');

    await page.locator('input[name="email"], input[type="email"]').first().fill(MOCK_USER_WITH_SUB.email);
    await page.locator('input[type="password"]').first().fill('Test@1234');
    await page.locator('button[type="submit"]').click();

    const finalUrl = await stableUrl(page);
    console.log(`[Test 3] Final URL: ${finalUrl}`);
    const finalPath = new URL(finalUrl).pathname;
    expect(finalPath).toBe('/dashboard');
  });

  // ── Scenario 4: Already-authed visits /login, no subscription → / ───
  // This simulates a Google login result where the user lands back on /login
  // with localStorage populated but no variant subscription.
  test('4. Already-authed visits /login, no sub → /', async ({ page, context }) => {
    await setAuthCookie(context);
    await installAuthMocks(page, {
      hasSubscription: false,
      user: MOCK_USER_NO_SUB,
      seedLocalStorage: true,
    });

    await page.goto(`${BASE_URL}/login`);
    const finalUrl = await stableUrl(page);
    console.log(`[Test 4] Final URL: ${finalUrl}`);
    const finalPath = new URL(finalUrl).pathname;
    expect(finalPath).toBe('/');
  });

  // ── Scenario 5: Already-authed visits /login, WITH subscription → /dashboard ─
  test('5. Already-authed visits /login, has sub → /dashboard', async ({ page, context }) => {
    await setAuthCookie(context);
    await installAuthMocks(page, {
      hasSubscription: true,
      user: MOCK_USER_WITH_SUB,
      seedLocalStorage: true,
    });

    await page.goto(`${BASE_URL}/login`);
    const finalUrl = await stableUrl(page);
    console.log(`[Test 5] Final URL: ${finalUrl}`);
    const finalPath = new URL(finalUrl).pathname;
    expect(finalPath).toBe('/dashboard');
  });

  // ── Scenario 6: Already-authed visits /signup, no subscription → / ──
  test('6. Already-authed visits /signup, no sub → /', async ({ page, context }) => {
    await setAuthCookie(context);
    await installAuthMocks(page, {
      hasSubscription: false,
      user: MOCK_USER_NO_SUB,
      seedLocalStorage: true,
    });

    await page.goto(`${BASE_URL}/signup`);
    const finalUrl = await stableUrl(page);
    console.log(`[Test 6] Final URL: ${finalUrl}`);
    const finalPath = new URL(finalUrl).pathname;
    expect(finalPath).toBe('/');
  });

  // ── Scenario 7: Already-authed visits /signup, WITH subscription → /dashboard ─
  test('7. Already-authed visits /signup, has sub → /dashboard', async ({ page, context }) => {
    await setAuthCookie(context);
    await installAuthMocks(page, {
      hasSubscription: true,
      user: MOCK_USER_WITH_SUB,
      seedLocalStorage: true,
    });

    await page.goto(`${BASE_URL}/signup`);
    const finalUrl = await stableUrl(page);
    console.log(`[Test 7] Final URL: ${finalUrl}`);
    const finalPath = new URL(finalUrl).pathname;
    expect(finalPath).toBe('/dashboard');
  });
});

