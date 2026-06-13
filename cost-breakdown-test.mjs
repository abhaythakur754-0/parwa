import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ 
    headless: true,
    args: [
      '--disable-gpu',
      '--disable-dev-shm-usage',
      '--no-sandbox',
      '--disable-extensions',
      '--js-flags=--max-old-space-size=128',
      '--disable-background-timer-throttling',
      '--disable-backgrounding-occluded-windows',
      '--disable-renderer-backgrounding',
      '--no-first-run',
      '--no-default-browser-check',
    ]
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    ignoreHTTPSErrors: true,
    javaScriptEnabled: true,
  });

  const errors = [];
  let screenshots = {};

  try {
    // ── Step 1: Login ──
    console.log('1. Logging in...');
    const page = await context.newPage();
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(`[LOGIN] ${msg.text()}`);
    });
    page.on('pageerror', (err) => errors.push(`[LOGIN PAGE ERROR] ${err.message}`));
    
    await page.goto('http://localhost:3000/login', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(2000);
    
    await page.locator('input[type="email"], input[name="email"]').first().fill('dashboard@test.io');
    await page.locator('input[type="password"]').first().fill('Test@1234');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(3000);
    console.log('   Post-login URL:', page.url());
    
    // Close login page to free memory
    await page.close();

    // ── Step 2: Navigate to cost-breakdown ──
    console.log('\n2. Navigating to cost-breakdown page...');
    const page2 = await context.newPage();
    page2.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(`[COST] ${msg.text()}`);
    });
    page2.on('pageerror', (err) => errors.push(`[COST PAGE ERROR] ${err.message}`));
    
    await page2.goto('http://localhost:3000/dashboard/cost-breakdown', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page2.waitForTimeout(5000);
    console.log('   Page loaded. URL:', page2.url());

    // ── Step 3: Take screenshot (viewport only) ──
    console.log('\n3. Taking screenshot...');
    try {
      await page2.screenshot({ path: '/tmp/cost-breakdown-top.png', fullPage: false, timeout: 10000 });
      screenshots.top = true;
      console.log('   ✅ Top screenshot saved.');
    } catch (e) {
      console.log('   ⚠️ Screenshot failed:', e.message?.substring(0, 80));
    }

    // ── Step 4: Verify key elements ──
    console.log('\n4. Verifying key elements...');
    const bodyText = await page2.locator('body').innerText().catch(() => '');
    
    // Debug: print page text
    console.log('\n   --- PAGE TEXT (first 800 chars) ---');
    console.log(bodyText.substring(0, 800));
    console.log('   --- END ---\n');

    const hasCostBreakdown = bodyText.includes('Cost Breakdown');
    const hasStarter = bodyText.includes('PARWA Starter');
    const hasGrowth = bodyText.includes('PARWA Growth');
    const hasHigh = bodyText.includes('PARWA High');
    const hasUsage = bodyText.includes('Ticket Usage');
    const hasAddOns = bodyText.includes('Optional Add-On');
    const hasPrice3999 = bodyText.includes('$3,999') || bodyText.includes('3,999');
    const hasTotalMonthly = bodyText.includes('Total Monthly');
    const hasSavings = bodyText.includes('vs human');
    const hasIntegrations = bodyText.includes('Integrations Impact');
    const hasLineItems = bodyText.includes('Line Items');

    console.log(`   "Cost Breakdown" heading: ${hasCostBreakdown ? '✅' : '❌'}`);
    console.log(`   PARWA Starter card: ${hasStarter ? '✅' : '❌'}`);
    console.log(`   PARWA Growth card: ${hasGrowth ? '✅' : '❌'}`);
    console.log(`   PARWA High card: ${hasHigh ? '✅' : '❌'}`);
    console.log(`   Ticket Usage bar: ${hasUsage ? '✅' : '❌'}`);
    console.log(`   Add-ons section: ${hasAddOns ? '✅' : '❌'}`);
    console.log(`   $3,999 price: ${hasPrice3999 ? '✅' : '❌'}`);
    console.log(`   Total Monthly: ${hasTotalMonthly ? '✅' : '❌'}`);
    console.log(`   Savings vs humans: ${hasSavings ? '✅' : '❌'}`);
    console.log(`   Integrations Impact: ${hasIntegrations ? '✅' : '❌'}`);
    console.log(`   Line Items: ${hasLineItems ? '✅' : '❌'}`);

    // ── Step 5: Test adding PARWA High ──
    console.log('\n5. Testing variant toggle (adding PARWA High)...');
    const addButtons = page2.locator('button:has-text("Add Variant")');
    const addBtnCount = await addButtons.count().catch(() => 0);
    console.log(`   Found ${addBtnCount} "Add Variant" buttons`);
    
    let highAdded = false;
    if (addBtnCount >= 3) {
      await addButtons.nth(2).click();
      highAdded = true;
      await page2.waitForTimeout(1500);
      
      const updatedText = await page2.locator('body').innerText().catch(() => '');
      const hasPriceAfterAdd = updatedText.includes('$3,999') || updatedText.includes('3,999');
      console.log(`   $3,999 after adding High: ${hasPriceAfterAdd ? '✅ FOUND' : '❌ NOT FOUND'}`);
      
      try {
        await page2.screenshot({ path: '/tmp/cost-breakdown-with-high.png', fullPage: false, timeout: 10000 });
        screenshots.withHigh = true;
      } catch {}
    }

    await page2.close();

    // ── Summary ──
    console.log('\n═══════════════════════════════════════');
    console.log('            TEST SUMMARY');
    console.log('═══════════════════════════════════════');
    console.log(`Page loaded successfully: ✅ YES`);
    console.log(`"Cost Breakdown" heading: ${hasCostBreakdown ? '✅' : '❌'}`);
    console.log(`Variant mixer cards: Starter=${hasStarter ? '✅' : '❌'} Growth=${hasGrowth ? '✅' : '❌'} High=${hasHigh ? '✅' : '❌'}`);
    console.log(`Usage bars: ${hasUsage ? '✅' : '❌'}`);
    console.log(`Add-ons section: ${hasAddOns ? '✅' : '❌'}`);
    console.log(`PARWA High price $3,999/mo: ${hasPrice3999 ? '✅ CORRECT' : '❌ NOT DISPLAYED'}`);
    console.log(`Screenshot captured: ${screenshots.top ? '✅' : '❌ (OOM)'}`);
    console.log(`Console errors: ${errors.length}`);
    if (errors.length > 0) {
      errors.slice(0, 5).forEach(e => console.log(`  - ${e}`));
    }
    console.log('═══════════════════════════════════════');

  } catch (err) {
    console.error('\n❌ TEST FAILED WITH ERROR:');
    console.error(err.message);
  } finally {
    await browser.close();
  }
})();
