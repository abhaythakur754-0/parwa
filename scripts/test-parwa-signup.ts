import { chromium, Browser, Page } from 'playwright';
import * as fs from 'fs';

const DOWNLOAD_DIR = '/home/z/my-project/download';

// Generate random test credentials
const timestamp = Date.now();
const testEmail = `flexpaytest${timestamp}@parwa.dev`;
const testPassword = 'TestPass123!@#';
const testName = 'FlexPay Test User';

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
  console.log('=== PARWA.BUZZ FLEXPAY UI TEST ===\n');
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
    // Step 1: Go to signup/login page
    console.log('📍 Step 1: Navigating to parwa.buzz...');
    await page.goto('https://parwa.buzz', { waitUntil: 'networkidle', timeout: 60000 });
    await sleep(2000);
    await screenshot(page, 'test-01-homepage.png');

    // Step 2: Find and click signup link
    console.log('📍 Step 2: Looking for signup option...');
    
    // Try common signup patterns
    const signupLink = await page.$('a[href*="signup"], a[href*="register"], a[href*="sign-up"], button:has-text("Sign Up"), button:has-text("Register")');
    if (signupLink) {
      await signupLink.click();
      await sleep(2000);
    } else {
      // Try navigating directly to signup
      await page.goto('https://parwa.buzz/signup', { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
      await page.goto('https://parwa.buzz/register', { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
    }
    
    await screenshot(page, 'test-02-signup-page.png');
    
    // Step 3: Fill signup form
    console.log('📍 Step 3: Filling signup form...');
    
    // Look for email input
    const emailInput = await page.$('input[type="email"], input[name="email"], input[placeholder*="email" i]');
    if (emailInput) {
      await emailInput.fill(testEmail);
    }
    
    // Look for password input
    const passwordInput = await page.$('input[type="password"], input[name="password"]');
    if (passwordInput) {
      await passwordInput.fill(testPassword);
    }
    
    // Look for name input
    const nameInput = await page.$('input[name="name"], input[name="fullName"], input[placeholder*="name" i]');
    if (nameInput) {
      await nameInput.fill(testName);
    }

    await screenshot(page, 'test-03-form-filled.png');

    // Step 4: Submit signup
    console.log('📍 Step 4: Submitting signup...');
    const submitBtn = await page.$('button[type="submit"], button:has-text("Sign Up"), button:has-text("Register"), button:has-text("Create")');
    if (submitBtn) {
      await submitBtn.click();
      await sleep(3000);
    }
    
    await screenshot(page, 'test-04-after-signup.png');

    // Step 5: Navigate to billing page
    console.log('📍 Step 5: Navigating to billing page...');
    await page.goto('https://parwa.buzz/dashboard/billing', { waitUntil: 'networkidle', timeout: 60000 });
    await sleep(3000);
    
    await screenshot(page, 'test-05-billing-page.png', true);
    await screenshot(page, 'test-05-billing-viewport.png');

    // Step 6: Check for FlexPay info banner
    console.log('📍 Step 6: Checking FlexPay UI elements...');
    
    const hasFlexPayBanner = await page.$('.bg-gradient-to-r, [class*="blue"]').catch(() => null);
    const hasFeatureTimeline = await page.$textContent(/Day 1|Day 11|Immediate/).catch(() => false);
    const hasUsdPricing = await page.$textContent(/\$\d+/).catch(() => false);
    
    console.log('\n=== UI VERIFICATION RESULTS ===');
    console.log(`FlexPay Banner Present: ${!!hasFlexPayBanner}`);
    console.log(`Feature Timeline Present: ${!!hasFeatureTimeline}`);
    console.log(`USD Pricing Present: ${!!hasUsdPricing}`);

    // Step 7: Try clicking Subscribe button
    console.log('\n📍 Step 7: Testing Subscribe flow...');
    const subscribeBtn = await page.$('button:has-text("Subscribe"), button:has-text("Get Started"), button:has-text("Choose")');
    if (subscribeBtn) {
      await subscribeBtn.click();
      await sleep(2000);
      await screenshot(page, 'test-06-after-subscribe-click.png');
      
      // Check for modal/dialog
      const modal = await page.$('[role="dialog"], .modal, [class*="modal"], .fixed.z-50');
      if (modal) {
        await screenshot(page, 'test-07-confirmation-modal.png', true);
        console.log('✅ Confirmation modal captured!');
      }
    } else {
      console.log('⚠️ No subscribe button found');
    }

    // Save test credentials
    fs.writeFileSync(`${DOWNLOAD_DIR}/test-credentials.txt`, `
=== PARWA TEST ACCOUNT CREDENTIALS ===
Email: ${testEmail}
Password: ${testPassword}
Created: ${new Date().toISOString()}
Site: https://parwa.buzz
    `.trim());
    
    console.log('\n=== TEST COMPLETE ===');
    console.log(`📄 Credentials saved to: ${DOWNLOAD_DIR}/test-credentials.txt`);
    console.log(`📧 Email: ${testEmail}`);
    console.log(`🔑 Password: ${testPassword}`);

  } catch (error) {
    console.error('❌ Error:', error);
    await screenshot(page, 'test-error-state.png');
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
