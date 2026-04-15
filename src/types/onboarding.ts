/**
 * PARWA Onboarding Types
 * 
 * Types for the onboarding flow including user details,
 * onboarding state, and related entities.
 */

// ── Industry Types ─────────────────────────────────────────────────────

export type Industry = 
  | 'saas'
  | 'ecommerce'
  | 'logistics'
  | 'finance'
  | 'education'
  | 'real_estate'
  | 'manufacturing'
  | 'consulting'
  | 'agency'
  | 'nonprofit'
  | 'hospitality'
  | 'retail'
  | 'other';

export type CompanySize =
  | '1_10'
  | '11_50'
  | '51_200'
  | '201_500'
  | '501_1000'
  | '1000_plus';

// ── User Details ───────────────────────────────────────────────────────

export interface UserDetails {
  id: string;
  user_id: string;
  company_id: string;
  full_name: string;
  company_name: string;
  work_email: string | null;
  work_email_verified: boolean;
  industry: Industry;
  company_size: CompanySize | null;
  website: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface UserDetailsRequest {
  full_name: string;
  company_name: string;
  work_email?: string;
  industry: Industry;
  company_size?: CompanySize;
  website?: string;
}

// ── Onboarding State ───────────────────────────────────────────────────

export type OnboardingStatus = 
  | 'not_started'
  | 'in_progress'
  | 'completed'
  | 'paused';

export interface OnboardingState {
  id: string;
  user_id: string;
  company_id: string;
  current_step: number;
  completed_steps: number[];
  status: OnboardingStatus;
  details_completed: boolean;
  wizard_started: boolean;
  legal_accepted: boolean;
  first_victory_completed: boolean;
  ai_name: string;
  ai_tone: AITone;
  ai_response_style: AIResponseStyle;
  ai_greeting: string | null;
  created_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
}

// ── AI Configuration ───────────────────────────────────────────────────

export type AITone = 'professional' | 'friendly' | 'casual';
export type AIResponseStyle = 'concise' | 'detailed';

export interface AIConfig {
  ai_name: string;
  ai_tone: AITone;
  ai_response_style: AIResponseStyle;
  ai_greeting?: string;
}

// ── Integration Types ──────────────────────────────────────────────────

// Synced with backend INTEGRATION_TYPES (integration_service.py)
export type IntegrationType =
  | 'zendesk'
  | 'shopify'
  | 'slack'
  | 'gmail'
  | 'freshdesk'
  | 'intercom'
  | 'custom';

// Synced with backend STATUS_* constants
export type IntegrationStatus = 'pending' | 'active' | 'error' | 'disconnected';

export interface Integration {
  id: string;
  type: IntegrationType;
  name: string;
  status: IntegrationStatus;
  config: Record<string, unknown>;
  last_test_at: string | null;
  last_test_result: string | null;
  created_at: string;
  updated_at: string;
}

// ── Knowledge Base Types ───────────────────────────────────────────────

export type DocumentStatus = 
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed';

export interface KnowledgeDocument {
  id: string;
  filename: string;
  file_size: number;
  mime_type: string;
  status: DocumentStatus;
  chunk_count: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

// ── Consent Types ──────────────────────────────────────────────────────

export type ConsentType = 
  | 'terms'
  | 'privacy'
  | 'ai_data';

export interface ConsentRecord {
  id: string;
  consent_type: ConsentType;
  accepted_at: string;
  ip_address: string;
  user_agent: string | null;
}

// ── API Response Types ─────────────────────────────────────────────────

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface ApiErrorResponse {
  detail: string;
  status_code: number;
}

// ── Form State Types ───────────────────────────────────────────────────

export interface FormState {
  isSubmitting: boolean;
  isValid: boolean;
  errors: Record<string, string>;
}

// ── Onboarding Step Types ──────────────────────────────────────────────

export interface OnboardingStep {
  id: number;
  title: string;
  description: string;
  isCompleted: boolean;
  isActive: boolean;
  isOptional: boolean;
}

export const ONBOARDING_STEPS: Omit<OnboardingStep, 'isCompleted' | 'isActive'>[] = [
  {
    id: 1,
    title: 'Welcome',
    description: 'Get started with PARWA',
    isOptional: false,
  },
  {
    id: 2,
    title: 'Legal',
    description: 'Accept terms and privacy policy',
    isOptional: false,
  },
  {
    id: 3,
    title: 'Integrations',
    description: 'Connect your support channels',
    isOptional: false,
  },
  {
    id: 4,
    title: 'Knowledge Base',
    description: 'Upload your documentation',
    isOptional: true,
  },
  {
    id: 5,
    title: 'AI Setup',
    description: 'Configure your AI assistant',
    isOptional: false,
  },
];
