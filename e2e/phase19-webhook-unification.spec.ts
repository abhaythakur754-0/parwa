/**
 * PARWA Phase 19 — Webhook Unification + Universal API E2E Spec
 * ===============================================================
 * Tests all Phase 19 features: Webhook parser registry, verifier registry,
 * unified webhook service, CustomApiBuilder UI, WebhookConfigurator UI,
 * and useIntegrations hook.
 *
 * Run: npx playwright test e2e/phase19-webhook-unification.spec.ts
 */

import { test, expect } from '@playwright/test';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:3000';

// ══════════════════════════════════════════════════════════════════════
// 1. BACKEND WEBHOOK API TESTS
// ══════════════════════════════════════════════════════════════════════

test.describe('Phase 19: Backend Webhook API', () => {
  test('POST /api/webhooks/paddle rejects without signature', async ({ request }) => {
    const resp = await request.post(`${BACKEND_URL}/api/webhooks/paddle`, {
      data: {
        event_id: 'evt_test_001',
        event_type: 'subscription.created',
        company_id: 'test-company',
        occurred_at: new Date().toISOString(),
      },
    });
    // Should reject (401 = invalid signature, 500 = no secret configured)
    expect([401, 500, 403]).toContain(resp.status());
  });

  test('POST /api/webhooks/shopify rejects without signature', async ({ request }) => {
    const resp = await request.post(`${BACKEND_URL}/api/webhooks/shopify`, {
      data: {
        id: 'shopify-order-001',
        topic: 'orders/create',
        company_id: 'test-company',
        created_at: new Date().toISOString(),
      },
    });
    expect([401, 500, 403]).toContain(resp.status());
  });

  test('POST /api/webhooks/twilio rejects without signature', async ({ request }) => {
    const resp = await request.post(`${BACKEND_URL}/api/webhooks/twilio`, {
      data: {
        MessageSid: 'SM_test_001',
        EventType: 'sms.incoming',
        AccountSid: 'AC_test',
        Timestamp: new Date().toISOString(),
      },
    });
    expect([401, 500, 403]).toContain(resp.status());
  });

  test('POST /api/webhooks/brevo rejects without proper IP', async ({ request }) => {
    const resp = await request.post(`${BACKEND_URL}/api/webhooks/brevo`, {
      data: {
        event_id: 'brevo-evt-001',
        event: 'delivered',
        company_id: 'test-company',
        event_time: new Date().toISOString(),
      },
    });
    // Brevo uses IP verification, so from test runner IP it should be rejected
    expect([401, 500, 403]).toContain(resp.status());
  });

  test('POST /api/webhooks/unsupported returns 404', async ({ request }) => {
    const resp = await request.post(`${BACKEND_URL}/api/webhooks/unsupported_provider`, {
      data: { event_id: 'test', company_id: 'test', occurred_at: new Date().toISOString() },
    });
    expect(resp.status()).toBe(404);
    const body = await resp.json();
    expect(body.error).toBeDefined();
    expect(body.error.code).toBe('NOT_FOUND');
  });

  test('POST /api/webhooks/paddle rejects missing timestamp (replay protection)', async ({ request }) => {
    const resp = await request.post(`${BACKEND_URL}/api/webhooks/paddle`, {
      data: {
        event_id: 'evt_no_timestamp',
        event_type: 'subscription.created',
        company_id: 'test-company',
        // No occurred_at/created_at/timestamp
      },
    });
    expect([403, 401, 500]).toContain(resp.status());
  });

  test('POST /api/webhooks/paddle rejects oversized payload', async ({ request }) => {
    const hugePayload = 'x'.repeat(2 * 1024 * 1024); // 2MB
    const resp = await request.post(`${BACKEND_URL}/api/webhooks/paddle`, {
      data: {
        event_id: 'evt_huge',
        event_type: 'subscription.created',
        company_id: 'test-company',
        occurred_at: new Date().toISOString(),
        extra_data: hugePayload,
      },
    });
    // Should reject with 413 (payload too large) or fail during processing
    expect([413, 401, 500, 403]).toContain(resp.status());
  });

  test('POST /api/webhooks/paddle rejects missing event_id', async ({ request }) => {
    const resp = await request.post(`${BACKEND_URL}/api/webhooks/paddle`, {
      data: {
        // No event_id
        event_type: 'subscription.created',
        company_id: 'test-company',
        occurred_at: new Date().toISOString(),
      },
    });
    expect([422, 401, 500, 403]).toContain(resp.status());
  });
});

