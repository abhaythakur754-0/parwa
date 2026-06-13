import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:3000';
const DIR = '/home/z/my-project/download/journey-test';
const EMAIL = 'journey1781299408@parwa.com';
const PASSWORD = 'TestPassword123!';

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-gpu'] });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

// Step 1: Landing
console.log('1. Landing...');
await page.goto(BASE, { timeout: 30000 });
await sleep(2000);
await page.screenshot({ path: DIR+'/e2e-00-landing.png' });

// Step 2: Login
console.log('2. Login...');
await page.goto(BASE+'/login', { timeout: 30000 });
await sleep(2000);
const ei = page.locator('input[type="email"], input[placeholder*="email" i]').first();
const pi = page.locator('input[type="password"]').first();
await ei.fill(EMAIL);
await pi.fill(PASSWORD);
const sb = page.locator('button[type="submit"], button:has-text("Sign in")').first();
await sb.click();
await sleep(5000);
const afterUrl = page.url();
console.log('After login:', afterUrl);
await page.screenshot({ path: DIR+'/e2e-01-after-login.png' });

// Step 3: Onboarding
console.log('3. Onboarding...');
await page.goto(BASE+'/onboarding', { timeout: 30000 });
await sleep(3000);
const onbUrl = page.url();
console.log('Onboarding URL:', onbUrl);
await page.screenshot({ path: DIR+'/e2e-02-onboarding.png' });

if (onbUrl.includes('onboarding') && !onbUrl.includes('login')) {
  console.log('✅ Onboarding loaded!');
  const s = page.locator('button:has-text("SaaS")').first();
  if (await s.count() > 0) await s.click(); await sleep(500);
  const p = page.locator('button:has-text("PARWA")').first();
  if (await p.count() > 0) await p.click(); await sleep(500);
  await page.screenshot({ path: DIR+'/e2e-03-step1-selected.png' });
  
  const c1 = page.locator('button:has-text("Continue")').last();
  if (await c1.count() > 0) await c1.click(); await sleep(4000);
  await page.screenshot({ path: DIR+'/e2e-04-step2-legal.png' });
  
  const cbs = page.locator('button[role="checkbox"], input[type="checkbox"]');
  for (let i = 0; i < await cbs.count(); i++) { try { await cbs.nth(i).click({timeout:1000}); } catch {} }
  await sleep(500);
  const ab = page.locator('button:has-text("Accept"), button:has-text("Agree"), button:has-text("Continue")').last();
  if (await ab.count() > 0) await ab.click(); await sleep(4000);
  await page.screenshot({ path: DIR+'/e2e-05-step3-integrations.png' });
  console.log('✅ Step 3 (Phase 13)');
  
  for (let step = 4; step <= 6; step++) {
    const c = page.locator('button:has-text("Continue")').last();
    if (await c.count() > 0) await c.click(); await sleep(4000);
    await page.screenshot({ path: DIR+'/e2e-0'+(5+step)+'-step'+step+'.png' });
  }
  
  const act = page.locator('button:has-text("Continue"), button:has-text("Activate"), button:has-text("Launch")').last();
  if (await act.count() > 0) await act.click(); await sleep(6000);
  await page.screenshot({ path: DIR+'/e2e-12-victory.png' });
  console.log('✅ Victory!');
}

// Step 4: Dashboard
console.log('4. Dashboard...');
await page.goto(BASE+'/dashboard', { timeout: 30000 }); await sleep(3000);
console.log('Dashboard URL:', page.url());
await page.screenshot({ path: DIR+'/e2e-13-dashboard.png' });

await page.goto(BASE+'/dashboard/ai-tools', { timeout: 30000 }); await sleep(3000);
await page.screenshot({ path: DIR+'/e2e-14-ai-tools.png' });

await page.goto(BASE+'/dashboard/variants', { timeout: 30000 }); await sleep(3000);
await page.screenshot({ path: DIR+'/e2e-15-variants.png' });

// Step 5: Models + Confirm
console.log('5. Models...');
await page.goto(BASE+'/models', { timeout: 30000 }); await sleep(3000);
const ind = page.locator('button:has-text("SaaS")').first();
if (await ind.count() > 0) await ind.click(); await sleep(2000);
await page.screenshot({ path: DIR+'/e2e-16-models-saas.png' });

const hire = page.locator('button:has-text("Hire Agent")').first();
console.log('Hire Agent:', await hire.count() > 0);
if (await hire.count() > 0) {
  await hire.click(); await sleep(2000);
  await page.screenshot({ path: DIR+'/e2e-17-confirm-modal.png' });
  const cont = page.locator('button:has-text("Continue")').first();
  if (await cont.count() > 0) await cont.click(); await sleep(5000);
  await page.screenshot({ path: DIR+'/e2e-18-onboarding-modal.png' });
}

console.log('\n═══ E2E COMPLETE ═══');
await browser.close();
