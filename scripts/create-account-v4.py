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
        
        # Step 1: Go to signup page
        print("\n📍 Going to Signup Page...")
        await page.goto("https://parwa.buzz/signup", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(3000)
        
        # Step 2: Fill form using JavaScript for reliability
        print("\n📍 Filling form with JavaScript...")
        await page.evaluate('''(data) => {
            // Fill email
            const emailInput = document.querySelector('input[name="email"]');
            if (emailInput) {
                emailInput.value = data.email;
                emailInput.dispatchEvent(new Event('input', { bubbles: true }));
                emailInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            
            // Fill full name
            const nameInput = document.querySelector('input[name="full_name"]');
            if (nameInput) {
                nameInput.value = data.name;
                nameInput.dispatchEvent(new Event('input', { bubbles: true }));
                nameInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            
            // Fill company name
            const companyInput = document.querySelector('input[name="company_name"]');
            if (companyInput) {
                companyInput.value = data.company;
                companyInput.dispatchEvent(new Event('input', { bubbles: true }));
                companyInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            
            // Fill password
            const pwdInput = document.querySelector('input[name="password"]');
            if (pwdInput) {
                pwdInput.value = data.password;
                pwdInput.dispatchEvent(new Event('input', { bubbles: true }));
                pwdInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            
            // Fill confirm password
            const confirmPwdInput = document.querySelector('input[name="confirm_password"]');
            if (confirmPwdInput) {
                confirmPwdInput.value = data.password;
                confirmPwdInput.dispatchEvent(new Event('input', { bubbles: true }));
                confirmPwdInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }''', {
            'email': test_email,
            'name': 'FlexPay Test User',
            'company': 'FlexPay Test Corp',
            'password': test_password
        })
        
        print("   ✅ Text fields filled via JS")
        
        # Handle Industry dropdown separately
        print("   📍 Handling Industry dropdown...")
        try:
            # Try to find and click the industry select/dropdown
            industry_select = await page.query_selector('select')
            if industry_select:
                # It's a native select element
                await industry_select.select_option(index=1)  # Select first real option
                print("   ✅ Industry selected (native select)")
            else:
                # Custom dropdown - try clicking it
                industry_trigger = await page.query_selector('[class*="industry"], [class*="select"]')
                if industry_trigger:
                    await industry_trigger.click()
                    await page.wait_for_timeout(500)
                    # Look for options that appeared
                    options = await page.query_selector_all('[role="option"], [class*="option"], li[class*="item"]')
                    if options and len(options) > 0:
                        await options[0].click()
                        print("   ✅ Industry selected (custom dropdown)")
                    else:
                        print("   ⚠️ No options found in dropdown")
                else:
                    print("   ⚠️ Industry dropdown not found")
        except Exception as e:
            print(f"   ⚠️ Industry error: {e}")
        
        await page.screenshot(path="/home/z/my-project/download/v4-01-filled.png")
        print("✅ Screenshot 1: Form filled")
        
        # Step 3: Submit form
        print("\n📍 Submitting form...")
        try:
            submit_btn = await page.query_selector('button[type="submit"]')
            if submit_btn:
                await submit_btn.click()
                
                print("⏳ Waiting for account creation...")
                await page.wait_for_timeout(12000)  # Long wait for account creation + redirect
                
                current_url = page.url
                print(f"🔗 URL after submit: {current_url}")
                
                await page.screenshot(path="/home/z/my-project/download/v4-02-after-submit.png")
                print("✅ Screenshot 2: After submission")
                
        except Exception as e:
            print(f"⚠️ Submit error: {e}")
        
        # Step 4: Try to login with created credentials
        print("\n📍 Attempting login with new account...")
        try:
            await page.goto("https://parwa.buzz/login", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Fill login form
            await page.fill('input[type="email"]', test_email)
            await page.fill('input[type="password"]', test_password)
            
            # Click sign in
            signin_btn = await page.query_selector('button[type="submit"]')
            if signin_btn:
                await signin_btn.click()
                print("✅ Login attempted")
                await page.wait_for_timeout(8000)
                
                login_url = page.url
                print(f"🔗 URL after login: {login_url}")
                
                await page.screenshot(path="/home/z/my-project/download/v4-03-after-login.png")
                print("✅ Screenshot 3: After login attempt")
                
        except Exception as e:
            print(f"⚠️ Login error: {e}")
        
        # Step 5: Go to billing page
        print("\n📍 Going to Billing Page...")
        await page.goto("https://parwa.buzz/dashboard/billing", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(6000)
        
        final_url = page.url
        is_billing = "/dashboard/billing" in final_url and "/login" not in final_url
        
        print(f"🔗 Final URL: {final_url}")
        print(f"📄 On Billing: {is_billing}")
        
        await page.screenshot(path="/home/z/my-project/download/v4-04-billing.png")
        await page.screenshot(path="/home/z/my-project/download/v4-05-full-billing.png", full_page=True)
        print("✅ Screenshots 4 & 5: Billing page saved")
        
        # Content check
        content = await page.content()
        
        print("\n" + "=" * 60)
        if is_billing:
            print("🎉 SUCCESS - ON BILLING PAGE!")
            print("=" * 60)
            
            checks = [
                ("FlexPay Banner", "FlexPay Payment Plan"),
                ("$100/day info", "$100"),
                ("Day 1 features", "Day 1"),
                ("Day 11 unlock", "Day 11"),
                ("$999 pricing", "$999"),
                ("Subscribe/Activate", "Subscribe"),
            ]
            
            for name, text in checks:
                found = text in content
                print(f"  {'✅' if found else '❌'} {name}")
        else:
            print("❌ Not authenticated - on login page")
            print("=" * 60)
        
        await browser.close()
        
        print("\n" + "🎊" * 20)
        print(f"DONE! Account: {test_email} / {test_password}")
        print("🎊" * 20)

asyncio.run(create_and_test())
