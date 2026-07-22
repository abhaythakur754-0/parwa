import asyncio
from playwright.async_api import async_playwright

async def wait_and_capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        
        # Login first
        print("📍 Logging in...")
        await page.goto("https://parwa.buzz/login", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2000)
        
        await page.fill('input[type="email"]', "flexpay_wcmom1hb@parwa.dev")
        await page.fill('input[type="password"]', "FlexPayTest2024!")
        
        btn = await page.query_selector('button[type="submit"]')
        await btn.click()
        
        print("⏳ Waiting for login...")
        await page.wait_for_timeout(8000)
        
        # Go to billing and wait for content to load
        print("\n📍 Going to Billing Page...")
        await page.goto("https://parwa.buzz/dashboard/billing", wait_until="domcontentloaded", timeout=45000)
        
        # Wait for the loading spinner to disappear or content to appear
        print("⏳ Waiting for page content to load (up to 30s)...")
        
        try:
            # Wait for pricing cards or subscription info
            await page.wait_for_function('''() => {
                const content = document.body.innerText;
                return content.includes('$999') || 
                       content.includes('$2,499') || 
                       content.includes('$3,999') ||
                       content.includes('Subscribe') ||
                       content.includes('No active subscriptions');
            }''', timeout=30000)
            
            print("✅ Content loaded!")
            
        except Exception as e:
            print(f"⚠️ Timeout: {e}")
        
        # Extra wait for animations
        await page.wait_for_timeout(3000)
        
        final_url = page.url
        print(f"🔗 URL: {final_url}")
        
        # Take screenshots
        await page.screenshot(path="/home/z/my-project/download/final-billing-loaded.png")
        print("✅ Screenshot 1: Billing page (loaded)")
        
        await page.screenshot(path="/home/z/my-project/download/final-billing-full.png", full_page=True)
        print("✅ Screenshot 2: Full billing page")
        
        # Get page text for analysis
        content = await page.evaluate('() => document.body.innerText')
        
        print("\n" + "=" * 60)
        print("📄 PAGE CONTENT ANALYSIS:")
        print("=" * 60)
        
        # Check for various indicators
        indicators = [
            ("FlexPay Banner", ["FlexPay Payment Plan", "FlexPay"]),
            ("Banking Limit Info", ["banking transaction", "$100 per day", "$100/day"]),
            ("Day 1 Features", ["Day 1", "Available from Day 1"]),
            ("Day 11 Unlock", ["Day 11", "Unlocks on Day 11"]),
            ("USD Pricing $999", ["$999"]),
            ("USD Pricing $2499", ["$2,499", "$2499"]),
            ("USD Pricing $3999", ["$3,999", "$3999"]),
            ("Subscribe Button", ["Subscribe · $", "Subscribe"]),
            ("Activate Button", ["Activate · $", "Activate"]),
            ("Mini PARWA Card", ["Mini PARWA", "mini"]),
            ("PARWA High Card", ["PARWA High", "high"]),
            ("No Subscriptions Msg", ["No active subscriptions"]),
        ]
        
        found_count = 0
        for name, search_terms in indicators:
            found = any(term.lower() in content.lower() for term in search_terms)
            if found:
                found_count += 1
            
            status = "✅ FOUND" if found else "❌ Missing"
            print(f"  {status}: {name}")
        
        print("-" * 60)
        print(f"📊 Total: {found_count}/{len(indicators)} features detected")
        
        if found_count >= 5:
            print("\n🎉🎉🎉 FLEXPAY UI IS LIVE AND VISIBLE! 🎉🎉🎉")
        elif found_count >= 2:
            print("\n⚠️ Partial UI visible - may still be loading")
        else:
            print("\n❌ FlexPay UI not visible yet")
        
        # Print some of the actual content
        print("\n📝 Sample page content (first 800 chars):")
        print("-" * 40)
        print(content[:800] if len(content) > 800 else content)
        print("-" * 40)
        
        await browser.close()
        
        print("\n✅ Done! Screenshots saved.")

asyncio.run(wait_and_capture())
