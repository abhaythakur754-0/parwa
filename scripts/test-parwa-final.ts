import { chromium, Browser, Page } from 'playwright';
import * as fs from 'fs';

const DOWNLOAD_DIR = '/home/z/my-project/download';

const testEmail = 'flexpaytest1784357596469@parwa.dev';
const testPassword = 'TestPass123!@#';

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
  console.log('=== PARWA BILLING TEST (SIMPLE) ===\n');

  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-web-security']
  });
  
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    ignoreHTTPSErrors: true
  });
  
  const page = await context.newPage();

  try {
    // Step 1: Login
    console.log('📍 Step 1: Login...');
    await page.goto('https://parwa.buzz/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await sleep(2000);
    
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', testPassword);
    await page.click('button[type="submit"]');
    
    console.log('   Waiting for navigation...');
    await sleep(5000); // Give it time to login and redirect
    
    let currentUrl = page.url();
    console.log(`   Current URL: ${currentUrl}`);
    await screenshot(page, 'final-01-after-login.png');

    // Step 2: Go to billing
    console.log('\n📍 Step 2: Go to billing...');
    try {
      await page.goto('https://parwa.buzz/dashboard/billing', { 
        waitUntil: 'domcontentloaded', 
        timeout: 45000 
      });
    } catch (e) {
      console.log('   Page load timeout, continuing anyway...');
    }
    
    // Wait for content
    console.log('   Waiting for content...');
    for (let i = 0; i < 15; i++) {
      await sleep(1000);
      const hasContent = await page.evaluate(() => {
        return document.body.innerText.includes('$') || 
               document.body.innerText.includes('Subscribe') ||
               document.body.innerText.length > 500;
      }).catch(() => false);
      
      if (hasContent) {
        console.log(`   ✅ Content loaded after ${i+1}s`);
        break;
      }
      
      if (i === 14) {
        console.log('   ⚠️ Still loading after 15s, capturing anyway');
      }
    }

    // Screenshots
    await screenshot(page, 'final-02-billing-full.png', true);
    await screenshot(page, 'final-03-billing-viewport.png');

    // Get text content
    const bodyText = await page.evaluate(() => document.body.innerText).catch(() => '');
    
    console.log('\n========== PAGE TEXT ==========');
    console.log(bodyText.substring(0, 2500));

    // Check for FlexPay elements
    console.log('\n========== FLEXPAY ELEMENTS CHECK ==========');
    const elements = [
      'FlexPay', '$100', 'Day 1', 'Day 11',
      'Ticket Management', 'Team Collaboration', 'Analytics Dashboard', 'Custom Workflows',
      'SMS Notification', 'Calling Features',
      '$999', '$2,499', '$3,999',
      'Subscribe', 'USD'
    ];
    
    for (const el of elements) {
      const found = bodyText.includes(el);
      console.log(`${found ? '✅' : '❌'} ${el}`);
    }

    // Try clicking subscribe
    console.log('\n📍 Step 3: Try Subscribe button...');
    const buttons = await page.$$eval('button', btns => 
      btns.map(b => b.innerText.trim()).filter(t => t)
    ).catch(() => []);
    
    console.log(`Buttons found: ${buttons.join(', ')}`);

    for (const btnText of ['Subscribe', 'Get Started', 'Choose Plan']) {
      const btn = await page.$(`button:has-text("${btnText}")`).catch(() => null);
      if (btn) {
        console.log(`Clicking: ${btnText}`);
        await btn.click();
        await sleep(2000);
        await screenshot(page, 'final-04-after-subscribe.png', true);
        
        // Check modal
        const modalText = await page.evaluate(() => {
          const els = document.querySelectorAll('[role="dialog"], [class*="modal-overlay"], [class*="dialog"]');
          return Array.from(els).map(e => e.innerText).join('\n---\n');
        }).catch(() => '');
        
        if (modalText) {
          console.log('\n📋 MODAL/POPUP:');
          console.log(modalText.substring(0, 600));
        }
        break;
      }
    }

    console.log('\n✅ DONE!');

  } catch (error) {
    console.error('Error:', error.message);
    await screenshot(page, 'final-error.png');
  } finally {
    await browser.close();
  }
}

main();
