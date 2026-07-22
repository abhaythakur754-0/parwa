import { chromium, Browser, Page } from 'playwright';
import * as fs from 'fs';

const DOWNLOAD_DIR = '/home/z/my-project/download';

const timestamp = Date.now();
const testEmail = `flexpaytest${timestamp}@parwa.dev`;
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
  console.log('=== PARWA SIGNUP & BILLING TEST v4 ===\n');
  console.log(`📧 Email: ${testEmail}`);

  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    locale: 'en-US'
  });
  
  const page = await context.newPage();

  try {
    // Step 1: Go to login page
    console.log('\n📍 Step 1: Login page...');
    await page.goto('https://parwa.buzz/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await sleep(1500);
    await screenshot(page, 'v4-01-login.png');

    // Step 2: Fill credentials
    console.log('📍 Step 2: Filling form...');
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', testPassword);
    await screenshot(page, 'v4-02-filled.png');

    // Step 3: Click Sign in button (might create account if new)
    console.log('📍 Step 3: Clicking Sign in...');
    
    // Listen for navigation/dialogs
    page.on('dialog', async dialog => {
      console.log(`   Dialog: ${dialog.message()}`);
      await dialog.accept().catch(() => {});
    });

    // Try clicking Sign in - some systems auto-register
    await page.click('button[type="submit"]');
    await sleep(4000);
    
    await screenshot(page, 'v4-03-after-signin.png');
    let currentUrl = page.url();
    console.log(`   URL: ${currentUrl}`);

    // Check if there's an error
    const errorText = await page.textContent('.text-red-500, .text-red-600, [class*="error"], [class*="invalid"]').catch(() => '');
    if (errorText && errorText.trim()) {
      console.log(`   Error shown: ${errorText.trim()}`);
    }

    // If still on login, try clicking "Sign up" text link
    if (currentUrl.includes('/login')) {
      console.log('\n📍 Step 3b: Trying Sign up link...');
      
      // Look for sign up link more carefully
      const allLinks = await page.$$('a');
      console.log(`   Found ${allLinks.length} links`);
      
      for (const link of allLinks) {
        const href = await link.getAttribute('href').catch(() => '');
        const text = await link.textContent().catch(() => '');
        if (text && text.toLowerCase().includes('sign up')) {
          console.log(`   Found link: "${text?.trim()}" → ${href}`);
          
          // Try clicking with navigation wait
          await Promise.all([
            page.waitForNavigation({ timeout: 10000 }).catch(() => {}),
            link.click()
          ]).catch(() => {});
          
          await sleep(2000);
          currentUrl = page.url();
          console.log(`   After click URL: ${currentUrl}`);
          await screenshot(page, 'v4-04-after-signup-link.png');
          break;
        }
      }

      // Check if we're now on a different page/form
      const inputs = await page.$$('input');
      console.log(`   Input count now: ${inputs.length}`);
      
      for (let i = 0; i < inputs.length; i++) {
        const inp = inputs[i];
        const type = await inp.getAttribute('type').catch(() => '');
        const name = await inp.getAttribute('name').catch(() => '');
        const ph = await inp.getAttribute('placeholder').catch(() => '');
        console.log(`   Input[${i}]: type=${type} name=${name} ph=${ph}`);
      }
    }

    // Step 4: Try direct API call to create user (if UI doesn't work)
    if (currentUrl.includes('/login')) {
      console.log('\n📍 Step 4: Trying API-based registration...');
      
      // Try NextAuth / custom auth endpoints
      const apiEndpoints = [
        { url: 'https://parwa.buzz/api/auth/register', method: 'POST' },
        { url: 'https://parwa.buzz/api/users', method: 'POST' },
        { url: 'https://parwa.buzz/api/signup', method: 'POST' },
      ];

      for (const ep of apiEndpoints) {
        try {
          console.log(`   Trying ${ep.method} ${ep.url}...`);
          const response = await page.evaluate(async ({ url, email, password }) => {
            const res = await fetch(url, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ email, password, name: 'FlexPay Test' })
            });
            return { status: res.status, ok: res.ok, data: await res.text().catch(() => '') };
          }, { url: ep.url, email: testEmail, password: testPassword });
          
          console.log(`   Response: ${response.status} ${response.ok ? 'OK' : 'FAIL'}`);
          if (response.ok || response.status === 201) {
            console.log('   ✅ User created via API!');
            break;
          }
        } catch (e) {
          console.log(`   Failed: ${(e as Error).message.substring(0, 60)}`);
        }
      }

      // Now try logging in again
      console.log('\n   Trying login after API attempt...');
      await page.goto('https://parwa.buzz/login', { waitUntil: 'domcontentloaded', timeout: 20000 });
      await sleep(1000);
      await page.fill('input[name="email"]', testEmail);
      await page.fill('input[name="password"]', testPassword);
      await page.click('button[type="submit"]');
      await sleep(4000);
      
      await screenshot(page, 'v4-05-after-api-login.png');
      currentUrl = page.url();
      console.log(`   URL after API+login: ${currentUrl}`);
    }

    // Step 5: Navigate to billing regardless
    console.log('\n📍 Step 5: Navigating to billing...');
    try {
      await page.goto('https://parwa.buzz/dashboard/billing', { 
        waitUntil: 'load', 
        timeout: 60000 
      });
    } catch (e) {
      console.log('   ⚠️ Timeout, capturing current state');
    }
    await sleep(3000);
    
    await screenshot(page, 'v4-06-billing-full.png', true);
    await screenshot(page, 'v4-06-billing-viewport.png');

    // Final analysis
    console.log('\n========== ANALYSIS ==========');
    const finalUrl = page.url();
    const bodyText = await page.textContent('body').catch(() => '') || '';
    
    console.log(`Final URL: ${finalUrl}`);
    
    // Search for FlexPay content
    const searchTerms = [
      'FlexPay', 'flexpay', 'Flex Pay',
      '$100', '100/day', 'daily',
      'Day 1', 'Day 11',
      'Ticket Management', 'Team Collaboration',
      'SMS Notification', 'Calling Feature',
      '$999', '$2,499', '$3,999', '2499', '3999',
      'Subscribe', 'subscribe',
      'Installment', 'installment',
      'billing', 'Billing',
      'plan', 'Plan', 'pricing', 'Pricing'
    ];
    
    console.log('\nContent found:');
    const foundTerms = [];
    for (const term of searchTerms) {
      if (bodyText.includes(term)) {
        foundTerms.push(term);
        console.log(`  ✅ "${term}"`);
      }
    }
    
    if (foundTerms.length === 0) {
      console.log('  ❌ No billing/FlexPay terms found - may not be logged in');
    }

    // Save results
    fs.writeFileSync(`${DOWNLOAD_DIR}/test-credentials.txt`, 
`PARWA TEST ACCOUNT
===============
Email: ${testEmail}
Password: ${testPassword}
Created: ${new Date().toISOString()}
Final URL: ${finalUrl}
Found Terms: ${foundTerms.join(', ') || 'None'}`
    );

    console.log('\n✅ Test complete!');
    console.log(`Credentials: ${DOWNLOAD_DIR}/test-credentials.txt`);

  } catch (error) {
    console.error('❌ Error:', error);
    await screenshot(page, 'v4-error.png');
  } finally {
    await browser.close();
  }
}

main();
