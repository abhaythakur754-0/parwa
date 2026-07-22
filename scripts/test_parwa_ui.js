// Test PARWA UI like a human would - using Puppeteer in headless mode
const puppeteer = require('puppeteer');

(async () => {
  console.log('🚀 Launching browser...');
  
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  });
  
  const page = await browser.newPage();
  
  // Set viewport to desktop size
  await page.setViewport({ width: 1280, height: 800 });
  
  try {
    console.log('1️⃣ Opening parwa.buzz...');
    await page.goto('https://parwa.buzz', { waitUntil: 'networkidle2', timeout: 30000 });
    
    // Take screenshot of homepage
    await page.screenshot({ path: '/home/z/my-project/download/01_homepage.png', fullPage: true });
    console.log('✅ Homepage screenshot saved!');
    
    console.log('\n2️⃣ Looking for Login/Signup button...');
    
    // Get page content to understand structure
    const pageContent = await page.evaluate(() => {
      return {
        url: window.location.href,
        title: document.title,
        // Find all links and buttons
        links: Array.from(document.querySelectorAll('a')).map(a => ({
          text: a.textContent.trim(),
          href: a.href
        })).filter(l => l.text),
        buttons: Array.from(document.querySelectorAll('button')).map(b => ({
          text: b.textContent.trim(),
          type: b.type
        }))
      };
    });
    
    console.log('Page Title:', pageContent.title);
    console.log('URL:', pageContent.url);
    console.log('\nLinks found:', pageContent.links.slice(0, 15));
    console.log('\nButtons found:', pageContent.buttons);
    
    // Look for login link (case-insensitive)
    const loginLink = await page.evaluateHandle(() => {
      const links = Array.from(document.querySelectorAll('a'));
      return links.find(a => 
        a.textContent.toLowerCase().includes('login') || 
        a.textContent.toLowerCase().includes('sign in') ||
        a.href.toLowerCase().includes('login')
      );
    });
    
    const loginLinkElement = loginLink.asElement();
    
    if (loginLinkElement) {
      console.log('\n✅ Found login link! Clicking...');
      await loginLinkElement.click();
      await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 10000 }).catch(() => {});
      await new Promise(r => setTimeout(r, 2000));
      
      await page.screenshot({ path: '/home/z/my-project/download/02_login_page.png', fullPage: true });
      console.log('✅ Login page screenshot saved!');
      
      console.log('\n3️⃣ Filling in login form...');
      
      // Find and fill email input
      const emailInput = await page.$('input[type="email"], input[name="email"], input[id*="email" i]');
      if (emailInput) {
        await emailInput.click();
        await emailInput.type('testuser123@test.com');
        console.log('✅ Email filled');
      } else {
        console.log('❌ Email input not found');
      }
      
      // Find and fill password input
      const passwordInput = await page.$('input[type="password"], input[name="password"]');
      if (passwordInput) {
        await passwordInput.click();
        await passwordInput.type('TestPass123!');
        console.log('✅ Password filled');
      } else {
        console.log('❌ Password input not found');
      }
      
      await page.screenshot({ path: '/home/z/my-project/download/03_form_filled.png', fullPage: true });
      console.log('✅ Form filled screenshot saved!');
      
      console.log('\n4️⃣ Clicking Login button...');
      
      // Find submit/login button
      const submitBtn = await page.evaluateHandle(() => {
        const buttons = Array.from(document.querySelectorAll('button, [type="submit"], [role="button"]'));
        return buttons.find(b => 
          b.textContent.toLowerCase().includes('login') ||
          b.textContent.toLowerCase().includes('sign in') ||
          b.type === 'submit'
        );
      });
      
      const submitBtnElement = submitBtn.asElement();
      
      if (submitBtnElement) {
        await submitBtnElement.click();
        console.log('Clicked submit button...');
        
        // Wait for navigation or response
        await Promise.race([
          page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 15000 }),
          new Promise(r => setTimeout(r, 5000))
        ]).catch(() => {});
        
        await new Promise(r => setTimeout(r, 2000));
        
        await page.screenshot({ path: '/home/z/my-project/download/04_after_login.png', fullPage: true });
        console.log('✅ After login screenshot saved!');
        
        console.log('\n5️⃣ Current URL:', page.url());
        
        // Get current page info
        const afterLoginInfo = await page.evaluate(() => ({
          url: window.location.href,
          title: document.title,
          buttons: Array.from(document.querySelectorAll('button')).map(b => b.textContent.trim()).filter(Boolean)
        }));
        
        console.log('Page after login:', afterLoginInfo.title);
        console.log('Buttons available:', afterLoginInfo.buttons);
        
        // Look for Jarvis or Ticket creation
        console.log('\n6️⃣ Looking for Jarvis Chat / Create Ticket...');
        
        // Check for Jarvis-related elements
        const jarvisFound = await page.evaluate(() => {
          const allElements = document.querySelectorAll('*');
          const jarvisElements = [];
          for (const el of allElements) {
            if (el.textContent && (
              el.textContent.toLowerCase().includes('jarvis') ||
              el.className && el.className.toString().toLowerCase().includes('jarvis') ||
              el.id && el.id.toString().toLowerCase().includes('jarvis')
            )) {
              jarvisElements.push({
                tag: el.tagName,
                text: el.textContent.trim().substring(0, 50),
                class: el.className?.toString()?.substring(0, 50)
              });
            }
          }
          return jarvisElements.slice(0, 10);
        });
        
        console.log('Jarvis elements found:', jarvisFound);
        
        await page.screenshot({ path: '/home/z/my-project/download/05_dashboard_view.png', fullPage: true });
        console.log('✅ Dashboard screenshot saved!');
        
      } else {
        console.log('❌ Could not find submit button');
        // Take screenshot to see what's there
        await page.screenshot({ path: '/home/z/my-project/download/04_no_submit_btn.png', fullPage: true });
      }
      
    } else {
      console.log('\n❌ No login link found on homepage');
      await page.screenshot({ path: '/home/z/my-project/download/02_no_login_link.png', fullPage: true });
    }
    
  } catch (error) {
    console.error('❌ Error:', error.message);
    await page.screenshot({ path: '/home/z/my-project/download/error.png', fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
    console.log('\n✅ Browser closed!');
    console.log('📸 Screenshots saved to: /home/z/my-project/download/');
    console.log('\nFiles created:');
    console.log('  - 01_homepage.png');
    console.log('  - 02_login_page.png (or 02_no_login_link.png)');
    console.log('  - 03_form_filled.png');
    console.log('  - 04_after_login.png (or 04_no_submit_btn.png)');
    console.log('  - 05_dashboard_view.png');
  }
})();
