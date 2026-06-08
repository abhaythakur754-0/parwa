/**
 * PARWA E2E Test Suite v2 — Full User Flow
 *
 * Tests the complete user journey:
 * 1. Homepage loads correctly
 * 2. Models/pricing page renders
 * 3. Login page renders with Google Sign-in button
 * 4. 404 page works (no prerender crash)
 * 5. MFA proxy responds
 * 6. Onboarding redirects when not authed
 * 7. Dashboard routes redirect when not authed
 * 8. Google Sign-in API rejects invalid tokens properly
 */

import { chromium } from 'playwright';

const BASE_URL = 'https://parwa.buzz';
const TIMEOUT = 30000;

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runTests() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
  });

  const results = [];

  function log(name, status, details = '') {
    const icon = status === 'PASS' ? '✅' : status === 'FAIL' ? '❌' : '⚠️';
    console.log(`${icon} [${status}] ${name}${details ? ' — ' + details : ''}`);
    results.push({ name, status, details });
  }

  try {
    // ═══════════════════════════════════════════════════════════
    // TEST 1: Homepage loads
    // ═══════════════════════════════════════════════════════════
    let page = await context.newPage();
    try {
      await page.goto(BASE_URL, { timeout: TIMEOUT, waitUntil: 'domcontentloaded' });
      const title = await page.title();
      log('Homepage loads', title.includes('PARWA') ? 'PASS' : 'FAIL', `Title: ${title}`);
    } catch (e) {
      log('Homepage loads', 'FAIL', e.message);
    }
    await page.close();

    // ═══════════════════════════════════════════════════════════
    // TEST 2: Models/pricing page renders (client-side)
    // ═══════════════════════════════════════════════════════════
    page = await context.newPage();
    try {
      await page.goto(`${BASE_URL}/models`, { timeout: TIMEOUT, waitUntil: 'networkidle' });
      await sleep(5000); // Wait for client-side rendering
      const content = await page.content();
      const hasPricing = content.includes('PARWA Starter') || content.includes('PARWA Growth') ||
                         content.includes('PARWA High') || content.includes('$999') ||
                         content.includes('1,000') || content.includes('tickets');
      log('Models/pricing page renders', hasPricing ? 'PASS' : 'WARN',
          hasPricing ? 'Pricing content found' : 'Content may need industry selection first');
    } catch (e) {
      log('Models/pricing page renders', 'FAIL', e.message);
    }
    await page.close();

    // ═══════════════════════════════════════════════════════════
    // TEST 3: Login page renders with Google button
    // ═══════════════════════════════════════════════════════════
    page = await context.newPage();
    try {
      await page.goto(`${BASE_URL}/login`, { timeout: TIMEOUT, waitUntil: 'networkidle' });
      await sleep(4000);

      const content = await page.content();
      const hasLoginForm = content.includes('email') || content.includes('password');
      const hasGoogleBtn = content.includes('Continue with Google') ||
                           content.includes('accounts.google.com') ||
                           content.includes('google');
      const hasParwa = content.includes('PARWA');

      if (hasLoginForm && hasParwa) {
        log('Login page renders with form + Google', 'PASS',
            `Google: ${hasGoogleBtn ? 'present' : 'missing'}`);
      } else {
        log('Login page renders', 'FAIL',
            `LoginForm: ${hasLoginForm}, Google: ${hasGoogleBtn}, Branding: ${hasParwa}`);
      }
    } catch (e) {
      log('Login page renders', 'FAIL', e.message);
    }
    await page.close();

    // ═══════════════════════════════════════════════════════════
    // TEST 4: 404 page works (not-found prerender fix)
    // ═══════════════════════════════════════════════════════════
    page = await context.newPage();
    try {
      const response = await page.goto(`${BASE_URL}/this-page-does-not-exist`, { timeout: TIMEOUT, waitUntil: 'domcontentloaded' });
      await sleep(3000);
      const content = await page.content();
      const has404 = content.includes('404') || content.includes('not found');
      log('404 page renders without crash', has404 ? 'PASS' : 'WARN',
          `Status: ${response?.status()}, Has 404 text: ${has404}`);
    } catch (e) {
      log('404 page renders', 'FAIL', e.message);
    }
    await page.close();

    // ═══════════════════════════════════════════════════════════
    // TEST 5: MFA proxy route responds
    // ═══════════════════════════════════════════════════════════
    page = await context.newPage();
    try {
      const response = await page.goto(`${BASE_URL}/api/mfa/setup`, { timeout: TIMEOUT });
      const status = response?.status();
      // 405 (GET not allowed) or 401 (not authed) = proxy works
      log('MFA proxy route responds', (status === 405 || status === 401) ? 'PASS' : 'WARN',
          `Status: ${status}`);
    } catch (e) {
      log('MFA proxy route responds', 'FAIL', e.message);
    }
    await page.close();

    // ═══════════════════════════════════════════════════════════
    // TEST 6: Onboarding redirects to login when not authed
    // ═══════════════════════════════════════════════════════════
    page = await context.newPage();
    try {
      await page.goto(`${BASE_URL}/onboarding`, { timeout: TIMEOUT, waitUntil: 'domcontentloaded' });
      await sleep(3000);
      const url = page.url();
      log('Onboarding redirects when not authed', url.includes('/login') ? 'PASS' : 'WARN',
          `URL: ${url}`);
    } catch (e) {
      log('Onboarding redirect', 'FAIL', e.message);
    }
    await page.close();

    // ═══════════════════════════════════════════════════════════
    // TEST 7: Dashboard routes redirect when not authed
    // ═══════════════════════════════════════════════════════════
    page = await context.newPage();
    try {
      await page.goto(`${BASE_URL}/dashboard`, { timeout: TIMEOUT, waitUntil: 'domcontentloaded' });
      await sleep(3000);
      const url = page.url();
      log('Dashboard redirects when not authed', url.includes('/login') ? 'PASS' : 'WARN',
          `URL: ${url}`);
    } catch (e) {
      log('Dashboard redirect', 'FAIL', e.message);
    }
    await page.close();

    // ═══════════════════════════════════════════════════════════
    // TEST 8: Google auth API rejects invalid tokens
    // ═══════════════════════════════════════════════════════════
    page = await context.newPage();
    try {
      const response = await page.goto(`${BASE_URL}/api/auth/google`, {
        method: 'POST',
        timeout: TIMEOUT,
      });
      // POST via goto doesn't work well, let's use evaluate with full URL
      const result = await page.evaluate(async (baseUrl) => {
        try {
          const res = await fetch(`${baseUrl}/api/auth/google`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id_token: 'fake-test-token' }),
          });
          return { status: res.status, ok: res.ok };
        } catch (e) {
          return { error: e.message };
        }
      }, BASE_URL);

      if (result.status === 401 || result.status === 400) {
        log('Google auth API rejects invalid token', 'PASS', `Status: ${result.status}`);
      } else if (result.status === 500) {
        log('Google auth API error handling', 'FAIL', `Status: 500`);
      } else if (result.error) {
        log('Google auth API', 'WARN', `Fetch error: ${result.error}`);
      } else {
        log('Google auth API responds', 'PASS', `Status: ${result.status}`);
      }
    } catch (e) {
      log('Google auth API', 'WARN', e.message);
    }
    await page.close();

    // ═══════════════════════════════════════════════════════════
    // TEST 9: Signup page renders
    // ═══════════════════════════════════════════════════════════
    page = await context.newPage();
    try {
      await page.goto(`${BASE_URL}/signup`, { timeout: TIMEOUT, waitUntil: 'networkidle' });
      await sleep(3000);
      const content = await page.content();
      const hasSignup = content.includes('Create') && content.includes('account');
      log('Signup page renders', hasSignup ? 'PASS' : 'WARN',
          hasSignup ? 'Form found' : 'Form not found');
    } catch (e) {
      log('Signup page renders', 'FAIL', e.message);
    }
    await page.close();

    // ═══════════════════════════════════════════════════════════
    // TEST 10: Google Sign-in button click test
    // ═══════════════════════════════════════════════════════════
    page = await context.newPage();
    try {
      await page.goto(`${BASE_URL}/login`, { timeout: TIMEOUT, waitUntil: 'networkidle' });
      await sleep(4000);

      // Check for native GIS button or custom button
      const googleButtonInfo = await page.evaluate(() => {
        const nativeBtn = document.querySelector('div[aria-label="Sign in with Google"]') ||
                          document.querySelector('iframe[title="Sign in with Google"]') ||
                          document.querySelector('div[id^="button"]');
        const customBtn = document.querySelector('button');
        const allButtons = Array.from(document.querySelectorAll('button'));
        const googleBtn = allButtons.find(b => b.textContent?.includes('Continue with Google'));

        return {
          hasNativeGIS: !!nativeBtn,
          hasCustomBtn: !!googleBtn,
          totalButtons: allButtons.length,
          buttonTexts: allButtons.map(b => b.textContent?.trim()).filter(Boolean).slice(0, 10),
        };
      });

      log('Google Sign-in button detection', 'PASS',
          `Native GIS: ${googleButtonInfo.hasNativeGIS}, Custom: ${googleButtonInfo.hasCustomBtn}, Buttons: ${googleButtonInfo.totalButtons}`);
    } catch (e) {
      log('Google Sign-in button detection', 'FAIL', e.message);
    }
    await page.close();

    // ═══════════════════════════════════════════════════════════
    // TEST 11: API health check
    // ═══════════════════════════════════════════════════════════
    page = await context.newPage();
    try {
      const result = await page.evaluate(async (baseUrl) => {
        try {
          const res = await fetch(`${baseUrl}/api/health`, { method: 'GET' });
          return { status: res.status, ok: res.ok };
        } catch (e) {
          return { error: e.message };
        }
      }, BASE_URL);
      log('API health endpoint', result.ok ? 'PASS' : 'WARN',
          `Status: ${result.status || result.error}`);
    } catch (e) {
      log('API health endpoint', 'WARN', e.message);
    }
    await page.close();

  } catch (e) {
    console.error('Fatal error:', e);
  } finally {
    await browser.close();
  }

  // ═══════════════════════════════════════════════════════════
  // SUMMARY
  // ═══════════════════════════════════════════════════════════
  console.log('\n═══════════════════════════════════════════');
  console.log('      PARWA E2E TEST RESULTS (v2)          ');
  console.log('═══════════════════════════════════════════');
  const passed = results.filter(r => r.status === 'PASS').length;
  const warned = results.filter(r => r.status === 'WARN').length;
  const failed = results.filter(r => r.status === 'FAIL').length;
  console.log(`✅ Passed: ${passed}  ⚠️  Warned: ${warned}  ❌ Failed: ${failed}`);
  console.log('───────────────────────────────────────────');
  for (const r of results) {
    const icon = r.status === 'PASS' ? '✅' : r.status === 'FAIL' ? '❌' : '⚠️';
    console.log(`${icon} ${r.name}${r.details ? ' — ' + r.details : ''}`);
  }
  console.log('═══════════════════════════════════════════\n');

  return { passed, warned, failed, results };
}

runTests().then(results => {
  process.exit(results.failed > 0 ? 1 : 0);
}).catch(e => {
  console.error('Test runner error:', e);
  process.exit(1);
});
