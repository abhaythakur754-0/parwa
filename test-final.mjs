import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const BACKEND = 'http://127.0.0.1:8000';
const DIR = '/home/z/my-project/download/journey-test';

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-gpu'] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

// Register on backend and get tokens
console.log('Registering on backend...');
const regRes = await fetch(`${BACKEND}/api/v1/auth/register`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: `final${Date.now()}@parwa.com`, password: 'TestPassword123!', name: 'Final Test' }),
});
const regData = await regRes.json();
const accessToken = regData.access_token;
const refreshToken = regData.refresh_token;
console.log('Got token:', accessToken ? 'YES' : 'NO');

// Step 1: Landing page (public)
console.log('Landing page...');
await page.goto(BASE, { timeout: 30000 });
await sleep(2000);
await page.screenshot({ path: `${DIR}/final-00-landing.png` });

// Step 2: Models page (public) — select industry + variant
console.log('Models page...');
await page.goto(`${BASE}/models`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/final-01-models.png` });

// Select industry
const indBtn = page.locator('button:has-text("SaaS")').first();
if (await indBtn.count() > 0) { await indBtn.click(); await sleep(2000); }
await page.screenshot({ path: `${DIR}/final-02-models-saas.png` });

// Try Hire Agent (may show as "Get Started" if not auth'd)
const hireBtn = page.locator('button:has-text("Hire Agent")').first();
const gsBtn = page.locator('button:has-text("Get Started")').first();
console.log('Hire Agent visible:', await hireBtn.count() > 0);
console.log('Get Started visible:', await gsBtn.count() > 0);

// Step 3: Onboarding step 1 (public)
console.log('Onboarding step 1...');
await page.goto(`${BASE}/onboarding`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/final-03-onboarding-start.png` });

// Select SaaS + PARWA
const saasBtn = page.locator('button:has-text("SaaS")').first();
if (await saasBtn.count() > 0) { await saasBtn.click(); await sleep(500); }
const parwaBtn = page.locator('button:has-text("PARWA")').first();
if (await parwaBtn.count() > 0) { await parwaBtn.click(); await sleep(500); }
await page.screenshot({ path: `${DIR}/final-04-step1-selected.png` });
console.log('✅ Industry + Variant selected');

// Continue to step 2
const step1Cont = page.locator('button:has-text("Continue")').last();
if (await step1Cont.count() > 0) { await step1Cont.click(); await sleep(4000); }
await page.screenshot({ path: `${DIR}/final-05-step2-legal.png` });
console.log('✅ Step 2 Legal');

// Accept legal checkboxes
const checkboxes = page.locator('button[role="checkbox"], input[type="checkbox"]');
for (let i = 0; i < await checkboxes.count(); i++) {
  try { await checkboxes.nth(i).click({ timeout: 1000 }); } catch {}
}
await sleep(500);
const acceptBtn = page.locator('button:has-text("Accept"), button:has-text("Agree"), button:has-text("Continue")').last();
if (await acceptBtn.count() > 0) { await acceptBtn.click(); await sleep(4000); }
await page.screenshot({ path: `${DIR}/final-06-step3-integrations.png` });
console.log('✅ Step 3 Integrations (Phase 13)');

// Phase 13: Check if API Key Management section is visible
const keyMgmt = await page.locator('text=Key Management').count();
console.log('Phase 13 - Key Management section present:', keyMgmt > 0);

// Continue through remaining steps
const s3Cont = page.locator('button:has-text("Continue")').last();
if (await s3Cont.count() > 0) { await s3Cont.click(); await sleep(4000); }
await page.screenshot({ path: `${DIR}/final-07-step4-knowledge.png` });

const s4Cont = page.locator('button:has-text("Continue")').last();
if (await s4Cont.count() > 0) { await s4Cont.click(); await sleep(4000); }
await page.screenshot({ path: `${DIR}/final-08-step5-aiconfig.png` });

const s5Cont = page.locator('button:has-text("Continue")').last();
if (await s5Cont.count() > 0) { await s5Cont.click(); await sleep(4000); }
await page.screenshot({ path: `${DIR}/final-09-step6-cost.png` });

const s6Cont = page.locator('button:has-text("Continue"), button:has-text("Activate"), button:has-text("Launch")').last();
if (await s6Cont.count() > 0) { await s6Cont.click(); await sleep(6000); }
await page.screenshot({ path: `${DIR}/final-10-victory.png` });
console.log('✅ First Victory');

// Now set auth cookies for dashboard access
await ctx.addCookies([
  { name: 'parwa_at', value: accessToken, domain: '127.0.0.1', path: '/', httpOnly: true, sameSite: 'Lax' },
  { name: 'parwa_rt', value: refreshToken, domain: '127.0.0.1', path: '/', httpOnly: true, sameSite: 'Lax' },
  { name: 'parwa_user', value: JSON.stringify({ id: regData.user?.id, email: regData.user?.email, fullName: regData.user?.name }), domain: '127.0.0.1', path: '/', sameSite: 'Lax' },
]);

// Dashboard - Phase 14: AI Tools
console.log('Dashboard AI Tools (Phase 14)...');
await page.goto(`${BASE}/dashboard/ai-tools`, { timeout: 30000 });
await sleep(4000);
const aiUrl = page.url();
console.log('AI Tools URL:', aiUrl);
await page.screenshot({ path: `${DIR}/final-11-ai-tools.png` });

// Dashboard - Phase 14: Variants
console.log('Dashboard Variants (Phase 14)...');
await page.goto(`${BASE}/dashboard/variants`, { timeout: 30000 });
await sleep(4000);
const varUrl = page.url();
console.log('Variants URL:', varUrl);
await page.screenshot({ path: `${DIR}/final-12-variants.png` });

// Dashboard main
await page.goto(`${BASE}/dashboard`, { timeout: 30000 });
await sleep(4000);
const dashUrl = page.url();
console.log('Dashboard URL:', dashUrl);
await page.screenshot({ path: `${DIR}/final-13-dashboard.png` });

// Phase 13: Models page with Hire Agent (now authenticated)
console.log('Models page with auth...');
await page.goto(`${BASE}/models`, { timeout: 30000 });
await sleep(3000);
// Select industry again
const indBtn2 = page.locator('button:has-text("SaaS")').first();
if (await indBtn2.count() > 0) { await indBtn2.click(); await sleep(1500); }
await page.screenshot({ path: `${DIR}/final-14-models-auth.png` });
const hireBtn2 = page.locator('button:has-text("Hire Agent")').first();
console.log('Hire Agent visible (auth):', await hireBtn2.count() > 0);

if (await hireBtn2.count() > 0) {
  await hireBtn2.click();
  await sleep(2000);
  await page.screenshot({ path: `${DIR}/final-15-confirm-modal.png` });
  console.log('✅ Confirm modal captured!');
  
  const contBtn = page.locator('button:has-text("Continue")').first();
  if (await contBtn.count() > 0) { await contBtn.click(); await sleep(5000); }
  await page.screenshot({ path: `${DIR}/final-16-onboarding-from-modal.png` });
}

console.log('\n═══ FULL JOURNEY COMPLETE ═══');
await browser.close();
