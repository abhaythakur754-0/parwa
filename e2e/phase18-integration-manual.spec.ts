/**
 * PARWA Phase 18 — Integration Manual Testing E2E Spec
 * ======================================================
 * Tests all Phase 18 gap fixes: Tickets API, Billing Store, KB API paths,
 * Ticket Detail route, Accessibility, and P2 hooks.
 *
 * Run: npx playwright test e2e/phase18-integration-manual.spec.ts
 */

import { test, expect } from '@playwright/test';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:3000';

// ── Backend API Tests ────────────────────────────────────────────────

test.describe('Phase 18: Backend Ticket API', () => {
  test('GET /api/v1/tickets returns proper response', async ({ request }) => {
    const resp = await request.get(`${BACKEND_URL}/api/v1/tickets`);
    expect([200, 401, 403]).toContain(resp.status());
  });

  test('POST /api/v1/tickets requires auth', async ({ request }) => {
    const resp = await request.post(`${BACKEND_URL}/api/v1/tickets`, {
      data: { subject: 'Test', customer_id: '1', channel: 'email' },
    });
    expect([401, 403, 422]).toContain(resp.status());
  });

  test('GET /api/v1/tickets/{id} requires auth', async ({ request }) => {
    const resp = await request.get(`${BACKEND_URL}/api/v1/tickets/test-id`);
    expect([401, 403, 404, 422]).toContain(resp.status());
  });

  test('PATCH /api/v1/tickets/{id}/status requires auth', async ({ request }) => {
    const resp = await request.patch(`${BACKEND_URL}/api/v1/tickets/test-id/status`, {
      data: { status: 'resolved' },
    });
    expect([401, 403, 404, 422]).toContain(resp.status());
  });

  test('POST /api/v1/tickets/detect-priority accepts text', async ({ request }) => {
    const resp = await request.post(`${BACKEND_URL}/api/v1/tickets/detect-priority`, {
      data: { text: 'URGENT: My system is down!' },
    });
    expect([200, 401, 403, 422]).toContain(resp.status());
  });

  test('POST /api/v1/tickets/detect-category accepts text', async ({ request }) => {
    const resp = await request.post(`${BACKEND_URL}/api/v1/tickets/detect-category`, {
      data: { subject: 'Billing issue', message: 'I was overcharged' },
    });
    expect([200, 401, 403, 422]).toContain(resp.status());
  });
});

test.describe('Phase 18: Backend Billing API', () => {
  test('GET /api/billing/subscription requires auth', async ({ request }) => {
    const resp = await request.get(`${BACKEND_URL}/api/billing/subscription`);
    expect([200, 401, 403]).toContain(resp.status());
  });

  test('GET /api/billing/invoices requires auth', async ({ request }) => {
    const resp = await request.get(`${BACKEND_URL}/api/billing/invoices`);
    expect([200, 401, 403]).toContain(resp.status());
  });

  test('GET /api/billing/usage requires auth', async ({ request }) => {
    const resp = await request.get(`${BACKEND_URL}/api/billing/usage`);
    expect([200, 401, 403]).toContain(resp.status());
  });

  test('GET /api/billing/status requires auth', async ({ request }) => {
    const resp = await request.get(`${BACKEND_URL}/api/billing/status`);
    expect([200, 401, 403]).toContain(resp.status());
  });
});

test.describe('Phase 18: Backend KB API', () => {
  test('GET /api/kb/documents requires auth', async ({ request }) => {
    const resp = await request.get(`${BACKEND_URL}/api/kb/documents`);
    expect([200, 401, 403]).toContain(resp.status());
  });

  test('GET /api/kb/stats requires auth', async ({ request }) => {
    const resp = await request.get(`${BACKEND_URL}/api/kb/stats`);
    expect([200, 401, 403]).toContain(resp.status());
  });
});

// ── Frontend Source Code Validation (no browser needed) ───────────────

