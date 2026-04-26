/**
 * JARVIS Client Deployment Manager - Week 14 (Phase 4)
 *
 * Manages client deployment, onboarding, and configuration.
 */

import type {
  ClientConfig,
  ClientDeploymentStatus,
  ClientFeatures,
  JarvisClientSettings,
  OnboardingRequest,
  OnboardingResponse,
  OnboardingStep,
  DeployClientRequest,
  DeployClientResponse,
  ValidateIntegrationRequest,
  ValidateIntegrationResponse,
  SetupProgress,
  SetupStep,
  HealthStatus,
  IntegrationStatus,
  DEFAULT_CLIENT_FEATURES,
  DEFAULT_JARVIS_SETTINGS,
  ClientIntegrations,
} from './types';

// ── Client Deployment Manager ────────────────────────────────────────

export class ClientDeploymentManager {
  private deployments: Map<string, ClientConfig> = new Map();
  private healthChecks: Map<string, NodeJS.Timeout> = new Map();
  
  /**
   * Create a new client deployment
   */
  async createDeployment(request: OnboardingRequest): Promise<OnboardingResponse> {
    try {
      // Generate organization ID
      const organizationId = this.generateOrganizationId();
      
      // Generate slug from name
      const slug = this.generateSlug(request.name);
      
      // Get default features for plan
      const features = this.getDefaultFeatures(request.plan);
      
      // Get default JARVIS settings
      const jarvisSettings = this.getDefaultJarvisSettings();
      
      // Create initial integrations
      const integrations = await this.initializeIntegrations(request.integrations);
      
      // Create client config
      const config: ClientConfig = {
        organizationId,
        name: request.name,
        slug,
        status: 'pending',
        variant: request.plan,
        features,
        integrations,
        jarvis: jarvisSettings,
        createdAt: new Date(),
        updatedAt: new Date(),
        deployment: {
          version: '1.0.0',
          environment: 'production',
          deployedBy: request.admin.email,
          deployedAt: new Date(),
          setupProgress: this.createInitialSetupProgress(),
          errorCount: 0,
        },
      };
      
      // Store deployment
      this.deployments.set(organizationId, config);
      
      // Start setup process
      await this.startSetupProcess(organizationId);
      
      return {
        success: true,
        organizationId,
        slug,
        setupUrl: `/onboarding/${slug}`,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
  
  /**
   * Deploy a client with configuration
   */
  async deployClient(request: DeployClientRequest): Promise<DeployClientResponse> {
    try {
      const existing = this.deployments.get(request.organizationId);
      
      if (!existing) {
        return {
          success: false,
          error: 'Client not found',
        };
      }
      
      // Update config
      const updated: ClientConfig = {
        ...existing,
        ...request.config,
        updatedAt: new Date(),
        status: 'configuring',
      };
      
      this.deployments.set(request.organizationId, updated);
      
      // Validate configuration
      const validation = await this.validateConfiguration(updated);
      
      if (!validation.valid) {
        return {
          success: false,
          error: validation.error,
        };
      }
      
      // Deploy to environment
      await this.deployToEnvironment(updated, request.environment || 'production');
      
      // Update status
      updated.status = 'active';
      updated.updatedAt = new Date();
      this.deployments.set(request.organizationId, updated);
      
      // Start health monitoring
      this.startHealthMonitoring(request.organizationId);
      
      return {
        success: true,
        deploymentId: request.organizationId,
        status: 'active',
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
  
  /**
   * Get client configuration
   */
  getClientConfig(organizationId: string): ClientConfig | undefined {
    return this.deployments.get(organizationId);
  }
  
  /**
   * Get client by slug
   */
  getClientBySlug(slug: string): ClientConfig | undefined {
    for (const config of this.deployments.values()) {
      if (config.slug === slug) {
        return config;
      }
    }
    return undefined;
  }
  
  /**
   * Update client configuration
   */
  async updateClientConfig(
    organizationId: string,
    updates: Partial<ClientConfig>
  ): Promise<{ success: boolean; config?: ClientConfig; error?: string }> {
    const existing = this.deployments.get(organizationId);
    
    if (!existing) {
      return { success: false, error: 'Client not found' };
    }
    
    const updated: ClientConfig = {
      ...existing,
      ...updates,
      updatedAt: new Date(),
    };
    
    this.deployments.set(organizationId, updated);
    
    return { success: true, config: updated };
  }
  
  /**
   * Validate integration credentials
   */
  async validateIntegration(
    request: ValidateIntegrationRequest
  ): Promise<ValidateIntegrationResponse> {
    try {
      switch (request.integrationType) {
        case 'email':
          return await this.validateEmailIntegration(request.provider, request.credentials);
        
        case 'sms':
          return await this.validateSMSIntegration(request.credentials);
        
        case 'chat':
          return await this.validateChatIntegration(request.provider, request.credentials);
        
        case 'webhook':
          return await this.validateWebhookIntegration(request.credentials);
        
        default:
          return { valid: false, error: 'Unsupported integration type' };
      }
    } catch (error) {
      return {
        valid: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
  
  /**
   * Get onboarding steps for a client
   */
  getOnboardingSteps(organizationId: string): OnboardingStep[] {
    const config = this.deployments.get(organizationId);
    
    const steps: OnboardingStep[] = [
      {
        id: 'account',
        title: 'Account Setup',
        description: 'Configure your admin account and organization details',
        status: config ? 'completed' : 'active',
        order: 1,
        actions: [
          { id: 'name', type: 'input', label: 'Organization Name', required: true },
          { id: 'email', type: 'input', label: 'Admin Email', required: true },
          { id: 'plan', type: 'select', label: 'Select Plan', required: true, options: [
            { value: 'mini_parwa', label: 'Mini PARWA' },
            { value: 'parwa', label: 'PARWA' },
            { value: 'parwa_high', label: 'PARWA High' },
          ]},
        ],
      },
      {
        id: 'email_integration',
        title: 'Email Integration',
        description: 'Connect your email provider for ticket notifications',
        status: config?.integrations.email ? 'completed' : 'pending',
        order: 2,
        actions: [
          { id: 'provider', type: 'select', label: 'Email Provider', required: true, options: [
            { value: 'brevo', label: 'Brevo (Sendinblue)' },
            { value: 'sendgrid', label: 'SendGrid' },
            { value: 'mailgun', label: 'Mailgun' },
            { value: 'ses', label: 'AWS SES' },
          ]},
          { id: 'api_key', type: 'input', label: 'API Key', required: true, placeholder: 'Your API key' },
        ],
      },
      {
        id: 'sms_integration',
        title: 'SMS Integration',
        description: 'Connect Twilio for SMS notifications',
        status: config?.integrations.sms ? 'completed' : 'pending',
        order: 3,
        actions: [
          { id: 'account_sid', type: 'input', label: 'Twilio Account SID', required: true },
          { id: 'auth_token', type: 'input', label: 'Auth Token', required: true },
          { id: 'from_number', type: 'input', label: 'From Number', required: false, placeholder: '+1234567890' },
        ],
      },
      {
        id: 'jarvis_config',
        title: 'JARVIS Configuration',
        description: 'Configure JARVIS assistant settings',
        status: 'pending',
        order: 4,
        actions: [
          { id: 'shadow_mode', type: 'select', label: 'Shadow Mode', required: true, options: [
            { value: 'true', label: 'Enabled (Safe)' },
            { value: 'false', label: 'Disabled' },
          ]},
          { id: 'approval', type: 'select', label: 'Approval Required', required: true, options: [
            { value: 'low', label: 'Low Risk Only' },
            { value: 'medium', label: 'Medium and Above' },
            { value: 'high', label: 'High Risk Only' },
            { value: 'critical', label: 'Critical Only' },
          ]},
        ],
      },
      {
        id: 'verify',
        title: 'Verification',
        description: 'Verify all integrations are working correctly',
        status: 'pending',
        order: 5,
        actions: [
          { id: 'test_email', type: 'button', label: 'Test Email', required: false },
          { id: 'test_sms', type: 'button', label: 'Test SMS', required: false },
          { id: 'verify', type: 'button', label: 'Complete Setup', required: true },
        ],
      },
    ];
    
    return steps;
  }
  
  /**
   * Get client health status
   */
  async getHealthStatus(organizationId: string): Promise<HealthStatus | undefined> {
    const config = this.deployments.get(organizationId);
    
    if (!config) {
      return undefined;
    }
    
    // Check all components
    const components = await this.checkComponents(config);
    
    // Determine overall status
    const status = this.determineOverallHealth(components);
    
    return {
      status,
      components,
      lastCheck: new Date(),
    };
  }
  
  /**
   * List all deployments
   */
  listDeployments(): ClientConfig[] {
    return Array.from(this.deployments.values());
  }
  
  /**
   * Suspend a client
   */
  async suspendClient(organizationId: string): Promise<{ success: boolean; error?: string }> {
    const config = this.deployments.get(organizationId);
    
    if (!config) {
      return { success: false, error: 'Client not found' };
    }
    
    config.status = 'suspended';
    config.updatedAt = new Date();
    
    this.deployments.set(organizationId, config);
    
    // Stop health monitoring
    this.stopHealthMonitoring(organizationId);
    
    return { success: true };
  }
  
  /**
   * Reactivate a client
   */
  async reactivateClient(organizationId: string): Promise<{ success: boolean; error?: string }> {
    const config = this.deployments.get(organizationId);
    
    if (!config) {
      return { success: false, error: 'Client not found' };
    }
    
    config.status = 'active';
    config.updatedAt = new Date();
    
    this.deployments.set(organizationId, config);
    
    // Restart health monitoring
    this.startHealthMonitoring(organizationId);
    
    return { success: true };
  }
  
  /**
   * Delete a client deployment
   */
  async deleteClient(organizationId: string): Promise<{ success: boolean; error?: string }> {
    const config = this.deployments.get(organizationId);
    
    if (!config) {
      return { success: false, error: 'Client not found' };
    }
    
    // Stop health monitoring
    this.stopHealthMonitoring(organizationId);
    
    // Remove deployment
    this.deployments.delete(organizationId);
    
    return { success: true };
  }
  
  // ── Private Methods ────────────────────────────────────────────────
  
  private generateOrganizationId(): string {
    return `org_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
  
  private generateSlug(name: string): string {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
      .substring(0, 50);
  }
  
  private getDefaultFeatures(plan: string): ClientFeatures {
    const defaults: Record<string, ClientFeatures> = {
      mini_parwa: {
        jarvis: true,
        proactiveAlerts: false,
        smartSuggestions: false,
        patternDetection: false,
        analytics: true,
        automation: false,
        customIntegrations: false,
        apiAccess: 'none',
        maxCommandsPerDay: 100,
        memoryRetentionDays: 1,
        customBranding: false,
      },
      parwa: {
        jarvis: true,
        proactiveAlerts: true,
        smartSuggestions: true,
        patternDetection: true,
        analytics: true,
        automation: true,
        customIntegrations: true,
        apiAccess: 'read',
        maxCommandsPerDay: 500,
        memoryRetentionDays: 7,
        customBranding: false,
      },
      parwa_high: {
        jarvis: true,
        proactiveAlerts: true,
        smartSuggestions: true,
        patternDetection: true,
        analytics: true,
        automation: true,
        customIntegrations: true,
        apiAccess: 'full',
        maxCommandsPerDay: -1,
        memoryRetentionDays: 30,
        customBranding: true,
      },
    };
    
    return defaults[plan] || defaults.mini_parwa;
  }
  
  private getDefaultJarvisSettings(): JarvisClientSettings {
    return {
      shadowMode: true,
      approvalRequired: true,
      approvalThreshold: 'medium',
      autoApprove: false,
      auditLogging: true,
      rateLimit: {
        requestsPerMinute: 60,
        commandsPerHour: 100,
      },
      alertChannels: [],
    };
  }
  
  private createInitialSetupProgress(): SetupProgress {
    return {
      steps: [
        { id: 'create_organization', name: 'Create Organization', status: 'completed' },
        { id: 'configure_integrations', name: 'Configure Integrations', status: 'pending' },
        { id: 'setup_jarvis', name: 'Setup JARVIS', status: 'pending' },
        { id: 'validate', name: 'Validate Configuration', status: 'pending' },
        { id: 'deploy', name: 'Deploy', status: 'pending' },
      ],
      currentStep: 'configure_integrations',
      progress: 20,
      startedAt: new Date(),
    };
  }
  
  private async initializeIntegrations(
    integrations?: OnboardingRequest['integrations']
  ): Promise<ClientIntegrations> {
    const result: ClientIntegrations = {};
    
    if (integrations?.email) {
      result.email = {
        provider: integrations.email.provider as 'brevo' | 'sendgrid',
        status: 'pending',
        credentials: integrations.email.credentials,
        settings: {},
      };
    }
    
    if (integrations?.sms) {
      result.sms = {
        provider: 'twilio',
        status: 'pending',
        credentials: {
          accountSid: integrations.sms.credentials.accountSid,
          authToken: integrations.sms.credentials.authToken,
          apiKey: integrations.sms.credentials.apiKey,
          apiSecret: integrations.sms.credentials.apiSecret,
        },
        settings: {
          fromNumber: integrations.sms.credentials.fromNumber,
        },
      };
    }
    
    return result;
  }
  
  private async startSetupProcess(organizationId: string): Promise<void> {
    const config = this.deployments.get(organizationId);
    
    if (!config) return;
    
    config.status = 'configuring';
    this.deployments.set(organizationId, config);
  }
  
  private async validateConfiguration(config: ClientConfig): Promise<{ valid: boolean; error?: string }> {
    // Validate features match plan
    if (!config.features.jarvis) {
      return { valid: false, error: 'JARVIS must be enabled' };
    }
    
    // Validate integrations
    if (config.integrations.email && config.integrations.email.status !== 'active') {
      // Email not validated yet
    }
    
    return { valid: true };
  }
  
  private async deployToEnvironment(config: ClientConfig, environment: string): Promise<void> {
    // Simulate deployment steps
    await new Promise(resolve => setTimeout(resolve, 100));
    
    if (config.deployment) {
      config.deployment.environment = environment as 'development' | 'staging' | 'production';
      config.deployment.deployedAt = new Date();
    }
  }
  
  private async validateEmailIntegration(
    provider: string,
    credentials: Record<string, string>
  ): Promise<ValidateIntegrationResponse> {
    const apiKey = credentials.apiKey || credentials.api_key;
    
    if (!apiKey) {
      return { valid: false, error: 'API key is required' };
    }
    
    // Validate API key format
    if (provider === 'brevo' && !apiKey.startsWith('xkeysib-')) {
      return { valid: false, error: 'Invalid Brevo API key format' };
    }
    
    if (provider === 'sendgrid' && !apiKey.startsWith('SG.')) {
      return { valid: false, error: 'Invalid SendGrid API key format' };
    }
    
    return { valid: true };
  }
  
  private async validateSMSIntegration(
    credentials: Record<string, string>
  ): Promise<ValidateIntegrationResponse> {
    const accountSid = credentials.accountSid || credentials.account_sid;
    const authToken = credentials.authToken || credentials.auth_token;
    
    if (!accountSid || !authToken) {
      return { valid: false, error: 'Account SID and Auth Token are required' };
    }
    
    if (!accountSid.startsWith('AC')) {
      return { valid: false, error: 'Invalid Twilio Account SID format' };
    }
    
    return { valid: true };
  }
  
  private async validateChatIntegration(
    provider: string,
    credentials: Record<string, string>
  ): Promise<ValidateIntegrationResponse> {
    if (!credentials.botToken && !credentials.accessToken) {
      return { valid: false, error: 'Bot token or access token is required' };
    }
    
    return { valid: true };
  }
  
  private async validateWebhookIntegration(
    credentials: Record<string, string>
  ): Promise<ValidateIntegrationResponse> {
    const url = credentials.url || credentials.webhookUrl;
    
    if (!url) {
      return { valid: false, error: 'Webhook URL is required' };
    }
    
    try {
      new URL(url);
    } catch {
      return { valid: false, error: 'Invalid webhook URL' };
    }
    
    return { valid: true };
  }
  
  private async checkComponents(config: ClientConfig): Promise<HealthStatus['components']> {
    const components: HealthStatus['components'] = [];
    
    // Check email integration
    if (config.integrations.email) {
      components.push({
        name: 'Email Integration',
        status: config.integrations.email.status === 'active' ? 'healthy' : 'unhealthy',
        lastCheck: new Date(),
      });
    }
    
    // Check SMS integration
    if (config.integrations.sms) {
      components.push({
        name: 'SMS Integration',
        status: config.integrations.sms.status === 'active' ? 'healthy' : 'unhealthy',
        lastCheck: new Date(),
      });
    }
    
    // Check JARVIS
    components.push({
      name: 'JARVIS Assistant',
      status: 'healthy',
      lastCheck: new Date(),
    });
    
    return components;
  }
  
  private determineOverallHealth(components: HealthStatus['components']): 'healthy' | 'degraded' | 'unhealthy' {
    if (components.length === 0) {
      return 'healthy';
    }
    
    const unhealthy = components.filter(c => c.status === 'unhealthy').length;
    const degraded = components.filter(c => c.status === 'degraded').length;
    
    if (unhealthy > 0) {
      return 'unhealthy';
    }
    
    if (degraded > 0) {
      return 'degraded';
    }
    
    return 'healthy';
  }
  
  private startHealthMonitoring(organizationId: string): void {
    // Stop existing monitoring
    this.stopHealthMonitoring(organizationId);
    
    // Start new monitoring interval (every 5 minutes)
    const interval = setInterval(async () => {
      const config = this.deployments.get(organizationId);
      
      if (config && config.status === 'active') {
        const health = await this.getHealthStatus(organizationId);
        
        if (health && health.status === 'unhealthy') {
          config.deployment!.errorCount++;
          config.deployment!.lastError = 'Health check failed';
        }
      }
    }, 5 * 60 * 1000);
    
    this.healthChecks.set(organizationId, interval);
  }
  
  private stopHealthMonitoring(organizationId: string): void {
    const interval = this.healthChecks.get(organizationId);
    
    if (interval) {
      clearInterval(interval);
      this.healthChecks.delete(organizationId);
    }
  }
}

// ── Singleton Instance ───────────────────────────────────────────────

let deploymentManagerInstance: ClientDeploymentManager | null = null;

export function getDeploymentManager(): ClientDeploymentManager {
  if (!deploymentManagerInstance) {
    deploymentManagerInstance = new ClientDeploymentManager();
  }
  return deploymentManagerInstance;
}

export function resetDeploymentManager(): void {
  deploymentManagerInstance = null;
}
