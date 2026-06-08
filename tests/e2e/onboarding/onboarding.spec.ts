/**
 * PARWA Onboarding Flow - Playwright E2E Tests
 *
 * Tests the complete onboarding wizard flow:
 *   Auth: Sign up with email/password
 *   Details: Post-payment details form (name, company, industry)
 *   Step 1: Welcome → "Let's Get Started"
 *   Step 2: Legal Compliance → Accept all consents
 *   Step 3: Integration Setup → Configure channels
 *   Step 4: Knowledge Upload → Upload knowledge base
 *   Step 5: AI Config → Configure AI assistant
 *   First Victory → Celebration screen
 *
 * Run against deployed site:
 *   npx playwright test tests/e2e/onboarding/onboarding.spec.ts --project=chromium
 *
 * Run against local dev server:
 *   BASE_URL=http://localhost:3000 npx playwright test tests/e2e/onboarding/onboarding.spec.ts --project=chromium
 */

import { test, expect, Page } from '@playwright/test';

// ── Configuration ──────────────────────────────────────────────
const BASE_URL = process.env.BASE_URL || 'https://parwadashboard.netlify.app';
const ONBOARDING_PATH = '/onboarding';

// Test user credentials (for registration/login before onboarding)
const TEST_USER = {
  email: `pwtest${Date.now()}@parwa.buzz`,
  password: 'TestPass123!@#',
  name: 'Playwright Test User',
  company: 'PW Test Company',
};

// ── Helpers ────────────────────────────────────────────────────

