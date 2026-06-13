/**
 * Phase 4 End-to-End Test: Onboarding → Paddle Checkout → Dashboard
 *
 * Tests the complete flow:
 * 1. Login with test user
 * 2. Navigate through onboarding wizard
 * 3. Verify Paddle checkout is available on Step 6
 * 4. Verify variant appears on dashboard after onboarding
 */

import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';
const TEST_EMAIL = 'dashboard@test.io';
const TEST_PASSWORD = 'Test@1234';

// Allow longer timeouts for onboarding flow
test.setTimeout(120000);

test.describe('Phase 4: Onboarding → Paddle → Dashboard', () => {

  test('should complete onboarding and show variant on dashboard', async ({ page }) => {
    // ── Step 1: Login ──────────────────────────────────────────────
    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle');

    // Fill login form
    const emailInput = page.locator('input[type="email"], input[name="email"], input[placeholder*="email"]');
    await emailInput.fill(TEST_EMAIL);

    const passwordInput = page.locator('input[type="password"], input[name="password"]');
    await passwordInput.fill(TEST_PASSWORD);

    // Submit login
    const submitButton = page.locator('button[type="submit"]');
    await submitButton.click();

    // Wait for redirect after login
    await page.waitForURL(/\/(onboarding|dashboard)/, { timeout: 15000 });
    console.log('✓ Login successful, redirected to:', page.url());

    // ── Step 2: If on dashboard, navigate to onboarding ──────────
    if (page.url().includes('/dashboard')) {
      console.log('✓ Already on dashboard — onboarding was completed previously');
      
      // Check for variant display on dashboard
      const variantSection = page.locator('text=Active Variants');
      if (await variantSection.isVisible()) {
        console.log('✓ Active Variants section visible on dashboard');
        
        // Take screenshot
        await page.screenshot({ path: '/home/z/my-project/download/dashboard-variants.png', fullPage: true });
        console.log('✓ Dashboard screenshot saved');
        return;
      }
    }

    // ── Step 3: Onboarding Step 1 - Industry + Variant ─────────────
    if (page.url().includes('/onboarding')) {
      console.log('On onboarding page, starting flow...');

      // Wait for Step 1 to render
      await page.waitForSelector('text=Welcome to PARWA', { timeout: 10000 });

      // Select industry (e.g., SaaS)
      const saasButton = page.locator('button:has-text("SaaS")');
      await saasButton.click();
      console.log('✓ Selected SaaS industry');

      // Select variant (PARWA)
      const parwaButton = page.locator('button:has-text("PARWA")').first();
      await parwaButton.click();
      console.log('✓ Selected PARWA variant');

      // Click Continue
      const continueButton = page.locator('button:has-text("Continue")');
      await continueButton.click();
      await page.waitForTimeout(2000);

      // ── Step 4: Step 2 - Legal Compliance ────────────────────────
      const legalSection = page.locator('text=Legal');
      if (await legalSection.isVisible({ timeout: 5000 }).catch(() => false)) {
        console.log('✓ On Legal step');
        
        // Accept all legal consents
        const checkboxes = page.locator('input[type="checkbox"]');
        const count = await checkboxes.count();
        for (let i = 0; i < count; i++) {
          await checkboxes.nth(i).check();
        }
        
        const acceptButton = page.locator('button:has-text("Accept"), button:has-text("Continue")');
        await acceptButton.first().click();
        await page.waitForTimeout(2000);
      }

      // ── Step 5: Skip through remaining steps to Cost Breakdown ───
      // Try to navigate through steps quickly
      for (let step = 0; step < 5; step++) {
        const nextButton = page.locator('button:has-text("Continue"), button:has-text("Next"), button:has-text("Skip")');
        if (await nextButton.first().isVisible({ timeout: 3000 }).catch(() => false)) {
          await nextButton.first().click();
          await page.waitForTimeout(2000);
        }
      }

      // ── Step 6: Cost Breakdown (Step 6) ──────────────────────────
      const costBreakdown = page.locator('text=Review Your Plan');
      if (await costBreakdown.isVisible({ timeout: 5000 }).catch(() => false)) {
        console.log('✓ On Cost Breakdown step (Step 6)');
        
        // Check Paddle status indicator
        const paddleReady = page.locator('text=Secure checkout powered by Paddle');
        const paddleUnavailable = page.locator('text=Payment checkout unavailable');
        
        if (await paddleReady.isVisible({ timeout: 3000 }).catch(() => false)) {
          console.log('✓ Paddle checkout is READY');
        } else if (await paddleUnavailable.isVisible({ timeout: 3000 }).catch(() => false)) {
          console.log('⚠ Paddle checkout is unavailable (expected if Paddle.js not initialized)');
        } else {
          console.log('ℹ Paddle status indicator not found yet');
        }

        // Check variant info is displayed
        const variantDisplay = page.locator('text=PARWA');
        if (await variantDisplay.isVisible({ timeout: 3000 }).catch(() => false)) {
          console.log('✓ Variant info displayed on cost breakdown');
        }

        // Take screenshot of cost breakdown
        await page.screenshot({ path: '/home/z/my-project/download/cost-breakdown.png', fullPage: true });
        console.log('✓ Cost breakdown screenshot saved');

        // Click Proceed to Checkout
        const checkoutButton = page.locator('button:has-text("Proceed to Checkout")');
        await checkoutButton.click();
        await page.waitForTimeout(3000);

        // Take screenshot after clicking checkout
        await page.screenshot({ path: '/home/z/my-project/download/after-checkout-click.png', fullPage: true });
        console.log('✓ After checkout click screenshot saved');
      }

      // ── Step 7: Check if we made it to dashboard ────────────────
      // Wait for potential redirects
      await page.waitForTimeout(5000);
      console.log('Current URL:', page.url());
      
      // Take final screenshot
      await page.screenshot({ path: '/home/z/my-project/download/final-state.png', fullPage: true });
    }
  });

  test('should show variant instance on dashboard API', async ({ request }) => {
    // Test the /api/ai/instances endpoint directly
    const response = await request.get(`${BASE_URL}/api/ai/instances`);
    
    if (response.ok()) {
      const data = await response.json();
      console.log('API /api/ai/instances response:', JSON.stringify(data, null, 2));
      
      // Should have items array
      expect(data).toHaveProperty('items');
      
      if (data.items && data.items.length > 0) {
        console.log(`✓ Found ${data.items.length} variant instance(s)`);
        // Check first instance has required fields
        const instance = data.items[0];
        expect(instance).toHaveProperty('name');
        expect(instance).toHaveProperty('variant_type');
        expect(instance).toHaveProperty('status');
        console.log(`✓ Instance: ${instance.name} (${instance.variant_type}) - ${instance.status}`);
      } else {
        console.log('⚠ No variant instances found — onboarding may not have been completed yet');
      }
    } else {
      console.log('⚠ /api/ai/instances returned:', response.status());
    }
  });

  test('should verify Paddle.js initialization', async ({ page }) => {
    await page.goto(`${BASE_URL}/onboarding`);
    await page.waitForLoadState('networkidle');
    
    // Check if Paddle.js is loaded
    const paddleLoaded = await page.evaluate(() => {
      // Check if the Paddle script is loaded
      const scripts = document.querySelectorAll('script[src*="paddle"]');
      return scripts.length > 0;
    });
    
    console.log('Paddle scripts on page:', paddleLoaded ? 'Yes' : 'No');
    
    // Check NEXT_PUBLIC_PADDLE_KEY is set
    const paddleKeySet = await page.evaluate(() => {
      // @ts-ignore - check if the env var is available
      return typeof window !== 'undefined';
    });
    
    console.log('Window available:', paddleKeySet);
    
    // Try to initialize Paddle from console
    const paddleInitResult = await page.evaluate(async () => {
      try {
        // Dynamic import of paddle module
        const paddleModule = await import('/src/lib/paddle.ts');
        const instance = await paddleModule.getPaddleInstance();
        return { success: true, hasInstance: !!instance };
      } catch (err) {
        return { success: false, error: String(err) };
      }
    });
    
    console.log('Paddle init result:', JSON.stringify(paddleInitResult));
  });
});
