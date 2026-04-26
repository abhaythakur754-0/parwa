/**
 * JARVIS Voice Integration Types - Week 9 (Phase 3)
 *
 * Type definitions for voice processing, speech-to-text, and text-to-speech.
 */

import type { Variant } from '@/types/variant';

// ── Voice Configuration ──────────────────────────────────────────────

export interface VoiceConfig {
  /** Tenant ID */
  tenant_id: string;
  /** Variant for capability gating */
  variant: Variant;
  /** Enable speech-to-text */
  stt_enabled: boolean;
  /** Enable text-to-speech */
  tts_enabled: boolean;
  /** Language code (e.g., 'en-US', 'es-ES') */
  language: string;
  /** Voice ID for TTS */
  voice_id?: string;
  /** Speech rate (0.5 - 2.0) */
  speech_rate?: number;
  /** Enable voice activity detection */
  vad_enabled?: boolean;
  /** Minimum silence duration to detect end of speech (ms) */
  vad_silence_threshold_ms?: number;
  /** Noise suppression level */
  noise_suppression?: 'none' | 'low' | 'medium' | 'high';
}

export const DEFAULT_VOICE_CONFIG: Record<Variant, Partial<VoiceConfig>> = {
  mini_parwa: {
    stt_enabled: false,
    tts_enabled: false,
    language: 'en-US',
    vad_enabled: false,
  },
  parwa: {
    stt_enabled: true,
    tts_enabled: true,
    language: 'en-US',
    speech_rate: 1.0,
    vad_enabled: true,
    vad_silence_threshold_ms: 1500,
    noise_suppression: 'medium',
  },
  parwa_high: {
    stt_enabled: true,
    tts_enabled: true,
    language: 'en-US',
    speech_rate: 1.0,
    vad_enabled: true,
    vad_silence_threshold_ms: 2000,
    noise_suppression: 'high',
  },
};

// ── Speech-to-Text Types ─────────────────────────────────────────────

export interface STTRequest {
  /** Audio data (base64 encoded or ArrayBuffer) */
  audio_data: string | ArrayBuffer;
  /** Audio format */
  format: AudioFormat;
  /** Sample rate in Hz */
  sample_rate?: number;
  /** Language code */
  language?: string;
  /** Enable profanity filter */
  profanity_filter?: boolean;
  /** Enable punctuation */
  enable_punctuation?: boolean;
  /** Session ID for context */
  session_id?: string;
}

export interface STTResult {
  /** Transcript ID */
  id: string;
  /** Recognized text */
  transcript: string;
  /** Confidence score (0-1) */
  confidence: number;
  /** Alternative transcripts */
  alternatives?: STTAlternative[];
  /** Detected language */
  detected_language?: string;
  /** Processing time in ms */
  processing_time_ms: number;
  /** Word-level timing */
  words?: WordTiming[];
  /** Timestamp */
  timestamp: Date;
}

export interface STTAlternative {
  /** Alternative transcript */
  transcript: string;
  /** Confidence score */
  confidence: number;
}

export interface WordTiming {
  /** The word */
  word: string;
  /** Start time in seconds */
  start_time: number;
  /** End time in seconds */
  end_time: number;
  /** Confidence score */
  confidence: number;
}

export type AudioFormat = 'wav' | 'mp3' | 'ogg' | 'webm' | 'flac' | 'pcm';

// ── Text-to-Speech Types ─────────────────────────────────────────────

export interface TTSRequest {
  /** Text to synthesize */
  text: string;
  /** Voice ID */
  voice_id?: string;
  /** Language code */
  language?: string;
  /** Speech rate (0.5 - 2.0) */
  rate?: number;
  /** Pitch adjustment (-20 to +20) */
  pitch?: number;
  /** Output format */
  output_format?: AudioFormat;
  /** SSML markup */
  ssml?: boolean;
  /** Session ID for context */
  session_id?: string;
}

export interface TTSResult {
  /** Audio data (base64 encoded) */
  audio_data: string;
  /** Audio format */
  format: AudioFormat;
  /** Duration in seconds */
  duration_seconds: number;
  /** Voice ID used */
  voice_id: string;
  /** Processing time in ms */
  processing_time_ms: number;
  /** Timestamp */
  timestamp: Date;
}

export interface VoiceInfo {
  /** Voice ID */
  id: string;
  /** Display name */
  name: string;
  /** Language code */
  language: string;
  /** Gender */
  gender: 'male' | 'female' | 'neutral';
  /** Voice type */
  type: 'standard' | 'neural' | 'premium';
  /** Sample audio URL */
  sample_url?: string;
}

// ── Voice Activity Detection Types ───────────────────────────────────

export interface VADConfig {
  /** Enable VAD */
  enabled: boolean;
  /** Silence threshold in dB */
  silence_threshold_db?: number;
  /** Minimum speech duration (ms) */
  min_speech_duration_ms?: number;
  /** Silence duration to detect end (ms) */
  silence_duration_ms?: number;
  /** Speech probability threshold (0-1) */
  speech_probability_threshold?: number;
}

export interface VADResult {
  /** Speech detected */
  speech_detected: boolean;
  /** Speech probability (0-1) */
  probability: number;
  /** Start time of speech segment */
  start_time?: number;
  /** End time of speech segment */
  end_time?: number;
  /** Audio level in dB */
  audio_level_db: number;
}

