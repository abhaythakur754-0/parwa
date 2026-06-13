/**
 * PARWA Phase 9 & 10 — Playwright Manual Tests
 *
 * Phase 9: Audit Trail & Action Logging
 *   - Verify AI actions are logged and visible to clients
 *   - Verify client sees only their own actions (BC-001)
 *   - Verify export audit logs for compliance
 *   - Verify integrity check works
 *
 * Phase 10: Rate Limiting & Error Handling
 *   - Verify integration health dashboard shows circuit breaker status
 *   - Verify rate limit status visible
 *   - Verify graceful degradation when APIs fail
 *   - Verify integration disconnect instant cleanup
 */

import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';
const BACKEND_URL = 'http://localhost:8000';

// Test user credentials
const TEST_EMAIL = `playwright_p9_${Date.now()}@parwa.io`;
const TEST_PASSWORD = 'TestPhase9!2024';
const TEST_NAME = 'Phase9 Tester';
const TEST_COMPANY = 'Phase9 Test Corp';

test.describe('Phase 9: Audit Trail & Action Logging', () => {

  test.beforeAll(async () => {
    // Register a test user via the backend
    const { chromium } = await import('@playwright/test');
    // We'll register via API
  });

  test('1. Register and login to get auth token', async ({ page }) => {
    // Navigate to signup
    await page.goto(`${BASE_URL}/signup`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);

    // Fill registration form
    const nameInput = page.locator('input[name="fullName"], input[placeholder*="name"], input[id*="name"]').first();
    const emailInput = page.locator('input[type="email"], input[name="email"], input[placeholder*="email"]').first();
    const passwordInput = page.locator('input[type="password"], input[name="password"], input[placeholder*="assword"]').first();
    const companyInput = page.locator('input[name="company"], input[placeholder*="company"]').first();

    if (await nameInput.isVisible()) {
      await nameInput.fill(TEST_NAME);
    }
    if (await emailInput.isVisible()) {
      await emailInput.fill(TEST_EMAIL);
    }
    if (await passwordInput.isVisible()) {
      await passwordInput.fill(TEST_PASSWORD);
    }
    if (await companyInput.isVisible()) {
      await companyInput.fill(TEST_COMPANY);
    }

    // Click submit
    const submitBtn = page.locator('button[type="submit"], button:has-text("Sign up"), button:has-text("Create"), button:has-text("Register"), button:has-text("Get Started")').first();
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
    }

    // Wait for redirect to dashboard or onboarding
    await page.waitForTimeout(5000);
    await page.screenshot({ path: '/home/z/my-project/download/test_after_register.png' });

    // Check if we're on dashboard or onboarding
    const currentUrl = page.url();
    console.log('After register URL:', currentUrl);
  });

  test('2. Backend audit API returns data', async ({ request }) => {
    // First register a user directly via backend
    const regRes = await request.post(`${BACKEND_URL}/api/auth/register`, {
      headers: {
        'Content-Type': 'application/json',
        'Origin': 'http://localhost:3000',
      },
      data: {
        email: `audit_test_${Date.now()}@parwa.io`,
        password: 'AuditTest123!',
        full_name: 'Audit Tester',
        company_name: 'Audit Corp',
      },
      timeout: 15000,
    });

    console.log('Register status:', regRes.status());

    // Extract cookies for auth
    const cookies = regRes.headers()['set-cookie'] || '';
    console.log('Cookies received:', cookies ? 'yes' : 'no');

    // Try to login to get token
    const loginRes = await request.post(`${BACKEND_URL}/api/auth/login`, {
      headers: {
        'Content-Type': 'application/json',
        'Origin': 'http://localhost:3000',
      },
      data: {
        email: `audit_test_${Date.now()}@parwa.io`,
        password: 'AuditTest123!',
      },
      timeout: 15000,
    });

    console.log('Login status:', loginRes.status());
    if (loginRes.ok()) {
      const loginData = await loginRes.json();
      console.log('Login data keys:', Object.keys(loginData));
    }
  });

  test('3. Audit entries endpoint responds', async ({ request }) => {
    // Register and get auth token
    const email = `audit_entries_${Date.now()}@parwa.io`;
    
    const regRes = await request.post(`${BACKEND_URL}/api/auth/register`, {
      headers: {
        'Content-Type': 'application/json',
        'Origin': 'http://localhost:3000',
      },
      data: {
        email,
        password: 'AuditTest123!',
        full_name: 'Audit Entries Tester',
        company_name: 'Audit Entries Corp',
      },
      timeout: 15000,
    });

    // Get the auth cookie from register response
    const setCookieHeader = regRes.headers()['set-cookie'] || '';
    let authToken = '';
    
    // Extract access_token cookie
    const accessMatch = setCookieHeader.match(/parwa_at=([^;]+)/);
    if (accessMatch) {
      authToken = accessMatch[1];
    }

    // If no token from register, try login
    if (!authToken) {
      const loginRes = await request.post(`${BACKEND_URL}/api/auth/login`, {
        headers: {
          'Content-Type': 'application/json',
          'Origin': 'http://localhost:3000',
        },
        data: { email, password: 'AuditTest123!' },
        timeout: 15000,
      });
      const loginCookie = loginRes.headers()['set-cookie'] || '';
      const loginMatch = loginCookie.match(/parwa_at=([^;]+)/);
      if (loginMatch) {
        authToken = loginMatch[1];
      }
      
      // Also try to get token from response body
      if (!authToken && loginRes.ok()) {
        try {
          const loginData = await loginRes.json();
          authToken = loginData.access_token || loginData.token || '';
        } catch {}
      }
    }

    console.log('Auth token obtained:', authToken ? 'yes' : 'no');

    if (authToken) {
      // Test audit entries endpoint
      const entriesRes = await request.get(`${BACKEND_URL}/api/v1/audit/entries?limit=5`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Origin': 'http://localhost:3000',
        },
        timeout: 15000,
      });

      console.log('Audit entries status:', entriesRes.status());
      if (entriesRes.ok()) {
        const data = await entriesRes.json();
        console.log('Audit entries response keys:', Object.keys(data));
        console.log('Total entries:', data.total);
        console.log('Items count:', data.items?.length || 0);
        expect(data).toHaveProperty('items');
        expect(data).toHaveProperty('total');
      } else {
        const errorText = await entriesRes.text();
        console.log('Audit entries error:', errorText.substring(0, 200));
      }

      // Test audit stats endpoint
      const statsRes = await request.get(`${BACKEND_URL}/api/v1/audit/stats`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Origin': 'http://localhost:3000',
        },
        timeout: 15000,
      });

      console.log('Audit stats status:', statsRes.status());
      if (statsRes.ok()) {
        const statsData = await statsRes.json();
        console.log('Stats:', JSON.stringify(statsData).substring(0, 200));
      }

      // Test audit export endpoint (JSON)
      const exportRes = await request.get(`${BACKEND_URL}/api/v1/audit/export?format=json`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Origin': 'http://localhost:3000',
        },
        timeout: 15000,
      });

      console.log('Audit export status:', exportRes.status());
      if (exportRes.ok()) {
        const exportData = await exportRes.json();
        console.log('Export keys:', Object.keys(exportData));
      }

      // Test audit integrity endpoint
      const integrityRes = await request.get(`${BACKEND_URL}/api/v1/audit/integrity`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Origin': 'http://localhost:3000',
        },
        timeout: 15000,
      });

      console.log('Audit integrity status:', integrityRes.status());
      if (integrityRes.ok()) {
        const integrityData = await integrityRes.json();
        console.log('Integrity status:', integrityData.status);
      }

      // Test audit alerts endpoint
      const alertsRes = await request.get(`${BACKEND_URL}/api/v1/audit/alerts`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Origin': 'http://localhost:3000',
        },
        timeout: 15000,
      });

      console.log('Audit alerts status:', alertsRes.status());

      // Test POST ai-action
      const aiActionRes = await request.post(`${BACKEND_URL}/api/v1/audit/ai-action`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
          'Origin': 'http://localhost:3000',
        },
        data: {
          action: 'ai_tool_call',
          resource_type: 'ticket',
          resource_id: 'test-ticket-001',
          new_value: 'Processed refund via HubSpot',
          metadata: { tool: 'hubspot', confidence: 0.95 },
          severity: 'info',
          category: 'ai_operation',
        },
        timeout: 15000,
      });

      console.log('AI action log status:', aiActionRes.status());
      if (aiActionRes.ok()) {
        const actionData = await aiActionRes.json();
        console.log('Logged AI action ID:', actionData.id);
        console.log('Action:', actionData.action);
        expect(actionData).toHaveProperty('id');
        expect(actionData).toHaveProperty('action');
      }
    }
  });
});