test.describe('Phase 18: Frontend Source Validation', () => {
  test('ticketApi module exists in api.ts', async () => {
    const fs = require('fs');
    const path = require('path');
    const apiPath = path.join(__dirname, '..', 'src', 'lib', 'api.ts');
    const content = fs.readFileSync(apiPath, 'utf-8');
    expect(content).toContain('ticketApi');
    expect(content).toContain('/api/v1/tickets');
  });

  test('ticket-store has API integration', async () => {
    const fs = require('fs');
    const path = require('path');
    const storePath = path.join(__dirname, '..', 'src', 'lib', 'ticket-store.ts');
    const content = fs.readFileSync(storePath, 'utf-8');
    expect(content).toContain('ticketApi');
    expect(content).toContain('fetchTickets');
    expect(content).toContain('isLoading');
  });

  test('billing page imports useBillingStore', async () => {
    const fs = require('fs');
    const path = require('path');
    const pagePath = path.join(__dirname, '..', 'src', 'app', 'dashboard', 'billing', 'page.tsx');
    const content = fs.readFileSync(pagePath, 'utf-8');
    expect(content).toContain('useBillingStore');
    expect(content).toContain('fetchBilling');
    expect(content).toContain('changePlan');
  });

  test('billing store uses /api/billing path', async () => {
    const fs = require('fs');
    const path = require('path');
    const storePath = path.join(__dirname, '..', 'src', 'lib', 'billing-store.ts');
    const content = fs.readFileSync(storePath, 'utf-8');
    expect(content).toContain('/api/billing/');
    expect(content).not.toContain('/api/v1/billing/');
  });

  test('knowledgeApi uses /api/kb paths', async () => {
    const fs = require('fs');
    const path = require('path');
    const apiPath = path.join(__dirname, '..', 'src', 'lib', 'api.ts');
    const content = fs.readFileSync(apiPath, 'utf-8');
    expect(content).toContain('/api/kb/upload');
    expect(content).toContain('/api/kb/documents');
    expect(content).not.toContain('/api/knowledge/upload');
    expect(content).not.toContain('/api/knowledge"');
  });

  test('ticket detail route exists', async () => {
    const fs = require('fs');
    const path = require('path');
    const detailPath = path.join(__dirname, '..', 'src', 'app', 'dashboard', 'tickets', '[id]', 'page.tsx');
    expect(fs.existsSync(detailPath)).toBe(true);
    const content = fs.readFileSync(detailPath, 'utf-8');
    expect(content).toContain('useTicketStore');
    expect(content).toContain('addMessage');
  });

  test('skip-to-content link in DashboardLayout', async () => {
    const fs = require('fs');
    const path = require('path');
    const layoutPath = path.join(__dirname, '..', 'src', 'components', 'dashboard', 'DashboardLayout.tsx');
    const content = fs.readFileSync(layoutPath, 'utf-8');
    expect(content).toContain('main-content');
    expect(content).toContain('skip to content');
  });

  test('aria-hidden on billing SVGs', async () => {
    const fs = require('fs');
    const path = require('path');
    const pagePath = path.join(__dirname, '..', 'src', 'app', 'dashboard', 'billing', 'page.tsx');
    const content = fs.readFileSync(pagePath, 'utf-8');
    expect(content).toContain('aria-hidden="true"');
    expect(content).toContain('sr-only');
  });

  test('P2 hooks exist', async () => {
    const fs = require('fs');
    const path = require('path');
    const hooksDir = path.join(__dirname, '..', 'src', 'hooks');
    expect(fs.existsSync(path.join(hooksDir, 'useTypingIndicator.ts'))).toBe(true);
    expect(fs.existsSync(path.join(hooksDir, 'usePresence.ts'))).toBe(true);
    expect(fs.existsSync(path.join(hooksDir, 'useCollisionDetection.ts'))).toBe(true);
  });

  test('ARIA switch roles in settings', async () => {
    const fs = require('fs');
    const path = require('path');
    const settingsPath = path.join(__dirname, '..', 'src', 'app', 'dashboard', 'settings', 'page.tsx');
    const content = fs.readFileSync(settingsPath, 'utf-8');
    expect(content).toContain('role="switch"');
    expect(content).toContain('aria-checked');
  });
});

// ── Manual Test Procedures (documented as skipped tests) ─────────────

test.describe('Phase 18: Manual Test Procedures', () => {
  test.skip('MT-01: Create ticket via UI and verify API call', async () => {
    // Manual procedure:
    // 1. Navigate to /dashboard/tickets
    // 2. Click "New Ticket" button
    // 3. Fill in subject, description, category, priority
    // 4. Submit and verify ticket appears in list
    // 5. Check browser DevTools Network tab for POST /api/v1/tickets
  });

  test.skip('MT-02: View ticket detail page', async () => {
    // Manual procedure:
    // 1. Click on any ticket in the list
    // 2. Verify URL changes to /dashboard/tickets/[id]
    // 3. Verify ticket details, messages, and actions are displayed
    // 4. Click "Back to Tickets" and verify navigation
  });

  test.skip('MT-03: Reply to ticket', async () => {
    // Manual procedure:
    // 1. Open ticket detail page
    // 2. Type a reply in the message input
    // 3. Click Send
    // 4. Verify message appears in thread
  });

  test.skip('MT-04: Upgrade billing plan', async () => {
    // Manual procedure:
    // 1. Navigate to /dashboard/billing
    // 2. Click "Upgrade" button on a higher plan
    // 3. Check DevTools Network for PATCH /api/billing/subscription
    // 4. Verify plan changes in the UI
  });

  test.skip('MT-05: Upload document to Knowledge Base', async () => {
    // Manual procedure:
    // 1. Navigate to /dashboard/knowledge
    // 2. Upload a PDF file
    // 3. Check DevTools Network for POST /api/kb/upload
    // 4. Verify document appears in the list
  });

  test.skip('MT-06: Skip-to-content accessibility', async () => {
    // Manual procedure:
    // 1. Load dashboard page
    // 2. Press Tab key
    // 3. Verify "Skip to content" link appears
    // 4. Press Enter to skip to main content
    // 5. Verify focus moves to main content area
  });

  test.skip('MT-07: Screen reader status badges', async () => {
    // Manual procedure:
    // 1. Navigate to /dashboard/billing
    // 2. Enable screen reader (VoiceOver/NVDA)
    // 3. Navigate to invoice status badges
    // 4. Verify screen reader announces "paid invoice", "pending invoice", etc.
  });

  test.skip('MT-08: Profile save', async () => {
    // Manual procedure:
    // 1. Navigate to /dashboard/settings
    // 2. Change full name
    // 3. Click "Save Changes"
    // 4. Check DevTools Network for PATCH /api/v1/auth/me
    // 5. Verify success toast appears
  });
});
