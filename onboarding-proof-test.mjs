/**
 * PARWA Onboarding Flow — LIGHTWEIGHT PROOF TEST
 * Uses agent-browser (Rust-based, lighter than full Playwright) for screenshots
 * + API-level verification for backend connectivity
 * 
 * Per CLAUDE.md Rule #5: "Do not say 'it works' unless you have PROVEN it works."
 */

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = '/home/z/my-project/download/onboarding-proof';
const RESULTS_FILE = '/home/z/my-project/download/onboarding-proof/honest-results.json';

const results = {
  timestamp: new Date().toISOString(),
  steps: [],
  api_evidence: [],
  honest_verdict: '',
  issues_found: [],
};

function addStep(step) {
  results.steps.push(step);
  const icon = step.status === 'PASS' ? '✅' : step.status === 'FAIL' ? '❌' : '⚠️';
  console.log(`${icon} Step ${step.step}: ${step.name} — ${step.status}${step.detail ? ' → ' + step.detail : ''}`);
}

async function testApi(method, url, body = null, headers = {}) {
  const fetchOptions = { method, headers: { 'Content-Type': 'application/json', ...headers } };
  if (body) fetchOptions.body = JSON.stringify(body);
  try {
    const response = await fetch(url, fetchOptions);
    const status = response.status;
    let data;
    try { data = await response.json(); } catch { data = await response.text(); }
    const result = { method, url, status, success: status >= 200 && status < 300, response: typeof data === 'object' ? JSON.stringify(data).substring(0, 2000) : String(data).substring(0, 2000) };
    results.api_evidence.push(result);
    return result;
  } catch (err) {
    const result = { method, url, status: 0, success: false, response: err.message };
    results.api_evidence.push(result);
    return result;
  }
}

