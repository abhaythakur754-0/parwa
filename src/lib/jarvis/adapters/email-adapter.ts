/**
 * JARVIS Email Adapters - Week 13 (Phase 4)
 *
 * Email adapter implementations for JARVIS.
 * Supports multiple providers: Brevo, SendGrid, Mailgun, SES, Postmark, SMTP
 */

import type {
  EmailAdapter,
  EmailProviderType,
  SendEmailRequest,
  SendEmailResponse,
  AdapterStatus,
  EmailAddress,
} from './types';

// ── Base Email Adapter ─────────────────────────────────────────────

export abstract class BaseEmailAdapter implements EmailAdapter {
  abstract readonly providerType: EmailProviderType;
  abstract readonly providerName: string;
  
  abstract isReady(): Promise<boolean>;
  abstract getStatus(): Promise<AdapterStatus>;
  abstract sendEmail(request: SendEmailRequest): Promise<SendEmailResponse>;
  abstract sendTemplateEmail(
    templateId: string,
    to: EmailAddress[],
    variables: Record<string, unknown>
  ): Promise<SendEmailResponse>;
  abstract validateConfig(): Promise<boolean>;
  
  /**
   * Format email address for API
   */
  protected formatAddress(addr: EmailAddress): string {
    return addr.name ? `${addr.name} <${addr.email}>` : addr.email;
  }
  
  /**
   * Format multiple email addresses
   */
  protected formatAddresses(addrs: EmailAddress[]): string {
    return addrs.map(a => this.formatAddress(a)).join(', ');
  }
}

// ── Brevo Email Adapter ────────────────────────────────────────────

export interface BrevoConfig {
  apiKey: string;
  defaultSender?: EmailAddress;
}

export class BrevoEmailAdapter extends BaseEmailAdapter {
  readonly providerType: EmailProviderType = 'brevo';
  readonly providerName = 'Brevo (Sendinblue)';
  
  private config: BrevoConfig;
  private baseUrl = 'https://api.brevo.com/v3';
  private lastError?: string;
  private lastSuccess?: Date;
  
  constructor(config: BrevoConfig) {
    super();
    this.config = config;
  }
  
  async isReady(): Promise<boolean> {
    return !!(this.config.apiKey && this.config.apiKey.startsWith('xkeysib-'));
  }
  
  async getStatus(): Promise<AdapterStatus> {
    return {
      connected: await this.isReady(),
      lastSuccess: this.lastSuccess,
      lastError: this.lastError,
      providerType: this.providerType,
      providerName: this.providerName,
    };
  }
  
