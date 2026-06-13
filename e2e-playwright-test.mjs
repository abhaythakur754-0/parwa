#!/usr/bin/env node
/**
 * PARWA End-to-End Playwright Test
 * 
 * Tests the complete flow: Login → Pricing → Onboarding → FirstVictory
 * Starts both backend and frontend servers, then uses Playwright to test.
 * 
 * Usage: node e2e-playwright-test.mjs
 */

import { chromium } from 'playwright';
import { spawn, exec } from 'child_process';
import { createWriteStream, existsSync, mkdirSync } from 'fs';
import { join } from 'path';

const SCREENSHOT_DIR = '/home/z/my-project/download/parwa-proof';
const BACKEND_URL = 'http://localhost:8000';
const FRONTEND_URL = 'http://localhost:3000';

// Ensure screenshot dir exists
if (!existsSync(SCREENSHOT_DIR)) {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

let backendProc = null;
let frontendProc = null;
let browser = null;

function log(msg) {
  const ts = new Date().toISOString().split('T')[1].split('.')[0];
  console.log(`[${ts}] ${msg}`);
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function screenshot(page, name) {
  const path = join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path, fullPage: true });
  log(`📸 Screenshot saved: ${name}.png`);
  return path;
}

async function waitForServer(url, maxWait = 30000) {
  const start = Date.now();
  while (Date.now() - start < maxWait) {
    try {
      const resp = await fetch(url);
      if (resp.status < 500) {
        log(`✅ Server at ${url} is ready (status ${resp.status})`);
        return true;
      }
    } catch (e) {
      // Not ready yet
    }
    await sleep(1000);
  }
  log(`❌ Server at ${url} did not start within ${maxWait}ms`);
  return false;
}

async function killPort(port) {
  return new Promise((resolve) => {
    exec(`fuser -k ${port}/tcp 2>/dev/null || true`, () => {
      resolve();
    });
  });
}

async function startBackend() {
  log('Starting backend server...');
  await killPort(8000);
  await sleep(2);
  
  backendProc = spawn('bash', ['-c', 
    'cd /home/z/my-project/parwa/backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000'
  ], {
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: false,
  });
  
  backendProc.stdout.on('data', (data) => {
    const msg = data.toString().trim();
    if (msg.includes('ERROR') || msg.includes('Traceback')) {
      log(`[BACKEND-ERR] ${msg}`);
    }
  });
  
  backendProc.stderr.on('data', (data) => {
    const msg = data.toString().trim();
    if (msg.includes('ERROR') || msg.includes('Traceback') || msg.includes('error')) {
      log(`[BACKEND-ERR] ${msg}`);
    }
  });
  
  backendProc.on('exit', (code) => {
    log(`Backend process exited with code ${code}`);
  });
  
  const ready = await waitForServer(`${BACKEND_URL}/health`, 30000);
  if (!ready) {
    // Try alternate health path
    const ready2 = await waitForServer(`${BACKEND_URL}/api/health`, 5000);
    return ready2;
  }
  return ready;
}

async function startFrontend() {
  log('Starting frontend server...');
  await killPort(3000);
  await sleep(2);
  
  frontendProc = spawn('npm', ['run', 'dev'], {
    cwd: '/home/z/my-project/parwa',
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: false,
    env: { ...process.env, PORT: '3000' },
  });
  
  frontendProc.stdout.on('data', (data) => {
    const msg = data.toString().trim();
    if (msg.includes('error') || msg.includes('Error')) {
      log(`[FRONTEND-ERR] ${msg}`);
    }
  });
  
  frontendProc.on('exit', (code) => {
    log(`Frontend process exited with code ${code}`);
  });
  
  return await waitForServer(FRONTEND_URL, 60000);
}

async function cleanup() {
  log('Cleaning up...');
  if (browser) await browser.close().catch(() => {});
  if (frontendProc) frontendProc.kill();
  if (backendProc) backendProc.kill();
  await killPort(3000);
  await killPort(8000);
  log('Cleanup done.');
}

