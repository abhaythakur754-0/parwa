/**
 * PARWA Voice Channel Types
 *
 * Type definitions for voice calls, conversations, and configuration.
 * Matches the backend VoiceChannel models and API schemas.
 *
 * D3: Supports two number source modes:
 * - "parwa_provided": Parwa provisions a number using our Twilio account
 * - "bring_own": Client provides their own Twilio credentials
 */

// ── Voice Call ──────────────────────────────────────────────────────

export type CallDirection = 'inbound' | 'outbound';

export type CallStatus =
  | 'queued'
  | 'ringing'
  | 'in-progress'
  | 'completed'
  | 'failed'
  | 'busy'
  | 'no-answer'
  | 'canceled';

export type NumberSource = 'parwa_provided' | 'bring_own';

export type GreetingStyle = 'professional' | 'friendly' | 'casual';

export interface VoiceCall {
  id: string;
  company_id: string;
  conversation_id?: string;
  ticket_id?: string;
  twilio_call_sid: string;
  twilio_account_sid?: string;
  direction: CallDirection;
  from_number: string;
  to_number: string;
  status: CallStatus;
  variant_tier: string;
  intent_detected?: string;
  resolution?: string;
  duration_seconds: number;
  started_at?: string;
  ended_at?: string;
  recording_url?: string;
  recording_sid?: string;
  recording_enabled?: boolean;
  transcript_summary?: string;
  topics_discussed?: string[] | string;
  key_moments_json?: string;
  satisfaction_score?: number;
  sender_id?: string;
  sender_role?: string;
  metadata_json?: string;
  created_at: string;
  updated_at?: string;
}

// ── Voice Conversation ──────────────────────────────────────────────

export interface VoiceConversation {
  id: string;
  company_id: string;
  customer_number: string;
  twilio_number: string;
  call_count: number;
  total_duration_seconds: number;
  last_call_at?: string;
  is_opted_out: boolean;
  created_at: string;
  updated_at?: string;
}

// ── Voice Channel Config ────────────────────────────────────────────

export interface VoiceChannelConfig {
  id: string;
  company_id: string;

  // D3: Number source mode
  number_source: NumberSource;

  // D3: Caller ID and greeting
  caller_id_name?: string;
  greeting_style: GreetingStyle;
  language_preference: string;

  // Parwa-provided number info (only when number_source = "parwa_provided")
  parwa_phone_number?: string;

  // Twilio info (masked in API responses for security)
  twilio_account_sid: string;  // Masked: "****cdef"
  twilio_phone_number?: string;

  // Channel settings
  is_enabled: boolean;
  default_variant: string;
  max_call_duration_minutes: number;
  enable_recording: boolean;

  // Speech settings
  speech_language: string;
  tts_voice: string;

  // Transfer
  transfer_number?: string;

  // Rate limits
  max_calls_per_hour: number;
  max_calls_per_day: number;

  // Messages
  greeting_message?: string;
  after_hours_message?: string;

  created_at: string;
  updated_at?: string;
}

// ── API Request/Response Types ──────────────────────────────────────

export interface InitiateCallRequest {
  to_number: string;
  variant_tier?: string;
  message?: string;
  ticket_id?: string;
  enable_recording?: boolean;
  sender_role?: string;
}

export interface InitiateCallResponse {
  id: string;
  twilio_call_sid: string;
  status: CallStatus;
  direction: CallDirection;
  to_number: string;
  from_number: string;
  created_at: string;
}

export interface ListCallsParams {
  page?: number;
  page_size?: number;
  direction?: CallDirection;
  status?: CallStatus;
}

export interface ListCallsResponse {
  calls: VoiceCall[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TransferCallRequest {
  to_number: string;
}

export interface CallHistoryParams {
  phone_number?: string;
  direction?: CallDirection;
  status?: CallStatus;
  page?: number;
  page_size?: number;
}

export interface CallHistoryResponse {
  calls: VoiceCall[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/**
 * Create voice config — D3 supports two modes:
 *
 * Option A (parwa_provided): Parwa provisions a number. Only optional fields needed.
 *   - number_source: "parwa_provided"
 *   - area_code (optional), country (optional)
 *
 * Option B (bring_own): Client provides Twilio credentials.
 *   - number_source: "bring_own"
 *   - twilio_account_sid, twilio_auth_token, twilio_phone_number (required)
 */
export interface CreateVoiceConfigRequest {
  // D3: Number source mode
  number_source?: NumberSource;

  // Option A: Parwa-provided number parameters
  area_code?: string;
  country?: string;

  // Option B: Bring own number (required when number_source = "bring_own")
  twilio_account_sid?: string;
  twilio_auth_token?: string;
  twilio_phone_number?: string;

  // D3: Caller ID and greeting
  caller_id_name?: string;
  greeting_style?: GreetingStyle;
  language_preference?: string;

  // Channel settings
  is_enabled?: boolean;
  default_variant?: string;
  max_call_duration_minutes?: number;
  enable_recording?: boolean;

  // Speech settings
  speech_language?: string;
  tts_voice?: string;

  // Transfer
  transfer_number?: string;

  // Rate limits
  max_calls_per_hour?: number;
  max_calls_per_day?: number;

  // Messages
  greeting_message?: string;
  after_hours_message?: string;
  business_hours_json?: string;
}

export interface UpdateVoiceConfigRequest {
  // D3 fields
  caller_id_name?: string;
  greeting_style?: GreetingStyle;
  language_preference?: string;

  // Twilio credentials (only for bring_own mode)
  twilio_account_sid?: string;
  twilio_auth_token?: string;
  twilio_phone_number?: string;

  // Channel settings
  is_enabled?: boolean;
  default_variant?: string;
  max_call_duration_minutes?: number;
  enable_recording?: boolean;

  // Speech settings
  speech_language?: string;
  tts_voice?: string;

  // Transfer
  transfer_number?: string;

  // Rate limits
  max_calls_per_hour?: number;
  max_calls_per_day?: number;

  // Messages
  greeting_message?: string;
  after_hours_message?: string;
  business_hours_json?: string;
}

export interface TestCallRequest {
  to_number: string;
}

export interface TestCallResponse {
  id: string;
  twilio_call_sid: string;
  status: CallStatus;
  message: string;
}

// ── Provision Response ──────────────────────────────────────────────

export interface ProvisionNumberResponse {
  status: 'provisioned' | 'error';
  phone_number?: string;
  number_sid?: string;
  error?: string;
}

export interface ReleaseNumberResponse {
  status: 'released' | 'skipped' | 'error';
  number_sid?: string;
  message?: string;
  error?: string;
}
