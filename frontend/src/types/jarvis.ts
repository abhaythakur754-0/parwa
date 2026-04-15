/**
 * PARWA Jarvis Types (Week 6 — Day 2 Phase 4)
 *
 * TypeScript type definitions for the Jarvis onboarding chat system.
 * Mirrors backend Pydantic schemas from backend/app/schemas/jarvis.py
 *
 * Based on: JARVIS_SPECIFICATION.md v3.0 / JARVIS_ROADMAP.md v4.0
 */

// ── Core Enums (union types) ──────────────────────────────────────

export type MessageType =
  | 'text'
  | 'bill_summary'
  | 'payment_card'
  | 'otp_card'
  | 'handoff_card'
  | 'demo_call_card'
  | 'action_ticket'
  | 'call_summary'
  | 'recharge_cta'
  | 'limit_reached'
  | 'pack_expired'
  | 'error'
  | 'message_counter'
  | 'demo_pack_cta';

export type SessionType = 'onboarding' | 'customer_care';

export type PackType = 'free' | 'demo';

export type PaymentStatus = 'none' | 'pending' | 'completed' | 'failed';

export type MessageRole = 'user' | 'jarvis' | 'system';

export type ConversationStage =
  | 'welcome'
  | 'discovery'
  | 'demo'
  | 'pricing'
  | 'bill_review'
  | 'verification'
  | 'payment'
  | 'handoff';

export type EntrySource =
  | 'direct'
  | 'pricing'
  | 'roi'
  | 'demo'
  | 'features'
  | 'referral'
  | 'ad'
  | 'organic'
  | 'email_campaign'
  | 'other';

export type TicketType =
  | 'otp_verification'
  | 'otp_verified'
  | 'payment_demo_pack'
  | 'payment_variant'
  | 'payment_variant_completed'
  | 'demo_call'
  | 'demo_call_completed'
  | 'roi_import'
  | 'handoff';

export type TicketStatus = 'pending' | 'in_progress' | 'completed' | 'failed';

// ── Variant & ROI Types ───────────────────────────────────────────

export interface VariantSelection {
  id: string;
  name?: string;
  quantity: number;
  price?: number;
  price_per_month?: number;
  tickets_per_month?: number;
  features?: string[];
}

export interface RoiResult {
  monthly_tickets: number;
  monthly_cost: number;
  annual_cost: number;
  annual_savings: number;
  currency?: string;
}

// ── Context (everything Jarvis remembers) ─────────────────────────

export interface JarvisContext {
  pages_visited: string[];
  industry: string | null;
  selected_variants: VariantSelection[];
  roi_result: RoiResult | null;
  demo_topics: string[];
  concerns_raised: string[];
  business_email: string | null;
  email_verified: boolean;
  referral_source: string;
  entry_source: EntrySource;
  entry_params: Record<string, unknown>;
  detected_stage: ConversationStage;
  total_price?: number;
  otp?: OtpContextData;
  bill_shown?: boolean;
  variant?: string;
  variant_id?: string;
  selected_plan?: string;
}

export interface OtpContextData {
  code?: string;
  email: string;
  attempts: number;
  attempts_remaining: number;
  expires_at: string | null;
  status: 'idle' | 'sent' | 'verified' | 'expired' | 'error';
  verified_at?: string;
}

// ── Session ───────────────────────────────────────────────────────

export interface JarvisSession {
  id: string;
  type: SessionType;
  context: JarvisContext;
  message_count_today: number;
  total_message_count: number;
  remaining_today: number;
  pack_type: PackType;
  pack_expiry: string | null;
  demo_call_used: boolean;
  is_active: boolean;
  payment_status: PaymentStatus;
  handoff_completed: boolean;
  detected_stage: ConversationStage;
  created_at: string | null;
  updated_at: string | null;
}

// ── Messages ──────────────────────────────────────────────────────

export interface JarvisMessage {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  message_type: MessageType;
  metadata: Record<string, unknown>;
  timestamp: string | null;
  knowledge_used?: KnowledgeUsedItem[];
}

export interface KnowledgeUsedItem {
  file: string;
  score: number;
}

// ── Flow State Types ──────────────────────────────────────────────

