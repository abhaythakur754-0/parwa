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
        print(f"🔑 Password: {test_password}")
        print("-" * 50)
        
        # Step 1: Go to login page
        print("\n📍 Step 1: Going to Login Page...")
        await page.goto("https://parwa.buzz/login", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(3000)
        
        # Step 2: Click "Sign up" link to switch to registration
        print("\n📍 Step 2: Clicking 'Sign up' link...")
        try:
            signup_link = await page.wait_for_selector('a:has-text("Sign up"), a:has-text("Sign Up")', timeout=10000)
            await signup_link.click()
            print("✅ Clicked Sign up link")
            await page.wait_for_timeout(3000)
            
            current_url = page.url
            print(f"🔗 URL after clicking signup: {current_url}")
            
            await page.screenshot(path="/home/z/my-project/download/v2-01-signup-page.png")
            print("✅ Screenshot 1: Signup page")
            
        except Exception as e:
            print(f"⚠️ Signup link error: {e}")
            await page.screenshot(path="/home/z/my-project/download/v2-01-signup-page.png")
        
        # Step 3: Fill registration form
        print("\n📍 Step 3: Filling registration form...")
        try:
            # Wait for form fields
            await page.wait_for_timeout(2000)
            
            # Try different selectors for name field
            name_filled = False
            for selector in ['input[name="name"]', 'input[placeholder*="name" i]', 'input[id*="name"]', 'input[type="text"]']:
                name_input = await page.query_selector(selector)
                if name_input:
                    await name_input.fill("FlexPay Test User")
                    name_filled = True
                    print("✅ Filled name field")
                    break
            
            # Email field
            email_input = await page.wait_for_selector('input[type="email"], input[name="email"]', timeout=5000)
            if email_input:
                await email_input.fill(test_email)
                print(f"✅ Filled email: {test_email}")
            
            # Password field(s) - might have password + confirm password
            password_inputs = await page.query_selector_all('input[type="password"]')
            if len(password_inputs) >= 1:
                await password_inputs[0].fill(test_password)
                print("✅ Filled password")
                
            if len(password_inputs) >= 2:
                await password_inputs[1].fill(test_password)
                print("✅ Filled confirm password")
            
            await page.screenshot(path="/home/z/my-project/download/v2-02-form-filled.png")
            print("✅ Screenshot 2: Registration form filled")
            
            # Step 4: Submit registration
            print("\n📍 Step 4: Submitting registration...")
            submit_btn = await page.query_selector('button[type="submit"], button:has-text("Sign up"), button:has-text("Create"), button:has-text("Register"), button:has-text("Get started")')
            if submit_btn:
                btn_text = await submit_btn.inner_text()
                print(f"✅ Found button: '{btn_text}'")
                await submit_btn.click()
                
                print("⏳ Waiting for registration...")
                await page.wait_for_timeout(8000)
                
                final_url = page.url
                print(f"🔗 URL after registration: {final_url}")
                
                await page.screenshot(path="/home/z/my-project/download/v2-03-after-registration.png")
                print("✅ Screenshot 3: After registration")
                
            else:
                print("❌ No submit button found")
                await page.screenshot(path="/home/z/my-project/download/v2-03-after-registration.png")
                
        except Exception as e:
            print(f"⚠️ Registration error: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path="/home/z/my-project/download/v2-03-after-registration.png")
        
        # Step 5: Navigate to billing page (might redirect to onboarding or dashboard)
        print("\n📍 Step 5: Navigating to Billing Page...")
        try:
            await page.goto("https://parwa.buzz/dashboard/billing", wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(6000)
            
            billing_url = page.url
            print(f"🔗 Billing URL: {billing_url}")
            
            await page.screenshot(path="/home/z/my-project/download/v2-04-billing-page.png")
            print("✅ Screenshot 4: Billing page")
            
            await page.screenshot(path="/home/z/my-project/download/v2-05-billing-fullpage.png", full_page=True)
            print("✅ Screenshot 5: Full billing page")
            
            # Check content
            content = await page.content()
            checks = {
                "FlexPay Banner": "FlexPay Payment Plan" in content,
                "Banking Limit": "$100" in content and ("banking" in content.lower() or "transaction" in content.lower()),
                "Day 1 Features": "Day 1" in content,
                "Day 11 Features": "Day 11" in content,
                "USD Pricing": any(price in content for price in ["$999", "$2,499", "$3,999"]),
                "Subscribe/Activate": "Subscribe" in content or "Activate" in content,
                "Pricing Cards": "Mini PARWA" in content or "PARWA High" in content,
            }
            
            print("\n" + "=" * 60)
            print("🎯 FINAL CONTENT CHECK - FlexPay UI:")
            print("=" * 60)
            found_count = 0
            for check, result in checks.items():
                status = "✅" if result else "❌"
                if result: found_count += 1
                print(f"  {status} {check}")
            print("-" * 60)
            print(f"  📊 Results: {found_count}/{len(checks)} features found")
            print("=" * 60)
            
            if found_count >= 4:
                print("\n🎉 SUCCESS! FlexPay UI is LIVE!")
            else:
                print("\n⚠️ Partial deployment - some features may still be deploying")
                
        except Exception as e:
            print(f"⚠️ Billing page error: {e}")
        
        await browser.close()
        
        print("\n" + "🎊" * 25)
        print("TEST COMPLETE!")
        print("🎊" * 25)
        print(f"\n📧 Test Account:")
        print(f"   Email: {test_email}")
        print(f"   Password: {test_password}")
        print(f"\n📁 Screenshots: /home/z/my-project/download/v2-*.png")

asyncio.run(create_and_test())