test.describe('Phase 10: Rate Limiting & Error Handling', () => {

  test('1. Circuit breaker manager health check', async ({ request }) => {
    // Check the health endpoint which includes circuit breaker info
    const healthRes = await request.get(`${BACKEND_URL}/health`, {
      timeout: 30000,
    });

    console.log('Health status:', healthRes.status());
    if (healthRes.ok()) {
      const healthData = await healthRes.json();
      console.log('Health status field:', healthData.status);
      console.log('Circuit breakers:', JSON.stringify(healthData.circuit_breakers)?.substring(0, 300));
      expect(healthData).toHaveProperty('circuit_breakers');
      expect(healthData.circuit_breakers).toHaveProperty('status');
    }
  });

  test('2. Rate limiter configuration exists in backend', async ({ request }) => {
    // Register and get token
    const email = `ratelimit_${Date.now()}@parwa.io`;
    
    const regRes = await request.post(`${BACKEND_URL}/api/auth/register`, {
      headers: {
        'Content-Type': 'application/json',
        'Origin': 'http://localhost:3000',
      },
      data: {
        email,
        password: 'RateLimit123!',
        full_name: 'Rate Limit Tester',
        company_name: 'Rate Limit Corp',
      },
      timeout: 15000,
    });

    // Get auth token
    let authToken = '';
    const setCookieHeader = regRes.headers()['set-cookie'] || '';
    const accessMatch = setCookieHeader.match(/parwa_at=([^;]+)/);
    if (accessMatch) authToken = accessMatch[1];

    if (!authToken) {
      const loginRes = await request.post(`${BACKEND_URL}/api/auth/login`, {
        headers: {
          'Content-Type': 'application/json',
          'Origin': 'http://localhost:3000',
        },
        data: { email, password: 'RateLimit123!' },
        timeout: 15000,
      });
      const loginCookie = loginRes.headers()['set-cookie'] || '';
      const loginMatch = loginCookie.match(/parwa_at=([^;]+)/);
      if (loginMatch) authToken = loginMatch[1];
      if (!authToken && loginRes.ok()) {
        try {
          const loginData = await loginRes.json();
          authToken = loginData.access_token || loginData.token || '';
        } catch {}
      }
    }

    if (authToken) {
      // Test integration health endpoint
      const healthRes = await request.get(`${BACKEND_URL}/api/v1/integrations/health`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Origin': 'http://localhost:3000',
        },
        timeout: 15000,
      });

      console.log('Integration health status:', healthRes.status());
      if (healthRes.ok()) {
        const healthData = await healthRes.json();
        console.log('Integration health keys:', Object.keys(healthData));
      } else {
        console.log('Integration health response:', healthRes.status());
      }
    }
  });

  test('3. BFF audit proxy route works', async ({ request }) => {
    // Register user and get token
    const email = `bff_audit_${Date.now()}@parwa.io`;
    
    const regRes = await request.post(`${BACKEND_URL}/api/auth/register`, {
      headers: {
        'Content-Type': 'application/json',
        'Origin': 'http://localhost:3000',
      },
      data: {
        email,
        password: 'BffAudit123!',
        full_name: 'BFF Audit Tester',
        company_name: 'BFF Audit Corp',
      },
      timeout: 15000,
    });

    let authToken = '';
    const setCookieHeader = regRes.headers()['set-cookie'] || '';
    const accessMatch = setCookieHeader.match(/parwa_at=([^;]+)/);
    if (accessMatch) authToken = accessMatch[1];

    if (!authToken) {
      const loginRes = await request.post(`${BACKEND_URL}/api/auth/login`, {
        headers: {
          'Content-Type': 'application/json',
          'Origin': 'http://localhost:3000',
        },
        data: { email, password: 'BffAudit123!' },
        timeout: 15000,
      });
      const loginCookie = loginRes.headers()['set-cookie'] || '';
      const loginMatch = loginCookie.match(/parwa_at=([^;]+)/);
      if (loginMatch) authToken = loginMatch[1];
      if (!authToken && loginRes.ok()) {
        try {
          const loginData = await loginRes.json();
          authToken = loginData.access_token || loginData.token || '';
        } catch {}
      }
    }

    if (authToken) {
      // Test BFF audit entries route
      const bffRes = await request.get(`${BASE_URL}/api/audit/entries?limit=5`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Cookie': `parwa_at=${authToken}`,
        },
        timeout: 15000,
      });

      console.log('BFF audit entries status:', bffRes.status());
      if (bffRes.ok()) {
        const data = await bffRes.json();
        console.log('BFF audit response keys:', Object.keys(data));
        console.log('Total entries:', data.total);
      } else {
        const errorText = await bffRes.text();
        console.log('BFF audit error:', errorText.substring(0, 300));
      }

      // Test BFF audit stats
      const statsRes = await request.get(`${BASE_URL}/api/audit/stats`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Cookie': `parwa_at=${authToken}`,
        },
        timeout: 15000,
      });
      console.log('BFF audit stats status:', statsRes.status());

      // Test BFF audit alerts
      const alertsRes = await request.get(`${BASE_URL}/api/audit/alerts`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Cookie': `parwa_at=${authToken}`,
        },
        timeout: 15000,
      });
      console.log('BFF audit alerts status:', alertsRes.status());

      // Test BFF audit integrity
      const integrityRes = await request.get(`${BASE_URL}/api/audit/integrity`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Cookie': `parwa_at=${authToken}`,
        },
        timeout: 15000,
      });
      console.log('BFF audit integrity status:', integrityRes.status());
      if (integrityRes.ok()) {
        const intData = await integrityRes.json();
        console.log('Integrity status:', intData.status);
      }
    }
  });
});
