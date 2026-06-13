#!/usr/bin/env python3
"""
PARWA End-to-End Test with Playwright
Starts backend and frontend as subprocesses, then runs browser tests.
"""

import subprocess
import time
import os
import sys
import json
import signal
import urllib.request
import urllib.error
from pathlib import Path

SCREENSHOT_DIR = Path("/home/z/my-project/download/parwa-proof")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

backend_proc = None
frontend_proc = None

def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def wait_for_server(url, max_wait=30):
    start = time.time()
    while time.time() - start < max_wait:
        try:
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=3)
            log(f"✅ Server at {url} is ready (status {resp.status})")
            return True
        except Exception:
            time.sleep(1)
    log(f"❌ Server at {url} did not start within {max_wait}s")
    return False

def start_backend():
    global backend_proc
    log("Starting backend server...")
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///./parwa_dev.db"
    
    backend_proc = subprocess.Popen(
        ["bash", "-c", "cd /home/z/my-project/parwa/backend && source venv/bin/activate && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        preexec_fn=os.setsid,
    )
    return wait_for_server(f"{BACKEND_URL}/health", 30)

def start_frontend():
    global frontend_proc
    log("Starting frontend server...")
    
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd="/home/z/my-project/parwa",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PORT": "3000"},
        preexec_fn=os.setsid,
    )
    return wait_for_server(FRONTEND_URL, 60)

def cleanup():
    log("Cleaning up...")
    for proc in [frontend_proc, backend_proc]:
        if proc and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                proc.kill()
    log("Cleanup done.")

