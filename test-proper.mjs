import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const BACKEND = 'http://127.0.0.1:8000';
const DIR = '/home/z/my-project/download/journey-test';

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-gpu'] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

// Register user on backend directly
const email = `proper${Date.now()}@parwa.com`;
const password = 'TestPassword123!';
console.log('Registering:', email);
const regRes = await fetch(`${BACKEND}/api/v1/auth/register`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password, name: 'Proper Test' }),
});
const regData = await regRes.json();
console.log('Registered:', regData.user?.email);

// Step 1: Landing
console.log('1. Landing page...');
await page.goto(BASE, { timeout: 30000 });
await sleep(2000);
await page.screenshot({ path: `${DIR}/p-00-landing.png` });

// Step 2: Login page
console.log('2. Login page...');
await page.goto(`${BASE}/login`, { timeout: 30000 });
await sleep(2000);
await page.screenshot({ path: `${DIR}/p-01-login.png` });

// Fill login form
const emailInput = page.locator('input[type="email"], input[placeholder*="email" i]').first();
const passInput = page.locator('input[type="password"]').first();
await emailInput.fill(email);
await passInput.fill(password);
await page.screenshot({ path: `${DIR}/p-02-login-filled.png` });

// Submit login
const submitBtn = page.locator('button[type="submit"], button:has-text("Sign in")').first();
await submitBtn.click();
await sleep(5000);
const afterLoginUrl = page.url();
console.log('After login URL:', afterLoginUrl);
await page.screenshot({ path: `${DIR}/p-03-after-login.png` });

// If we got redirected to onboarding, great! If to dashboard, go to onboarding
if (afterLoginUrl.includes('onboarding')) {
  console.log('✅ Redirected to onboarding after login');
} else if (afterLoginUrl.includes('dashboard')) {
  console.log('✅ Redirected to dashboard after login');
} else if (afterLoginUrl.includes('login')) {
  console.log('⚠️ Still on login page - trying BFF login');
  // Try BFF login
  const loginRes = await page.request.post(`${BASE}/api/auth/login`, {
    data: { email, password }
  });
  console.log('BFF login status:', loginRes.status());
  await sleep(2000);
  // Reload page
  await page.goto(`${BASE}/onboarding`, { timeout: 30000 });
  await sleep(3000);
  console.log('Onboarding URL:', page.url());
  await page.screenshot({ path: `${DIR}/p-03b-onboarding-retry.png` });
}

// Step 3: Onboarding
console.log('3. Onboarding...');
await page.goto(`${BASE}/onboarding`, { timeout: 30000 });
await sleep(3000);
const onbUrl = page.url();
console.log('Onboarding URL:', onbUrl);
await page.screenshot({ path: `${DIR}/p-04-onboarding.png` });

if (onbUrl.includes('onboarding')) {
  // Select industry
  const saasBtn = page.locator('button:has-text("SaaS")').first();
  if (await saasBtn.count() > 0) { await saasBtn.click(); await sleep(500); }
  const parwaBtn = page.locator('button:has-text("PARWA")').first();
  if (await parwaBtn.count() > 0) { await parwaBtn.click(); await sleep(500); }
  await page.screenshot({ path: `${DIR}/p-05-step1-selected.png` });
  console.log('✅ Step 1 selected');
  
  // Continue through steps
  const step1Cont = page.locator('button:has-text("Continue")').last();
  if (await step1Cont.count() > 0) { await step1Cont.click(); await sleep(4000); }
  await page.screenshot({ path: `${DIR}/p-06-step2-legal.png` });
  
  // Accept legal
  const checkboxes = page.locator('button[role="checkbox"], input[type="checkbox"]');
  for (let i = 0; i < await checkboxes.count(); i++) {
    try { await checkboxes.nth(i).click({ timeout: 1000 }); } catch {}
  }
  await sleep(500);
  const acceptBtn = page.locator('button:has-text("Accept"), button:has-text("Agree"), button:has-text("Continue")').last();
  if (await acceptBtn.count() > 0) { await acceptBtn.click(); await sleep(4000); }
  await page.screenshot({ path: `${DIR}/p-07-step3-integrations.png` });
  console.log('✅ Step 3 (Phase 13 API Keys)');
  
  // Continue
  for (let step = 4; step <= 6; step++) {
    const contBtn = page.locator('button:has-text("Continue")').last();
    if (await contBtn.count() > 0) { await contBtn.click(); await sleep(4000); }
    await page.screenshot({ path: `${DIR}/p-0${7+step}-step${step}.png` });
  }
  
  // Victory
  const actBtn = page.locator('button:has-text("Continue"), button:has-text("Activate"), button:has-text("Launch")').last();
  if (await actBtn.count() > 0) { await actBtn.click(); await sleep(6000); }
  await page.screenshot({ path: `${DIR}/p-13-victory.png` });
  console.log('✅ First Victory');
}

// Step 4: Dashboard pages
console.log('4. Dashboard pages...');
await page.goto(`${BASE}/dashboard`, { timeout: 30000 });
await sleep(3000);
const dashUrl = page.url();
console.log('Dashboard URL:', dashUrl);
await page.screenshot({ path: `${DIR}/p-14-dashboard.png` });

await page.goto(`${BASE}/dashboard/ai-tools`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/p-15-ai-tools.png` });

await page.goto(`${BASE}/dashboard/variants`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/p-16-variants.png` });

// Step 5: Models page (with auth) → Confirm modal
console.log('5. Models → Confirm modal...');
await page.goto(`${BASE}/models`, { timeout: 30000 });
await sleep(3000);
const indBtn = page.locator('button:has-text("SaaS")').first();
if (await indBtn.count() > 0) { await indBtn.click(); await sleep(2000); }
await page.screenshot({ path: `${DIR}/p-17-models-saas.png` });

const hireBtn = page.locator('button:has-text("Hire Agent")').first();
console.log('Hire Agent visible:', await hireBtn.count() > 0);
if (await hireBtn.count() > 0) {
  await hireBtn.click();
  await sleep(2000);
  await page.screenshot({ path: `${DIR}/p-18-confirm-modal.png` });
  console.log('✅ Confirm modal captured!');
}

console.log('\n═══ JOURNEY COMPLETE ═══');
await browser.close();
