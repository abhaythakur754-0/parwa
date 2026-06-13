import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const DIR = '/home/z/my-project/download/journey-test';

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-gpu'] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

try {
  console.log('Landing...');
  await page.goto(BASE, { timeout: 30000 });
  await sleep(3000);
  await page.screenshot({ path: `${DIR}/00-landing.png` });
  console.log('✅ Landing');

  console.log('Login...');
  await page.goto(`${BASE}/login`, { timeout: 30000 });
  await sleep(3000);
  await page.screenshot({ path: `${DIR}/01-login-page.png` });
  console.log('✅ Login page');

  // Fill login
  const email = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first();
  const pass = page.locator('input[type="password"]').first();
  if (await email.count() > 0) {
    await email.fill('test@parwa.com');
    await pass.fill('TestPassword123!');
    await page.screenshot({ path: `${DIR}/02-login-filled.png` });
    const btn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")').first();
    if (await btn.count() > 0) { await btn.click(); await sleep(4000); }
    await page.screenshot({ path: `${DIR}/03-after-login.png` });
    console.log('✅ Login submitted');
  }

  // Models page
  console.log('Models...');
  await page.goto(`${BASE}/models`, { timeout: 30000 });
  await sleep(3000);
  await page.screenshot({ path: `${DIR}/04-models-page.png` });

  // Select industry
  const indBtn = page.locator('button:has-text("SaaS")').first();
  if (await indBtn.count() > 0) { await indBtn.click(); await sleep(1500); }
  await page.screenshot({ path: `${DIR}/05-industry-selected.png` });
  console.log('✅ Industry selected');

  // Click Hire Agent
  const hire = page.locator('button:has-text("Hire Agent")').first();
  if (await hire.count() > 0) {
    await hire.click(); await sleep(1500);
    await page.screenshot({ path: `${DIR}/06-confirm-modal.png` });
    console.log('✅ Confirm modal');
    const cont = page.locator('button:has-text("Continue")').first();
    if (await cont.count() > 0) { await cont.click(); await sleep(4000); }
    await page.screenshot({ path: `${DIR}/07-onboarding.png` });
  } else {
    await page.goto(`${BASE}/onboarding`, { timeout: 30000 });
    await sleep(3000);
    await page.screenshot({ path: `${DIR}/07-onboarding-direct.png` });
  }
  console.log('✅ Onboarding');

  // Onboarding step 1
  await page.goto(`${BASE}/onboarding`, { timeout: 30000 });
  await sleep(3000);
  await page.screenshot({ path: `${DIR}/08-onboarding-step1.png` });
  const sBtn = page.locator('button:has-text("SaaS")').first();
  if (await sBtn.count() > 0) { await sBtn.click(); await sleep(500); }
  const pBtn = page.locator('button:has-text("PARWA")').first();
  if (await pBtn.count() > 0) { await pBtn.click(); await sleep(500); }
  await page.screenshot({ path: `${DIR}/09-step1-selections.png` });
  const cBtn = page.locator('button:has-text("Continue")').last();
  if (await cBtn.count() > 0) { await cBtn.click(); await sleep(3000); }
  await page.screenshot({ path: `${DIR}/10-step2-legal.png` });
  console.log('✅ Step 1 → Step 2');

  // Dashboard AI Tools
  await page.goto(`${BASE}/dashboard/ai-tools`, { timeout: 30000 });
  await sleep(3000);
  await page.screenshot({ path: `${DIR}/11-dashboard-ai-tools.png` });
  console.log('✅ AI Tools');

  // Dashboard Variants
  await page.goto(`${BASE}/dashboard/variants`, { timeout: 30000 });
  await sleep(3000);
  await page.screenshot({ path: `${DIR}/12-dashboard-variants.png` });
  console.log('✅ Variants');

  // Dashboard main
  await page.goto(`${BASE}/dashboard`, { timeout: 30000 });
  await sleep(3000);
  await page.screenshot({ path: `${DIR}/13-dashboard-main.png` });
  console.log('✅ Dashboard');

  console.log('\n═══ ALL DONE ═══');
} catch (e) {
  console.error('ERROR:', e.message);
} finally {
  await browser.close();
}
