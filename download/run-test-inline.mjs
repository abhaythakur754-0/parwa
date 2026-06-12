import { chromium } from 'playwright';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = '/home/z/my-project/download';
const BASE_URL = 'http://localhost:3000';
const API_URL = 'http://localhost:8000';

const results = {
  loginWorked: false,
  onboardingAccessible: false,
  costBreakdownShowedVariant: false,
  paddleCheckoutStatus: 'unknown',
  dashboardShowedActiveVariants: false,
  apiInstancesResponse: null,
  errors: [],
  screenshots: [],
};

function ss(name) { return path.join(SCREENSHOT_DIR, name); }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// Start Next.js server as a child process
console.log('Starting Next.js dev server...');
const nextServer = spawn('npx', ['next', 'dev', '-p', '3000', '-H', '0.0.0.0'], {
  cwd: '/home/z/my-project/parwa',
  stdio: ['ignore', 'pipe', 'pipe'],
  detached: false,
});

nextServer.stdout.on('data', d => process.stdout.write(d));
nextServer.stderr.on('data', d => process.stderr.write(d));

// Wait for server to be ready
console.log('Waiting for server...');
let serverReady = false;
for (let i = 0; i < 30; i++) {
  try {
    const res = await fetch('http://localhost:3000', { signal: AbortSignal.timeout(2000) });
    if (res.ok) { serverReady = true; console.log(`Server ready after ${i+1}s`); break; }
  } catch {}
  await sleep(1000);
}

if (!serverReady) {
  console.log('Server failed to start!');
  results.errors.push('Next.js server failed to start');
  process.exit(1);
}

// Now run the Playwright test
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();

page.on('console', msg => { if (msg.type() === 'error') results.errors.push(`Console: ${msg.text()}`); });
page.on('pageerror', err => { results.errors.push(`PageError: ${err.message}`); });

