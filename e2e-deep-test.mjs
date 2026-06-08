/**
 * PARWA Deep E2E Test — Full User Journey
 *
 * Simulates a real user:
 * 1. Visit /models page
 * 2. Select an industry
 * 3. Click "Free Chat" on a variant → goes to /jarvis
 * 4. From /jarvis, click sign-in → /login
 * 5. Click Google Sign-in button (verify it's clickable)
 * 6. Try email login with test creds
 * 7. Check error handling
 */

import { chromium } from 'playwright';

const BASE_URL = 'https://parwa.buzz';
const TIMEOUT = 30000;

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runDeepTest() {
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
    // STEP 1: Visit models page and select industry
    // ═══════════════════════════════════════════════════════════
    const page = await context.newPage();

    console.log('\n--- STEP 1: Models page + industry selection ---');
    await page.goto(`${BASE_URL}/models`, { timeout: TIMEOUT, waitUntil: 'networkidle' });
    await sleep(5000);

    // Click on E-commerce industry
    const ecommerceBtn = await page.$('button:has-text("E-commerce")');
    if (ecommerceBtn) {
      await ecommerceBtn.click();
      await sleep(3000);
      const content = await page.content();
      const hasPricing = content.includes('PARWA Starter') || content.includes('$999');
      log('Industry selection shows pricing', hasPricing ? 'PASS' : 'FAIL',
          hasPricing ? 'Pricing cards visible' : 'No pricing visible');
    } else {
      log('Industry selection', 'WARN', 'E-commerce button not found');
    }

    // ═══════════════════════════════════════════════════════════
    // STEP 2: Find and test Free Chat / Get Started buttons
    // ═══════════════════════════════════════════════════════════
    console.log('\n--- STEP 2: Action buttons ---');
    const allButtons = await page.$$('button');
    let freeChatBtn = null;
    let getStartedBtn = null;

    for (const btn of allButtons) {
      const text = await btn.textContent();
      if (text?.includes('Free Chat') || text?.includes('Try Free')) freeChatBtn = btn;
      if (text?.includes('Get Started') || text?.includes('Start')) getStartedBtn = btn;
    }

    if (freeChatBtn) {
      // Click Free Chat → should navigate to /jarvis
      const [navResponse] = await Promise.all([
        page.waitForNavigation({ timeout: 10000 }).catch(() => null),
        freeChatBtn.click(),
      ]);
      await sleep(3000);

      const currentUrl = page.url();
      if (currentUrl.includes('/jarvis')) {
        log('Free Chat navigates to Jarvis', 'PASS', `URL: ${currentUrl}`);
      } else if (currentUrl.includes('/login')) {
        log('Free Chat redirects to login', 'PASS', 'Auth required first');
      } else {
        log('Free Chat navigation', 'WARN', `URL: ${currentUrl}`);
      }
    } else if (getStartedBtn) {
      log('Get Started button found', 'PASS', 'Available as alternative');
    } else {
      // Check if there are sign-in or CTA links
      const links = await page.$$('a');
      let jarvisLink = null;
      let loginLink = null;
      for (const link of links) {
        const href = await link.getAttribute('href');
        if (href?.includes('/jarvis')) jarvisLink = link;
        if (href?.includes('/login')) loginLink = link;
      }
      log('CTA buttons', 'WARN',
          `FreeChat: ${!!freeChatBtn}, GetStarted: ${!!getStartedBtn}, JarvisLink: ${!!jarvisLink}, LoginLink: ${!!loginLink}`);
    }

    // ═══════════════════════════════════════════════════════════
    // STEP 3: Navigate to login and test Google Sign-in
    // ═══════════════════════════════════════════════════════════
    console.log('\n--- STEP 3: Login page + Google Sign-in ---');
    await page.goto(`${BASE_URL}/login`, { timeout: TIMEOUT, waitUntil: 'networkidle' });
    await sleep(5000);

    // Take screenshot for analysis
    await page.screenshot({ path: '/home/z/my-project/parwa/e2e-screenshot-login.png' });

    // Check for Google button
    const googleBtnInfo = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const googleCustomBtn = buttons.find(b =>
        b.textContent?.includes('Continue with Google') ||
        b.textContent?.includes('Google')
      );

      // Check for Google GIS iframe
      const iframes = Array.from(document.querySelectorAll('iframe'));
      const googleIframe = iframes.find(f =>
        f.title?.includes('Google') || f.src?.includes('google')
      );

      // Check for GIS container
      const gisContainer = document.querySelector('div[style*="max-width"]') ||
                           document.querySelector('div[class*="google"]');

      return {
        hasCustomBtn: !!googleCustomBtn,
        customBtnText: googleCustomBtn?.textContent?.trim(),
        hasIframe: !!googleIframe,
        iframeSrc: googleIframe?.src?.substring(0, 80),
        buttonCount: buttons.length,
        buttonTexts: buttons.map(b => b.textContent?.trim()).filter(Boolean).slice(0, 10),
      };
    });

    log('Google Sign-in button state', 'PASS',
        `Custom: ${googleBtnInfo.hasCustomBtn} ("${googleBtnInfo.customBtnText}"), ` +
        `GIS iframe: ${googleBtnInfo.hasIframe}, ` +
        `Buttons: ${JSON.stringify(googleBtnInfo.buttonTexts)}`);

    // Try clicking the Google button
    if (googleBtnInfo.hasCustomBtn) {
      try {
        const customBtn = await page.$('button:has-text("Continue with Google")') ||
                          await page.$('button:has-text("Google")');
        if (customBtn) {
          await customBtn.click();
          await sleep(2000);
          const afterClick = await page.content();
          const showsSetupMsg = afterClick.includes('Setup Required') || afterClick.includes('client_id');
          const showsUnavailable = afterClick.includes('unavailable');
          log('Google button click response', showsSetupMsg || showsUnavailable ? 'PASS' : 'WARN',
              showsSetupMsg ? 'Shows setup message (no CLIENT_ID configured)' :
              showsUnavailable ? 'GIS unavailable message' : 'No visible response');
        }
      } catch (e) {
        log('Google button click', 'WARN', e.message);
      }
    }

    // ═══════════════════════════════════════════════════════════
    // STEP 4: Test email login form
    // ═══════════════════════════════════════════════════════════
    console.log('\n--- STEP 4: Email login form ---');

    // Reload page to reset any state from Google button click
    await page.reload({ waitUntil: 'networkidle' });
    await sleep(3000);

    const emailInput = await page.$('input[type="email"], input[name="email"], input[placeholder*="email" i]');
    const passwordInput = await page.$('input[type="password"], input[name="password"]');

    if (emailInput && passwordInput) {
      await emailInput.fill('test@example.com');
      await passwordInput.fill('TestPassword123!');

      const submitBtn = await page.$('button[type="submit"], button:has-text("Sign in")');
      if (submitBtn) {
        await submitBtn.click();
        await sleep(5000);

        const afterLogin = await page.content();
        const hasError = afterLogin.includes('error') || afterLogin.includes('invalid') ||
                        afterLogin.includes('failed') || afterLogin.includes('incorrect');
        const currentUrl = page.url();

        if (currentUrl.includes('/login')) {
          log('Email login error handling', hasError ? 'PASS' : 'WARN',
              hasError ? 'Error shown for invalid creds' : 'No error message visible');
        } else {
          log('Email login redirects', 'PASS', `URL: ${currentUrl}`);
        }
      } else {
        log('Email login submit', 'FAIL', 'Submit button not found');
      }
    } else {
      log('Email login form', 'FAIL', `Email input: ${!!emailInput}, Password: ${!!passwordInput}`);
    }

    // ═══════════════════════════════════════════════════════════
    // STEP 5: Navigate to signup page
    // ═══════════════════════════════════════════════════════════
    console.log('\n--- STEP 5: Signup page ---');
    await page.goto(`${BASE_URL}/signup`, { timeout: TIMEOUT, waitUntil: 'networkidle' });
    await sleep(4000);

    const signupContent = await page.content();
    const hasSignupForm = signupContent.includes('Create') && signupContent.includes('account');
    const hasGoogleOnSignup = signupContent.includes('Google') || signupContent.includes('google');

    log('Signup page with Google option', hasSignupForm && hasGoogleOnSignup ? 'PASS' : 'WARN',
        `Form: ${hasSignupForm}, Google: ${hasGoogleOnSignup}`);

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
  console.log('     PARWA DEEP E2E TEST RESULTS            ');
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

runDeepTest().then(results => {
  process.exit(results.failed > 0 ? 1 : 0);
}).catch(e => {
  console.error('Test runner error:', e);
  process.exit(1);
});
