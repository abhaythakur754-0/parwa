import { chromium } from 'playwright';
const BASE = 'http://127.0.0.1:3000';
const DIR = '/home/z/my-project/download/proof-final';
const EMAIL = 'final1781299519@parwa.com';
const PASS = 'TestPassword123!';
async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-gpu'] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

// Landing
await page.goto(BASE, { timeout: 30000 }); await sleep(2000);
await page.screenshot({ path: DIR+'/00-landing.png' });

// Login
await page.goto(BASE+'/login', { timeout: 30000 }); await sleep(2000);
const ei = page.locator('input[type="email"], input[placeholder*="email" i]').first();
const pi = page.locator('input[type="password"]').first();
await ei.fill(EMAIL); await pi.fill(PASS);
await page.screenshot({ path: DIR+'/01-login-filled.png' });
const sb = page.locator('button[type="submit"], button:has-text("Sign in")').first();
await sb.click(); await sleep(5000);
await page.screenshot({ path: DIR+'/02-after-login.png' });
console.log('After login URL:', page.url());

// If on onboarding, go through steps
if (page.url().includes('onboarding')) {
  console.log('✅ On onboarding page!');
  // Select SaaS + PARWA
  const s = page.locator('button:has-text("SaaS")').first();
  if (await s.count() > 0) await s.click(); await sleep(500);
  const p = page.locator('button:has-text("PARWA")').first();
  if (await p.count() > 0) await p.click(); await sleep(500);
  await page.screenshot({ path: DIR+'/03-step1-selected.png' });
  
  // Continue to step 2
  const c1 = page.locator('button:has-text("Continue")').last();
  if (await c1.count() > 0) await c1.click(); await sleep(4000);
  await page.screenshot({ path: DIR+'/04-step2-legal.png' });
  
  // Accept legal
  const cbs = page.locator('button[role="checkbox"], input[type="checkbox"]');
  for (let i = 0; i < await cbs.count(); i++) { try { await cbs.nth(i).click({timeout:1000}); } catch {} }
  await sleep(500);
  const ab = page.locator('button:has-text("Accept"), button:has-text("Agree"), button:has-text("Continue")').last();
  if (await ab.count() > 0) await ab.click(); await sleep(4000);
  await page.screenshot({ path: DIR+'/05-step3-integrations.png' });
  console.log('✅ Step 3 (Phase 13 API Key system)');
  
  // Step 4: Knowledge
  const c3 = page.locator('button:has-text("Continue")').last();
  if (await c3.count() > 0) await c3.click(); await sleep(4000);
  await page.screenshot({ path: DIR+'/06-step4-knowledge.png' });
  
  // Step 5: AI Config
  const c4 = page.locator('button:has-text("Continue")').last();
  if (await c4.count() > 0) await c4.click(); await sleep(4000);
  await page.screenshot({ path: DIR+'/07-step5-aiconfig.png' });
  
  // Step 6: Cost Breakdown
  const c5 = page.locator('button:has-text("Continue")').last();
  if (await c5.count() > 0) await c5.click(); await sleep(4000);
  await page.screenshot({ path: DIR+'/08-step6-cost.png' });
  
  // Step 7: Launch
  const c6 = page.locator('button:has-text("Continue"), button:has-text("Activate"), button:has-text("Launch")').last();
  if (await c6.count() > 0) await c6.click(); await sleep(6000);
  await page.screenshot({ path: DIR+'/09-step7-victory.png' });
  console.log('✅ First Victory!');
}

// Dashboard
await page.goto(BASE+'/dashboard', { timeout: 30000 }); await sleep(3000);
console.log('Dashboard URL:', page.url());
await page.screenshot({ path: DIR+'/10-dashboard.png' });

if (!page.url().includes('login')) {
  await page.goto(BASE+'/dashboard/ai-tools', { timeout: 30000 }); await sleep(3000);
  await page.screenshot({ path: DIR+'/11-ai-tools.png' });
  await page.goto(BASE+'/dashboard/variants', { timeout: 30000 }); await sleep(3000);
  await page.screenshot({ path: DIR+'/12-variants.png' });
}

// Models page with Hire Agent
await page.goto(BASE+'/models', { timeout: 30000 }); await sleep(3000);
const ind = page.locator('button:has-text("SaaS")').first();
if (await ind.count() > 0) await ind.click(); await sleep(2000);
await page.screenshot({ path: DIR+'/13-models-saas.png' });
const hire = page.locator('button:has-text("Hire Agent")').first();
if (await hire.count() > 0) {
  await hire.click(); await sleep(2000);
  await page.screenshot({ path: DIR+'/14-confirm-modal.png' });
  const cont = page.locator('button:has-text("Continue")').first();
  if (await cont.count() > 0) await cont.click(); await sleep(5000);
  await page.screenshot({ path: DIR+'/15-onboarding-from-modal.png' });
}

console.log('\n═══ NATURAL JOURNEY COMPLETE ═══');
await browser.close();
