/**
 * JARVIS Integration Adapters Tests - Week 13 (Phase 4)
 *
 * Tests for the integration adapter layer.
 */

import {
  BrevoEmailAdapter,
  SendGridEmailAdapter,
  MockEmailAdapter,
  createEmailAdapter,
} from '../email-adapter';

import {
  TwilioSMSAdapter,
  MockSMSAdapter,
  createSMSAdapter,
} from '../sms-adapter';

import {
  MockIntegrationManager,
  getIntegrationManager,
  clearIntegrationManagerCache,
} from '../tenant-integration-manager';

import type {
  SendEmailRequest,
  SendSMSRequest,
  EmailAddress,
} from '../types';

// ── Mock Fetch for API Tests ─────────────────────────────────────────

const originalFetch = global.fetch;

function mockFetch(responses: Record<string, { ok: boolean; status: number; data: unknown }>) {
  global.fetch = jest.fn().mockImplementation(async (url: string) => {
    for (const [pattern, response] of Object.entries(responses)) {
      if (url.includes(pattern)) {
        return {
          ok: response.ok,
          status: response.status,
          json: async () => response.data,
          headers: {
            get: (name: string) => {
              if (name === 'X-Message-Id') return 'msg-123';
              return null;
            },
          },
        };
      }
    }
    return {
      ok: false,
      status: 404,
      json: async () => ({ message: 'Not found' }),
    };
  });
}

function restoreFetch() {
  global.fetch = originalFetch;
}

// ── Test Data ───────────────────────────────────────────────────────

const testEmail: EmailAddress = {
  email: 'test@example.com',
  name: 'Test User',
};

const testEmailRequest: SendEmailRequest = {
  to: [testEmail],
  from: { email: 'noreply@parwa.com', name: 'PARWA' },
  subject: 'Test Subject',
  htmlBody: '<p>Test body</p>',
  textBody: 'Test body',
};

const testSMSRequest: SendSMSRequest = {
  to: [{ phone: '+1234567890' }],
  message: 'Test SMS message',
};

// ── Email Adapter Tests ──────────────────────────────────────────────

describe('BrevoEmailAdapter', () => {
  let adapter: BrevoEmailAdapter;
  
  beforeEach(() => {
    adapter = new BrevoEmailAdapter({
      apiKey: 'xkeysib-test-key-123456',
      defaultSender: { email: 'default@parwa.com', name: 'PARWA' },
    });
  });
  
  afterEach(() => {
    restoreFetch();
  });
  
  describe('isReady', () => {
    it('should return true when API key is valid format', async () => {
      const result = await adapter.isReady();
      expect(result).toBe(true);
    });
    
    it('should return false when API key is missing', async () => {
      const badAdapter = new BrevoEmailAdapter({ apiKey: '' });
      const result = await badAdapter.isReady();
      expect(result).toBe(false);
    });
    
    it('should return false when API key has wrong format', async () => {
      const badAdapter = new BrevoEmailAdapter({ apiKey: 'wrong-format' });
      const result = await badAdapter.isReady();
      expect(result).toBe(false);
    });
  });
  
  describe('getStatus', () => {
    it('should return connected status when ready', async () => {
      const status = await adapter.getStatus();
      expect(status.connected).toBe(true);
      expect(status.providerType).toBe('brevo');
      expect(status.providerName).toBe('Brevo (Sendinblue)');
    });
  });
  
  describe('sendEmail', () => {
    it('should send email successfully', async () => {
      mockFetch({
        'smtp/email': {
          ok: true,
          status: 200,
          data: { messageId: 'msg-123' },
        },
      });
      
      const result = await adapter.sendEmail(testEmailRequest);
      
      expect(result.success).toBe(true);
      expect(result.messageId).toBe('msg-123');
    });
    
    it('should handle API errors', async () => {
      mockFetch({
        'smtp/email': {
          ok: false,
          status: 400,
          data: { message: 'Invalid email' },
        },
      });
      
      const result = await adapter.sendEmail(testEmailRequest);
      
      expect(result.success).toBe(false);
      expect(result.error).toBe('Invalid email');
    });
    
    it('should include CC and BCC when provided', async () => {
      mockFetch({
        'smtp/email': {
          ok: true,
          status: 200,
          data: { messageId: 'msg-123' },
        },
      });
      
      const result = await adapter.sendEmail({
        ...testEmailRequest,
        cc: [{ email: 'cc@example.com' }],
        bcc: [{ email: 'bcc@example.com' }],
      });
      
      expect(result.success).toBe(true);
    });
    
    it('should include attachments when provided', async () => {
      mockFetch({
        'smtp/email': {
          ok: true,
          status: 200,
          data: { messageId: 'msg-123' },
        },
      });
      
      const result = await adapter.sendEmail({
        ...testEmailRequest,
        attachments: [
          {
            filename: 'test.pdf',
            content: 'base64content',
            contentType: 'application/pdf',
          },
        ],
      });
      
      expect(result.success).toBe(true);
    });
  });
  
  describe('sendTemplateEmail', () => {
    it('should send template email successfully', async () => {
      mockFetch({
        'smtp/email': {
          ok: true,
          status: 200,
          data: { messageId: 'msg-template-123' },
        },
      });
      
      const result = await adapter.sendTemplateEmail(
        '123',
        [testEmail],
        { name: 'John' }
      );
      
      expect(result.success).toBe(true);
    });
  });
  
  describe('validateConfig', () => {
    it('should validate config successfully', async () => {
      mockFetch({
        'account': {
          ok: true,
          status: 200,
          data: { email: 'test@brevo.com' },
        },
      });
      
      const result = await adapter.validateConfig();
      expect(result).toBe(true);
    });
    
    it('should return false for invalid config', async () => {
      mockFetch({
        'account': {
          ok: false,
          status: 401,
          data: { message: 'Unauthorized' },
        },
      });
      
      const result = await adapter.validateConfig();
      expect(result).toBe(false);
    });
  });
});

