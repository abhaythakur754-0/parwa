// FINAL Test - Complete JARVIS interaction with scrolling and proper send
const puppeteer = require('puppeteer');

(async () => {
  console.log('🎯 FINAL TEST: Complete JARVIS Ticket Creation');
  
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  });
  
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  
  try {
    // Login
    console.log('📝 Step 1: Logging in...');
    await page.goto('https://parwa.buzz/login', { waitUntil: 'networkidle2' });
    await page.type('input[type="email"]', 'testuser123@test.com');
    await page.type('input[type="password"]', 'TestPass123!');
    await page.click('button[type="submit"]');
    await new Promise(r => setTimeout(r, 5000));
    console.log('✅ Logged in!');
    
    // Go to Jarvis
    console.log('\n🤖 Step 2: Opening Jarvis...');
    await page.goto('https://parwa.buzz/jarvis', { waitUntil: 'networkidle2' });
    
    // Wait for Jarvis to fully load (check for "Online" status)
    console.log('⏳ Waiting for Jarvis to come online...');
    await page.waitForFunction(
      () => document.body.innerText.includes('Online') || document.body.innerText.includes('Ready'),
      { timeout: 20000 }
    ).catch(() => console.log('Timeout waiting for Online status'));
    
    await new Promise(r => setTimeout(r, 3000)); // Extra wait
    
    // Screenshot: Jarvis ready state
    await page.screenshot({ path: '/home/z/my-project/download/final_01_jarvis_ready.png' });
    console.log('✅ Screenshot 1: Jarvis Ready');
    
    // Find and click the textarea
    console.log('\n⌨️ Step 3: Typing ticket request...');
    const textarea = await page.$('textarea');
    if (textarea) {
      await textarea.click();
      await textarea.type('Create a support ticket for John Doe - billing issue overcharged $50', { delay: 50 });
      
      await page.screenshot({ path: '/home/z/my-project/download/final_02_message_typed.png' });
      console.log('✅ Screenshot 2: Message Typed');
      
      // Click the send button (paper plane icon) instead of pressing Enter
      console.log('\n📤 Step 4: Clicking Send button...');
      
      // Try to find and click send button
      const sendClicked = await page.evaluate(() => {
        // Look for send button (usually an icon button near textarea)
        const buttons = Array.from(document.querySelectorAll('button, [role="button"], [class*="send"], svg'));
        
        // Try clicking the last button near the input area (often send)
        for (let i = buttons.length - 1; i >= Math.max(0, buttons.length - 5); i--) {
          const btn = buttons[i];
          if (btn.offsetParent !== null) { // Visible
            btn.click();
            return true;
          }
        }
        return false;
      });
      
      if (!sendClicked) {
        // Fallback: Press Enter
        await page.keyboard.press('Enter');
        console.log('Used Enter key as fallback');
      }
      
      console.log('✅ Message sent! Waiting for response...');
      
      // Wait for Jarvis response (look for new text in chat)
      let previousText = '';
      for (let i = 0; i < 12; i++) { // Wait up to 60 seconds
        await new Promise(r => setTimeout(r, 5000));
        
        const currentText = await page.evaluate(() => document.body.innerText);
        
        if (currentText !== previousText && currentText.length > previousText.length + 20) {
          console.log(`✅ Got response after ${(i+1)*5} seconds!`);
          break;
        }
        
        previousText = currentText;
        console.log(`⏳ Still waiting... (${(i+1)*5}s)`);
        
        // Take intermediate screenshot every 20 seconds
        if ((i + 1) % 4 === 0) {
          await page.screenshot({ path: `/home/z/my-project/download/final_03_waiting_${(i+1)*5}s.png` });
        }
      }
      
      // Scroll to bottom of chat to see latest messages
      await page.evaluate(() => {
        window.scrollTo(0, document.body.scrollHeight);
        // Also try scrolling any chat container
        const chatContainer = document.querySelector('[class*="chat"], [class*="messages"], [class*="conversation"]');
        if (chatContainer) {
          chatContainer.scrollTop = chatContainer.scrollHeight;
        }
      });
      
      await new Promise(r => setTimeout(r, 1000));
      
      // Final screenshot with full conversation
      await page.screenshot({ 
        path: '/home/z/my-project/download/final_04_full_conversation.png',
        fullPage: true 
      });
      console.log('✅ Screenshot 4: Full Conversation');
      
      // Extract all conversation text
      console.log('\n💬 FULL CONVERSATION:');
      console.log('=' .repeat(50));
      
      const fullConversation = await page.evaluate(() => {
        return document.body.innerText;
      });
      
      console.log(fullConversation);
      console.log('=' .repeat(50));
      
      // Check if ticket was created or mentioned
      if (fullConversation.toLowerCase().includes('ticket')) {
        console.log('\n🎉 TICKET MENTIONED IN CONVERSATION!');
      }
      if (fullConversation.toLowerCase().includes('created') || fullConversation.toLowerCase().includes('done')) {
        console.log('✅ ACTION APPEARS TO HAVE BEEN TAKEN!');
      }
      
    } else {
      console.log('❌ Textarea not found');
    }
    
  } catch (error) {
    console.error('❌ Error:', error.message);
    await page.screenshot({ path: '/home/z/my-project/download/final_error.png' }).catch(() => {});
  } finally {
    await browser.close();
    console.log('\n🎉 FINAL TEST COMPLETE!');
    console.log('\n📸 Screenshots saved:');
    console.log('  - final_01_jarvis_ready.png');
    console.log('  - final_02_message_typed.png');
    console.log('  - final_03_waiting_*.png (if needed)');
    console.log('  - final_04_full_conversation.png (MOST IMPORTANT!)');
  }
})();
