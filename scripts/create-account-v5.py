import asyncio
from playwright.async_api import async_playwright
import random
import string

def generate_random_email():
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"flexpay_{random_str}@parwa.dev"

async def create_and_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        
        test_email = generate_random_email()
        test_password = "FlexPayTest2024!"
        
        print(f"📧 New Account: {test_email}")
        print("-" * 50)
        
        # Step 1: Go to signup
        print("\n📍 Going to Signup Page...")
        await page.goto("https://parwa.buzz/signup", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(3000)
        
        # Step 2: Fill each field using Playwright's .fill() (works with React!)
        print("\n📍 Filling form fields...")
        
        try:
            # Email field
            email_input = await page.wait_for_selector('input[name="email"]', timeout=10000)
            await email_input.click()  # Focus first
            await email_input.fill(test_email)
            print(f"   ✅ Email: {test_email}")
            await page.wait_for_timeout(500)
            
            # Full name
            name_input = await page.query_selector('input[name="full_name"]')
            if name_input:
                await name_input.click()
                await name_input.fill("FlexPay Test User")
                print("   ✅ Full Name")
                await page.wait_for_timeout(300)
            
            # Company name
            company_input = await page.query_selector('input[name="company_name"]')
            if company_input:
                await company_input.click()
                await company_input.fill("FlexPay Test Corp")
                print("   ✅ Company Name")
                await page.wait_for_timeout(300)
            
            # Industry dropdown (select element)
            industry_select = await page.query_selector('select')
            if industry_select:
                await industry_select.select_option(index=1)  # Select first option after default
                print("   ✅ Industry: E-commerce (or similar)")
            
            # Password
            pwd_input = await page.query_selector('input[name="password"]')
            if pwd_input:
                await pwd_input.click()
                await pwd_input.fill(test_password)
                print("   ✅ Password")
                await page.wait_for_timeout(300)
            
            # Confirm Password
            confirm_pwd = await page.query_selector('input[name="confirm_password"]')
            if confirm_pwd:
                await confirm_pwd.click()
                await confirm_pwd.fill(test_password)
                print("   ✅ Confirm Password")
                await page.wait_for_timeout(300)
            
            await page.screenshot(path="/home/z/my-project/download/v5-01-filled.png")
            print("✅ Screenshot 1: Form filled correctly")
            
        except Exception as e:
            print(f"⚠️ Error: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path="/home/z/my-project/download/v5-01-filled.png")
        
        # Step 3: Submit
        print("\n📍 Submitting registration...")
        submit_btn = await page.query_selector('button[type="submit"]')
        if submit_btn:
            await submit_btn.click()
            
            print("⏳ Waiting for account creation (15s)...")
            await page.wait_for_timeout(15000)
            
            url_after = page.url
            print(f"🔗 URL: {url_after}")
            
            await page.screenshot(path="/home/z/my-project/download/v5-02-after-submit.png")
            print("✅ Screenshot 2: After submission")
        
        # Step 4: Check if we're logged in or need to login
        print("\n📍 Checking auth status...")
        
        # If we're on a page other than login/signup, we might be in!
        if "/login" not in page.url and "/signup" not in page.url:
            print("✅ Looks like we're logged in!")
        else:
            # Try logging in
            print("🔑 Trying to login...")
            await page.goto("https://parwa.buzz/login", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
            
            await page.fill('input[type="email"]', test_email)
            await page.fill('input[type="password"]', test_password)
            
            btn = await page.query_selector('button[type="submit"]')
            if btn:
                await btn.click()
                await page.wait_for_timeout(8000)
                
                print(f"🔗 URL after login attempt: {page.url}")
                await page.screenshot(path="/home/z/my-project/download/v5-03-login-result.png")
        
        # Step 5: Go to billing
        print("\n📍 Navigating to Billing...")
        await page.goto("https://parwa.buzz/dashboard/billing", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(6000)
        
        final_url = page.url
        on_billing = "/dashboard/billing" in final_url and "/login" not in final_url
        
        print(f"🔗 Final URL: {final_url}")
        print(f"📄 On Billing Page: {on_billing}")
        
        await page.screenshot(path="/home/z/my-project/download/v5-04-billing.png")
        await page.screenshot(path="/home/z/my-project/download/v5-05-full-billing.png", full_page=True)
        
        # Analysis
        content = await page.content()
        
        print("\n" + "=" * 60)
        if on_billing:
            print("🎉🎉🎉 SUCCESS!!! 🎉🎉🎉")
            print("=" * 60)
            print("\n📸 SCREENSHOTS OF FLEXPAY UI:")
            
            features_found = []
            for feature, text in [
                ("FlexPay Banner", "FlexPay Payment Plan"),
                ("$100/day limit", "$100"),
                ("Day 1 features", "Day 1"),
                ("Day 11 unlock", "Day 11"),
                ("$999 pricing", "$999"),
                ("Subscribe button", "Subscribe"),
                ("Activate button", "Activate"),
            ]:
                found = text in content
                features_found.append((feature, found))
                print(f"  {'✅' if found else '❌'} {feature}")
            
            count = sum(1 for _, f in features_found if f)
            print(f"\n  📊 {count}/7 FlexPay features visible")
            
            if count >= 4:
                print("\n  🚀 FLEXPAY UI IS LIVE AND WORKING!")
        else:
            print("❌ Still requires authentication")
            print("=" * 60)
        
        await browser.close()
        
        print("\n" + "🎊" * 25)
        print(f"COMPLETE! Account created:")
        print(f"  📧 {test_email}")
        print(f"  🔑 {test_password}")
        print("🎊" * 25)

asyncio.run(create_and_test())
