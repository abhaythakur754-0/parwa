import asyncio
from playwright.async_api import async_playwright

async def take_screenshot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        
        # Go to login page with domcontentloaded (faster)
        print("📍 Navigating to PARWA...")
        try:
            await page.goto("https://parwa.buzz/login", wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(3000)
            await page.screenshot(path="/home/z/my-project/download/01-login-page.png")
            print("✅ Screenshot 1: Login page saved")
        except Exception as e:
            print(f"⚠️ Login page: {e}")
            await page.screenshot(path="/home/z/my-project/download/01-login-page.png")
        
        # Navigate to billing page
        print("\n📍 Navigating to Billing Page...")
        try:
            await page.goto("https://parwa.buzz/dashboard/billing", wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)
            
            current_url = page.url
            print(f"🔗 URL after navigation: {current_url}")
            
            await page.screenshot(path="/home/z/my-project/download/02-billing-page.png", full_page=False)
            print("✅ Screenshot 2: Billing page saved")
            
            # Take a full page screenshot too
            await page.screenshot(path="/home/z/my-project/download/03-billing-fullpage.png", full_page=True)
            print("✅ Screenshot 3: Full billing page saved")
            
        except Exception as e:
            print(f"⚠️ Billing page: {e}")
            await page.screenshot(path="/home/z/my-project/download/02-billing-page.png")
        
        await browser.close()
        print("\n🎉 Done! Screenshots in /home/z/my-project/download/")

asyncio.run(take_screenshot())
