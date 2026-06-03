#!/usr/bin/env python3
"""
PARWA Full Onboarding Test - Playwright (Browser-based)
========================================================
Acts like a real user with a real browser. CSRF cookies handled automatically.
Takes screenshots after every interaction.
"""

import time
import os
from pathlib import Path

SCREENSHOT_DIR = Path("/home/z/my-project/download/parwa-test-screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

shot_num = [0]

def screenshot(page, name: str) -> str:
    shot_num[0] += 1
    filename = f"{shot_num[0]:02d}-{name}.png"
    path = SCREENSHOT_DIR / filename
    page.screenshot(path=str(path), full_page=True)
    print(f"  📸 SCREENSHOT: {path}")
    return str(path)


def test_onboarding():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-US"
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        print("\n" + "="*60)
        print("  PARWA Onboarding Test — Playwright")
        print("="*60)

        # =============================================
        # 1. LANDING PAGE
        # =============================================
        print("\n[1/8] 🏠 Landing Page")
        try:
            page.goto("http://localhost:3000", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=60000)
            screenshot(page, "landing-page")
            print(f"  Title: {page.title()}")
            print(f"  URL: {page.url}")
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            screenshot(page, "landing-error")

        # =============================================
        # 2. SIGNUP PAGE
        # =============================================
        print("\n[2/8] 📝 Signup Page")
        try:
            page.goto("http://localhost:3000/signup", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=30000)
            screenshot(page, "signup-page")

            # Check Google OAuth button
            google_btn = page.locator("button:has-text('Google'), a:has-text('Google')")
            print(f"  Google OAuth button: {'✅ FOUND' if google_btn.count() > 0 else '❌ NOT FOUND'}")

            # Fill signup form
            email_input = page.locator("input[name='email']")
            name_input = page.locator("input[name='full_name']")
            company_input = page.locator("input[name='company_name']")
            password_input = page.locator("input[name='password']")
            confirm_input = page.locator("input[name='confirm_password']")

            test_email = f"testuser{int(time.time())}@parwa.ai"

            if email_input.count() > 0:
                email_input.first.fill(test_email)
                print(f"  ✅ Filled email: {test_email}")
            if name_input.count() > 0:
                name_input.first.fill("Test User")
                print(f"  ✅ Filled name: Test User")
            if company_input.count() > 0:
                company_input.first.fill("Test Company")
                print(f"  ✅ Filled company: Test Company")
            if password_input.count() > 0:
                password_input.first.fill("TestPass123!")
                print(f"  ✅ Filled password")
            if confirm_input.count() > 0:
                confirm_input.first.fill("TestPass123!")
                print(f"  ✅ Filled confirm password")

            # Select industry if dropdown exists
            industry_select = page.locator("select, [role='combobox']")
            if industry_select.count() > 0:
                try:
                    industry_select.first.select_option(value="technology")
                    print(f"  ✅ Selected industry: technology")
                except:
                    pass

            screenshot(page, "signup-form-filled")

            # Click Create Account
            submit_btn = page.locator("button:has-text('Create account'), button[type='submit']")
            if submit_btn.count() > 0:
                print(f"  Clicking: {submit_btn.first.text_content()}")
                submit_btn.first.click()
                
                # Wait for response (could be success or error)
                time.sleep(5)
                page.wait_for_load_state("networkidle", timeout=30000)
                screenshot(page, "signup-after-submit")
                print(f"  URL after signup: {page.url}")

                # Check for error messages
                error_msg = page.locator("[class*='error'], [class*='alert'], [role='alert'], .text-red, .text-destructive")
                if error_msg.count() > 0:
                    print(f"  ⚠️ Error message: {error_msg.first.text_content()[:200]}")
                else:
                    print(f"  No error messages visible")
            else:
                print(f"  ❌ Submit button not found")

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            screenshot(page, "signup-error")

        # =============================================
        # 3. LOGIN PAGE  
        # =============================================
        print("\n[3/8] 🔐 Login Page")
        try:
            page.goto("http://localhost:3000/login", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=30000)
            screenshot(page, "login-page")

            # Check Google OAuth button
            google_btn = page.locator("button:has-text('Google'), a:has-text('Google')")
            print(f"  Google OAuth button: {'✅ FOUND' if google_btn.count() > 0 else '❌ NOT FOUND'}")
            if google_btn.count() > 0:
                screenshot(page, "login-google-button")

            # Fill login form
            email_input = page.locator("input[name='email'], input[type='email']")
            password_input = page.locator("input[type='password']")

            if email_input.count() > 0:
                email_input.first.fill("admin@parwa.ai")
                print(f"  ✅ Filled email: admin@parwa.ai")
            if password_input.count() > 0:
                password_input.first.fill("admin123")
                print(f"  ✅ Filled password")

            screenshot(page, "login-form-filled")

            # Click Sign In
            submit_btn = page.locator("button:has-text('Sign in'), button[type='submit']")
            if submit_btn.count() > 0:
                print(f"  Clicking: {submit_btn.first.text_content()}")
                submit_btn.first.click()
                
                # Wait longer for auth to complete
                time.sleep(8)
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except:
                    pass
                screenshot(page, "login-after-submit")
                print(f"  URL after login: {page.url}")

                # Check for error
                error_msg = page.locator("[class*='error'], [class*='alert'], [role='alert'], .text-red, .text-destructive")
                if error_msg.count() > 0:
                    print(f"  ⚠️ Error: {error_msg.first.text_content()[:200]}")
                
                # Check if we got redirected to dashboard/welcome
                if "dashboard" in page.url or "welcome" in page.url or "onboarding" in page.url:
                    print(f"  ✅ LOGIN SUCCESS! Redirected to: {page.url}")
                else:
                    print(f"  ⚠️ Still on login page - login may have failed")

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            screenshot(page, "login-error")

        # =============================================
        # 4. DASHBOARD (try direct navigation)
        # =============================================
        print("\n[4/8] 📊 Dashboard Page")
        try:
            page.goto("http://localhost:3000/dashboard", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=30000)
            screenshot(page, "dashboard-page")
            print(f"  URL: {page.url}")

            if "login" in page.url:
                print(f"  ⚠️ Redirected to login - need to authenticate first")
            elif "dashboard" in page.url:
                print(f"  ✅ Dashboard loaded!")

                # Check for dashboard elements
                nav = page.locator("nav")
                cards = page.locator("[class*='card'], [class*='Card']")
                charts = page.locator("canvas, svg, [class*='chart'], [class*='Chart']")
                print(f"  Nav: {nav.count()}, Cards: {cards.count()}, Charts: {charts.count()}")

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            screenshot(page, "dashboard-error")

        # =============================================
        # 5. PRICING PAGE
        # =============================================
        print("\n[5/8] 💰 Pricing Page")
        try:
            page.goto("http://localhost:3000/pricing", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=30000)
            screenshot(page, "pricing-page")
            print(f"  URL: {page.url}")

            # Try clicking an industry card
            industry_cards = page.locator("[class*='card'], [class*='Card'], button:has-text('E-commerce'), button:has-text('SaaS')")
            if industry_cards.count() > 0:
                print(f"  Found {industry_cards.count()} industry cards")
                # Click the first one
                industry_cards.first.click()
                time.sleep(2)
                page.wait_for_load_state("networkidle", timeout=15000)
                screenshot(page, "pricing-after-select")

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            screenshot(page, "pricing-error")

        # =============================================
        # 6. ROI CALCULATOR
        # =============================================
        print("\n[6/8] 📈 ROI Calculator")
        try:
            page.goto("http://localhost:3000/roi-calculator", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=30000)
            screenshot(page, "roi-calculator")
            print(f"  URL: {page.url}")
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            screenshot(page, "roi-error")

        # =============================================
        # 7. MODELS PAGE
        # =============================================
        print("\n[7/8] 🤖 Models Page")
        try:
            page.goto("http://localhost:3000/models", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=30000)
            screenshot(page, "models-page")
            print(f"  URL: {page.url}")
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            screenshot(page, "models-error")

        # =============================================
        # 8. JARVIS PAGE
        # =============================================
        print("\n[8/8] 🧠 Jarvis Page")
        try:
            page.goto("http://localhost:3000/jarvis", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=30000)
            screenshot(page, "jarvis-page")
            print(f"  URL: {page.url}")
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            screenshot(page, "jarvis-error")

        # =============================================
        # SUMMARY
        # =============================================
        print("\n" + "="*60)
        print(f"  TESTING COMPLETE!")
        print(f"  📸 Screenshots: {SCREENSHOT_DIR}")
        print(f"  Total screenshots: {shot_num[0]}")
        print("="*60)

        browser.close()


if __name__ == "__main__":
    test_onboarding()
