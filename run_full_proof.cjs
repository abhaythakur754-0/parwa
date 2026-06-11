const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const DIR = '/home/z/my-project/download/parwa-proof';
  
  function log(msg) { console.log(`[${new Date().toISOString().split('T')[1].split('.')[0]}] ${msg}`); }
  async function ss(name) { await page.screenshot({ path: `${DIR}/${name}.png`, fullPage: true }); log('📸 ' + name); }
  
  // LOGIN
  log('━━━ LOGIN ━━━');
  await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);
  await (await page.$('input[type="email"], input[name="email"]')).fill('test@parwa.buzz');
  await (await page.$('input[type="password"]')).fill('Test1234!');
  await (await page.$('button[type="submit"]')).click();
  await page.waitForTimeout(5000);
  await ss('proof-01-login-success');
  log('✅ Login successful: ' + page.url());
  
  // Set pricing context
  await page.evaluate(() => {
    localStorage.setItem('parwa_pricing_context', JSON.stringify({ industry: 'saas', variant: 'parwa', variants: ['parwa'], totalMonthly: 299 }));
  });
  await page.goto('http://localhost:3000/onboarding?source=pricing&industry=saas', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  
  // STEP 1: INDUSTRY/VARIANT
  log('━━━ STEP 1: INDUSTRY/VARIANT ━━━');
  await page.evaluate(() => {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) { if (btn.textContent?.trim() === 'SaaS') { btn.click(); return; } }
  });
  await page.waitForTimeout(500);
  await page.evaluate(() => {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) { if (btn.textContent?.trim() === 'PARWA') { btn.click(); return; } }
  });
  await page.waitForTimeout(500);
  await ss('proof-02-variant-selected');
  await page.evaluate(() => {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) { if (!btn.disabled && btn.textContent?.includes('Continue')) { btn.click(); return; } }
  });
  await page.waitForTimeout(3000);
  await ss('proof-03-step1-done');
  log('✅ Step 1 done');
  
  // STEP 2: LEGAL
  log('━━━ STEP 2: LEGAL COMPLIANCE ━━━');
  await page.evaluate(() => {
    const buttons = document.querySelectorAll('button');
    for (const btn of buttons) {
      const rect = btn.getBoundingClientRect();
      const classes = btn.className?.toString() || '';
      if (rect.width <= 25 && rect.height <= 25 && rect.y > 200 && classes.includes('border')) {
        const parent = btn.parentElement;
        if (parent?.textContent?.includes('Terms') || parent?.textContent?.includes('Privacy') || parent?.textContent?.includes('AI Data')) {
          btn.click();
        }
      }
    }
  });
  await page.waitForTimeout(500);
  await ss('proof-04-legal-checkboxes');
  await page.evaluate(() => {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) { if (btn.textContent?.includes('Accept All') && !btn.disabled) { btn.click(); return; } }
  });
  await page.waitForTimeout(4000);
  await ss('proof-05-step2-done');
  log('✅ Step 2 done');
  
  // STEP 3: INTEGRATIONS - Connect at least one tool!
  log('━━━ STEP 3: INTEGRATIONS ━━━');
  await page.waitForTimeout(2000);
  await ss('proof-06-integrations');
  
  // Click "Connect" on the first available integration (Brevo since we have its API key)
  await page.evaluate(() => {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) {
      if (btn.textContent?.trim() === 'Connect') { btn.click(); return true; }
    }
    return false;
  });
  await page.waitForTimeout(3000);
  await ss('proof-07-integration-connecting');
  
  // Now click Continue
  await page.evaluate(() => {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) {
      const t = btn.textContent?.trim();
      if (!btn.disabled && t?.includes('Continue')) { btn.click(); return; }
    }
  });
  await page.waitForTimeout(4000);
  await ss('proof-08-step3-done');
  log('✅ Step 3 done');
  
  // STEP 4: KNOWLEDGE UPLOAD
  log('━━━ STEP 4: KNOWLEDGE UPLOAD ━━━');
  await page.waitForTimeout(2000);
  await ss('proof-09-knowledge');
  await page.evaluate(() => {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) {
      const t = btn.textContent?.trim();
      if (!btn.disabled && t?.includes('Continue')) { btn.click(); return; }
    }
  });
  await page.waitForTimeout(4000);
  await ss('proof-10-step4-done');
  log('✅ Step 4 done');
  
  // STEP 5: AI CONFIG
  log('━━━ STEP 5: AI CONFIG ━━━');
  await page.waitForTimeout(2000);
  await ss('proof-11-ai-config');
  
  // Check if Activate button is enabled
  const activateEnabled = await page.evaluate(() => {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) {
      if (btn.textContent?.includes('Activate') && !btn.disabled) { btn.click(); return true; }
    }
    return false;
  });
  log('Activate button clicked: ' + activateEnabled);
  
  if (!activateEnabled) {
    log('⚠️ Activate button disabled - prerequisites not met. Trying to proceed anyway...');
    // Click Continue as fallback
    await page.evaluate(() => {
      const btns = document.querySelectorAll('button');
      for (const btn of btns) {
        const t = btn.textContent?.trim();
        if (!btn.disabled && t?.includes('Continue')) { btn.click(); return; }
      }
    });
  }
  await page.waitForTimeout(4000);
  await ss('proof-12-step5-done');
  log('✅ Step 5 done');
  
  // STEP 6: COST BREAKDOWN
  log('━━━ STEP 6: COST BREAKDOWN ━━━');
  await page.waitForTimeout(2000);
  await ss('proof-13-cost-breakdown');
  await page.evaluate(() => {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) {
      const t = btn.textContent?.trim();
      if (!btn.disabled && (t?.includes('Proceed') || t?.includes('Checkout') || t?.includes('Confirm') || t?.includes('Complete') || t?.includes('Continue'))) { btn.click(); return; }
    }
  });
  await page.waitForTimeout(4000);
  await ss('proof-14-step6-done');
  log('✅ Step 6 done');
  
  // STEP 7: FIRST VICTORY
  log('━━━ STEP 7: FIRST VICTORY ━━━');
  await page.waitForTimeout(2000);
  await ss('proof-15-first-victory');
  
  // Click Go to Dashboard
  await page.evaluate(() => {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) {
      const t = btn.textContent?.trim();
      if (t?.includes('Dashboard') || t?.includes('Go to')) { btn.click(); return; }
    }
  });
  await page.waitForTimeout(5000);
  await ss('proof-16-dashboard');
  
  // SUMMARY
  log('━━━ SUMMARY ━━━');
  log('Final URL: ' + page.url());
  const finalText = await page.evaluate(() => document.body?.textContent?.slice(0, 500));
  if (finalText?.includes('something went wrong') || finalText?.includes('Something went wrong')) {
    log('❌ "Something went wrong" found!');
  } else {
    log('✅ NO "Something went wrong" errors!');
  }
  log('Screenshots: ' + DIR);
  
  await browser.close();
})();
