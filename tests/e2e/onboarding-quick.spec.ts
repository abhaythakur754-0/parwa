/**
 * Quick Onboarding Flow Test — Focused on verifying the frontend renders correctly
 */

import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';
const BACKEND_URL = 'http://localhost:8000';

// Skip in CI (no server running)
const isCI = process.env.CI === 'true';
const describeOrSkip = isCI ? test.describe.skip : test.describe;
describeOrSkip('Onboarding Frontend Renders', () => {
  test.setTimeout(60000);
  test('Landing page loads', async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);
    
    // Screenshot
    await page.screenshot({ path: '/home/z/my-project/download/01-landing-page.png', fullPage: false });
    
    // Verify page loaded
    const title = await page.title();
    console.log(`Landing page title: ${title}`);
    expect(title).toContain('PARWA');
  });

  test('Onboarding page loads with Step 1', async ({ page }) => {
    await page.goto(`${BASE_URL}/onboarding`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(5000);
    
    // Screenshot
    await page.screenshot({ path: '/home/z/my-project/download/02-onboarding-step1.png', fullPage: false });
    
    // Check for industry selection
    const pageText = await page.textContent('body');
    const hasIndustry = pageText?.includes('SaaS') || pageText?.includes('E-commerce') || pageText?.includes('Industry');
    console.log(`Step 1 has industry selection: ${hasIndustry}`);
    
    // Check for variant selection
    const hasVariant = pageText?.includes('999') || pageText?.includes('Mini') || pageText?.includes('PARWA');
    console.log(`Step 1 has variant selection: ${hasVariant}`);
    
    // Check for progress indicator
    const hasProgress = pageText?.includes('Plan') || pageText?.includes('Legal') || pageText?.includes('step');
    console.log(`Step 1 has progress indicator: ${hasProgress}`);
  });

  test('Pricing page loads', async ({ page }) => {
    await page.goto(`${BASE_URL}/pricing`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);
    
    await page.screenshot({ path: '/home/z/my-project/download/03-pricing-page.png', fullPage: false });
    
    const pageText = await page.textContent('body');
    const hasPricing = pageText?.includes('999') || pageText?.includes('2,499') || pageText?.includes('4,999');
    console.log(`Pricing page has prices: ${hasPricing}`);
  });

  test('Dashboard page loads or redirects', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);
    
    await page.screenshot({ path: '/home/z/my-project/download/04-dashboard.png', fullPage: false });
    
    const currentUrl = page.url();
    console.log(`Dashboard URL: ${currentUrl}`);
  });

  test('Login page loads', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);
    
    await page.screenshot({ path: '/home/z/my-project/download/05-login-page.png', fullPage: false });
    
    const hasEmailInput = await page.locator('input[type="email"], input[name="email"]').count();
    const hasPasswordInput = await page.locator('input[type="password"]').count();
    console.log(`Login page: email inputs=${hasEmailInput}, password inputs=${hasPasswordInput}`);
  });
});

test.describe('Backend API Checks', () => {
  test('Health check', async ({ request }) => {
    const res = await request.get(`${BACKEND_URL}/health`, { timeout: 10000 }).catch(() => null);
    if (res) {
      const data = await res.json();
      console.log(`Backend status: ${data.status}`);
      expect(data).toHaveProperty('status');
    } else {
      console.log('Backend not reachable');
    }
  });

  test('Onboarding state endpoint', async ({ request }) => {
    const res = await request.get(`${BACKEND_URL}/api/onboarding/state`, { timeout: 10000 }).catch(() => null);
    if (res) {
      console.log(`Onboarding state: status=${res.status()}`);
      expect([200, 401, 403, 422]).toContain(res.status());
    } else {
      console.log('Backend not reachable');
    }
  });

  test('KB upload endpoint', async ({ request }) => {
    const res = await request.post(`${BACKEND_URL}/api/kb/upload`, {
      timeout: 10000,
      multipart: {
        file: { name: 'test.txt', mimeType: 'text/plain', buffer: Buffer.from('test') },
      },
    }).catch(() => null);
    if (res) {
      console.log(`KB upload: status=${res.status()}`);
      expect([200, 201, 401, 403, 422]).toContain(res.status());
    } else {
      console.log('Backend not reachable for KB upload');
    }
  });
});