def test_backend_auth():
    """Test backend auth directly"""
    log("Testing backend auth endpoint...")
    try:
        data = json.dumps({"email": "test@parwa.buzz", "password": "Test1234!"}).encode()
        req = urllib.request.Request(
            f"{BACKEND_URL}/api/auth/login",
            data=data,
            headers={"Content-Type": "application/json", "Origin": "http://localhost:3000"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        log(f"✅ Backend login successful: {json.dumps(result)[:200]}")
        return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        log(f"❌ Backend login failed ({e.code}): {body[:200]}")
        return None
    except Exception as e:
        log(f"❌ Backend login error: {e}")
        return None

def run_playwright_tests():
    """Run Playwright tests using Node.js"""
    log("Running Playwright tests...")
    
    test_script = '''
const { chromium } = require('playwright');

(async () => {
  const SCREENSHOT_DIR = '/home/z/my-project/download/parwa-proof';
  const fs = require('fs');
  
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
  });
  
  const page = await context.newPage();
  
  // Collect errors
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('requestfailed', req => {
    errors.push(`FAILED: ${req.method()} ${req.url()}`);
  });
  
  function log(msg) {
    const ts = new Date().toISOString().split('T')[1].split('.')[0];
    console.log(`[${ts}] ${msg}`);
  }
  
  async function screenshot(name) {
    const path = `${SCREENSHOT_DIR}/${name}.png`;
    await page.screenshot({ path, fullPage: true });
    log(`📸 ${name}.png saved`);
  }
  
  try {
    // ── Test 1: Login Page ──
    log('TEST 1: Login Page');
    await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);
    await screenshot('01-login-page');
    
    // Find and fill login form
    const emailInput = await page.$('input[type="email"], input[name="email"], input[placeholder*="email" i]');
    const passwordInput = await page.$('input[type="password"]');
    
    if (emailInput && passwordInput) {
      await emailInput.fill('test@parwa.buzz');
      await passwordInput.fill('Test1234!');
      await screenshot('02-login-filled');
      
      // Click login
      const loginBtn = await page.$('button[type="submit"]');
      if (loginBtn) {
        await loginBtn.click();
        await page.waitForTimeout(5000);
      }
    } else {
      log('⚠️ Could not find login inputs');
      const bodyText = await page.textContent('body');
      log(`Page text: ${bodyText?.slice(0, 300)}`);
    }
    await screenshot('03-after-login');
    log(`URL after login: ${page.url()}`);
    
    // ── Test 2: Set pricing context and go to onboarding ──
    log('TEST 2: Navigate to Onboarding');
    await page.evaluate(() => {
      localStorage.setItem('parwa_pricing_context', JSON.stringify({
        industry: 'saas',
        variant: 'parwa',
        variants: ['parwa'],
        totalMonthly: 299,
        timestamp: new Date().toISOString(),
      }));
    });
    
    await page.goto('http://localhost:3000/onboarding?source=pricing&industry=saas', { 
      waitUntil: 'networkidle', 
      timeout: 30000 
    });
    await page.waitForTimeout(3000);
    await screenshot('04-onboarding-page');
    
    // Check page content
    const bodyText = await page.textContent('body');
    log(`Onboarding page: ${bodyText?.slice(0, 300)}`);
    
    // Check for errors
    if (bodyText?.includes('something went wrong') || bodyText?.includes('Something went wrong')) {
      log('❌ "Something went wrong" found on onboarding page!');
    }
    
    // ── Test 3: Step through Onboarding ──
    log('TEST 3: Step through Onboarding Wizard');
    
    // Try to find and interact with industry selection
    const allButtons = await page.$$('button');
    for (const btn of allButtons) {
      const text = await btn.textContent();
      if (text && text.includes('SaaS')) {
        log('Clicking SaaS industry');
        await btn.click();
        await page.waitForTimeout(1000);
        break;
      }
    }
    await screenshot('05-industry-selection');
    
    // Find variant selection
    const allButtons2 = await page.$$('button, [role="button"]');
    for (const btn of allButtons2) {
      const text = await btn.textContent();
      if (text && (text.includes('PARWA') || text.includes('Growth'))) {
        log(`Clicking variant: ${text.trim().slice(0, 50)}`);
        await btn.click();
        await page.waitForTimeout(1000);
        break;
      }
    }
    await screenshot('06-variant-selection');
    
    // Click Continue/Next buttons through each step
    for (let step = 0; step < 6; step++) {
      const continueBtns = await page.$$('button');
      let clicked = false;
      for (const btn of continueBtns) {
        const text = await btn.textContent();
        const isEnabled = await btn.isEnabled();
        if (isEnabled && text && (
          text.includes('Continue') || 
          text.includes('Next') || 
          text.includes('Accept') ||
          text.includes('Activate') ||
          text.includes('Confirm') ||
          text.includes('Complete') ||
          text.includes('Get Started')
        )) {
          log(`Step ${step}: Clicking "${text.trim().slice(0, 50)}"`);
          await btn.click();
          await page.waitForTimeout(3000);
          await screenshot(`07-step-${step + 1}-completed`);
          clicked = true;
          break;
        }
      }
      if (!clicked) {
        log(`Step ${step}: No continue button found`);
        await screenshot(`07-step-${step + 1}-no-button`);
        // Try checkboxes first
        const checkboxes = await page.$$('input[type="checkbox"]');
        for (const cb of checkboxes) {
          await cb.click().catch(() => {});
          await page.waitForTimeout(500);
        }
        if (checkboxes.length > 0) {
          await screenshot(`07-step-${step + 1}-checkboxes-checked`);
          // Try continue again
          const continueBtns2 = await page.$$('button');
          for (const btn of continueBtns2) {
            const text = await btn.textContent();
            const isEnabled = await btn.isEnabled();
            if (isEnabled && text && (text.includes('Continue') || text.includes('Accept') || text.includes('Agree'))) {
              await btn.click();
              await page.waitForTimeout(3000);
              await screenshot(`07-step-${step + 1}-after-checkbox-continue`);
              break;
            }
          }
        }
      }
    }
    
    await screenshot('08-final-state');
    
    // ── Test 4: Check for "something went wrong" ──
    log('TEST 4: Check for errors');
    const finalText = await page.textContent('body');
    if (finalText?.includes('something went wrong') || finalText?.includes('Something went wrong')) {
      log('❌ "Something went wrong" detected!');
    } else {
      log('✅ No "Something went wrong" error detected');
    }
    
    log(`Final URL: ${page.url()}`);
    log(`Errors collected: ${errors.length}`);
    errors.forEach(e => log(`  ${e}`));
    
  } catch (err) {
    log(`❌ Test error: ${err.message}`);
    await screenshot('error-state').catch(() => {});
  } finally {
    await browser.close();
  }
})();
'''
    
    # Write test script
    test_path = "/home/z/my-project/parwa/run_pw_test.cjs"
    with open(test_path, "w") as f:
        f.write(test_script)
    
    result = subprocess.run(
        ["node", "run_pw_test.cjs"],
        cwd="/home/z/my-project/parwa",
        capture_output=True,
        text=True,
        timeout=120,
    )
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[:2000])
    
    return result.returncode == 0

if __name__ == "__main__":
    try:
        # Start backend
        backend_ok = start_backend()
        if not backend_ok:
            log("⚠️  Backend not reachable, but continuing (BFF has mock fallbacks)")
        
        # Test backend directly
        if backend_ok:
            test_backend_auth()
        
        # Start frontend
        frontend_ok = start_frontend()
        if not frontend_ok:
            log("❌ Frontend failed to start")
            cleanup()
            sys.exit(1)
        
        # Run Playwright tests
        run_playwright_tests()
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup()
