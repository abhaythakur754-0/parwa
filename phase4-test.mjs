import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  try {
    console.log('Step 1: Login...');
    await page.goto('http://127.0.0.1:3000/login', { timeout: 30000 });
    await page.waitForLoadState('networkidle', { timeout: 15000 });
    
    const emailInput = page.locator('input[type="email"], input[name="email"]');
    if (await emailInput.count() > 0) {
      await emailInput.fill('dashboard@test.io');
    }
    
    const passInput = page.locator('input[type="password"]');
    await passInput.fill('Test@1234');
    
    await page.click('button[type="submit"]');
    await page.waitForTimeout(5000);
    
    console.log('After login URL:', page.url());
    await page.screenshot({ path: '/home/z/my-project/download/01-after-login.png', fullPage: true });
    
    if (page.url().includes('/onboarding')) {
      console.log('On onboarding page...');
      await page.waitForSelector('text=Welcome to PARWA', { timeout: 10000 }).catch(() => {});
      await page.screenshot({ path: '/home/z/my-project/download/02-onboarding-step1.png', fullPage: true });
      
      // Select SaaS
      const saasBtn = page.locator('button:has-text("SaaS")');
      if (await saasBtn.count() > 0) await saasBtn.click();
      
      // Select PARWA
      const parwaBtn = page.locator('button:has-text("PARWA")').first();
      if (await parwaBtn.count() > 0) await parwaBtn.click();
      
      await page.screenshot({ path: '/home/z/my-project/download/03-selections.png', fullPage: true });
      
      // Click Continue
      const continueBtn = page.locator('button:has-text("Continue")').first();
      if (await continueBtn.count() > 0) {
        await continueBtn.click();
        await page.waitForTimeout(3000);
      }
      
      // Skip through steps
      for (let i = 0; i < 8; i++) {
        const btn = page.locator('button:has-text("Continue"), button:has-text("Next"), button:has-text("Skip"), button:has-text("Accept"), button:has-text("Proceed")').first();
        if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
          await btn.click().catch(() => {});
          await page.waitForTimeout(2000);
          
          const costHeader = page.locator('text=Review Your Plan');
          if (await costHeader.isVisible({ timeout: 1000 }).catch(() => false)) {
            console.log('Found Cost Breakdown!');
            await page.screenshot({ path: '/home/z/my-project/download/04-cost-breakdown.png', fullPage: true });
            
            const paddleReady = page.locator('text=Secure checkout');
            const paddleUnavailable = page.locator('text=Payment checkout unavailable');
            
            if (await paddleReady.isVisible({ timeout: 2000 }).catch(() => false)) {
              console.log('PADDLE: READY');
            } else if (await paddleUnavailable.isVisible({ timeout: 2000 }).catch(() => false)) {
              console.log('PADDLE: UNAVAILABLE');
            } else {
              console.log('PADDLE: Status indicator not found');
            }
            
            const checkoutBtn = page.locator('button:has-text("Proceed to Checkout")');
            if (await checkoutBtn.count() > 0) {
              await checkoutBtn.click();
              await page.waitForTimeout(3000);
              await page.screenshot({ path: '/home/z/my-project/download/05-after-checkout.png', fullPage: true });
            }
            break;
          }
        }
      }
    }
    
    // Dashboard
    await page.goto('http://127.0.0.1:3000/dashboard', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(5000);
    await page.screenshot({ path: '/home/z/my-project/download/06-dashboard.png', fullPage: true });
    
    const variantSection = page.locator('text=Active Variants');
    if (await variantSection.isVisible({ timeout: 5000 }).catch(() => false)) {
      console.log('DASHBOARD: Active Variants VISIBLE');
    } else {
      console.log('DASHBOARD: Active Variants NOT VISIBLE');
    }
    
  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: '/home/z/my-project/download/error.png', fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
  }
})();
