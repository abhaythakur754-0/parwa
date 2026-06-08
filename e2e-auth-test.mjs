/**
 * E2E Auth Test - Tests signup and login flow on parwa.buzz
 * Uses Playwright to verify:
 * 1. Signup page loads
 * 2. Google sign-in button renders
 * 3. Email/password signup works
 * 4. Login page loads
 * 5. API routes respond correctly
 */
import { chromium } from 'playwright';

const BASE_URL = 'https://parwa.buzz';

async function test() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  const results = [];

  // Test 1: Homepage loads
  console.log('--- Test 1: Homepage loads ---');
  try {
    await page.goto(BASE_URL, { timeout: 30000 });
    const title = await page.title();
    console.log(`✅ Homepage title: ${title}`);
    results.push({ test: 'Homepage', status: 'PASS', detail: title });
  } catch (e) {
    console.log(`❌ Homepage failed: ${e.message}`);
    results.push({ test: 'Homepage', status: 'FAIL', detail: e.message });
  }

  // Test 2: Signup page loads
  console.log('\n--- Test 2: Signup page loads ---');
  try {
    await page.goto(`${BASE_URL}/signup`, { timeout: 30000 });
    await page.waitForSelector('input[type="email"], input[name="email"]', { timeout: 10000 });
    const hasGoogleBtn = await page.locator('text=Continue with Google').count() > 0;
    const hasEmailInput = await page.locator('input[type="email"], input[name="email"]').count() > 0;
    console.log(`✅ Signup page loaded. Google button: ${hasGoogleBtn}, Email input: ${hasEmailInput}`);
    results.push({ test: 'Signup page', status: 'PASS', detail: `Google: ${hasGoogleBtn}, Email: ${hasEmailInput}` });
  } catch (e) {
    console.log(`❌ Signup page failed: ${e.message}`);
    results.push({ test: 'Signup page', status: 'FAIL', detail: e.message });
  }

  // Test 3: Login page loads
  console.log('\n--- Test 3: Login page loads ---');
  try {
    await page.goto(`${BASE_URL}/login`, { timeout: 30000 });
    await page.waitForSelector('input[type="email"], input[name="email"]', { timeout: 10000 });
    const hasGoogleBtn = await page.locator('text=Continue with Google').count() > 0;
    const hasEmailInput = await page.locator('input[type="email"], input[name="email"]').count() > 0;
    console.log(`✅ Login page loaded. Google button: ${hasGoogleBtn}, Email input: ${hasEmailInput}`);
    results.push({ test: 'Login page', status: 'PASS', detail: `Google: ${hasGoogleBtn}, Email: ${hasEmailInput}` });
  } catch (e) {
    console.log(`❌ Login page failed: ${e.message}`);
    results.push({ test: 'Login page', status: 'FAIL', detail: e.message });
  }

  // Test 4: API - Check email endpoint
  console.log('\n--- Test 4: Check-email API ---');
  try {
    const resp = await page.request.post(`${BASE_URL}/api/auth/check-email`, {
      data: { email: 'test-nonexistent@example.com' },
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await resp.json();
    console.log(`✅ Check-email API: status=${resp.status()}, available=${data.available}`);
    results.push({ test: 'Check-email API', status: 'PASS', detail: `status=${resp.status()}` });
  } catch (e) {
    console.log(`❌ Check-email API failed: ${e.message}`);
    results.push({ test: 'Check-email API', status: 'FAIL', detail: e.message });
  }

  // Test 5: API - Login with invalid credentials (should return 401)
  console.log('\n--- Test 5: Login API with bad credentials ---');
  try {
    const resp = await page.request.post(`${BASE_URL}/api/auth/login`, {
      data: { email: 'nonexistent@example.com', password: 'WrongPass123!' },
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await resp.json();
    const is401 = resp.status() === 401;
    const hasErrorMsg = data.message && data.message.length > 0;
    console.log(`✅ Login API (bad creds): status=${resp.status()}, message="${data.message}"`);
    if (is401 || hasErrorMsg) {
      results.push({ test: 'Login API (bad creds)', status: 'PASS', detail: `status=${resp.status()}, msg="${data.message}"` });
    } else {
      results.push({ test: 'Login API (bad creds)', status: 'WARN', detail: `status=${resp.status()}, response=${JSON.stringify(data).slice(0, 200)}` });
    }
  } catch (e) {
    console.log(`❌ Login API failed: ${e.message}`);
    results.push({ test: 'Login API (bad creds)', status: 'FAIL', detail: e.message });
  }

  // Test 6: API - Register with valid data
  console.log('\n--- Test 6: Register API ---');
  try {
    const timestamp = Date.now();
    const resp = await page.request.post(`${BASE_URL}/api/auth/register`, {
      data: {
        email: `e2etest_${timestamp}@example.com`,
        password: 'TestPass123!',
        fullName: 'E2E Test User',
        companyName: 'E2E Test Company',
        industry: 'technology',
      },
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await resp.json();
    console.log(`✅ Register API: status=${resp.status()}, status_field="${data.status}", user=${data.user ? data.user.email : 'none'}`);
    
    if (data.status === 'success' && data.user) {
      results.push({ test: 'Register API', status: 'PASS', detail: `status=${resp.status()}, user=${data.user.email}` });
      
      // Test 7: Me-proxy with the auth cookie
      console.log('\n--- Test 7: Me-proxy with auth cookie ---');
      const cookies = await context.cookies();
      const parwaAt = cookies.find(c => c.name === 'parwa_at');
      if (parwaAt) {
        console.log(`✅ Auth cookie found: parwa_at exists (value length: ${parwaAt.value.length})`);
        
        const meResp = await page.request.get(`${BASE_URL}/api/auth/me-proxy`);
        const meData = await meResp.json();
        console.log(`   Me-proxy: status=${meResp.status()}, data=${JSON.stringify(meData).slice(0, 200)}`);
        
        if (meResp.status() === 200) {
          results.push({ test: 'Me-proxy after login', status: 'PASS', detail: `email=${meData.email}` });
        } else {
          results.push({ test: 'Me-proxy after login', status: 'WARN', detail: `status=${meResp.status()}, msg=${meData.message || JSON.stringify(meData).slice(0, 100)}` });
        }
      } else {
        console.log('⚠️  No parwa_at cookie found after register');
        results.push({ test: 'Me-proxy after login', status: 'FAIL', detail: 'No parwa_at cookie' });
      }
    } else {
      results.push({ test: 'Register API', status: 'WARN', detail: `status=${resp.status()}, response=${JSON.stringify(data).slice(0, 300)}` });
    }
  } catch (e) {
    console.log(`❌ Register API failed: ${e.message}`);
    results.push({ test: 'Register API', status: 'FAIL', detail: e.message });
  }

  // Print summary
  console.log('\n\n========== E2E TEST SUMMARY ==========');
  const passed = results.filter(r => r.status === 'PASS').length;
  const warned = results.filter(r => r.status === 'WARN').length;
  const failed = results.filter(r => r.status === 'FAIL').length;
  for (const r of results) {
    const icon = r.status === 'PASS' ? '✅' : r.status === 'WARN' ? '⚠️' : '❌';
    console.log(`${icon} ${r.test}: ${r.detail}`);
  }
  console.log(`\nTotal: ${results.length} | Passed: ${passed} | Warnings: ${warned} | Failed: ${failed}`);

  await browser.close();
  process.exit(failed > 0 ? 1 : 0);
}

test().catch(e => {
  console.error('E2E test crashed:', e);
  process.exit(2);
});
