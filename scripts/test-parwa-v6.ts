import { chromium, Browser, Page } from 'playwright';
import * as fs from 'fs';

const DOWNLOAD_DIR = '/home/z/my-project/download';

const timestamp = Date.now();
const testEmail = `flexpaytest${timestamp}@parwa.dev`;
const testPassword = 'TestPass1234!';

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
  console.log('=== PARWA FLEXPAY UI TEST (AUTH FIX) ===\n');
  console.log(`📧 New Email: ${testEmail}`);

  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
  });
  
  const page = await context.newPage();

  // Capture API responses
  const apiResponses: { url: string; status: number; body: string }[] = [];
  page.on('response', async response => {
    const url = response.url();
    if (url.includes('/api/auth/')) {
      try {
        const body = await response.text().catch(() => '');
        apiResponses.push({ url: url.split('?')[0], status: response.status(), body: body.substring(0, 300) });
      } catch {}
    }
  });

  try {
    // Step 1: Go to site first (establish origin)
    console.log('📍 Step 1: Navigating to parwa.buzz...');
    await page.goto('https://parwa.buzz', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await sleep(1000);

    // Step 2: Register via fetch (same-origin)
    console.log('\n📍 Step 2: Registering new account...');
    
    const registerResult = await page.evaluate(async ({ email, password }) => {
      try {
        const res = await fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email,
            password,
            confirmPassword: password,
            fullName: 'FlexPay Test User',
            companyName: 'Test Company'
          })
        });
        const data = await res.json();
        return { ok: res.ok, status: res.status, data };
      } catch (e) {
        return { ok: false, error: String(e) };
      }
    }, { email: testEmail, password: testPassword });

    console.log(`   Register result: ${JSON.stringify(registerResult).substring(0, 200)}`);

    // Check if we got cookies set
    const cookies = await context.cookies();
    const authCookies = cookies.filter(c => c.name.includes('token') || c.name.includes('auth') || c.name.includes('session'));
    console.log(`   Auth cookies after register: ${authCookies.map(c => c.name).join(', ') || 'none'}`);

    // Step 3: If registration worked, try to verify email or just proceed
    if (registerResult.ok || registerResult.status === 200 || registerResult.status === 201) {
      console.log('\n📍 Step 3a: Registration successful, checking if auto-logged-in...');
      
      // Check current state
      await sleep(1000);
      let currentUrl = page.url();
      console.log(`   Current URL: ${currentUrl}`);
      
      // Try going to dashboard directly
      await page.goto('https://parwa.buzz/dashboard/billing', { 
        waitUntil: 'domcontentloaded', 
        timeout: 45000 
      }).catch(() => {});
      
      await sleep(5000); // Wait for content to load
      await screenshot(page, 'v6-01-after-register-billing.png', true);
      
      currentUrl = page.url();
      const bodyText = await page.textContent('body').catch(() => '') || '';
      console.log(`   URL after billing attempt: ${currentUrl}`);
      console.log(`   On login page?: ${bodyText.includes('Welcome back')}`);
      console.log(`   Has billing content?: ${bodyText.includes('Billing') && !bodyText.includes('Welcome back')}`);
      
      // If redirected to login, need to actually login
      if (bodyText.includes('Welcome back')) {
        console.log('\n📍 Step 3b: Need to login manually...');
        
        // Try login now
        await page.goto('https://parwa.buzz/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await sleep(1000);
        
        await page.fill('input[name="email"]', testEmail);
        await page.fill('input[name="password"]', testPassword);
        
        // Click sign in and capture what happens
        const [response] = await Promise.all([
          page.waitForResponse(res => res.url().includes('/api/auth/login'), { timeout: 10000 }).catch(() => null),
          page.click('button[type="submit"]')
        ]).catch(() => [null]);
        
        await sleep(4000);
        
        if (response) {
          const loginData = await response.json().catch(() => ({}));
          console.log(`   Login API response: ${JSON.stringify(loginData).substring(0, 200)}`);
        }
        
        await screenshot(page, 'v6-02-after-login-attempt.png');
        
        // Check URL again
        currentUrl = page.url();
        console.log(`   URL after login: ${currentUrl}`);
        
        // Check for errors on page
        const errorEl = await page.$('.text-red-500, .text-red-600, [class*="error"]').catch(() => null);
        if (errorEl) {
          const errorText = await errorEl.textContent().catch(() => '');
          console.log(`   Error shown: ${errorText}`);
        }
      }
    } else {
      console.log(`\n⚠️ Registration failed: ${registerResult.data?.message || registerResult.error}`);
    }

    // Step 4: Final billing page capture
    console.log('\n📍 Step 4: Final billing page capture...');
    
    // Try navigating to billing one more time
    try {
      await page.goto('https://parwa.buzz/dashboard/billing', { 
        waitUntil: 'load', 
        timeout: 60000 
      });
    } catch (e) {
      console.log('   Timeout on billing, capturing anyway...');
    }
    
    // Wait extra long for any dynamic content
    console.log('   Waiting up to 20s for content...');
    for (let i = 0; i < 20; i++) {
      await sleep(1000);
      const text = await page.textContent('body').catch(() => '') || '';
      const hasRealContent = text.includes('$') || text.includes('Subscribe') || text.includes('FlexPay');
      const notLoginPage = !text.includes('Welcome back') || !text.includes('Sign in to your account');
      
      if (hasRealContent && notLoginPage) {
        console.log(`   ✅ Real content loaded after ${i+1}s`);
        break;
      }
      
      if (i === 19) {
        console.log('   ⚠️ Timeout waiting for content');
      }
    }
    
    await screenshot(page, 'v6-03-billing-final.png', true);
    await screenshot(page, 'v6-03-billing-viewport.png');

    // Analysis
    console.log('\n========== FINAL ANALYSIS ==========');
    const finalUrl = page.url();
    const finalBody = await page.textContent('body').catch(() => '') || '';
    
    console.log(`URL: ${finalUrl}`);
    console.log(`Page length: ${finalBody.length} chars`);
    
    // Key terms check
    const terms = [
      ['FlexPay Banner', ['FlexPay', '$100', 'daily']],
      ['Day 1 Features', ['Day 1', 'Immediate', 'Ticket Management']],
      ['Day 11 Features', ['Day 11', 'SMS', 'Calling']],
      ['Pricing ($)', ['$', '999', '2499', '3999']],
      ['Subscribe Button', ['Subscribe', 'Get Started']],
      ['USD Note', ['USD', 'US Dollar']]
    ];
    
    console.log('\nUI Elements:');
    for (const [name, keywords] of terms) {
      const found = keywords.some(k => finalBody.includes(k));
      console.log(`${found ? '✅' : '❌'} ${name}`);
    }

    // Print first part of body text for debugging
    if (finalBody.length > 0) {
      console.log('\n--- PAGE TEXT PREVIEW ---');
      console.log(finalBody.substring(0, 1500));
    }

    // Save credentials
    fs.writeFileSync(`${DOWNLOAD_DIR}/test-credentials.txt`,
`Email: ${testEmail}
Password: ${testPassword}
Created: ${new Date().toISOString()}
Final URL: ${finalUrl}`
    );

    console.log('\n✅ TEST COMPLETE');

  } catch (error) {
    console.error('❌ Error:', error);
    await screenshot(page, 'v6-error.png');
  } finally {
    await browser.close();
  }
}

main();
