/**
 * JARVIS Client Deployment Types - Week 14 (Phase 4)
 *
 * Types for multi-tenant client deployment and configuration.
 */

// ── Client Configuration ────────────────────────────────────────────

export interface ClientConfig {
  /** Unique client/organization ID */
  organizationId: string;
  
  /** Client name */
  name: string;
  
  /** Client slug (for URLs) */
  slug: string;
  
  /** Deployment status */
  status: ClientDeploymentStatus;
  
  /** Plan/variant level */
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
  
  /** Feature flags */
  features: ClientFeatures;
  
  /** Integration settings */
  integrations: ClientIntegrations;
  
  /** JARVIS settings */
  jarvis: JarvisClientSettings;
  
  /** Created timestamp */
  createdAt: Date;
  
  /** Updated timestamp */
  updatedAt: Date;
  
  /** Deployment metadata */
  deployment?: DeploymentMetadata;
}

export type ClientDeploymentStatus =
  | 'pending'      // Initial setup
  | 'configuring'  // Integrations being configured
  | 'testing'      // Running tests
  | 'active'       // Live and running
  | 'suspended'    // Paused/suspended
  | 'error';       // Error state

// ── Client Features ──────────────────────────────────────────────────

export interface ClientFeatures {
  /** JARVIS AI assistant enabled */
  jarvis: boolean;
  
  /** Proactive alerts enabled */
  proactiveAlerts: boolean;
  
  /** Smart suggestions enabled */
  smartSuggestions: boolean;
  
  /** Pattern detection enabled */
  patternDetection: boolean;
  
  /** Analytics dashboard enabled */
  analytics: boolean;
  
  /** Automation rules enabled */
  automation: boolean;
  
  /** Custom integrations allowed */
  customIntegrations: boolean;
  
  /** API access level */
  apiAccess: 'none' | 'read' | 'write' | 'full';
  
  /** Max commands per day */
  maxCommandsPerDay: number;
  
  /** Memory retention days */
  memoryRetentionDays: number;
  
  /** Custom branding allowed */
  customBranding: boolean;
}

// ── Client Integrations ──────────────────────────────────────────────

export interface ClientIntegrations {
  /** Email provider configuration */
  email?: EmailIntegrationConfig;
  
  /** SMS provider configuration (Twilio only) */
  sms?: SMSIntegrationConfig;
  
  /** Chat provider configuration */
  chat?: ChatIntegrationConfig;
  
  /** Webhook configurations */
  webhooks?: WebhookIntegrationConfig[];
  
  /** Helpdesk integrations */
  helpdesk?: HelpdeskIntegrationConfig;
  
  /** CRM integrations */
  crm?: CRMIntegrationConfig;
}

export interface EmailIntegrationConfig {
  provider: 'brevo' | 'sendgrid' | 'mailgun' | 'ses' | 'postmark' | 'smtp';
  status: IntegrationStatus;
  credentials: Record<string, string>; // Encrypted
  settings: {
    defaultFrom?: string;
    defaultReplyTo?: string;
    trackingEnabled?: boolean;
  };
  lastSync?: Date;
  error?: string;
}

export interface SMSIntegrationConfig {
  provider: 'twilio'; // Fixed
  status: IntegrationStatus;
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
  lastSync?: Date;
  error?: string;
}

export interface ChatIntegrationConfig {
  provider: 'slack' | 'discord' | 'teams';
  status: IntegrationStatus;
  credentials: Record<string, string>;
  settings: {
    defaultChannel?: string;
    channels?: Record<string, string>;
  };
  lastSync?: Date;
  error?: string;
}

export interface WebhookIntegrationConfig {
  id: string;
  name: string;
  url: string;
  secret?: string;
  events: string[];
  status: IntegrationStatus;
  lastDelivery?: Date;
  error?: string;
}

export interface HelpdeskIntegrationConfig {
  provider: 'zendesk' | 'freshdesk' | 'helpscout' | 'intercom';
  status: IntegrationStatus;
  credentials: Record<string, string>;
  settings: Record<string, unknown>;
  lastSync?: Date;
  error?: string;
}

export interface CRMIntegrationConfig {
  provider: 'salesforce' | 'hubspot' | 'pipedrive';
  status: IntegrationStatus;
  credentials: Record<string, string>;
  settings: Record<string, unknown>;
  lastSync?: Date;
  error?: string;
}

export type IntegrationStatus =
  | 'not_configured'
  | 'pending'
  | 'validating'
  | 'active'
  | 'error'
  | 'disabled';

// ── JARVIS Client Settings ───────────────────────────────────────────

export interface JarvisClientSettings {
  /** Enable shadow mode */
  shadowMode: boolean;
  
  /** Approval required for actions */
  approvalRequired: boolean;
  
  /** Approval threshold (risk level) */
  approvalThreshold: 'low' | 'medium' | 'high' | 'critical';
  
  /** Auto-approve safe actions */
  autoApprove: boolean;
  
  /** Audit logging enabled */
  auditLogging: boolean;
  
  /** Rate limiting */
  rateLimit: {
    requestsPerMinute: number;
    commandsPerHour: number;
  };
  
  /** Alert channels */
  alertChannels: AlertChannelConfig[];
  
  /** Custom prompts */
  customPrompts?: {
    systemPrompt?: string;
    greetingMessage?: string;
    escalationMessage?: string;
  };
  