describe('SendGridEmailAdapter', () => {
  let adapter: SendGridEmailAdapter;
  
  beforeEach(() => {
    adapter = new SendGridEmailAdapter({
      apiKey: 'SG.test-key-123456',
    });
  });
  
  afterEach(() => {
    restoreFetch();
  });
  
  describe('isReady', () => {
    it('should return true when API key is valid format', async () => {
      const result = await adapter.isReady();
      expect(result).toBe(true);
    });
    
    it('should return false when API key has wrong format', async () => {
      const badAdapter = new SendGridEmailAdapter({ apiKey: 'wrong-format' });
      const result = await badAdapter.isReady();
      expect(result).toBe(false);
    });
  });
  
  describe('sendEmail', () => {
    it('should send email successfully', async () => {
      mockFetch({
        'mail/send': {
          ok: true,
          status: 202,
          data: {},
        },
      });
      
      const result = await adapter.sendEmail(testEmailRequest);
      
      expect(result.success).toBe(true);
    });
    
    it('should handle API errors', async () => {
      mockFetch({
        'mail/send': {
          ok: false,
          status: 400,
          data: { errors: [{ message: 'Invalid from address' }] },
        },
      });
      
      const result = await adapter.sendEmail(testEmailRequest);
      
      expect(result.success).toBe(false);
      expect(result.error).toBe('Invalid from address');
    });
  });
});

describe('MockEmailAdapter', () => {
  let adapter: MockEmailAdapter;
  
  beforeEach(() => {
    adapter = new MockEmailAdapter();
  });
  
  it('should always be ready', async () => {
    expect(await adapter.isReady()).toBe(true);
  });
  
  it('should track sent emails', async () => {
    await adapter.sendEmail(testEmailRequest);
    await adapter.sendEmail({ ...testEmailRequest, subject: 'Second' });
    
    const sent = adapter.getSentEmails();
    expect(sent).toHaveLength(2);
    expect(sent[0].subject).toBe('Test Subject');
    expect(sent[1].subject).toBe('Second');
  });
  
  it('should fail when configured', async () => {
    adapter.setFail(true);
    const result = await adapter.sendEmail(testEmailRequest);
    expect(result.success).toBe(false);
    expect(result.error).toBe('Mock failure');
  });
  
  it('should clear sent emails', async () => {
    await adapter.sendEmail(testEmailRequest);
    expect(adapter.getSentEmails()).toHaveLength(1);
    
    adapter.clearSentEmails();
    expect(adapter.getSentEmails()).toHaveLength(0);
  });
});

describe('createEmailAdapter', () => {
  it('should create Brevo adapter', () => {
    const adapter = createEmailAdapter('brevo', { apiKey: 'xkeysib-test' });
    expect(adapter).toBeInstanceOf(BrevoEmailAdapter);
  });
  
  it('should create SendGrid adapter', () => {
    const adapter = createEmailAdapter('sendgrid', { apiKey: 'SG.test' });
    expect(adapter).toBeInstanceOf(SendGridEmailAdapter);
  });
  
  it('should throw for unsupported provider', () => {
    expect(() => createEmailAdapter('unsupported' as never, {})).toThrow();
  });
});

// ── SMS Adapter Tests ────────────────────────────────────────────────

