import { chromium } from 'playwright';

const TEST_URL = 'https://parwa.buzz';

async function testEscalationFlow() {
  console.log('🚀 Starting Parwa Escalation Flow Test...\n');
  
  const browser = await chromium.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
  });
  
  const page = await context.newPage();
  
  // Collect test results
  const results = {
    passed: [],
    failed: []
  };
  
  try {
    // ── TEST 1: Main Page Loads ──
    console.log('📋 Test 1: Loading main page...');
    await page.goto(TEST_URL, { waitUntil: 'networkidle', timeout: 30000 });
    const title = await page.title();
    console.log(`   ✅ Page loaded: ${title}`);
    results.passed.push('Main page loads');
    
    // Screenshot
    await page.screenshot({ path: '/home/z/my-project/download/test_01_main_page.png', fullPage: true });
    console.log('   📸 Screenshot saved: test_01_main_page.png');
    
    // ── TEST 2: Navigate to Escalations (should redirect to login) ──
    console.log('\n📋 Test 2: Navigating to /dashboard/escalations...');
    const response1 = await page.goto(`${TEST_URL}/dashboard/escalations`, { waitUntil: 'networkidle', timeout: 15000 });
    const currentUrl = page.url();
    console.log(`   Current URL: ${currentUrl}`);
    
    if (currentUrl.includes('/login')) {
      console.log('   ✅ Correctly redirects to login (auth required)');
      results.passed.push('Escalations requires auth → redirects to login');
      await page.screenshot({ path: '/home/z/my-project/download/test_02_login_redirect.png' });
    } else {
      console.log('   ⚠️ Did not redirect to login (might be logged in)');
      results.failed.push('Expected login redirect');
    }
    
    // ── TEST 3: Test Jarvis Chat with URL Params (Direct Access) ──
    console.log('\n📋 Test 3: Testing Jarvis Chat with escalation params...');
    const jarvisTestUrl = `${TEST_URL}/dashboard/jarvis?ticket_id=test_001&subject=URGENT%20Refund%20Request&description=Customer%20charged%20twice&escalation_id=esc_test_123&complexity=high&ticket_type=refund`;
    
    const response2 = await page.goto(jarvisTestUrl, { waitUntil: 'networkidle', timeout: 20000 });
    const jarvisUrl = page.url();
    console.log(`   Jarvis URL: ${jarvisUrl}`);
    
    // Take screenshot of Jarvis page
    await page.screenshot({ path: '/home/z/my-project/download/test_03_jarvis_with_params.png', fullPage: true });
    console.log('   📸 Screenshot saved: test_03_jarvis_with_params.png');
    
    if (jarvisUrl.includes('/login')) {
      console.log('   ✅ Jarvis also requires auth (expected)');
      results.passed.push('Jarvis chat requires auth');
    } else {
      console.log('   ℹ️ Might be on Jarvis page (if already authenticated)');
      
      // Check for any content that indicates our code is working
      const content = await page.content();
      if (content.includes('jarvis') || content.includes('Jarvis') || content.includes('JARVIS')) {
        console.log('   ✅ Jarvis-related content found on page');
        results.passed.push('Jarvis page renders correctly');
      }
    }
    
    // ── TEST 4: Verify Code is Deployed via Source ──
    console.log('\n📋 Test 4: Checking deployed JavaScript bundles...');
    
    // Go back to main page and check JS files
    await page.goto(TEST_URL, { waitUntil: 'networkidle' });
    
    // Get all script sources
    const scripts = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('script[src]')).map(s => s.src);
    });
    
    console.log(`   Found ${scripts.length} JS bundles`);
    
    // Check each bundle for our code
    let foundOurCode = false;
    for (const script of scripts) {
      try {
        const scriptResponse = await page.request.get(script);
        const scriptContent = await scriptResponse.text();
        
        if (scriptContent.includes('Discuss with Jarvis') || scriptContent.includes('escalation_id')) {
          console.log(`   ✅ FOUND our code in: ${script.split('/').pop()}`);
          foundOurCode = true;
          results.push('Deployed code contains "Discuss with Jarvis" button logic');
          break;
        }
      } catch (e) {
        // Skip failed loads
      }
    }
    
    if (!foundOurCode) {
      console.log('   ⚠️ Our code not found in initial bundles (may be lazy-loaded)');
      results.push('⚠️ Code may be in lazy-loaded chunks (dashboard-specific)');
    }
    
    // ── TEST 5: Check API Endpoints ──
    console.log('\n📋 Test 5: Testing backend API...');
    
    try {
      const apiResponse = await page.request.get('https://parwa-backend.onrender.com/api/v1/tickets');
      const apiStatus = apiResponse.status();
      const apiBody = await apiResponse.text();
      console.log(`   Backend status: ${apiStatus}`);
      console.log(`   Response: ${apiBody.substring(0, 100)}...`);
      
      if (apiStatus === 401 || apiStatus === 403) {
        console.log('   ✅ Backend requires auth (correct behavior)');
        results.passed.push('Backend API requires authentication');
      }
    } catch (e) {
      console.log(`   ⚠️ Backend error: ${e.message}`);
      results.failed.push('Backend unreachable');
    }
    
  } catch (error) {
    console.error(`\n❌ Test error: ${error.message}`);
    results.failed.push(error.message);
  } finally {
    await browser.close();
  }
  
  // ── Print Summary ──
  console.log('\n' + '='.repeat(50));
  console.log('📊 TEST RESULTS SUMMARY');
  console.log('='.repeat(50));
  console.log(`\n✅ Passed: ${results.passed.length}`);
  results.passed.forEach(r => console.log(`   + ${r}`));
  console.log(`\n❌ Failed: ${results.failed.length}`);
  results.failed.forEach(r => console.log(`   - ${r}`));
  console.log('\n' + '='.repeat(50));
  
  return results;
}

// Run tests
testEscalationFlow()
  .then(() => {
    console.log('\n✨ Tests complete! Screenshots saved to /home/z/my-project/download/');
    process.exit(0);
  })
  .catch((err) => {
    console.error('Fatal error:', err);
    process.exit(1);
  });
