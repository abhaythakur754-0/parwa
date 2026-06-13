const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = '/home/z/my-project/download/parwa-proof';
const BACKEND_URL = 'http://localhost:8000';
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
    // TEST 1: LOGIN PAGE
    // ══════════════════════════════════════════════════
    log('━━━ TEST 1: LOGIN PAGE ━━━');
    await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    await screenshot(page, 'step01-login-page');
    
    // Find login form elements
    const emailSelectors = [
      'input[type="email"]',
      'input[name="email"]',
      'input[placeholder*="email" i]',
      'input[placeholder*="Email" i]',
    ];
    let emailInput = null;
    for (const sel of emailSelectors) {
      emailInput = await page.$(sel);
      if (emailInput) break;
    }
    
    const passwordInput = await page.$('input[type="password"]');
    
    if (emailInput && passwordInput) {
      log('Found login form - filling credentials');
      await emailInput.fill('test@parwa.buzz');
      await passwordInput.fill('Test1234!');
      await screenshot(page, 'step02-login-filled');
      
      // Click submit
      const submitBtn = await page.$('button[type="submit"]');
      if (submitBtn) {
        log('Clicking login button...');
        await submitBtn.click();
        await page.waitForTimeout(5000);
      } else {
        log('⚠️ No submit button found');
      }
    } else {
      log(`⚠️ Login form not found. Email: ${!!emailInput}, Password: ${!!passwordInput}`);
    }
    
    await screenshot(page, 'step03-after-login');
    log(`URL after login: ${page.url()}`);
    
    // ══════════════════════════════════════════════════
    // TEST 2: NAVIGATE TO ONBOARDING
    // ══════════════════════════════════════════════════
    log('━━━ TEST 2: ONBOARDING PAGE ━━━');
    
    // Set pricing context in localStorage
    await page.evaluate(() => {
      localStorage.setItem('parwa_pricing_context', JSON.stringify({
        industry: 'saas',
        variant: 'parwa',
        variants: ['parwa'],
        totalMonthly: 299,
        timestamp: new Date().toISOString(),
      }));
    });
    
    await page.goto(`${FRONTEND_URL}/onboarding?source=pricing&industry=saas`, {
      waitUntil: 'networkidle',
      timeout: 30000,
    });
    await page.waitForTimeout(3000);
    await screenshot(page, 'step04-onboarding-page');
    
    const bodyText = await page.textContent('body');
    log(`Onboarding page text: ${bodyText?.slice(0, 300)}`);
    
    // Check for error message
    if (bodyText?.includes('something went wrong') || bodyText?.includes('Something went wrong')) {
      log('❌ "Something went wrong" detected on onboarding page!');
    } else if (bodyText?.includes('Loading onboarding')) {
      log('⚠️ Still loading...');
    } else {
      log('✅ Onboarding page loaded successfully');
    }
    
    // ══════════════════════════════════════════════════
    // TEST 3: STEP THROUGH ONBOARDING WIZARD
    // ══════════════════════════════════════════════════
    log('━━━ TEST 3: ONBOARDING WIZARD STEPS ━━━');
    
    // Step 1: Industry/Variant selection
    log('Step 1: Industry/Variant Selection');
    // Try to click on SaaS industry
    const allText = await page.textContent('body');
    if (allText?.includes('SaaS') || allText?.includes('saas')) {
      const cards = await page.$$('[class*="card"], [class*="option"], button');
      for (const card of cards) {
        const text = await card.textContent();
        if (text?.trim() === 'SaaS' || text?.includes('SaaS')) {
          log('Clicking SaaS industry card');
          await card.click();
          await page.waitForTimeout(1000);
          break;
        }
      }
    }
    await screenshot(page, 'step05-industry-selected');
    
    // Try to click PARWA variant
    const variantCards = await page.$$('[class*="card"], [class*="option"], button');
    for (const card of variantCards) {
      const text = await card.textContent();
      if (text?.includes('PARWA') && !text?.includes('Mini') && !text?.includes('High')) {
        log('Clicking PARWA variant');
        await card.click();
        await page.waitForTimeout(1000);
        break;
      }
    }
    await screenshot(page, 'step06-variant-selected');
    
    // Click Continue
    const continueButtons = await page.$$('button');
    for (const btn of continueButtons) {
      const text = await btn.textContent();
      const isEnabled = await btn.isEnabled();
      if (isEnabled && text?.includes('Continue')) {
        log(`Clicking "${text.trim()}"`);
        await btn.click();
        await page.waitForTimeout(3000);
        break;
      }
    }
    await screenshot(page, 'step07-step1-done');
    
    // Steps 2-6: Keep clicking buttons and interacting with each step
    for (let step = 2; step <= 7; step++) {
      log(`--- Step iteration ${step} ---`);
      await page.waitForTimeout(2000);
      
      // First check for checkboxes (Legal step)
      // Try native checkboxes first
      const nativeCheckboxes = await page.$$('input[type="checkbox"]');
      if (nativeCheckboxes.length > 0) {
        log(`Found ${nativeCheckboxes.length} native checkboxes - checking them all`);
        for (const cb of nativeCheckboxes) {
          try {
            const checked = await cb.isChecked();
            if (!checked) {
              await cb.click();
              await page.waitForTimeout(300);
            }
          } catch (e) { /* ignore */ }
        }
      }
      
      // Try custom checkbox elements (role="checkbox" or class containing "check")
      const customCheckboxes = await page.$$('[role="checkbox"], [class*="checkbox"], [class*="check-box"], [data-state]');
      if (customCheckboxes.length > 0) {
        log(`Found ${customCheckboxes.length} custom checkboxes - clicking them all`);
        for (const cb of customCheckboxes) {
          try {
            await cb.click();
            await page.waitForTimeout(300);
          } catch (e) { /* ignore */ }
        }
      }
      
      if (nativeCheckboxes.length > 0 || customCheckboxes.length > 0) {
        await screenshot(page, `step${step.toString().padStart(2,'0')}-checkboxes`);
      }
      
      // Find and click the appropriate button - expanded search
      // Wait a moment for checkboxes to update state
      await page.waitForTimeout(500);
      const buttons = await page.$$('button');
      let clicked = false;
      for (const btn of buttons) {
        const text = await btn.textContent();
        const isEnabled = await btn.isEnabled();
        const trimmedText = text?.trim();
        
        if (isEnabled && trimmedText && (
          trimmedText.includes('Continue') ||
          trimmedText.includes('Accept') ||
          trimmedText.includes('Agree') ||
          trimmedText.includes('Activate') ||
          trimmedText.includes('Confirm') ||
          trimmedText.includes('Complete') ||
          trimmedText.includes('Next') ||
          trimmedText.includes('Get Started') ||
          trimmedText.includes('Skip') ||
          trimmedText.includes('optional')
        )) {
          log(`Clicking "${trimmedText}"`);
          await btn.click();
          clicked = true;
          await page.waitForTimeout(4000);
          break;
        }
      }
      
      // If no button found, try clicking any enabled button that's not "Back" or "Logout"
      if (!clicked) {
        for (const btn of buttons) {
          const text = await btn.textContent();
          const isEnabled = await btn.isEnabled();
          const trimmedText = text?.trim();
          
          if (isEnabled && trimmedText && 
              !trimmedText.includes('Back') && 
              !trimmedText.includes('Logout') &&
              !trimmedText.includes('Google') &&
              trimmedText.length > 2) {
            log(`Fallback: Clicking "${trimmedText}"`);
            await btn.click();
            clicked = true;
            await page.waitForTimeout(4000);
            break;
          }
        }
      }
      
      if (!clicked) {
        log(`⚠️ No actionable button found for step ${step}`);
      }
      
      await screenshot(page, `step${step.toString().padStart(2,'0')}-completed`);
      
      // Check for errors
      const currentText = await page.textContent('body');
      if (currentText?.includes('something went wrong') || currentText?.includes('Something went wrong')) {
        log(`❌ "Something went wrong" at step ${step}!`);
      }
      
      // Check if we've reached First Victory
      if (currentText?.includes('Welcome to PARWA') || currentText?.includes('First Victory')) {
        log('✅ Reached First Victory page!');
        break;
      }
    }
    
    // ══════════════════════════════════════════════════
    // TEST 4: FIRST VICTORY
    // ══════════════════════════════════════════════════
    log('━━━ TEST 4: FIRST VICTORY ━━━');
    await screenshot(page, 'step12-first-victory');
    
    const victoryText = await page.textContent('body');
    if (victoryText?.includes('Welcome to PARWA') || victoryText?.includes('Jarvis')) {
      log('✅ First Victory page displayed!');
    } else {
      log(`First Victory content: ${victoryText?.slice(0, 300)}`);
    }
    
    // Click Go to Dashboard
    const dashBtns = await page.$$('button');
    for (const btn of dashBtns) {
      const text = await btn.textContent();
      if (text?.includes('Dashboard') || text?.includes('Go to')) {
        log(`Clicking "${text.trim()}"`);
        await btn.click();
        await page.waitForTimeout(3000);
        break;
      }
    }
    await screenshot(page, 'step13-dashboard');
    
    // ══════════════════════════════════════════════════
    // SUMMARY
    // ══════════════════════════════════════════════════
    log('━━━ TEST SUMMARY ━━━');
    log(`Final URL: ${page.url()}`);
    log(`Console errors: ${errors.length}`);
    errors.slice(0, 10).forEach(e => log(`  ${e}`));
    
    const finalText = await page.textContent('body');
    if (finalText?.includes('something went wrong') || finalText?.includes('Something went wrong')) {
      log('❌ "Something went wrong" found somewhere in the flow');
    } else {
      log('✅ No "Something went wrong" error detected!');
    }
    
    log(`Screenshots saved to: ${SCREENSHOT_DIR}`);
    
  } catch (err) {
    log(`❌ Error: ${err.message}`);
    await screenshot(page, 'error-state').catch(() => {});
  } finally {
    await browser.close();
  }
})();