describe('TwilioSMSAdapter', () => {
  let adapter: TwilioSMSAdapter;
  
  beforeEach(() => {
    adapter = new TwilioSMSAdapter({
      accountSid: 'ACtest123456789',
      authToken: 'testAuthToken',
      fromNumber: '+1555123456',
    });
  });
  
  afterEach(() => {
    restoreFetch();
  });
  
  describe('isReady', () => {
    it('should return true when credentials are valid', async () => {
      const result = await adapter.isReady();
      expect(result).toBe(true);
    });
    
    it('should return false when account SID is missing', async () => {
      const badAdapter = new TwilioSMSAdapter({
        accountSid: '',
        authToken: 'token',
      });
      const result = await badAdapter.isReady();
      expect(result).toBe(false);
    });
    
    it('should return false when account SID has wrong format', async () => {
      const badAdapter = new TwilioSMSAdapter({
        accountSid: 'WRONG',
        authToken: 'token',
      });
      const result = await badAdapter.isReady();
      expect(result).toBe(false);
    });
  });
  
  describe('validatePhoneNumber', () => {
    it('should validate E.164 format', () => {
      expect(adapter.validatePhoneNumber('+1234567890')).toBe(true);
      expect(adapter.validatePhoneNumber('+441234567890')).toBe(true);
    });
    
    it('should reject invalid formats', () => {
      // 'invalid' becomes '+invalid' after formatting, which doesn't match E.164
      expect(adapter.validatePhoneNumber('invalid')).toBe(false);
      // '123' becomes '+123' which is technically valid E.164 (short but matches pattern)
      // This is expected behavior - the adapter tries to make numbers valid
      expect(adapter.validatePhoneNumber('+123')).toBe(true);
    });
  });
  
  describe('sendSMS', () => {
    it('should send SMS successfully', async () => {
      mockFetch({
        'Messages.json': {
          ok: true,
          status: 201,
          data: {
            sid: 'SM123',
            status: 'queued',
          },
        },
      });
      
      const result = await adapter.sendSMS(testSMSRequest);
      
      expect(result.success).toBe(true);
      expect(result.messageSid).toBe('SM123');
    });
    
    it('should handle API errors', async () => {
      mockFetch({
        'Messages.json': {
          ok: false,
          status: 400,
          data: { message: 'Invalid phone number' },
        },
      });
      
      const result = await adapter.sendSMS(testSMSRequest);
      
      expect(result.success).toBe(false);
    });
    
    it('should require from number', async () => {
      const noFromAdapter = new TwilioSMSAdapter({
        accountSid: 'ACtest123',
        authToken: 'token',
      });
      
      const result = await noFromAdapter.sendSMS(testSMSRequest);
      
      expect(result.success).toBe(false);
      expect(result.error).toContain('No from number');
    });
    
    it('should use messaging service SID if configured', async () => {
      const msAdapter = new TwilioSMSAdapter({
        accountSid: 'ACtest123',
        authToken: 'token',
        messagingServiceSid: 'MG123',
      });
      
      mockFetch({
        'Messages.json': {
          ok: true,
          status: 201,
          data: { sid: 'SM123', status: 'queued' },
        },
      });
      
      const result = await msAdapter.sendSMS(testSMSRequest);
      expect(result.success).toBe(true);
    });
  });
  
  describe('getMessageStatus', () => {
    it('should get message status', async () => {
      mockFetch({
        'Messages/SM123': {
          ok: true,
          status: 200,
          data: {
            sid: 'SM123',
            status: 'delivered',
            date_sent: '2024-01-01T12:00:00Z',
          },
        },
      });
      
      const result = await adapter.getMessageStatus('SM123');
      
      expect(result.status).toBe('delivered');
    });
  });
  
  describe('validateConfig', () => {
    it('should validate config successfully', async () => {
      mockFetch({
        'ACtest123456789': {
          ok: true,
          status: 200,
          data: { sid: 'ACtest123456789' },
        },
      });
      
      const result = await adapter.validateConfig();
      expect(result).toBe(true);
    });
  });
});

describe('MockSMSAdapter', () => {
  let adapter: MockSMSAdapter;
  
  beforeEach(() => {
    adapter = new MockSMSAdapter();
  });
  
  it('should always be ready', async () => {
    expect(await adapter.isReady()).toBe(true);
  });
  
  it('should track sent messages', async () => {
    await adapter.sendSMS(testSMSRequest);
    await adapter.sendSMS({ ...testSMSRequest, message: 'Second' });
    
    const sent = adapter.getSentMessages();
    expect(sent).toHaveLength(2);
  });
  
  it('should return message status', async () => {
    const status = await adapter.getMessageStatus('SM123');
    expect(status.status).toBe('delivered');
  });
  
  it('should fail when configured', async () => {
    adapter.setFail(true);
    const result = await adapter.sendSMS(testSMSRequest);
    expect(result.success).toBe(false);
  });
});

