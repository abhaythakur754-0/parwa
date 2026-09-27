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
  console.log('=== PARWA.BUZZ FLEXPAY UI TEST v2 ===\n');
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
    // Step 1: Go to login page
    console.log('📍 Step 1: Navigating to parwa.buzz/login...');
    await page.goto('https://parwa.buzz/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await sleep(2000);
    await screenshot(page, 'v2-01-login-page.png');

    // Step 2: Click "Sign up" link to go to registration
    console.log('📍 Step 2: Clicking Sign up link...');
    const signUpLink = await page.$('a:has-text("Sign up"), a:has-text("sign up"), a:has-text("Register")');
    if (signUpLink) {
      await signUpLink.click();
      console.log('   ✅ Clicked Sign up link');
      await sleep(2000);
    } else {
      // Try direct URL
      console.log('   🔄 Trying direct signup URL...');
      await page.goto('https://parwa.buzz/auth/signup', { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {});
      await sleep(1000);
    }
    
    await screenshot(page, 'v2-02-signup-page.png');

    // Check current URL
    const currentUrl = page.url();
    console.log(`   🔗 Current URL: ${currentUrl}`);

    // Step 3: Fill signup form - look for all input fields
    console.log('📍 Step 3: Filling signup form...');
    
    // Get all input fields
    const inputs = await page.$$('input');
    console.log(`   📝 Found ${inputs.length} input fields`);
    
    for (let i = 0; i < inputs.length; i++) {
      const input = inputs[i];
      const type = await input.getAttribute('type').catch(() => 'text');
      const name = await input.getAttribute('name').catch(() => '');
      const placeholder = await input.getAttribute('placeholder').catch(() => '');
      console.log(`   Input ${i}: type=${type}, name=${name}, placeholder=${placeholder}`);
      
      if (type === 'email' || name?.includes('email') || placeholder?.toLowerCase().includes('email')) {
        await input.fill(testEmail);
        console.log(`   ✅ Filled email: ${testEmail}`);
      } else if (type === 'password' || name?.includes('password') || placeholder?.toLowerCase().includes('password')) {
        await input.fill(testPassword);
        console.log(`   ✅ Filled password`);
      } else if (name?.includes('name') || placeholder?.toLowerCase().includes('name')) {
        await input.fill(testName);
        console.log(`   ✅ Filled name: ${testName}`);
      }
    }

    await screenshot(page, 'v2-03-form-filled.png');

    // Step 4: Submit signup form
    console.log('📍 Step 4: Submitting signup...');
    
    // Find and click submit button
    const submitBtn = await page.$('button[type="submit"], button:has-text("Sign Up"), button:has-text("Create"), button:has-text("Register")');
    if (submitBtn) {
      await submitBtn.click();
      console.log('   ✅ Clicked submit button');
      await sleep(4000);
    } else {
      console.log('   ⚠️ No submit button found, trying Enter key...');
      await page.keyboard.press('Enter');
      await sleep(4000);
    }
    
    await screenshot(page, 'v4-04-after-signup.png');
    
    // Check for error messages
    const pageContent = await page.textContent('body').catch(() => '');
    if (pageContent.includes('Invalid') || pageContent.includes('error') || pageContent.includes('Error')) {
      console.log('   ⚠️ Possible error on page');
    }

    // Step 5: Navigate to billing page (try different approaches)
    console.log('📍 Step 5: Navigating to billing page...');
    
    try {
      await page.goto('https://parwa.buzz/dashboard/billing', { waitUntil: 'load', timeout: 45000 });
      await sleep(3000);
    } catch (e) {
      console.log('   ⚠️ Timeout on billing page, capturing current state...');
    }
    
    await screenshot(page, 'v2-05-billing-page.png', true);
    await screenshot(page, 'v2-05-billing-viewport.png');

    // Step 6: Analyze the page content
    console.log('\n📍 Step 6: Analyzing FlexPay UI elements...');
    
    const bodyText = await page.textContent('body').catch(() => '') || '';
    
    const checks = [
      { name: 'FlexPay/Flex Pay text', test: bodyText.toLowerCase().includes('flexpay') || bodyText.toLowerCase().includes('flex pay') },
      { name: '$100/day or daily limit', test: bodyText.includes('$100') || bodyText.includes('daily') || bodyText.includes('per day') },
      { name: 'Day 1 features', test: bodyText.includes('Day 1') || bodyText.includes('Immediate') },
      { name: 'Day 11 features', test: bodyText.includes('Day 11') || bodyText.includes('SMS') || bodyText.includes('Calling') },
      { name: 'USD pricing ($)', test: bodyText.includes('$999') || bodyText.includes('$2,499') || bodyText.includes('$3,999') },
      { name: 'Subscribe button', test: await page.$('button:has-text("Subscribe"), button:has-text("Get Started")').then(b => !!b).catch(() => false) },
    ];
    
    console.log('\n=== UI VERIFICATION RESULTS ===');
    let passedCount = 0;
    for (const check of checks) {
      const status = check.test ? '✅ PASS' : '❌ FAIL';
      console.log(`${status}: ${check.name}`);
      if (check.test) passedCount++;
    }
    console.log(`\nScore: ${passedCount}/${checks.length} checks passed`);

    // Step 7: Try Subscribe button interaction
    console.log('\n📍 Step 7: Testing Subscribe button...');
    
    const subscribeBtn = await page.$('button:has-text("Subscribe"), button:has-text("Get Started"), button:has-text("Choose Plan")');
    if (subscribeBtn) {
      console.log('   ✅ Found subscribe button, clicking...');
      await subscribeBtn.click();
      await sleep(2500);
      await screenshot(page, 'v2-06-after-subscribe-click.png');
      
      // Look for modal/popup
      const modalVisible = await page.$('[role="dialog"], .modal, [class*="modal-overlay"]').catch(() => null);
      if (modalVisible) {
        await screenshot(page, 'v2-07-modal-opened.png', true);
        console.log('   ✅ Modal/dialog captured!');
        
        // Get modal text
        const modalText = await modalVisible.textContent().catch(() => '');
        if (modalText) {
          console.log('\n=== MODAL CONTENT PREVIEW ===');
          console.log(modalText.substring(0, 500) + (modalText.length > 500 ? '...' : ''));
        }
      }
    } else {
      console.log('   ⚠️ No subscribe button found on page');
      
      // List available buttons
      const buttons = await page.$$('button');
      console.log('\nAvailable buttons:');
      for (const btn of buttons) {
        const text = await btn.textContent().catch(() => '');
        if (text && text.trim()) {
          console.log(`  - "${text.trim()}"`);
        }
      }
    }

    // Save test info
    const reportContent = `
=== PARWA TEST REPORT ===
Generated: ${new Date().toISOString()}
Site: https://parwa.buzz

TEST CREDENTIALS:
Email: ${testEmail}
Password: ${testPassword}

UI CHECKS PASSED: ${passedCount}/${checks.length}
${checks.map(c => `- ${c.name}: ${c.test ? 'PASS' : 'FAIL'}`).join('\n')}

SCREENSHOTS CAPTURED:
- v2-01-login-page.png (Login page)
- v2-02-signup-page.png (Signup page)
- v2-03-form-filled.png (Form with data)
- v4-04-after-signup.png (After submit)
- v2-05-billing-page.png (Billing full page)
- v2-05-billing-viewport.png (Billing viewport)
- v2-06-after-subscribe-click.png (After subscribe click)
- v2-07-modal-opened.png (Confirmation modal)
`.trim();

    fs.writeFileSync(`${DOWNLOAD_DIR}/test-report.txt`, reportContent);
    fs.writeFileSync(`${DOWNLOAD_DIR}/test-credentials.txt`, `Email: ${testEmail}\nPassword: ${testPassword}`);
    
    console.log('\n=== TEST COMPLETE ===');
    console.log(`📄 Report: ${DOWNLOAD_DIR}/test-report.txt`);
    console.log(`🔑 Credentials: ${DOWNLOAD_DIR}/test-credentials.txt`);

  } catch (error) {
    console.error('❌ Error:', error);
    await screenshot(page, 'v2-error-state.png');
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
