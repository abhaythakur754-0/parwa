/**
 * PARWA Full Journey Test — Variant-to-Payment Screenshot Capture
 *
 * Captures screenshots of EVERY step in the onboarding journey:
 *   A) Models/Pricing Page
 *   B) SaaS Industry selected
 *   C) Click "Hire Agent" on PARWA (middle) variant
 *   D) Confirmation Modal
 *   E) After Confirm
 *   F) Onboarding Step 1 - Industry + Variant
 *   G) Onboarding Step 1 - SaaS + PARWA selected
 *   H) Onboarding Step 2 - Legal Compliance
 *   I) Onboarding Step 2 - Checkboxes checked
 *   J) Onboarding Step 3 - Integration setup
 *   K) Onboarding Step 4 - Knowledge base upload
 *   L) Onboarding Step 5 - AI Config
 *   M) Onboarding Step 6 - Cost Breakdown / Payment
 *   N) First Victory - Step 7 celebration
 */

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'http://127.0.0.1:3000';
const SCREENSHOT_DIR = '/home/z/my-project/download/full-journey-proof';
const TIMEOUT = 30000;

// Ensure screenshot directory exists
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

// Helper: take a full-page screenshot
async function screenshot(page, name) {
  const filePath = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: filePath, fullPage: true });
  console.log(`  📸 Screenshot saved: ${name}.png`);
  return filePath;
}

// Helper: debug current page state
async function debugPage(page, label) {
  const url = page.url();
  const buttons = await page.locator('button').allTextContents();
  const links = await page.locator('a').allTextContents();
  console.log(`\n  🔍 DEBUG [${label}]`);
  console.log(`     URL: ${url}`);
  console.log(`     Buttons: ${JSON.stringify(buttons.slice(0, 10))}`);
  console.log(`     Links: ${JSON.stringify(links.slice(0, 10))}`);
}

// Helper: wait for page to stabilize
async function waitForStable(page, ms = 1500) {
  await page.waitForTimeout(ms);
}