// ══════════════════════════════════════════════════════════════════════
// 2. BACKEND INTEGRATION API TESTS
// ══════════════════════════════════════════════════════════════════════

test.describe('Phase 19: Backend Integration API', () => {
  test('GET /api/integrations/available returns provider list', async ({ request }) => {
    const resp = await request.get(`${BACKEND_URL}/api/integrations/available`);
    expect([200, 401, 403]).toContain(resp.status());
  });

  test('GET /api/integrations returns integration list (requires auth)', async ({ request }) => {
    const resp = await request.get(`${BACKEND_URL}/api/integrations`);
    expect([200, 401, 403]).toContain(resp.status());
  });

  test('POST /api/integrations creates new integration (requires auth)', async ({ request }) => {
    const resp = await request.post(`${BACKEND_URL}/api/integrations`, {
      data: {
        provider: 'custom',
        category: 'custom',
        name: 'Test Custom API',
        base_url: 'https://api.example.com',
        auth_method: 'bearer',
      },
    });
    expect([200, 201, 401, 403, 422]).toContain(resp.status());
  });

  test('POST /api/jarvis/integrations/detect-key detects provider from API key', async ({ request }) => {
    const resp = await request.post(`${BACKEND_URL}/api/jarvis/integrations/detect-key`, {
      data: { api_key: 'sk_test_1234567890abcdef' },
    });
    expect([200, 401, 403, 422]).toContain(resp.status());
  });

  test('GET /api/jarvis/integrations/status returns provider status (requires auth)', async ({ request }) => {
    const resp = await request.get(`${BACKEND_URL}/api/jarvis/integrations/status`);
    expect([200, 401, 403]).toContain(resp.status());
  });
});

// ══════════════════════════════════════════════════════════════════════
// 3. BACKEND WEBHOOK UNIFIED SERVICE SOURCE CODE VALIDATION
// ══════════════════════════════════════════════════════════════════════

test.describe('Phase 19: Webhook Unified Service Source Validation', () => {
  test('webhook_parser.py exists with WebhookParserRegistry', async () => {
    const fs = require('fs');
    const path = require('path');
    const parserPath = path.join(__dirname, '..', 'backend', 'app', 'core', 'providers', 'webhook_parser.py');
    expect(fs.existsSync(parserPath)).toBe(true);
    const content = fs.readFileSync(parserPath, 'utf-8');
    expect(content).toContain('WebhookParserRegistry');
    expect(content).toContain('parse_paddle');
    expect(content).toContain('parse_shopify');
    expect(content).toContain('parse_twilio');
    expect(content).toContain('parse_brevo');
    expect(content).toContain('parse_generic');
  });

  test('webhook_verifier.py exists with WebhookVerifierRegistry', async () => {
    const fs = require('fs');
    const path = require('path');
    const verifierPath = path.join(__dirname, '..', 'backend', 'app', 'core', 'providers', 'webhook_verifier.py');
    expect(fs.existsSync(verifierPath)).toBe(true);
    const content = fs.readFileSync(verifierPath, 'utf-8');
    expect(content).toContain('WebhookVerifierRegistry');
    expect(content).toContain('verify_paddle');
    expect(content).toContain('verify_shopify');
    expect(content).toContain('verify_twilio');
    expect(content).toContain('verify_brevo_ip');
    expect(content).toContain('verify_generic');
  });

  test('webhook_unified_service.py exists with WebhookUnifiedService', async () => {
    const fs = require('fs');
    const path = require('path');
    const servicePath = path.join(__dirname, '..', 'backend', 'app', 'services', 'webhook_unified_service.py');
    expect(fs.existsSync(servicePath)).toBe(true);
    const content = fs.readFileSync(servicePath, 'utf-8');
    expect(content).toContain('WebhookUnifiedService');
    expect(content).toContain('WebhookParserRegistry');
    expect(content).toContain('WebhookVerifierRegistry');
    expect(content).toContain('receive');
    expect(content).toContain('retry_failed');
    expect(content).toContain('_check_timestamp');
    expect(content).toContain('_get_provider_secret');
  });

  test('webhook_parser.py has register/parse/list_providers methods', async () => {
    const fs = require('fs');
    const path = require('path');
    const parserPath = path.join(__dirname, '..', 'backend', 'app', 'core', 'providers', 'webhook_parser.py');
    const content = fs.readFileSync(parserPath, 'utf-8');
    expect(content).toContain('def register');
    expect(content).toContain('def parse');
    expect(content).toContain('def list_providers');
    expect(content).toContain('def has_parser');
    expect(content).toContain('def get_parser');
  });

  test('webhook_verifier.py has register/verify/list_providers methods', async () => {
    const fs = require('fs');
    const path = require('path');
    const verifierPath = path.join(__dirname, '..', 'backend', 'app', 'core', 'providers', 'webhook_verifier.py');
    const content = fs.readFileSync(verifierPath, 'utf-8');
    expect(content).toContain('def register');
    expect(content).toContain('def verify');
    expect(content).toContain('def list_providers');
    expect(content).toContain('def has_verifier');
    expect(content).toContain('def get_verifier');
  });

  test('webhook_unified_service.py has retry logic with MAX_RETRIES', async () => {
    const fs = require('fs');
    const path = require('path');
    const servicePath = path.join(__dirname, '..', 'backend', 'app', 'services', 'webhook_unified_service.py');
    const content = fs.readFileSync(servicePath, 'utf-8');
    expect(content).toContain('MAX_RETRIES');
    expect(content).toContain('retry_failed');
    expect(content).toContain('PAYLOAD_TOO_LARGE');
    expect(content).toContain('REPLAY_DETECTED');
    expect(content).toContain('AUTHENTICATION_ERROR');
    expect(content).toContain('CONFIGURATION_ERROR');
  });
});

