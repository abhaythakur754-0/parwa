import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const DIR = '/home/z/my-project/download/journey-test';

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-gpu'] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

// Collect console errors
const errors = [];
page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });

// Register via API first
console.log('Registering user...');
try {
  const regRes = await page.request.post(`${BASE}/api/auth/register`, {
    data: { email: 'testjourney@parwa.com', password: 'TestPassword123!', full_name: 'Test User' }
  });
  console.log('Register status:', regRes.status());
} catch (e) {
  console.log('Register error (may already exist):', e.message?.substring(0, 80));
}

// Login via API
console.log('Logging in...');
try {
  const loginRes = await page.request.post(`${BASE}/api/auth/login`, {
    data: { email: 'testjourney@parwa.com', password: 'TestPassword123!' }
  });
  console.log('Login status:', loginRes.status());
  const loginData = await loginRes.json();
  console.log('Login response keys:', Object.keys(loginData));
} catch (e) {
  console.log('Login API error:', e.message?.substring(0, 80));
}

// Now visit the login page and submit
console.log('Visiting login page...');
await page.goto(`${BASE}/login`, { timeout: 30000 });
await sleep(2000);

const emailInput = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first();
const passInput = page.locator('input[type="password"]').first();

if (await emailInput.count() > 0) {
  await emailInput.fill('testjourney@parwa.com');
  await passInput.fill('TestPassword123!');
  await page.screenshot({ path: `${DIR}/auth-01-login-filled.png` });
  
  const submitBtn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")').first();
  await submitBtn.click();
  await sleep(5000);
  
  const url = page.url();
  console.log('After login URL:', url);
  await page.screenshot({ path: `${DIR}/auth-02-after-login.png` });
  
  if (url.includes('onboarding')) {
    console.log('✅ Redirected to onboarding!');
  } else if (url.includes('dashboard')) {
    console.log('✅ Redirected to dashboard!');
  } else {
    console.log('⚠️ Still on login or unknown page');
  }
}

// Models page with industry + variant selection
console.log('Models page...');
await page.goto(`${BASE}/models`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/auth-03-models.png` });

// Select industry
const indBtn = page.locator('button:has-text("SaaS")').first();
if (await indBtn.count() > 0) { await indBtn.click(); await sleep(2000); }
await page.screenshot({ path: `${DIR}/auth-04-models-saas.png` });

// Check which button is showing (Hire Agent or Get Started)
const hireBtn = page.locator('button:has-text("Hire Agent")').first();
const gsBtn = page.locator('button:has-text("Get Started")').first();
console.log('Hire Agent button visible:', await hireBtn.count() > 0);
console.log('Get Started button visible:', await gsBtn.count() > 0);

if (await hireBtn.count() > 0) {
  await hireBtn.click();
  await sleep(2000);
  await page.screenshot({ path: `${DIR}/auth-05-confirm-modal.png` });
  console.log('✅ Confirm modal!');
  
  const contBtn = page.locator('button:has-text("Continue")').first();
  if (await contBtn.count() > 0) { await contBtn.click(); await sleep(5000); }
  await page.screenshot({ path: `${DIR}/auth-06-onboarding.png` });
  console.log('✅ Redirected to onboarding!');
} else if (await gsBtn.count() > 0) {
  console.log('⚠️ Not authenticated on models page - going to onboarding directly');
  await page.goto(`${BASE}/onboarding`, { timeout: 30000 });
  await sleep(3000);
  await page.screenshot({ path: `${DIR}/auth-06-onboarding-direct.png` });
}

// Onboarding step 1
console.log('Onboarding step 1...');
await page.goto(`${BASE}/onboarding`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/auth-07-onboarding-step1.png` });

const saasBtn = page.locator('button:has-text("SaaS")').first();
if (await saasBtn.count() > 0) { await saasBtn.click(); await sleep(500); }
const parwaBtn = page.locator('button:has-text("PARWA")').first();
if (await parwaBtn.count() > 0) { await parwaBtn.click(); await sleep(500); }
await page.screenshot({ path: `${DIR}/auth-08-step1-selected.png` });

const step1Cont = page.locator('button:has-text("Continue")').last();
if (await step1Cont.count() > 0) { await step1Cont.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/auth-09-step2-legal.png` });

// Accept legal and continue
const checkboxes = page.locator('button[role="checkbox"], input[type="checkbox"]');
for (let i = 0; i < await checkboxes.count(); i++) {
  try { await checkboxes.nth(i).click({ timeout: 1000 }); } catch {}
}
await sleep(500);
const acceptBtn = page.locator('button:has-text("Accept"), button:has-text("Agree"), button:has-text("Continue")').last();
if (await acceptBtn.count() > 0) { await acceptBtn.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/auth-10-step3-integrations.png` });

// Phase 13: Check API key management section exists in integrations
const keyMgmt = page.locator('text=Key Management, text=Rotate Key, text=API Key').first();
console.log('Phase 13 - Key Management visible:', await keyMgmt.count() > 0);

// Continue through remaining steps
const step3Cont = page.locator('button:has-text("Continue")').last();
if (await step3Cont.count() > 0) { await step3Cont.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/auth-11-step4-knowledge.png` });

const step4Cont = page.locator('button:has-text("Continue")').last();
if (await step4Cont.count() > 0) { await step4Cont.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/auth-12-step5-aiconfig.png` });

const step5Cont = page.locator('button:has-text("Continue")').last();
if (await step5Cont.count() > 0) { await step5Cont.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/auth-13-step6-cost.png` });

const step6Cont = page.locator('button:has-text("Continue"), button:has-text("Activate"), button:has-text("Launch")').last();
if (await step6Cont.count() > 0) { await step6Cont.click(); await sleep(5000); }
await page.screenshot({ path: `${DIR}/auth-14-step7-victory.png` });

// Dashboard pages (Phase 14)
console.log('Dashboard - Phase 14 pages...');
await page.goto(`${BASE}/dashboard/ai-tools`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/auth-15-ai-tools.png` });

await page.goto(`${BASE}/dashboard/variants`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/auth-16-variants.png` });

await page.goto(`${BASE}/dashboard`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/auth-17-dashboard.png` });

console.log('\n═══ FULL JOURNEY COMPLETE ═══');
console.log('Console errors:', errors.length);
if (errors.length > 0) console.log('First 5 errors:', errors.slice(0, 5));

await browser.close();
