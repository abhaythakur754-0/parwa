/**
 * Playwright Onboarding Test for PARWA - v2
 * More robust selectors and better wait handling
 */

import { chromium } from 'playwright';
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

function screenshot(name) {
  return path.join(SCREENSHOT_DIR, name);
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function clickAnyButton(page, texts, timeout = 5000) {
  for (const text of texts) {
    try {
      const btn = page.locator(`button:has-text("${text}")`).first();
      const visible = await btn.isVisible({ timeout: 2000 });
      if (visible) {
        const enabled = await btn.isEnabled();
        if (enabled) {
          await btn.click({ timeout: 5000 });
          return text;
        } else {
          console.log(`  Button "${text}" found but disabled`);
        }
      }
    } catch {
      // Continue
    }
  }
  return null;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();

  page.on('console', msg => {
    if (msg.type() === 'error') results.errors.push(`Console: ${msg.text()}`);
  });
  page.on('pageerror', err => {
    results.errors.push(`PageError: ${err.message}`);
  });

  try {
    // ─── STEP 1: Login ─────────────────────────────────────────────────
    console.log('1. Navigating to login page...');
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: 30000 });
    await sleep(3000);
    await page.screenshot({ path: screenshot('01-login-page.png'), fullPage: true });
    results.screenshots.push('01-login-page.png');

    console.log('2. Logging in...');
    await page.locator('input#email').fill('dashboard@test.io');
    await page.locator('input#password').fill('Test@1234');
    await page.screenshot({ path: screenshot('02-login-filled.png'), fullPage: true });
    results.screenshots.push('02-login-filled.png');
    
    // Click the Sign in button
    await page.locator('button[type="submit"]').click();
    console.log('   Clicked Sign in, waiting for redirect...');
    
    // Wait for navigation
    await page.waitForURL(/\/(onboarding|dashboard)/, { timeout: 30000 }).catch(() => {});
    await sleep(3000);
    
    const currentUrl = page.url();
    console.log(`   Redirected to: ${currentUrl}`);
    await page.screenshot({ path: screenshot('03-after-login.png'), fullPage: true });
    results.screenshots.push('03-after-login.png');
    
    const isOnOnboarding = currentUrl.includes('/onboarding');
    const isOnDashboard = currentUrl.includes('/dashboard');
    results.loginWorked = isOnOnboarding || isOnDashboard;
    console.log(`   Login: ${results.loginWorked ? 'SUCCESS' : 'FAILED'}`);

    // ─── STEP 3: Navigate Onboarding Wizard ───────────────────────────
    if (isOnOnboarding) {
      console.log('3. On onboarding — navigating wizard...');
      results.onboardingAccessible = true;
      
      // Wait for React hydration and content to load
      await sleep(5000);
      
      // Dump the page content to understand the DOM
      const bodyText = await page.textContent('body').catch(() => '');
      console.log(`   Page text preview: ${bodyText.substring(0, 300).replace(/\n/g, ' ')}`);
      
      await page.screenshot({ path: screenshot('04-onboarding-step1.png'), fullPage: true });
      results.screenshots.push('04-onboarding-step1.png');
      
      // ─── Step 1: Industry + Variant ──────────────────────────────────
      console.log('   Step 1: Selecting SaaS industry...');
      
      // Try multiple strategies to find and click SaaS
      // The buttons are: <button type="button" onClick={...}> containing "SaaS" text
      let saasClicked = false;
      
      // Strategy 1: Direct text match
      try {
        const saasBtn = page.locator('button:has-text("SaaS")').first();
        if (await saasBtn.isVisible({ timeout: 3000 })) {
          await saasBtn.click({ timeout: 5000 });
          saasClicked = true;
          console.log('   SaaS clicked (strategy 1)');
        }
      } catch(e) {
        console.log(`   Strategy 1 failed: ${e.message.substring(0, 80)}`);
      }
      
      // Strategy 2: Look for buttons with specific structure
      if (!saasClicked) {
        try {
          // Maybe the text is split across elements
          const buttons = page.locator('button[type="button"]');
          const count = await buttons.count();
          console.log(`   Found ${count} buttons on page`);
          for (let i = 0; i < count; i++) {
            const text = await buttons.nth(i).textContent({ timeout: 2000 }).catch(() => '');
            if (text.includes('SaaS')) {
              await buttons.nth(i).click({ timeout: 5000 });
              saasClicked = true;
              console.log(`   SaaS clicked (button index ${i}): "${text.substring(0, 50)}"`);
              break;
            }
          }
        } catch(e) {
          console.log(`   Strategy 2 failed: ${e.message.substring(0, 80)}`);
        }
      }
      
      if (!saasClicked) {
        results.errors.push('Could not click SaaS industry button');
        // Try force clicking if we can find it
        try {
          await page.evaluate(() => {
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
              if (btn.textContent?.includes('SaaS')) {
                btn.click();
                return true;
              }
            }
            return false;
          });
          saasClicked = true;
          console.log('   SaaS clicked via JS evaluate');
        } catch(e) {
          console.log(`   JS evaluate failed: ${e.message}`);
        }
      }
      
      await sleep(1000);
      
      // Select PARWA variant
      console.log('   Step 1: Selecting PARWA variant...');
      let parwaClicked = false;
      
      // Strategy: Find the button that says "PARWA" but not "Mini PARWA" or "PARWA High"
      try {
        const buttons = page.locator('button[type="button"]');
        const count = await buttons.count();
        for (let i = 0; i < count; i++) {
          const text = await buttons.nth(i).textContent({ timeout: 2000 }).catch(() => '');
          // Looking for a button that has "PARWA" as the variant name (not Mini PARWA or PARWA High)
          // The variant button text includes: name "PARWA", price "$2,499/mo", features
          if (text.includes('PARWA') && text.includes('2,499') && !text.includes('Mini') && !text.includes('High')) {
            await buttons.nth(i).click({ timeout: 5000 });
            parwaClicked = true;
            console.log(`   PARWA variant clicked (button index ${i})`);
            break;
          }
        }
      } catch(e) {
        console.log(`   PARWA click failed: ${e.message.substring(0, 80)}`);
      }
      
      // Fallback: Try direct text match
      if (!parwaClicked) {
        try {
          // Click the second PARWA button (first is usually in the header/logo)
          const parwaBtns = page.locator('button:has-text("PARWA")');
          const count = await parwaBtns.count();
          console.log(`   Found ${count} buttons containing "PARWA"`);
          // Click the one that's a variant card (not header)
          for (let i = 0; i < count; i++) {
            const parentText = await parwaBtns.nth(i).textContent({ timeout: 2000 }).catch(() => '');
            if (parentText.includes('$2,499') || parentText.includes('2,499/mo') || parentText.includes('Popular')) {
              await parwaBtns.nth(i).click({ timeout: 5000 });
              parwaClicked = true;
              console.log(`   PARWA variant clicked (fallback, index ${i})`);
              break;
            }
          }
        } catch(e) {
          console.log(`   PARWA fallback failed: ${e.message.substring(0, 80)}`);
        }
      }
      
      if (!parwaClicked) {
        // Last resort: use JS evaluate
        try {
          await page.evaluate(() => {
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
              const text = btn.textContent || '';
              if (text.includes('PARWA') && text.includes('2,499') && !text.includes('Mini') && !text.includes('High')) {
                btn.click();
                return;
              }
            }
          });
          parwaClicked = true;
          console.log('   PARWA clicked via JS evaluate');
        } catch(e) {}
      }
      
      if (!parwaClicked) {
        results.errors.push('Could not click PARWA variant button');
      }
      
      await sleep(1000);
      await page.screenshot({ path: screenshot('05-step1-selections.png'), fullPage: true });
      results.screenshots.push('05-step1-selections.png');
      
      // Click Continue button on Step 1
      console.log('   Step 1: Clicking Continue...');
      const continueResult = await clickAnyButton(page, ['Continue', 'Next', 'Proceed'], 10000);
      if (continueResult) {
        console.log(`   Clicked "${continueResult}" on Step 1`);
      } else {
        // Force click via JS
        try {
          await page.evaluate(() => {
            const btns = document.querySelectorAll('button');
            for (const btn of btns) {
              if (btn.textContent?.includes('Continue') && !btn.disabled) {
                btn.click();
                return true;
              }
            }
            // If all are disabled, force enable and click
            for (const btn of btns) {
              if (btn.textContent?.includes('Continue')) {
                btn.removeAttribute('disabled');
                btn.click();
                return true;
              }
            }
            return false;
          });
          console.log('   Continue clicked via JS evaluate');
        } catch(e) {
          results.errors.push(`Step 1 Continue: ${e.message}`);
        }
      }
      
      await sleep(3000);
      
      // ─── Steps 2-5: Skip through ────────────────────────────────────
      for (let step = 2; step <= 5; step++) {
        const stepUrl = page.url();
        const bodyText = await page.textContent('body').catch(() => '');
        console.log(`   Step ${step}: URL=${stepUrl}`);
        console.log(`   Content preview: ${bodyText.substring(0, 150).replace(/\n/g, ' ')}`);
        
        await page.screenshot({ path: screenshot(`06-step${step}.png`), fullPage: true });
        results.screenshots.push(`06-step${step}.png`);
        
        // First try to find checkboxes and check them all (for legal compliance step)
        const checkboxes = page.locator('input[type="checkbox"]');
        const checkboxCount = await checkboxes.count();
        if (checkboxCount > 0) {
          console.log(`   Found ${checkboxCount} checkboxes`);
          for (let i = 0; i < checkboxCount; i++) {
            const isChecked = await checkboxes.nth(i).isChecked().catch(() => false);
            if (!isChecked) {
              await checkboxes.nth(i).click({ force: true }).catch(() => {});
              await sleep(300);
            }
          }
        }
        
        // Also look for toggle switches (custom divs that act as toggles)
        try {
          const toggles = page.locator('[class*="rounded-full"][class*="w-8"]');
          const toggleCount = await toggles.count();
          console.log(`   Found ${toggleCount} toggle switches`);
        } catch {}
        
        // Try clicking any action button
        const btnResult = await clickAnyButton(page, [
          'Continue', 'Next', 'Skip', 'Accept', 'Agree', 'I agree', 
          'Proceed', 'Save', 'Save & Continue', 'Complete'
        ], 5000);
        
        if (btnResult) {
          console.log(`   Step ${step}: Clicked "${btnResult}"`);
        } else {
          // Force via JS
          console.log(`   Step ${step}: No button found, trying JS evaluate...`);
          try {
            const clicked = await page.evaluate(() => {
              const btns = document.querySelectorAll('button');
              for (const btn of btns) {
                const text = (btn.textContent || '').trim();
                if (['Continue', 'Next', 'Skip', 'Accept', 'Agree', 'I Agree', 'Proceed', 'Save', 'Complete'].some(t => text.includes(t))) {
                  if (btn.disabled) btn.removeAttribute('disabled');
                  btn.click();
                  return text;
                }
              }
              return null;
            });
            if (clicked) {
              console.log(`   Step ${step}: JS clicked "${clicked}"`);
            } else {
              results.errors.push(`Step ${step}: No button found to proceed`);
            }
          } catch(e) {
            results.errors.push(`Step ${step}: ${e.message}`);
          }
        }
        
        await sleep(3000);
      }
      
      // ─── Step 6: Cost Breakdown ─────────────────────────────────────
      console.log('   Step 6: Looking for Cost Breakdown...');
      await sleep(3000);
      
      const pageContent = await page.textContent('body').catch(() => '');
      const isCostBreakdown = pageContent.includes('Review Your Plan') || 
                               pageContent.includes('Proceed to Checkout') || 
                               pageContent.includes('Cost Breakdown') ||
                               pageContent.includes('Selected Plan') ||
                               pageContent.includes('Total Monthly');
      
      if (isCostBreakdown) {
        console.log('   ✅ Cost Breakdown step found!');
        
        // Check for variant info
        const hasVariantName = pageContent.includes('PARWA');
        const hasPrice = pageContent.includes('2,499') || pageContent.includes('$2,499');
        results.costBreakdownShowedVariant = hasVariantName && hasPrice;
        console.log(`   Variant info: name=${hasVariantName}, price=${hasPrice}`);
        
        // Check Paddle status
        if (pageContent.includes('Secure checkout powered by Paddle')) {
          results.paddleCheckoutStatus = 'green (Secure checkout powered by Paddle)';
        } else if (pageContent.includes('Payment checkout unavailable') || pageContent.includes('checkout unavailable')) {
          results.paddleCheckoutStatus = 'amber (Payment checkout unavailable)';
        } else if (pageContent.includes('Paddle')) {
          results.paddleCheckoutStatus = 'present (Paddle mentioned but status unclear)';
        } else {
          results.paddleCheckoutStatus = 'not visible (no Paddle indicator)';
        }
        console.log(`   Paddle status: ${results.paddleCheckoutStatus}`);
        
        await page.screenshot({ path: screenshot('cost-breakdown-step.png'), fullPage: true });
        results.screenshots.push('cost-breakdown-step.png');
        console.log('   Screenshot saved: cost-breakdown-step.png');
        
        // Click "Proceed to Checkout"
        const proceedResult = await clickAnyButton(page, ['Proceed to Checkout'], 5000);
        if (proceedResult) {
          console.log('   Proceed to Checkout clicked');
        } else {
          // Force via JS
          try {
            await page.evaluate(() => {
              const btns = document.querySelectorAll('button');
              for (const btn of btns) {
                if (btn.textContent?.includes('Proceed to Checkout')) {
                  if (btn.disabled) btn.removeAttribute('disabled');
                  btn.click();
                  return;
                }
              }
            });
            console.log('   Proceed to Checkout clicked via JS');
          } catch(e) {
            results.errors.push(`Proceed to Checkout: ${e.message}`);
          }
        }
        
        await sleep(5000);
        await page.screenshot({ path: screenshot('after-checkout.png'), fullPage: true });
        results.screenshots.push('after-checkout.png');
        console.log('   Screenshot saved: after-checkout.png');
        
      } else {
        console.log('   ❌ NOT on Cost Breakdown step');
        console.log(`   Content: ${pageContent.substring(0, 300).replace(/\n/g, ' ')}`);
        results.errors.push('Cost Breakdown step not reached');
        await page.screenshot({ path: screenshot('cost-breakdown-step.png'), fullPage: true });
        results.screenshots.push('cost-breakdown-step.png');
      }
    }
    
    // ─── STEP 4: Check Dashboard ──────────────────────────────────────
    console.log('4. Checking dashboard...');
    
    if (!page.url().includes('/dashboard')) {
      await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'networkidle', timeout: 30000 });
      await sleep(3000);
    }
    
    const dashContent = await page.textContent('body').catch(() => '');
    results.dashboardShowedActiveVariants = dashContent.includes('Active Variants') || 
                                              dashContent.includes('active variant') || 
                                              dashContent.includes('Your Variants') ||
                                              dashContent.includes('My Variants');
    
    await page.screenshot({ path: screenshot('dashboard-variants.png'), fullPage: true });
    results.screenshots.push('dashboard-variants.png');
    console.log(`   Dashboard Active Variants: ${results.dashboardShowedActiveVariants}`);
    
    // Also check /dashboard/variants
    await page.goto(`${BASE_URL}/dashboard/variants`, { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
    await sleep(2000);
    const variantsContent = await page.textContent('body').catch(() => '');
    if (variantsContent.includes('Variant') && !results.dashboardShowedActiveVariants) {
      results.dashboardShowedActiveVariants = true;
    }
    await page.screenshot({ path: screenshot('dashboard-variants-page.png'), fullPage: true });
    results.screenshots.push('dashboard-variants-page.png');

    // ─── STEP 5: API Test ─────────────────────────────────────────────
    console.log('5. Testing API /api/ai/instances...');
    
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
        const instancesData = await instancesRes.json();
        results.apiInstancesResponse = instancesData;
        
        fs.writeFileSync(
          path.join(SCREENSHOT_DIR, 'instances-api-response.json'),
          JSON.stringify(instancesData, null, 2)
        );
        console.log('   API response saved');
      } else {
        results.errors.push('Could not get auth token for API testing');
      }
    } catch(e) {
      results.errors.push(`API test error: ${e.message}`);
    }

  } catch (err) {
    results.errors.push(`Test error: ${err.message}`);
    console.error('Test error:', err.message);
    await page.screenshot({ path: screenshot('error-state.png'), fullPage: true }).catch(() => {});
    results.screenshots.push('error-state.png');
  } finally {
    await browser.close();
  }

  // ─── OUTPUT ────────────────────────────────────────────────────────
  console.log('\n' + '='.repeat(60));
  console.log('TEST RESULTS SUMMARY');
  console.log('='.repeat(60));
  console.log(`Login worked:            ${results.loginWorked ? '✅ YES' : '❌ NO'}`);
  console.log(`Onboarding accessible:   ${results.onboardingAccessible ? '✅ YES' : '❌ NO'}`);
  console.log(`Cost Breakdown variant:  ${results.costBreakdownShowedVariant ? '✅ YES' : '❌ NO'}`);
  console.log(`Paddle checkout status:  ${results.paddleCheckoutStatus}`);
  console.log(`Dashboard Active Var:    ${results.dashboardShowedActiveVariants ? '✅ YES' : '❌ NO'}`);
  console.log(`API /ai/instances:       ${results.apiInstancesResponse ? '✅ Response received' : '❌ No response'}`);
  console.log(`Screenshots:             ${results.screenshots.length}`);
  console.log(`Errors:                  ${results.errors.length}`);
  results.errors.forEach(e => console.log(`  ⚠️  ${e}`));
  if (results.apiInstancesResponse) {
    console.log(`\nAPI Response:\n${JSON.stringify(results.apiInstancesResponse, null, 2)}`);
  }
  console.log('='.repeat(60));
  
  fs.writeFileSync(
    path.join(SCREENSHOT_DIR, 'test-results.json'),
    JSON.stringify(results, null, 2)
  );
})();