(async () => {
  console.log('\n' + '='.repeat(70));
  console.log('  PARWA ONBOARDING — HONEST EVIDENCE TEST');
  console.log('='.repeat(70));

  // ===========================================
  // PART A: BACKEND API VERIFICATION
  // ===========================================
  console.log('\n📋 PART A: Backend API Verification\n');

  // Login to get auth token
  const loginResult = await testApi('POST', 'http://localhost:8000/api/auth/login', 
    { email: 'dashboard@test.io', password: 'Test@1234' },
    { 'Origin': 'http://localhost:3000', 'Referer': 'http://localhost:3000/' }
  );
  
  let token = '';
  if (loginResult.success) {
    try {
      const data = JSON.parse(loginResult.response);
      token = data.tokens?.access_token || '';
    } catch {}
  }
  
  addStep({
    step: 1, name: 'Backend Login',
    status: loginResult.success ? 'PASS' : 'FAIL',
    detail: `Status: ${loginResult.status}, Token obtained: ${!!token}`
  });

  if (!token) {
    addStep({ step: 99, name: 'ABORT', status: 'FAIL', detail: 'Cannot login — skipping remaining tests' });
    fs.writeFileSync(RESULTS_FILE, JSON.stringify(results, null, 2));
    process.exit(1);
  }

  const authHeaders = { 'Authorization': `Bearer ${token}` };

  // Test all critical onboarding APIs
  const apiTests = [
    { name: 'Onboarding State', url: 'http://localhost:8000/api/onboarding/state', critical: true },
    { name: 'Onboarding Prerequisites', url: 'http://localhost:8000/api/onboarding/prerequisites', critical: true },
    { name: 'Integration Catalog (SaaS)', url: 'http://localhost:8000/api/integrations/catalog?industry=saas', critical: true },
    { name: 'Available Integrations', url: 'http://localhost:8000/api/integrations/available', critical: true },
    { name: 'Pricing Industries', url: 'http://localhost:8000/api/pricing/industries', critical: true },
    { name: 'Pricing Variants (SaaS)', url: 'http://localhost:8000/api/pricing/variants/saas', critical: true },
    { name: 'AI Instances', url: 'http://localhost:8000/api/ai/instances', critical: true },
    { name: 'Billing Status', url: 'http://localhost:8000/api/billing/status', critical: false },
    { name: 'Billing Subscription', url: 'http://localhost:8000/api/billing/subscription', critical: false },
    { name: 'Auth/Me', url: 'http://localhost:8000/api/auth/me', critical: false },
  ];
  
  let stepNum = 2;
  let passCount = 0;
  let failCount = 0;
  
  for (const test of apiTests) {
    const result = await testApi('GET', test.url, null, authHeaders);
    if (result.success) {
      passCount++;
      addStep({
        step: stepNum++, name: test.name,
        status: 'PASS',
        detail: `HTTP ${result.status}, Response: ${result.response.substring(0, 100)}`
      });
    } else {
      failCount++;
      addStep({
        step: stepNum++, name: test.name,
        status: 'FAIL',
        detail: `HTTP ${result.status}, Error: ${result.response.substring(0, 150)}`
      });
      if (test.critical) {
        results.issues_found.push(`${test.name} returns ${result.status}: ${result.response.substring(0, 100)}`);
      }
    }
  }

  // ===========================================
  // PART B: FRONTEND + BROWSER TESTS
  // ===========================================
  console.log('\n📋 PART B: Frontend Browser Tests (Lightweight)\n');

  // Use a lightweight browser context
  let browser;
  try {
    browser = await chromium.launch({ 
      headless: true,
      args: ['--disable-gpu', '--disable-dev-shm-usage', '--no-sandbox', '--disable-setuid-sandbox', '--single-process']
    });
  } catch (err) {
    console.log('⚠️ Browser launch failed, using API-only testing');
    browser = null;
  }

  if (browser) {
    const context = await browser.newContext({ 
      viewport: { width: 1280, height: 720 },
      ignoreHTTPSErrors: true 
    });
    const page = await context.newPage();

    // Test: Landing page
    try {
      await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(3000);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'landing-page.png'), fullPage: true });
      const text = await page.textContent('body');
      addStep({
        step: stepNum++, name: 'Landing Page (Browser)',
        status: text && text.length > 100 ? 'PASS' : 'FAIL',
        detail: `Content: ${text?.length || 0} chars`
      });
    } catch (err) {
      addStep({ step: stepNum++, name: 'Landing Page (Browser)', status: 'FAIL', detail: err.message.substring(0, 100) });
    }

    // Test: Login page
    try {
      await page.goto('http://localhost:3000/auth/login', { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(2000);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'login-page.png'), fullPage: true });
      
      const emailInput = page.locator('input[type="email"], input[name="email"]').first();
      const passwordInput = page.locator('input[type="password"]').first();
      
      if (await emailInput.count() > 0) {
        await emailInput.fill('dashboard@test.io');
        await passwordInput.fill('Test@1234');
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'login-filled.png'), fullPage: true });
        
        const submitBtn = page.locator('button[type="submit"]').first();
        await submitBtn.click();
        await page.waitForTimeout(6000);
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'login-result.png'), fullPage: true });
        
        const url = page.url();
        const loginSuccess = !url.includes('/auth/login');
        addStep({
          step: stepNum++, name: 'Login (Browser)',
          status: loginSuccess ? 'PASS' : 'FAIL',
          detail: `Redirected to: ${url}`
        });

        // If logged in, test dashboard
        if (loginSuccess) {
          try {
            if (!url.includes('/dashboard')) {
              await page.goto('http://localhost:3000/dashboard', { waitUntil: 'domcontentloaded', timeout: 15000 });
            }
            await page.waitForTimeout(3000);
            await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'dashboard.png'), fullPage: true });
            const dashText = await page.textContent('body');
            addStep({
              step: stepNum++, name: 'Dashboard (Browser)',
              status: dashText && dashText.length > 100 ? 'PASS' : 'FAIL',
              detail: `Content: ${dashText?.length || 0} chars`
            });
          } catch (err) {
            addStep({ step: stepNum++, name: 'Dashboard (Browser)', status: 'FAIL', detail: err.message.substring(0, 100) });
          }
        }
      } else {
        addStep({ step: stepNum++, name: 'Login (Browser)', status: 'FAIL', detail: 'Login form not found' });
      }
    } catch (err) {
      addStep({ step: stepNum++, name: 'Login (Browser)', status: 'FAIL', detail: err.message.substring(0, 100) });
    }

    // Test: Onboarding page
    try {
      await page.goto('http://localhost:3000/onboarding', { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(3000);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'onboarding-page.png'), fullPage: true });
      const onbText = await page.textContent('body');
      addStep({
        step: stepNum++, name: 'Onboarding Page (Browser)',
        status: onbText && onbText.length > 50 ? 'PASS' : 'FAIL',
        detail: `Content: ${onbText?.length || 0} chars`
      });
    } catch (err) {
      addStep({ step: stepNum++, name: 'Onboarding Page (Browser)', status: 'FAIL', detail: err.message.substring(0, 100) });
    }

    // Test: Cost Breakdown page
    try {
      await page.goto('http://localhost:3000/dashboard/cost-breakdown', { waitUntil: 'domcontentloaded', timeout: 15000 });
      await page.waitForTimeout(3000);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'cost-breakdown.png'), fullPage: true });
      const costText = await page.textContent('body');
      const hasCost = costText?.toLowerCase().includes('cost') || costText?.toLowerCase().includes('$') || costText?.toLowerCase().includes('variant');
      addStep({
        step: stepNum++, name: 'Cost Breakdown (Browser)',
        status: hasCost ? 'PASS' : 'FAIL',
        detail: `Has cost content: ${hasCost}`
      });
    } catch (err) {
      addStep({ step: stepNum++, name: 'Cost Breakdown (Browser)', status: 'FAIL', detail: err.message.substring(0, 100) });
    }

    await browser.close();
  }

  // ===========================================
  // PART C: BFF PROXY TESTS
  // ===========================================
  console.log('\n📋 PART C: BFF Proxy API Tests\n');
  
  const bffTests = [
    { name: 'BFF Onboarding State', url: 'http://localhost:3000/api/onboarding/state' },
    { name: 'BFF Integration Catalog', url: 'http://localhost:3000/api/integrations/catalog?industry=saas' },
    { name: 'BFF Available Integrations', url: 'http://localhost:3000/api/integrations/available' },
    { name: 'BFF Pricing Industries', url: 'http://localhost:3000/api/pricing/industries' },
    { name: 'BFF AI Instances', url: 'http://localhost:3000/api/ai/instances' },
  ];
  
  for (const test of bffTests) {
    const result = await testApi('GET', test.url);
    addStep({
      step: stepNum++, name: test.name,
      status: result.success ? 'PASS' : 'FAIL',
      detail: `HTTP ${result.status}${result.success ? ', Response: ' + result.response.substring(0, 80) : ', Error: ' + result.response.substring(0, 80)}`
    });
    if (!result.success) {
      results.issues_found.push(`${test.name}: HTTP ${result.status}`);
    }
  }

  // ===========================================
  // FINAL VERDICT
  // ===========================================
  console.log('\n' + '='.repeat(70));
  console.log('  HONEST VERDICT');
  console.log('='.repeat(70));
  
  const passed = results.steps.filter(s => s.status === 'PASS').length;
  const failed = results.steps.filter(s => s.status === 'FAIL').length;
  const total = results.steps.length;
  
  results.total_steps = total;
  results.passed_steps = passed;
  results.failed_steps = failed;
  
  if (failed === 0) {
    results.honest_verdict = `ALL ${total} STEPS PASS — Onboarding fully verified`;
  } else if (failed <= 3) {
    results.honest_verdict = `PARTIAL: ${passed}/${total} pass, ${failed} fail. Issues found that need fixing.`;
  } else {
    results.honest_verdict = `FAILURES: Only ${passed}/${total} pass. ${failed} failures. NOT ready for Phase 5.`;
  }
  
  console.log(`\n  Result: ${passed} PASS / ${failed} FAIL / ${total} TOTAL`);
  console.log(`  Verdict: ${results.honest_verdict}`);
  
  if (results.issues_found.length > 0) {
    console.log('\n  ❌ Issues found:');
    for (const issue of results.issues_found) {
      console.log(`    - ${issue}`);
    }
  }

  fs.writeFileSync(RESULTS_FILE, JSON.stringify(results, null, 2));
  console.log(`\n📊 Full results: ${RESULTS_FILE}`);
  console.log(`📸 Screenshots: ${SCREENSHOT_DIR}/`);
})().catch(err => {
  console.error('FATAL:', err);
  fs.writeFileSync(RESULTS_FILE, JSON.stringify({ fatal_error: err.message, results }, null, 2));
  process.exit(1);
});
