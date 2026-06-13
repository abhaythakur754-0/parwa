import { chromium } from 'playwright';
import fs from 'fs';

const DIR = '/home/z/my-project/download/full-journey-proof';

async function shot(page, name) {
  await page.screenshot({ path: `${DIR}/${name}.png`, fullPage: true });
  console.log(`✅ ${name}`);
}

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  // === REGISTER + LOGIN via API ===
  const ts = Date.now();
  const email = `variant${ts}@parwa.io`;
  console.log(`\n📝 Registering: ${email}`);
  
  const regResp = await ctx.request.post('http://127.0.0.1:3000/api/auth/register', {
    data: { name: 'Variant Tester', email, password: 'TestPass123!' }
  });
  console.log(`  Register: ${regResp.status()}`);
  const regData = await regResp.json().catch(() => ({}));
  console.log(`  Response: ${JSON.stringify(regData).substring(0, 300)}`);

  // If register failed, try login with existing user
  let loginResp = await ctx.request.post('http://127.0.0.1:3000/api/auth/login', {
    data: { email, password: 'TestPass123!' }
  });
  console.log(`  Login: ${loginResp.status()}`);
  
  if (!loginResp.ok) {
    // Try registering again with different approach
    console.log('  Retrying with different email...');
    const email2 = `test${ts+1}@parwa.io`;
    const reg2 = await ctx.request.post('http://127.0.0.1:3000/api/auth/register', {
      data: { name: 'Variant Tester', email: email2, password: 'TestPass123!' }
    });
    console.log(`  Register2: ${reg2.status()}`);
    loginResp = await ctx.request.post('http://127.0.0.1:3000/api/auth/login', {
      data: { email: email2, password: 'TestPass123!' }
    });
    console.log(`  Login2: ${loginResp.status()}`);
  }
  
  const loginData = await loginResp.json().catch(() => ({}));
  console.log(`  Login response: ${JSON.stringify(loginData).substring(0, 300)}`);

  // === 1. MODELS / PRICING PAGE ===
  console.log('\n📍 1. Models/Pricing Page');
  await page.goto('http://127.0.0.1:3000/models', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  await shot(page, '01-models-page');

  // === 2. SELECT INDUSTRY TAB ===
  console.log('\n📍 2. Select Industry');
  // Try to find and click SaaS industry tab
  const saasTab = page.locator('button:has-text("SaaS"), [data-industry="saas"]').first();
  if (await saasTab.isVisible()) {
    await saasTab.click();
    await page.waitForTimeout(1000);
    await shot(page, '02-saas-industry-selected');
    console.log('  Clicked SaaS tab');
  } else {
    console.log('  No SaaS tab found, checking page...');
    const text = await page.locator('body').innerText();
    console.log('  Page text (first 500):', text.substring(0, 500));
    await shot(page, '02-no-saas-tab');
  }

  // === 3. CLICK "HIRE AGENT" ON PARWA VARIANT ===
  console.log('\n📍 3. Click Hire Agent on PARWA variant');
  // Look for the PARWA (middle) variant hire button
  const hireBtn = page.locator('button:has-text("Hire Agent"), button:has-text("Get Started"), button:has-text("Choose")').first();
  if (await hireBtn.isVisible()) {
    await hireBtn.click();
    await page.waitForTimeout(2000);
    await shot(page, '03-confirmation-modal');
    console.log('  Clicked Hire Agent');

    // === 4. CLICK CONFIRM IN MODAL ===
    console.log('\n📍 4. Confirm selection');
    const confirmBtn = page.locator('button:has-text("Confirm"), button:has-text("Yes"), button:has-text("Proceed"), button:has-text("Continue")').first();
    if (await confirmBtn.isVisible()) {
      await confirmBtn.click();
      await page.waitForTimeout(3000);
      await shot(page, '04-after-confirm-redirect');
      console.log('  Clicked Confirm, URL:', page.url());
    }
  } else {
    console.log('  No Hire Agent button found');
    // Check what buttons exist
    const allBtns = await page.locator('button').allTextContents();
    console.log('  Available buttons:', allBtns.join(', '));
  }

  // === 5. ONBOARDING FLOW ===
  // Navigate directly to onboarding (may have been redirected to login)
  console.log('\n📍 5. Navigate to Onboarding');
  await page.goto('http://127.0.0.1:3000/onboarding', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  let currentUrl = page.url();
  console.log(`  URL: ${currentUrl}`);
  await shot(page, '05-onboarding-page');

  // If redirected to login, login through UI
  if (currentUrl.includes('login') || currentUrl.includes('auth')) {
    console.log('  Redirected to login, filling credentials...');
    const emailField = page.locator('input[type="email"], input[name="email"]').first();
    const passField = page.locator('input[type="password"]').first();
    if (await emailField.isVisible()) {
      await emailField.fill(email);
      await passField.fill('TestPass123!');
      await shot(page, '05a-login-form-filled');
      
      const loginBtn = page.locator('button[type="submit"]').first();
      await loginBtn.click();
      await page.waitForTimeout(4000);
      currentUrl = page.url();
      console.log(`  After login URL: ${currentUrl}`);
      await shot(page, '05b-after-login');
    }
  }

  // === 6. STEP 1: INDUSTRY + VARIANT ===
  console.log('\n📍 6. Step 1: Industry + Variant Selection');
  if (page.url().includes('onboarding')) {
    // Look for industry cards
    const industryCards = page.locator('[data-industry], .industry-card, button:has-text("SaaS"), div:has-text("SaaS")').first();
    if (await industryCards.isVisible({ timeout: 3000 }).catch(() => false)) {
      await industryCards.click();
      await page.waitForTimeout(1000);
      await shot(page, '06-step1-industry-selected');
    }
    
    // Look for variant selection
    const variantBtn = page.locator('button:has-text("PARWA"), [data-variant="growth"], .variant-card').first();
    if (await variantBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await variantBtn.click();
      await page.waitForTimeout(1000);
      await shot(page, '07-step1-variant-selected');
    }
    
    // Click Continue/Next
    const continueBtn = page.locator('button:has-text("Continue"), button:has-text("Next"), button:has-text("Proceed")').first();
    if (await continueBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await continueBtn.click();
      await page.waitForTimeout(2000);
      await shot(page, '08-step1-completed');
      console.log('  Step 1 completed, URL:', page.url());
    }
  }

  // === 7. STEP 2: LEGAL COMPLIANCE ===
  console.log('\n📍 7. Step 2: Legal Compliance');
  if (page.url().includes('onboarding')) {
    // Check checkboxes
    const checkboxes = page.locator('input[type="checkbox"]');
    const count = await checkboxes.count();
    for (let i = 0; i < count; i++) {
      if (!(await checkboxes.nth(i).isChecked())) {
        await checkboxes.nth(i).check();
      }
    }
    await page.waitForTimeout(500);
    await shot(page, '09-step2-legal-checkboxes');

    // Click Continue
    const continueBtn2 = page.locator('button:has-text("Continue"), button:has-text("Agree"), button:has-text("Accept"), button:has-text("Next")').first();
    if (await continueBtn2.isVisible({ timeout: 2000 }).catch(() => false)) {
      await continueBtn2.click();
      await page.waitForTimeout(2000);
      await shot(page, '10-step2-completed');
      console.log('  Step 2 completed');
    }
  }

  // === 8. STEP 3: INTEGRATIONS + API KEY ===
  console.log('\n📍 8. Step 3: Integrations');
  if (page.url().includes('onboarding')) {
    await shot(page, '11-step3-integrations');
    const continueBtn3 = page.locator('button:has-text("Continue"), button:has-text("Next"), button:has-text("Skip"), button:has-text("Proceed")').first();
    if (await continueBtn3.isVisible({ timeout: 2000 }).catch(() => false)) {
      await continueBtn3.click();
      await page.waitForTimeout(2000);
      await shot(page, '12-step3-completed');
      console.log('  Step 3 completed');
    }
  }

  // === 9. STEP 4: KNOWLEDGE BASE ===
  console.log('\n📍 9. Step 4: Knowledge Base');
  if (page.url().includes('onboarding')) {
    await shot(page, '13-step4-knowledge');
    const continueBtn4 = page.locator('button:has-text("Continue"), button:has-text("Next"), button:has-text("Skip")').first();
    if (await continueBtn4.isVisible({ timeout: 2000 }).catch(() => false)) {
      await continueBtn4.click();
      await page.waitForTimeout(2000);
      await shot(page, '14-step4-completed');
      console.log('  Step 4 completed');
    }
  }

  // === 10. STEP 5: AI CONFIG ===
  console.log('\n📍 10. Step 5: AI Config');
  if (page.url().includes('onboarding')) {
    await shot(page, '15-step5-ai-config');
    const continueBtn5 = page.locator('button:has-text("Continue"), button:has-text("Next"), button:has-text("Save")').first();
    if (await continueBtn5.isVisible({ timeout: 2000 }).catch(() => false)) {
      await continueBtn5.click();
      await page.waitForTimeout(2000);
      await shot(page, '16-step5-completed');
      console.log('  Step 5 completed');
    }
  }

  // === 11. STEP 6: COST BREAKDOWN / PAYMENT ===
  console.log('\n📍 11. Step 6: Cost Breakdown');
  if (page.url().includes('onboarding')) {
    await shot(page, '17-step6-cost-breakdown');
    // Check if Paddle checkout button exists
    const payBtn = page.locator('button:has-text("Pay"), button:has-text("Checkout"), button:has-text("Subscribe"), button:has-text("Complete"), button:has-text("Activate")').first();
    if (await payBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await shot(page, '18-step6-payment-ready');
      console.log('  Payment button visible');
    }
    const continueBtn6 = page.locator('button:has-text("Complete"), button:has-text("Finish"), button:has-text("Activate"), button:has-text("Continue")').first();
    if (await continueBtn6.isVisible({ timeout: 2000 }).catch(() => false)) {
      await continueBtn6.click();
      await page.waitForTimeout(3000);
      await shot(page, '19-step6-completed');
      console.log('  Step 6 completed');
    }
  }

  // === 12. STEP 7: FIRST VICTORY ===
  console.log('\n📍 12. Step 7: First Victory');
  if (page.url().includes('onboarding')) {
    await shot(page, '20-step7-first-victory');
  }

  await browser.close();
  console.log('\n✅ All screenshots captured!');
})();
