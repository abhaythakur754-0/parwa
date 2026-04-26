/**
 * JARVIS Integration Adapter Types - Week 13 (Phase 4)
 *
 * Defines the adapter interface for connecting JARVIS to client integrations.
 * 
 * Architecture:
 * - Email: Pluggable (Brevo, SendGrid, etc.) - client chooses
 * - SMS: Twilio only - fixed provider
 * - Webhook/Chat: Configurable per client
 */

// ── Provider Types ─────────────────────────────────────────────────

export type EmailProviderType = 'brevo' | 'sendgrid' | 'mailgun' | 'ses' | 'postmark' | 'smtp';
export type SMSProviderType = 'twilio'; // Fixed - only Twilio supported
export type ChatProviderType = 'slack' | 'discord' | 'teams';
export type WebhookProviderType = 'generic' | 'zapier' | 'make';

export type IntegrationProviderType = EmailProviderType | SMSProviderType | ChatProviderType | WebhookProviderType;

// ── Adapter Status ─────────────────────────────────────────────────

export interface AdapterStatus {
  /** Whether the adapter is connected and ready */
  connected: boolean;
  /** Last successful operation timestamp */
  lastSuccess?: Date;
  /** Last error if any */
  lastError?: string;
  /** Provider type */
  providerType: IntegrationProviderType;
  /** Provider name */
  providerName: string;
}

// ── Email Adapter Types ────────────────────────────────────────────

export interface EmailAddress {
  email: string;
  name?: string;
}

export interface EmailAttachment {
  filename: string;
  content: string | Buffer;
  contentType?: string;
}

export interface SendEmailRequest {
  to: EmailAddress[];
  cc?: EmailAddress[];
  bcc?: EmailAddress[];
  from: EmailAddress;
  replyTo?: EmailAddress;
  subject: string;
  htmlBody?: string;
  textBody?: string;
  attachments?: EmailAttachment[];
  headers?: Record<string, string>;
  /** Template ID if using provider templates */
  templateId?: string;
  /** Template variables */
  templateVars?: Record<string, unknown>;
  /** Custom ID for tracking */
  customId?: string;
}

export interface SendEmailResponse {
  success: boolean;
  messageId?: string;
  providerResponse?: Record<string, unknown>;
  error?: string;
}

export interface EmailAdapter {
  readonly providerType: EmailProviderType;
  readonly providerName: string;
  
  /** Check if adapter is configured and ready */
  isReady(): Promise<boolean>;
  
  /** Get current status */
  getStatus(): Promise<AdapterStatus>;
  
  /** Send an email */
  sendEmail(request: SendEmailRequest): Promise<SendEmailResponse>;
  
  /** Send using a template */
  sendTemplateEmail(
    templateId: string,
    to: EmailAddress[],
    variables: Record<string, unknown>
  ): Promise<SendEmailResponse>;
  
  /** Validate configuration */
  validateConfig(): Promise<boolean>;
}

// ── SMS Adapter Types ──────────────────────────────────────────────

export interface SMSAddress {
  phone: string;
  /** Country code for formatting */
  countryCode?: string;
}

export interface SendSMSRequest {
  to: SMSAddress[];
  from?: string; // Sender ID
  message: string;
  /** For tracking */
  customId?: string;
  /** Scheduled send time */
  scheduledAt?: Date;
  /** Media URLs for MMS */
  mediaUrls?: string[];
}

export interface SendSMSResponse {
  success: boolean;
  messageSid?: string; // Twilio message SID
  providerResponse?: Record<string, unknown>;
  error?: string;
  /** Per-recipient status */
  recipients?: {
    phone: string;
    status: 'queued' | 'sent' | 'failed' | 'delivered' | 'undelivered';
    sid?: string;
    error?: string;
  }[];
}

export interface SMSAdapter {
  readonly providerType: SMSProviderType;
  readonly providerName: string;
  
  /** Check if adapter is configured and ready */
  isReady(): Promise<boolean>;
  
  /** Get current status */
  getStatus(): Promise<AdapterStatus>;
  
  /** Send an SMS */
  sendSMS(request: SendSMSRequest): Promise<SendSMSResponse>;
  
  /** Get message status */
  getMessageStatus(messageSid: string): Promise<{
    status: string;
    deliveredAt?: Date;
    error?: string;
  }>;
  
  /** Validate phone number format */
  validatePhoneNumber(phone: string): boolean;
  
  /** Validate configuration */
  validateConfig(): Promise<boolean>;
}

// ── Chat Adapter Types ─────────────────────────────────────────────

