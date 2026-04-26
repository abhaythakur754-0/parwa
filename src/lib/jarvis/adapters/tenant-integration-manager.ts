/**
 * JARVIS Tenant Integration Manager - Week 13 (Phase 4)
 *
 * Manages integration adapters per tenant/client.
 * Fetches integration config from database and creates appropriate adapters.
 * 
 * Architecture:
 * - Email: Pluggable (Brevo, SendGrid, etc.)
 * - SMS: Twilio only (fixed)
 */

import { prisma } from '@/lib/db';
import type {
  EmailAdapter,
  SMSAdapter,
  ChatAdapter,
  WebhookAdapter,
  AdapterSet,
  TenantIntegrationConfig,
  EmailProviderType,
  SMSProviderType,
  JarvisIntegrationAction,
  JarvisIntegrationResult,
} from './types';

import {
  createEmailAdapter,
  MockEmailAdapter,
} from './email-adapter';

import {
  createSMSAdapter,
  MockSMSAdapter,
} from './sms-adapter';

// ── Integration Manager ─────────────────────────────────────────────

export class TenantIntegrationManager {
  private adapterCache: Map<string, AdapterSet> = new Map();
  private organizationId: string;
  
  constructor(organizationId: string) {
    this.organizationId = organizationId;
  }
  
  /**
   * Get all adapters for this tenant
   */
  async getAdapters(): Promise<AdapterSet> {
    // Check cache first
    const cached = this.adapterCache.get(this.organizationId);
    if (cached) {
      return cached;
    }
    
    // Fetch integration config from database
    const config = await this.fetchIntegrationConfig();
    
    // Create adapters based on config
    const adapters: AdapterSet = {};
    
    // Email adapter (pluggable)
    if (config.email?.isActive) {
      adapters.email = createEmailAdapter(
        config.email.provider,
        config.email.credentials
      );
    }
    
    // SMS adapter (Twilio only)
    if (config.sms?.isActive) {
      adapters.sms = createSMSAdapter(config.sms.credentials);
    }
    
    // Cache and return
    this.adapterCache.set(this.organizationId, adapters);
    return adapters;
  }
  
  /**
   * Get email adapter
   */
  async getEmailAdapter(): Promise<EmailAdapter | undefined> {
    const adapters = await this.getAdapters();
    return adapters.email;
  }
  
  /**
   * Get SMS adapter
   */
  async getSMSAdapter(): Promise<SMSAdapter | undefined> {
    const adapters = await this.getAdapters();
    return adapters.sms;
  }
  
  /**
   * Get chat adapter
   */
  async getChatAdapter(): Promise<ChatAdapter | undefined> {
    const adapters = await this.getAdapters();
    return adapters.chat;
  }
  
  /**
   * Execute a JARVIS integration action
   */
  async executeAction(action: JarvisIntegrationAction): Promise<JarvisIntegrationResult> {
    const adapters = await this.getAdapters();
    
    switch (action.type) {
      case 'send_email': {
        if (!adapters.email) {
          return {
            success: false,
            action: 'send_email',
            error: 'Email integration not configured',
          };
        }
        
        const result = await adapters.email.sendEmail(action.payload);
        return {
          success: result.success,
          action: 'send_email',
          provider: adapters.email.providerName,
          messageId: result.messageId,
          error: result.error,
        };
      }
      
      case 'send_sms': {
        if (!adapters.sms) {
          return {
            success: false,
            action: 'send_sms',
            error: 'SMS integration not configured',
          };
        }
        
        const result = await adapters.sms.sendSMS(action.payload);
        return {
          success: result.success,
          action: 'send_sms',
          provider: adapters.sms.providerName,
          messageId: result.messageSid,
          error: result.error,
          metadata: { recipients: result.recipients },
        };
      }
      
      case 'send_chat': {
        if (!adapters.chat) {
          return {
            success: false,
            action: 'send_chat',
            error: 'Chat integration not configured',
          };
        }
        
        const result = await adapters.chat.sendMessage(action.payload);
        return {
          success: result.success,
          action: 'send_chat',
          provider: adapters.chat.providerName,
          messageId: result.messageId,
          error: result.error,
        };
      }
      
      case 'trigger_webhook': {
        if (!adapters.webhook) {
          return {
            success: false,
            action: 'trigger_webhook',
            error: 'Webhook integration not configured',
          };
        }
        
        const result = await adapters.webhook.sendWebhook(action.payload);
        return {
          success: result.success,
          action: 'trigger_webhook',
          error: result.error,
          metadata: { statusCode: result.statusCode },
        };
      }
      
      default:
        return {
          success: false,
          action: action.type,
          error: `Unknown action type`,
        };
    }
  }
  
