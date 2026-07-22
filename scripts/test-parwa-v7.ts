import { chromium, Browser, Page } from 'playwright';
import * as fs from 'fs';

const DOWNLOAD_DIR = '/home/z/my-project/download';

// Use existing account that was created
const testEmail = 'flexpaytest1784357874633@parwa.dev';
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
  console.log('=== PARWA BILLING - LONG WAIT TEST ===\n');

  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
  });
  
  const page = await context.newPage();

  // Collect all console messages and errors
  const logs: string[] = [];
  const errors: string[] = [];
  
  page.on('console', msg => {
    const text = `[${msg.type()}] ${msg.text().substring(0, 200)}`;
    logs.push(text);
    if (msg.type() === 'error') errors.push(text);
  });
  
  page.on('pageerror', err => {
    errors.push(`[PAGE ERROR] ${err.message.substring(0, 200)}`);
  });

  // Track network requests
  const failedRequests: string[] = [];
  page.on('requestfailed', req => {
    failedRequests.push(`${req.method()} ${req.url().substring(0, 100)} - ${req.failure()?.errorText}`);
  });

  try {
    // Step 1: Login first
    console.log('📍 Step 1: Logging in...');
    await page.goto('https://parwa.buzz/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await sleep(1000);
    
    // Use API to login directly
    await page.evaluate(async ({ email, password }) => {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      return { status: res.status, ok: res.ok };
    }, { email: testEmail, password: testPassword });
    
    await sleep(2000);
    console.log('   ✅ Logged in via API');

    // Step 2: Navigate to billing with long wait
    console.log('\n📍 Step 2: Navigating to billing...');
    
    // Use waitForNavigation with longer timeout
    await page.goto('https://parwa.buzz/dashboard/billing', { 
      waitUntil: 'commit',
      timeout: 60000 
    }).catch(() => console.log('   Navigation timeout (continuing anyway)'));

    console.log('   Waiting for page to fully render (up to 30s)...');
    
    let loaded = false;
    for (let i = 0; i < 30; i++) {
      await sleep(1000);
      
      // Check if loading spinner is gone
      const isLoading = await page.evaluate(() => {
        const body = document.body;
        return body.innerText.includes('Loading...') && body.innerText.length < 200;
      }).catch(() => true);
      
      // Check for actual content
      const hasContent = await page.evaluate(() => {
        const text = document.body.innerText;
        return text.includes('Billing') && 
               (text.includes('$') || text.includes('Subscribe') || text.includes('plan'));
      }).catch(() => false);
      
      if (!isLoading || hasContent) {
        loaded = true;
        console.log(`   ✅ Page rendered after ${i+1}s`);
        break;
      }
      
      if (i % 5 === 4) {
        console.log(`   Still loading... (${i+1}s)`);
        await screenshot(page, `v7-loading-${i+1}s.png`);
      }
    }

    // Take final screenshots
    console.log('\n📍 Step 3: Capturing screenshots...');
    await screenshot(page, 'v7-billing-final.png', true);
    await screenshot(page, 'v7-billing-viewport.png');

    // Get visible text only (not scripts)
    const visibleText = await page.evaluate(() => {
      // Get text from visible elements only
      const walker = document.createTreeWalker(
        document.body,
        NodeFilter.SHOW_TEXT,
        null
      );
      const texts = [];
      while (walker.nextNode()) {
        const text = walker.currentNode.textContent?.trim();
        if (text && text.length > 0) {
          texts.push(text);
        }
      }
      return texts.join('\n').substring(0, 3000);
    }).catch(() => '');

    console.log('\n========== VISIBLE PAGE TEXT ==========');
    console.log(visibleText);

    // Check for FlexPay elements in visible text
    console.log('\n========== FLEXPAY UI CHECKS ==========');
    const checks = [
      'FlexPay', '$100', 'Day 1', 'Day 11',
      'Ticket Management', 'Team Collaboration', 'Analytics Dashboard', 'Custom Workflows',
      'SMS Notification', 'Calling Features',
      '$999', '$2,499', '$3,999',
      'Subscribe', 'Get Started', 'Choose Plan',
      'USD'
    ];
    
    for (const check of checks) {
      const found = visibleText.includes(check);
      console.log(`${found ? '✅' : '❌'} ${check}`);
    }

    // Print errors if any
    if (errors.length > 0) {
      console.log('\n========== CONSOLE ERRORS ==========');
      errors.slice(0, 10).forEach(e => console.log(e));
    }

    if (failedRequests.length > 0) {
      console.log('\n========== FAILED REQUESTS ==========');
      failedRequests.slice(0, 10).forEach(f => console.log(f));
    }

    // Try clicking elements if they exist
    console.log('\n📍 Step 4: Looking for interactive elements...');
    
    // Look for any buttons
    const buttonsInfo = await page.$$eval('button', btns => 
      btns.map(b => ({
        text: b.innerText.trim(),
        visible: b.offsetParent !== null,
        disabled: b.disabled
      })).filter(b => b.text)
    ).catch(() => []);
    
    console.log('Buttons found:');
    buttonsInfo.forEach(b => console.log(`  ${b.visible ? '✅' : '❌'} "${b.text}"${b.disabled ? ' [DISABLED]' : ''}`));

    // Try to click Subscribe or similar button
    for (const btn of buttonsInfo.filter(b => b.visible && !b.disabled)) {
      if (btn.text.toLowerCase().includes('subscribe') || 
          btn.text.toLowerCase().includes('get started') ||
          btn.text.toLowerCase().includes('choose')) {
        console.log(`\nClicking: "${btn.text}"`);
        await page.click(`button:has-text("${btn.text}")`);
        await sleep(2500);
        await screenshot(page, 'v7-after-click.png', true);
        break;
      }
    }

    console.log('\n✅ TEST COMPLETE');
    console.log(`Credentials: ${testEmail}`);

  } catch (error) {
    console.error('❌ Error:', error);
    await screenshot(page, 'v7-error.png');
  } finally {
    await browser.close();
  }
}

main();
