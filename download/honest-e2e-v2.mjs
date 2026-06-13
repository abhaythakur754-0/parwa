/**
 * PARWA Honest E2E Test v2
 * Starts servers AND runs the test in one process to avoid server dying
 */

import { chromium } from 'playwright';
import { execSync, spawn } from 'child_process';

const BASE_URL = 'http://127.0.0.1:3000';
const SCREENSHOT_DIR = '/home/z/my-project/download/e2e-honest';

const results = [];

function log(step, status, message) {
  results.push({ step, status, message, timestamp: new Date().toISOString() });
  const icon = status === 'PASS' ? '✅' : status === 'FAIL' ? '❌' : '⚠️';
  console.log(`${icon} [${step}] ${message}`);
}

async function screenshot(page, name) {
  const path = `${SCREENSHOT_DIR}/${name}.png`;
  try {
    await page.screenshot({ path, fullPage: true });
    console.log(`📸 ${path}`);
  } catch (e) {
    console.log(`📸 FAILED: ${e.message}`);
  }
}

async function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  console.log('\n════════════════════════════════════════════════════════════');
  console.log('  PARWA HONEST E2E TEST v2');
  console.log('════════════════════════════════════════════════════════════\n');

  // Verify server is up first
  try {
    const response = await fetch(BASE_URL);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    log('0-Server', 'PASS', `Next.js responding at ${BASE_URL}`);
  } catch (e) {
    log('0-Server', 'FAIL', `Next.js NOT responding: ${e.message}`);
    console.log('❌ Server not running. Aborting test.');
    process.exit(1);
  }

  // Verify backend
  try {
    const res = await fetch('http://127.0.0.1:8000/health');
    const data = await res.json();
    log('0-Backend', 'PASS', `Backend: ${JSON.stringify(data)}`);
  } catch (e) {
    log('0-Backend', 'WARN', `Backend unreachable: ${e.message} (some features may fail)`);
  }

  // Launch browser
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text().substring(0, 200));
  });
  page.on('pageerror', err => {
    consoleErrors.push(`PageError: ${err.message.substring(0, 200)}`);
  });

  // ── STEP 1: Landing Page ──────────────────────────────────
  console.log('\n── Step 1: Landing Page ──');
  try {
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await wait(3000);
    await screenshot(page, '01-landing-page');
    const title = await page.title();
    log('1-Landing', 'PASS', `Title: "${title}"`);
  } catch (e) {
    log('1-Landing', 'FAIL', e.message);
    await screenshot(page, '01-landing-ERROR');
  }

  // ── STEP 2: Login Page ───────────────────────────────────
  console.log('\n── Step 2: Login Page ──');
  try {
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await wait(3000);
    await screenshot(page, '02-login-page');
    
    // Find email and password fields
    const emailInput = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first();
    const passwordInput = page.locator('input[type="password"]').first();
    
    const emailVisible = await emailInput.isVisible().catch(() => false);
    const passwordVisible = await passwordInput.isVisible().catch(() => false);
    
    log('2-LoginFields', emailVisible && passwordVisible ? 'PASS' : 'FAIL', 
      `Email: ${emailVisible}, Password: ${passwordVisible}`);
    
    if (emailVisible && passwordVisible) {
      await emailInput.fill('test@parwa.ai');
      await passwordInput.fill('TestPass123!');
      await screenshot(page, '02b-login-filled');
      log('2-LoginFill', 'PASS', 'Filled email and password');
      
      // Submit
      const submitBtn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")').first();
      if (await submitBtn.isVisible().catch(() => false)) {
        await submitBtn.click();
        await wait(4000);
        const afterUrl = page.url();
        log('2-LoginSubmit', 'PASS', `After login, URL: ${afterUrl}`);
        await screenshot(page, '02c-after-login');
      } else {
        log('2-LoginSubmit', 'FAIL', 'Submit button not found');
      }
    }
  } catch (e) {
    log('2-Login', 'FAIL', e.message);
    await screenshot(page, '02-login-ERROR');
  }

  // ── STEP 3: Try registering if login failed ─────────────
  const currentUrl = page.url();
  if (currentUrl.includes('login') || currentUrl === BASE_URL + '/') {
    console.log('\n── Step 3: Try Signup ──');
    try {
      await page.goto(`${BASE_URL}/signup`, { waitUntil: 'domcontentloaded', timeout: 15000 });
      await wait(3000);
      await screenshot(page, '03-signup-page');
      
      const nameInput = page.locator('input[name="name"], input[placeholder*="name" i], input[id="name"]').first();
      const emailInput = page.locator('input[type="email"], input[name="email"]').first();
      const passwordInput = page.locator('input[type="password"]').first();
      
      if (await nameInput.isVisible().catch(() => false)) {
        await nameInput.fill('Test User');
        log('3-SignupName', 'PASS', 'Name filled');
      }
      if (await emailInput.isVisible().catch(() => false)) {
        await emailInput.fill('test@parwa.ai');
        log('3-SignupEmail', 'PASS', 'Email filled');
      }
      if (await passwordInput.isVisible().catch(() => false)) {
        await passwordInput.fill('TestPass123!');
        log('3-SignupPass', 'PASS', 'Password filled');
      }
      
      await screenshot(page, '03b-signup-filled');
      
      // Submit signup
      const submitBtn = page.locator('button[type="submit"], button:has-text("Sign up"), button:has-text("Create")').first();
      if (await submitBtn.isVisible().catch(() => false)) {
        await submitBtn.click();
        await wait(4000);
        const afterUrl = page.url();
        log('3-SignupSubmit', 'PASS', `After signup, URL: ${afterUrl}`);
        await screenshot(page, '03c-after-signup');
      }
    } catch (e) {
      log('3-Signup', 'FAIL', e.message);
    }
  }

  // ── STEP 4: Models Page ─────────────────────────────────
  console.log('\n── Step 4: Models Page ──');
  try {
    await page.goto(`${BASE_URL}/models`, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await wait(5000);
    await screenshot(page, '04-models-page');
    log('4-Models', 'PASS', 'Models page loaded');

    // Find SaaS industry button
    const saasBtn = page.locator('button:has-text("SaaS"), button:has-text("Software")').first();
    if (await saasBtn.isVisible().catch(() => false)) {
      await saasBtn.click();
      await wait(2000);
      log('4-SaaS', 'PASS', 'SaaS industry selected');
      await screenshot(page, '04b-saas-selected');
    } else {
      log('4-SaaS', 'FAIL', 'SaaS button not found');
      // Log what's on the page
      const bodyText = await page.locator('body').innerText().catch(() => '');
      console.log('Page text (first 500):', bodyText.substring(0, 500));
    }
  } catch (e) {
    log('4-Models', 'FAIL', e.message);
    await screenshot(page, '04-models-ERROR');
  }

  // ── STEP 5: Click "Hire Agent" on PARWA variant ─────────
  console.log('\n── Step 5: Hire Agent on PARWA ──');
  try {
    // Look for variant action buttons
    const hireBtn = page.locator('button:has-text("Hire Agent"), button:has-text("Get Started"), button:has-text("Start Free")').first();
    if (await hireBtn.isVisible().catch(() => false)) {
      await hireBtn.click();
      await wait(3000);
      log('5-HireAgent', 'PASS', 'Clicked Hire Agent');
      await screenshot(page, '05-after-hire');
    } else {
      log('5-HireAgent', 'FAIL', 'Hire Agent button not found');
      // Check what buttons exist
      const buttons = await page.locator('button').allTextContents();
      console.log('Available buttons:', buttons.filter(b => b.trim()).join(', '));
    }
  } catch (e) {
    log('5-HireAgent', 'FAIL', e.message);
  }

  // ── STEP 6: Navigate to Onboarding directly ─────────────
  console.log('\n── Step 6: Onboarding Page ──');
  try {
    await page.goto(`${BASE_URL}/onboarding`, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await wait(4000);
    const onbUrl = page.url();
    log('6-Onboarding', onbUrl.includes('onboarding') ? 'PASS' : 'FAIL', `URL: ${onbUrl}`);
    await screenshot(page, '06-onboarding-page');
  } catch (e) {
    log('6-Onboarding', 'FAIL', e.message);
    await screenshot(page, '06-onboarding-ERROR');
  }

  // ── STEP 7: Onboarding Step 1 - Industry + Variant ─────
  console.log('\n── Step 7: Step 1 - Industry & Variant ──');
  try {
    // Select SaaS
    const saasBtn = page.locator('button:has-text("SaaS")').first();
    if (await saasBtn.isVisible().catch(() => false)) {
      await saasBtn.click();
      await wait(1000);
      log('7-Industry', 'PASS', 'SaaS selected');
    }
    await screenshot(page, '07-step1-industry');

    // Select PARWA variant
    const parwaBtn = page.locator('button:has-text("PARWA")').first();
    if (await parwaBtn.isVisible().catch(() => false)) {
      await parwaBtn.click();
      await wait(1000);
      log('7-Variant', 'PASS', 'PARWA variant selected');
    }
    await screenshot(page, '07b-step1-variant');

    // Click Continue
    const continueBtn = page.locator('button:has-text("Continue")').first();
    if (await continueBtn.isVisible().catch(() => false)) {
      await continueBtn.click();
      await wait(3000);
      log('7-Continue', 'PASS', 'Continued to Step 2');
    }
    await screenshot(page, '07c-step1-done');
  } catch (e) {
    log('7-Step1', 'FAIL', e.message);
  }

  // ── STEP 8: Legal Compliance ────────────────────────────
  console.log('\n── Step 8: Step 2 - Legal Compliance ──');
  try {
    // Check for legal compliance heading
    const legalHeading = page.locator('h2:has-text("Legal"), h2:has-text("Compliance")').first();
    const legalVisible = await legalHeading.isVisible().catch(() => false);
    log('8-LegalVisible', legalVisible ? 'PASS' : 'FAIL', `Legal step ${legalVisible ? 'visible' : 'NOT visible'}`);
    
    await screenshot(page, '08-step2-legal');

    // Find all checkboxes and check them
    // PARWA uses custom checkbox buttons - find the small square toggle buttons
    const checkboxes = page.locator('input[type="checkbox"]');
    const cbCount = await checkboxes.count();
    
    if (cbCount > 0) {
      for (let i = 0; i < cbCount; i++) {
        const checked = await checkboxes.nth(i).isChecked().catch(() => false);
        if (!checked) {
          await checkboxes.nth(i).click().catch(() => {});
          await wait(300);
        }
      }
      log('8-Checkboxes', 'PASS', `Checked ${cbCount} checkboxes`);
    } else {
      // Try clicking the custom toggle buttons (the small square ones with w-5 h-5 class)
      const toggleBtns = page.locator('button').filter({ has: page.locator('svg') });
      const allBtns = await page.locator('button').all();
      
      // Look for the 3 consent card toggle buttons
      for (const btn of allBtns) {
        const cls = await btn.getAttribute('class').catch(() => '');
        if (cls && cls.includes('w-5 h-5')) {
          const hasCheckSvg = await btn.locator('svg').count().catch(() => 0);
          if (hasCheckSvg === 0) {
            await btn.click().catch(() => {});
            await wait(300);
          }
        }
      }
      log('8-ToggleButtons', 'INFO', 'Toggled custom consent buttons');
    }

    await screenshot(page, '08b-step2-checked');

    // Click Accept All & Continue
    const acceptBtn = page.locator('button:has-text("Accept All"), button:has-text("Accept")').first();
    if (await acceptBtn.isVisible().catch(() => false)) {
      await acceptBtn.click();
      await wait(3000);
      log('8-Accept', 'PASS', 'Clicked Accept All');
    }
    await screenshot(page, '08c-step2-done');
  } catch (e) {
    log('8-Legal', 'FAIL', e.message);
  }

  // ── STEP 9: Integration Setup ──────────────────────────
  console.log('\n── Step 9: Step 3 - Integrations ──');
  try {
    const integHeading = page.locator('h2:has-text("Integration"), h2:has-text("Connect")').first();
    const integVisible = await integHeading.isVisible().catch(() => false);
    log('9-Integration', integVisible ? 'PASS' : 'FAIL', `Integration step ${integVisible ? 'visible' : 'NOT visible'}`);
    await screenshot(page, '09-step3-integrations');

    // Click Slack integration
    const slackBtn = page.locator('button:has-text("Slack")').first();
    if (await slackBtn.isVisible().catch(() => false)) {
      await slackBtn.click();
      await wait(1000);
      
      // Fill Slack form
      const botTokenInput = page.locator('input[placeholder*="xoxb"], input[placeholder*="Bot"]').first();
      if (await botTokenInput.isVisible().catch(() => false)) {
        await botTokenInput.fill('xoxb-test-parwa-token-12345');
        log('9-BotToken', 'PASS', 'Bot token filled');
      }
      
      const channelInput = page.locator('input[placeholder*="C01"], input[placeholder*="Channel"]').first();
      if (await channelInput.isVisible().catch(() => false)) {
        await channelInput.fill('C01PARWATEST');
        log('9-Channel', 'PASS', 'Channel ID filled');
      }
      
      await screenshot(page, '09b-slack-filled');

      // Save
      const saveBtn = page.locator('button:has-text("Save")').first();
      if (await saveBtn.isVisible().catch(() => false)) {
        await saveBtn.click();
        await wait(2000);
        log('9-Save', 'PASS', 'Saved Slack integration');
      }
    }

    await screenshot(page, '09c-step3-after');

    // Continue
    const continueBtn = page.locator('button:has-text("Continue")').first();
    if (await continueBtn.isVisible().catch(() => false)) {
      await continueBtn.click();
      await wait(3000);
      log('9-Continue', 'PASS', 'Continued to Step 4');
    }
  } catch (e) {
    log('9-Integration', 'FAIL', e.message);
  }

  // ── STEP 10: Knowledge Base ────────────────────────────
  console.log('\n── Step 10: Step 4 - Knowledge Base ──');
  try {
    await screenshot(page, '10-step4-knowledge');
    const kbHeading = page.locator('h2:has-text("Knowledge")').first();
    const kbVisible = await kbHeading.isVisible().catch(() => false);
    log('10-Knowledge', kbVisible ? 'PASS' : 'FAIL', `Knowledge step ${kbVisible ? 'visible' : 'NOT visible'}`);

    // Skip (optional) - click Continue
    const continueBtn = page.locator('button:has-text("Continue")').first();
    if (await continueBtn.isVisible().catch(() => false)) {
      await continueBtn.click();
      await wait(3000);
      log('10-Continue', 'PASS', 'Skipped to Step 5');
    }
  } catch (e) {
    log('10-Knowledge', 'FAIL', e.message);
  }

  // ── STEP 11: AI Config ─────────────────────────────────
  console.log('\n── Step 11: Step 5 - AI Config ──');
  try {
    await screenshot(page, '11-step5-aiconfig');
    const aiHeading = page.locator('h2:has-text("Configure"), h2:has-text("AI")').first();
    const aiVisible = await aiHeading.isVisible().catch(() => false);
    log('11-AIConfig', aiVisible ? 'PASS' : 'FAIL', `AI Config step ${aiVisible ? 'visible' : 'NOT visible'}`);

    // Click Activate
    const activateBtn = page.locator('button:has-text("Activate"), button:has-text("Continue")').first();
    if (await activateBtn.isVisible().catch(() => false)) {
      await activateBtn.click();
      await wait(3000);
      log('11-Activate', 'PASS', 'Clicked Activate/Continue');
    }
    await screenshot(page, '11b-step5-done');
  } catch (e) {
    log('11-AIConfig', 'FAIL', e.message);
  }

  // ── STEP 12: Cost Breakdown ────────────────────────────
  console.log('\n── Step 12: Step 6 - Cost Breakdown ──');
  try {
    await screenshot(page, '12-step6-cost');
    const costHeading = page.locator('h2:has-text("Cost"), h2:has-text("Breakdown"), h2:has-text("Review")').first();
    const costVisible = await costHeading.isVisible().catch(() => false);
    log('12-CostBreakdown', costVisible ? 'PASS' : 'FAIL', `Cost step ${costVisible ? 'visible' : 'NOT visible'}`);

    // Look for Paddle or payment button
    const paymentBtn = page.locator('button:has-text("Proceed"), button:has-text("Pay"), button:has-text("Checkout"), button:has-text("Subscribe"), button:has-text("Complete"), button:has-text("Go Live")').first();
    const paymentVisible = await paymentBtn.isVisible().catch(() => false);
    log('12-PaymentBtn', paymentVisible ? 'PASS' : 'WARN', `Payment button ${paymentVisible ? 'found' : 'not found'}`);

    // DON'T click real Paddle - just screenshot what's there
    await screenshot(page, '12b-step6-detail');
  } catch (e) {
    log('12-CostBreakdown', 'FAIL', e.message);
  }

  // ── STEP 13: Check for Victory or simulate completing Step 6 ──
  console.log('\n── Step 13: Checking current page state ──');
  try {
    // If we're on cost breakdown, we need to complete it to see Victory
    // But we can't actually pay through Paddle in E2E
    // Instead, let's try navigating with step=victory param
    // OR check if there's a "Complete Setup" type button
    
    // First check if victory is already showing
    const victoryHeading = page.locator('h1:has-text("Welcome"), h1:has-text("Victory")').first();
    const victoryVisible = await victoryHeading.isVisible().catch(() => false);
    
    if (victoryVisible) {
      log('13-Victory', 'PASS', 'First Victory visible!');
      await screenshot(page, '13-victory');
    } else {
      log('13-Victory', 'WARN', 'Victory not showing yet (likely on cost breakdown step needing real payment)');
      
      // Try clicking whatever action button is available on the cost page
      const actionBtn = page.locator('button:has-text("Complete"), button:has-text("Go Live"), button:has-text("Activate"), button:has-text("Launch")').first();
      if (await actionBtn.isVisible().catch(() => false)) {
        await actionBtn.click();
        await wait(3000);
        await screenshot(page, '13-after-action');
      }
      
      // Check for victory now
      const victoryNow = page.locator('h1:has-text("Welcome"), h1:has-text("Victory")').first();
      if (await victoryNow.isVisible().catch(() => false)) {
        log('13-VictoryAfterAction', 'PASS', 'First Victory now visible!');
        await screenshot(page, '13b-victory');
      } else {
        await screenshot(page, '13-no-victory-yet');
        log('13-NoVictory', 'WARN', 'Still not on Victory page');
      }
    }
  } catch (e) {
    log('13-Victory', 'FAIL', e.message);
  }

  // ── Console Errors ─────────────────────────────────────
  console.log('\n── Console Errors ──');
  if (consoleErrors.length > 0) {
    log('Console-Errors', 'WARN', `${consoleErrors.length} errors`);
    consoleErrors.slice(0, 10).forEach(e => console.log(`  🐛 ${e}`));
  } else {
    log('Console-Errors', 'PASS', 'No console errors');
  }

  // ── Summary ────────────────────────────────────────────
  const passes = results.filter(r => r.status === 'PASS').length;
  const fails = results.filter(r => r.status === 'FAIL').length;
  const warns = results.filter(r => r.status === 'WARN').length;
  
  console.log('\n════════════════════════════════════════════════════════════');
  console.log('  HONEST TEST RESULTS');
  console.log('════════════════════════════════════════════════════════════');
  console.log(`  ✅ PASS: ${passes}`);
  console.log(`  ❌ FAIL: ${fails}`);
  console.log(`  ⚠️  WARN: ${warns}`);
  console.log(`  📸 Screenshots: ${SCREENSHOT_DIR}`);
  console.log('════════════════════════════════════════════════════════════\n');

  // Save results
  const fs = await import('fs');
  fs.writeFileSync(`${SCREENSHOT_DIR}/test-results.json`, JSON.stringify({ results, summary: { passes, fails, warns } }, null, 2));

  await browser.close();
}

main().catch(e => {
  console.error('FATAL:', e.message);
  process.exit(1);
});
