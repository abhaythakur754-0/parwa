/**
 * JARVIS Production Types - Week 16 (Phase 4)
 *
 * Types for production readiness, security audit, and deployment validation.
 */

// ── Production Readiness ─────────────────────────────────────────────

export interface ProductionReadinessCheck {
  /** Check ID */
  id: string;
  
  /** Check category */
  category: ProductionCheckCategory;
  
  /** Check name */
  name: string;
  
  /** Check description */
  description: string;
  
  /** Is check passed */
  passed: boolean;
  
  /** Severity if failed */
  severity: 'critical' | 'warning' | 'info';
  
  /** Details */
  details?: string;
  
  /** Remediation steps */
  remediation?: string[];
  
  /** Timestamp */
  timestamp: Date;
}

export type ProductionCheckCategory =
  | 'security'
  | 'performance'
  | 'integrations'
  | 'configuration'
  | 'monitoring'
  | 'database'
  | 'api'
  | 'compliance';

export interface ProductionReadinessReport {
  /** Report ID */
  id: string;
  
  /** Organization ID */
  organizationId: string;
  
  /** Overall readiness status */
  ready: boolean;
  
  /** Readiness score (0-100) */
  score: number;
  
  /** All checks */
  checks: ProductionReadinessCheck[];
  
  /** Summary by category */
  summary: Record<ProductionCheckCategory, {
    total: number;
    passed: number;
    failed: number;
  }>;
  
  /** Critical issues */
  criticalIssues: string[];
  
  /** Recommendations */
  recommendations: string[];
  
  /** Generated timestamp */
  generatedAt: Date;
}

// ── Security Audit ───────────────────────────────────────────────────

export interface SecurityAuditResult {
  /** Audit ID */
  id: string;
  
  /** Organization ID */
  organizationId: string;
  
  /** Overall security score (0-100) */
  securityScore: number;
  
  /** Security status */
  status: 'secure' | 'at_risk' | 'critical';
  
  /** Vulnerabilities found */
  vulnerabilities: SecurityVulnerability[];
  
  /** Configuration issues */
  configurationIssues: ConfigurationIssue[];
  
  /** Compliance status */
  compliance: ComplianceStatus;
  
  /** Audit timestamp */
  auditedAt: Date;
}

export interface SecurityVulnerability {
  /** Vulnerability ID */
  id: string;
  
  /** Severity */
  severity: 'low' | 'medium' | 'high' | 'critical';
  
  /** Type */
  type: VulnerabilityType;
  
  /** Title */
  title: string;
  
  /** Description */
  description: string;
  
  /** Affected component */
  component: string;
  
  /** CVE ID if applicable */
  cve?: string;
  
  /** Remediation */
  remediation: string;
  
  /** Is resolved */
  resolved: boolean;
}

export type VulnerabilityType =
  | 'injection'
  | 'authentication'
  | 'authorization'
  | 'data_exposure'
  | 'encryption'
  | 'configuration'
  | 'dependency';

export interface ConfigurationIssue {
  /** Issue ID */
  id: string;
  
  /** Severity */
  severity: 'low' | 'medium' | 'high';
  
  /** Setting name */
  setting: string;
  
  /** Current value */
  currentValue: string;
  
  /** Recommended value */
  recommendedValue: string;
  
  /** Description */
  description: string;
}

export interface ComplianceStatus {
  /** GDPR compliant */
  gdpr: boolean;
  
  /** SOC 2 compliant */
  soc2: boolean;
  
  /** HIPAA compliant (if applicable) */
  hipaa?: boolean;
  
  /** Data retention compliant */
  dataRetention: boolean;
  
  /** Audit logging enabled */
  auditLogging: boolean;
  
  /** Encryption at rest */
  encryptionAtRest: boolean;
  
  /** Encryption in transit */
  encryptionInTransit: boolean;
}

// ── Deployment Validation ────────────────────────────────────────────

export interface DeploymentValidation {
  /** Validation ID */
  id: string;
  
  /** Organization ID */
  organizationId: string;
  
  /** Environment */
  environment: 'development' | 'staging' | 'production';
  
  /** Validation status */
  status: 'valid' | 'invalid' | 'warning';
  
  /** All validations */
  validations: ValidationItem[];
  
  /** Required integrations */
  integrations: IntegrationValidation[];
  
  /** API endpoints */
  endpoints: EndpointValidation[];
  
  /** Database status */
  database: DatabaseValidation;
  
  /** Validation timestamp */
  validatedAt: Date;
}

export interface ValidationItem {
  /** Item name */
  name: string;
  
  /** Is valid */
  valid: boolean;
  
  /** Message */
  message: string;
  
  /** Critical */
  critical: boolean;
}

export interface IntegrationValidation {
  /** Integration type */
  type: 'email' | 'sms' | 'chat' | 'webhook' | 'helpdesk' | 'crm';
  
  /** Provider */
  provider: string;
  
  /** Is configured */
  configured: boolean;
  
  /** Is validated */
  validated: boolean;
  
  /** Last test result */
  lastTestResult?: 'success' | 'failed' | 'not_tested';
  
  /** Error message */
  error?: string;
}

export interface EndpointValidation {
  /** Endpoint path */
  path: string;
  
  /** HTTP method */
  method: string;
  
  /** Is accessible */
  accessible: boolean;
  
  /** Response time (ms) */
  responseTime?: number;
  
  /** Status code */
  statusCode?: number;
  
  /** Error */
  error?: string;
}

export interface DatabaseValidation {
  /** Is connected */
  connected: boolean;
  
  /** Migration status */
  migrations: 'up_to_date' | 'pending' | 'error';
  
  /** Connection pool status */
  connectionPool: {
    active: number;
    idle: number;
    max: number;
  };
  
