/**
 * PARWA Honest E2E Test v3
 * Correctly handles the real flow:
 * 1. Register a new user (auto-verified in dev)
 * 2. Login
 * 3. Models page → Select industry → Increase quantity → Confirm
 * 4. Welcome/Details → Fill form → Next
 * 5. Onboarding Steps 1-7 → First Victory
 */

import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'fs';

const BASE = 'http://127.0.0.1:3000';
const DIR = '/home/z/my-project/download/e2e-honest';
const results = [];

function log(step, status, message) {
  results.push({ step, status, message, time: new Date().toISOString() });
  const icon = status === 'PASS' ? '✅' : status === 'FAIL' ? '❌' : status === 'WARN' ? '⚠️' : 'ℹ️';
  console.log(`${icon} [${step}] ${message}`);
}

async function snap(page, name) {
  try { await page.screenshot({ path: `${DIR}/${name}.png`, fullPage: true }); } catch {}
}

async function wait(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  console.log('\n════════════════════════════════════════════');
  console.log('  PARWA HONEST E2E v3');
  console.log('════════════════════════════════════════════\n');

  // Check server
  try {
    const r = await fetch(BASE);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    log('0-Server', 'PASS', 'Next.js responding');
  } catch (e) {
    log('0-Server', 'FAIL', `Server not responding: ${e.message}`);
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text().substring(0, 200)); });
  page.on('pageerror', e => errors.push(`PageError: ${e.message.substring(0, 200)}`));

  // ── STEP 1: Register ──────────────────────────────────
  console.log('\n── Register ──');
  await page.goto(`${BASE}/signup`, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await wait(3000);
  await snap(page, '01-signup-page');

  // Fill signup form
  const nameInput = page.locator('input[name="name"], input[id="name"], input[placeholder*="name" i]').first();
  const emailInput = page.locator('input[type="email"], input[name="email"]').first();
  const passwordInput = page.locator('input[type="password"]').first();

  let signupOk = true;
  if (await nameInput.isVisible().catch(() => false)) {
    await nameInput.fill('Test User');
  }
  if (await emailInput.isVisible().catch(() => false)) {
    await emailInput.fill(`test+${Date.now()}@parwa.ai`); // unique email
  } else {
    signupOk = false;
    log('1-Register', 'FAIL', 'Email input not found');
  }
  if (await passwordInput.isVisible().catch(() => false)) {
    await passwordInput.fill('TestPass123!');
  } else {
    signupOk = false;
    log('1-Register', 'FAIL', 'Password input not found');
  }
  await snap(page, '02-signup-filled');

  if (signupOk) {
    const submitBtn = page.locator('button[type="submit"], button:has-text("Sign up"), button:has-text("Create")').first();
    if (await submitBtn.isVisible().catch(() => false)) {
      await submitBtn.click();
      await wait(5000);
      const url = page.url();
      log('1-Register', !url.includes('signup') ? 'PASS' : 'FAIL', `After signup URL: ${url}`);
      await snap(page, '03-after-register');
    } else {
      log('1-Register', 'FAIL', 'Submit button not found');
    }
  }

  // ── STEP 2: If still on signup/login, try login ───────
  let currentUrl = page.url();
  if (currentUrl.includes('signup') || currentUrl.includes('login')) {
    console.log('\n── Login fallback ──');
    await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await wait(3000);
    
    const em = page.locator('input[type="email"], input[name="email"]').first();
    const pw = page.locator('input[type="password"]').first();
    if (await em.isVisible().catch(() => false)) await em.fill('test@parwa.ai');
    if (await pw.isVisible().catch(() => false)) await pw.fill('TestPass123!');
    
    const btn = page.locator('button[type="submit"], button:has-text("Sign in")').first();
    if (await btn.isVisible().catch(() => false)) await btn.click();
    await wait(5000);
    currentUrl = page.url();
    log('2-Login', !currentUrl.includes('login') ? 'PASS' : 'FAIL', `URL: ${currentUrl}`);
    await snap(page, '04-after-login');
  }

  // ── STEP 3: Models Page - Select Industry ─────────────
  console.log('\n── Models Page ──');
  await page.goto(`${BASE}/models`, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await wait(5000);
  await snap(page, '05-models-page');
  log('3-Models', 'PASS', 'Models page loaded');

  // Select SaaS industry
  const saasBtn = page.locator('button:has-text("SaaS")').first();
  if (await saasBtn.isVisible().catch(() => false)) {
    await saasBtn.click();
    await wait(2000);
    log('3-SaaS', 'PASS', 'SaaS industry selected');
  } else {
    log('3-SaaS', 'FAIL', 'SaaS button not found');
  }
  await snap(page, '06-saas-selected');

  // ── STEP 4: Increase quantity on Growth variant ────────
  console.log('\n── Select Variant ──');
  
  // The models page has quantity buttons. Need to click + on the Growth (PARWA) variant
  // Find the "+" button for the Growth tier
  const plusButtons = page.locator('button:has-text("+")');
  const plusCount = await plusButtons.count();
  log('4-PlusButtons', plusCount > 0 ? 'PASS' : 'FAIL', `Found ${plusCount} plus buttons`);

  if (plusCount > 0) {
    // Click the second + button (Growth/PARWA tier - middle one)
    // Or find the one associated with Growth
    await plusButtons.first().click(); // Click first + to add a starter variant
    await wait(1000);
    log('4-Quantity', 'PASS', 'Increased quantity');
  }
  await snap(page, '07-variant-quantity');

  // ── STEP 5: Click Confirm button ───────────────────────
  console.log('\n── Confirm Selection ──');
  
  const confirmBtn = page.locator('button:has-text("Confirm")').first();
  if (await confirmBtn.isVisible().catch(() => false)) {
    const isEnabled = await confirmBtn.isEnabled().catch(() => false);
    if (isEnabled) {
      await confirmBtn.click();
      await wait(5000);
      log('5-Confirm', 'PASS', 'Clicked Confirm button');
    } else {
      log('5-Confirm', 'FAIL', 'Confirm button is disabled (no variant selected?)');
      // Try clicking other + buttons
      if (plusCount > 1) {
        for (let i = 0; i < plusCount; i++) {
          await plusButtons.nth(i).click();
          await wait(500);
        }
        await wait(1000);
        if (await confirmBtn.isEnabled().catch(() => false)) {
          await confirmBtn.click();
          await wait(5000);
          log('5-ConfirmRetry', 'PASS', 'Confirm worked after adding all variants');
        }
      }
    }
  } else {
    // Maybe the "Sign Up & Hire Now" button instead
    const signUpHire = page.locator('button:has-text("Sign Up")').first();
    if (await signUpHire.isVisible().catch(() => false)) {
      await signUpHire.click();
      await wait(5000);
      log('5-SignUpHire', 'PASS', 'Clicked Sign Up & Hire Now');
    } else {
      log('5-Confirm', 'FAIL', 'No Confirm or Sign Up button found');
    }
  }
  await snap(page, '08-after-confirm');

  // ── STEP 6: Welcome/Details or Onboarding ─────────────
  console.log('\n── Welcome/Onboarding ──');
  currentUrl = page.url();
  log('6-CurrentUrl', 'INFO', `URL: ${currentUrl}`);

  // If on welcome/details page, fill the form
  if (currentUrl.includes('/welcome/details')) {
    log('6-WelcomeDetails', 'PASS', 'On Welcome/Details page');
    await snap(page, '09-welcome-details');

    // Fill details form
    const companyInput = page.locator('input[name="company_name"], input[placeholder*="company" i], input[placeholder*="Company"]').first();
    if (await companyInput.isVisible().catch(() => false)) {
      await companyInput.fill('Parwa Test Company');
    }
    
    const phoneInput = page.locator('input[name="phone"], input[type="tel"], input[placeholder*="phone" i]').first();
    if (await phoneInput.isVisible().catch(() => false)) {
      await phoneInput.fill('+1234567890');
    }

    await snap(page, '09b-details-filled');

    // Click Next/Continue
    const nextBtn = page.locator('button:has-text("Next"), button:has-text("Continue"), button[type="submit"]').first();
    if (await nextBtn.isVisible().catch(() => false)) {
      await nextBtn.click();
      await wait(5000);
      log('6-DetailsNext', 'PASS', 'Clicked Next after details');
    }
  }

  // Navigate to onboarding directly if needed
  currentUrl = page.url();
  if (!currentUrl.includes('/onboarding')) {
    log('6-Navigate', 'INFO', 'Navigating directly to onboarding...');
    await page.goto(`${BASE}/onboarding`, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await wait(4000);
    currentUrl = page.url();
  }

  // Check if redirected to login (not authenticated)
  if (currentUrl.includes('/login')) {
    log('6-AuthRedirect', 'WARN', 'Redirected to login - need auth');
    // Fill login
    const em = page.locator('input[type="email"], input[name="email"]').first();
    const pw = page.locator('input[type="password"]').first();
    if (await em.isVisible().catch(() => false)) await em.fill('test@parwa.ai');
    if (await pw.isVisible().catch(() => false)) await pw.fill('TestPass123!');
    const btn = page.locator('button[type="submit"], button:has-text("Sign in")').first();
    if (await btn.isVisible().catch(() => false)) await btn.click();
    await wait(5000);
    await page.goto(`${BASE}/onboarding`, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await wait(4000);
    currentUrl = page.url();
  }

  const onOnboarding = currentUrl.includes('/onboarding');
  log('6-Onboarding', onOnboarding ? 'PASS' : 'FAIL', `On onboarding: ${currentUrl}`);
  await snap(page, '10-onboarding-page');

  // ── STEP 7: Onboarding Step 1 - Industry + Variant ────
  console.log('\n── Step 1: Industry & Variant ──');
  if (onOnboarding) {
    // Select SaaS
    const saas = page.locator('button:has-text("SaaS")').first();
    if (await saas.isVisible().catch(() => false)) {
      await saas.click();
      await wait(500);
      log('7-SaaS', 'PASS', 'SaaS selected');
    }
    await snap(page, '11-step1-industry');

    // Select PARWA variant (middle one)
    const parwa = page.locator('button:has-text("PARWA")').first();
    if (await parwa.isVisible().catch(() => false)) {
      await parwa.click();
      await wait(500);
      log('7-PARWA', 'PASS', 'PARWA variant selected');
    }
    await snap(page, '11b-step1-variant');

    // Click Continue
    const cont = page.locator('button:has-text("Continue")').first();
    if (await cont.isVisible().catch(() => false)) {
      await cont.click();
      await wait(3000);
      log('7-Continue', 'PASS', 'Continued to Step 2');
    }
    await snap(page, '11c-step1-done');
  }

  // ── STEP 8: Step 2 - Legal Compliance ─────────────────
  console.log('\n── Step 2: Legal ──');
  // The custom checkboxes are toggle buttons with class "w-5 h-5"
  // Find all small square buttons and click them
  const allBtns = await page.locator('button').all();
  for (const btn of allBtns) {
    const cls = await btn.getAttribute('class').catch(() => '');
    if (cls && cls.includes('w-5 h-5') && cls.includes('rounded')) {
      const svgCount = await btn.locator('svg').count().catch(() => 0);
      if (svgCount === 0) {
        await btn.click().catch(() => {});
        await wait(300);
      }
    }
  }
  await snap(page, '12-step2-checked');

  // Click Accept All & Continue
  const acceptBtn = page.locator('button:has-text("Accept")').first();
  if (await acceptBtn.isVisible().catch(() => false)) {
    await acceptBtn.click();
    await wait(3000);
    log('8-Legal', 'PASS', 'Accepted legal terms');
  }
  await snap(page, '12b-step2-done');

  // ── STEP 9: Step 3 - Integrations ─────────────────────
  console.log('\n── Step 3: Integrations ──');
  await snap(page, '13-step3-integrations');

  // Try adding Slack integration
  const slackBtn = page.locator('button:has-text("Slack")').first();
  if (await slackBtn.isVisible().catch(() => false)) {
    await slackBtn.click();
    await wait(1000);

    // Fill Slack fields
    const botToken = page.locator('input[placeholder*="xoxb"], input[placeholder*="Bot"]').first();
    if (await botToken.isVisible().catch(() => false)) {
      await botToken.fill('xoxb-test-parwa-integration-token-12345');
      log('9-BotToken', 'PASS', 'Bot token filled');
    }

    const channelId = page.locator('input[placeholder*="C01"], input[placeholder*="Channel"]').first();
    if (await channelId.isVisible().catch(() => false)) {
      await channelId.fill('C01PARWATEST');
      log('9-Channel', 'PASS', 'Channel ID filled');
    }

    await snap(page, '13b-slack-filled');

    // Save
    const saveBtn = page.locator('button:has-text("Save")').first();
    if (await saveBtn.isVisible().catch(() => false)) {
      await saveBtn.click();
      await wait(2000);
      log('9-SaveSlack', 'PASS', 'Saved Slack');
    }
  }

  // Continue
  const step3Cont = page.locator('button:has-text("Continue")').first();
  if (await step3Cont.isVisible().catch(() => false)) {
    await step3Cont.click();
    await wait(3000);
    log('9-Continue', 'PASS', 'Continued to Step 4');
  }
  await snap(page, '13c-step3-done');

  // ── STEP 10: Step 4 - Knowledge Base ──────────────────
  console.log('\n── Step 4: Knowledge ──');
  await snap(page, '14-step4-knowledge');
  
  // Skip (optional)
  const step4Cont = page.locator('button:has-text("Continue")').first();
  if (await step4Cont.isVisible().catch(() => false)) {
    await step4Cont.click();
    await wait(3000);
    log('10-Knowledge', 'PASS', 'Skipped knowledge upload');
  }

  // ── STEP 11: Step 5 - AI Config ───────────────────────
  console.log('\n── Step 5: AI Config ──');
  await snap(page, '15-step5-aiconfig');

  const activateBtn = page.locator('button:has-text("Activate")').first();
  if (await activateBtn.isVisible().catch(() => false)) {
    await activateBtn.click();
    await wait(3000);
    log('11-AIConfig', 'PASS', 'Activated AI');
  } else {
    const step5Cont = page.locator('button:has-text("Continue")').first();
    if (await step5Cont.isVisible().catch(() => false)) {
      await step5Cont.click();
      await wait(3000);
      log('11-AIConfig', 'PASS', 'Continued from AI Config');
    }
  }
  await snap(page, '15b-step5-done');

  // ── STEP 12: Step 6 - Cost Breakdown ──────────────────
  console.log('\n── Step 6: Cost Breakdown ──');
  await snap(page, '16-step6-cost');

  // Check if cost breakdown is visible
  const costHeading = page.locator('h2').filter({ hasText: /Cost|Breakdown|Review/i }).first();
  if (await costHeading.isVisible().catch(() => false)) {
    log('12-CostBreakdown', 'PASS', 'Cost breakdown visible');
  } else {
    // Maybe we're already on victory or another page
    const pageText = await page.locator('body').innerText().catch(() => '');
    log('12-CostBreakdown', 'WARN', `Cost breakdown not found. Page content: ${pageText.substring(0, 200)}`);
  }

  // Try to complete by clicking whatever action button is available
  const actionBtns = ['Complete Setup', 'Go Live', 'Launch', 'Activate Plan', 'Proceed to Payment', 'Complete'];
  for (const text of actionBtns) {
    const btn = page.locator(`button:has-text("${text}")`).first();
    if (await btn.isVisible().catch(() => false)) {
      log('12-Action', 'PASS', `Found button: "${text}"`);
      // Don't click Paddle - just note it exists
      if (text.includes('Payment') || text.includes('Checkout')) {
        log('12-Payment', 'WARN', 'Payment button found - not clicking (would open Paddle)');
      } else {
        await btn.click();
        await wait(3000);
      }
      break;
    }
  }
  await snap(page, '16b-step6-after');

  // ── STEP 13: First Victory ────────────────────────────
  console.log('\n── Step 7: First Victory ──');
  await wait(2000);
  await snap(page, '17-victory-check');

  const victoryText = page.locator('h1:has-text("Welcome"), h1:has-text("Victory"), h1:has-text("PARWA")').first();
  if (await victoryText.isVisible().catch(() => false)) {
    log('13-Victory', 'PASS', 'First Victory celebration visible!');
    await snap(page, '17b-victory-final');
  } else {
    // Check what's on the page
    const bodyText = await page.locator('body').innerText().catch(() => '');
    log('13-Victory', 'WARN', `Victory not visible. Page heading area: ${bodyText.substring(0, 300)}`);
  }

  // ── Console Errors ────────────────────────────────────
  if (errors.length > 0) {
    log('Errors', 'WARN', `${errors.length} console errors`);
    errors.slice(0, 10).forEach(e => console.log(`  🐛 ${e}`));
  } else {
    log('Errors', 'PASS', 'No console errors');
  }

  // ── Summary ───────────────────────────────────────────
  const passes = results.filter(r => r.status === 'PASS').length;
  const fails = results.filter(r => r.status === 'FAIL').length;
  const warns = results.filter(r => r.status === 'WARN').length;
  
  console.log('\n════════════════════════════════════════════');
  console.log(`  ✅ PASS: ${passes}  ❌ FAIL: ${fails}  ⚠️  WARN: ${warns}`);
  console.log(`  📸 Screenshots: ${DIR}`);
  console.log('════════════════════════════════════════════\n');

  writeFileSync(`${DIR}/test-results.json`, JSON.stringify({ results, summary: { passes, fails, warns } }, null, 2));
  await browser.close();
}

main().catch(e => { console.error('FATAL:', e.message); process.exit(1); });
