// SIMPLE but ROBUST JARVIS test
const puppeteer = require('puppeteer');

(async () => {
  console.log('🚀 Simple Jarvis Test');
  
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });
  
  try {
    // Login
    await page.goto('https://parwa.buzz/login', { waitUntil: 'networkidle2' });
    await page.type('input[type="email"]', 'testuser123@test.com');
    await page.type('input[type="password"]', 'TestPass123!');
    await page.keyboard.press('Enter');
    await new Promise(r => setTimeout(r, 6000));
    
    // Go to Jarvis
    await page.goto('https://parwa.buzz/jarvis', { waitUntil: 'networkidle2' });
    
    // Wait for "Online" text (Jarvis ready)
    await page.waitForSelector('textarea', { timeout: 30000 });
    await new Promise(r => setTimeout(r, 5000)); // Extra time for full load
    
    // Screenshot 1: Ready state
    await page.screenshot({ path: '/home/z/my-project/download/simple_01_ready.png' });
    console.log('✅ Screenshot 1: Jarvis Ready');
    
    // Type message in textarea
    const textarea = await page.$('textarea');
    await textarea.click();
    await page.keyboard.type('Create a support ticket for John Doe - billing issue', { delay: 30 });
    
    // Screenshot 2: Message typed
    await page.screenshot({ path: '/home/z/my-project/download/simple_02_typed.png' });
    console.log('✅ Screenshot 2: Message Typed');
    
    // Send with Enter
    await page.keyboard.press('Enter');
    console.log('📤 Message sent! Waiting 15s for response...');
    
    // Wait for response
    await new Promise(r => setTimeout(r, 15000));
    
    // Screenshot 3: After response wait
    await page.screenshot({ path: '/home/z/my-project/download/simple_03_response.png' });
    console.log('✅ Screenshot 3: After Response Wait');
    
    // Get conversation text
    const text = await page.evaluate(() => document.body.innerText);
    console.log('\n📄 Page Text:');
    console.log(text);
    
  } catch (err) {
    console.error('❌ Error:', err.message);
  } finally {
    await browser.close();
    console.log('\n✅ Done!');
  }
})();
