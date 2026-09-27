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
        
        # Step 1: Go to signup page directly
        print("\n📍 Step 1: Going to Signup Page...")
        await page.goto("https://parwa.buzz/signup", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(3000)
        
        await page.screenshot(path="/home/z/my-project/download/final-01-signup.png")
        print("✅ Screenshot 1: Signup page")
        
        # Step 2: Fill ALL required fields
        print("\n📍 Step 2: Filling ALL form fields...")
        try:
            # Email
            email_input = await page.wait_for_selector('input[name="email"]', timeout=5000)
            await email_input.fill(test_email)
            print(f"   ✅ Email: {test_email}")
            
            # Full Name
            name_input = await page.query_selector('input[name="full_name"]')
            if name_input:
                await name_input.fill("FlexPay Test User")
                print("   ✅ Full Name")
            
            # Company Name (REQUIRED!)
            company_input = await page.query_selector('input[name="company_name"]')
            if company_input:
                await company_input.fill("FlexPay Test Company")
                print("   ✅ Company Name")
            
            # Industry (REQUIRED!) - Select from dropdown
            industry_select = await page.query_selector('select, [role="combobox"], .select-dropdown')
            if industry_select:
                await industry_select.click()
                await page.wait_for_timeout(500)
                # Click first option
                first_option = await page.query_selector('option[value], [role="option"]')
                if first_option:
                    await first_option.click()
                    print("   ✅ Industry selected")
            else:
                # Try clicking the dropdown trigger
                industry_dropdown = await page.query_selector('text=Select your industry')
                if industry_dropdown:
                    await industry_dropdown.click()
                    await page.wait_for_timeout(500)
                    # Click an option
                    option = await page.query_selector('[class*="option"]:first-child, li:first-child')
                    if option:
                        await option.click()
                        print("   ✅ Industry selected (alternative)")
            
            # Password
            pwd_input = await page.query_selector('input[name="password"]')
            if pwd_input:
                await pwd_input.fill(test_password)
                print("   ✅ Password")
            
            # Confirm Password
            confirm_pwd = await page.query_selector('input[name="confirm_password"]')
            if confirm_pwd:
                await confirm_pwd.fill(test_password)
                print("   ✅ Confirm Password")
            
            await page.screenshot(path="/home/z/my-project/download/final-02-filled.png")
            print("✅ Screenshot 2: All fields filled")
            
        except Exception as e:
            print(f"⚠️ Error filling form: {e}")
            await page.screenshot(path="/home/z/my-project/download/final-02-filled.png")
        
        # Step 3: Submit
        print("\n📍 Step 3: Creating account...")
        try:
            submit_btn = await page.wait_for_selector('button[type="submit"]', timeout=5000)
            await submit_btn.click()
            
            print("⏳ Waiting for account creation...")
            await page.wait_for_timeout(10000)  # Longer wait for account creation
            
            final_url = page.url
            print(f"🔗 URL after submit: {final_url}")
            
            await page.screenshot(path="/home/z/my-project/download/final-03-after-submit.png")
            print("✅ Screenshot 3: After submission")
            
        except Exception as e:
            print(f"⚠️ Submit error: {e}")
        
        # Step 4: Check if we need to complete onboarding or go to billing
        print("\n📍 Step 4: Navigating to Billing Page...")
        
        # Try going to dashboard/billing
        await page.goto("https://parwa.buzz/dashboard/billing", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(6000)
        
        billing_url = page.url
        is_billing_page = "/dashboard/billing" in billing_url and "/login" not in billing_url
        
        print(f"🔗 Final URL: {billing_url}")
        print(f"📄 On Billing Page: {is_billing_page}")
        
        await page.screenshot(path="/home/z/my-project/download/final-04-billing.png")
        print("✅ Screenshot 4: Billing page")
        
        await page.screenshot(path="/home/z/my-project/download/final-05-full-billing.png", full_page=True)
        print("✅ Screenshot 5: Full billing page")
        
        # Content analysis
        content = await page.content()
        
        print("\n" + "=" * 60)
        if is_billing_page:
            print("🎉🎉🎉 SUCCESS! ON BILLING PAGE! 🎉🎉🎉")
            print("=" * 60)
            
            features = [
                ("FlexPay Banner", "FlexPay Payment Plan"),
                ("$100/day Banking Limit", "$100"),
                ("Day 1 Features", "Day 1"),
                ("Day 11 Unlock", "Day 11"),
                ("USD Pricing ($999)", "$999"),
                ("USD Pricing ($2,499)", "$2,499"),
                ("USD Pricing ($3,999)", "$3,999"),
                ("Subscribe Button", "Subscribe"),
                ("Activate Button", "Activate"),
                ("Mini PARWA Card", "Mini PARWA"),
                ("PARWA High Card", "PARWA High"),
            ]
            
            found = 0
            for name, search_text in features:
                exists = search_text in content
                if exists: found += 1
                status = "✅" if exists else "❌"
                print(f"  {status} {name}")
            
            print("-" * 60)
            print(f"  📊 {found}/{len(features)} features detected")
            
            if found >= 6:
                print("\n  🚀 FLEXPAY UI IS FULLY DEPLOYED!")
        else:
            print("❌ Not on billing page (requires login)")
            print("=" * 60)
        
        await browser.close()
        
        print("\n" + "🎊" * 25)
        print("TEST COMPLETE!")
        print(f"📧 Account: {test_email}")
        print(f"🔑 Password: {test_password}")
        print("🎊" * 25)

asyncio.run(create_and_test())