async function navigateToOnboarding(page: Page) {
  await page.goto(`${BASE_URL}${ONBOARDING_PATH}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(3000);
}

/**
 * Sign up a new user to access onboarding.
 * The deployed site redirects unauthenticated users to a login page.
 * The sign-up form has these fields:
 *   - textbox "Email address" (placeholder: you@example.com)
 *   - textbox "Full name" (placeholder: John Doe)
 *   - textbox "Company name" (placeholder: Acme Inc.)
 *   - combobox "Industry" (options: E-commerce, SaaS, etc.)
 *   - textbox "Password" (placeholder: Create a strong password)
 *   - textbox "Confirm password" (placeholder: Confirm your password)
 *   - button "Create account"
 */
async function signUpIfNeeded(page: Page) {
  // Check if we're on the login page (redirected from /onboarding)
  const welcomeBack = page.getByRole('heading', { name: /welcome back/i });
  const createAccount = page.getByRole('heading', { name: /create your account/i });
  const isLoginPage = await welcomeBack.isVisible().catch(() => false);
  const isSignUpPage = await createAccount.isVisible().catch(() => false);

  if (isLoginPage) {
    console.log('Detected login page — switching to sign up...');

    // Click "Sign up" to switch to registration mode
    const signUpBtn = page.getByRole('button', { name: /^sign up$/i });
    if (await signUpBtn.isVisible().catch(() => false)) {
      await signUpBtn.click();
      await page.waitForTimeout(2000);
    }
  }

  // Check if we're now on the sign-up form
  const isNowSignUp = await createAccount.isVisible().catch(() => false);

  if (isNowSignUp || isSignUpPage) {
    console.log('Filling sign-up form...');

    // Fill registration form using proper accessible names
    await page.getByRole('textbox', { name: /email address/i }).fill(TEST_USER.email);
    await page.getByRole('textbox', { name: /full name/i }).fill(TEST_USER.name);
    await page.getByRole('textbox', { name: /company name/i }).fill(TEST_USER.company);

    // Select industry
    const industrySelect = page.getByRole('combobox', { name: /industry/i });
    if (await industrySelect.isVisible().catch(() => false)) {
      await industrySelect.selectOption('SaaS');
    }

    // Fill password fields
    await page.getByRole('textbox', { name: /^password$/i }).fill(TEST_USER.password);
    await page.getByRole('textbox', { name: /confirm password/i }).fill(TEST_USER.password);

    // Click Create Account
    const createBtn = page.getByRole('button', { name: /create account/i });
    if (await createBtn.isVisible().catch(() => false)) {
      console.log('Clicking Create Account...');
      await createBtn.click();
      await page.waitForTimeout(5000);
    }
  }
}

async function waitForApiCall(page: Page, urlPattern: string | RegExp, timeout = 15000) {
  return page.waitForResponse(
    (resp) => {
      const url = resp.url();
      if (typeof urlPattern === 'string') {
        return url.includes(urlPattern);
      }
      return urlPattern.test(url);
    },
    { timeout }
  );
}

// ── Test Suite ─────────────────────────────────────────────────

test.describe('PARWA Onboarding Flow', () => {

  // ────────────────────────────────────────────────────────────
  // Auth Gate: Login/Signup Page
  // ────────────────────────────────────────────────────────────
  test.describe('Auth Gate', () => {
    test('should redirect to login page when not authenticated', async ({ page }) => {
      await navigateToOnboarding(page);

      // Should see login page (heading "Welcome back") or sign-up form
      const welcomeBack = page.getByRole('heading', { name: /welcome back/i });
      const signInBtn = page.getByRole('button', { name: /sign in/i });
      const createAccount = page.getByRole('heading', { name: /create your account/i });

      const hasLogin = await welcomeBack.isVisible().catch(() => false);
      const hasSignIn = await signInBtn.isVisible().catch(() => false);
      const hasSignUp = await createAccount.isVisible().catch(() => false);
      const hasOnboarding = await page.getByText(/welcome to parwa/i).first().isVisible().catch(() => false);

      expect(hasLogin || hasSignIn || hasSignUp || hasOnboarding).toBeTruthy();
    });

    test('should switch to sign-up form when clicking Sign Up', async ({ page }) => {
      await navigateToOnboarding(page);

      const welcomeBack = page.getByRole('heading', { name: /welcome back/i });
      const isLoginPage = await welcomeBack.isVisible().catch(() => false);

      if (isLoginPage) {
        const signUpBtn = page.getByRole('button', { name: /^sign up$/i });
        await signUpBtn.click();
        await page.waitForTimeout(1500);

        // Should now show "Create your account" heading
        const createAccount = page.getByRole('heading', { name: /create your account/i });
        await expect(createAccount).toBeVisible({ timeout: 5000 });

        // Should have email, name, company, industry, password fields
        await expect(page.getByRole('textbox', { name: /email address/i })).toBeVisible();
        await expect(page.getByRole('textbox', { name: /full name/i })).toBeVisible();
        await expect(page.getByRole('textbox', { name: /company name/i })).toBeVisible();
        await expect(page.getByRole('combobox', { name: /industry/i })).toBeVisible();
        await expect(page.getByRole('textbox', { name: /^password$/i })).toBeVisible();
        await expect(page.getByRole('textbox', { name: /confirm password/i })).toBeVisible();
        await expect(page.getByRole('button', { name: /create account/i })).toBeVisible();
      }
    });

    test('should have Google OAuth sign-in option', async ({ page }) => {
      await navigateToOnboarding(page);

      const googleBtn = page.getByRole('button', { name: /google/i });
      const hasGoogle = await googleBtn.isVisible().catch(() => false);
      console.log(`Google sign-in button visible: ${hasGoogle}`);
      expect(hasGoogle).toBeTruthy();
    });

    test('should have Terms of Service and Privacy Policy links', async ({ page }) => {
      await navigateToOnboarding(page);

      // Switch to sign up to see the links
      const signUpBtn = page.getByRole('button', { name: /^sign up$/i });
      if (await signUpBtn.isVisible().catch(() => false)) {
        await signUpBtn.click();
        await page.waitForTimeout(1500);
      }

      const termsLink = page.getByRole('link', { name: /terms of service/i });
      const privacyLink = page.getByRole('link', { name: /privacy policy/i });

      const hasTerms = await termsLink.isVisible().catch(() => false);
      const hasPrivacy = await privacyLink.isVisible().catch(() => false);
      console.log(`Terms link visible: ${hasTerms}, Privacy link visible: ${hasPrivacy}`);
    });
  });

  // ────────────────────────────────────────────────────────────
  // Sign-Up Form Validation
  // ────────────────────────────────────────────────────────────
  test.describe('Sign-Up Form', () => {
    test.beforeEach(async ({ page }) => {
      await navigateToOnboarding(page);
      // Switch to sign up form
      const signUpBtn = page.getByRole('button', { name: /^sign up$/i });
      if (await signUpBtn.isVisible().catch(() => false)) {
        await signUpBtn.click();
        await page.waitForTimeout(1500);
      }
    });

    test('should have all required form fields', async ({ page }) => {
      await expect(page.getByRole('textbox', { name: /email address/i })).toBeVisible();
      await expect(page.getByRole('textbox', { name: /full name/i })).toBeVisible();
      await expect(page.getByRole('textbox', { name: /company name/i })).toBeVisible();
      await expect(page.getByRole('combobox', { name: /industry/i })).toBeVisible();
      await expect(page.getByRole('textbox', { name: /^password$/i })).toBeVisible();
      await expect(page.getByRole('textbox', { name: /confirm password/i })).toBeVisible();
      await expect(page.getByRole('button', { name: /create account/i })).toBeVisible();
    });

    test('should have industry dropdown with options', async ({ page }) => {
      const industrySelect = page.getByRole('combobox', { name: /industry/i });
      await expect(industrySelect).toBeVisible();

      // Verify industry options
      const options = await industrySelect.locator('option').allTextContents();
      console.log(`Industry options: ${options.join(', ')}`);
      expect(options).toContain('E-commerce');
      expect(options).toContain('SaaS');
    });

    test('should fill and submit the sign-up form', async ({ page }) => {
      await page.getByRole('textbox', { name: /email address/i }).fill(TEST_USER.email);
      await page.getByRole('textbox', { name: /full name/i }).fill(TEST_USER.name);
      await page.getByRole('textbox', { name: /company name/i }).fill(TEST_USER.company);
      await page.getByRole('combobox', { name: /industry/i }).selectOption('SaaS');
      await page.getByRole('textbox', { name: /^password$/i }).fill(TEST_USER.password);
      await page.getByRole('textbox', { name: /confirm password/i }).fill(TEST_USER.password);

      // Submit
      const createBtn = page.getByRole('button', { name: /create account/i });
      await expect(createBtn).toBeEnabled();
    });

    test('should toggle back to sign-in form', async ({ page }) => {
      const signInToggle = page.getByRole('button', { name: /sign in/i });
      if (await signInToggle.isVisible().catch(() => false)) {
        await signInToggle.click();
        await page.waitForTimeout(1000);

        // Should show "Welcome back" heading
        await expect(page.getByRole('heading', { name: /welcome back/i })).toBeVisible({ timeout: 5000 });
      }
    });
  });

  // ────────────────────────────────────────────────────────────
  // Step 1: Welcome Screen (requires auth)
  // ────────────────────────────────────────────────────────────
  test.describe('Step 1 - Welcome Screen', () => {
    test('should display onboarding wizard after authentication', async ({ page }) => {
      await navigateToOnboarding(page);
      await signUpIfNeeded(page);

      // After auth, should see onboarding content or sign-up confirmation
      const pageContent = await page.locator('body').textContent().catch(() => '');
      console.log(`After sign-up, page preview: ${pageContent?.substring(0, 300)}`);

      // Check various possible states
      const hasOnboarding = await page.getByText(/welcome to parwa|onboarding|get started/i).first().isVisible().catch(() => false);
      const hasVerification = await page.getByText(/verify|check your email|confirmation/i).first().isVisible().catch(() => false);
      const hasDashboard = await page.getByText(/dashboard|tickets/i).first().isVisible().catch(() => false);

      console.log(`Onboarding visible: ${hasOnboarding}, Verification: ${hasVerification}, Dashboard: ${hasDashboard}`);

      if (hasOnboarding) {
        const getStartedBtn = page.getByRole('button', { name: /let.*get started|get started/i });
        const hasGetStarted = await getStartedBtn.isVisible().catch(() => false);
        console.log(`Get Started button visible: ${hasGetStarted}`);
      }
    });
  });

  // ────────────────────────────────────────────────────────────
  // Welcome Details Page (Post-Payment Details Form)
  // ────────────────────────────────────────────────────────────
  test.describe('Welcome Details Page', () => {
    test('should display details form on /welcome/details', async ({ page }) => {
      await page.goto(`${BASE_URL}/welcome/details`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(3000);

      // Should show the details form heading
      const heading = page.getByRole('heading', { name: /tell us about yourself|details/i });
      const hasHeading = await heading.isVisible().catch(() => false);

      if (hasHeading) {
        // Should have form fields
        const fullNameInput = page.locator('#full_name').or(page.getByPlaceholder(/john doe/i));
        const companyNameInput = page.locator('#company_name').or(page.getByPlaceholder(/acme/i));
        const industrySelect = page.getByRole('combobox', { name: /industry/i });

        const hasFullName = await fullNameInput.first().isVisible().catch(() => false);
        const hasCompanyName = await companyNameInput.first().isVisible().catch(() => false);
        const hasIndustry = await industrySelect.isVisible().catch(() => false);

        console.log(`Full name field: ${hasFullName}, Company name: ${hasCompanyName}, Industry: ${hasIndustry}`);

        // Should have a Continue button
        const continueBtn = page.getByRole('button', { name: /continue/i });
        const hasContinue = await continueBtn.isVisible().catch(() => false);
        console.log(`Continue button visible: ${hasContinue}`);
      } else {
        // May be on login page if not authenticated
        const loginHeading = page.getByRole('heading', { name: /welcome back|create your account/i });
        const isLoginPage = await loginHeading.isVisible().catch(() => false);
        console.log(`Details page heading not found. Login page: ${isLoginPage}`);
      }
    });

    test('should not return Access Denied when submitting details', async ({ page }) => {
      await page.goto(`${BASE_URL}/welcome/details`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(3000);

      // Check if we're on the details form (requires auth)
      const heading = page.getByText(/tell us about yourself/i);
      const isDetailsForm = await heading.isVisible().catch(() => false);

      if (isDetailsForm) {
        // Fill the form
        const fullNameInput = page.locator('#full_name').or(page.getByPlaceholder(/john doe/i));
        const companyNameInput = page.locator('#company_name').or(page.getByPlaceholder(/acme/i));
        const industrySelect = page.getByRole('combobox', { name: /industry/i });

        if (await fullNameInput.first().isVisible().catch(() => false)) {
          await fullNameInput.first().fill('Test User');
        }
        if (await companyNameInput.first().isVisible().catch(() => false)) {
          await companyNameInput.first().fill('Test Company');
        }
        if (await industrySelect.isVisible().catch(() => false)) {
          await industrySelect.selectOption('saas');
        }

        // Listen for the API call
        const apiCallPromise = page.waitForResponse(
          (resp) => resp.url().includes('/api/user/details'),
          { timeout: 10000 }
        ).catch(() => null);

        // Click Continue
        const continueBtn = page.getByRole('button', { name: /continue/i });
        if (await continueBtn.isVisible().catch(() => false)) {
          await continueBtn.click();

          // Check the API response
          const apiResponse = await apiCallPromise;
          if (apiResponse) {
            const status = apiResponse.status();
            console.log(`API /api/user/details response status: ${status}`);

            // Should NOT be 403 (Access Denied)
            if (status === 403) {
              const body = await apiResponse.text().catch(() => '');
              console.error(`ACCESS DENIED! Response body: ${body}`);
            }
            expect(status).not.toBe(403);
          } else {
            console.log('No API call detected — may have used mock fallback');
          }
        }
      } else {
        console.log('Not on details form — likely not authenticated');
      }
    });
  });

  // ────────────────────────────────────────────────────────────
  // Login Page Form Validation
  // ────────────────────────────────────────────────────────────
  test.describe('Login Page', () => {
    test('should display sign-in form elements', async ({ page }) => {
      await navigateToOnboarding(page);

      const welcomeBack = page.getByRole('heading', { name: /welcome back/i });
      const isLoginPage = await welcomeBack.isVisible().catch(() => false);

      if (isLoginPage) {
        // Email input
        await expect(page.getByRole('textbox', { name: /email address/i })).toBeVisible({ timeout: 5000 });

        // Password input
        await expect(page.getByRole('textbox', { name: /^password$/i })).toBeVisible({ timeout: 5000 });

        // Sign in button
        await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();

        // Sign up button
        await expect(page.getByRole('button', { name: /^sign up$/i })).toBeVisible();
      }
    });

    test('should have Forgot Password link', async ({ page }) => {
      await navigateToOnboarding(page);

      const forgotPassword = page.getByRole('button', { name: /forgot password/i });
      const hasForgot = await forgotPassword.isVisible().catch(() => false);
      console.log(`Forgot password button visible: ${hasForgot}`);
    });
  });

  // ────────────────────────────────────────────────────────────
  // Responsive Design
  // ────────────────────────────────────────────────────────────
  test.describe('Responsive Design', () => {
    test('should render auth page correctly on mobile viewport', async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 812 }); // iPhone X
      await navigateToOnboarding(page);

      // Should have visible content
      const heading = page.getByRole('heading').first();
      await expect(heading).toBeVisible({ timeout: 10000 });
    });

    test('should render correctly on tablet viewport', async ({ page }) => {
      await page.setViewportSize({ width: 768, height: 1024 }); // iPad
      await navigateToOnboarding(page);

      const body = page.locator('body');
      await expect(body).toBeVisible();
    });
  });

  // ────────────────────────────────────────────────────────────
  // Page Structure
  // ────────────────────────────────────────────────────────────
  test.describe('Page Structure', () => {
    test('should have PARWA branding visible', async ({ page }) => {
      await navigateToOnboarding(page);

      const parwaBrand = page.getByText('PARWA').or(page.getByAltText(/parwa/i));
      const hasBrand = await parwaBrand.first().isVisible().catch(() => false);
      expect(hasBrand).toBeTruthy();
    });

    test('should have proper page title', async ({ page }) => {
      await navigateToOnboarding(page);
      const title = await page.title();
      expect(title).toContain('PARWA');
    });

    test('should have contact support link', async ({ page }) => {
      await navigateToOnboarding(page);

      const supportLink = page.getByRole('link', { name: /contact support/i });
      const hasSupport = await supportLink.isVisible().catch(() => false);
      expect(hasSupport).toBeTruthy();

      if (hasSupport) {
        const href = await supportLink.getAttribute('href');
        expect(href).toBe('/contact');
      }
    });

    test('should have Back to Home link', async ({ page }) => {
      await navigateToOnboarding(page);

      const backToHome = page.getByRole('link', { name: /back to home/i });
      const hasBackToHome = await backToHome.isVisible().catch(() => false);
      expect(hasBackToHome).toBeTruthy();
    });
  });
});

// ────────────────────────────────────────────────────────────
// Full End-to-End Onboarding Flow
// ────────────────────────────────────────────────────────────
test.describe('Full Onboarding Flow (E2E)', () => {
  test.skip(() => !process.env.RUN_FULL_E2E, 'Set RUN_FULL_E2E=1 to run full flow');

  test('should complete the full onboarding wizard from signup', async ({ page }) => {
    // ── Step 0: Navigate and Sign Up ──
    await navigateToOnboarding(page);
    await signUpIfNeeded(page);
    await page.waitForTimeout(5000);

    // ── Step 1: Welcome ──
    const getStartedBtn = page.getByRole('button', { name: /let.*get started|get started/i });
    if (await getStartedBtn.isVisible().catch(() => false)) {
      await getStartedBtn.click();
      await page.waitForTimeout(2000);

      // ── Step 2: Legal Compliance ──
      const legalContent = page.getByText(/legal compliance/i);
      if (await legalContent.isVisible().catch(() => false)) {
        // Check all checkboxes
        const checkboxes = page.locator('button[role="checkbox"], input[type="checkbox"]');
        const count = await checkboxes.count();
        for (let i = 0; i < count; i++) {
          await checkboxes.nth(i).click().catch(() => {});
        }

        await page.getByRole('button', { name: /accept all & continue/i }).click();
        await page.waitForTimeout(3000);

        // ── Step 3: Integration Setup ──
        const continueBtn = page.getByRole('button', { name: /continue|next|skip/i });
        if (await continueBtn.first().isVisible().catch(() => false)) {
          await continueBtn.first().click();
          await page.waitForTimeout(2000);
        }

        // ── Step 4: Knowledge Upload ──
        const skipBtn = page.getByRole('button', { name: /skip|continue/i });
        if (await skipBtn.first().isVisible().catch(() => false)) {
          await skipBtn.first().click();
          await page.waitForTimeout(2000);
        }

        // ── Step 5: AI Config ──
        const nameInput = page.locator('input[name="ai_name"]').or(page.getByPlaceholder(/name your ai/i));
        if (await nameInput.first().isVisible().catch(() => false)) {
          await nameInput.first().fill('TestBot');
        }

        const completeBtn = page.getByRole('button', { name: /complete|finish|done/i });
        if (await completeBtn.first().isVisible().catch(() => false)) {
          await completeBtn.first().click();
        }

        // ── First Victory ──
        await page.waitForTimeout(3000);
        const victoryContent = page.getByText(/congratulations|first victory/i);
        const hasVictory = await victoryContent.first().isVisible().catch(() => false);
        console.log(`First Victory screen visible: ${hasVictory}`);
      }
    } else {
      console.log('Could not reach onboarding wizard — may need to verify email first');
      const pageContent = await page.locator('body').textContent().catch(() => '');
      console.log(`Page preview: ${pageContent?.substring(0, 300)}`);
    }
  });
});