(async () => {
  console.log('🚀 Starting PARWA Full Journey Test...\n');

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    ignoreHTTPSErrors: true,
  });

  const page = await context.newPage();
  page.setDefaultTimeout(TIMEOUT);

  // Generate unique test user
  const timestamp = Date.now();
  const testEmail = `journey-test-${timestamp}@parwa.ai`;
  const testPassword = 'TestP@ss123!';

  try {
    // ── STEP 0: Register a new user via API ──────────────────────────
    console.log('📝 Step 0: Registering test user...');
    const registerRes = await page.request.post(`${BASE_URL}/api/auth/register`, {
      data: {
        email: testEmail,
        password: testPassword,
        fullName: 'Journey Tester',
        companyName: 'Test Corp',
        industry: 'saas',
      },
    });
    const registerData = await registerRes.json();
    console.log(`  Register status: ${registerRes.status()}`);
    console.log(`  Register response: ${JSON.stringify(registerData).slice(0, 200)}`);

    // ── STEP 0b: Login via UI to get cookies ──────────────────────────
    console.log('\n🔐 Step 0b: Logging in via UI...');
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: TIMEOUT });
    await waitForStable(page, 2000);

    // Fill in login form
    const emailInput = page.locator('input[id="email"], input[name="email"], input[type="email"]').first();
    const passwordInput = page.locator('input[id="password"], input[name="password"], input[type="password"]').first();

    await emailInput.fill(testEmail);
    await passwordInput.fill(testPassword);

    // Submit the login form
    const submitBtn = page.locator('button[type="submit"], button:has-text("Sign in")').first();
    await submitBtn.click();
    await waitForStable(page, 3000);

    // Check where we ended up after login
    const afterLoginUrl = page.url();
    console.log(`  After login URL: ${afterLoginUrl}`);

    // If we got redirected to onboarding, that's fine. If we're still on login, try again.
    if (afterLoginUrl.includes('/login')) {
      console.log('  ⚠️ Still on login page, checking for errors...');
      const errorMsg = await page.locator('[class*="rose"], [class*="error"], [class*="red"]').first().textContent().catch(() => '');
      console.log(`  Error on page: ${errorMsg}`);

      // Try verifying email first then logging in
      // Check if user needs verification
      if (errorMsg.includes('verify') || errorMsg.includes('Verify')) {
        console.log('  Email verification required - trying to bypass...');
        // We need to set user as verified in the local DB
        // Let's try logging in again after a moment
      }

      // Alternative: try API login directly and set cookies
      console.log('  Trying API login instead...');
      const loginRes = await context.request.post(`${BASE_URL}/api/auth/login`, {
        data: { email: testEmail, password: testPassword },
      });
      console.log(`  API Login status: ${loginRes.status()}`);
      const loginData = await loginRes.json();
      console.log(`  API Login response: ${JSON.stringify(loginData).slice(0, 200)}`);

      // The cookies should have been set by the API response
      // Navigate to onboarding directly
      await page.goto(`${BASE_URL}/onboarding`, { waitUntil: 'networkidle', timeout: TIMEOUT });
      await waitForStable(page, 2000);
    }

    // If we got redirected to onboarding after login, we need to go to models first
    // Let's navigate to models page directly
    console.log('\n📋 A) Navigating to Models page...');
    await page.goto(`${BASE_URL}/models`, { waitUntil: 'networkidle', timeout: TIMEOUT });
    await waitForStable(page, 3000);

    // Check if we're on models page or got redirected
    const modelsUrl = page.url();
    console.log(`  Current URL: ${modelsUrl}`);

    if (modelsUrl.includes('/login') || modelsUrl.includes('/signup')) {
      console.log('  ⚠️ Got redirected to auth page. Need to login first...');
      // Fill login form again
      await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: TIMEOUT });
      await waitForStable(page, 2000);

      const emailInput2 = page.locator('input[id="email"], input[name="email"], input[type="email"]').first();
      const passwordInput2 = page.locator('input[id="password"], input[name="password"], input[type="password"]').first();
      await emailInput2.fill(testEmail);
      await passwordInput2.fill(testPassword);

      const submitBtn2 = page.locator('button[type="submit"], button:has-text("Sign in")').first();
      await submitBtn2.click();
      await waitForStable(page, 3000);

      // Now go to models
      await page.goto(`${BASE_URL}/models`, { waitUntil: 'networkidle', timeout: TIMEOUT });
      await waitForStable(page, 3000);
    }

    // Screenshot A: Models/Pricing Page
    await screenshot(page, 'A-models-page');
    await debugPage(page, 'Models Page');

    // ── STEP B: Click SaaS Industry Tab ──────────────────────────
    console.log('\n📋 B) Selecting SaaS industry...');
    // Look for SaaS industry button/tab
    const saasBtn = page.locator('button:has-text("SaaS"), div:has-text("SaaS")').first();
    if (await saasBtn.isVisible()) {
      await saasBtn.click();
      await waitForStable(page, 2000);
      await screenshot(page, 'B-saas-selected');
    } else {
      console.log('  ⚠️ SaaS button not found, trying alternative selectors...');
      // Try clicking by looking at industry cards
      const industryButtons = await page.locator('button').allTextContents();
      console.log(`  Available buttons: ${JSON.stringify(industryButtons)}`);

      // Try different approach - find the button containing SaaS text
      const allButtons = page.locator('button');
      for (let i = 0; i < await allButtons.count(); i++) {
        const text = await allButtons.nth(i).textContent();
        if (text && text.includes('SaaS')) {
          await allButtons.nth(i).click();
          await waitForStable(page, 2000);
          await screenshot(page, 'B-saas-selected');
          break;
        }
      }
    }

    // ── STEP C: Click "Hire Agent" on PARWA (middle/growth) variant ──────────────────────────
    console.log('\n📋 C) Clicking "Hire Agent" on PARWA variant...');
    // The growth variant is the middle one (PARWA Growth)
    const hireAgentBtn = page.locator('button:has-text("Hire Agent")').first();
    if (await hireAgentBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await hireAgentBtn.click();
      await waitForStable(page, 1500);
      await screenshot(page, 'C-hire-agent-clicked');
    } else {
      console.log('  ⚠️ "Hire Agent" button not found. May need authentication.');
      console.log('  Trying "Get Started" button instead...');

      const getStartedBtn = page.locator('button:has-text("Get Started")').first();
      if (await getStartedBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await getStartedBtn.click();
        await waitForStable(page, 1500);
        await screenshot(page, 'C-get-started-clicked');
      }
    }

    // ── STEP D: Confirmation Modal ──────────────────────────
    console.log('\n📋 D) Checking for Confirmation Modal...');
    const confirmModal = page.locator('text=Confirm Selection, text=Continue, [class*="modal"], [class*="fixed inset-0"]').first();
    if (await confirmModal.isVisible({ timeout: 5000 }).catch(() => false)) {
      await screenshot(page, 'D-confirmation-modal');

      // ── STEP E: After Confirm ──────────────────────────
      console.log('\n📋 E) Clicking Continue in confirmation modal...');
      const continueBtn = page.locator('button:has-text("Continue")').last();
      if (await continueBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await continueBtn.click();
        await waitForStable(page, 3000);
        await screenshot(page, 'E-after-confirm');
      }
    } else {
      console.log('  ⚠️ No confirmation modal found. Might already be on onboarding.');
    }

    // ── Navigate to onboarding if not already there ──────────────────────────
    const currentUrl = page.url();
    if (!currentUrl.includes('/onboarding')) {
      console.log('\n📋 Navigating to onboarding page...');
      await page.goto(`${BASE_URL}/onboarding`, { waitUntil: 'networkidle', timeout: TIMEOUT });
      await waitForStable(page, 3000);
    }

    // Check if we're on onboarding or got redirected
    const onboardingUrl = page.url();
    console.log(`  Onboarding URL: ${onboardingUrl}`);

    if (onboardingUrl.includes('/login')) {
      console.log('  ⚠️ Got redirected to login from onboarding. Need to re-login...');

      // Login via UI form
      const emailInput3 = page.locator('input[id="email"], input[name="email"], input[type="email"]').first();
      const passwordInput3 = page.locator('input[id="password"], input[name="password"], input[type="password"]').first();

      // Clear and fill
      await emailInput3.clear();
      await emailInput3.fill(testEmail);
      await passwordInput3.clear();
      await passwordInput3.fill(testPassword);

      const submitBtn3 = page.locator('button[type="submit"], button:has-text("Sign in")').first();
      await submitBtn3.click();
      await waitForStable(page, 4000);

      const afterLoginUrl2 = page.url();
      console.log(`  After login URL: ${afterLoginUrl2}`);

      // If we were redirected to a non-onboarding page, navigate manually
      if (!afterLoginUrl2.includes('/onboarding')) {
        await page.goto(`${BASE_URL}/onboarding`, { waitUntil: 'networkidle', timeout: TIMEOUT });
        await waitForStable(page, 3000);
      }
    }

    // ── STEP F: Onboarding Step 1 - Industry + Variant ──────────────────────────
    console.log('\n📋 F) Onboarding Step 1 - Industry + Variant Selection...');
    await screenshot(page, 'F-onboarding-step1');
    await debugPage(page, 'Onboarding Step 1');

    // ── STEP G: Select SaaS + PARWA ──────────────────────────
    console.log('\n📋 G) Selecting SaaS industry and PARWA variant...');

    // Click SaaS industry
    const saasIndustryBtn = page.locator('button:has-text("SaaS")').first();
    if (await saasIndustryBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await saasIndustryBtn.click();
      await waitForStable(page, 500);
    }

    // Click PARWA (growth/middle) variant - look for the "Popular" badge
    // PARWA variant has key='parwa' and badge='Popular'
    const parwaVariantBtn = page.locator('button:has-text("PARWA")').first();
    if (await parwaVariantBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await parwaVariantBtn.click();
      await waitForStable(page, 500);
    } else {
      // Try the middle variant
      const variantButtons = await page.locator('button').allTextContents();
      console.log(`  Available buttons: ${JSON.stringify(variantButtons)}`);
      // Find the growth/parwa variant button
      for (let i = 0; i < await page.locator('button').count(); i++) {
        const text = await page.locator('button').nth(i).textContent();
        if (text && (text.includes('PARWA') && !text.includes('Mini') && !text.includes('High'))) {
          await page.locator('button').nth(i).click();
          await waitForStable(page, 500);
          break;
        }
      }
    }

    await screenshot(page, 'G-step1-saas-parwa-selected');

    // Click Continue on Step 1
    const continueStep1 = page.locator('button:has-text("Continue")').last();
    if (await continueStep1.isVisible({ timeout: 3000 }).catch(() => false)) {
      await continueStep1.click();
      await waitForStable(page, 3000);
    }

    // ── STEP H: Onboarding Step 2 - Legal Compliance ──────────────────────────
    console.log('\n📋 H) Onboarding Step 2 - Legal Compliance...');
    await screenshot(page, 'H-step2-legal');
    await debugPage(page, 'Step 2 Legal');

    // ── STEP I: Check all 3 checkboxes ──────────────────────────
    console.log('\n📋 I) Checking all 3 legal checkboxes...');

    // Find and click all unchecked checkboxes
    const checkboxes = page.locator('button[role="checkbox"], .w-5.h-5.rounded, button:has(svg.CheckCircle2)').all();
    // Alternative: find the checkbox containers by looking at the legal compliance cards
    // The checkboxes are small buttons with w-5 h-5 class
    const checkboxButtons = page.locator('.w-5.h-5.rounded');
    const checkboxCount = await checkboxButtons.count();
    console.log(`  Found ${checkboxCount} checkboxes`);

    for (let i = 0; i < checkboxCount; i++) {
      try {
        const box = checkboxButtons.nth(i);
        if (await box.isVisible({ timeout: 2000 }).catch(() => false)) {
          await box.click();
          await waitForStable(page, 300);
        }
      } catch (e) {
        console.log(`  Checkbox ${i} click failed: ${e.message}`);
      }
    }

    // Alternative approach: click on the card header rows which have the checkbox toggle
    // Look for all elements that contain Terms of Service, Privacy Policy, AI Data
    const consentCards = ['Terms of Service', 'Privacy Policy', 'AI Data'];
    for (const cardTitle of consentCards) {
      try {
        // Find the card header containing the title and click the checkbox area
        const cardHeader = page.locator(`div:has(> :text("${cardTitle}"))`).first();
        if (await cardHeader.isVisible({ timeout: 3000 }).catch(() => false)) {
          // Find the checkbox button within this card
          const checkbox = cardHeader.locator('button').first();
          if (await checkbox.isVisible({ timeout: 2000 }).catch(() => false)) {
            await checkbox.click();
            await waitForStable(page, 300);
          }
        }
      } catch (e) {
        console.log(`  ${cardTitle} checkbox failed: ${e.message}`);
      }
    }

    // Another approach: just click the small rounded buttons in the legal section
    // These are the 5x5 rounded buttons
    const smallButtons = page.locator('.w-5.h-5');
    const smallBtnCount = await smallButtons.count();
    console.log(`  Found ${smallBtnCount} small buttons`);
    for (let i = 0; i < Math.min(smallBtnCount, 3); i++) {
      try {
        await smallButtons.nth(i).click();
        await waitForStable(page, 300);
      } catch (e) {
        // ignore
      }
    }

    await screenshot(page, 'I-step2-checkboxes-checked');

    // Click "Accept All & Continue" button
    const acceptBtn = page.locator('button:has-text("Accept All"), button:has-text("Accept")').last();
    if (await acceptBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await acceptBtn.click();
      await waitForStable(page, 3000);
    }

    // ── STEP J: Onboarding Step 3 - Integration Setup ──────────────────────────
    console.log('\n📋 J) Onboarding Step 3 - Integration Setup...');
    const step3Url = page.url();
    console.log(`  URL: ${step3Url}`);
    await screenshot(page, 'J-step3-integrations');
    await debugPage(page, 'Step 3 Integrations');

    // Skip integrations - find the Continue/Next/Skip button
    const skipOrNextBtn = page.locator('button:has-text("Skip"), button:has-text("Continue"), button:has-text("Next")').first();
    if (await skipOrNextBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await skipOrNextBtn.click();
      await waitForStable(page, 3000);
    }

    // ── STEP K: Onboarding Step 4 - Knowledge Base ──────────────────────────
    console.log('\n📋 K) Onboarding Step 4 - Knowledge Base Upload...');
    await screenshot(page, 'K-step4-knowledge');
    await debugPage(page, 'Step 4 Knowledge');

    // Click Continue (uploading is optional)
    const continueStep4 = page.locator('button:has-text("Continue")').last();
    if (await continueStep4.isVisible({ timeout: 3000 }).catch(() => false)) {
      await continueStep4.click();
      await waitForStable(page, 3000);
    }

    // ── STEP L: Onboarding Step 5 - AI Config ──────────────────────────
    console.log('\n📋 L) Onboarding Step 5 - AI Config...');
    await screenshot(page, 'L-step5-ai-config');
    await debugPage(page, 'Step 5 AI Config');

    // Click "Activate AI Assistant" button
    const activateBtn = page.locator('button:has-text("Activate")').first();
    if (await activateBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await activateBtn.click();
      await waitForStable(page, 3000);
    }

    // ── STEP M: Onboarding Step 6 - Cost Breakdown / Payment ──────────────────────────
    console.log('\n📋 M) Onboarding Step 6 - Cost Breakdown / Payment...');
    await screenshot(page, 'M-step6-cost-breakdown');
    await debugPage(page, 'Step 6 Cost');

    // Click "Proceed to Checkout" or "Confirm & Activate" or similar
    const checkoutBtn = page.locator('button:has-text("Checkout"), button:has-text("Proceed"), button:has-text("Confirm"), button:has-text("Activate"), button:has-text("Pay"), button:has-text("Continue")').first();
    if (await checkoutBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await checkoutBtn.click();
      await waitForStable(page, 3000);
    }

    // ── STEP N: First Victory - Step 7 ──────────────────────────
    console.log('\n📋 N) First Victory - Step 7 Celebration...');
    // Check if we're on the victory page
    const currentUrlN = page.url();
    console.log(`  URL: ${currentUrlN}`);

    // Look for victory page elements
    const victoryText = page.locator('text=Welcome to PARWA, text=First Victory, text=ready, text=PartyPopper, svg').first();
    await waitForStable(page, 3000);
    await screenshot(page, 'N-step7-first-victory');
    await debugPage(page, 'Step 7 Victory');

    // ── Summary ──────────────────────────
    console.log('\n✅ Journey test completed!');

  } catch (error) {
    console.error('\n❌ Journey test failed with error:', error.message);
    // Take a final error screenshot
    await screenshot(page, 'Z-error-state').catch(() => {});
    await debugPage(page, 'Error State');
  } finally {
    await browser.close();
  }

  // List all captured screenshots
  console.log('\n📁 Captured screenshots:');
  const files = fs.readdirSync(SCREENSHOT_DIR).filter(f => f.endsWith('.png')).sort();
  for (const f of files) {
    const stats = fs.statSync(path.join(SCREENSHOT_DIR, f));
    console.log(`  ${f} (${(stats.size / 1024).toFixed(1)} KB)`);
  }
  console.log(`\nTotal: ${files.length} screenshots`);
})();
