import { chromium, Browser, Page } from 'playwright';
import * as fs from 'fs';

const DOWNLOAD_DIR = '/home/z/my-project/download';

// Generate random test credentials
const timestamp = Date.now();
const testEmail = `flexpaytest${timestamp}@parwa.dev`;
const testPassword = 'TestPass123!@#';
const testName = 'FlexPay Test';

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
  console.log('=== PARWA.BUZZ FLEXPAY UI TEST v3 ===\n');
  console.log(`📧 Test Email: ${testEmail}`);
  console.log(`🔑 Test Password: ${testPassword}\n`);

  const browser: Browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    locale: 'en-US'
  });
  
  const page: Page = await context.newPage();

  try {
    // Step 1: Try multiple possible signup URLs
    console.log('📍 Step 1: Finding signup page...');
    
    const signupUrls = [
      'https://parwa.buzz/auth/signup',
      'https://parwa.buzz/register',
      'https://parwa.buzz/sign-up',
      'https://parwa.buzz/api/auth/signup',
    ];
    
    let signupPageFound = false;
    
    for (const url of signupUrls) {
      console.log(`   🔄 Trying: ${url}`);
      try {
        const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
        await sleep(1000);
        const currentUrl = page.url();
        const pageTitle = await page.title();
        const bodyText = await page.textContent('body').catch(() => '') || '';
        
        console.log(`   → Landed on: ${currentUrl}`);
        console.log(`   → Title: ${pageTitle}`);
        
        // Check if this is actually a signup page (not login)
        const isSignup = bodyText.includes('Sign up') || bodyText.includes('Create account') || 
                        bodyText.includes('Register') || bodyText.includes('Create your');
        const isLogin = bodyText.includes('Welcome back') || bodyText.includes('Sign in to');
        
        console.log(`   → Is Signup?: ${isSignup}, Is Login?: ${isLogin}`);
        
        // Check for password confirmation field (signup specific)
        const inputs = await page.$$('input');
        const inputCount = inputs.length;
        console.log(`   → Input count: ${inputCount}`);
        
        await screenshot(page, `v3-01-url-${url.split('/').pop() || 'home'}.png`);
        
        if ((isSignup && !isLogin) || inputCount > 2) {
          signupPageFound = true;
          console.log(`   ✅ Found signup page at: ${url}`);
          break;
        }
      } catch (e) {
        console.log(`   ⚠️ Failed: ${(e as Error).message.substring(0, 50)}`);
      }
    }
    
    if (!signupPageFound) {
      console.log('\n   🔄 Trying click-based approach on login page...');
      await page.goto('https://parwa.buzz/login', { waitUntil: 'domcontentloaded', timeout: 20000 });
      await sleep(1500);
      
      // Click Sign up link and wait for navigation
      const [newPage] = await Promise.all([
        context.waitForEvent('page', { timeout: 10000 }).catch(() => null),
        page.click('a:has-text("Sign up")').catch(() => null)
      ]);
      
      if (newPage) {
        await newPage.waitForLoadState('domcontentloaded').catch(() => {});
        await sleep(1000);
        console.log(`   ✅ New page opened: ${newPage.url()}`);
        await screenshot(newPage, 'v3-02-signup-new-tab.png');
      } else {
        // Maybe same-page navigation
        await sleep(2000);
        console.log(`   → Current URL after click: ${page.url()}`);
        await screenshot(page, 'v3-02-after-click.png');
      }
    }

    // Step 2: Check what we have now and fill form
    console.log('\n📍 Step 2: Analyzing current page...');
    const currentUrl = page.url();
    const bodyText = await page.textContent('body').catch(() => '') || '';
    
    // Get all input details
    const inputs = await page.$$('input');
    console.log(`   Current URL: ${currentUrl}`);
    console.log(`   Input fields found: ${inputs.length}`);
    
    for (let i = 0; i < inputs.length; i++) {
      const input = inputs[i];
      const type = await input.getAttribute('type').catch(() => 'text');
      const name = await input.getAttribute('name').catch(() => '');
      const placeholder = await input.getAttribute('placeholder').catch(() => '');
      console.log(`   [${i}] type=${type} name="${name}" placeholder="${placeholder}"`);
    }

    // Fill based on field types
    let filledEmail = false;
    let filledPassword = false;
    let filledName = false;
    let filledConfirmPassword = false;

    for (const input of inputs) {
      const type = await input.getAttribute('type').catch(() => 'text');
      const name = await input.getAttribute('name').catch(() => '').toLowerCase();
      const placeholder = await input.getAttribute('placeholder').catch(() => '').toLowerCase();

      if (type === 'email' || name.includes('email') || placeholder.includes('email')) {
        await input.fill(testEmail);
        filledEmail = true;
        console.log(`   ✅ Filled email`);
      } else if (type === 'password' && !filledPassword) {
        await input.fill(testPassword);
        filledPassword = true;
        console.log(`   ✅ Filled password`);
      } else if (type === 'password' && filledPassword && !filledConfirmPassword) {
        // This would be confirm password field
        await input.fill(testPassword);
        filledConfirmPassword = true;
        console.log(`   ✅ Filled confirm password`);
      } else if (name.includes('name') || placeholder.includes('name')) {
        await input.fill(testName);
        filledName = true;
        console.log(`   ✅ Filled name`);
      }
    }

    await screenshot(page, 'v3-03-form-filled.png');

    // Step 3: Submit
    console.log('\n📍 Step 3: Submitting form...');
    
    // Find all buttons
    const buttons = await page.$$('button');
    console.log(`   Buttons found: ${buttons.length}`);
    
    for (let i = 0; i < buttons.length; i++) {
      const btn = buttons[i];
      const text = await btn.textContent().catch(() => '');
      const type = await btn.getAttribute('type').catch(() => '');
      console.log(`   [${i}] "${text?.trim()}" type=${type}`);
      
      // Click submit-like buttons (but not Google/SSO)
      if (text && (text.toLowerCase().includes('sign up') || 
                   text.toLowerCase().includes('create') ||
                   text.toLowerCase().includes('register') ||
                   type === 'submit') &&
                  !text.toLowerCase().includes('google')) {
        console.log(`   ✅ Clicking: "${text.trim()}"`);
        await btn.click();
        break;
      }
    }
    
    await sleep(4000);
    await screenshot(page, 'v3-04-after-submit.png');
    
    // Check result
    const afterSubmitText = await page.textContent('body').catch(() => '') || '';
    const afterUrl = page.url();
    console.log(`   URL after submit: ${afterUrl}`);
    
    if (afterSubmitText.includes('Invalid') || afterSubmitText.includes('error')) {
      console.log('   ⚠️ Form submission may have failed');
    } else if (afterUrl.includes('/dashboard') || afterUrl.includes('/home')) {
      console.log('   ✅ Successfully redirected to dashboard!');
    }

    // Step 4: Navigate to billing
    console.log('\n📍 Step 4: Going to billing page...');
    try {
      await page.goto('https://parwa.buzz/dashboard/billing', { waitUntil: 'load', timeout: 50000 });
    } catch (e) {
      console.log('   ⚠️ Timeout, capturing anyway...');
    }
    await sleep(3000);
    
    await screenshot(page, 'v3-05-billing-full.png', true);
    await screenshot(page, 'v3-05-billing-viewport.png');

    // Final analysis
    console.log('\n=== FINAL PAGE ANALYSIS ===');
    const finalBody = await page.textContent('body').catch(() => '') || '';
    const finalUrl = page.url();
    console.log(`Final URL: ${finalUrl}`);
    
    // Look for key FlexPay elements
    const keywords = ['FlexPay', '$100', 'Day 1', 'Day 11', 'SMS', 'Calling', 'Ticket Management', 
                      '$999', '$2,499', '$3,999', 'Subscribe', 'Installment'];
    
    console.log('\nKeyword search:');
    for (const kw of keywords) {
      const found = finalBody.includes(kw);
      console.log(`  ${found ? '✅' : '❌'} "${kw}"`);
    }

    // Save everything
    fs.writeFileSync(`${DOWNLOAD_DIR}/test-credentials.txt`, 
      `Email: ${testEmail}\nPassword: ${testPassword}\nCreated: ${new Date().toISOString()}`
    );
    
    console.log('\n=== DONE ===');
    console.log(`Credentials saved to test-credentials.txt`);

  } catch (error) {
    console.error('❌ Error:', error);
    await screenshot(page, 'v3-error.png');
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