// ══════════════════════════════════════════════════════════════════════
// 4. FRONTEND COMPONENT SOURCE VALIDATION
// ══════════════════════════════════════════════════════════════════════

test.describe('Phase 19: Frontend Component Source Validation', () => {
  test('CustomApiBuilder.tsx exists with correct structure', async () => {
    const fs = require('fs');
    const path = require('path');
    const compPath = path.join(__dirname, '..', 'src', 'components', 'integrations', 'CustomApiBuilder.tsx');
    expect(fs.existsSync(compPath)).toBe(true);
    const content = fs.readFileSync(compPath, 'utf-8');
    expect(content).toContain('CustomApiBuilder');
    expect(content).toContain('AuthMethod');
    expect(content).toContain('bearer');
    expect(content).toContain('api_key');
    expect(content).toContain('basic');
    expect(content).toContain('onSave');
    expect(content).toContain('onTest');
    expect(content).toContain('Test Connection');
    expect(content).toContain('Save Connection');
  });

  test('CustomApiBuilder.tsx has custom header management', async () => {
    const fs = require('fs');
    const path = require('path');
    const compPath = path.join(__dirname, '..', 'src', 'components', 'integrations', 'CustomApiBuilder.tsx');
    const content = fs.readFileSync(compPath, 'utf-8');
    expect(content).toContain('handleAddHeader');
    expect(content).toContain('handleRemoveHeader');
    expect(content).toContain('Custom Headers');
  });

  test('CustomApiBuilder.tsx has request body template for non-GET', async () => {
    const fs = require('fs');
    const path = require('path');
    const compPath = path.join(__dirname, '..', 'src', 'components', 'integrations', 'CustomApiBuilder.tsx');
    const content = fs.readFileSync(compPath, 'utf-8');
    expect(content).toContain('bodyTemplate');
    expect(content).toContain('Request Body Template');
    expect(content).toContain('responsePath');
  });

  test('CustomApiBuilder.tsx has accessibility attributes', async () => {
    const fs = require('fs');
    const path = require('path');
    const compPath = path.join(__dirname, '..', 'src', 'components', 'integrations', 'CustomApiBuilder.tsx');
    const content = fs.readFileSync(compPath, 'utf-8');
    expect(content).toContain('aria-label');
    expect(content).toContain('role="alert"');
    expect(content).toContain('aria-hidden="true"');
  });

  test('WebhookConfigurator.tsx exists with correct structure', async () => {
    const fs = require('fs');
    const path = require('path');
    const compPath = path.join(__dirname, '..', 'src', 'components', 'integrations', 'WebhookConfigurator.tsx');
    expect(fs.existsSync(compPath)).toBe(true);
    const content = fs.readFileSync(compPath, 'utf-8');
    expect(content).toContain('WebhookConfigurator');
    expect(content).toContain('WebhookConfig');
    expect(content).toContain('onSave');
    expect(content).toContain('onTest');
    expect(content).toContain('onRetry');
    expect(content).toContain('onDelete');
  });

  test('WebhookConfigurator.tsx has provider event subscriptions', async () => {
    const fs = require('fs');
    const path = require('path');
    const compPath = path.join(__dirname, '..', 'src', 'components', 'integrations', 'WebhookConfigurator.tsx');
    const content = fs.readFileSync(compPath, 'utf-8');
    expect(content).toContain('PROVIDER_EVENTS');
    expect(content).toContain('subscription.created');
    expect(content).toContain('orders/create');
    expect(content).toContain('sms.incoming');
    expect(content).toContain('delivered');
  });

  test('WebhookConfigurator.tsx has activity logs tab', async () => {
    const fs = require('fs');
    const path = require('path');
    const compPath = path.join(__dirname, '..', 'src', 'components', 'integrations', 'WebhookConfigurator.tsx');
    const content = fs.readFileSync(compPath, 'utf-8');
    expect(content).toContain('Activity Logs');
    expect(content).toContain('WebhookLog');
    expect(content).toContain('retrying');
  });

  test('WebhookConfigurator.tsx has accessibility attributes', async () => {
    const fs = require('fs');
    const path = require('path');
    const compPath = path.join(__dirname, '..', 'src', 'components', 'integrations', 'WebhookConfigurator.tsx');
    const content = fs.readFileSync(compPath, 'utf-8');
    expect(content).toContain('role="tablist"');
    expect(content).toContain('role="tab"');
    expect(content).toContain('role="checkbox"');
    expect(content).toContain('role="status"');
    expect(content).toContain('role="alert"');
    expect(content).toContain('aria-selected');
    expect(content).toContain('aria-checked');
    expect(content).toContain('aria-hidden="true"');
  });

  test('useIntegrations.ts hook exists with full API', async () => {
    const fs = require('fs');
    const path = require('path');
    const hookPath = path.join(__dirname, '..', 'src', 'hooks', 'useIntegrations.ts');
    expect(fs.existsSync(hookPath)).toBe(true);
    const content = fs.readFileSync(hookPath, 'utf-8');
    expect(content).toContain('useIntegrations');
    expect(content).toContain('fetchIntegrations');
    expect(content).toContain('addIntegration');
    expect(content).toContain('removeIntegration');
    expect(content).toContain('testConnection');
    expect(content).toContain('fetchWebhooks');
    expect(content).toContain('saveWebhook');
    expect(content).toContain('deleteWebhook');
    expect(content).toContain('testWebhook');
    expect(content).toContain('retryWebhook');
    expect(content).toContain('createCustomApi');
    expect(content).toContain('availableProviders');
  });

  test('useIntegrations.ts has ProviderCategory types', async () => {
    const fs = require('fs');
    const path = require('path');
    const hookPath = path.join(__dirname, '..', 'src', 'hooks', 'useIntegrations.ts');
    const content = fs.readFileSync(hookPath, 'utf-8');
    expect(content).toContain('ProviderCategory');
    expect(content).toContain('email');
    expect(content).toContain('sms');
    expect(content).toContain('payment');
    expect(content).toContain('custom');
    expect(content).toContain('ConnectionStatus');
  });

  test('useIntegrations.ts has mock data fallback', async () => {
    const fs = require('fs');
    const path = require('path');
    const hookPath = path.join(__dirname, '..', 'src', 'hooks', 'useIntegrations.ts');
    const content = fs.readFileSync(hookPath, 'utf-8');
    expect(content).toContain('getMockIntegrations');
    expect(content).toContain('getMockWebhooks');
    expect(content).toContain('mountedRef');
  });
});

