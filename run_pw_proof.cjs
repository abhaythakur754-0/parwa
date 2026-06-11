const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = '/home/z/my-project/download/parwa-proof';
const FRONTEND_URL = 'http://localhost:3000';

if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

function log(msg) {
  const ts = new Date().toISOString().split('T')[1].split('.')[0];
  console.log(`[${ts}] ${msg}`);
}

async function screenshot(page, name) {
  const p = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: p, fullPage: true });
  log(`📸 ${name}.png`);
}

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  
  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('requestfailed', req => errors.push(`FAIL: ${req.method()} ${req.url()}`));
  
  try {
    // ══════════════════════════════════════════════════
    // STEP 1: LOGIN
    // ══════════════════════════════════════════════════
    log('━━━ STEP 1: LOGIN ━━━');
    await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    await screenshot(page, 'proof-01-login-page');
    
    const emailInput = await page.$('input[type="email"], input[name="email"]');
    const passwordInput = await page.$('input[type="password"]');
    await emailInput.fill('test@parwa.buzz');
    await passwordInput.fill('Test1234!');
    await screenshot(page, 'proof-02-login-filled');
    
    const submitBtn = await page.$('button[type="submit"]');
    await submitBtn.click();
    await page.waitForTimeout(5000);
    await screenshot(page, 'proof-03-after-login');
    log(`After login URL: ${page.url()}`);
    
    if (page.url().includes('/onboarding') || page.url().includes('/dashboard')) {
      log('✅ Login successful - redirected to onboarding/dashboard');
    } else {
      log('⚠️ Login may have failed - still on login page');
    }
    
    // ══════════════════════════════════════════════════
    // STEP 2: ONBOARDING PAGE (Step 1: Industry/Variant)
    // ══════════════════════════════════════════════════
    log('━━━ STEP 2: ONBOARDING - INDUSTRY/VARIANT ━━━');
    
    // Set pricing context
    await page.evaluate(() => {
      localStorage.setItem('parwa_pricing_context', JSON.stringify({
        industry: 'saas', variant: 'parwa', variants: ['parwa'], totalMonthly: 299
      }));
    });
    
    if (!page.url().includes('/onboarding')) {
      await page.goto(`${FRONTEND_URL}/onboarding?source=pricing&industry=saas`, {
        waitUntil: 'networkidle', timeout: 30000
      });
    }
    await page.waitForTimeout(3000);
    await screenshot(page, 'proof-04-onboarding-step1');
    
    // Click SaaS industry
    const saasBtn = page.locator('button:has-text("SaaS"), div:has-text("SaaS")').first();
    if (await saasBtn.count() > 0) {
      await saasBtn.click();
      await page.waitForTimeout(1000);
      log('Clicked SaaS industry');
    }
    
    // Click PARWA variant (not Mini or High)
    const allButtons = await page.$$('button');
    for (const btn of allButtons) {
      const text = await btn.textContent();
      if (text?.trim() === 'PARWA') {
        await btn.click();
        await page.waitForTimeout(1000);
        log('Clicked PARWA variant');
        break;
      }
    }
    await screenshot(page, 'proof-05-variant-selected');
    
    // Click Continue button
    const continueBtn = page.locator('button:has-text("Continue")').first();
    if (await continueBtn.count() > 0 && await continueBtn.isEnabled()) {
      await continueBtn.click();
      await page.waitForTimeout(3000);
      log('Clicked Continue');
    }
    await screenshot(page, 'proof-06-step1-complete');
    
    // ══════════════════════════════════════════════════
    // STEP 3: LEGAL COMPLIANCE
    // ══════════════════════════════════════════════════
    log('━━━ STEP 3: LEGAL COMPLIANCE ━━━');
    
    // The checkboxes are <button> elements with class "w-5 h-5 rounded"
    const checkboxButtons = await page.$$('button.w-5');
    log(`Found ${checkboxButtons.length} checkbox buttons`);
    for (const btn of checkboxButtons) {
      await btn.click();
      await page.waitForTimeout(300);
    }
    await screenshot(page, 'proof-07-checkboxes-checked');
    
    // Click Accept All & Continue
    const acceptBtn = page.locator('button:has-text("Accept All")');
    if (await acceptBtn.count() > 0 && await acceptBtn.isEnabled()) {
      await acceptBtn.click();
      log('✅ Clicked Accept All & Continue');
      await page.waitForTimeout(4000);
    }
    await screenshot(page, 'proof-08-step2-legal-complete');
    
    // ══════════════════════════════════════════════════
    // STEP 4: INTEGRATION SETUP
    // ══════════════════════════════════════════════════
    log('━━━ STEP 4: INTEGRATION SETUP ━━━');
    await screenshot(page, 'proof-09-integration-step');
    
    // Click Continue/Skip
    const intContinue = page.locator('button:has-text("Continue"), button:has-text("Skip"), button:has-text("Next")').first();
    if (await intContinue.count() > 0 && await intContinue.isEnabled()) {
      await intContinue.click();
      log('Clicked integration continue');
      await page.waitForTimeout(3000);
    }
    await screenshot(page, 'proof-10-step3-integration-complete');
    
    // ══════════════════════════════════════════════════
    // STEP 5: KNOWLEDGE UPLOAD
    // ══════════════════════════════════════════════════
    log('━━━ STEP 5: KNOWLEDGE UPLOAD ━━━');
    await screenshot(page, 'proof-11-knowledge-step');
    
    // Click Continue (skip upload)
    const knContinue = page.locator('button:has-text("Continue"), button:has-text("Skip"), button:has-text("Next")').first();
    if (await knContinue.count() > 0 && await knContinue.isEnabled()) {
      await knContinue.click();
      log('Clicked knowledge continue');
      await page.waitForTimeout(3000);
    }
    await screenshot(page, 'proof-12-step4-knowledge-complete');
    
    // ══════════════════════════════════════════════════
    // STEP 6: AI CONFIG
    // ══════════════════════════════════════════════════
    log('━━━ STEP 6: AI CONFIG ━━━');
    await screenshot(page, 'proof-13-ai-config-step');
    
    // Click Activate AI Assistant
    const activateBtn = page.locator('button:has-text("Activate"), button:has-text("Continue")').first();
    if (await activateBtn.count() > 0 && await activateBtn.isEnabled()) {
      await activateBtn.click();
      log('Clicked Activate');
      await page.waitForTimeout(3000);
    }
    await screenshot(page, 'proof-14-step5-ai-config-complete');
    
    // ══════════════════════════════════════════════════
    // STEP 7: COST BREAKDOWN / REVIEW
    // ══════════════════════════════════════════════════
    log('━━━ STEP 7: COST BREAKDOWN ━━━');
    await screenshot(page, 'proof-15-cost-breakdown-step');
    
    const costBtn = page.locator('button:has-text("Continue"), button:has-text("Confirm"), button:has-text("Complete")').first();
    if (await costBtn.count() > 0 && await costBtn.isEnabled()) {
      await costBtn.click();
      log('Clicked cost breakdown continue');
      await page.waitForTimeout(4000);
    }
    await screenshot(page, 'proof-16-step6-cost-complete');
    
    // ══════════════════════════════════════════════════
    // STEP 8: FIRST VICTORY
    // ══════════════════════════════════════════════════
    log('━━━ STEP 8: FIRST VICTORY ━━━');
    await screenshot(page, 'proof-17-first-victory');
    
    // Verify First Victory page
    const victoryText = await page.textContent('body');
    if (victoryText?.includes('Welcome to PARWA') || victoryText?.includes('Jarvis')) {
      log('✅ FIRST VICTORY PAGE DISPLAYED!');
    }
    
    // Click Go to Dashboard
    const dashBtn = page.locator('button:has-text("Dashboard"), button:has-text("Go to")').first();
    if (await dashBtn.count() > 0) {
      await dashBtn.click();
      log('Clicked Go to Dashboard');
      await page.waitForTimeout(5000);
    }
    await screenshot(page, 'proof-18-dashboard-redirect');
    
    // ══════════════════════════════════════════════════
    // SUMMARY
    // ══════════════════════════════════════════════════
    log('━━━ TEST SUMMARY ━━━');
    log(`Final URL: ${page.url()}`);
    log(`Console errors: ${errors.length}`);
    errors.slice(0, 5).forEach(e => log(`  ${e}`));
    
    const finalText = await page.textContent('body');
    if (finalText?.includes('something went wrong') || finalText?.includes('Something went wrong')) {
      log('❌ "Something went wrong" found!');
    } else {
      log('✅ NO "Something went wrong" errors!');
    }
    
    log(`\nScreenshots saved to: ${SCREENSHOT_DIR}`);
    
  } catch (err) {
    log(`❌ Error: ${err.message}`);
    await screenshot(page, 'error-state').catch(() => {});
  } finally {
    await browser.close();
  }
})();
