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
        
        # Step 1: Go to login page
        print("\n📍 Step 1: Going to Login Page...")
        await page.goto("https://parwa.buzz/login", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(3000)
        
        # Step 2: Click "Sign up" link (using text content match)
        print("\n📍 Step 2: Clicking 'Sign up' link...")
        try:
            # Try multiple approaches to find the signup link
            signup_clicked = False
            
            # Approach 1: Get all links and find one with "Sign up"
            all_links = await page.query_selector_all('a')
            for link in all_links:
                text = await link.inner_text()
                if 'sign up' in text.lower() or 'signup' in text.lower():
                    print(f"✅ Found link: '{text}'")
                    await link.click()
                    signup_clicked = True
                    break
            
            if not signup_clicked:
                # Approach 2: Use text selector with exact match
                await page.click('text=Sign up', timeout=5000)
                signup_clicked = True
            
            if signup_clicked:
                print("✅ Clicked Sign up!")
                await page.wait_for_timeout(3000)
                
                current_url = page.url
                print(f"🔗 URL: {current_url}")
                
                await page.screenshot(path="/home/z/my-project/download/v3-01-signup-form.png")
                print("✅ Screenshot 1: Signup form")
                
        except Exception as e:
            print(f"⚠️ Error: {e}")
            await page.screenshot(path="/home/z/my-project/download/v3-01-signup-form.png")
        
        # Step 3: Fill the registration form
        print("\n📍 Step 3: Filling registration form...")
        try:
            await page.wait_for_timeout(2000)
            
            # Look for ALL input fields on the page
            inputs = await page.query_selector_all('input')
            print(f"   Found {len(inputs)} input fields")
            
            for i, inp in enumerate(inputs):
                inp_type = await inp.get_attribute('type') or 'text'
                inp_name = await inp.get_attribute('name') or ''
                inp_placeholder = await inp.get_attribute('placeholder') or ''
                print(f"   Input {i}: type={inp_type}, name={inp_name}, placeholder={inp_placeholder}")
            
            # Fill name field (usually first text input or named "name")
            for selector in ['input[name="name"]', 'input[type="text"]:not([type="email"])']:
                name_input = await page.query_selector(selector)
                if name_input:
                    await name_input.fill("FlexPay Test User")
                    print("✅ Filled NAME field")
                    break
            
            # Fill email
            email_input = await page.query_selector('input[type="email"], input[name="email"]')
            if email_input:
                await email_input.fill(test_email)
                print(f"✅ Filled EMAIL: {test_email}")
            
            # Fill password(s)
            password_inputs = await page.query_selector_all('input[type="password"]')
            for idx, pwd_input in enumerate(password_inputs):
                await pwd_input.fill(test_password)
                label = "PASSWORD" if idx == 0 else "CONFIRM PASSWORD"
                print(f"✅ Filled {label}")
            
            await page.screenshot(path="/home/z/my-project/download/v3-02-filled-form.png")
            print("✅ Screenshot 2: Form filled")
            
        except Exception as e:
            print(f"⚠️ Form fill error: {e}")
            await page.screenshot(path="/home/z/my-project/download/v3-02-filled-form.png")
        
        # Step 4: Submit
        print("\n📍 Step 4: Submitting...")
        try:
            submit_btn = await page.query_selector('button[type="submit"]')
            if submit_btn:
                btn_text = await submit_btn.inner_text()
                print(f"   Button: '{btn_text}'")
                await submit_btn.click()
                
                print("⏳ Waiting for account creation...")
                await page.wait_for_timeout(8000)
                
                final_url = page.url
                print(f"🔗 URL after submit: {final_url}")
                
                await page.screenshot(path="/home/z/my-project/download/v3-03-after-submit.png")
                print("✅ Screenshot 3: After submission")
                
        except Exception as e:
            print(f"⚠️ Submit error: {e}")
        
        # Step 5: Check if we're logged in and go to billing
        print("\n📍 Step 5: Checking auth status & going to billing...")
        
        # Check if we have any cookies/cookies that indicate login
        cookies = await page.context.cookies()
        auth_cookies = [c for c in cookies if 'auth' in c['name'].lower() or 'token' in c['name'].lower() or 'session' in c['name'].lower()]
        print(f"   Found {len(auth_cookies)} auth cookies")
        
        # Navigate to billing
        await page.goto("https://parwa.buzz/dashboard/billing", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(6000)
        
        billing_url = page.url
        print(f"🔗 Billing URL: {billing_url}")
        
        await page.screenshot(path="/home/z/my-project/download/v3-04-billing-page.png")
        print("✅ Screenshot 4: Billing page")
        
        await page.screenshot(path="/home/z/my-project/download/v3-05-full-billing.png", full_page=True)
        print("✅ Screenshot 5: Full billing page")
        
        # Final check
        content = await page.content()
        is_billing_page = "billing" in billing_url.lower() and "login" not in billing_url.lower()
        
        print("\n" + "=" * 60)
        if is_billing_page:
            print("🎉 SUCCESS! We're on the BILLING PAGE!")
            print("=" * 60)
            
            checks = {
                "FlexPay Banner": "FlexPay Payment Plan" in content,
                "$100/day info": "$100" in content,
                "Day 1 features": "Day 1" in content,
                "Day 11 features": "Day 11" in content,
                "USD prices": "$999" in content or "$2,499" in content or "$3,999" in content,
                "Subscribe buttons": "Subscribe" in content or "Activate" in content,
            }
            
            for check, result in checks.items():
                status = "✅" if result else "❌"
                print(f"  {status} {check}")
        else:
            print("❌ Still on LOGIN page - need authentication")
            print("=" * 60)
            print(f"   URL: {billing_url}")
        
        await browser.close()
        
        print("\n" + "🎊" * 20)
        print(f"DONE! Account: {test_email}")
        print("🎊" * 20)

asyncio.run(create_and_test())
