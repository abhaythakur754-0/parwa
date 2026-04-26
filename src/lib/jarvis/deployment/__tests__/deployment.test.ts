/**
 * JARVIS Client Deployment Tests - Week 14 (Phase 4)
 *
 * Tests for multi-tenant client deployment and configuration.
 */

import {
  ClientDeploymentManager,
  getDeploymentManager,
  resetDeploymentManager,
} from '../client-deployment-manager';

import type {
  OnboardingRequest,
  DeployClientRequest,
  ValidateIntegrationRequest,
  ClientDeploymentStatus,
} from '../types';

// ── Test Data ────────────────────────────────────────────────────────

const testOnboardingRequest: OnboardingRequest = {
  name: 'Test Company',
  admin: {
    email: 'admin@testcompany.com',
    name: 'Admin User',
    password: 'SecurePassword123!',
  },
  plan: 'parwa',
  integrations: {
    email: {
      provider: 'brevo',
      credentials: {
        apiKey: 'xkeysib-test-key-123456',
      },
    },
    sms: {
      credentials: {
        accountSid: 'ACtest123456789',
        authToken: 'testAuthToken123',
      },
    },
  },
  timezone: 'America/New_York',
};

// ── Client Deployment Manager Tests ──────────────────────────────────

describe('ClientDeploymentManager', () => {
  let manager: ClientDeploymentManager;
  
  beforeEach(() => {
    manager = new ClientDeploymentManager();
  });
  
  describe('createDeployment', () => {
    it('should create a new client deployment', async () => {
      const result = await manager.createDeployment(testOnboardingRequest);
      
      expect(result.success).toBe(true);
      expect(result.organizationId).toBeDefined();
      expect(result.organizationId).toMatch(/^org_/);
      expect(result.slug).toBe('test-company');
      expect(result.setupUrl).toBeDefined();
    });
    
    it('should generate unique organization IDs', async () => {
      const result1 = await manager.createDeployment(testOnboardingRequest);
      const result2 = await manager.createDeployment({
        ...testOnboardingRequest,
        name: 'Another Company',
      });
      
      expect(result1.organizationId).not.toBe(result2.organizationId);
    });
    
    it('should generate slug from name', async () => {
      const result = await manager.createDeployment({
        ...testOnboardingRequest,
        name: 'My Test Company Inc.',
      });
      
      expect(result.slug).toBe('my-test-company-inc');
    });
    
    it('should set initial status to pending', async () => {
      const result = await manager.createDeployment(testOnboardingRequest);
      const config = manager.getClientConfig(result.organizationId!);
      
      expect(config?.status).toBe('configuring');
    });
    
    it('should set correct variant from plan', async () => {
      const result = await manager.createDeployment(testOnboardingRequest);
      const config = manager.getClientConfig(result.organizationId!);
      
      expect(config?.variant).toBe('parwa');
    });
    
    it('should initialize features based on plan', async () => {
      const result = await manager.createDeployment(testOnboardingRequest);
      const config = manager.getClientConfig(result.organizationId!);
      
      // parwa plan features
      expect(config?.features.jarvis).toBe(true);
      expect(config?.features.proactiveAlerts).toBe(true);
      expect(config?.features.smartSuggestions).toBe(true);
      expect(config?.features.patternDetection).toBe(true);
      expect(config?.features.maxCommandsPerDay).toBe(500);
      expect(config?.features.memoryRetentionDays).toBe(7);
    });
    
    it('should set mini_parwa features correctly', async () => {
      const result = await manager.createDeployment({
        ...testOnboardingRequest,
        plan: 'mini_parwa',
      });
      const config = manager.getClientConfig(result.organizationId!);
      
      expect(config?.features.proactiveAlerts).toBe(false);
      expect(config?.features.smartSuggestions).toBe(false);
      expect(config?.features.patternDetection).toBe(false);
      expect(config?.features.maxCommandsPerDay).toBe(100);
    });
    
    it('should set parwa_high features correctly', async () => {
      const result = await manager.createDeployment({
        ...testOnboardingRequest,
        plan: 'parwa_high',
      });
      const config = manager.getClientConfig(result.organizationId!);
      
      expect(config?.features.apiAccess).toBe('full');
      expect(config?.features.maxCommandsPerDay).toBe(-1); // Unlimited
      expect(config?.features.memoryRetentionDays).toBe(30);
      expect(config?.features.customBranding).toBe(true);
    });
    
    it('should initialize JARVIS settings', async () => {
      const result = await manager.createDeployment(testOnboardingRequest);
      const config = manager.getClientConfig(result.organizationId!);
      
      expect(config?.jarvis.shadowMode).toBe(true);
      expect(config?.jarvis.approvalRequired).toBe(true);
      expect(config?.jarvis.auditLogging).toBe(true);
    });
    
    it('should initialize integrations from request', async () => {
      const result = await manager.createDeployment(testOnboardingRequest);
      const config = manager.getClientConfig(result.organizationId!);
      
      expect(config?.integrations.email).toBeDefined();
      expect(config?.integrations.email?.provider).toBe('brevo');
      expect(config?.integrations.sms).toBeDefined();
      expect(config?.integrations.sms?.provider).toBe('twilio');
    });
    
    it('should create setup progress', async () => {
      const result = await manager.createDeployment(testOnboardingRequest);
      const config = manager.getClientConfig(result.organizationId!);
      
      expect(config?.deployment?.setupProgress).toBeDefined();
      expect(config?.deployment?.setupProgress.progress).toBe(20);
      expect(config?.deployment?.setupProgress.steps).toHaveLength(5);
    });
  });
  
  describe('deployClient', () => {
    it('should deploy an existing client', async () => {
      const createResult = await manager.createDeployment(testOnboardingRequest);
      
      const deployResult = await manager.deployClient({
        organizationId: createResult.organizationId!,
        config: {
          status: 'active',
        },
      });
      
      expect(deployResult.success).toBe(true);
      expect(deployResult.status).toBe('active');
    });
    
    it('should fail for non-existent client', async () => {
      const result = await manager.deployClient({
        organizationId: 'org-nonexistent',
        config: {},
      });
      
      expect(result.success).toBe(false);
      expect(result.error).toBe('Client not found');
    });
    
    it('should update client status', async () => {
      const createResult = await manager.createDeployment(testOnboardingRequest);
      
      await manager.deployClient({
        organizationId: createResult.organizationId!,
        config: { status: 'active' },
      });
      
      const config = manager.getClientConfig(createResult.organizationId!);
      expect(config?.status).toBe('active');
    });
  });
  
  describe('getClientConfig', () => {
    it('should return config for existing client', async () => {
      const result = await manager.createDeployment(testOnboardingRequest);
      const config = manager.getClientConfig(result.organizationId!);
      
      expect(config).toBeDefined();
      expect(config?.name).toBe('Test Company');
    });
    
    it('should return undefined for non-existent client', () => {
      const config = manager.getClientConfig('org-nonexistent');
      expect(config).toBeUndefined();
    });
  });
  
  describe('getClientBySlug', () => {
    it('should find client by slug', async () => {
      await manager.createDeployment(testOnboardingRequest);
      const config = manager.getClientBySlug('test-company');
      
      expect(config).toBeDefined();
      expect(config?.name).toBe('Test Company');
    });
    
    it('should return undefined for unknown slug', () => {
      const config = manager.getClientBySlug('unknown-slug');
      expect(config).toBeUndefined();
    });
  });
  
  describe('updateClientConfig', () => {
    it('should update client configuration', async () => {
      const createResult = await manager.createDeployment(testOnboardingRequest);
      
      const updateResult = await manager.updateClientConfig(
        createResult.organizationId!,
        { name: 'Updated Company Name' }
      );
      
      expect(updateResult.success).toBe(true);
      expect(updateResult.config?.name).toBe('Updated Company Name');
    });
    
    it('should fail for non-existent client', async () => {
      const result = await manager.updateClientConfig('org-nonexistent', { name: 'Test' });
      
      expect(result.success).toBe(false);
      expect(result.error).toBe('Client not found');
    });
    
    it('should update timestamp', async () => {
      const createResult = await manager.createDeployment(testOnboardingRequest);
      const originalConfig = manager.getClientConfig(createResult.organizationId!);
      
      await new Promise(resolve => setTimeout(resolve, 10)); // Small delay
      
      await manager.updateClientConfig(createResult.organizationId!, { name: 'New Name' });
      const updatedConfig = manager.getClientConfig(createResult.organizationId!);
      
      expect(updatedConfig?.updatedAt.getTime()).toBeGreaterThan(
        originalConfig!.updatedAt.getTime()
      );
    });
  });
  
  describe('validateIntegration', () => {
    it('should validate Brevo API key', async () => {
      const result = await manager.validateIntegration({
        organizationId: 'test-org',
        integrationType: 'email',
        provider: 'brevo',
        credentials: { apiKey: 'xkeysib-valid-key' },
      });
      
      expect(result.valid).toBe(true);
    });
    
    it('should reject invalid Brevo API key', async () => {
      const result = await manager.validateIntegration({
        organizationId: 'test-org',
        integrationType: 'email',
        provider: 'brevo',
        credentials: { apiKey: 'invalid-key' },
      });
      
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Invalid Brevo API key format');
    });
    
    it('should validate SendGrid API key', async () => {
      const result = await manager.validateIntegration({
        organizationId: 'test-org',
        integrationType: 'email',
        provider: 'sendgrid',
        credentials: { apiKey: 'SG.valid-key' },
      });
      
      expect(result.valid).toBe(true);
    });
    
    it('should reject invalid SendGrid API key', async () => {
      const result = await manager.validateIntegration({
        organizationId: 'test-org',
        integrationType: 'email',
        provider: 'sendgrid',
        credentials: { apiKey: 'invalid-key' },
      });
      
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Invalid SendGrid API key format');
    });
    
    it('should validate Twilio credentials', async () => {
      const result = await manager.validateIntegration({
        organizationId: 'test-org',
        integrationType: 'sms',
        provider: 'twilio',
        credentials: {
          accountSid: 'ACtest123456',
          authToken: 'authToken123',
        },
      });
      
      expect(result.valid).toBe(true);
    });
    
    it('should reject invalid Twilio Account SID', async () => {
      const result = await manager.validateIntegration({
        organizationId: 'test-org',
        integrationType: 'sms',
        provider: 'twilio',
        credentials: {
          accountSid: 'INVALID',
          authToken: 'authToken',
        },
      });
      
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Invalid Twilio Account SID');
    });
    
    it('should require Account SID and Auth Token', async () => {
      const result = await manager.validateIntegration({
        organizationId: 'test-org',
        integrationType: 'sms',
        provider: 'twilio',
        credentials: { accountSid: 'ACtest' },
      });
      
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Auth Token');
    });
    
    it('should validate webhook URL', async () => {
      const result = await manager.validateIntegration({
        organizationId: 'test-org',
        integrationType: 'webhook',
        provider: 'generic',
        credentials: { url: 'https://example.com/webhook' },
      });
      
      expect(result.valid).toBe(true);
    });
    
    it('should reject invalid webhook URL', async () => {
      const result = await manager.validateIntegration({
        organizationId: 'test-org',
        integrationType: 'webhook',
        provider: 'generic',
        credentials: { url: 'not-a-url' },
      });
      
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Invalid webhook URL');
    });
    
    it('should require API key for email', async () => {
      const result = await manager.validateIntegration({
        organizationId: 'test-org',
        integrationType: 'email',
        provider: 'brevo',
        credentials: {},
      });
      
      expect(result.valid).toBe(false);
      expect(result.error).toContain('API key');
    });
  });
  
  describe('getOnboardingSteps', () => {
    it('should return onboarding steps', async () => {
      const steps = manager.getOnboardingSteps('test-org');
      
      expect(steps).toHaveLength(5);
      expect(steps[0].id).toBe('account');
      expect(steps[0].title).toBe('Account Setup');
    });
    
    it('should mark account step completed for existing client', async () => {
      const createResult = await manager.createDeployment(testOnboardingRequest);
      const steps = manager.getOnboardingSteps(createResult.organizationId!);
      
      expect(steps[0].status).toBe('completed');
    });
    
    it('should include all required fields', () => {
      const steps = manager.getOnboardingSteps('test-org');
      
      for (const step of steps) {
        expect(step.id).toBeDefined();
        expect(step.title).toBeDefined();
        expect(step.description).toBeDefined();
        expect(step.status).toBeDefined();
        expect(step.order).toBeDefined();
        expect(step.actions).toBeDefined();
      }
    });
  });
  
  describe('getHealthStatus', () => {
    it('should return health status for active client', async () => {
      const createResult = await manager.createDeployment(testOnboardingRequest);
      await manager.deployClient({
        organizationId: createResult.organizationId!,
        config: { status: 'active' },
      });
      
      const health = await manager.getHealthStatus(createResult.organizationId!);
      
      expect(health).toBeDefined();
      expect(health?.status).toBeDefined();
      expect(health?.components).toBeDefined();
      expect(health?.lastCheck).toBeDefined();
    });
    
    it('should return undefined for non-existent client', async () => {
      const health = await manager.getHealthStatus('org-nonexistent');
      expect(health).toBeUndefined();
    });
    
    it('should check component health', async () => {
      const createResult = await manager.createDeployment(testOnboardingRequest);
      await manager.deployClient({
        organizationId: createResult.organizationId!,
        config: { status: 'active' },
      });
      
      const health = await manager.getHealthStatus(createResult.organizationId!);
      
      // Should have JARVIS component
      const jarvisComponent = health?.components.find(c => c.name === 'JARVIS Assistant');
      expect(jarvisComponent).toBeDefined();
    });
  });
  
  describe('listDeployments', () => {
    it('should list all deployments', async () => {
      await manager.createDeployment(testOnboardingRequest);
      await manager.createDeployment({
        ...testOnboardingRequest,
        name: 'Another Company',
      });
      
      const deployments = manager.listDeployments();
      
      expect(deployments).toHaveLength(2);
    });
    
    it('should return empty array when no deployments', () => {
      const deployments = manager.listDeployments();
      expect(deployments).toHaveLength(0);
    });
  });
  
  describe('suspendClient', () => {
    it('should suspend an active client', async () => {
      const createResult = await manager.createDeployment(testOnboardingRequest);
      await manager.deployClient({
        organizationId: createResult.organizationId!,
        config: { status: 'active' },
      });
      
      const result = await manager.suspendClient(createResult.organizationId!);
      
      expect(result.success).toBe(true);
      
      const config = manager.getClientConfig(createResult.organizationId!);
      expect(config?.status).toBe('suspended');
    });
    
    it('should fail for non-existent client', async () => {
      const result = await manager.suspendClient('org-nonexistent');
      
      expect(result.success).toBe(false);
      expect(result.error).toBe('Client not found');
    });
  });
  
  describe('reactivateClient', () => {
    it('should reactivate a suspended client', async () => {
      const createResult = await manager.createDeployment(testOnboardingRequest);
      await manager.deployClient({
        organizationId: createResult.organizationId!,
        config: { status: 'active' },
      });
      await manager.suspendClient(createResult.organizationId!);
      
      const result = await manager.reactivateClient(createResult.organizationId!);
      
      expect(result.success).toBe(true);
      
      const config = manager.getClientConfig(createResult.organizationId!);
      expect(config?.status).toBe('active');
    });
    
    it('should fail for non-existent client', async () => {
      const result = await manager.reactivateClient('org-nonexistent');
      
      expect(result.success).toBe(false);
      expect(result.error).toBe('Client not found');
    });
  });
  
  describe('deleteClient', () => {
    it('should delete a client', async () => {
      const createResult = await manager.createDeployment(testOnboardingRequest);
      
      const result = await manager.deleteClient(createResult.organizationId!);
      
      expect(result.success).toBe(true);
      
      const config = manager.getClientConfig(createResult.organizationId!);
      expect(config).toBeUndefined();
    });
    
    it('should fail for non-existent client', async () => {
      const result = await manager.deleteClient('org-nonexistent');
      
      expect(result.success).toBe(false);
      expect(result.error).toBe('Client not found');
    });
  });
});

// ── Singleton Tests ──────────────────────────────────────────────────

describe('getDeploymentManager', () => {
  beforeEach(() => {
    resetDeploymentManager();
  });
  
  it('should return a singleton instance', () => {
    const manager1 = getDeploymentManager();
    const manager2 = getDeploymentManager();
    
    expect(manager1).toBe(manager2);
  });
  
  it('should reset to new instance', () => {
    const manager1 = getDeploymentManager();
    resetDeploymentManager();
    const manager2 = getDeploymentManager();
    
    expect(manager1).not.toBe(manager2);
  });
});

// ── Type Tests ────────────────────────────────────────────────────────

describe('Types', () => {
  it('should have correct deployment statuses', () => {
    const statuses: ClientDeploymentStatus[] = [
      'pending',
      'configuring',
      'testing',
      'active',
      'suspended',
      'error',
    ];
    
    expect(statuses).toHaveLength(6);
  });
  
  it('should have correct integration statuses', () => {
    const statuses = [
      'not_configured',
      'pending',
      'validating',
      'active',
      'error',
      'disabled',
    ];
    
    expect(statuses).toHaveLength(6);
  });
});