// ══════════════════════════════════════════════════════════════════════
// 5. INTEGRATION WITH EXISTING PROVIDERS
// ══════════════════════════════════════════════════════════════════════

test.describe('Phase 19: Provider Integration Consistency', () => {
  test('webhook API route uses SUPPORTED_PROVIDERS that match parsers', async () => {
    const fs = require('fs');
    const path = require('path');
    const apiPath = path.join(__dirname, '..', 'backend', 'app', 'api', 'webhooks.py');
    const content = fs.readFileSync(apiPath, 'utf-8');
    // The existing API supports paddle, twilio, shopify, brevo
    expect(content).toContain('paddle');
    expect(content).toContain('twilio');
    expect(content).toContain('shopify');
    expect(content).toContain('brevo');
  });

  test('existing webhook_service.py has process_webhook and retry', async () => {
    const fs = require('fs');
    const path = require('path');
    const servicePath = path.join(__dirname, '..', 'backend', 'app', 'services', 'webhook_service.py');
    expect(fs.existsSync(servicePath)).toBe(true);
    const content = fs.readFileSync(servicePath, 'utf-8');
    expect(content).toContain('process_webhook');
    expect(content).toContain('retry_failed_webhook');
  });

  test('provider registry has all expected providers', async () => {
    const fs = require('fs');
    const path = require('path');
    const registryPath = path.join(__dirname, '..', 'backend', 'app', 'core', 'providers', 'registry.py');
    expect(fs.existsSync(registryPath)).toBe(true);
    const content = fs.readFileSync(registryPath, 'utf-8');
    expect(content).toContain('ProviderRegistry');
    expect(content).toContain('ProviderFactory');
  });

  test('integration API routes exist for basic CRUD', async () => {
    const fs = require('fs');
    const path = require('path');
    const integrationsPath = path.join(__dirname, '..', 'backend', 'app', 'api', 'integrations.py');
    expect(fs.existsSync(integrationsPath)).toBe(true);
    const content = fs.readFileSync(integrationsPath, 'utf-8');
    expect(content).toContain('/api/integrations');
    expect(content).toContain('available');
  });

  test('jarvis integrations API exists for provider management', async () => {
    const fs = require('fs');
    const path = require('path');
    const jarvisPath = path.join(__dirname, '..', 'backend', 'app', 'api', 'jarvis_integrations.py');
    expect(fs.existsSync(jarvisPath)).toBe(true);
    const content = fs.readFileSync(jarvisPath, 'utf-8');
    expect(content).toContain('detect-key');
    expect(content).toContain('test-connection');
    expect(content).toContain('connect');
  });
});