  /** Error */
  error?: string;
}

// ── Release Checklist ────────────────────────────────────────────────

export interface ReleaseChecklist {
  /** Checklist ID */
  id: string;
  
  /** Organization ID */
  organizationId: string;
  
  /** Version */
  version: string;
  
  /** Items */
  items: ReleaseChecklistItem[];
  
  /** Progress percentage */
  progress: number;
  
  /** Is complete */
  complete: boolean;
  
  /** Created at */
  createdAt: Date;
  
  /** Updated at */
  updatedAt: Date;
}

export interface ReleaseChecklistItem {
  /** Item ID */
  id: string;
  
  /** Category */
  category: 'pre_deploy' | 'deploy' | 'post_deploy' | 'verification';
  
  /** Item title */
  title: string;
  
  /** Description */
  description: string;
  
  /** Is completed */
  completed: boolean;
  
  /** Completed by */
  completedBy?: string;
  
  /** Completed at */
  completedAt?: Date;
  
  /** Notes */
  notes?: string;
  
  /** Required */
  required: boolean;
}

// ── Deployment Status ─────────────────────────────────────────────────

export interface DeploymentStatus {
  /** Deployment ID */
  id: string;
  
  /** Organization ID */
  organizationId: string;
  
  /** Status */
  status: DeploymentStatusType;
  
  /** Current step */
  currentStep: string;
  
  /** Progress (0-100) */
  progress: number;
  
  /** Steps */
  steps: DeploymentStep[];
  
  /** Started at */
  startedAt: Date;
  
  /** Completed at */
  completedAt?: Date;
  
  /** Error */
  error?: string;
  
  /** Rollback available */
  rollbackAvailable: boolean;
}

export type DeploymentStatusType =
  | 'pending'
  | 'initializing'
  | 'validating'
  | 'deploying'
  | 'migrating'
  | 'testing'
  | 'completed'
  | 'failed'
  | 'rolled_back';

export interface DeploymentStep {
  /** Step ID */
  id: string;
  
  /** Step name */
  name: string;
  
  /** Step status */
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';
  
  /** Started at */
  startedAt?: Date;
  
  /** Completed at */
  completedAt?: Date;
  
  /** Error */
  error?: string;
  
  /** Logs */
  logs?: string[];
}

// ── Health Check ──────────────────────────────────────────────────────

export interface HealthCheckResult {
  /** Component name */
  component: string;
  
  /** Health status */
  status: 'healthy' | 'degraded' | 'unhealthy';
  
  /** Response time (ms) */
  responseTime: number;
  
  /** Last check */
  lastCheck: Date;
  
  /** Error */
  error?: string;
  
  /** Details */
  details?: Record<string, unknown>;
}

export interface SystemHealthReport {
  /** Report ID */
  id: string;
  
  /** Organization ID */
  organizationId: string;
  
  /** Overall status */
  status: 'healthy' | 'degraded' | 'unhealthy';
  
  /** Components */
  components: HealthCheckResult[];
  
  /** Uptime (seconds) */
  uptime: number;
  
  /** Version */
  version: string;
  
  /** Generated at */
  generatedAt: Date;
}

// ── Default Checklist Items ───────────────────────────────────────────

export const DEFAULT_RELEASE_CHECKLIST: Omit<ReleaseChecklistItem, 'id'>[] = [
  // Pre-deploy
  {
    category: 'pre_deploy',
    title: 'Code Review Completed',
    description: 'All code changes have been reviewed and approved',
    completed: false,
    required: true,
  },
  {
    category: 'pre_deploy',
    title: 'Tests Passing',
    description: 'All automated tests are passing',
    completed: false,
    required: true,
  },
  {
    category: 'pre_deploy',
    title: 'Security Audit Passed',
    description: 'Security audit has been completed with no critical issues',
    completed: false,
    required: true,
  },
  {
    category: 'pre_deploy',
    title: 'Performance Baseline Met',
    description: 'Performance tests meet baseline requirements',
    completed: false,
    required: false,
  },
  {
    category: 'pre_deploy',
    title: 'Documentation Updated',
    description: 'Documentation has been updated for new features',
    completed: false,
    required: false,
  },
  // Deploy
  {
    category: 'deploy',
    title: 'Database Migrations',
    description: 'All database migrations have been applied',
    completed: false,
    required: true,
  },
  {
    category: 'deploy',
    title: 'Environment Variables Set',
    description: 'All required environment variables are configured',
    completed: false,
    required: true,
  },
  {
    category: 'deploy',
    title: 'Integrations Configured',
    description: 'All integrations are configured and tested',
    completed: false,
    required: true,
  },
  {
    category: 'deploy',
    title: 'Services Deployed',
    description: 'All services have been deployed to production',
    completed: false,
    required: true,
  },
  // Post-deploy
  {
    category: 'post_deploy',
    title: 'Smoke Tests Passed',
    description: 'Smoke tests have passed in production',
    completed: false,
    required: true,
  },
  {
    category: 'post_deploy',
    title: 'Monitoring Active',
    description: 'Monitoring and alerting are active',
    completed: false,
    required: true,
  },
  {
    category: 'post_deploy',
    title: 'Logs Flowing',
    description: 'Logs are flowing to logging service',
    completed: false,
    required: true,
  },
  // Verification
  {
    category: 'verification',
    title: 'End-to-End Tests Passed',
    description: 'E2E tests have passed in production',
    completed: false,
    required: false,
  },
  {
    category: 'verification',
    title: 'Performance Verified',
    description: 'Production performance meets requirements',
    completed: false,
    required: false,
  },
  {
    category: 'verification',
    title: 'Stakeholder Sign-off',
    description: 'Stakeholders have signed off on the release',
    completed: false,
    required: true,
  },
];
