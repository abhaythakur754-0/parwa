import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const DIR = '/home/z/my-project/download/journey-test';

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-gpu'] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

// Register first, then login
console.log('Signup...');
await page.goto(`${BASE}/signup`, { timeout: 30000 });
await sleep(3000);
const nameInput = page.locator('input[name="name"], input[placeholder*="name" i], input[placeholder*="Name"]').first();
const emailInput = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first();
const passInput = page.locator('input[type="password"]').first();

if (await emailInput.count() > 0) {
  // Try filling signup form
  if (await nameInput.count() > 0) await nameInput.fill('Test User');
  await emailInput.fill('test+journey@parwa.com');
  if (await passInput.count() > 0) await passInput.fill('TestPassword123!');
  
  // Check for confirm password
  const passInputs = page.locator('input[type="password"]');
  if (await passInputs.count() > 1) {
    await passInputs.nth(1).fill('TestPassword123!');
  }
  
  await page.screenshot({ path: `${DIR}/14-signup-filled.png` });
  
  const signupBtn = page.locator('button[type="submit"], button:has-text("Sign up"), button:has-text("Create")').first();
  if (await signupBtn.count() > 0) {
    await signupBtn.click();
    await sleep(5000);
    await page.screenshot({ path: `${DIR}/15-after-signup.png` });
    console.log('✅ Signup done');
  }
}

// Now go to models
console.log('Models...');
await page.goto(`${BASE}/models`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/16-models-auth.png` });

// Select industry
const indBtn = page.locator('button:has-text("SaaS")').first();
if (await indBtn.count() > 0) { await indBtn.click(); await sleep(1500); }
await page.screenshot({ path: `${DIR}/17-models-saas.png` });

// Click Hire Agent
const hireBtn = page.locator('button:has-text("Hire Agent")').first();
if (await hireBtn.count() > 0) {
  await hireBtn.click();
  await sleep(2000);
  await page.screenshot({ path: `${DIR}/18-confirm-modal.png` });
  console.log('✅ Confirm modal captured!');
  
  // Click Continue in modal
  const contBtn = page.locator('button:has-text("Continue")').first();
  if (await contBtn.count() > 0) {
    await contBtn.click();
    await sleep(5000);
    await page.screenshot({ path: `${DIR}/19-onboarding-from-modal.png` });
    console.log('✅ Onboarding from modal captured!');
  }
} else {
  console.log('⚠️ No Hire Agent button (not authenticated?)');
  // Try the Get Started button
  const gsBtn = page.locator('button:has-text("Get Started")').first();
  if (await gsBtn.count() > 0) {
    console.log('  Found "Get Started" instead of "Hire Agent"');
  }
}

// Full onboarding flow
console.log('Onboarding full flow...');
await page.goto(`${BASE}/onboarding`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/20-onboarding-start.png` });

// Select SaaS industry
const saasBtn = page.locator('button:has-text("SaaS")').first();
if (await saasBtn.count() > 0) { await saasBtn.click(); await sleep(500); }

// Select PARWA variant  
const parwaBtn = page.locator('button:has-text("PARWA")').first();
if (await parwaBtn.count() > 0) { await parwaBtn.click(); await sleep(500); }

await page.screenshot({ path: `${DIR}/21-step1-selected.png` });

// Click Continue
const contBtn = page.locator('button:has-text("Continue")').last();
if (await contBtn.count() > 0) { await contBtn.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/22-step2-legal.png` });

// Phase 13: Integration step (Step 3)
console.log('Checking Step 3 (Integrations + API Keys)...');
// Accept legal by checking checkboxes and continuing
const checkboxes = page.locator('input[type="checkbox"], button[role="checkbox"]');
const cbCount = await checkboxes.count();
for (let i = 0; i < cbCount; i++) {
  try { await checkboxes.nth(i).click({ timeout: 1000 }); } catch {}
}
await sleep(500);
const step2Cont = page.locator('button:has-text("Continue"), button:has-text("Accept"), button:has-text("Agree")').last();
if (await step2Cont.count() > 0) { await step2Cont.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/23-step3-integrations.png` });
console.log('✅ Step 3 (Integrations with Phase 13 API key system)');

// Continue through step 3
const step3Cont = page.locator('button:has-text("Continue")').last();
if (await step3Cont.count() > 0) { await step3Cont.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/24-step4-knowledge.png` });

// Continue through step 4
const step4Cont = page.locator('button:has-text("Continue")').last();
if (await step4Cont.count() > 0) { await step4Cont.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/25-step5-aiconfig.png` });

// Continue through step 5
const step5Cont = page.locator('button:has-text("Continue")').last();
if (await step5Cont.count() > 0) { await step5Cont.click(); await sleep(3000); }
await page.screenshot({ path: `${DIR}/26-step6-cost.png` });

// Dashboard pages
console.log('Dashboard Phase 14 pages...');
await page.goto(`${BASE}/dashboard/ai-tools`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/27-ai-tools-dark.png` });

await page.goto(`${BASE}/dashboard/variants`, { timeout: 30000 });
await sleep(3000);
await page.screenshot({ path: `${DIR}/28-variants-dark.png` });

console.log('\n═══ FULL JOURNEY COMPLETE ═══');
await browser.close();