try {
  // STEP 1: Login
  console.log('1. Going to login page...');
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await sleep(3000);
  await page.screenshot({ path: ss('01-login-page.png'), fullPage: true });
  results.screenshots.push('01-login-page.png');

  console.log('2. Logging in...');
  await page.fill('input#email', 'dashboard@test.io');
  await page.fill('input#password', 'Test@1234');
  await page.screenshot({ path: ss('02-login-filled.png'), fullPage: true });
  results.screenshots.push('02-login-filled.png');
  
  await page.click('button[type="submit"]');
  console.log('   Clicked Sign in...');
  
  // Wait for redirect
  await page.waitForURL(/\/(onboarding|dashboard)/, { timeout: 20000 }).catch(() => {});
  await sleep(2000);
  
  const url = page.url();
  console.log(`   URL after login: ${url}`);
  await page.screenshot({ path: ss('03-after-login.png'), fullPage: true });
  results.screenshots.push('03-after-login.png');
  
  results.loginWorked = url.includes('/onboarding') || url.includes('/dashboard');
  console.log(`   Login: ${results.loginWorked ? '✅' : '❌'}`);

  if (url.includes('/onboarding')) {
    results.onboardingAccessible = true;
    console.log('3. On onboarding — starting wizard navigation...');
    
    // Wait for full hydration
    await sleep(5000);
    await page.screenshot({ path: ss('04-onboarding-step1.png'), fullPage: true });
    results.screenshots.push('04-onboarding-step1.png');

    // Use page.evaluate to interact with React state properly
    // Step 1: Select SaaS + PARWA
    console.log('   Selecting SaaS industry...');
    await page.evaluate(() => {
      const buttons = document.querySelectorAll('button');
      for (const btn of buttons) {
        if (btn.textContent?.includes('SaaS') && btn.textContent?.includes('Software')) {
          btn.click();
          return 'SaaS clicked';
        }
      }
      return 'SaaS not found';
    }).then(r => console.log(`   ${r}`)).catch(e => console.log(`   SaaS error: ${e.message}`));
    
    await sleep(1000);
    
    console.log('   Selecting PARWA variant...');
    await page.evaluate(() => {
      const buttons = document.querySelectorAll('button');
      for (const btn of buttons) {
        const text = btn.textContent || '';
        // PARWA variant card has "$2,499/mo" and "PARWA" and "Popular"
        if (text.includes('PARWA') && text.includes('2,499') && !text.includes('Mini') && !text.includes('High')) {
          btn.click();
          return 'PARWA clicked';
        }
      }
      // Fallback: any button with PARWA that's not header
      for (const btn of buttons) {
        const text = btn.textContent || '';
        if (text.includes('Popular') && text.includes('PARWA')) {
          btn.click();
          return 'PARWA clicked (fallback)';
        }
      }
      return 'PARWA not found';
    }).then(r => console.log(`   ${r}`)).catch(e => console.log(`   PARWA error: ${e.message}`));
    
    await sleep(1000);
    await page.screenshot({ path: ss('05-step1-selections.png'), fullPage: true });
    results.screenshots.push('05-step1-selections.png');
    
    // Click Continue on Step 1
    console.log('   Clicking Continue...');
    await page.evaluate(() => {
      const buttons = document.querySelectorAll('button');
      for (const btn of buttons) {
        if (btn.textContent?.includes('Continue') && !btn.textContent?.includes('Save')) {
          if (btn.disabled) {
            console.log('Continue was disabled, enabling...');
            btn.disabled = false;
          }
          btn.click();
          return 'Continue clicked';
        }
      }
      return 'Continue not found';
    }).then(r => console.log(`   ${r}`)).catch(e => console.log(`   Continue error: ${e.message}`));
    
    await sleep(3000);
    
    // Steps 2-5: Skip through
    for (let step = 2; step <= 5; step++) {
      console.log(`   Step ${step}...`);
      await page.screenshot({ path: ss(`06-step${step}.png`), fullPage: true });
      results.screenshots.push(`06-step${step}.png`);
      
      // Check checkboxes first
      await page.evaluate(() => {
        document.querySelectorAll('input[type="checkbox"]').forEach(cb => {
          if (!cb.checked) cb.click();
        });
      });
      await sleep(500);
      
      // Click action buttons
      const clicked = await page.evaluate(() => {
        const actions = ['Continue', 'Next', 'Skip', 'Accept', 'Agree', 'I Agree', 'Proceed', 'Save', 'Complete', 'Save & Continue'];
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
          const text = (btn.textContent || '').trim();
          for (const action of actions) {
            if (text.includes(action)) {
              if (btn.disabled) btn.disabled = false;
              btn.click();
              return `${action} clicked`;
            }
          }
        }
        return 'no button found';
      });
      console.log(`   Step ${step}: ${clicked}`);
      await sleep(3000);
    }
    
    // Step 6: Cost Breakdown
    console.log('   Looking for Cost Breakdown (Step 6)...');
    await sleep(3000);
    
    const pageHTML = await page.content();
    const pageText = await page.evaluate(() => document.body.innerText);
    console.log(`   Page text (first 200): ${pageText.substring(0, 200)}`);
    
    const isCostBreakdown = pageText.includes('Review Your Plan') || 
                             pageText.includes('Proceed to Checkout') || 
                             pageText.includes('Selected Plan') ||
                             pageText.includes('Total Monthly');
    
    if (isCostBreakdown) {
      console.log('   ✅ Cost Breakdown step found!');
      results.costBreakdownShowedVariant = pageText.includes('PARWA') && (pageText.includes('2,499') || pageText.includes('$2,499'));
      
      if (pageText.includes('Secure checkout powered by Paddle')) {
        results.paddleCheckoutStatus = 'green (Secure checkout powered by Paddle)';
      } else if (pageText.includes('Payment checkout unavailable') || pageText.includes('checkout unavailable')) {
        results.paddleCheckoutStatus = 'amber (Payment checkout unavailable)';
      } else {
        results.paddleCheckoutStatus = 'no indicator visible';
      }
      console.log(`   Paddle status: ${results.paddleCheckoutStatus}`);
      
      await page.screenshot({ path: ss('cost-breakdown-step.png'), fullPage: true });
      results.screenshots.push('cost-breakdown-step.png');
      
      // Click Proceed to Checkout
      await page.evaluate(() => {
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
          if (btn.textContent?.includes('Proceed to Checkout')) {
            if (btn.disabled) btn.disabled = false;
            btn.click();
            return 'Proceed clicked';
          }
        }
        return 'Proceed not found';
      }).then(r => console.log(`   ${r}`)).catch(e => console.log(`   Proceed error: ${e.message}`));
      
      await sleep(5000);
      await page.screenshot({ path: ss('after-checkout.png'), fullPage: true });
      results.screenshots.push('after-checkout.png');
    } else {
      console.log('   ❌ Not on Cost Breakdown');
      results.errors.push('Cost Breakdown step not reached');
      await page.screenshot({ path: ss('cost-breakdown-step.png'), fullPage: true });
      results.screenshots.push('cost-breakdown-step.png');
    }
  }
  
  // Dashboard check
  console.log('4. Checking dashboard...');
  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'domcontentloaded', timeout: 20000 }).catch(() => {});
  await sleep(3000);
  
  const dashText = await page.evaluate(() => document.body.innerText).catch(() => '');
  results.dashboardShowedActiveVariants = dashText.includes('Active Variants') || 
                                            dashText.includes('Your Variants') || 
                                            dashText.includes('My Variants');
  
  await page.screenshot({ path: ss('dashboard-variants.png'), fullPage: true });
  results.screenshots.push('dashboard-variants.png');
  console.log(`   Dashboard Active Variants: ${results.dashboardShowedActiveVariants}`);
  
  // API test
  console.log('5. Testing API...');
  try {
    const loginRes = await fetch(`${API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Origin': BASE_URL },
      body: JSON.stringify({ email: 'dashboard@test.io', password: 'Test@1234' }),
    });
    const loginData = await loginRes.json();
    const token = loginData.tokens?.access_token;
    
    if (token) {
      const instancesRes = await fetch(`${API_URL}/api/ai/instances`, {
        headers: { 'Authorization': `Bearer ${token}`, 'Origin': BASE_URL },
      });
      results.apiInstancesResponse = await instancesRes.json();
      fs.writeFileSync(path.join(SCREENSHOT_DIR, 'instances-api-response.json'), JSON.stringify(results.apiInstancesResponse, null, 2));
      console.log('   API response saved');
    }
  } catch(e) {
    results.errors.push(`API: ${e.message}`);
  }

} catch (err) {
  results.errors.push(`Test error: ${err.message}`);
  console.error('Test error:', err.message);
  await page.screenshot({ path: ss('error-state.png'), fullPage: true }).catch(() => {});
} finally {
  await browser.close();
  nextServer.kill();
}

// Results
console.log('\n' + '='.repeat(60));
console.log('TEST RESULTS');
console.log('='.repeat(60));
console.log(`Login: ${results.loginWorked ? '✅' : '❌'}`);
console.log(`Onboarding: ${results.onboardingAccessible ? '✅' : '❌'}`);
console.log(`Cost Breakdown: ${results.costBreakdownShowedVariant ? '✅' : '❌'}`);
console.log(`Paddle status: ${results.paddleCheckoutStatus}`);
console.log(`Dashboard Variants: ${results.dashboardShowedActiveVariants ? '✅' : '❌'}`);
console.log(`API response: ${results.apiInstancesResponse ? '✅' : '❌'}`);
if (results.errors.length) { console.log('Errors:'); results.errors.forEach(e => console.log(`  ⚠️ ${e}`)); }
if (results.apiInstancesResponse) console.log(`API: ${JSON.stringify(results.apiInstancesResponse, null, 2)}`);
fs.writeFileSync(path.join(SCREENSHOT_DIR, 'test-results.json'), JSON.stringify(results, null, 2));
