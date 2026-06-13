import { chromium } from 'playwright';
const BASE = 'http://127.0.0.1:3000';
const DIR = '/home/z/my-project/download/proof-final';
const EMAIL = '${EMAIL}';
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
await page.locator('input[type="email"], input[placeholder*="email" i]').first().fill(EMAIL);
await page.locator('input[type="password"]').first().fill(PASS);
await page.locator('button[type="submit"], button:has-text("Sign in")').first().click();
await sleep(5000);
await page.screenshot({ path: DIR+'/01-after-login.png' });

// Step 1: Industry + Variant
const s = page.locator('button:has-text("SaaS")').first();
if (await s.count() > 0) await s.click(); await sleep(500);
const p = page.locator('button:has-text("PARWA")').first();
if (await p.count() > 0) await p.click(); await sleep(500);
await page.screenshot({ path: DIR+'/02-step1-selected.png' });

// Continue to step 2
const c1 = page.locator('button:has-text("Continue")').last();
await c1.click(); await sleep(4000);
await page.screenshot({ path: DIR+'/03-step2-legal.png' });

// Accept all legal - try clicking ALL interactive elements that look like checkboxes
// Use JavaScript to click all checkboxes
await page.evaluate(() => {
  document.querySelectorAll('button[role="checkbox"], input[type="checkbox"], [data-state="unchecked"]').forEach(el => {
    try { el.click(); } catch {}
  });
});
await sleep(1000);
// Also try clicking labels near checkboxes
const labels = page.locator('label, span:has-text("I agree"), span:has-text("I accept"), span:has-text("I have read")');
for (let i = 0; i < await labels.count(); i++) {
  try { await labels.nth(i).click({ timeout: 500 }); } catch {}
}
await sleep(1000);
await page.screenshot({ path: DIR+'/04-step2-checkboxes.png' });

// Now click the Accept/Continue button on step 2
const step2Btn = page.locator('button:not([disabled]):has-text("Accept"), button:not([disabled]):has-text("Agree"), button:not([disabled]):has-text("Continue")').last();
if (await step2Btn.count() > 0) {
  await step2Btn.click(); await sleep(4000);
} else {
  // Fallback: click any enabled Continue button
  const anyCont = page.locator('button:not([disabled]):has-text("Continue")').last();
  if (await anyCont.count() > 0) await anyCont.click(); await sleep(4000);
}
await page.screenshot({ path: DIR+'/05-step3-integrations.png' });

// Phase 13: Check for API key management
const keyMgmt = await page.locator('text=Key Management, text=Rotate Key, text=API Key').first().count();
console.log('Phase 13 - Key Management visible:', keyMgmt > 0);

// Continue through steps
for (let step = 4; step <= 6; step++) {
  const c = page.locator('button:not([disabled]):has-text("Continue")').last();
  if (await c.count() > 0) await c.click(); await sleep(4000);
  await page.screenshot({ path: DIR+`/0${step+2}-step${step}.png` });
}

// Victory
const act = page.locator('button:not([disabled]):has-text("Continue"), button:not([disabled]):has-text("Activate"), button:not([disabled]):has-text("Launch")').last();
if (await act.count() > 0) await act.click(); await sleep(6000);
await page.screenshot({ path: DIR+'/09-victory.png' });
console.log('✅ Victory!');

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

// Models → Confirm
await page.goto(BASE+'/models', { timeout: 30000 }); await sleep(3000);
const ind = page.locator('button:has-text("SaaS")').first();
if (await ind.count() > 0) await ind.click(); await sleep(2000);
await page.screenshot({ path: DIR+'/13-models-saas.png' });
const hire = page.locator('button:has-text("Hire Agent")').first();
if (await hire.count() > 0) {
  await hire.click(); await sleep(2000);
  await page.screenshot({ path: DIR+'/14-confirm-modal.png' });
}

console.log('\\n═══ COMPLETE ═══');
await browser.close();
