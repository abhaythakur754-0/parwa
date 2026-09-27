import { chromium, Browser, Page } from 'playwright';
import * as fs from 'fs';

const DOWNLOAD_DIR = '/home/z/my-project/download';

// Use existing credentials from previous test
const testEmail = 'flexpaytest1784357596469@parwa.dev';
const testPassword = 'TestPass123!@#';

async function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function screenshot(page: Page, name: string, fullPage = false) {
  const path = `${DOWNLOAD_DIR}/${name}`;
  await page.screenshot({ path, fullPage });
  console.log(`✅ Saved: ${name}`);
  return path;
}

async function main() {
  console.log('=== PARWA BILLING PAGE DEEP TEST ===\n');

  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    locale: 'en-US'
  });
  
  const page = await context.newPage();

  // Log console messages
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      console.log(`   Browser ${msg.type()}: ${msg.text().substring(0, 100)}`);
    }
  });

  try {
    // Step 1: Login via API first to set auth
    console.log('📍 Step 1: Setting up authentication...');
    
    // First call register API to ensure user exists
    await page.evaluate(async ({ email, password }) => {
      await fetch('https://parwa.buzz/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name: 'FlexPay Test User' })
      });
    }, { email: testEmail, password: testPassword }).catch(() => {});
    
    console.log('   ✅ API registration called');

    // Step 2: Go to login page and login properly
    console.log('📍 Step 2: Logging in via UI...');
    await page.goto('https://parwa.buzz/login', { waitUntil: 'networkidle', timeout: 45000 });
    await sleep(1000);
    
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', testPassword);
    await page.click('button[type="submit"]');
    
    // Wait for navigation away from login
    console.log('   Waiting for redirect...');
    try {
      await page.waitForURL('**/dashboard/**', { timeout: 15000 });
      console.log('   ✅ Redirected to dashboard');
    } catch (e) {
      console.log('   ⚠️ No dashboard redirect, checking current URL...');
      console.log(`   URL: ${page.url()}`);
    }
    
    await sleep(2000);
    await screenshot(page, 'v5-01-after-login.png');

    // Step 3: Navigate to billing and wait for full load
    console.log('\n📍 Step 3: Loading billing page...');
    await page.goto('https://parwa.buzz/dashboard/billing', { waitUntil: 'commit', timeout: 60000 });
    
    // Wait for loading spinner to disappear or content to appear
    console.log('   Waiting for content to load...');
    
    let attempts = 0;
    const maxAttempts = 20; // 20 seconds max
    
    while (attempts < maxAttempts) {
      await sleep(1000);
      attempts++;
      
      // Check if loading spinner is gone
      const spinner = await page.$('[class*="spinner"], [class*="loading"], svg.animate-spin').catch(() => null);
      
      // Check if we have real content (pricing cards, etc.)
      const hasContent = await page.evaluate(() => {
        const body = document.body.innerText;
        return body.includes('$') || body.includes('Subscribe') || body.includes('FlexPay') || 
               body.includes('plan') || body.includes('999') || body.includes('2499');
      }).catch(() => false);
      
      if (!spinner && hasContent) {
        console.log(`   ✅ Content loaded after ${attempts}s`);
        break;
      }
      
      if (attempts % 5 === 0) {
        console.log(`   Still waiting... (${attempts}s)`);
        await screenshot(page, `v5-loading-${attempts}s.png`);
      }
    }

    // Take final screenshots regardless
    console.log('\n📍 Step 4: Capturing billing page...');
    await screenshot(page, 'v5-02-billing-final.png', true);
    await screenshot(page, 'v5-02-billing-viewport.png');

    // Get full page text for analysis
    const pageText = await page.evaluate(() => document.body.innerText).catch(() => '');
    
    console.log('\n========== BILLING PAGE CONTENT ==========');
    // Print truncated text
    console.log(pageText.substring(0, 2000) + (pageText.length > 2000 ? '\n...(truncated)' : ''));

    // Check for specific FlexPay elements
    console.log('\n========== FLEXPAY UI CHECKS ==========');
    const checks = [
      { name: 'FlexPay Info Banner', terms: ['FlexPay', '$100', 'daily', 'bank'] },
      { name: 'Feature Timeline (Day 1)', terms: ['Day 1', 'Immediate', 'Ticket Management'] },
      { name: 'Feature Timeline (Day 11)', terms: ['Day 11', 'SMS', 'Calling'] },
      { name: 'Pricing Cards ($)', terms: ['$', '999', '2499', '3999'] },
      { name: 'Subscribe Buttons', terms: ['Subscribe', 'Get Started', 'Choose'] },
      { name: 'USD Currency Note', terms: ['USD', 'US Dollar', 'dollar'] },
    ];

    for (const check of checks) {
      const found = check.terms.some(term => pageText.toLowerCase().includes(term.toLowerCase()));
      console.log(`${found ? '✅' : '❌'} ${check.name}: ${found ? 'FOUND' : 'NOT FOUND'}`);
    }

    // Step 5: Try interacting with Subscribe button
    console.log('\n📍 Step 5: Testing Subscribe interaction...');
    
    const subscribeSelectors = [
      'button:has-text("Subscribe")',
      'button:has-text("Get Started")',
      'button:has-text("Choose")',
      'button[class*="subscribe"]',
      '[data-testid*="subscribe"]'
    ];
    
    let clickedSubscribe = false;
    for (const selector of subscribeSelectors) {
      const btn = await page.$(selector).catch(() => null);
      if (btn) {
        const text = await btn.textContent().catch(() => '');
        console.log(`   Found button: "${text?.trim()}"`);
        
        await btn.click();
        clickedSubscribe = true;
        await sleep(2500);
        
        await screenshot(page, 'v5-03-after-subscribe.png', true);
        
        // Check for modal
        const modalText = await page.evaluate(() => {
          const modal = document.querySelector('[role="dialog"], [class*="modal"], [class*="dialog"]');
          return modal ? modal.innerText : null;
        }).catch(() => null);
        
        if (modalText) {
          console.log('\n   📋 MODAL CONTENT:');
          console.log(modalText.substring(0, 800));
          await screenshot(page, 'v5-04-modal.png', true);
        }
        break;
      }
    }
    
    if (!clickedSubscribe) {
      console.log('   ⚠️ No subscribe button found');
      
      // List all buttons on page
      const allButtons = await page.$$eval('button', btns => 
        btns.map(b => ({ text: b.innerText.trim(), class: b.className.substring(0, 50) }))
      ).catch(() => []);
      console.log('\n   Available buttons:');
      allButtons.forEach(b => console.log(`     - "${b.text}" (${b.class}...)`));
    }

    // Final summary
    console.log('\n========== TEST COMPLETE ==========');
    console.log(`Test Account: ${testEmail}`);
    console.log(`Screenshots saved to: ${DOWNLOAD_DIR}/`);

  } catch (error) {
    console.error('❌ Error:', error);
    await screenshot(page, 'v5-error.png');
  } finally {
    await browser.close();
  }
}

main();
