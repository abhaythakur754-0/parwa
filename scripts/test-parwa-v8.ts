import { chromium, Browser, Page, BrowserContext } from 'playwright';
import * as fs from 'fs';

const DOWNLOAD_DIR = '/home/z/my-project/download';

const timestamp = Date.now();
const testEmail = `flexpaytest${timestamp}@parwa.dev`;
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

async function registerAndLogin(context: BrowserContext, email: string, password: string): Promise<boolean> {
  const page = await context.newPage();
  
  try {
    // Step 1: Register via API (same origin)
    console.log('   Registering...');
    await page.goto('https://parwa.buzz', { waitUntil: 'domcontentloaded', timeout: 30000 });
    
    const regResult = await page.evaluate(async ({ e, p }) => {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: e, password: p, confirmPassword: p, fullName: 'Test User' })
      });
      return { ok: res.ok, status: res.status };
    }, { e: email, p: password });
    
    console.log(`   Register: ${regResult.status}`);
    
    // Step 2: Check cookies after register
    let cookies = await context.cookies();
    console.log(`   Cookies after register: ${cookies.length}`);
    
    // Step 3: Login via form (not API) - this ensures proper redirect + cookie handling
    console.log('   Logging in via form...');
    await page.goto('https://parwa.buzz/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await sleep(1000);
    
    await page.fill('input[name="email"]', email);
    await page.fill('input[name="password"]', password);
    
    // Click sign in and wait for navigation
    await Promise.all([
      page.waitForNavigation({ timeout: 15000 }).catch(() => null),
      page.click('button[type="submit"]')
    ]);
    
    await sleep(2000);
    
    // Check if we're logged in
    const currentUrl = page.url();
    const bodyText = await page.textContent('body').catch(() => '') || '';
    
    console.log(`   URL after login: ${currentUrl}`);
    console.log(`   On dashboard?: ${currentUrl.includes('/dashboard') || !bodyText.includes('Welcome back')}`);
    
    // Check cookies again
    cookies = await context.cookies();
    const hasAuthCookie = cookies.some(c => 
      c.name.includes('token') || c.name.includes('auth') || c.name.includes('session')
    );
    console.log(`   Has auth cookie?: ${hasAuthCookie}`);
    
    await page.close();
    
    return !bodyText.includes('Welcome back') || currentUrl.includes('/dashboard');
    
  } catch (e) {
    console.error(`   Error: ${(e as Error).message}`);
    await page.close();
    return false;
  }
}

