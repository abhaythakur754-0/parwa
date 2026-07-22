import { chromium, Browser, Page } from 'playwright';

const DOWNLOAD_DIR = '/home/z/my-project/download';

// Use existing account
const testEmail = 'flexpaytest1784358018218@parwa.dev';
const testPassword = 'TestPass1234!';

async function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function screenshot(page: Page, name: string, fullPage = false) {
  const path = `${DOWNLOAD_DIR}/${name}`;
  await page.screenshot({ path, fullPage });
  console.log(`✅ Saved: ${name}`);
}

async function main() {
  console.log('=== FINAL FLEXPAY UI VERIFICATION ===\n');

  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
  });
  
  const page = await context.newPage();

  try {
    // Step 1: Login via API then form for cookies
    console.log('📍 Step 1: Authenticating...');
    await page.goto('https://parwa.buzz', { waitUntil: 'domcontentloaded', timeout: 30000 });
    
    // Register/login via API
    await page.evaluate(async ({ e, p }) => {
      try { await fetch('/api/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: e, password: p, confirmPassword: p, fullName: 'Test' }) }); } catch {}
    }, { e: testEmail, p: testPassword });
    
    // Login via form
    await page.goto('https://parwa.buzz/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await sleep(1000);
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', testPassword);
    await Promise.all([
      page.waitForNavigation({ timeout: 15000 }).catch(() => null),
      page.click('button[type="submit"]')
    ]);
    await sleep(2000);

    // Step 2: Go to billing
    console.log('📍 Step 2: Loading billing page...');
    await page.goto('https://parwa.buzz/dashboard/billing', { 
      waitUntil: 'domcontentloaded',
      timeout: 60000 
    }).catch(() => {});
    
    // Wait for content
    console.log('   Waiting for render...');
    for (let i = 0; i < 20; i++) {
      await sleep(1000);
      const text = await page.textContent('body').catch(() => '') || '';
      if (text.includes('$999') && text.length > 500 && !text.includes('Loading...')) {
        console.log(`   ✅ Rendered after ${i+1}s`);
        break;
      }
    }

    // Screenshots
    console.log('\n📍 Step 3: Capturing final screenshots...');
    await screenshot(page, 'FINAL-billing-full.png', true);
    await screenshot(page, 'FINAL-billing-viewport.png');

    // Get visible text
    const pageInfo = await page.evaluate(() => ({
      url: window.location.href,
      headings: Array.from(document.querySelectorAll('h1, h2, h3')).map(h => h.innerText.trim()).filter(Boolean),
      text: document.body.innerText.substring(0, 5000)
    }));

    console.log('\n========== RESULTS ==========');
    console.log(`URL: ${pageInfo.url}`);
    console.log(`Headings: ${pageInfo.headings.join(' | ')}`);

    // Check for FlexPay elements
    const checks = [
      ['FlexPay Banner', ['FlexPay Payment Plan', '$100 USD per day']],
      ['Day 1 Section', ['Available from Day 1', 'Ticket Management', 'Team Collaboration']],
      ['Day 11 Section', ['Unlocks on Day 11', 'SMS Notifications', 'Calling Features']],
      ['Pricing Cards', ['$999.00/mo', '$2,499.00/mo', '$3,999.00/mo']],
      ['Subscribe Buttons', ['Subscribe · $']]
    ];

    console.log('\nFlexPay UI Checks:');
    let allPassed = true;
    for (const [name, keywords] of checks) {
      const found = keywords.every(k => pageInfo.text.includes(k));
      console.log(`${found ? '✅' : '❌'} ${name}`);
      if (!found) allPassed = false;
    }

    if (allPassed) {
      console.log('\n🎉 ALL FLEXPAY UI ELEMENTS ARE SHOWING!');
    } else {
      console.log('\n⚠️ Some elements missing - Vercel may still be deploying');
    }

    // Save final result
    require('fs').writeFileSync(`${DOWNLOAD_DIR}/final-test-result.txt`,
`TEST COMPLETED: ${new Date().toISOString()}
URL: ${pageInfo.url}
ALL CHECKS PASSED: ${allPassed}
HEADINGS: ${pageInfo.headings.join(', ')}
`
    );

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
}

main();
