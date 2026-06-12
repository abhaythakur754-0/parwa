const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = '/home/z/my-project/download/proof';
const BASE_URL = 'http://localhost:3000';
const API_URL = 'http://localhost:8000';

// Ensure screenshot dir exists
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function screenshot(page, name) {
  const filePath = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: filePath, fullPage: true });
  console.log(`📸 Screenshot saved: ${name}.png`);
  return filePath;
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const context = await browser.newContext({ 
    viewport: { width: 1440, height: 900 },
    ignoreHTTPSErrors: true 
  });
  const page = await context.newPage();

  // Collect console errors
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[${msg.type()}] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[PAGE_ERROR] ${err.message}`));

  const results = {
    login: { status: 'NOT_TESTED', details: '' },
    onboarding_redirect: { status: 'NOT_TESTED', details: '' },
    step1_industry_variant: { status: 'NOT_TESTED', details: '' },
    step2_legal: { status: 'NOT_TESTED', details: '' },
    step3_integrations: { status: 'NOT_TESTED', details: '' },
    step4_knowledge: { status: 'NOT_TESTED', details: '' },
    step5_ai_config: { status: 'NOT_TESTED', details: '' },
    step6_cost_breakdown_paddle: { status: 'NOT_TESTED', details: '' },
    step7_launch: { status: 'NOT_TESTED', details: '' },
    dashboard_after_onboarding: { status: 'NOT_TESTED', details: '' },
    fake_tickets: { status: 'NOT_TESTED', details: '' },
    variant_display: { status: 'NOT_TESTED', details: '' },
    ai_resolution_metrics: { status: 'NOT_TESTED', details: '' }
  };

  try {
    // ============================================
    // STEP 0: Login
    // ============================================
    console.log('\n=== STEP 0: LOGIN ===');
    try {
      await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle', timeout: 15000 });
      await sleep(2000);
      await screenshot(page, '00-login-page');

      // Fill login form
      const emailInput = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first();
      const passwordInput = page.locator('input[type="password"]').first();
      
      if (await emailInput.isVisible()) {
        await emailInput.fill('dashboard@test.io');
        await passwordInput.fill('Test@1234');
        await screenshot(page, '00-login-filled');
        
        // Click login button
        const loginBtn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Login"), button:has-text("Log in")').first();
        await loginBtn.click();
        await sleep(3000);
        await screenshot(page, '00-after-login');
        
        const currentUrl = page.url();
        if (currentUrl.includes('dashboard') || currentUrl.includes('onboarding')) {
          results.login.status = 'PASS';
          results.login.details = `Login successful, redirected to: ${currentUrl}`;
        } else {
          results.login.status = 'PARTIAL';
          results.login.details = `Login form submitted but landed on: ${currentUrl}`;
        }
      } else {
        results.login.status = 'FAIL';
        results.login.details = 'Could not find email input on login page';
      }
    } catch (e) {
      results.login.status = 'FAIL';
      results.login.details = `Error: ${e.message}`;
    }

    // ============================================
    // Check if we're on onboarding
    // ============================================
    console.log('\n=== CHECKING ONBOARDING REDIRECT ===');
    let currentUrl = page.url();
    console.log(`Current URL after login: ${currentUrl}`);
    
    if (!currentUrl.includes('onboarding')) {
      // Try navigating directly
      console.log('Not on onboarding, navigating directly...');
      await page.goto(`${BASE_URL}/onboarding`, { waitUntil: 'networkidle', timeout: 15000 });
      await sleep(2000);
      currentUrl = page.url();
    }

    await screenshot(page, '01-onboarding-initial');
    
    if (currentUrl.includes('onboarding')) {
      results.onboarding_redirect.status = 'PASS';
      results.onboarding_redirect.details = `Onboarding page loaded at: ${currentUrl}`;
    } else {
      results.onboarding_redirect.status = 'FAIL';
      results.onboarding_redirect.details = `Could not reach onboarding page. Current URL: ${currentUrl}`;
    }

    // ============================================
    // STEP 1: Industry & Variant Selection
    // ============================================
    console.log('\n=== STEP 1: INDUSTRY & VARIANT SELECTION ===');
    try {
      await sleep(2000);
      await screenshot(page, '02-step1-industry-variant');

      // Check for industry options
      const industryOptions = page.locator('text=/SaaS|E-commerce|Logistics|Other/i');
      const industryCount = await industryOptions.count();
      console.log(`Found ${industryCount} industry options`);
      
      // Check for variant options
      const variantOptions = page.locator('text=/Mini PARWA|PARWA High|\\$999|\\$2,499|\\$4,999/');
      const variantCount = await variantOptions.count();
      console.log(`Found ${variantCount} variant/price elements`);

      // Select E-commerce industry
      const ecommerceBtn = page.locator('button:has-text("E-commerce"), div:has-text("E-commerce") >> nth=0, [class*="industry"]:has-text("E-commerce") >> nth=0').first();
      if (await ecommerceBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await ecommerceBtn.click();
        await sleep(1000);
        console.log('Selected E-commerce industry');
      } else {
        // Try clicking any industry card
        const firstIndustry = page.locator('[class*="card"], [class*="option"]').filter({ hasText: /SaaS|E-commerce|Logistics/i }).first();
        if (await firstIndustry.isVisible({ timeout: 3000 }).catch(() => false)) {
          await firstIndustry.click();
          await sleep(1000);
          console.log('Selected first available industry');
        }
      }

      await screenshot(page, '02-step1-industry-selected');

      // Select a variant - look for PARWA (growth) or Mini
      const variantBtn = page.locator('button:has-text("PARWA"), [class*="variant"]:has-text("PARWA"), [class*="plan"]:has-text("PARWA")').first();
      if (await variantBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await variantBtn.click();
        await sleep(1000);
        console.log('Selected PARWA variant');
      }

      await screenshot(page, '02-step1-variant-selected');

      // Click Continue/Next
      const continueBtn = page.locator('button:has-text("Continue"), button:has-text("Next"), button:has-text("Proceed")').first();
      if (await continueBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await continueBtn.click();
        await sleep(2000);
      }

      const hasIndustry = industryCount > 0;
      const hasVariants = variantCount > 0;
      
      if (hasIndustry && hasVariants) {
        results.step1_industry_variant.status = 'PASS';
        results.step1_industry_variant.details = `Industry options: ${industryCount}, Variant options: ${variantCount}`;
      } else if (hasIndustry || hasVariants) {
        results.step1_industry_variant.status = 'PARTIAL';
        results.step1_industry_variant.details = `Industry options: ${industryCount}, Variant options: ${variantCount}`;
      } else {
        results.step1_industry_variant.status = 'FAIL';
        results.step1_industry_variant.details = 'No industry or variant options found';
      }
    } catch (e) {
      results.step1_industry_variant.status = 'FAIL';
      results.step1_industry_variant.details = `Error: ${e.message}`;
    }

    // ============================================
    // STEP 2: Legal Compliance
    // ============================================
    console.log('\n=== STEP 2: LEGAL COMPLIANCE ===');
    try {
      await sleep(2000);
      await screenshot(page, '03-step2-legal');

      // Look for legal/consent checkboxes or buttons
      const checkboxes = page.locator('input[type="checkbox"]');
      const checkboxCount = await checkboxes.count();
      console.log(`Found ${checkboxCount} checkboxes`);

      // Check all checkboxes
      for (let i = 0; i < checkboxCount; i++) {
        try {
          await checkboxes.nth(i).check({ timeout: 2000 });
        } catch (e) {
          // Click the label/parent instead
          try {
            await checkboxes.nth(i).click({ force: true });
          } catch (e2) {}
        }
      }

      // Look for "Accept" or "Agree" buttons
      const acceptBtn = page.locator('button:has-text("Accept"), button:has-text("Agree"), button:has-text("I agree")').first();
      if (await acceptBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await acceptBtn.click();
        await sleep(1000);
      }

      await screenshot(page, '03-step2-legal-accepted');

      // Click Continue/Next
      const continueBtn = page.locator('button:has-text("Continue"), button:has-text("Next")').first();
      if (await continueBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await continueBtn.click();
        await sleep(2000);
      }

      // Check if legal terms are visible
      const legalText = page.locator('text=/Terms of Service|Privacy Policy|AI Data Processing/i');
      const legalCount = await legalText.count();

      if (legalCount > 0 || checkboxCount > 0) {
        results.step2_legal.status = 'PASS';
        results.step2_legal.details = `Legal elements found: terms=${legalCount}, checkboxes=${checkboxCount}`;
      } else {
        results.step2_legal.status = 'PARTIAL';
        results.step2_legal.details = 'May have been skipped or auto-accepted';
      }
    } catch (e) {
      results.step2_legal.status = 'FAIL';
      results.step2_legal.details = `Error: ${e.message}`;
    }

    // ============================================
    // STEP 3: Integrations
    // ============================================
    console.log('\n=== STEP 3: INTEGRATIONS ===');
    try {
      await sleep(2000);
      await screenshot(page, '04-step3-integrations');

      // Check for integration options
      const integrationItems = page.locator('text=/HubSpot|Shopify|Slack|Zendesk|Stripe|Salesforce|Mailchimp/i');
      const integrationCount = await integrationItems.count();
      console.log(`Found ${integrationCount} integration mentions`);

      // Look for "Skip" or "Continue" (integrations are optional)
      const skipBtn = page.locator('button:has-text("Skip"), button:has-text("Later")').first();
      const continueBtn = page.locator('button:has-text("Continue"), button:has-text("Next")').first();
      
      if (await skipBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await skipBtn.click();
        console.log('Clicked Skip for integrations');
      } else if (await continueBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await continueBtn.click();
        console.log('Clicked Continue for integrations');
      }

      await sleep(2000);
      await screenshot(page, '04-step3-after-integrations');

      if (integrationCount > 0) {
        results.step3_integrations.status = 'PASS';
        results.step3_integrations.details = `Integration options visible: ${integrationCount} found`;
      } else {
        results.step3_integrations.status = 'PARTIAL';
        results.step3_integrations.details = 'Integration step reached but no integrations visible';
      }
    } catch (e) {
      results.step3_integrations.status = 'FAIL';
      results.step3_integrations.details = `Error: ${e.message}`;
    }

    // ============================================
    // STEP 4: Knowledge Upload
    // ============================================
    console.log('\n=== STEP 4: KNOWLEDGE UPLOAD ===');
    try {
      await sleep(2000);
      await screenshot(page, '05-step4-knowledge');

      // Check for upload area
      const uploadArea = page.locator('text=/upload|drag.*drop|Drop.*files|Knowledge/i');
      const uploadVisible = await uploadArea.count();
      console.log(`Found ${uploadVisible} upload/knowledge elements`);

      // Skip this step (optional)
      const skipBtn = page.locator('button:has-text("Skip"), button:has-text("Later")').first();
      const continueBtn = page.locator('button:has-text("Continue"), button:has-text("Next")').first();
      
      if (await skipBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await skipBtn.click();
      } else if (await continueBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await continueBtn.click();
      }

      await sleep(2000);
      await screenshot(page, '05-step4-after-knowledge');

      if (uploadVisible > 0) {
        results.step4_knowledge.status = 'PASS';
        results.step4_knowledge.details = `Knowledge upload area visible with ${uploadVisible} elements`;
      } else {
        results.step4_knowledge.status = 'PARTIAL';
        results.step4_knowledge.details = 'Knowledge step reached but upload area not clearly visible';
      }
    } catch (e) {
      results.step4_knowledge.status = 'FAIL';
      results.step4_knowledge.details = `Error: ${e.message}`;
    }

    // ============================================
    // STEP 5: AI Configuration
    // ============================================
    console.log('\n=== STEP 5: AI CONFIGURATION ===');
    try {
      await sleep(2000);
      await screenshot(page, '06-step5-ai-config');

      // Check for AI config fields
      const aiNameInput = page.locator('input[name*="name"], input[placeholder*="name" i], input[placeholder*="assistant" i]').first();
      const toneSelector = page.locator('text=/tone|professional|friendly|casual/i');
      const aiConfigElements = page.locator('text=/AI Setup|AI Config|Configure|Assistant Name|Tone/i');
      
      const aiConfigCount = await aiConfigElements.count();
      console.log(`Found ${aiConfigCount} AI config elements`);

      // Fill in AI name if visible
      if (await aiNameInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await aiNameInput.fill('Test Assistant');
      }

      await screenshot(page, '06-step5-ai-config-filled');

      // Click Activate or Continue
      const activateBtn = page.locator('button:has-text("Activate"), button:has-text("Continue"), button:has-text("Next"), button:has-text("Launch")').first();
      if (await activateBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await activateBtn.click();
      }

      await sleep(2000);
      await screenshot(page, '06-step5-after-ai-config');

      if (aiConfigCount > 0) {
        results.step5_ai_config.status = 'PASS';
        results.step5_ai_config.details = `AI config elements found: ${aiConfigCount}`;
      } else {
        results.step5_ai_config.status = 'PARTIAL';
        results.step5_ai_config.details = 'AI config step reached but elements not clearly visible';
      }
    } catch (e) {
      results.step5_ai_config.status = 'FAIL';
      results.step5_ai_config.details = `Error: ${e.message}`;
    }

    // ============================================
    // STEP 6: Cost Breakdown + Paddle Checkout
    // ============================================
    console.log('\n=== STEP 6: COST BREAKDOWN & PADDLE ===');
    try {
      await sleep(2000);
      await screenshot(page, '07-step6-cost-breakdown');

      // Check for cost breakdown elements
      const costElements = page.locator('text=/\\$999|\\$2,499|\\$4,999|Cost|Breakdown|Monthly|Checkout|Paddle/i');
      const costCount = await costElements.count();
      console.log(`Found ${costCount} cost/billing elements`);

      // Check for Paddle checkout button
      const paddleBtn = page.locator('button:has-text("Checkout"), button:has-text("Pay"), button:has-text("Proceed"), button:has-text("Paddle")').first();
      const paddleVisible = await paddleBtn.isVisible({ timeout: 3000 }).catch(() => false);
      console.log(`Paddle checkout button visible: ${paddleVisible}`);

      // Check for Paddle badge/indicator
      const paddleBadge = page.locator('text=/Paddle|Secure checkout|Powered by/i');
      const paddleBadgeCount = await paddleBadge.count();
      console.log(`Paddle badge elements: ${paddleBadgeCount}`);

      await screenshot(page, '07-step6-paddle-checkout');

      // Check variant mixer
      const variantMixer = page.locator('text=/Variant Mixer|Add Variant|Remove Variant|Active Variants/i');
      const mixerCount = await variantMixer.count();
      console.log(`Variant mixer elements: ${mixerCount}`);

      if (costCount > 0 && (paddleVisible || paddleBadgeCount > 0)) {
        results.step6_cost_breakdown_paddle.status = 'PASS';
        results.step6_cost_breakdown_paddle.details = `Cost elements: ${costCount}, Paddle visible: ${paddleVisible}, Paddle badge: ${paddleBadgeCount}, Variant mixer: ${mixerCount}`;
      } else if (costCount > 0) {
        results.step6_cost_breakdown_paddle.status = 'PARTIAL';
        results.step6_cost_breakdown_paddle.details = `Cost elements: ${costCount}, but Paddle checkout NOT visible. Paddle badge: ${paddleBadgeCount}`;
      } else {
        results.step6_cost_breakdown_paddle.status = 'FAIL';
        results.step6_cost_breakdown_paddle.details = 'No cost breakdown or Paddle elements found';
      }

      // Try to proceed without actual payment
      const continueBtn = page.locator('button:has-text("Continue"), button:has-text("Skip"), button:has-text("Proceed")').first();
      if (await continueBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await continueBtn.click();
        await sleep(2000);
      }
    } catch (e) {
      results.step6_cost_breakdown_paddle.status = 'FAIL';
      results.step6_cost_breakdown_paddle.details = `Error: ${e.message}`;
    }

    // ============================================
    // STEP 7: Launch / First Victory
    // ============================================
    console.log('\n=== STEP 7: LAUNCH / FIRST VICTORY ===');
    try {
      await sleep(2000);
      await screenshot(page, '08-step7-launch');

      const celebrationElements = page.locator('text=/Congratulations|Launch|Victory|Welcome|Go to Dashboard|confetti/i');
      const celebrationCount = await celebrationElements.count();
      console.log(`Celebration elements: ${celebrationCount}`);

      if (celebrationCount > 0) {
        results.step7_launch.status = 'PASS';
        results.step7_launch.details = `Launch/celebration visible with ${celebrationCount} elements`;
      } else {
        results.step7_launch.status = 'PARTIAL';
        results.step7_launch.details = 'Step 7 reached but no celebration elements found';
      }

      // Click "Go to Dashboard"
      const dashboardBtn = page.locator('button:has-text("Dashboard"), a:has-text("Dashboard"), button:has-text("Go to")').first();
      if (await dashboardBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await dashboardBtn.click();
        await sleep(3000);
      }
    } catch (e) {
      results.step7_launch.status = 'FAIL';
      results.step7_launch.details = `Error: ${e.message}`;
    }

    // ============================================
    // Dashboard After Onboarding
    // ============================================
    console.log('\n=== DASHBOARD AFTER ONBOARDING ===');
    try {
      await sleep(3000);
      await screenshot(page, '09-dashboard-after-onboarding');

      // Check dashboard URL
      const dashboardUrl = page.url();
      console.log(`Dashboard URL: ${dashboardUrl}`);

      // Check for key dashboard elements
      const variantCards = page.locator('text=/Mini PARWA|PARWA High|Active Variant/i');
      const variantCardCount = await variantCards.count();
      
      const aiMetrics = page.locator('text=/Automation Rate|AI Accuracy|Resolution|AI Resolve/i');
      const aiMetricCount = await aiMetrics.count();

      const ticketElements = page.locator('text=/ticket/i');
      const ticketCount = await ticketElements.count();

      console.log(`Dashboard - Variants: ${variantCardCount}, AI Metrics: ${aiMetricCount}, Tickets: ${ticketCount}`);

      if (dashboardUrl.includes('dashboard')) {
        results.dashboard_after_onboarding.status = 'PASS';
        results.dashboard_after_onboarding.details = `Dashboard loaded. Variant cards: ${variantCardCount}, AI metrics: ${aiMetricCount}, Ticket refs: ${ticketCount}`;
      } else {
        results.dashboard_after_onboarding.status = 'PARTIAL';
        results.dashboard_after_onboarding.details = `Not on dashboard. URL: ${dashboardUrl}`;
      }
    } catch (e) {
      results.dashboard_after_onboarding.status = 'FAIL';
      results.dashboard_after_onboarding.details = `Error: ${e.message}`;
    }

    // ============================================
    // Check Fake Tickets / Ticket Page
    // ============================================
    console.log('\n=== FAKE TICKETS CHECK ===');
    try {
      // Navigate to tickets page
      await page.goto(`${BASE_URL}/dashboard/tickets`, { waitUntil: 'networkidle', timeout: 15000 });
      await sleep(3000);
      await screenshot(page, '10-tickets-page');

      const ticketRows = page.locator('tr, [class*="ticket"], [class*="row"]').filter({ hasText: /TKT|ticket|refund|order|billing/i });
      const ticketRowCount = await ticketRows.count();
      console.log(`Ticket rows found: ${ticketRowCount}`);

      // Check if tickets are from backend or localStorage
      const pageContent = await page.textContent('body');
      const hasFakeTickets = pageContent.includes('refund') || pageContent.includes('billing') || pageContent.includes('order') || pageContent.includes('TKT');
      
      if (ticketRowCount > 0 || hasFakeTickets) {
        results.fake_tickets.status = 'PASS';
        results.fake_tickets.details = `Tickets visible: ${ticketRowCount} rows, has ticket content: ${hasFakeTickets}`;
      } else {
        results.fake_tickets.status = 'FAIL';
        results.fake_tickets.details = 'No tickets visible on tickets page';
      }
    } catch (e) {
      results.fake_tickets.status = 'FAIL';
      results.fake_tickets.details = `Error: ${e.message}`;
    }

    // ============================================
    // Check Variant Display on Dashboard
    // ============================================
    console.log('\n=== VARIANT DISPLAY CHECK ===');
    try {
      await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'networkidle', timeout: 15000 });
      await sleep(3000);
      await screenshot(page, '11-dashboard-variants');

      const pageContent = await page.textContent('body');
      const hasVariantInfo = pageContent.includes('Mini') || pageContent.includes('PARWA') || pageContent.includes('variant') || pageContent.includes('Starter') || pageContent.includes('Growth');
      
      // Also check the variants page
      await page.goto(`${BASE_URL}/dashboard/variants`, { waitUntil: 'networkidle', timeout: 15000 });
      await sleep(3000);
      await screenshot(page, '11-variants-page');

      const variantPageContent = await page.textContent('body');
      const hasVariantPageInfo = variantPageContent.includes('Mini') || variantPageContent.includes('PARWA') || variantPageContent.includes('variant') || variantPageContent.includes('Starter');

      if (hasVariantInfo || hasVariantPageInfo) {
        results.variant_display.status = 'PASS';
        results.variant_display.details = `Dashboard variant info: ${hasVariantInfo}, Variants page info: ${hasVariantPageInfo}`;
      } else {
        results.variant_display.status = 'FAIL';
        results.variant_display.details = 'No variant information visible on dashboard or variants page';
      }
    } catch (e) {
      results.variant_display.status = 'FAIL';
      results.variant_display.details = `Error: ${e.message}`;
    }

    // ============================================
    // Check AI Resolution Metrics
    // ============================================
    console.log('\n=== AI RESOLUTION METRICS CHECK ===');
    try {
      await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'networkidle', timeout: 15000 });
      await sleep(3000);

      const pageContent = await page.textContent('body');
      
      // Check for any AI resolution / automation / human work metrics
      const hasAutomationRate = pageContent.includes('Automation') || pageContent.includes('automation');
      const hasAIResolution = pageContent.includes('AI Resolve') || pageContent.includes('resolution') || pageContent.includes('Resolution');
      const hasAIvsHuman = pageContent.includes('human') || pageContent.includes('Human');
      const hasAccuracy = pageContent.includes('Accuracy') || pageContent.includes('accuracy');
      const has15Percent = pageContent.includes('15%') || pageContent.includes('12%') || pageContent.includes('88%') || pageContent.includes('78%') || pageContent.includes('60%');

      await screenshot(page, '12-ai-resolution-metrics');

      if (hasAutomationRate || hasAIResolution) {
        results.ai_resolution_metrics.status = 'PASS';
        results.ai_resolution_metrics.details = `Automation Rate: ${hasAutomationRate}, AI Resolution: ${hasAIResolution}, AI vs Human: ${hasAIvsHuman}, Accuracy: ${hasAccuracy}, Resolution %: ${has15Percent}`;
      } else {
        results.ai_resolution_metrics.status = 'PARTIAL';
        results.ai_resolution_metrics.details = `Automation: ${hasAutomationRate}, Resolution: ${hasAIResolution}, Human: ${hasAIvsHuman}, Accuracy: ${hasAccuracy}, %: ${has15Percent}`;
      }

      // Also check the backend API directly
      console.log('\n=== BACKEND API CHECKS ===');
      
      // Login via API first to get cookies
      const apiContext = await browser.newContext();
      const apiPage = await apiContext.newPage();
      
      // Login
      const loginResponse = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'dashboard@test.io', password: 'Test@1234' })
      });
      
      if (loginResponse.ok) {
        const loginData = await loginResponse.json();
        console.log(`API Login: ${loginResponse.status}`);
        
        // Check AI instances
        const aiResponse = await fetch(`${API_URL}/api/ai/instances`, {
          headers: { 'Cookie': loginResponse.headers.get('set-cookie') || '' }
        });
        console.log(`AI Instances API: ${aiResponse.status}`);
        
        // Check onboarding state
        const onboardingResponse = await fetch(`${API_URL}/api/onboarding/state`, {
          headers: { 'Cookie': loginResponse.headers.get('set-cookie') || '' }
        });
        console.log(`Onboarding State API: ${onboardingResponse.status}`);
        if (onboardingResponse.ok) {
          const onboardingData = await onboardingResponse.json();
          console.log(`Onboarding state: ${JSON.stringify(onboardingData).substring(0, 200)}`);
        }
      } else {
        console.log(`API Login failed: ${loginResponse.status}`);
      }
    } catch (e) {
      results.ai_resolution_metrics.status = 'FAIL';
      results.ai_resolution_metrics.details = `Error: ${e.message}`;
    }

  } catch (e) {
    console.error('FATAL ERROR:', e.message);
  }

  // Print results
  console.log('\n\n========================================');
  console.log('   ONBOARDING TEST RESULTS - HONEST');
  console.log('========================================');
  for (const [key, result] of Object.entries(results)) {
    const icon = result.status === 'PASS' ? '✅' : result.status === 'PARTIAL' ? '⚠️' : result.status === 'FAIL' ? '❌' : '⬜';
    console.log(`${icon} ${key}: ${result.status}`);
    console.log(`   → ${result.details}`);
  }

  // Save results to file
  const reportPath = path.join(SCREENSHOT_DIR, 'test-results.json');
  fs.writeFileSync(reportPath, JSON.stringify(results, null, 2));
  console.log(`\n📄 Results saved to: ${reportPath}`);

  // Save console errors
  if (errors.length > 0) {
    const errorsPath = path.join(SCREENSHOT_DIR, 'console-errors.json');
    fs.writeFileSync(errorsPath, JSON.stringify(errors.slice(0, 50), null, 2));
    console.log(`🚨 ${errors.length} console errors saved to: ${errorsPath}`);
  }

  await browser.close();
}

main().catch(e => {
  console.error('Fatal:', e);
  process.exit(1);
});