async function main() {
  console.log('=== PARWA FLEXPAY TEST v8 (FORM LOGIN) ===\n');
  console.log(`📧 Email: ${testEmail}`);

  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
  });

  try {
    // Step 1: Register and Login
    console.log('\n📍 Step 1: Account setup...');
    const loggedIn = await registerAndLogin(context, testEmail, testPassword);
    
    if (!loggedIn) {
      console.log('⚠️ Login may have failed, trying anyway...');
    }

    // Step 2: Navigate to billing with the same context
    console.log('\n📍 Step 2: Going to billing page...');
    const page = await context.newPage();
    
    await page.goto('https://parwa.buzz/dashboard/billing', { 
      waitUntil: 'domcontentloaded',
      timeout: 60000 
    }).catch(() => {});
    
    // Wait for real content (not loading spinner)
    console.log('   Waiting for content...');
    let contentLoaded = false;
    
    for (let i = 0; i < 25; i++) {
      await sleep(1000);
      
      const state = await page.evaluate(() => {
        const body = document.body;
        const text = body.innerText;
        
        return {
          isLoading: text.includes('Loading...') && text.length < 300,
          hasBilling: text.includes('Billing') && text.length > 500,
          hasPrice: text.includes('$999') || text.includes('$2,499') || text.includes('$3,999'),
          hasFlexPay: text.includes('FlexPay') || text.includes('$100'),
          isLogin: text.includes('Welcome back'),
          textLength: text.length,
          url: window.location.href
        };
      }).catch(() => ({ isLoading: true }));
      
      if ((state.hasBilling || state.hasPrice) && !state.isLogin) {
        contentLoaded = true;
        console.log(`   ✅ Content loaded after ${i+1}s`);
        break;
      }
      
      if (state.isLogin) {
        console.log(`   ⚠️ Redirected to login after ${i+1}s`);
        break;
      }
      
      if (i % 8 === 7 && i > 0) {
        console.log(`   Still waiting... (${i+1}s, len=${state.textLength})`);
      }
    }

    // Screenshots
    console.log('\n📍 Step 3: Capturing screenshots...');
    await screenshot(page, 'v8-billing-full.png', true);
    await screenshot(page, 'v8-billing-viewport.png');

    // Get rendered text (use innerText of main content areas)
    const pageInfo = await page.evaluate(() => {
      // Try multiple selectors to get visible text
      const mainContent = document.querySelector('main') || 
                         document.querySelector('[role="main"]') ||
                         document.querySelector('.flex-1') ||
                         document.body;
      
      return {
        url: window.location.href,
        title: document.title,
        text: mainContent?.innerText?.substring(0, 4000) || '',
        // Also get all headings
        headings: Array.from(document.querySelectorAll('h1, h2, h3')).map(h => h.innerText.trim()).filter(Boolean)
      };
    }).catch(() => ({ url: '', title: '', text: '', headings: [] }));

    console.log('\n========== PAGE INFO ==========');
    console.log(`URL: ${pageInfo.url}`);
    console.log(`Title: ${pageInfo.title}`);
    console.log(`Headings: ${pageInfo.headings.join(' | ')}`);

    if (pageInfo.text) {
      console.log('\n========== VISIBLE TEXT ==========');
      console.log(pageInfo.text.substring(0, 2500));
    }

    // FlexPay checks
    console.log('\n========== FLEXPAY ELEMENTS ==========');
    const checks = [
      ['FlexPay Info Banner', ['FlexPay', '$100', 'daily installment']],
      ['Day 1 Features', ['Day 1', 'Immediate', 'Ticket Management', 'Team Collaboration']],
      ['Day 11 Features', ['Day 11', 'SMS Notification', 'Calling Features']],
      ['Pricing Cards', ['$', 'Mini', 'PARWA', 'PARWA High', '999', '2499', '3999']],
      ['Subscribe Buttons', ['Subscribe', 'Get Started', 'Choose Plan', 'Activate']],
      ['USD Currency Note', ['USD', 'US Dollar', 'dollar']]
    ];

    for (const [name, keywords] of checks) {
      const found = keywords.some(k => pageInfo.text.toLowerCase().includes(k.toLowerCase()));
      console.log(`${found ? '✅' : '❌'} ${name}`);
    }

    // Look for interactive elements
    console.log('\n📍 Step 4: Interactive elements...');
    const elements = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'))
        .filter(b => b.offsetParent !== null)
        .map(b => b.innerText.trim())
        .filter(Boolean);
      
      const links = Array.from(document.querySelectorAll('a[href]'))
        .filter(a => a.offsetParent !== null)
        .map(a => ({ text: a.innerText.trim(), href: a.getAttribute('href') }))
        .filter(a => a.text);

      return { buttons, links: links.slice(0, 10) };
    }).catch(() => ({ buttons: [], links: [] }));

    console.log(`Buttons: ${elements.buttons.slice(0, 10).join(', ') || 'none'}`);

    // Try clicking subscribe-like button
    const subscribeBtns = elements.buttons.filter(b => 
      b.toLowerCase().includes('subscribe') || 
      b.toLowerCase().includes('get started') ||
      b.toLowerCase().includes('choose')
    );

    if (subscribeBtns.length > 0) {
      console.log(`\nClicking: "${subscribeBtns[0]}"`);
      await page.click(`button:has-text("${subscribeBtns[0]}")`);
      await sleep(2500);
      await screenshot(page, 'v8-after-subscribe.png', true);
      
      // Check for modal
      const modalText = await page.evaluate(() => {
        const modal = document.querySelector('[role="dialog"], [class*="modal-overlay"], [class*="dialog"]');
        return modal?.innerText?.substring(0, 1000) || '';
      }).catch(() => '');
      
      if (modalText) {
        console.log('\n📋 MODAL CONTENT:');
        console.log(modalText);
      }
    }

    // Save credentials
    fs.writeFileSync(`${DOWNLOAD_DIR}/test-credentials.txt`,
`Email: ${testEmail}
Password: ${testPassword}
Created: ${new Date().toISOString()}
URL: ${pageInfo.url}`
    );

    console.log('\n✅ COMPLETE!');
    console.log(`Credentials saved to: ${DOWNLOAD_DIR}/test-credentials.txt`);

  } catch (error) {
    console.error('❌ Error:', error);
  } finally {
    await browser.close();
  }
}

main();