  /**
   * Check if integrations are configured
   */
  async hasIntegration(type: 'email' | 'sms' | 'chat' | 'webhook'): Promise<boolean> {
    const adapters = await this.getAdapters();
    return !!adapters[type];
  }
  
  /**
   * Get integration status
   */
  async getStatus(): Promise<{
    email: { configured: boolean; provider?: string };
    sms: { configured: boolean; provider?: string };
    chat: { configured: boolean; provider?: string };
    webhook: { configured: boolean };
  }> {
    const adapters = await this.getAdapters();
    
    return {
      email: {
        configured: !!adapters.email,
        provider: adapters.email?.providerName,
      },
      sms: {
        configured: !!adapters.sms,
        provider: adapters.sms?.providerName,
      },
      chat: {
        configured: !!adapters.chat,
        provider: adapters.chat?.providerName,
      },
      webhook: {
        configured: !!adapters.webhook,
      },
    };
  }
  
  /**
   * Clear cache (useful when integration config changes)
   */
  clearCache(): void {
    this.adapterCache.delete(this.organizationId);
  }
  
  /**
   * Fetch integration config from database
   */
  private async fetchIntegrationConfig(): Promise<TenantIntegrationConfig> {
    const config: TenantIntegrationConfig = {
      organizationId: this.organizationId,
    };
    
    try {
      // Fetch integrations from database
      const integrations = await prisma.integration.findMany({
        where: {
          company_id: this.organizationId,
          status: 'connected',
        },
      });
      
      for (const integration of integrations) {
        // Parse credentials (decrypt in production)
        const credentials = this.parseCredentials(integration.credentials_encrypted);
        const settings = JSON.parse(integration.settings || '{}');
        
        switch (integration.integration_type) {
          case 'email':
          case 'brevo':
          case 'sendgrid':
          case 'mailgun':
            config.email = {
              provider: this.getEmailProviderType(integration.integration_type),
              credentials,
              settings,
              isActive: true,
            };
            break;
          
          case 'sms':
          case 'twilio':
            config.sms = {
              provider: 'twilio',
              credentials: {
                accountSid: credentials.accountSid || credentials.account_sid,
                authToken: credentials.authToken || credentials.auth_token,
                apiKey: credentials.apiKey || credentials.api_key,
                apiSecret: credentials.apiSecret || credentials.api_secret,
              },
              settings: {
                fromNumber: settings.fromNumber || settings.from_number,
                messagingServiceSid: settings.messagingServiceSid || settings.messaging_service_sid,
              },
              isActive: true,
            };
            break;
          
          case 'slack':
          case 'discord':
          case 'teams':
            config.chat = {
              provider: integration.integration_type as 'slack' | 'discord' | 'teams',
              credentials,
              settings,
              isActive: true,
            };
            break;
        }
      }
    } catch (error) {
      console.error('Failed to fetch integration config:', error);
    }
    
    return config;
  }
  
  /**
   * Parse credentials (decrypt if needed)
   */
  private parseCredentials(encrypted: string | null): Record<string, string> {
    if (!encrypted) {
      return {};
    }
    
    try {
      // In production, decrypt the credentials
      // For now, assume it's JSON
      return JSON.parse(encrypted);
    } catch {
      return {};
    }
  }
  
