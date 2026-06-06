/**
 * PARWA Onboarding Jarvis — Type Definitions
 *
 * Types for the pre-purchase demo chat experience where
 * potential clients interact with Jarvis AI.
 */

// ── Session Types ──────────────────────────────────────────────────

export type OnboardingSessionType = 'onboarding' | 'customer_care';
export type PackType = 'free' | 'demo';
export type PaymentStatus = 'none' | 'pending' | 'completed' | 'failed';
export type ConversationStage =
  | 'welcome'
  | 'discovery'
  | 'demo'
  | 'pricing'
  | 'bill_review'
  | 'verification'
  | 'payment'
  | 'handoff';

export type MessageType =
  | 'text'
  | 'bill_summary'
  | 'payment_card'
  | 'otp_card'
  | 'handoff_card'
  | 'demo_call_card'
  | 'error'
  | 'limit_reached'
  | 'pack_expired'
  | 'recharge_cta'
  | 'action_ticket';

// ── Session ────────────────────────────────────────────────────────

export interface OnboardingSession {
  session_id: string;
  session_type: OnboardingSessionType;
  context: Record<string, any>;
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
}

// ── Messages ───────────────────────────────────────────────────────

export interface OnboardingMessage {
  id: string;
  session_id: string;
  role: 'user' | 'jarvis' | 'system';
  content: string;
  message_type: MessageType;
  metadata: Record<string, any>;
  timestamp: string;
}

// ── Flow States ────────────────────────────────────────────────────

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

export interface DemoCallState {
  status:
    | 'idle'
    | 'booking'
    | 'otp'
    | 'payment'
    | 'initiating'
    | 'active'
    | 'completed'
    | 'failed';
  phone: string | null;
  duration: number;
}

// ── Card Data ──────────────────────────────────────────────────────

export interface BillItem {
  variant_id: string;
  variant_name: string;
  quantity: number;
  price_per_unit: number;
  total: number;
}

export interface BillSummaryData {
  items: BillItem[];
  subtotal: number;
  total: number;
  billing_period: 'monthly' | 'annual';
}

export interface DemoCallData {
  phone_number: string;
  call_phase: string;
  price: string;
  duration_minutes: number;
}

export interface PaymentCardData {
  amount: number;
  description: string;
  checkout_url?: string;
  paddle_checkout?: boolean;
}

export interface OtpCardData {
  email: string;
  status: string;
  attempts_remaining?: number;
  expires_at?: string;
}

export interface HandoffCardData {
  handoff_completed: boolean;
  new_session_id?: string;
  agents_active?: string[];
  industry?: string;
}

export interface RechargeCtaData {
  pack_type: string;
  remaining_today: number;
  total_allowed: number;
}