async function main() {
  try {
    // ── Step 1: Start Backend ────────────────────────────────
    const backendReady = await startBackend();
    if (!backendReady) {
      log('⚠️  Backend not reachable, but will try to continue (BFF has mock fallbacks)');
    }
    
    // Test backend directly
    try {
      const loginResp = await fetch(`${BACKEND_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Origin': 'http://localhost:3000' },
        body: JSON.stringify({ email: 'test@parwa.buzz', password: 'Test1234!' }),
      });
      log(`Backend login test: ${loginResp.status}`);
      if (loginResp.ok) {
        const data = await loginResp.json();
        log(`Backend login response: ${JSON.stringify(data).slice(0, 200)}`);
      }
    } catch (e) {
      log(`Backend login test failed: ${e.message}`);
    }
    
    // ── Step 2: Start Frontend ───────────────────────────────
    const frontendReady = await startFrontend();
    if (!frontendReady) {
      log('❌ Frontend failed to start. Aborting.');
      await cleanup();
      process.exit(1);
    }
    
    // ── Step 3: Launch Playwright Browser ────────────────────
    log('Launching Playwright browser...');
    browser = await chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
    const context = await browser.newContext({
      viewport: { width: 1280, height: 900 },
    });
    const page = await context.newPage();
    
    // Collect console messages
    const consoleMessages = [];
    page.on('console', msg => {
      if (msg.type() === 'error' || msg.type() === 'warning') {
        consoleMessages.push(`[${msg.type()}] ${msg.text()}`);
      }
    });
    
    // Collect network errors
    const networkErrors = [];
    page.on('requestfailed', req => {
      networkErrors.push(`Failed: ${req.method()} ${req.url()} - ${req.failure()?.errorText}`);
    });
    
    // ── Step 4: Test Login Page ──────────────────────────────
    log('═══════════════════════════════════════════');
    log('TEST 1: Login Page');
    log('═══════════════════════════════════════════');
    
    await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'networkidle', timeout: 30000 });
    await sleep(2000);
    await screenshot(page, '01-login-page');
    
    // Fill login form
    log('Filling login form...');
    const emailInput = await page.$('input[type="email"], input[name="email"], input[placeholder*="email" i]');
    const passwordInput = await page.$('input[type="password"], input[name="password"]');
    
    if (emailInput && passwordInput) {
      await emailInput.fill('test@parwa.buzz');
      await passwordInput.fill('Test1234!');
      await screenshot(page, '02-login-filled');
      
      // Click login button
      const loginBtn = await page.$('button[type="submit"], button:has-text("Sign in"), button:has-text("Login"), button:has-text("Log in")');
      if (loginBtn) {
        log('Clicking login button...');
        await loginBtn.click();
        await sleep(5000);
        await screenshot(page, '03-after-login');
        
        const currentUrl = page.url();
        log(`After login URL: ${currentUrl}`);
      } else {
        log('⚠️  Could not find login button');
      }
    } else {
      log(`⚠️  Could not find email/password inputs. Email: ${!!emailInput}, Password: ${!!passwordInput}`);
      // Let's check what's on the page
      const pageText = await page.textContent('body');
      log(`Page content (first 500 chars): ${pageText?.slice(0, 500)}`);
    }
    
    // ── Step 5: Navigate to Pricing if needed ────────────────
    log('═══════════════════════════════════════════');
    log('TEST 2: Pricing Page');
    log('═══════════════════════════════════════════');
    
    let currentUrl = page.url();
    if (!currentUrl.includes('/pricing')) {
      await page.goto(`${FRONTEND_URL}/pricing`, { waitUntil: 'networkidle', timeout: 30000 });
      await sleep(2000);
    }
    await screenshot(page, '04-pricing-page');
    
    // Select a variant (e.g., PARWA - Growth plan)
    log('Looking for variant selection...');
    const variantButtons = await page.$$('button, a');
    let variantClicked = false;
    for (const btn of variantButtons) {
      const text = await btn.textContent();
      if (text && (text.includes('Get Started') || text.includes('Choose') || text.includes('Select'))) {
        log(`Clicking variant button: "${text.trim().slice(0, 50)}"`);
        await btn.click();
        variantClicked = true;
        await sleep(3000);
        break;
      }
    }
    
    if (!variantClicked) {
      log('⚠️  No variant button found. Trying direct navigation to onboarding...');
      // Set pricing context in localStorage
      await page.evaluate(() => {
        localStorage.setItem('parwa_pricing_context', JSON.stringify({
          industry: 'saas',
          variant: 'parwa',
          variants: ['parwa'],
          totalMonthly: 299,
          timestamp: new Date().toISOString(),
        }));
      });
    }
    
    await screenshot(page, '05-after-variant-selection');
    
    // ── Step 6: Navigate to Onboarding ───────────────────────
    log('═══════════════════════════════════════════');
    log('TEST 3: Onboarding Page');
    log('═══════════════════════════════════════════');
    
    currentUrl = page.url();
    if (!currentUrl.includes('/onboarding')) {
      // Navigate directly to onboarding
      await page.evaluate(() => {
        localStorage.setItem('parwa_pricing_context', JSON.stringify({
          industry: 'saas',
          variant: 'parwa',
          variants: ['parwa'],
          totalMonthly: 299,
          timestamp: new Date().toISOString(),
        }));
      });
      await page.goto(`${FRONTEND_URL}/onboarding?source=pricing&industry=saas`, { 
        waitUntil: 'networkidle', 
        timeout: 30000 
      });
      await sleep(3000);
    }
    await screenshot(page, '06-onboarding-page');
    
    // Check what's displayed
    const onboardingText = await page.textContent('body');
    log(`Onboarding page content (first 500): ${onboardingText?.slice(0, 500)}`);
    
    // ── Step 7: Test Industry/Variant Step (Step 1) ──────────
    log('═══════════════════════════════════════════');
    log('TEST 4: Industry/Variant Selection (Step 1)');
    log('═══════════════════════════════════════════');
    
    // Try to select an industry
    const industryButtons = await page.$$('button, [role="button"], [class*="card"], [class*="option"]');
    for (const btn of industryButtons) {
      const text = await btn.textContent();
      if (text && (text.includes('SaaS') || text.includes('saas'))) {
        log(`Clicking SaaS industry: "${text.trim().slice(0, 50)}"`);
        await btn.click();
        await sleep(1000);
        break;
      }
    }
    await screenshot(page, '07-industry-selected');
    
    // Try to select a variant
    for (const btn of industryButtons) {
      const text = await btn.textContent();
      if (text && (text.includes('PARWA') || text.includes('Growth'))) {
        log(`Clicking PARWA variant: "${text.trim().slice(0, 50)}"`);
        await btn.click();
        await sleep(1000);
        break;
      }
    }
    await screenshot(page, '08-variant-selected');
    
    // Find and click "Continue" or "Next" button
    const continueButtons = await page.$$('button');
    for (const btn of continueButtons) {
      const text = await btn.textContent();
      if (text && (text.includes('Continue') || text.includes('Next') || text.includes('Get Started'))) {
        log(`Clicking continue: "${text.trim().slice(0, 50)}"`);
        await btn.click();
        await sleep(3000);
        break;
      }
    }
    await screenshot(page, '09-step1-completed');
    
    // ── Step 8: Test Legal Compliance (Step 2) ──────────────
    log('═══════════════════════════════════════════');
    log('TEST 5: Legal Compliance (Step 2)');
    log('═══════════════════════════════════════════');
    
    // Check for checkboxes and check them
    const checkboxes = await page.$$('input[type="checkbox"], [role="checkbox"]');
    for (const cb of checkboxes) {
      const isChecked = await cb.isChecked?.() || await cb.getAttribute('aria-checked');
      if (!isChecked || isChecked === 'false') {
        log('Checking a checkbox...');
        await cb.click().catch(() => {});
        await sleep(500);
      }
    }
    await screenshot(page, '10-legal-checkboxes');
    
    // Click continue/accept
    const legalButtons = await page.$$('button');
    for (const btn of legalButtons) {
      const text = await btn.textContent();
      if (text && (text.includes('Accept') || text.includes('Continue') || text.includes('Agree'))) {
        log(`Clicking legal button: "${text.trim().slice(0, 50)}"`);
        await btn.click();
        await sleep(3000);
        break;
      }
    }
    await screenshot(page, '11-step2-completed');
    
    // ── Step 9: Test Integration Setup (Step 3) ────────────
    log('═══════════════════════════════════════════');
    log('TEST 6: Integration Setup (Step 3)');
    log('═══════════════════════════════════════════');
    
    await screenshot(page, '12-integration-step');
    
    // Look for integration options or skip/continue
    const step3Text = await page.textContent('body');
    log(`Step 3 content (first 300): ${step3Text?.slice(0, 300)}`);
    
    const integrationButtons = await page.$$('button');
    for (const btn of integrationButtons) {
      const text = await btn.textContent();
      if (text && (text.includes('Continue') || text.includes('Skip') || text.includes('Next'))) {
        log(`Clicking integration button: "${text.trim().slice(0, 50)}"`);
        await btn.click();
        await sleep(3000);
        break;
      }
    }
    await screenshot(page, '13-step3-completed');
    
    // ── Step 10: Test Knowledge Upload (Step 4) ────────────
    log('═══════════════════════════════════════════');
    log('TEST 7: Knowledge Upload (Step 4)');
    log('═══════════════════════════════════════════');
    
    await screenshot(page, '14-knowledge-upload-step');
    
    const step4Text = await page.textContent('body');
    log(`Step 4 content (first 300): ${step4Text?.slice(0, 300)}`);
    
    // Click continue (skip upload for now)
    const knowledgeButtons = await page.$$('button');
    for (const btn of knowledgeButtons) {
      const text = await btn.textContent();
      if (text && (text.includes('Continue') || text.includes('Skip') || text.includes('Next'))) {
        log(`Clicking knowledge button: "${text.trim().slice(0, 50)}"`);
        await btn.click();
        await sleep(3000);
        break;
      }
    }
    await screenshot(page, '15-step4-completed');
    
    // ── Step 11: Test AI Config (Step 5) ────────────────────
    log('═══════════════════════════════════════════');
    log('TEST 8: AI Config (Step 5)');
    log('═══════════════════════════════════════════');
    
    await screenshot(page, '16-ai-config-step');
    
    const step5Text = await page.textContent('body');
    log(`Step 5 content (first 300): ${step5Text?.slice(0, 300)}`);
    
    // Try to activate AI
    const activateButtons = await page.$$('button');
    for (const btn of activateButtons) {
      const text = await btn.textContent();
      if (text && (text.includes('Activate') || text.includes('Continue'))) {
        log(`Clicking activate button: "${text.trim().slice(0, 50)}"`);
        await btn.click();
        await sleep(3000);
        break;
      }
    }
    await screenshot(page, '17-step5-completed');
    
    // ── Step 12: Test Cost Breakdown (Step 6) ──────────────
    log('═══════════════════════════════════════════');
    log('TEST 9: Cost Breakdown (Step 6)');
    log('═══════════════════════════════════════════');
    
    await screenshot(page, '18-cost-breakdown-step');
    
    const step6Text = await page.textContent('body');
    log(`Step 6 content (first 300): ${step6Text?.slice(0, 300)}`);
    
    // Click continue
    const costButtons = await page.$$('button');
    for (const btn of costButtons) {
      const text = await btn.textContent();
      if (text && (text.includes('Continue') || text.includes('Confirm') || text.includes('Complete'))) {
        log(`Clicking cost button: "${text.trim().slice(0, 50)}"`);
        await btn.click();
        await sleep(3000);
        break;
      }
    }
    await screenshot(page, '19-step6-completed');
    
    // ── Step 13: Test FirstVictory (Step 7) ─────────────────
    log('═══════════════════════════════════════════');
    log('TEST 10: First Victory Dashboard');
    log('═══════════════════════════════════════════');
    
    await screenshot(page, '20-first-victory');
    
    const step7Text = await page.textContent('body');
    log(`First Victory content (first 300): ${step7Text?.slice(0, 300)}`);
    
    // Click "Go to Dashboard"
    const dashboardButtons = await page.$$('button');
    for (const btn of dashboardButtons) {
      const text = await btn.textContent();
      if (text && (text.includes('Dashboard') || text.includes('Go to'))) {
        log(`Clicking dashboard button: "${text.trim().slice(0, 50)}"`);
        await btn.click();
        await sleep(3000);
        break;
      }
    }
    await screenshot(page, '21-dashboard-redirect');
    
    // ── Summary ──────────────────────────────────────────────
    log('═══════════════════════════════════════════');
    log('TEST SUMMARY');
    log('═══════════════════════════════════════════');
    log(`Console errors: ${consoleMessages.length}`);
    consoleMessages.forEach(m => log(`  ${m}`));
    log(`Network errors: ${networkErrors.length}`);
    networkErrors.forEach(e => log(`  ${e}`));
    log(`Final URL: ${page.url()}`);
    log(`Screenshots saved to: ${SCREENSHOT_DIR}`);
    
    // Check if any page showed "something went wrong"
    const bodyText = await page.textContent('body');
    if (bodyText?.includes('something went wrong') || bodyText?.includes('Something went wrong')) {
      log('❌ ERROR: "Something went wrong" message detected on page!');
    } else {
      log('✅ No "Something went wrong" error detected on final page');
    }
    
  } catch (error) {
    log(`❌ Fatal error: ${error.message}`);
    console.error(error);
  } finally {
    await cleanup();
  }
}

main();
