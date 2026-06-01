#!/usr/bin/env python3
"""
PARWA Manual Testing with Playwright
=====================================
Acts like a real user - clicks buttons, fills forms, navigates pages.
Takes screenshots after every action for visual proof.

Tests: Landing page, Signup, Login, Onboarding flow, Dashboard
"""

import time
import os
from pathlib import Path

# Screenshot directory
SCREENSHOT_DIR = Path("/home/z/my-project/download/parwa-test-screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Counter for screenshots
shot_num = [0]

def screenshot(page, name: str) -> str:
    """Take a screenshot and return the path."""
    shot_num[0] += 1
    filename = f"{shot_num[0]:02d}-{name}.png"
    path = SCREENSHOT_DIR / filename
    page.screenshot(path=str(path), full_page=True)
    print(f"  SCREENSHOT: {path}")
    return str(path)


def test_onboarding():
    """Full onboarding test flow."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-US"
        )
        page = context.new_page()

        # Set default timeout to 30s (pages may be slow on first load)
        page.set_default_timeout(30000)

        print("\n" + "="*60)
        print("  PARWA Manual Testing - Playwright")
        print("="*60)

        # ============================================
        # TEST 1: Landing Page
        # ============================================
        print("\n[TEST 1] Landing Page (Homepage)")
        try:
            page.goto("http://localhost:3000", wait_until="networkidle", timeout=60000)
            screenshot(page, "landing-page")
            title = page.title()
            print(f"  Page title: {title}")

            # Check for key elements
            h1 = page.locator("h1").first
            if h1.is_visible():
                print(f"  H1 text: {h1.text_content()[:80]}")

            # Look for CTA buttons
            buttons = page.locator("button, a[role='button'], a[href*='signup'], a[href*='login'], a[href*='demo']")
            btn_count = buttons.count()
            print(f"  Found {btn_count} buttons/links")

            # Check for "Sign Up" or "Get Started" link
            signup_links = page.locator("a[href*='signup'], a[href*='register'], a[href*='get-started']")
            login_links = page.locator("a[href*='login'], a[href*='signin']")

            print(f"  Signup links: {signup_links.count()}")
            print(f"  Login links: {login_links.count()}")

            # Click signup if available
            if signup_links.count() > 0:
                signup_links.first.click()
                page.wait_for_load_state("networkidle", timeout=30000)
                screenshot(page, "after-click-signup-link")
            elif login_links.count() > 0:
                login_links.first.click()
                page.wait_for_load_state("networkidle", timeout=30000)
                screenshot(page, "after-click-login-link")
        except Exception as e:
            print(f"  ERROR on landing page: {e}")
            screenshot(page, "landing-page-error")

        # ============================================
        # TEST 2: Signup Page
        # ============================================
        print("\n[TEST 2] Signup Page")
        try:
            page.goto("http://localhost:3000/signup", wait_until="networkidle", timeout=60000)
            screenshot(page, "signup-page")
            title = page.title()
            print(f"  Page title: {title}")

            # Check form fields
            inputs = page.locator("input")
            print(f"  Input fields found: {inputs.count()}")

            # List all input types
            for i in range(inputs.count()):
                inp = inputs.nth(i)
                input_type = inp.get_attribute("type") or "text"
                input_name = inp.get_attribute("name") or inp.get_attribute("placeholder") or f"field-{i}"
                print(f"    [{i}] type={input_type} name={input_name}")

            # Check for Google OAuth button
            google_btn = page.locator("button:has-text('Google'), a:has-text('Google')")
            if google_btn.count() > 0:
                print(f"  Google OAuth button: FOUND")
                screenshot(page, "signup-google-button-visible")
            else:
                print(f"  Google OAuth button: NOT FOUND")
                # Check for any social login buttons
                social = page.locator("button:has-text('Google'), button:has-text('GitHub'), a:has-text('Google'), svg")
                print(f"  Social buttons found: {social.count()}")

            # Try filling out the signup form
            email_input = page.locator("input[type='email'], input[name='email'], input[placeholder*='email' i]")
            password_input = page.locator("input[type='password']")
            name_input = page.locator("input[name='name'], input[name='fullName'], input[name='full_name'], input[placeholder*='name' i]")

            if email_input.count() > 0:
                test_email = f"playwright-test-{int(time.time())}@parwa.ai"
                email_input.first.fill(test_email)
                print(f"  Filled email: {test_email}")

            if name_input.count() > 0:
                name_input.first.fill("Playwright Test User")
                print(f"  Filled name: Playwright Test User")

            if password_input.count() > 0:
                password_input.first.fill("TestPass123!")
                print(f"  Filled password: TestPass123!")

            screenshot(page, "signup-form-filled")

            # Try to submit
            submit_btn = page.locator("button[type='submit'], button:has-text('Sign Up'), button:has-text('Register'), button:has-text('Create')")
            if submit_btn.count() > 0:
                print(f"  Submit button found: {submit_btn.first.text_content()}")
                submit_btn.first.click()
                page.wait_for_load_state("networkidle", timeout=30000)
                screenshot(page, "signup-after-submit")
                print(f"  After submit URL: {page.url}")
            else:
                print(f"  Submit button NOT found")

        except Exception as e:
            print(f"  ERROR on signup page: {e}")
            screenshot(page, "signup-page-error")

        # ============================================
        # TEST 3: Login Page
        # ============================================
        print("\n[TEST 3] Login Page")
        try:
            page.goto("http://localhost:3000/login", wait_until="networkidle", timeout=60000)
            screenshot(page, "login-page")
            title = page.title()
            print(f"  Page title: {title}")

            # Check form fields
            inputs = page.locator("input")
            print(f"  Input fields found: {inputs.count()}")

            for i in range(inputs.count()):
                inp = inputs.nth(i)
                input_type = inp.get_attribute("type") or "text"
                input_name = inp.get_attribute("name") or inp.get_attribute("placeholder") or f"field-{i}"
                print(f"    [{i}] type={input_type} name={input_name}")

            # Check for Google OAuth button
            google_btn = page.locator("button:has-text('Google'), a:has-text('Google')")
            print(f"  Google OAuth button: {'FOUND' if google_btn.count() > 0 else 'NOT FOUND'}")

            # Fill login form
            email_input = page.locator("input[type='email'], input[name='email'], input[placeholder*='email' i]")
            password_input = page.locator("input[type='password']")

            if email_input.count() > 0:
                email_input.first.fill("admin@parwa.ai")
                print(f"  Filled email: admin@parwa.ai")

            if password_input.count() > 0:
                password_input.first.fill("admin123")
                print(f"  Filled password: admin123")

            screenshot(page, "login-form-filled")

            # Submit login
            submit_btn = page.locator("button[type='submit'], button:has-text('Log In'), button:has-text('Sign In'), button:has-text('Login')")
            if submit_btn.count() > 0:
                print(f"  Submit button: {submit_btn.first.text_content()}")
                submit_btn.first.click()
                page.wait_for_load_state("networkidle", timeout=30000)
                screenshot(page, "login-after-submit")
                print(f"  After login URL: {page.url}")
            else:
                print(f"  Submit button NOT found")

        except Exception as e:
            print(f"  ERROR on login page: {e}")
            screenshot(page, "login-page-error")

        # ============================================
        # TEST 4: Dashboard (if login worked)
        # ============================================
        print("\n[TEST 4] Dashboard")
        try:
            # Check if we're on the dashboard or got redirected
            current_url = page.url
            print(f"  Current URL: {current_url}")

            if "dashboard" in current_url or "welcome" in current_url:
                screenshot(page, "dashboard-or-welcome")
                print(f"  Successfully reached: {current_url}")

                # Look for dashboard elements
                nav_items = page.locator("nav a, nav button, [role='navigation'] a")
                print(f"  Navigation items: {nav_items.count()}")
            else:
                # Try navigating directly
                page.goto("http://localhost:3000/dashboard", wait_until="networkidle", timeout=30000)
                screenshot(page, "dashboard-direct")
                print(f"  Dashboard URL: {page.url}")

        except Exception as e:
            print(f"  ERROR on dashboard: {e}")
            screenshot(page, "dashboard-error")

        # ============================================
        # TEST 5: Pricing Page
        # ============================================
        print("\n[TEST 5] Pricing Page")
        try:
            page.goto("http://localhost:3000/pricing", wait_until="networkidle", timeout=30000)
            screenshot(page, "pricing-page")
            print(f"  Pricing URL: {page.url}")

            # Check for pricing cards
            cards = page.locator("[class*='card'], [class*='pricing'], [class*='plan'], [class*='tier']")
            print(f"  Pricing cards found: {cards.count()}")

        except Exception as e:
            print(f"  ERROR on pricing page: {e}")
            screenshot(page, "pricing-error")

        # ============================================
        # TEST 6: Onboarding Page
        # ============================================
        print("\n[TEST 6] Onboarding Page")
        try:
            page.goto("http://localhost:3000/onboarding", wait_until="networkidle", timeout=30000)
            screenshot(page, "onboarding-page")
            print(f"  Onboarding URL: {page.url}")

            # Check for onboarding elements
            steps = page.locator("[class*='step'], [class*='progress'], [class*='onboarding']")
            print(f"  Onboarding elements found: {steps.count()}")

        except Exception as e:
            print(f"  ERROR on onboarding page: {e}")
            screenshot(page, "onboarding-error")

        # ============================================
        # TEST 7: Jarvis Page
        # ============================================
        print("\n[TEST 7] Jarvis Page")
        try:
            page.goto("http://localhost:3000/jarvis", wait_until="networkidle", timeout=30000)
            screenshot(page, "jarvis-page")
            print(f"  Jarvis URL: {page.url}")

            # Check for chat input
            chat_input = page.locator("input[type='text'], textarea, [contenteditable]")
            print(f"  Chat inputs found: {chat_input.count()}")

        except Exception as e:
            print(f"  ERROR on jarvis page: {e}")
            screenshot(page, "jarvis-error")

        # ============================================
        # SUMMARY
        # ============================================
        print("\n" + "="*60)
        print(f"  TESTING COMPLETE!")
        print(f"  Screenshots saved to: {SCREENSHOT_DIR}")
        print(f"  Total screenshots: {shot_num[0]}")
        print("="*60)

        browser.close()


if __name__ == "__main__":
    test_onboarding()
