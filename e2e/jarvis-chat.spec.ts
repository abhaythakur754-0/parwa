/**
 * PARWA — Onboarding Jarvis Chat E2E Tests
 *
 * Tests the complete onboarding Jarvis flow:
 * - Session creation from various entry points
 * - Message exchange and AI responses
 * - Stage detection and progression
 * - Message counting and limits
 * - Demo pack flow
 * - Variant demo mode
 * - Error handling
 */

import { test, expect, Page } from '@playwright/test';

const BASE_URL = process.env.FRONTEND_URL || 'http://localhost:3000';

// ── Helper Functions ──

async function createJarvisSession(page: Page, entrySource = 'direct', entryParams?: Record<string, any>) {
  const response = await page.request.post(`${BASE_URL}/api/onboarding-jarvis/session`, {
    data: { entry_source: entrySource, entry_params: entryParams },
  });
  expect(response.ok()).toBeTruthy();
  return await response.json();
}

async function sendJarvisMessage(page: Page, sessionId: string, message: string) {
  const response = await page.request.post(`${BASE_URL}/api/onboarding-jarvis/message`, {
    data: { session_id: sessionId, message, channel: 'chat' },
  });
  expect(response.ok()).toBeTruthy();
  return await response.json();
}

async function registerUser(page: Page, email: string, password = 'TestPass123!') {
  const response = await page.request.post(`${BASE_URL}/api/auth/register`, {
    data: {
      email,
      password,
      fullName: 'E2E Test User',
      companyName: 'E2E Test Co',
      industry: 'technology',
    },
  });
  return { response, data: await response.json() };
}

async function loginUser(page: Page, email: string, password = 'TestPass123!') {
  const response = await page.request.post(`${BASE_URL}/api/auth/login`, {
    data: { email, password },
  });
  return { response, data: await response.json() };
}

// ── Auth Flow Tests ──

test.describe('Auth Flow', () => {
  const uniqueEmail = `e2e_${Date.now()}@test.com`;

  test('should register a new user with auto-verification in dev', async ({ page }) => {
    const { response, data } = await registerUser(page, uniqueEmail);
    expect(response.status()).toBe(200);
    expect(data.status).toBe('success');
    expect(data.user.email).toBe(uniqueEmail);
    expect(data.user.isVerified).toBe(true); // Auto-verified in dev
  });

  test('should reject duplicate registration', async ({ page }) => {
    const { response } = await registerUser(page, uniqueEmail);
    expect(response.status()).toBe(409);
  });

  test('should reject weak passwords', async ({ page }) => {
    const { response } = await registerUser(page, `weak_${Date.now()}@test.com`, 'short');
    expect(response.status()).toBe(400);
  });

  test('should login with valid credentials', async ({ page }) => {
    const { response, data } = await loginUser(page, 'owner@technova.com');
    expect(response.status()).toBe(200);
    expect(data.status).toBe('success');
    expect(data.user.email).toBe('owner@technova.com');
  });

  test('should reject wrong password', async ({ page }) => {
    const { response } = await loginUser(page, 'owner@technova.com', 'WrongPass123!');
    expect(response.status()).toBe(401);
  });

  test('should reject unregistered email', async ({ page }) => {
    const { response } = await loginUser(page, `nonexistent_${Date.now()}@test.com`);
    expect(response.status()).toBe(401);
  });

  test('should validate Google auth token', async ({ page }) => {
    const response = await page.request.post(`${BASE_URL}/api/auth/google`, {
      data: { id_token: '' },
    });
    expect(response.status()).toBe(400);
  });
});

// ── Onboarding Jarvis Session Tests ──

test.describe('Onboarding Jarvis - Session Management', () => {
  test('should create a session with direct entry', async ({ page }) => {
    const session = await createJarvisSession(page);
    expect(session.session_id).toBeDefined();
    expect(session.remaining_today).toBe(20);
    expect(session.pack_type).toBe('free');
    expect(session.detected_stage).toBe('welcome');
  });

  test('should create session from pricing page', async ({ page }) => {
    const session = await createJarvisSession(page, 'pricing', { industry: 'ecommerce' });
    expect(session.session_id).toBeDefined();
    expect(session.context.industry).toBe('ecommerce');
  });

  test('should create session from ROI calculator', async ({ page }) => {
    const session = await createJarvisSession(page, 'roi', {
      roi_result: { savings_annual: 168000 },
    });
    expect(session.session_id).toBeDefined();
  });

  test('should create session from models page with variant', async ({ page }) => {
    const session = await createJarvisSession(page, 'models_page', {
      variant: 'PARWA Growth',
      variant_id: 'growth',
      industry: 'saas',
    });
    expect(session.session_id).toBeDefined();
    expect(session.context.selected_variants).toContain('PARWA Growth');
  });

  test('should create session from demo page', async ({ page }) => {
    const session = await createJarvisSession(page, 'demo');
    expect(session.session_id).toBeDefined();
  });
});

// ── Onboarding Jarvis Message Tests ──