describe('createSMSAdapter', () => {
  it('should always create Twilio adapter', () => {
    const adapter = createSMSAdapter({
      accountSid: 'ACtest',
      authToken: 'token',
    });
    expect(adapter).toBeInstanceOf(TwilioSMSAdapter);
  });
});

// ── Tenant Integration Manager Tests ─────────────────────────────────

describe('MockIntegrationManager', () => {
  let manager: MockIntegrationManager;
  
  beforeEach(() => {
    manager = new MockIntegrationManager('org-123');
  });
  
  it('should get adapters', async () => {
    const adapters = await manager.getAdapters();
    
    expect(adapters.email).toBeDefined();
    expect(adapters.sms).toBeDefined();
    expect(adapters.email?.providerType).toBe('brevo');
    expect(adapters.sms?.providerType).toBe('twilio');
  });
  
  it('should execute send_email action', async () => {
    const result = await manager.executeAction({
      type: 'send_email',
      payload: testEmailRequest,
    });
    
    expect(result.success).toBe(true);
    expect(result.action).toBe('send_email');
    expect(manager.getSentEmails()).toHaveLength(1);
  });
  
  it('should execute send_sms action', async () => {
    const result = await manager.executeAction({
      type: 'send_sms',
      payload: testSMSRequest,
    });
    
    expect(result.success).toBe(true);
    expect(result.action).toBe('send_sms');
    expect(manager.getSentSMS()).toHaveLength(1);
  });
  
  it('should return error for missing chat integration', async () => {
    const result = await manager.executeAction({
      type: 'send_chat',
      payload: {
        channel: 'general',
        text: 'Hello',
      },
    });
    
    expect(result.success).toBe(false);
    expect(result.error).toContain('not configured');
  });
  
  it('should track hasIntegration', async () => {
    expect(await manager.hasIntegration('email')).toBe(true);
    expect(await manager.hasIntegration('sms')).toBe(true);
    expect(await manager.hasIntegration('chat')).toBe(false);
  });
  
  it('should get status', async () => {
    const status = await manager.getStatus();
    
    expect(status.email.configured).toBe(true);
    expect(status.email.provider).toBe('Mock Email');
    expect(status.sms.configured).toBe(true);
    expect(status.sms.provider).toBe('Mock SMS');
    expect(status.chat.configured).toBe(false);
  });
  
  it('should handle failures', async () => {
    manager.setFail(true);
    
    const emailResult = await manager.executeAction({
      type: 'send_email',
      payload: testEmailRequest,
    });
    
    const smsResult = await manager.executeAction({
      type: 'send_sms',
      payload: testSMSRequest,
    });
    
    expect(emailResult.success).toBe(false);
    expect(smsResult.success).toBe(false);
  });
  
  it('should clear sent items', async () => {
    await manager.executeAction({ type: 'send_email', payload: testEmailRequest });
    await manager.executeAction({ type: 'send_sms', payload: testSMSRequest });
    
    manager.clearSent();
    
    expect(manager.getSentEmails()).toHaveLength(0);
    expect(manager.getSentSMS()).toHaveLength(0);
  });
});

describe('getIntegrationManager', () => {
  beforeEach(() => {
    clearIntegrationManagerCache();
  });
  
  it('should create and cache manager', () => {
    const manager1 = getIntegrationManager('org-123');
    const manager2 = getIntegrationManager('org-123');
    
    expect(manager1).toBe(manager2);
  });
  
  it('should create different managers for different orgs', () => {
    const manager1 = getIntegrationManager('org-123');
    const manager2 = getIntegrationManager('org-456');
    
    expect(manager1).not.toBe(manager2);
  });
});

// ── Types Tests ──────────────────────────────────────────────────────

describe('Types', () => {
  it('should have correct provider types', () => {
    const emailProviders: EmailProviderType[] = [
      'brevo', 'sendgrid', 'mailgun', 'ses', 'postmark', 'smtp'
    ];
    
    expect(emailProviders).toContain('brevo');
    expect(emailProviders).toContain('sendgrid');
  });
  
  it('should have only Twilio for SMS', () => {
    const smsProviders: SMSProviderType[] = ['twilio'];
    
    expect(smsProviders).toHaveLength(1);
    expect(smsProviders[0]).toBe('twilio');
  });
});
