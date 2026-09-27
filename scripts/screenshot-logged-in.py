import asyncio
from playwright.async_api import async_playwright

async def take_screenshot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        
        # Go to login page
        print("📍 Going to Login Page...")
        await page.goto("https://parwa.buzz/login", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2000)
        
        # Fill in credentials
        print("🔑 Filling in login credentials...")
        try:
            email_input = await page.wait_for_selector('input[type="email"], input[name="email"]', timeout=10000)
            await email_input.fill("flexpaytest@parwa.dev")
            
            password_input = await page.wait_for_selector('input[type="password"]', timeout=5000)
            await password_input.fill("Test1234!")
            
            # Click sign in button
            signin_btn = await page.wait_for_selector('button[type="submit"]', timeout=5000)
            await signin_btn.click()
            
            print("⏳ Waiting for login to complete...")
            await page.wait_for_timeout(5000)
            
            # Take screenshot after login attempt
            current_url = page.url
            print(f"🔗 URL after login: {current_url}")
            await page.screenshot(path="/home/z/my-project/download/04-after-login.png")
            print("✅ Screenshot 4: After login saved")
            
        except Exception as e:
            print(f"⚠️ Login error: {e}")
            await page.screenshot(path="/home/z/my-project/download/04-after-login.png")
        
        # Now navigate to billing page
        print("\n📍 Navigating to Billing Page...")
        try:
            await page.goto("https://parwa.buzz/dashboard/billing", wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)
            
            current_url = page.url
            print(f"🔗 Current URL: {current_url}")
            
            # Save screenshot
            await page.screenshot(path="/home/z/my-project/download/05-billing-page.png")
            print("✅ Screenshot 5: Billing page saved")
            
            # Full page screenshot
            await page.screenshot(path="/home/z/my-project/download/06-billing-fullpage.png", full_page=True)
            print("✅ Screenshot 6: Full billing page saved")
            
            # Check for FlexPay content
            content = await page.content()
            checks = {
                "FlexPay text": "FlexPay" in content,
                "Banking limit info": "banking transaction" in content.lower() or "$100" in content,
                "Day 1 features": "Day 1" in content or "Day 11" in content,
                "USD pricing": "$999" in content or "$2,499" in content or "$3,999" in content,
            }
            
            print("\n🔍 Content Check:")
            for check, result in checks.items():
                status = "✅" if result else "❌"
                print(f"  {status} {check}: {result}")
                
        except Exception as e:
            print(f"⚠️ Billing page error: {e}")
            await page.screenshot(path="/home/z/my-project/download/05-billing-page.png")
        
        await browser.close()
        print("\n🎉 All screenshots saved!")

asyncio.run(take_screenshot())
