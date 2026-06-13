import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const BACKEND = 'http://127.0.0.1:8000';
const DIR = '/home/z/my-project/download/journey-test';

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-gpu'] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

// Step 0: Register + get tokens from backend
console.log('Registering on backend...');
const regRes = await fetch(`${BACKEND}/api/v1/auth/register`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: `journey${Date.now()}@parwa.com`, password: 'TestPassword123!', name: 'Journey Test' }),
});
const regData = await regRes.json();
console.log('Register status:', regRes.status || 'ok');
const accessToken = regData.access_token;
const refreshToken = regData.refresh_token;
const userId = regData.user?.id;
console.log('Got access token:', accessToken ? 'YES' : 'NO');

// Set auth cookies on the frontend domain
await ctx.addCookies([
  {
    name: 'parwa_at',
    value: accessToken,
    domain: '127.0.0.1',
    path: '/',
    httpOnly: true,
    sameSite: 'Lax',
  },
  {
    name: 'parwa_rt',
    value: refreshToken,
    domain: '127.0.0.1',
    path: '/',
    httpOnly: true,
    sameSite: 'Lax',
  },
  {
    name: 'parwa_user',
    value: JSON.stringify({ id: userId, email: regData.user?.email, fullName: regData.user?.name }),
    domain: '127.0.0.1',
    path: '/',
    sameSite: 'Lax',
  },
]);

// Step 1: Landing page
console.log('Landing page...');
await page.goto(BASE, { timeout: 30000 });
await sleep(2000);
await page.screenshot({ path: `${DIR}/final-00-landing.png` });
console.log('✅ Landing');

// Step 2: Models page (authenticated)
console.log('Models page...');
await page.goto(`${BASE}/models`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/final-01-models.png` });

// Select industry
const indBtn = page.locator('button:has-text("SaaS")').first();
if (await indBtn.count() > 0) { await indBtn.click(); await sleep(2000); }
await page.screenshot({ path: `${DIR}/final-02-models-saas.png` });
console.log('✅ SaaS selected');

// Click Hire Agent
const hireBtn = page.locator('button:has-text("Hire Agent")').first();
console.log('Hire Agent button:', await hireBtn.count() > 0);
if (await hireBtn.count() > 0) {
  await hireBtn.click();
  await sleep(2000);
  await page.screenshot({ path: `${DIR}/final-03-confirm-modal.png` });
  console.log('✅ Confirm modal captured!');
  
  // Click Continue
  const contBtn = page.locator('button:has-text("Continue")').first();
  if (await contBtn.count() > 0) { await contBtn.click(); await sleep(5000); }
  await page.screenshot({ path: `${DIR}/final-04-onboarding.png` });
  console.log('✅ Onboarding from modal');
}

// Step 3: Onboarding Step 1
console.log('Onboarding step 1...');
await page.goto(`${BASE}/onboarding`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/final-05-onboarding-step1.png` });

// Select SaaS + PARWA
const saasBtn = page.locator('button:has-text("SaaS")').first();
if (await saasBtn.count() > 0) { await saasBtn.click(); await sleep(500); }
const parwaBtn = page.locator('button:has-text("PARWA")').first();
if (await parwaBtn.count() > 0) { await parwaBtn.click(); await sleep(500); }
await page.screenshot({ path: `${DIR}/final-06-step1-selected.png` });
console.log('✅ Industry + Variant selected');

// Continue to step 2
const step1Cont = page.locator('button:has-text("Continue")').last();
if (await step1Cont.count() > 0) { await step1Cont.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/final-07-step2-legal.png` });
console.log('✅ Step 2 Legal');

// Accept legal checkboxes and continue
const checkboxes = page.locator('button[role="checkbox"], input[type="checkbox"]');
for (let i = 0; i < await checkboxes.count(); i++) {
  try { await checkboxes.nth(i).click({ timeout: 1000 }); } catch {}
}
await sleep(500);
const acceptBtn = page.locator('button:has-text("Accept"), button:has-text("Agree"), button:has-text("Continue")').last();
if (await acceptBtn.count() > 0) { await acceptBtn.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/final-08-step3-integrations.png` });
console.log('✅ Step 3 Integrations (Phase 13 API Keys)');

// Continue step 3 → 4
const s3Cont = page.locator('button:has-text("Continue")').last();
if (await s3Cont.count() > 0) { await s3Cont.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/final-09-step4-knowledge.png` });

// Continue step 4 → 5
const s4Cont = page.locator('button:has-text("Continue")').last();
if (await s4Cont.count() > 0) { await s4Cont.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/final-10-step5-aiconfig.png` });

// Continue step 5 → 6
const s5Cont = page.locator('button:has-text("Continue")').last();
if (await s5Cont.count() > 0) { await s5Cont.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/final-11-step6-cost.png` });

// Step 6 → 7 (activate)
const s6Cont = page.locator('button:has-text("Continue"), button:has-text("Activate"), button:has-text("Launch")').last();
if (await s6Cont.count() > 0) { await s6Cont.click(); await sleep(5000); }
await page.screenshot({ path: `${DIR}/final-12-step7-victory.png` });
console.log('✅ First Victory');

// Dashboard - Phase 14: AI Tools
console.log('Dashboard AI Tools (Phase 14)...');
await page.goto(`${BASE}/dashboard/ai-tools`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/final-13-ai-tools.png` });
console.log('✅ AI Tools dashboard');

// Dashboard - Phase 14: Variants
console.log('Dashboard Variants (Phase 14)...');
await page.goto(`${BASE}/dashboard/variants`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/final-14-variants.png` });
console.log('✅ Variants dashboard');

// Dashboard main
await page.goto(`${BASE}/dashboard`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/final-15-dashboard.png` });

console.log('\n═══ FULL JOURNEY COMPLETE ═══');
await browser.close();
