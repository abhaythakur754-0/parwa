/**
 * JARVIS SMS Adapter - Week 13 (Phase 4)
 *
 * SMS adapter implementation for JARVIS.
 * Uses Twilio as the FIXED SMS provider (no other SMS APIs).
 */

import type {
  SMSAdapter,
  SMSProviderType,
  SendSMSRequest,
  SendSMSResponse,
  AdapterStatus,
} from './types';

// ── Twilio SMS Adapter ─────────────────────────────────────────────

export interface TwilioConfig {
  accountSid: string;
  authToken: string;
  apiKey?: string;
  apiSecret?: string;
  /** Default from number */
  fromNumber?: string;
  /** Messaging Service SID for multiple numbers */
  messagingServiceSid?: string;
}

export class TwilioSMSAdapter implements SMSAdapter {
  readonly providerType: SMSProviderType = 'twilio';
  readonly providerName = 'Twilio';
  
  private config: TwilioConfig;
  private baseUrl: string;
  private lastError?: string;
  private lastSuccess?: Date;
  
  constructor(config: TwilioConfig) {
    this.config = config;
    this.baseUrl = `https://api.twilio.com/2010-04-01/Accounts/${config.accountSid}`;
  }
  
  async isReady(): Promise<boolean> {
    return !!(
      this.config.accountSid &&
      this.config.accountSid.startsWith('AC') &&
      this.config.authToken
    );
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
  
  /**
   * Get auth header for Twilio API
   */
  private getAuthHeader(): string {
    // Use API key if provided, otherwise use account SID and auth token
    const credentials = this.config.apiKey && this.config.apiSecret
      ? `${this.config.apiKey}:${this.config.apiSecret}`
      : `${this.config.accountSid}:${this.config.authToken}`;
    
    return `Basic ${Buffer.from(credentials).toString('base64')}`;
  }
  
  /**
   * Format phone number to E.164 format
   */
  private formatPhoneNumber(phone: string): string {
    // Remove spaces, dashes, parentheses
    let formatted = phone.replace(/[\s\-\(\)]/g, '');
    
    // Add + if missing
    if (!formatted.startsWith('+')) {
      // Assume US number if no country code
      if (formatted.length === 10) {
        formatted = `+1${formatted}`;
      } else {
        formatted = `+${formatted}`;
      }
    }
    
    return formatted;
  }
  
  validatePhoneNumber(phone: string): boolean {
    const formatted = this.formatPhoneNumber(phone);
    // E.164 format: +[country code][number], max 15 digits
    const e164Regex = /^\+[1-9]\d{1,14}$/;
    return e164Regex.test(formatted);
  }
  
  async sendSMS(request: SendSMSRequest): Promise<SendSMSResponse> {
    try {
      // Use messaging service or individual from number
      const from = this.config.messagingServiceSid || request.from || this.config.fromNumber;
      
      if (!from) {
        return {
          success: false,
          error: 'No from number or messaging service configured',
        };
      }
      
      // Prepare form data for Twilio API
      const formData = new URLSearchParams();
      formData.append('Body', request.message);
      
      if (this.config.messagingServiceSid) {
        formData.append('MessagingServiceSid', this.config.messagingServiceSid);
      } else {
        formData.append('From', from);
      }
      
      // If multiple recipients, send individually (Twilio doesn't support batch in one call)
      const results: SendSMSResponse['recipients'] = [];
      
      for (const recipient of request.to) {
        const phone = this.formatPhoneNumber(recipient.phone);
        formData.set('To', phone);
        
        if (request.customId) {
          formData.set('StatusCallback', request.customId);
        }
        
        const response = await fetch(`${this.baseUrl}/Messages.json`, {
          method: 'POST',
          headers: {
            'Authorization': this.getAuthHeader(),
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: formData.toString(),
        });
        
        const data = await response.json();
        
        if (response.ok) {
          results.push({
            phone: recipient.phone,
            status: data.status as 'queued' | 'sent' | 'failed',
            sid: data.sid,
          });
        } else {
          results.push({
            phone: recipient.phone,
            status: 'failed',
            error: data.message || `HTTP ${response.status}`,
          });
        }
      }
      
      // Check if all succeeded
      const allSuccess = results.every(r => r.status !== 'failed');
      const firstResult = results[0];
      
      if (allSuccess) {
        this.lastSuccess = new Date();
        this.lastError = undefined;
        
        return {
          success: true,
          messageSid: firstResult?.sid,
          recipients: results,
        };
      } else {
        this.lastError = 'Some messages failed';
        return {
          success: false,
          messageSid: firstResult?.sid,
          recipients: results,
          error: this.lastError,
        };
      }
    } catch (error) {
      this.lastError = error instanceof Error ? error.message : 'Unknown error';
      return {
        success: false,
        error: this.lastError,
      };
    }
  }
  
  async getMessageStatus(messageSid: string): Promise<{
    status: string;
    deliveredAt?: Date;
    error?: string;
  }> {
    try {
      const response = await fetch(`${this.baseUrl}/Messages/${messageSid}.json`, {
        method: 'GET',
        headers: {
          'Authorization': this.getAuthHeader(),
        },
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        return {
          status: 'unknown',
          error: data.message || `HTTP ${response.status}`,
        };
      }
      
      return {
        status: data.status,
        deliveredAt: data.date_sent ? new Date(data.date_sent) : undefined,
        error: data.error_message,
      };
    } catch (error) {
      return {
        status: 'unknown',
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
  
  async validateConfig(): Promise<boolean> {
    try {
      // Test credentials by fetching account info
      const response = await fetch(`${this.baseUrl}.json`, {
        method: 'GET',
        headers: {
          'Authorization': this.getAuthHeader(),
        },
      });
      
      return response.ok;
    } catch {
      return false;
    }
  }
  
  /**
   * Get available phone numbers
   */
  async getPhoneNumbers(): Promise<{ phoneNumber: string; friendlyName: string }[]> {
    try {
      const response = await fetch(
        `${this.baseUrl}/IncomingPhoneNumbers.json`,
        {
          method: 'GET',
          headers: {
            'Authorization': this.getAuthHeader(),
          },
        }
      );
      
      const data = await response.json();
      
      if (!response.ok) {
        return [];
      }
      
      return (data.incoming_phone_numbers || []).map((n: Record<string, unknown>) => ({
        phoneNumber: n.phone_number as string,
        friendlyName: n.friendly_name as string,
      }));
    } catch {
      return [];
    }
  }
  
  /**
   * Get messaging services
   */
  async getMessagingServices(): Promise<{ sid: string; friendlyName: string }[]> {
    try {
      const response = await fetch(
        `${this.baseUrl}/MessagingServices.json`,
        {
          method: 'GET',
          headers: {
            'Authorization': this.getAuthHeader(),
          },
        }
      );
      
      const data = await response.json();
      
      if (!response.ok) {
        return [];
      }
      
      return (data.services || []).map((s: Record<string, unknown>) => ({
        sid: s.sid as string,
        friendlyName: s.friendly_name as string,
      }));
    } catch {
      return [];
    }
  }
}

// ── Mock SMS Adapter (for testing) ──────────────────────────────────

export class MockSMSAdapter implements SMSAdapter {
  readonly providerType: SMSProviderType = 'twilio';
  readonly providerName = 'Mock SMS';
  
  private sentMessages: SendSMSRequest[] = [];
  private shouldFail = false;
  
  setFail(shouldFail: boolean): void {
    this.shouldFail = shouldFail;
  }
  
  getSentMessages(): SendSMSRequest[] {
    return this.sentMessages;
  }
  
  clearSentMessages(): void {
    this.sentMessages = [];
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
  
  async sendSMS(request: SendSMSRequest): Promise<SendSMSResponse> {
    if (this.shouldFail) {
      return { success: false, error: 'Mock failure' };
    }
    
    this.sentMessages.push(request);
    
    return {
      success: true,
      messageSid: `SM${Date.now()}`,
      recipients: request.to.map(r => ({
        phone: r.phone,
        status: 'queued' as const,
        sid: `SM${Date.now()}-${r.phone}`,
      })),
    };
  }
  
  async getMessageStatus(_messageSid: string): Promise<{
    status: string;
    deliveredAt?: Date;
    error?: string;
  }> {
    if (this.shouldFail) {
      return { status: 'failed', error: 'Mock failure' };
    }
    
    return {
      status: 'delivered',
      deliveredAt: new Date(),
    };
  }
  
  validatePhoneNumber(phone: string): boolean {
    const e164Regex = /^\+[1-9]\d{1,14}$/;
    const cleaned = phone.replace(/[\s\-\(\)]/g, '');
    return e164Regex.test(cleaned) || cleaned.length >= 10;
  }
  
  async validateConfig(): Promise<boolean> {
    return true;
  }
}

// ── SMS Adapter Factory ─────────────────────────────────────────────

/**
 * Create SMS adapter - ALWAYS returns Twilio adapter
 * SMS is fixed to Twilio provider
 */
export function createSMSAdapter(config: Record<string, unknown>): SMSAdapter {
  return new TwilioSMSAdapter({
    accountSid: config.accountSid as string,
    authToken: config.authToken as string,
    apiKey: config.apiKey as string | undefined,
    apiSecret: config.apiSecret as string | undefined,
    fromNumber: config.fromNumber as string | undefined,
    messagingServiceSid: config.messagingServiceSid as string | undefined,
  });
}
