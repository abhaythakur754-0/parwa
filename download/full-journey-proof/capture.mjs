import { chromium } from 'playwright';
import fs from 'fs';

const DIR = '/home/z/my-project/download/full-journey-proof';
const BASE = 'http://0.0.0.0:3000';

async function shot(page, name) {
  try {
    await page.screenshot({ path: `${DIR}/${name}.png`, fullPage: false });
    console.log(`✅ ${name}`);
  } catch(e) {
    console.log(`❌ ${name}: ${e.message}`);
  }
}

(async () => {
  console.log('Launching browser...');
  const browser = await chromium.launch({ 
    headless: true, 
    args: ['--no-sandbox','--disable-setuid-sandbox','--disable-gpu','--disable-dev-shm-usage','--single-process'] 
  });
  console.log('Browser launched');
  
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  console.log('Page created');

  // Register via PAGE navigation (not context.request which opens separate connection)
  console.log('\n📍 Register user');
  const email = `proof${Date.now()}@parwa.io`;
  const password = 'TestPass123!';
  
  // Use page.evaluate to do fetch inside the browser context
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 30000 });
  console.log('On login page');
  
  // Register via fetch inside browser
  const regResult = await page.evaluate(async (creds) => {
    try {
      const r = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(creds)
      });
      return { status: r.status, data: await r.json() };
    } catch(e) {
      return { status: 0, error: e.message };
    }
  }, { name: 'Proof User', email, password: password });
  console.log(`Register: ${regResult.status}`, JSON.stringify(regResult.data || regResult.error || '').substring(0, 200));

  // ── 1. MODELS PAGE ──
  console.log('\n📍 1. Models Page');
  await page.goto(`${BASE}/models`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  await shot(page, '01-models-page');

  // ── 2. Click SaaS tab ──
  console.log('\n📍 2. SaaS Industry');
  const saasBtn = page.locator('button:has-text("SaaS"), [data-industry="saas"]').first();
  if (await saasBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await saasBtn.click();
    await page.waitForTimeout(1500);
    await shot(page, '02-saas-selected');
    console.log('  SaaS clicked');
  } else {
    await shot(page, '02-no-saas-tab');
    console.log('  No SaaS tab found');
  }

  // ── 3. Hire Agent on PARWA ──
  console.log('\n📍 3. Hire Agent');
  const hireBtns = await page.locator('button:has-text("Hire Agent")').all();
  console.log(`  Found ${hireBtns.length} buttons`);
  if (hireBtns.length >= 2) {
    await hireBtns[1].click();
    await page.waitForTimeout(2000);
    await shot(page, '03-confirmation-modal');
    console.log('  Clicked middle Hire Agent');
  } else if (hireBtns.length === 1) {
    await hireBtns[0].click();
    await page.waitForTimeout(2000);
    await shot(page, '03-confirmation-modal');
  } else {
    const alt = page.locator('button:has-text("Get Started"), button:has-text("Choose")').first();
    if (await alt.isVisible({ timeout: 2000 }).catch(() => false)) {
      await alt.click();
      await page.waitForTimeout(2000);
      await shot(page, '03-alt-button');
    }
  }

  // ── 4. Confirm ──
  console.log('\n📍 4. Confirm');
  const confirmBtn = page.locator('button:has-text("Confirm"), button:has-text("Proceed"), button:has-text("Yes")').first();
  if (await confirmBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await confirmBtn.click();
    await page.waitForTimeout(3000);
    await shot(page, '04-after-confirm');
    console.log(`  URL: ${page.url()}`);
  }

  // ── 5. Login via UI ──
  console.log('\n📍 5. Login UI');
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);
  await shot(page, '05-login-page');

  const emailInput = page.locator('input[type="email"], input[name="email"], input[placeholder*="mail"]').first();
  const passInput = page.locator('input[type="password"]').first();
  await emailInput.fill(email);
  await passInput.fill(password);
  await shot(page, '06-login-filled');

  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(4000);
  await shot(page, '07-after-login');
  console.log(`  URL after login: ${page.url()}`);

  // ── 6. Onboarding ──
  console.log('\n📍 6. Onboarding');
  await page.goto(`${BASE}/onboarding`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  console.log(`  Onboarding URL: ${page.url()}`);
  
  if (page.url().includes('login')) {
    console.log('  Redirected - trying login again');
    const ei = page.locator('input[type="email"], input[name="email"]').first();
    const pi = page.locator('input[type="password"]').first();
    await ei.fill(email);
    await pi.fill(password);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(4000);
    await page.goto(`${BASE}/onboarding`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
  }

  // ── STEP 1 ──
  if (page.url().includes('onboarding')) {
    console.log('\n📍 7. Step 1: Industry + Variant');
    await shot(page, '08-step1-initial');
    
    const saasCard = page.locator('button:has-text("SaaS"), div:has-text("SaaS")').first();
    if (await saasCard.isVisible({ timeout: 3000 }).catch(() => false)) {
      await saasCard.click();
      await page.waitForTimeout(1000);
      await shot(page, '09-step1-saas');
    }

    const parwaCard = page.locator('button:has-text("PARWA"), div:has-text("PARWA")').first();
    if (await parwaCard.isVisible({ timeout: 3000 }).catch(() => false)) {
      await parwaCard.click();
      await page.waitForTimeout(1000);
      await shot(page, '10-step1-parwa');
    }

    const cont1 = page.locator('button:has-text("Continue"), button:has-text("Next")').first();
    if (await cont1.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cont1.click();
      await page.waitForTimeout(2000);
      await shot(page, '11-step1-done');
    }
  }

  // ── STEP 2 ──
  if (page.url().includes('onboarding')) {
    console.log('\n📍 8. Step 2: Legal');
    await shot(page, '12-step2-legal');
    const cbs = page.locator('input[type="checkbox"]');
    const n = await cbs.count();
    for (let i = 0; i < n; i++) {
      if (!(await cbs.nth(i).isChecked())) await cbs.nth(i).check();
    }
    await page.waitForTimeout(500);
    await shot(page, '13-step2-checked');
    
    const cont2 = page.locator('button:has-text("Continue"), button:has-text("Agree"), button:has-text("Accept")').first();
    if (await cont2.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cont2.click();
      await page.waitForTimeout(2000);
      await shot(page, '14-step2-done');
    }
  }

  // ── STEP 3 ──
  if (page.url().includes('onboarding')) {
    console.log('\n📍 9. Step 3: Integrations');
    await shot(page, '15-step3-integrations');
    await page.evaluate(() => window.scrollBy(0, 500));
    await page.waitForTimeout(500);
    await shot(page, '16-step3-api-keys');
    
    const cont3 = page.locator('button:has-text("Continue"), button:has-text("Next"), button:has-text("Skip")').first();
    if (await cont3.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cont3.click();
      await page.waitForTimeout(2000);
      await shot(page, '17-step3-done');
    }
  }

  // ── STEP 4 ──
  if (page.url().includes('onboarding')) {
    console.log('\n📍 10. Step 4: Knowledge');
    await shot(page, '18-step4-knowledge');
    const cont4 = page.locator('button:has-text("Continue"), button:has-text("Next"), button:has-text("Skip")').first();
    if (await cont4.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cont4.click();
      await page.waitForTimeout(2000);
      await shot(page, '19-step4-done');
    }
  }

  // ── STEP 5 ──
  if (page.url().includes('onboarding')) {
    console.log('\n📍 11. Step 5: AI Config');
    await shot(page, '20-step5-ai-config');
    const cont5 = page.locator('button:has-text("Continue"), button:has-text("Next"), button:has-text("Save")').first();
    if (await cont5.isVisible({ timeout: 2000 }).catch(() => false)) {
      await cont5.click();
      await page.waitForTimeout(2000);
      await shot(page, '21-step5-done');
    }
  }

  // ── STEP 6 ──
  if (page.url().includes('onboarding')) {
    console.log('\n📍 12. Step 6: Cost + Payment');
    await shot(page, '22-step6-cost-breakdown');
    await page.evaluate(() => window.scrollBy(0, 500));
    await page.waitForTimeout(500);
    await shot(page, '23-step6-payment');
  }

  // ── STEP 7 ──
  const completeBtn = page.locator('button:has-text("Complete"), button:has-text("Finish"), button:has-text("Activate")').first();
  if (await completeBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    console.log('\n📍 13. First Victory');
    await completeBtn.click();
    await page.waitForTimeout(4000);
    await shot(page, '24-first-victory');
  }

  await browser.close();
  const files = fs.readdirSync(DIR).filter(f => f.endsWith('.png')).sort();
  console.log(`\n📋 ${files.length} screenshots captured:`);
  files.forEach(f => console.log(`  ✅ ${f}`));
})();