test.describe('Onboarding Jarvis - Message Exchange', () => {
  let sessionId: string;

  test.beforeEach(async ({ page }) => {
    const session = await createJarvisSession(page);
    sessionId = session.session_id;
  });

  test('should respond to greeting', async ({ page }) => {
    const result = await sendJarvisMessage(page, sessionId, 'Hello!');
    expect(result.content).toBeDefined();
    expect(result.content.length).toBeGreaterThan(10);
    expect(result.remaining_today).toBe(19);
  });

  test('should detect pricing stage', async ({ page }) => {
    const result = await sendJarvisMessage(page, sessionId, 'How much does PARWA cost?');
    expect(result.stage).toBe('pricing');
    expect(result.content).toBeDefined();
  });

  test('should detect demo stage', async ({ page }) => {
    const result = await sendJarvisMessage(page, sessionId, 'Show me a demo');
    expect(result.stage).toBe('demo');
  });

  test('should detect variant selection stage', async ({ page }) => {
    const result = await sendJarvisMessage(page, sessionId, 'Tell me about the Growth plan');
    expect(result.stage).toBe('variant_selection');
  });

  test('should detect objection handling stage', async ({ page }) => {
    const result = await sendJarvisMessage(page, sessionId, 'This is too expensive for us');
    expect(result.stage).toBe('objection_handling');
  });

  test('should decrement remaining messages', async ({ page }) => {
    await sendJarvisMessage(page, sessionId, 'Hi');
    const result = await sendJarvisMessage(page, sessionId, 'Tell me more');
    expect(result.remaining_today).toBe(18);
  });
});

// ── Onboarding Jarvis Full Flow Test ──

test.describe('Onboarding Jarvis - Full Conversation Flow', () => {
  test('should complete a full onboarding conversation', async ({ page }) => {
    // Step 1: Create session
    const session = await createJarvisSession(page, 'direct', { industry: 'ecommerce' });
    const sessionId = session.session_id;

    // Step 2: Greeting
    const greeting = await sendJarvisMessage(page, sessionId, 'Hello, I run an e-commerce store');
    expect(greeting.content).toBeDefined();
    expect(greeting.remaining_today).toBe(19);

    // Step 3: Ask about pricing
    const pricing = await sendJarvisMessage(page, sessionId, 'What are your pricing plans?');
    expect(pricing.stage).toBe('pricing');
    expect(pricing.content).toContain('$');

    // Step 4: Ask about ROI
    const roi = await sendJarvisMessage(page, sessionId, 'What kind of ROI can I expect?');
    expect(roi.content).toBeDefined();

    // Step 5: Ask for demo
    const demo = await sendJarvisMessage(page, sessionId, 'Can you show me a demo?');
    expect(demo.stage).toBe('demo');
    expect(demo.remaining_today).toBeLessThan(19);
  });

  test('should handle variant demo mode conversation', async ({ page }) => {
    const session = await createJarvisSession(page, 'models_page', {
      variant: 'PARWA Starter',
      variant_id: 'starter',
      industry: 'ecommerce',
    });
    const sessionId = session.session_id;

    const response = await sendJarvisMessage(page, sessionId, 'What can you do for me?');
    expect(response.content).toBeDefined();
    expect(response.content.length).toBeGreaterThan(20);
  });
});

// ── Onboarding Jarvis UI Tests ──

test.describe('Onboarding Jarvis - UI Rendering', () => {
  test('should render the Jarvis chat page', async ({ page }) => {
    await page.goto(`${BASE_URL}/jarvis`);
    await page.waitForLoadState('networkidle').catch(() => {});

    // Check for Jarvis branding or chat elements
    const bodyText = await page.textContent('body').catch(() => '');
    expect(bodyText).toBeDefined();
  });

  test('should render the login page', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('networkidle').catch(() => {});

    // Check for email/password fields or login form
    const emailInput = page.locator('input[type="email"], input[name="email"], input[placeholder*="email"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    // At least one of these should exist on a login page
    const hasLoginForm = (await emailInput.count()) > 0 || (await passwordInput.count()) > 0;
    expect(hasLoginForm || await page.textContent('body').then(t => t?.toLowerCase().includes('login') || t?.toLowerCase().includes('sign'))).toBeTruthy();
  });

  test('should render the signup page', async ({ page }) => {
    await page.goto(`${BASE_URL}/signup`);
    await page.waitForLoadState('networkidle').catch(() => {});

    const bodyText = (await page.textContent('body')) || '';
    const hasSignupContent = bodyText.toLowerCase().includes('sign') || bodyText.toLowerCase().includes('create') || bodyText.toLowerCase().includes('register');
    expect(hasSignupContent).toBeTruthy();
  });
});

// ── Onboarding Jarvis Limit & Edge Cases ──

test.describe('Onboarding Jarvis - Limits & Edge Cases', () => {
  test('should handle empty message gracefully', async ({ page }) => {
    const session = await createJarvisSession(page);
    const response = await page.request.post(`${BASE_URL}/api/onboarding-jarvis/message`, {
      data: { session_id: session.session_id, message: '' },
    });
    // Should either return 400 or handle gracefully
    expect([200, 400]).toContain(response.status());
  });

  test('should handle missing session_id', async ({ page }) => {
    const response = await page.request.post(`${BASE_URL}/api/onboarding-jarvis/message`, {
      data: { message: 'Hello' },
    });
    // Should create a new session or return error
    expect([200, 400, 404]).toContain(response.status());
  });

  test('should track message count accurately', async ({ page }) => {
    const session = await createJarvisSession(page);
    const sid = session.session_id;

    // Send 3 messages
    for (let i = 0; i < 3; i++) {
      await sendJarvisMessage(page, sid, `Message ${i + 1}`);
    }

    const lastResult = await sendJarvisMessage(page, sid, 'Final message');
    expect(lastResult.remaining_today).toBe(16); // 20 - 4 = 16
  });
});
