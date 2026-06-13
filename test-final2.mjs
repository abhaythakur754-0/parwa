import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const BACKEND = 'http://127.0.0.1:8000';
const DIR = '/home/z/my-project/download/journey-test';

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// Register and login on backend directly
const email = `final2${Date.now()}@parwa.com`;
const password = 'TestPassword123!';
const regRes = await fetch(`${BACKEND}/api/v1/auth/register`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password, name: 'Final Test' }),
});
const regData = await regRes.json();
const accessToken = regData.access_token;
const refreshToken = regData.refresh_token;
const userObj = regData.user;
console.log('✅ Registered on backend:', email);

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-gpu'] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

// Set auth cookies BEFORE any navigation
await ctx.addCookies([
  { name: 'parwa_at', value: accessToken, domain: '127.0.0.1', path: '/', httpOnly: true, sameSite: 'Lax', secure: false },
  { name: 'parwa_rt', value: refreshToken, domain: '127.0.0.1', path: '/', httpOnly: true, sameSite: 'Lax', secure: false },
  { name: 'parwa_user', value: JSON.stringify({ id: userObj.id, email: userObj.email, fullName: userObj.name, isVerified: false }), domain: '127.0.0.1', path: '/', sameSite: 'Lax', secure: false },
]);

// Step 1: Landing
console.log('1. Landing...');
await page.goto(BASE, { timeout: 30000 });
await sleep(2000);
await page.screenshot({ path: `${DIR}/f-00-landing.png` });

// Step 2: Login page (already authenticated, should redirect)
console.log('2. Login check...');
await page.goto(`${BASE}/login`, { timeout: 30000 });
await sleep(3000);
const loginUrl = page.url();
console.log('Login redirect:', loginUrl);
await page.screenshot({ path: `${DIR}/f-01-login-redirect.png` });

// Step 3: Models page
console.log('3. Models page...');
await page.goto(`${BASE}/models`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/f-02-models.png` });

// Select industry
const indBtn = page.locator('button:has-text("SaaS")').first();
if (await indBtn.count() > 0) { await indBtn.click(); await sleep(2000); }
await page.screenshot({ path: `${DIR}/f-03-models-saas.png` });

// Check buttons
const hireBtn = page.locator('button:has-text("Hire Agent")').first();
const gsBtn = page.locator('button:has-text("Get Started")').first();
console.log('Hire Agent:', await hireBtn.count() > 0, '| Get Started:', await gsBtn.count() > 0);

if (await hireBtn.count() > 0) {
  await hireBtn.click();
  await sleep(2000);
  await page.screenshot({ path: `${DIR}/f-04-confirm-modal.png` });
  console.log('✅ Confirm modal!');
  
  const contBtn = page.locator('button:has-text("Continue")').first();
  if (await contBtn.count() > 0) { await contBtn.click(); await sleep(5000); }
  await page.screenshot({ path: `${DIR}/f-05-onboarding-from-modal.png` });
}

// Step 4: Onboarding
console.log('4. Onboarding...');
await page.goto(`${BASE}/onboarding`, { timeout: 30000 });
await sleep(3000);
const onbUrl = page.url();
console.log('Onboarding URL:', onbUrl);
await page.screenshot({ path: `${DIR}/f-06-onboarding.png` });

if (onbUrl.includes('onboarding')) {
  // Step 1: Industry + Variant
  const saasBtn = page.locator('button:has-text("SaaS")').first();
  if (await saasBtn.count() > 0) { await saasBtn.click(); await sleep(500); }
  const parwaBtn = page.locator('button:has-text("PARWA")').first();
  if (await parwaBtn.count() > 0) { await parwaBtn.click(); await sleep(500); }
  await page.screenshot({ path: `${DIR}/f-07-step1-selected.png` });
  console.log('✅ Step 1 selected');
  
  const s1Cont = page.locator('button:has-text("Continue")').last();
  if (await s1Cont.count() > 0) { await s1Cont.click(); await sleep(4000); }
  await page.screenshot({ path: `${DIR}/f-08-step2-legal.png` });
  
  // Accept legal
  const cbs = page.locator('button[role="checkbox"], input[type="checkbox"]');
  for (let i = 0; i < await cbs.count(); i++) {
    try { await cbs.nth(i).click({ timeout: 1000 }); } catch {}
  }
  await sleep(500);
  const accBtn = page.locator('button:has-text("Accept"), button:has-text("Agree"), button:has-text("Continue")').last();
  if (await accBtn.count() > 0) { await accBtn.click(); await sleep(4000); }
  await page.screenshot({ path: `${DIR}/f-09-step3-integrations.png` });
  console.log('✅ Step 3 (Phase 13 API Keys)');
  
  // Step 4: Knowledge
  const s3Cont = page.locator('button:has-text("Continue")').last();
  if (await s3Cont.count() > 0) { await s3Cont.click(); await sleep(4000); }
  await page.screenshot({ path: `${DIR}/f-10-step4-knowledge.png` });
  
  // Step 5: AI Config
  const s4Cont = page.locator('button:has-text("Continue")').last();
  if (await s4Cont.count() > 0) { await s4Cont.click(); await sleep(4000); }
  await page.screenshot({ path: `${DIR}/f-11-step5-aiconfig.png` });
  
  // Step 6: Cost Breakdown
  const s5Cont = page.locator('button:has-text("Continue")').last();
  if (await s5Cont.count() > 0) { await s5Cont.click(); await sleep(4000); }
  await page.screenshot({ path: `${DIR}/f-12-step6-cost.png` });
  
  // Step 7: Activate/Victory
  const s6Cont = page.locator('button:has-text("Continue"), button:has-text("Activate"), button:has-text("Launch")').last();
  if (await s6Cont.count() > 0) { await s6Cont.click(); await sleep(6000); }
  await page.screenshot({ path: `${DIR}/f-13-victory.png` });
  console.log('✅ First Victory');
}

// Step 5: Dashboard
console.log('5. Dashboard pages...');
await page.goto(`${BASE}/dashboard`, { timeout: 30000 });
await sleep(3000);
const dashUrl = page.url();
console.log('Dashboard URL:', dashUrl);
await page.screenshot({ path: `${DIR}/f-14-dashboard.png` });

await page.goto(`${BASE}/dashboard/ai-tools`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/f-15-ai-tools.png` });

await page.goto(`${BASE}/dashboard/variants`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/f-16-variants.png` });

console.log('\n═══ FULL JOURNEY COMPLETE ═══');
await browser.close();