export interface OtpState {
  status: 'idle' | 'sending' | 'sent' | 'verifying' | 'verified' | 'error';
  email: string;
  attempts: number;
  expires_at: string | null;
}

export interface PaymentState {
  status: 'idle' | 'processing' | 'success' | 'failed';
  paddle_url: string | null;
  error: string | null;
}

export interface HandoffState {
  status: 'idle' | 'in_progress' | 'completed';
  new_session_id?: string | null;
}

export interface DemoCallState {
  status: 'idle' | 'initiating' | 'calling' | 'completed' | 'failed';
  phone: string | null;
  duration: number;
  call_id?: string | null;
}

// ── API Request Types ─────────────────────────────────────────────

export interface JarvisSessionCreateRequest {
  entry_source?: EntrySource;
  entry_params?: Record<string, unknown>;
}

export interface JarvisMessageSendRequest {
  content: string;
  session_id?: string;
}

export interface JarvisContextUpdateRequest {
  industry?: string | null;
  selected_variants?: VariantSelection[];
  roi_result?: RoiResult | null;
  demo_topics?: string[];
  concerns_raised?: string[];
  business_email?: string | null;
  email_verified?: boolean;
  referral_source?: string;
  pages_visited?: string[];
  detected_stage?: ConversationStage;
  total_price?: number;
}

export interface JarvisEntryContextRequest {
  entry_source: EntrySource;
  entry_params?: Record<string, unknown>;
}

export interface JarvisOtpRequest {
  email: string;
}

export interface JarvisOtpVerifyRequest {
  code: string;
  email?: string;
}

export interface JarvisPaymentCreateRequest {
  variants: VariantSelection[];
  industry: string;
}

export interface JarvisDemoCallRequest {
  phone: string;
}

export interface JarvisDemoCallVerifyOtpRequest {
  code: string;
}

export interface JarvisActionTicketCreateRequest {
  ticket_type: TicketType;
  metadata?: Record<string, unknown>;
}

export interface JarvisActionTicketUpdateStatusRequest {
  status: TicketStatus;
}

// ── API Response Types ────────────────────────────────────────────

export interface JarvisHistoryResponse {
  messages: JarvisMessage[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface JarvisOtpResponse {
  message: string;
  status: string;
  attempts_remaining: number | null;
  expires_at: string | null;
}

export interface JarvisDemoPackStatusResponse {
  pack_type: PackType;
  remaining_today: number;
  total_allowed: number;
  pack_expiry: string | null;
  demo_call_remaining: boolean;
}

export interface JarvisPaymentStatusResponse {
  status: PaymentStatus;
  paddle_transaction_id: string | null;
  amount: string | null;
  currency: string;
  paid_at: string | null;
}

export interface JarvisDemoCallSummaryResponse {
  call_id: string | null;
  status: string;
  duration_seconds: number;
  topics_discussed: string[];
  key_moments: Record<string, unknown>[];
  user_impressions: string | null;
  roi_mapping: Record<string, unknown> | null;
  transcript_summary: string | null;
  created_at: string | null;
}

export interface JarvisHandoffStatusResponse {
  handoff_completed: boolean;
  new_session_id: string | null;
  handoff_at: string | null;
}

export interface JarvisActionTicketResponse {
  id: string;
  session_id: string;
  ticket_type: TicketType;
  status: TicketStatus;
  result: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
}

export interface JarvisActionTicketListResponse {
  tickets: JarvisActionTicketResponse[];
  total: number;
}

export interface JarvisPurchaseResponse {
  message: string;
  pack_type: PackType;
  pack_expiry: string;
  remaining_today: number;
  demo_call_remaining: boolean;
}

export interface JarvisPaymentCreateResponse {
  checkout_url: string;
  transaction_id: string;
  status: string;
  amount: string;
  currency: string;
}

export interface JarvisDemoCallInitiateResponse {
  call_id: string;
  status: string;
  phone: string;
  duration_limit: number;
  message: string;
}

// ── Error Types ───────────────────────────────────────────────────

export interface ParwaApiError {
  error: {
    code: string;
    message: string;
    details: unknown;
    correlation_id?: string;
  };
}
