// Test PARWA JARVIS Chat - Create Ticket like a human would
const puppeteer = require('puppeteer');

(async () => {
  console.log('🚀 Launching browser for JARVIS test...');
  
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
    
    // Fill login form
    await page.type('input[type="email"], input[name="email"]', 'testuser123@test.com');
    await page.type('input[type="password"], input[name="password"]', 'TestPass123!');
    
    // Click sign in
    const signInBtn = await page.evaluateHandle(() => {
      const buttons = Array.from(document.querySelectorAll('button, [type="submit"]'));
      return buttons.find(b => b.textContent.toLowerCase().includes('sign in') || b.type === 'submit');
    });
    await (await signInBtn.asElement()).click();
    
    // Wait for login to complete
    await Promise.race([
      page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 15000 }),
      new Promise(r => setTimeout(r, 5000))
    ]).catch(() => {});
    
    console.log('✅ Logged in!');
    
    // Step 2: Navigate to Jarvis
    console.log('\n2️⃣ Navigating to Jarvis...');
    
    // Try clicking "Try Jarvis" link or navigate directly
    try {
      await page.goto('https://parwa.buzz/jarvis', { waitUntil: 'networkidle2', timeout: 30000 });
    } catch (e) {
      console.log('Direct nav failed, trying click...');
      const jarvisLink = await page.evaluateHandle(() => {
        const links = Array.from(document.querySelectorAll('a'));
        return links.find(a => 
          a.textContent.toLowerCase().includes('jarvis') ||
          a.href.toLowerCase().includes('jarvis')
        );
      });
      if (await jarvisLink.asElement()) {
        await (await jarvisLink.asElement()).click();
        await new Promise(r => setTimeout(r, 3000));
      }
    }
    
    await page.screenshot({ path: '/home/z/my-project/download/06_jarvis_page.png', fullPage: true });
    console.log('✅ Jarvis page screenshot saved!');
    
    // Step 3: Look for chat interface
    console.log('\n3️⃣ Looking for Jarvis chat interface...');
    
    const jarvisPageInfo = await page.evaluate(() => ({
      url: window.location.href,
      title: document.title,
      // Find chat input, textarea, or contenteditable elements
      inputs: Array.from(document.querySelectorAll('input, textarea, [contenteditable], [role="textbox"]')).map(el => ({
        tag: el.tagName,
        type: el.type,
        placeholder: el.placeholder,
        className: el.className?.toString()?.substring(0, 50)
      })),
      // Find any send/submit buttons
      buttons: Array.from(document.querySelectorAll('button')).map(b => ({
        text: b.textContent.trim(),
        className: b.className?.toString()?.substring(0, 50)
      })).filter(b => b.text || b.className.includes('send') || b.className.includes('submit'))
    }));
    
    console.log('Jarvis URL:', jarvisPageInfo.url);
    console.log('Inputs found:', jarvisPageInfo.inputs);
    console.log('Buttons:', jarvisPageInfo.buttons);
    
    // Step 4: Try to interact with Jarvis
    console.log('\n4️⃣ Attempting to chat with Jarvis...');
    
    // Look for chat input and type message
    const chatInput = await page.$('textarea, input[placeholder*="message" i], [contenteditable="true"], [role="textbox"]');
    
    if (chatInput) {
      console.log('Found chat input! Typing message...');
      await chatInput.click();
      await chatInput.type('Create a support ticket for John Doe about billing issue - overcharged $50');
      
      await page.screenshot({ path: '/home/z/my-project/download/07_message_typed.png', fullPage: true });
      console.log('✅ Message typed screenshot saved!');
      
      // Look for send button
      const sendBtn = await page.evaluateHandle(() => {
        const allElements = document.querySelectorAll('button, [role="button"], svg, [class*="send"]');
        for (const el of allElements) {
          const text = el.textContent?.toLowerCase() || '';
          const cls = el.className?.toString()?.toLowerCase() || '';
          if (text.includes('send') || cls.includes('send') || text.includes('submit')) {
            return el;
          }
        }
        // Return last button (often send button is last in chat interfaces)
        const buttons = Array.from(document.querySelectorAll('button'));
        return buttons[buttons.length - 1];
      });
      
      const sendElement = await sendBtn.asElement();
      if (sendElement) {
        console.log('Clicking send button...');
        await sendElement.click();
        
        // Wait for response
        console.log('Waiting for Jarvis response...');
        await new Promise(r => setTimeout(r, 8000)); // Wait 8 seconds for AI response
        
        await page.screenshot({ path: '/home/z/my-project/download/08_jarvis_response.png', fullPage: true });
        console.log('✅ Jarvis response screenshot saved!');
        
        // Get the response text
        const responseText = await page.evaluate(() => {
          // Look for message bubbles or chat responses
          const messages = document.querySelectorAll('[class*="message"], [class*="response"], [class*="chat"]');
          return Array.from(messages).map(m => m.textContent.trim()).filter(t => t.length > 0);
        });
        
        console.log('\n📝 Jarvis Response:', responseText.slice(-3)); // Last 3 messages
        
      } else {
        console.log('❌ No send button found');
      }
      
    } else {
      console.log('❌ No chat input found on Jarvis page');
      
      // Maybe we need to start a session first?
      console.log('\nLooking for session creation or start chat button...');
      
      const startBtn = await page.evaluateHandle(() => {
        const buttons = Array.from(document.querySelectorAll('button, [role="button"], a'));
        return buttons.find(b => {
          const text = b.textContent?.toLowerCase() || '';
          return text.includes('start') || text.includes('begin') || text.includes('chat') || text.includes('new');
        });
      });
      
      if (await startBtn.asElement()) {
        console.log('Found start button! Clicking...');
        await (await startBtn.asElement()).click();
        await new Promise(r => setTimeout(r, 3000));
        await page.screenshot({ path: '/home/z/my-project/download/07_after_start.png', fullPage: true });
      }
    }
    
    // Final screenshot
    await page.screenshot({ path: '/home/z/my-project/download/09_final_state.png', fullPage: true });
    console.log('\n✅ Final state screenshot saved!');
    
  } catch (error) {
    console.error('❌ Error:', error.message);
    await page.screenshot({ path: '/home/z/my-project/download/error_jarvis.png', fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
    console.log('\n🎉 Browser closed!');
    console.log('\n📸 New screenshots saved:');
    console.log('  - 06_jarvis_page.png');
    console.log('  - 07_message_typed.png (or 07_after_start.png)');
    console.log('  - 08_jarvis_response.png');
    console.log('  - 09_final_state.png');
  }
})();
