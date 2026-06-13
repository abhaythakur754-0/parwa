import { chromium } from 'playwright';

const BASE = 'http://localhost:3000';
const DIR = '/home/z/my-project/download/journey-test';

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function run() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  // Step 0: Landing
  console.log('Step 0: Landing...');
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 30000 });
  await sleep(2000);
  await page.screenshot({ path: `${DIR}/00-landing.png` });

  // Step 1: Login
  console.log('Step 1: Login page...');
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 30000 });
  await sleep(2000);
  await page.screenshot({ path: `${DIR}/01-login-page.png` });

  // Step 2: Fill login
  console.log('Step 2: Fill login...');
  const email = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first();
  const pass = page.locator('input[type="password"]').first();
  if (await email.count() > 0) {
    await email.fill('test@parwa.com');
    await pass.fill('TestPassword123!');
    await page.screenshot({ path: `${DIR}/02-login-filled.png` });
    const btn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")').first();
    if (await btn.count() > 0) { await btn.click(); await sleep(4000); }
    await page.screenshot({ path: `${DIR}/03-after-login.png` });
  }

  // Step 3: Models
  console.log('Step 3: Models page...');
  await page.goto(`${BASE}/models`, { waitUntil: 'networkidle', timeout: 30000 });
  await sleep(2000);
  await page.screenshot({ path: `${DIR}/04-models-page.png` });

  // Step 4: Select industry
  console.log('Step 4: Select industry...');
  const indBtn = page.locator('button:has-text("SaaS")').first();
  if (await indBtn.count() > 0) { await indBtn.click(); await sleep(1500); }
  await page.screenshot({ path: `${DIR}/05-industry-selected.png` });

  // Step 5: Click Hire Agent
  console.log('Step 5: Click Hire Agent...');
  const hire = page.locator('button:has-text("Hire Agent")').first();
  if (await hire.count() > 0) {
    await hire.click(); await sleep(1500);
    await page.screenshot({ path: `${DIR}/06-confirm-modal.png` });
    const cont = page.locator('button:has-text("Continue")').first();
    if (await cont.count() > 0) { await cont.click(); await sleep(4000); }
    await page.screenshot({ path: `${DIR}/07-onboarding.png` });
  } else {
    await page.goto(`${BASE}/onboarding`, { waitUntil: 'networkidle', timeout: 30000 });
    await sleep(2000);
    await page.screenshot({ path: `${DIR}/07-onboarding-direct.png` });
  }

  // Step 6: Onboarding Step 1
  console.log('Step 6: Onboarding Step 1...');
  await page.goto(`${BASE}/onboarding`, { waitUntil: 'networkidle', timeout: 30000 });
  await sleep(2000);
  await page.screenshot({ path: `${DIR}/08-onboarding-step1.png` });
  const sBtn = page.locator('button:has-text("SaaS")').first();
  if (await sBtn.count() > 0) { await sBtn.click(); await sleep(500); }
  const pBtn = page.locator('button:has-text("PARWA")').first();
  if (await pBtn.count() > 0) { await pBtn.click(); await sleep(500); }
  await page.screenshot({ path: `${DIR}/09-step1-selections.png` });

  // Click Continue
  const cBtn = page.locator('button:has-text("Continue")').last();
  if (await cBtn.count() > 0) { await cBtn.click(); await sleep(3000); }
  await page.screenshot({ path: `${DIR}/10-step2-legal.png` });

  // Step 7: Dashboard AI Tools
  console.log('Step 7: Dashboard AI Tools...');
  await page.goto(`${BASE}/dashboard/ai-tools`, { waitUntil: 'networkidle', timeout: 30000 });
  await sleep(2000);
  await page.screenshot({ path: `${DIR}/11-dashboard-ai-tools.png` });

  // Step 8: Dashboard Variants
  console.log('Step 8: Dashboard Variants...');
  await page.goto(`${BASE}/dashboard/variants`, { waitUntil: 'networkidle', timeout: 30000 });
  await sleep(2000);
  await page.screenshot({ path: `${DIR}/12-dashboard-variants.png` });

  // Step 9: Dashboard main
  console.log('Step 9: Dashboard main...');
  await page.goto(`${BASE}/dashboard`, { waitUntil: 'networkidle', timeout: 30000 });
  await sleep(2000);
  await page.screenshot({ path: `${DIR}/13-dashboard-main.png` });

  console.log('\n═══ ALL STEPS COMPLETE ═══');
  await browser.close();
}

run().catch(err => { console.error('FATAL:', err.message); process.exit(1); });
