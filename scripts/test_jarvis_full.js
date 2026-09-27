// Test PARWA JARVIS Chat - Wait for full load then interact
const puppeteer = require('puppeteer');

(async () => {
  console.log('🚀 Launching browser for JARVIS test (with longer waits)...');
  
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  });
  
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });
  
  try {
    // Step 1: Login first
    console.log('1️⃣ Logging in...');
    await page.goto('https://parwa.buzz/login', { waitUntil: 'networkidle2', timeout: 30000 });
    
    await page.type('input[type="email"], input[name="email"]', 'testuser123@test.com');
    await page.type('input[type="password"], input[name="password"]', 'TestPass123!');
    
    const signInBtn = await page.evaluateHandle(() => {
      const buttons = Array.from(document.querySelectorAll('button, [type="submit"]'));
      return buttons.find(b => b.textContent.toLowerCase().includes('sign in') || b.type === 'submit');
    });
    await (await signInBtn.asElement()).click();
    
    await Promise.race([
      page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 15000 }),
      new Promise(r => setTimeout(r, 5000))
    ]).catch(() => {});
    
    console.log('✅ Logged in!');
    
    // Step 2: Navigate to Jarvis and WAIT for it to load
    console.log('\n2️⃣ Navigating to Jarvis and waiting for load...');
    await page.goto('https://parwa.buzz/jarvis', { waitUntil: 'networkidle2', timeout: 30000 });
    
    console.log('⏳ Waiting for Jarvis to finish connecting (15 seconds)...');
    await new Promise(r => setTimeout(r, 15000)); // Wait 15 seconds for full load
    
    await page.screenshot({ path: '/home/z/my-project/download/10_jarvis_loaded.png', fullPage: true });
    console.log('✅ After wait screenshot saved!');
    
    // Step 3: Check what's on the page now
    console.log('\n3️⃣ Checking page content after wait...');
    
    const pageInfo = await page.evaluate(() => ({
      url: window.location.href,
      bodyText: document.body?.innerText?.substring(0, 1000),
      inputs: Array.from(document.querySelectorAll('input, textarea, [contenteditable], [role="textbox"]')).map(el => ({
        tag: el.tagName,
        type: el.type,
        placeholder: el.placeholder,
        visible: el.offsetParent !== null
      })),
      buttons: Array.from(document.querySelectorAll('button')).map(b => ({
        text: b.textContent.trim(),
        visible: b.offsetParent !== null
      })).filter(b => b.text && b.visible)
    }));
    
    console.log('Body text preview:', pageInfo.bodyText);
    console.log('Visible inputs:', pageInfo.inputs.filter(i => i.visible));
    console.log('Visible buttons:', pageInfo.buttons);
    
    // Step 4: Try to find and use chat interface
    console.log('\n4️⃣ Looking for chat interface...');
    
    // Wait a bit more if still loading
    if (pageInfo.bodyText.includes('Connecting') || pageInfo.bodyText.includes('loading')) {
      console.log('Still loading, waiting 10 more seconds...');
      await new Promise(r => setTimeout(r, 10000));
      
      await page.screenshot({ path: '/home/z/my-project/download/11_after_extra_wait.png', fullPage: true });
    }
    
    // Look for any text input or editable area
    const chatInput = await page.evaluateHandle(() => {
      // Try multiple selectors for chat input
      const selectors = [
        'textarea',
        'input[type="text"]',
        '[contenteditable="true"]',
        '[role="textbox"]',
        '[placeholder*="message" i]',
        '[placeholder*="type" i]',
        '[placeholder*="chat" i]',
        '[class*="input"]',
        '[class*="textarea"]'
      ];
      
      for (const selector of selectors) {
        const element = document.querySelector(selector);
        if (element && element.offsetParent !== null) { // Visible
          return element;
        }
      }
      return null;
    });
    
    const inputElement = await chatInput.asElement();
    
    if (inputElement) {
      console.log('✅ Found chat input!');
      
      // Click and type message
      await inputElement.click();
      await inputElement.type('Create a support ticket for John Doe - billing issue overcharged $50');
      
      await page.screenshot({ path: '/home/z/my-project/download/12_ticket_request_typed.png', fullPage: true });
      console.log('✅ Ticket request typed!');
      
      // Find and click send button
      console.log('Looking for send button...');
      
      // Try pressing Enter instead of clicking send
      await page.keyboard.press('Enter');
      console.log('Pressed Enter to send...');
      
      // Wait for response
      console.log('Waiting for Jarvis response (10 seconds)...');
      await new Promise(r => setTimeout(r, 10000));
      
      await page.screenshot({ path: '/home/z/my-project/download/13_jarvis_ticket_response.png', fullPage: true });
      console.log('✅ Response screenshot saved!');
      
      // Get all text content to see the conversation
      const conversation = await page.evaluate(() => document.body.innerText);
      console.log('\n💬 Conversation:');
      console.log(conversation.substring(0, 2000));
      
    } else {
      console.log('❌ Still no chat input found');
      
      // Take final screenshot to show current state
      await page.screenshot({ path: '/home/z/my-project/download/12_no_chat_input.png', fullPage: true });
      
      // Maybe try clicking somewhere to activate?
      console.log('Trying to click in center of page to activate...');
      await page.click('body');
      await new Promise(r => setTimeout(r, 3000));
      await page.screenshot({ path: '/home/z/my-project/download/13_after_click.png', fullPage: true });
    }
    
  } catch (error) {
    console.error('❌ Error:', error.message);
    await page.screenshot({ path: '/home/z/my-project/download/error_final.png', fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
    console.log('\n🎉 Test complete!');
    console.log('\n📸 All screenshots in /home/z/my-project/download/:');
    console.log('  - 10_jarvis_loaded.png (after 15s wait)');
    console.log('  - 11_after_extra_wait.png (if still loading)');
    console.log('  - 12_ticket_request_typed.png OR 12_no_chat_input.png');
    console.log('  - 13_jarvis_ticket_response.png OR 13_after_click.png');
  }
})();