  /** Working hours (for proactive alerts) */
  workingHours?: {
    enabled: boolean;
    timezone: string;
    schedule: {
      day: 'monday' | 'tuesday' | 'wednesday' | 'thursday' | 'friday' | 'saturday' | 'sunday';
      start: string; // HH:MM
      end: string;   // HH:MM
    }[];
  };
}

export interface AlertChannelConfig {
  type: 'email' | 'sms' | 'slack' | 'webhook';
  destination: string;
  events: string[];
  enabled: boolean;
}

// ── Deployment Metadata ──────────────────────────────────────────────

export interface DeploymentMetadata {
  /** Deployment version */
  version: string;
  
  /** Deployment environment */
  environment: 'development' | 'staging' | 'production';
  
  /** Deployed by */
  deployedBy: string;
  
  /** Deployed at */
  deployedAt: Date;
  
  /** Setup progress */
  setupProgress: SetupProgress;
  
  /** Last health check */
  lastHealthCheck?: Date;
  
  /** Health status */
  healthStatus?: HealthStatus;
  
  /** Error count */
  errorCount: number;
  
  /** Last error */
  lastError?: string;
}

export interface SetupProgress {
  /** Setup steps */
  steps: SetupStep[];
  
  /** Current step */
  currentStep: string;
  
  /** Overall progress (0-100) */
  progress: number;
  
  /** Started at */
  startedAt: Date;
  
  /** Completed at */
  completedAt?: Date;
}

export interface SetupStep {
  id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';
  startedAt?: Date;
  completedAt?: Date;
  error?: string;
}

export interface HealthStatus {
  /** Overall health */
  status: 'healthy' | 'degraded' | 'unhealthy';
  
  /** Component health */
  components: {
    name: string;
    status: 'healthy' | 'degraded' | 'unhealthy';
    latency?: number;
    errorRate?: number;
    lastCheck: Date;
    error?: string;
  }[];
  
  /** Last check timestamp */
  lastCheck: Date;
}

// ── Onboarding Types ─────────────────────────────────────────────────

export interface OnboardingRequest {
  /** Organization name */
  name: string;
  
  /** Admin user info */
  admin: {
    email: string;
    name: string;
    password?: string;
  };
  
  /** Selected plan */
  plan: 'mini_parwa' | 'parwa' | 'parwa_high';
  
  /** Initial integrations */
  integrations?: {
    email?: {
      provider: string;
      credentials: Record<string, string>;
    };
    sms?: {
      credentials: Record<string, string>;
    };
  };
  
  /** Timezone */
  timezone?: string;
}

export interface OnboardingResponse {
  success: boolean;
  organizationId?: string;
  slug?: string;
  setupUrl?: string;
  error?: string;
}

export interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'active' | 'completed' | 'error';
  order: number;
  actions: OnboardingAction[];
}

export interface OnboardingAction {
  id: string;
  type: 'input' | 'select' | 'button' | 'link' | 'oauth';
  label: string;
  required: boolean;
  placeholder?: string;
  options?: { value: string; label: string }[];
  url?: string;
}

// ── Deployment Operations ────────────────────────────────────────────

export interface DeployClientRequest {
  organizationId: string;
  config: Partial<ClientConfig>;
  environment?: 'development' | 'staging' | 'production';
}

export interface DeployClientResponse {
  success: boolean;
  deploymentId?: string;
  status?: ClientDeploymentStatus;
  error?: string;
}

export interface UpdateClientConfigRequest {
  organizationId: string;
  updates: Partial<ClientConfig>;
}

export interface ValidateIntegrationRequest {
  organizationId: string;
  integrationType: 'email' | 'sms' | 'chat' | 'webhook' | 'helpdesk' | 'crm';
  provider: string;
  credentials: Record<string, string>;
}

export interface ValidateIntegrationResponse {
  valid: boolean;
  error?: string;
  details?: Record<string, unknown>;
}

// ── Metrics & Monitoring ─────────────────────────────────────────────

export interface ClientMetrics {
  organizationId: string;
  period: {
    start: Date;
    end: Date;
  };
  
  /** Command stats */
  commands: {
    total: number;
    successful: number;
    failed: number;
    avgResponseTime: number;
    byType: Record<string, number>;
  };
  
  /** Alert stats */
  alerts: {
    total: number;
    acknowledged: number;
    escalated: number;
    byType: Record<string, number>;
  };
  
  /** Suggestion stats */
  suggestions: {
    total: number;
    accepted: number;
    rejected: number;
    acceptanceRate: number;
  };
  
  /** Pattern detection stats */
  patterns: {
    detected: number;
    confirmed: number;
    falsePositives: number;
    byType: Record<string, number>;
  };
  
  /** Integration health */
  integrations: {
    name: string;
    status: IntegrationStatus;
    uptime: number;
    errorRate: number;
    lastError?: string;
  }[];
}

// ── Default Configurations ───────────────────────────────────────────

export const DEFAULT_CLIENT_FEATURES: Record<string, ClientFeatures> = {
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
    maxCommandsPerDay: -1, // Unlimited
    memoryRetentionDays: 30,
    customBranding: true,
  },
};

export const DEFAULT_JARVIS_SETTINGS: JarvisClientSettings = {
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
