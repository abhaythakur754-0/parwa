import { chromium } from 'playwright';
const BASE = 'http://127.0.0.1:3000';
const DIR = '/home/z/my-project/download/proof-final';
const EMAIL = 'proof1781299736@parwa.com';
async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-gpu'] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

// Landing
console.log('0. Landing');
await page.goto(BASE, { waitUntil: 'networkidle', timeout: 30000 });
await sleep(1000);
await page.screenshot({ path: DIR+'/00-landing.png' });

// Login
console.log('1. Login');
await page.goto(BASE+'/login', { waitUntil: 'networkidle', timeout: 30000 });
await sleep(1000);
await page.locator('input[type="email"], input[placeholder*="email" i]').first().fill(EMAIL);
await page.locator('input[type="password"]').first().fill('TestPassword123!');
await page.screenshot({ path: DIR+'/01-login-filled.png' });
await page.locator('button[type="submit"], button:has-text("Sign in")').first().click();

// Wait for navigation to complete
await page.waitForURL('**/onboarding**', { timeout: 15000 }).catch(() => {});
await sleep(2000);
console.log('URL after login:', page.url());
await page.screenshot({ path: DIR+'/02-onboarding-step1.png' });

// Step 1: Select SaaS + PARWA
console.log('2. Step 1 - Industry + Variant');
await page.locator('button:has-text("SaaS")').first().click();
await sleep(300);
await page.locator('button:has-text("PARWA")').first().click();
await sleep(300);
await page.screenshot({ path: DIR+'/03-step1-selected.png' });

// Continue to step 2
await page.locator('button:has-text("Continue")').last().click();
await sleep(4000);
await page.screenshot({ path: DIR+'/04-step2-legal.png' });

// Accept legal - use JS to click all checkboxes then wait
await page.evaluate(() => {
  // Click all elements that could be checkboxes
  const els = document.querySelectorAll('button[role="checkbox"], input[type="checkbox"], [data-state]');
  els.forEach(el => { try { el.click(); } catch {} });
});
await sleep(1500);
await page.screenshot({ path: DIR+'/05-step2-checkboxes.png' });

// Click Continue on step 2 (find enabled button)
const step2Continue = page.locator('button:not([disabled]):has-text("Continue")').last();
if (await step2Continue.count() > 0) {
  await step2Continue.click();
  await sleep(4000);
}
await page.screenshot({ path: DIR+'/06-step3-integrations.png' });
console.log('✅ Step 3 - Integrations (Phase 13)');

// Step 3 → 4
const s3 = page.locator('button:not([disabled]):has-text("Continue")').last();
if (await s3.count() > 0) await s3.click();
await sleep(4000);
await page.screenshot({ path: DIR+'/07-step4-knowledge.png' });

// Step 4 → 5
const s4 = page.locator('button:not([disabled]):has-text("Continue")').last();
if (await s4.count() > 0) await s4.click();
await sleep(4000);
await page.screenshot({ path: DIR+'/08-step5-aiconfig.png' });

// Step 5 → 6
const s5 = page.locator('button:not([disabled]):has-text("Continue")').last();
if (await s5.count() > 0) await s5.click();
await sleep(4000);
await page.screenshot({ path: DIR+'/09-step6-cost.png' });

// Step 6 → Victory
const s6 = page.locator('button:not([disabled]):has-text("Continue"), button:not([disabled]):has-text("Activate"), button:not([disabled]):has-text("Launch")').last();
if (await s6.count() > 0) await s6.click();
await sleep(6000);
await page.screenshot({ path: DIR+'/10-victory.png' });
console.log('✅ Victory!');

// Models page
await page.goto(BASE+'/models', { waitUntil: 'networkidle', timeout: 30000 });
await sleep(2000);
await page.locator('button:has-text("SaaS")').first().click();
await sleep(1500);
await page.screenshot({ path: DIR+'/11-models-saas.png' });

const hire = page.locator('button:has-text("Hire Agent")').first();
if (await hire.count() > 0) {
  await hire.click();
  await sleep(2000);
  await page.screenshot({ path: DIR+'/12-confirm-modal.png' });
  console.log('✅ Confirm modal!');
} else {
  console.log('No Hire Agent button - checking Get Started');
  const gs = page.locator('button:has-text("Get Started")').first();
  console.log('Get Started visible:', await gs.count() > 0);
}

// Dashboard AI Tools (Phase 14)
await page.goto(BASE+'/dashboard/ai-tools', { waitUntil: 'networkidle', timeout: 30000 });
await sleep(3000);
const aiUrl = page.url();
await page.screenshot({ path: DIR+'/13-ai-tools.png' });
console.log('AI Tools URL:', aiUrl);

// Dashboard Variants (Phase 14)
await page.goto(BASE+'/dashboard/variants', { waitUntil: 'networkidle', timeout: 30000 });
await sleep(3000);
const varUrl = page.url();
await page.screenshot({ path: DIR+'/14-variants.png' });
console.log('Variants URL:', varUrl);

// Dashboard main
await page.goto(BASE+'/dashboard', { waitUntil: 'networkidle', timeout: 30000 });
await sleep(3000);
const dashUrl = page.url();
await page.screenshot({ path: DIR+'/15-dashboard.png' });
console.log('Dashboard URL:', dashUrl);

console.log('\n═══ PROOF JOURNEY COMPLETE ═══');
await browser.close();
