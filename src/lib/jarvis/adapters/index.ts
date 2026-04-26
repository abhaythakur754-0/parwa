/**
 * JARVIS Integration Adapters - Week 13 (Phase 4)
 *
 * Main entry point for integration adapters.
 * 
 * Architecture:
 * - Email: Pluggable (Brevo, SendGrid, etc.) - client chooses
 * - SMS: Twilio only - fixed provider
 */

// Types
export * from './types';

// Email Adapters
export {
  BaseEmailAdapter,
  BrevoEmailAdapter,
  SendGridEmailAdapter,
  MockEmailAdapter,
  createEmailAdapter,
} from './email-adapter';

// SMS Adapters
export {
  TwilioSMSAdapter,
  MockSMSAdapter,
  createSMSAdapter,
} from './sms-adapter';

// Tenant Integration Manager
export {
  TenantIntegrationManager,
  MockIntegrationManager,
  createIntegrationManagerFromEnv,
  getIntegrationManager,
  clearIntegrationManagerCache,
} from './tenant-integration-manager';