  /**
   * Get email provider type from integration type
   */
  private getEmailProviderType(type: string): EmailProviderType {
    const providerMap: Record<string, EmailProviderType> = {
      brevo: 'brevo',
      sendinblue: 'brevo',
      sendgrid: 'sendgrid',
      mailgun: 'mailgun',
      ses: 'ses',
      postmark: 'postmark',
      email: 'brevo', // Default to Brevo
    };
    
    return providerMap[type.toLowerCase()] || 'brevo';
  }
}

// ── Environment-based Integration Manager ───────────────────────────

/**
 * Create integration manager with environment variables
 * Used when database is not available (e.g., serverless functions)
 */
export function createIntegrationManagerFromEnv(organizationId: string): TenantIntegrationManager {
  const manager = new TenantIntegrationManager(organizationId);
  
  // Override fetchIntegrationConfig to use environment variables
  // This is useful for development and serverless deployments
  (manager as unknown as Record<string, unknown>).fetchIntegrationConfig = async () => {
    const config: TenantIntegrationConfig = { organizationId };
    
    // Check for Brevo API key
    const brevoApiKey = process.env.BREVO_API_KEY;
    if (brevoApiKey) {
      config.email = {
        provider: 'brevo',
        credentials: { apiKey: brevoApiKey },
        settings: {},
        isActive: true,
      };
    }
    
    // Check for Twilio credentials
    const twilioAccountSid = process.env.TWILIO_ACCOUNT_SID;
    const twilioAuthToken = process.env.TWILIO_AUTH_TOKEN;
    
    if (twilioAccountSid && twilioAuthToken) {
      config.sms = {
        provider: 'twilio',
        credentials: {
          accountSid: twilioAccountSid,
          authToken: twilioAuthToken,
          apiKey: process.env.TWILIO_API_KEY,
          apiSecret: process.env.TWILIO_API_SECRET,
        },
        settings: {
          fromNumber: process.env.TWILIO_FROM_NUMBER,
          messagingServiceSid: process.env.TWILIO_MESSAGING_SERVICE_SID,
        },
        isActive: true,
      };
    }
    
    return config;
  };
  
  return manager;
}

// ── Mock Integration Manager (for testing) ──────────────────────────

export class MockIntegrationManager extends TenantIntegrationManager {
  private mockEmailAdapter?: MockEmailAdapter;
  private mockSMSAdapter?: MockSMSAdapter;
  private shouldFail = false;
  
  constructor(organizationId: string) {
    super(organizationId);
    this.mockEmailAdapter = new MockEmailAdapter();
    this.mockSMSAdapter = new MockSMSAdapter();
  }
  
  setFail(shouldFail: boolean): void {
    this.shouldFail = shouldFail;
    this.mockEmailAdapter?.setFail(shouldFail);
    this.mockSMSAdapter?.setFail(shouldFail);
  }
  
  async getAdapters(): Promise<AdapterSet> {
    return {
      email: this.mockEmailAdapter,
      sms: this.mockSMSAdapter,
    };
  }
  
  getSentEmails() {
    return this.mockEmailAdapter?.getSentEmails() || [];
  }
  
  getSentSMS() {
    return this.mockSMSAdapter?.getSentMessages() || [];
  }
  
  clearSent() {
    this.mockEmailAdapter?.clearSentEmails();
    this.mockSMSAdapter?.clearSentMessages();
  }
}

// ── Singleton Manager Cache ─────────────────────────────────────────

const managerCache = new Map<string, TenantIntegrationManager>();

/**
 * Get or create integration manager for an organization
 */
export function getIntegrationManager(organizationId: string): TenantIntegrationManager {
  let manager = managerCache.get(organizationId);
  
  if (!manager) {
    // Use environment-based manager for serverless
    manager = createIntegrationManagerFromEnv(organizationId);
    managerCache.set(organizationId, manager);
  }
  
  return manager;
}

/**
 * Clear manager cache
 */
export function clearIntegrationManagerCache(): void {
  managerCache.clear();
}