  async sendEmail(request: SendEmailRequest): Promise<SendEmailResponse> {
    try {
      // Prepare Brevo API payload
      const payload: Record<string, unknown> = {
        sender: {
          email: request.from.email,
          name: request.from.name || '',
        },
        to: request.to.map(a => ({ email: a.email, name: a.name || '' })),
        subject: request.subject,
        htmlContent: request.htmlBody || '',
        textContent: request.textBody || '',
      };
      
      if (request.cc && request.cc.length > 0) {
        payload.cc = request.cc.map(a => ({ email: a.email, name: a.name || '' }));
      }
      
      if (request.bcc && request.bcc.length > 0) {
        payload.bcc = request.bcc.map(a => ({ email: a.email, name: a.name || '' }));
      }
      
      if (request.replyTo) {
        payload.replyTo = { email: request.replyTo.email, name: request.replyTo.name || '' };
      }
      
      if (request.attachments && request.attachments.length > 0) {
        payload.attachment = request.attachments.map(a => ({
          name: a.filename,
          content: typeof a.content === 'string' ? a.content : a.content.toString('base64'),
        }));
      }
      
      if (request.customId) {
        payload.headers = {
          ...request.headers,
          'X-Mailin-custom': request.customId,
        };
      }
      
      // Make API call
      const response = await fetch(`${this.baseUrl}/smtp/email`, {
        method: 'POST',
        headers: {
          'accept': 'application/json',
          'content-type': 'application/json',
          'api-key': this.config.apiKey,
        },
        body: JSON.stringify(payload),
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        this.lastError = data.message || `HTTP ${response.status}`;
        return {
          success: false,
          error: this.lastError,
          providerResponse: data,
        };
      }
      
      this.lastSuccess = new Date();
      this.lastError = undefined;
      
      return {
        success: true,
        messageId: data.messageId as string,
        providerResponse: data,
      };
    } catch (error) {
      this.lastError = error instanceof Error ? error.message : 'Unknown error';
      return {
        success: false,
        error: this.lastError,
      };
    }
  }
  
  async sendTemplateEmail(
    templateId: string,
    to: EmailAddress[],
    variables: Record<string, unknown>
  ): Promise<SendEmailResponse> {
    try {
      const payload = {
        templateId: parseInt(templateId, 10),
        to: to.map(a => ({ email: a.email, name: a.name || '' })),
        params: variables,
        sender: this.config.defaultSender ? {
          email: this.config.defaultSender.email,
          name: this.config.defaultSender.name || '',
        } : undefined,
      };
      
      const response = await fetch(`${this.baseUrl}/smtp/email`, {
        method: 'POST',
        headers: {
          'accept': 'application/json',
          'content-type': 'application/json',
          'api-key': this.config.apiKey,
        },
        body: JSON.stringify(payload),
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        this.lastError = data.message || `HTTP ${response.status}`;
        return {
          success: false,
          error: this.lastError,
          providerResponse: data,
        };
      }
      
      this.lastSuccess = new Date();
      this.lastError = undefined;
      
      return {
        success: true,
        messageId: data.messageId as string,
        providerResponse: data,
      };
    } catch (error) {
      this.lastError = error instanceof Error ? error.message : 'Unknown error';
      return {
        success: false,
        error: this.lastError,
      };
    }
  }
  
  async validateConfig(): Promise<boolean> {
    try {
      // Test API key by getting account info
      const response = await fetch(`${this.baseUrl}/account`, {
        method: 'GET',
        headers: {
          'accept': 'application/json',
          'api-key': this.config.apiKey,
        },
      });
      
      return response.ok;
    } catch {
      return false;
    }
  }
}

// ── SendGrid Email Adapter ──────────────────────────────────────────

export interface SendGridConfig {
  apiKey: string;
  defaultSender?: EmailAddress;
}

export class SendGridEmailAdapter extends BaseEmailAdapter {
  readonly providerType: EmailProviderType = 'sendgrid';
  readonly providerName = 'SendGrid';
  
  private config: SendGridConfig;
  private baseUrl = 'https://api.sendgrid.com/v3';
  private lastError?: string;
  private lastSuccess?: Date;
  
  constructor(config: SendGridConfig) {
    super();
    this.config = config;
  }
  
  async isReady(): Promise<boolean> {
    return !!(this.config.apiKey && this.config.apiKey.startsWith('SG.'));
  }
  
  async getStatus(): Promise<AdapterStatus> {
    return {
      connected: await this.isReady(),
      lastSuccess: this.lastSuccess,
      lastError: this.lastError,
      providerType: this.providerType,
      providerName: this.providerName,
    };
  }
  
  async sendEmail(request: SendEmailRequest): Promise<SendEmailResponse> {
    try {
      const payload: Record<string, unknown> = {
        personalizations: [
          {
            to: request.to.map(a => ({ email: a.email, name: a.name })),
            subject: request.subject,
          },
        ],
        from: {
          email: request.from.email,
          name: request.from.name,
        },
        content: [],
      };
      
      if (request.htmlBody) {
        (payload.content as unknown[]).push({
          type: 'text/html',
          value: request.htmlBody,
        });
      }
      
      if (request.textBody) {
        (payload.content as unknown[]).push({
          type: 'text/plain',
          value: request.textBody,
        });
      }
      
      const response = await fetch(`${this.baseUrl}/mail/send`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.config.apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      
      // SendGrid returns 202 on success with no body
      if (response.status === 202) {
        this.lastSuccess = new Date();
        this.lastError = undefined;
        
        const messageId = response.headers.get('X-Message-Id');
        return {
          success: true,
          messageId: messageId || undefined,
        };
      }
      
      const data = await response.json();
      this.lastError = data.errors?.[0]?.message || `HTTP ${response.status}`;
      
      return {
        success: false,
        error: this.lastError,
        providerResponse: data,
      };
    } catch (error) {
      this.lastError = error instanceof Error ? error.message : 'Unknown error';
      return {
        success: false,
        error: this.lastError,
      };
    }
  }
  
  async sendTemplateEmail(
    templateId: string,
    to: EmailAddress[],
    variables: Record<string, unknown>
  ): Promise<SendEmailResponse> {
    try {
      const payload = {
        template_id: templateId,
        personalizations: [
          {
            to: to.map(a => ({ email: a.email, name: a.name })),
            dynamic_template_data: variables,
          },
        ],
        from: this.config.defaultSender ? {
          email: this.config.defaultSender.email,
          name: this.config.defaultSender.name,
        } : undefined,
      };
      
      const response = await fetch(`${this.baseUrl}/mail/send`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.config.apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      
      if (response.status === 202) {
        this.lastSuccess = new Date();
        this.lastError = undefined;
        return { success: true };
      }
      
      const data = await response.json();
      this.lastError = data.errors?.[0]?.message || `HTTP ${response.status}`;
      return { success: false, error: this.lastError };
    } catch (error) {
      this.lastError = error instanceof Error ? error.message : 'Unknown error';
      return { success: false, error: this.lastError };
    }
  }
  
  async validateConfig(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/user/account`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.config.apiKey}`,
        },
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}

// ── Mock Email Adapter (for testing) ────────────────────────────────

export class MockEmailAdapter extends BaseEmailAdapter {
  readonly providerType: EmailProviderType = 'brevo';
  readonly providerName = 'Mock Email';
  
  private sentEmails: SendEmailRequest[] = [];
  private shouldFail = false;
  
  setFail(shouldFail: boolean): void {
    this.shouldFail = shouldFail;
  }
  
  getSentEmails(): SendEmailRequest[] {
    return this.sentEmails;
  }
  
  clearSentEmails(): void {
    this.sentEmails = [];
  }
  
  async isReady(): Promise<boolean> {
    return true;
  }
  
  async getStatus(): Promise<AdapterStatus> {
    return {
      connected: true,
      providerType: this.providerType,
      providerName: this.providerName,
    };
  }
  
  async sendEmail(request: SendEmailRequest): Promise<SendEmailResponse> {
    if (this.shouldFail) {
      return { success: false, error: 'Mock failure' };
    }
    
    this.sentEmails.push(request);
    return {
      success: true,
      messageId: `mock-${Date.now()}`,
    };
  }
  
  async sendTemplateEmail(
    _templateId: string,
    to: EmailAddress[],
    _variables: Record<string, unknown>
  ): Promise<SendEmailResponse> {
    if (this.shouldFail) {
      return { success: false, error: 'Mock failure' };
    }
    
    return {
      success: true,
      messageId: `mock-template-${Date.now()}`,
    };
  }
  
  async validateConfig(): Promise<boolean> {
    return true;
  }
}

// ── Email Adapter Factory ───────────────────────────────────────────

export function createEmailAdapter(
  provider: EmailProviderType,
  config: Record<string, unknown>
): EmailAdapter {
  switch (provider) {
    case 'brevo':
      return new BrevoEmailAdapter({
        apiKey: config.apiKey as string,
        defaultSender: config.defaultSender as EmailAddress | undefined,
      });
    
    case 'sendgrid':
      return new SendGridEmailAdapter({
        apiKey: config.apiKey as string,
        defaultSender: config.defaultSender as EmailAddress | undefined,
      });
    
    default:
      throw new Error(`Unsupported email provider: ${provider}`);
  }
}
