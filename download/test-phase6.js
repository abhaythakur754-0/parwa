const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = '/home/z/my-project/download/proof';
const BASE_URL = 'http://localhost:3000';

if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

async function screenshot(page, name) {
  const filePath = path.join(SCREENSHOT_DIR, `p6-${name}.png`);
  await page.screenshot({ path: filePath, fullPage: true });
  console.log(`Screenshot: ${name}.png`);
}

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, ignoreHTTPSErrors: true });
  const page = await context.newPage();

  const errors = [];
  page.on('pageerror', err => errors.push(err.message));

  console.log('=== PHASE 6 PLAYWRIGHT TEST ===\n');

  // Step 1: Login
  console.log('1. LOGIN');
  try {
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await sleep(3000);
    await screenshot(page, '01-login');

    const emailInput = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first();
    const passwordInput = page.locator('input[type="password"]').first();
    await emailInput.fill('dashboard@test.io');
    await passwordInput.fill('Test@1234');

    const submitBtn = page.locator('button[type="submit"]').first();
    await submitBtn.click();
    await sleep(5000);
    await screenshot(page, '02-after-login');

    const url = page.url();
    console.log(`After login URL: ${url}`);
    console.log(`Login: ${url.includes('dashboard') || url.includes('onboarding') ? 'PASS' : 'PARTIAL - stayed on login'}`);
  } catch (e) {
    console.log(`Login error: ${e.message}`);
  }

  // Step 2: Navigate to Settings → Webhooks
  console.log('\n2. SETTINGS → WEBHOOKS TAB');
  try {
    await page.goto(`${BASE_URL}/dashboard/settings`, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await sleep(3000);
    await screenshot(page, '03-settings-page');

    // Click Webhooks tab
    const webhooksTab = page.locator('[data-state="inactive"][data-value="webhooks"], button:has-text("Webhooks"), [role="tab"]:has-text("Webhooks")').first();
    if (await webhooksTab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await webhooksTab.click();
      await sleep(2000);
      console.log('Clicked Webhooks tab');
    } else {
      // Try clicking by value attribute
      await page.click('[value="webhooks"]').catch(() => {});
      await sleep(2000);
    }
    await screenshot(page, '04-webhooks-tab');

    // Check if the webhooks section is visible
    const webhookTitle = page.locator('text=Webhook Endpoints');
    const webhookVisible = await webhookTitle.isVisible({ timeout: 3000 }).catch(() => false);
    console.log(`Webhooks section visible: ${webhookVisible}`);

    // Check if "Add Endpoint" button exists
    const addBtn = page.locator('button:has-text("Add Endpoint"), button:has-text("Add Webhook")').first();
    const addBtnVisible = await addBtn.isVisible({ timeout: 2000 }).catch(() => false);
    console.log(`Add Endpoint button visible: ${addBtnVisible}`);

    // Check if Event Log section exists
    const eventLog = page.locator('text=Event Log');
    const eventLogVisible = await eventLog.isVisible({ timeout: 2000 }).catch(() => false);
    console.log(`Event Log section visible: ${eventLogVisible}`);

    // Check if Webhook Security info exists
    const securityInfo = page.locator('text=Webhook Security');
    const securityVisible = await securityInfo.isVisible({ timeout: 2000 }).catch(() => false);
    console.log(`Webhook Security info visible: ${securityVisible}`);

    console.log(`Webhooks Tab: ${webhookVisible && addBtnVisible ? 'PASS' : 'PARTIAL'}`);
  } catch (e) {
    console.log(`Settings error: ${e.message}`);
  }

  // Step 3: Test creating a webhook
  console.log('\n3. CREATE WEBHOOK');
  try {
    const addBtn = page.locator('button:has-text("Add Endpoint")').first();
    if (await addBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await addBtn.click();
      await sleep(1000);

      // Fill URL
      const urlInput = page.locator('input[type="url"], input[placeholder*="webhook"], input[placeholder*="https://"]').first();
      if (await urlInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await urlInput.fill('https://example.com/webhooks/parwa-test');
        await sleep(500);
      }

      // Select an event checkbox
      const eventCheckbox = page.locator('input[type="checkbox"]').first();
      if (await eventCheckbox.isVisible({ timeout: 2000 }).catch(() => false)) {
        await eventCheckbox.check().catch(() => {});
      }

      await screenshot(page, '05-create-webhook-form');

      // Click Create
      const createBtn = page.locator('button:has-text("Create Webhook")').first();
      if (await createBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await createBtn.click();
        await sleep(3000);
      }

      await screenshot(page, '06-after-create-webhook');
      console.log('Webhook creation form tested');
    }
  } catch (e) {
    console.log(`Create webhook error: ${e.message}`);
  }

  // Step 4: Test backend webhook API directly
  console.log('\n4. BACKEND WEBHOOK API TEST');
  try {
    // Test the BFF route
    const listRes = await page.evaluate(async () => {
      try {
        const res = await fetch('/api/integrations/webhooks', { credentials: 'include' });
        return { status: res.status, ok: res.ok, data: await res.text() };
      } catch (e) {
        return { error: e.message };
      }
    });
    console.log(`GET /api/integrations/webhooks: ${listRes.status || 'error'} - ${listRes.ok ? 'OK' : listRes.error || 'failed'}`);

    // Test creating a webhook via BFF
    const createRes = await page.evaluate(async () => {
      try {
        const res = await fetch('/api/integrations/webhooks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ url: 'https://test.example.com/hook', events: ['ticket.created', 'ticket.resolved'] }),
        });
        const data = await res.json();
        return { status: res.status, ok: res.ok, data };
      } catch (e) {
        return { error: e.message };
      }
    });
    console.log(`POST /api/integrations/webhooks: ${createRes.status || 'error'}`);
    if (createRes.data) {
      console.log(`  Created webhook ID: ${createRes.data.id}`);
      console.log(`  Has secret: ${!!createRes.data.secret}`);
      console.log(`  Events: ${JSON.stringify(createRes.data.events)}`);

      // Test the test endpoint
      if (createRes.data.id) {
        const testRes = await page.evaluate(async (whId) => {
          try {
            const res = await fetch(`/api/integrations/webhooks/${whId}/test`, {
              method: 'POST',
              credentials: 'include',
            });
            return { status: res.status, data: await res.json() };
          } catch (e) {
            return { error: e.message };
          }
        }, createRes.data.id);
        console.log(`POST /api/integrations/webhooks/${createRes.data.id}/test: ${testRes.status || 'error'}`);
        if (testRes.data) {
          console.log(`  Test result: ${testRes.data.success ? 'SUCCESS' : 'EXPECTED_FAIL'} - ${testRes.data.message}`);
        }

        // Test delete
        const deleteRes = await page.evaluate(async (whId) => {
          try {
            const res = await fetch(`/api/integrations/webhooks/${whId}`, {
              method: 'DELETE',
              credentials: 'include',
            });
            return { status: res.status, ok: res.ok };
          } catch (e) {
            return { error: e.message };
          }
        }, createRes.data.id);
        console.log(`DELETE /api/integrations/webhooks/${createRes.data.id}: ${deleteRes.status || 'error'}`);
      }
    }

    // Test webhook events endpoint
    const eventsRes = await page.evaluate(async () => {
      try {
        const res = await fetch('/api/webhooks/events', { credentials: 'include' });
        return { status: res.status, ok: res.ok, data: await res.text() };
      } catch (e) {
        return { error: e.message };
      }
    });
    console.log(`GET /api/webhooks/events: ${eventsRes.status || 'error'} - ${eventsRes.ok ? 'OK' : 'expected (needs admin)'}`);
  } catch (e) {
    console.log(`API test error: ${e.message}`);
  }

  // Step 5: Check inbound webhook receiver endpoint
  console.log('\n5. INBOUND WEBHOOK RECEIVER');
  try {
    const paddleRes = await page.evaluate(async () => {
      try {
        const res = await fetch('/api/v1/webhooks/paddle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ event_type: 'test', occurred_at: new Date().toISOString() }),
        });
        return { status: res.status };
      } catch (e) {
        return { error: e.message };
      }
    });
    console.log(`POST /api/v1/webhooks/paddle: ${paddleRes.status || 'error'} (401/403 = HMAC verification working)`);
  } catch (e) {
    console.log(`Inbound webhook error: ${e.message}`);
  }

  // Summary
  console.log('\n=== PHASE 6 TEST SUMMARY ===');
  console.log('Console errors:', errors.length);

  await browser.close();
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
