/**
 * PARWA Demo Variant Types
 *
 * TypeScript type definitions for the $1 Demo Pack variant system.
 * Supports shadow mode variant demos, knowledge base, billing, and usage tracking.
 */

// ── Variant Demo Types ──────────────────────────────────────────

export type VariantTier = 'starter' | 'growth' | 'high';

export type DemoSessionStatus = 'active' | 'expired' | 'consumed';

export type ShadowModeStatus = 'disabled' | 'shadow' | 'supervised' | 'promoted';

export interface DemoVariant {
  id: string;
  name: string;
  tier: VariantTier;
  description: string;
  price_per_month: number;
  tickets_per_month: number;
  features: string[];
  limitations: string[];
  best_for: string;
  core_capability: string;
  smart_decisions: string;
  key_advantage: string;
  tagline: string;
  integrations: string[];
}

export interface DemoSession {
  id: string;
  user_id?: string;
  variant_id: string;
  variant_tier: VariantTier;
  status: DemoSessionStatus;
  created_at: string;
  expires_at: string;
  messages_used: number;
  messages_limit: number;
  call_seconds_used: number;
  call_seconds_limit: number;
  shadow_mode: ShadowModeStatus;
  knowledge_base_ids: string[];
  bill_summary?: DemoBillSummary;
}

export interface DemoVariantSelection {
  variant: DemoVariant;
  industry: string;
  entry_source: string;
}

// ── Knowledge Base Types ────────────────────────────────────────

export interface DemoKnowledgeBase {
  id: string;
  name: string;
  description: string;
  industry: string;
  document_count: number;
  is_prebuilt: boolean;
  created_at: string;
}

export interface DemoKnowledgeBaseUpload {
  file_name: string;
  file_size: number;
  content_type: string;
  industry?: string;
}

export interface DemoKnowledgeBaseUploadResponse {
  id: string;
  name: string;
  status: 'uploading' | 'processing' | 'ready' | 'failed';
  chunks_count: number;
  message: string;
}

// ── Usage Tracking Types ────────────────────────────────────────

export interface DemoUsage {
  session_id: string;
  user_messages_sent: number;
  user_messages_limit: number;
  jarvis_messages_sent: number;
  call_seconds_used: number;
  call_seconds_limit: number;
  is_call_available: boolean;
  is_messages_remaining: boolean;
  percentage_used: number;
}

export interface DemoUsageEvent {
  type: 'user_message' | 'jarvis_message' | 'call_second' | 'call_initiated';
  timestamp: string;
  metadata?: Record<string, unknown>;
}

// ── Billing Types ───────────────────────────────────────────────

export interface DemoBillItem {
  name: string;
  type: 'plan' | 'variant' | 'addon' | 'call' | 'overage';
  unit_price: number;
  quantity: number;
  total: number;
  description?: string;
}

export interface DemoBillSummary {
  items: DemoBillItem[];
  subtotal: number;
  tax: number;
  total: number;
  currency: string;
  billing_cycle: 'monthly' | 'annual';
  savings_vs_human: number;
  savings_percentage: number;
  roi_months: number;
  monthly_estimate: number;
  annual_estimate: number;
}

export interface DemoBillingEstimate {
  industry: string;
  ticket_volume: number;
  selected_variants: DemoVariant[];
  plan: VariantTier;
  bill_summary: DemoBillSummary;
}

// ── Payment Types ───────────────────────────────────────────────

export type PaymentProvider = 'paddle' | 'stripe' | 'razorpay';

export interface DemoPaymentRequest {
  provider: PaymentProvider;
  amount: number;
  currency: string;
  variant_id: string;
  industry: string;
  return_url?: string;
}

export interface DemoPaymentResponse {
  checkout_url: string;
  transaction_id: string;
  provider: PaymentProvider;
  status: 'pending' | 'completed' | 'failed';
  amount: string;
  currency: string;
}

// ── API Request/Response Types ──────────────────────────────────

export interface DemoVariantListResponse {
  variants: DemoVariant[];
  industries: string[];
}

export interface DemoSessionCreateRequest {
  variant_id: string;
  variant_tier: VariantTier;
  industry: string;
  entry_source: string;
}

export interface DemoSessionCreateResponse {
  session: DemoSession;
  welcome_message: string;
}

export interface DemoKnowledgeBaseListResponse {
  prebuilt: DemoKnowledgeBase[];
  uploaded: DemoKnowledgeBase[];
}

export interface DemoUsageResponse {
  usage: DemoUsage;
  events: DemoUsageEvent[];
}

export interface DemoBillingResponse {
  bill_summary: DemoBillSummary;
  estimate: DemoBillingEstimate;
}
