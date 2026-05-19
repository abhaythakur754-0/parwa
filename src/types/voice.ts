/**
 * PARWA Voice Channel Types
 *
 * Type definitions for voice calls, conversations, and configuration.
 * Matches the backend VoiceChannel models and API schemas.
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

export interface VoiceCall {
  id: string;
  company_id: string;
  twilio_call_sid: string;
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
  transcript_summary?: string;
  topics_discussed?: string[];
  satisfaction_score?: number;
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
  twilio_phone_number: string;
  is_enabled: boolean;
  default_variant: string;
  max_call_duration_minutes: number;
  enable_recording: boolean;
  speech_language: string;
  tts_voice: string;
  transfer_number?: string;
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

export interface CreateVoiceConfigRequest {
  twilio_account_sid: string;
  twilio_auth_token: string;
  twilio_phone_number: string;
  is_enabled?: boolean;
  default_variant?: string;
  max_call_duration_minutes?: number;
  enable_recording?: boolean;
  speech_language?: string;
  tts_voice?: string;
  transfer_number?: string;
}

export interface UpdateVoiceConfigRequest {
  twilio_account_sid?: string;
  twilio_auth_token?: string;
  twilio_phone_number?: string;
  is_enabled?: boolean;
  default_variant?: string;
  max_call_duration_minutes?: number;
  enable_recording?: boolean;
  speech_language?: string;
  tts_voice?: string;
  transfer_number?: string;
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