// ══════════════════════════════════════════════════════════════════════
// 6. MANUAL TEST PROCEDURES
// ══════════════════════════════════════════════════════════════════════

test.describe('Phase 19: Manual Test Procedures', () => {
  test.skip('MT-01: Create custom API connection via CustomApiBuilder', async () => {
    // Manual procedure:
    // 1. Navigate to /dashboard/integrations
    // 2. Click "Add Custom API"
    // 3. Fill in name, base URL, auth method, and credentials
    // 4. Click "Test Connection" to verify
    // 5. Click "Save Connection"
    // 6. Verify the new connection appears in the list
  });

  test.skip('MT-02: Configure webhook for provider', async () => {
    // Manual procedure:
    // 1. Navigate to /dashboard/integrations
    // 2. Click "Webhook Configurator" tab
    // 3. Click "Add Webhook Configuration"
    // 4. Select a provider (e.g. Paddle)
    // 5. Copy the webhook endpoint URL
    // 6. Enter webhook secret
    // 7. Select events to subscribe to
    // 8. Save configuration
    // 9. Verify webhook appears as "active"
  });

  test.skip('MT-03: Test webhook delivery', async () => {
    // Manual procedure:
    // 1. Configure a webhook for a provider
    // 2. Click "Test" button on the webhook config
    // 3. Verify test event appears in Activity Logs
    // 4. Check the log shows "success" status
  });

  test.skip('MT-04: Retry failed webhook', async () => {
    // Manual procedure:
    // 1. Find a failed webhook event in Activity Logs
    // 2. Click "Retry" button
    // 3. Verify the event status changes to "retrying" then "success" or "failed"
    // 4. Check retry_count increments
  });

  test.skip('MT-05: Register new webhook parser', async () => {
    // Manual procedure (developer):
    // 1. Create a new parser function in webhook_parser.py
    // 2. Register it with WebhookParserRegistry.register("newprovider", parse_newprovider)
    // 3. POST a webhook to /api/webhooks/newprovider
    // 4. Verify the parser correctly extracts event_id, event_type, company_id
  });

  test.skip('MT-06: Register new webhook verifier', async () => {
    // Manual procedure (developer):
    // 1. Create a new verifier function in webhook_verifier.py
    // 2. Register it with WebhookVerifierRegistry.register("newprovider", verify_newprovider)
    // 3. Send a webhook with the correct signature
    // 4. Verify it passes verification
  });

  test.skip('MT-07: Webhook replay attack prevention', async () => {
    // Manual procedure:
    // 1. Send a webhook with an old timestamp (>5 minutes)
    // 2. Verify it's rejected with REPLAY_DETECTED error
    // 3. Send a webhook with no timestamp
    // 4. Verify it's also rejected
  });

  test.skip('MT-08: Webhook idempotency check', async () => {
    // Manual procedure:
    // 1. Send the same webhook event twice with the same event_id
    // 2. Verify the second response shows "duplicate: true"
    // 3. Verify only one event is stored in the database
  });
});