export interface SpeechSegment {
  /** Segment ID */
  id: string;
  /** Start time in seconds */
  start_time: number;
  /** End time in seconds */
  end_time: number;
  /** Duration in seconds */
  duration: number;
  /** Transcript of the segment */
  transcript?: string;
  /** Confidence score */
  confidence: number;
}

// ── Voice Command Types ──────────────────────────────────────────────

export interface VoiceCommand {
  /** Command ID */
  id: string;
  /** Raw transcript */
  transcript: string;
  /** Normalized command text */
  normalized_text: string;
  /** Detected intent */
  intent?: string;
  /** Extracted entities */
  entities?: VoiceEntity[];
  /** Confidence score */
  confidence: number;
  /** Session ID */
  session_id: string;
  /** Timestamp */
  timestamp: Date;
}

export interface VoiceEntity {
  /** Entity type */
  type: string;
  /** Entity value */
  value: string;
  /** Normalized value */
  normalized_value?: string | number;
  /** Start position in transcript */
  start_index: number;
  /** End position in transcript */
  end_index: number;
  /** Confidence score */
  confidence: number;
}

// ── Voice Session Types ──────────────────────────────────────────────

export interface VoiceSession {
  /** Session ID */
  id: string;
  /** Tenant ID */
  tenant_id: string;
  /** Variant */
  variant: Variant;
  /** User ID */
  user_id?: string;
  /** Session state */
  state: VoiceSessionState;
  /** Conversation history */
  history: VoiceExchange[];
  /** Created at */
  created_at: Date;
  /** Last activity */
  last_activity: Date;
  /** Configuration */
  config: VoiceConfig;
}

export type VoiceSessionState = 
  | 'idle'
  | 'listening'
  | 'processing'
  | 'speaking'
  | 'error';

export interface VoiceExchange {
  /** Exchange ID */
  id: string;
  /** User's voice input */
  user_input?: STTResult;
  /** JARVIS response */
  jarvis_response?: TTSResult;
  /** Parsed command */
  command?: VoiceCommand;
  /** Timestamp */
  timestamp: Date;
}

// ── Voice Events ─────────────────────────────────────────────────────

export interface VoiceEvent {
  /** Event type */
  type: VoiceEventType;
  /** Session ID */
  session_id: string;
  /** Timestamp */
  timestamp: Date;
  /** Event payload */
  payload: Record<string, unknown>;
}

export type VoiceEventType =
  | 'session_started'
  | 'session_ended'
  | 'speech_detected'
  | 'speech_ended'
  | 'transcript_ready'
  | 'command_parsed'
  | 'response_ready'
  | 'audio_played'
  | 'error'
  | 'silence_detected'
  | 'voice_activity';

// ── Voice Statistics ────────────────────────────────────────────────

export interface VoiceStats {
  /** Total sessions */
  total_sessions: number;
  /** Total STT requests */
  stt_requests: number;
  /** Total TTS requests */
  tts_requests: number;
  /** Average STT latency */
  avg_stt_latency_ms: number;
  /** Average TTS latency */
  avg_tts_latency_ms: number;
  /** Average confidence score */
  avg_confidence: number;
  /** Total audio processed (seconds) */
  total_audio_seconds: number;
  /** Error count */
  error_count: number;
}

// ── Voice Integration Response ──────────────────────────────────────

export interface ProcessVoiceInputRequest {
  /** Audio data */
  audio_data: string | ArrayBuffer;
  /** Audio format */
  format: AudioFormat;
  /** Session ID (optional, creates new if not provided) */
  session_id?: string;
  /** User ID */
  user_id?: string;
  /** User role */
  user_role?: string;
  /** Language override */
  language?: string;
}

export interface ProcessVoiceInputResponse {
  /** Session ID */
  session_id: string;
  /** Transcript */
  transcript: string;
  /** Confidence */
  confidence: number;
  /** Parsed command */
  command?: VoiceCommand;
  /** Response text */
  response_text?: string;
  /** Response audio (base64) */
  response_audio?: string;
  /** Audio format */
  audio_format?: AudioFormat;
  /** Success status */
  success: boolean;
  /** Error message */
  error?: string;
  /** Timestamp */
  timestamp: Date;
}

// ── Variant Capabilities ─────────────────────────────────────────────

export const VOICE_VARIANT_CAPABILITIES: Record<Variant, {
  stt_enabled: boolean;
  tts_enabled: boolean;
  vad_enabled: boolean;
  max_session_duration_minutes: number;
  max_audio_length_seconds: number;
  supported_languages: string[];
  voice_options: number;
}> = {
  mini_parwa: {
    stt_enabled: false,
    tts_enabled: false,
    vad_enabled: false,
    max_session_duration_minutes: 0,
    max_audio_length_seconds: 0,
    supported_languages: [],
    voice_options: 0,
  },
  parwa: {
    stt_enabled: true,
    tts_enabled: true,
    vad_enabled: true,
    max_session_duration_minutes: 30,
    max_audio_length_seconds: 60,
    supported_languages: ['en-US', 'en-GB', 'es-ES', 'fr-FR', 'de-DE'],
    voice_options: 5,
  },
  parwa_high: {
    stt_enabled: true,
    tts_enabled: true,
    vad_enabled: true,
    max_session_duration_minutes: 120,
    max_audio_length_seconds: 300,
    supported_languages: ['en-US', 'en-GB', 'es-ES', 'fr-FR', 'de-DE', 'ja-JP', 'zh-CN', 'pt-BR', 'it-IT'],
    voice_options: 20,
  },
};