export interface ChatMessage {
  channel: string;
  text: string;
  blocks?: unknown[]; // Provider-specific blocks
  attachments?: ChatAttachment[];
  threadTs?: string; // For threaded replies
}

export interface ChatAttachment {
  title: string;
  text?: string;
  color?: string;
  fields?: {
    title: string;
    value: string;
    short?: boolean;
  }[];
  actions?: {
    type: string;
    text: string;
    url?: string;
    value?: string;
  }[];
}

export interface SendChatMessageResponse {
  success: boolean;
  messageId?: string;
  timestamp?: string;
  threadTs?: string;
  error?: string;
}

export interface ChatAdapter {
  readonly providerType: ChatProviderType;
  readonly providerName: string;
  
  /** Check if adapter is configured and ready */
  isReady(): Promise<boolean>;
  
  /** Get current status */
  getStatus(): Promise<AdapterStatus>;
  
  /** Send a chat message */
  sendMessage(message: ChatMessage): Promise<SendChatMessageResponse>;
  
  /** Post to a specific channel */
  postToChannel(channelId: string, message: Omit<ChatMessage, 'channel'>): Promise<SendChatMessageResponse>;
  
  /** Validate configuration */
  validateConfig(): Promise<boolean>;
}

// ── Webhook Adapter Types ──────────────────────────────────────────

export interface WebhookPayload {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  headers?: Record<string, string>;
  body?: Record<string, unknown>;
  /** Secret for HMAC signing */
  signingSecret?: string;
  /** Retry configuration */
  retryConfig?: {
    maxRetries: number;
    backoffMs: number;
  };
}

export interface WebhookResponse {
  success: boolean;
  statusCode?: number;
  responseBody?: string;
  error?: string;
  duration?: number;
}

export interface WebhookAdapter {
  readonly providerType: WebhookProviderType;
  readonly providerName: string;
  
  /** Check if adapter is configured and ready */
  isReady(): Promise<boolean>;
  
  /** Get current status */
  getStatus(): Promise<AdapterStatus>;
  
  /** Send a webhook */
  sendWebhook(payload: WebhookPayload): Promise<WebhookResponse>;
  
  /** Validate webhook signature */
  validateSignature(payload: string, signature: string, secret: string): boolean;
  
  /** Validate configuration */
  validateConfig(): Promise<boolean>;
}

// ── Tenant Integration Configuration ───────────────────────────────

export interface TenantIntegrationConfig {
  organizationId: string;
  
  /** Email integration settings */
  email?: {
    provider: EmailProviderType;
    credentials: Record<string, string>; // Encrypted in DB
    settings: Record<string, unknown>;
    isActive: boolean;
  };
  
  /** SMS integration settings (Twilio only) */
  sms?: {
    provider: SMSProviderType;
    credentials: {
      accountSid: string;
      authToken: string;
      apiKey?: string;
      apiSecret?: string;
    };
    settings: {
      fromNumber?: string;
      messagingServiceSid?: string;
    };
    isActive: boolean;
  };
  
  /** Chat integration settings */
  chat?: {
    provider: ChatProviderType;
    credentials: Record<string, string>;
    settings: {
      defaultChannel?: string;
      channels?: Record<string, string>;
    };
    isActive: boolean;
  };
  
  /** Webhook integration settings */
  webhooks?: {
    endpoints: {
      name: string;
      url: string;
      secret?: string;
      events: string[];
    }[];
    isActive: boolean;
  };
}

// ── JARVIS Action Types ────────────────────────────────────────────

/**
 * JARVIS can perform these actions through adapters.
 * Each action maps to the appropriate adapter.
 */
export type JarvisIntegrationAction =
  | { type: 'send_email'; payload: SendEmailRequest }
  | { type: 'send_sms'; payload: SendSMSRequest }
  | { type: 'send_chat'; payload: ChatMessage }
  | { type: 'trigger_webhook'; payload: WebhookPayload };

export interface JarvisIntegrationResult {
  success: boolean;
  action: JarvisIntegrationAction['type'];
  provider?: string;
  messageId?: string;
  error?: string;
  metadata?: Record<string, unknown>;
}

// ── Adapter Factory Types ───────────────────────────────────────────

export interface AdapterFactoryConfig {
  /** Tenant/organization ID */
  organizationId: string;
  /** Integration configuration from database */
  integrationConfig: TenantIntegrationConfig;
}

export interface AdapterSet {
  email?: EmailAdapter;
  sms?: SMSAdapter;
  chat?: ChatAdapter;
  webhook?: WebhookAdapter;
}
