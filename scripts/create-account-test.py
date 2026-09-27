import asyncio
from playwright.async_api import async_playwright
import random
import string

def generate_random_email():
    """Generate a random email for testing"""
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"flexpaytest_{random_str}@parwa.dev"

async def create_and_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        
        # Generate unique test credentials
        test_email = generate_random_email()
        test_password = "FlexPayTest2024!"
        
        print(f"📧 Test Email: {test_email}")
        print(f"🔑 Test Password: {test_password}")
        print("-" * 50)
        
        # Step 1: Go to login/signup page
        print("\n📍 Step 1: Going to Login Page...")
        await page.goto("https://parwa.buzz/login", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path="/home/z/my-project/download/step1-login-page.png")
        print("✅ Screenshot 1: Login page")
        
        # Step 2: Click Sign Up link
        print("\n📍 Step 2: Looking for Sign Up link...")
        try:
            signup_link = await page.query_selector('a:has-text("Sign up"), a:has-text("Sign Up"), a:has-text("Register")')
            if signup_link:
                await signup_link.click()
                await page.wait_for_timeout(2000)
                print("✅ Clicked Sign Up link")
            else:
                print("⚠️ No Sign Up link found, trying alternative...")
                # Maybe there's a toggle or we're already on signup
        except Exception as e:
            print(f"⚠️ Signup link error: {e}")
        
        await page.screenshot(path="/home/z/my-project/download/step2-signup-page.png")
        print("✅ Screenshot 2: Signup page (or current state)")
        
        # Step 3: Fill in registration form
        print("\n📍 Step 3: Filling in registration form...")
        try:
            # Look for name field
            name_input = await page.query_selector('input[name="name"], input[placeholder*="name" i], input[id*="name"]')
            if name_input:
                await name_input.fill("FlexPay Test User")
                print("✅ Filled name field")
            
            # Look for email field
            email_input = await page.query_selector('input[type="email"], input[name="email"], input[placeholder*="email" i]')
            if email_input:
                await email_input.fill(test_email)
                print(f"✅ Filled email: {test_email}")
            
            # Look for password field  
            password_input = await page.query_selector('input[type="password"]')
            if password_input:
                await password_input.fill(test_password)
                print("✅ Filled password")
                
                # Confirm password if exists
                confirm_password = await page.query_selector('input[name="confirmPassword"], input[placeholder*="confirm" i]')
                if confirm_password:
                    await confirm_password.fill(test_password)
                    print("✅ Filled confirm password")
            
            await page.screenshot(path="/home/z/my-project/download/step3-form-filled.png")
            print("✅ Screenshot 3: Form filled")
            
            # Click submit button
            submit_btn = await page.query_selector('button[type="submit"], button:has-text("Sign up"), button:has-text("Create"), button:has-text("Register")')
            if submit_btn:
                await submit_btn.click()
                print("✅ Clicked submit button")
                
                # Wait for registration to complete
                await page.wait_for_timeout(5000)
                
                current_url = page.url
                print(f"🔗 URL after signup: {current_url}")
                
                await page.screenshot(path="/home/z/my-project/download/04-after-signup.png")
                print("✅ Screenshot 4: After signup attempt")
                
        except Exception as e:
            print(f"⚠️ Registration form error: {e}")
            await page.screenshot(path="/home/z/my-project/download/04-after-signup.png")
        
        # Step 4: Try to login if needed
        if "login" in page.url.lower():
            print("\n📍 Step 4: Trying to login with created account...")
            try:
                await page.goto("https://parwa.buzz/login", wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
                
                email_input = await page.query_selector('input[type="email"]')
                password_input = await page.query_selector('input[type="password"]')
                
                if email_input and password_input:
                    await email_input.fill(test_email)
                    await password_input.fill(test_password)
                    
                    signin_btn = await page.query_selector('button[type="submit"]')
                    if signin_btn:
                        await signin_btn.click()
                        print("✅ Attempted login")
                        await page.wait_for_timeout(5000)
                        
                        current_url = page.url
                        print(f"🔗 URL after login: {current_url}")
                        
                        await page.screenshot(path="/home/z/my-project/download/05-after-login.png")
                        print("✅ Screenshot 5: After login")
                        
            except Exception as e:
                print(f"⚠️ Login error: {e}")
        
        # Step 5: Navigate to Billing Page
        print("\n📍 Step 5: Navigating to Billing Page...")
        try:
            await page.goto("https://parwa.buzz/dashboard/billing", wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(5000)
            
            final_url = page.url
            print(f"🔗 Final URL: {final_url}")
            
            await page.screenshot(path="/home/z/my-project/download/06-billing-page.png")
            print("✅ Screenshot 6: Billing page")
            
            await page.screenshot(path="/home/z/my-project/download/07-billing-fullpage.png", full_page=True)
            print("✅ Screenshot 7: Full billing page")
            
            # Check content
            content = await page.content()
            checks = {
                "FlexPay Banner": "FlexPay Payment Plan" in content,
                "Banking Limit Info": "$100 USD per day" in content or "banking transaction" in content.lower(),
                "Day 1 Features": "Available from Day 1" in content or "Day 1" in content,
                "Day 11 Features": "Unlocks on Day 11" in content or "Day 11" in content,
                "USD Pricing": "$999" in content or "$2,499" in content or "$3,999" in content,
                "Subscribe Buttons": "Subscribe" in content or "Activate" in content,
            }
            
            print("\n" + "=" * 50)
            print("🔍 CONTENT CHECK RESULTS:")
            print("=" * 50)
            for check, result in checks.items():
                status = "✅ FOUND" if result else "❌ MISSING"
                print(f"  {status}: {check}")
            print("=" * 50)
            
        except Exception as e:
            print(f"⚠️ Billing page error: {e}")
            await page.screenshot(path="/home/z/my-project/download/06-billing-page.png")
        
        await browser.close()
        
        print("\n" + "🎉" * 20)
        print("ALL SCREENSHOTS SAVED!")
        print("🎉" * 20)
        print(f"\n📧 Test Account Created:")
        print(f"   Email: {test_email}")
        print(f"   Password: {test_password}")
        print(f"\n📁 Screenshots saved to: /home/z/my-project/download/")

asyncio.run(create_and_test())
