/**
 * JARVIS Voice Manager - Week 9 (Phase 3)
 *
 * Main orchestrator for voice processing including speech-to-text,
 * text-to-speech, voice activity detection, and command parsing.
 */

import type { Variant } from '@/types/variant';
import type {
  VoiceConfig,
  STTRequest,
  STTResult,
  TTSRequest,
  TTSResult,
  VADConfig,
  VADResult,
  VoiceCommand,
  VoiceSession,
  VoiceSessionState,
  VoiceEvent,
  VoiceEventType,
  VoiceStats,
  ProcessVoiceInputRequest,
  ProcessVoiceInputResponse,
  VoiceInfo,
  SpeechSegment,
  AudioFormat,
  VOICE_VARIANT_CAPABILITIES,
} from './types';
import { DEFAULT_VOICE_CONFIG } from './types';

// ── Voice Manager Class ──────────────────────────────────────────────

export class VoiceManager {
  private config: VoiceConfig;
  private sessions: Map<string, VoiceSession> = new Map();
  private stats: VoiceStats = {
    total_sessions: 0,
    stt_requests: 0,
    tts_requests: 0,
    avg_stt_latency_ms: 0,
    avg_tts_latency_ms: 0,
    avg_confidence: 0,
    total_audio_seconds: 0,
    error_count: 0,
  };
  private eventListeners: Map<VoiceEventType, Set<(event: VoiceEvent) => void>> = new Map();
  private isInitialized: boolean = false;

  constructor(config: VoiceConfig) {
    this.config = config;
  }

  /**
   * Initialize the voice manager
   */
  async initialize(): Promise<void> {
    if (this.isInitialized) return;
    
    // Initialize based on variant capabilities
    const capabilities = this.getCapabilities();
    
    if (!capabilities.stt_enabled && !capabilities.tts_enabled) {
      this.isInitialized = true;
      return;
    }

    this.isInitialized = true;
    this.emitEvent('session_started', { message: 'Voice manager initialized' });
  }

  /**
   * Process voice input (main entry point)
   */
  async processVoiceInput(request: ProcessVoiceInputRequest): Promise<ProcessVoiceInputResponse> {
    const startTime = Date.now();
    
    try {
      // Ensure initialized
      if (!this.isInitialized) {
        await this.initialize();
      }

      // Check capabilities
      const capabilities = this.getCapabilities();
      if (!capabilities.stt_enabled) {
        return this.createErrorResponse(
          request.session_id || '',
          'Voice input not supported for this variant'
        );
      }

      // Get or create session
      let session = request.session_id ? this.sessions.get(request.session_id) : null;
      if (!session) {
        session = this.createSession(request.user_id);
      }

      // Update session state
      session.state = 'listening';
      this.updateSessionActivity(session);

      // Step 1: Speech-to-Text
      const sttResult = await this.speechToText({
        audio_data: request.audio_data,
        format: request.format,
        language: request.language || this.config.language,
        session_id: session.id,
      });

      if (!sttResult.transcript) {
        return this.createErrorResponse(session.id, 'Could not transcribe audio');
      }

      // Update session state
      session.state = 'processing';

      // Step 2: Parse voice command
      const command = this.parseVoiceCommand(sttResult.transcript, session.id);

      // Step 3: Generate response (would integrate with JARVIS command processor)
      const responseText = this.generateResponse(command, sttResult.transcript);

      // Step 4: Text-to-Speech if enabled
      let responseAudio: string | undefined;
      let audioFormat: AudioFormat | undefined;

      if (capabilities.tts_enabled && responseText) {
        session.state = 'speaking';
        const ttsResult = await this.textToSpeech({
          text: responseText,
          language: request.language || this.config.language,
          session_id: session.id,
        });
        responseAudio = ttsResult.audio_data;
        audioFormat = ttsResult.format;
      }

      // Update session state
      session.state = 'idle';
      this.updateSessionActivity(session);

      // Update stats
      this.updateStats(Date.now() - startTime, sttResult.confidence, 0);

      return {
        session_id: session.id,
        transcript: sttResult.transcript,
        confidence: sttResult.confidence,
        command,
        response_text: responseText,
        response_audio: responseAudio,
        audio_format: audioFormat,
        success: true,
        timestamp: new Date(),
      };
    } catch (error) {
      this.stats.error_count++;
      return this.createErrorResponse(
        request.session_id || '',
        error instanceof Error ? error.message : 'Unknown error'
      );
    }
  }

  /**
   * Convert speech to text
   */
  async speechToText(request: STTRequest): Promise<STTResult> {
    const startTime = Date.now();

    // Check capabilities
    if (!this.getCapabilities().stt_enabled) {
      throw new Error('Speech-to-text not enabled for this variant');
    }

    // Simulate STT processing
    // In production, this would call actual STT service (Google, AWS, Azure, etc.)
    const result: STTResult = await this.simulateSTT(request);

    // Update stats
    this.stats.stt_requests++;
    this.stats.avg_stt_latency_ms = this.calculateAverage(
      this.stats.avg_stt_latency_ms,
      Date.now() - startTime,
      this.stats.stt_requests
    );

    this.emitEvent('transcript_ready', {
      transcript: result.transcript,
      confidence: result.confidence,
      session_id: request.session_id,
    });

    return result;
  }

  /**
   * Convert text to speech
   */
  async textToSpeech(request: TTSRequest): Promise<TTSResult> {
    const startTime = Date.now();

    // Check capabilities
    if (!this.getCapabilities().tts_enabled) {
      throw new Error('Text-to-speech not enabled for this variant');
    }

    // Simulate TTS processing
    // In production, this would call actual TTS service
    const result: TTSResult = await this.simulateTTS(request);

    // Update stats
    this.stats.tts_requests++;
    this.stats.avg_tts_latency_ms = this.calculateAverage(
      this.stats.avg_tts_latency_ms,
      Date.now() - startTime,
      this.stats.tts_requests
    );

    this.emitEvent('response_ready', {
      duration: result.duration_seconds,
      voice_id: result.voice_id,
      session_id: request.session_id,
    });

    return result;
  }

  /**
   * Detect voice activity
   */
  detectVoiceActivity(audioData: ArrayBuffer, config?: VADConfig): VADResult {
    const vadConfig = config || {
      enabled: this.config.vad_enabled ?? false,
      silence_threshold_db: -35,
      min_speech_duration_ms: 250,
      silence_duration_ms: this.config.vad_silence_threshold_ms ?? 1500,
    };

    if (!vadConfig.enabled) {
      return {
        speech_detected: false,
        probability: 0,
        audio_level_db: -60,
      };
    }

    // Simulate VAD processing
    // In production, this would analyze audio samples
    const audioLevel = this.calculateAudioLevel(audioData);
    const speechDetected = audioLevel > vadConfig.silence_threshold_db!;
    const probability = speechDetected ? 0.8 + Math.random() * 0.2 : Math.random() * 0.3;

    return {
      speech_detected: speechDetected,
      probability,
      audio_level_db: audioLevel,
    };
  }

  /**
   * Parse voice command from transcript
   */
  parseVoiceCommand(transcript: string, sessionId: string): VoiceCommand {
    // Normalize text
    const normalizedText = transcript
      .toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    // Detect intent based on keywords
    const intent = this.detectIntent(normalizedText);

    // Extract entities
    const entities = this.extractEntities(normalizedText);

    const command: VoiceCommand = {
      id: `cmd_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      transcript,
      normalized_text: normalizedText,
      intent,
      entities,
      confidence: this.calculateCommandConfidence(normalizedText, intent),
      session_id: sessionId,
      timestamp: new Date(),
    };

    this.emitEvent('command_parsed', {
      command_id: command.id,
      intent: command.intent,
      confidence: command.confidence,
    });

    return command;
  }

  /**
   * Get available voices
   */
  getAvailableVoices(language?: string): VoiceInfo[] {
    const capabilities = this.getCapabilities();
    
    const voices: VoiceInfo[] = [
      { id: 'en-US-Neural2-A', name: 'Jenny', language: 'en-US', gender: 'female', type: 'neural' },
      { id: 'en-US-Neural2-B', name: 'Jason', language: 'en-US', gender: 'male', type: 'neural' },
      { id: 'en-US-Neural2-C', name: 'Joanna', language: 'en-US', gender: 'female', type: 'neural' },
      { id: 'en-US-Neural2-D', name: 'Joey', language: 'en-US', gender: 'male', type: 'neural' },
      { id: 'en-GB-Neural2-A', name: 'Emma', language: 'en-GB', gender: 'female', type: 'neural' },
      { id: 'es-ES-Neural2-A', name: 'Lucia', language: 'es-ES', gender: 'female', type: 'neural' },
      { id: 'fr-FR-Neural2-A', name: 'Celine', language: 'fr-FR', gender: 'female', type: 'neural' },
    ];

    // Filter by language if specified
    const filtered = language
      ? voices.filter(v => v.language.startsWith(language.split('-')[0]))
      : voices;

    // Limit by variant capabilities
    return filtered.slice(0, capabilities.voice_options);
  }

  /**
   * Get or create session
   */
  getSession(sessionId: string): VoiceSession | undefined {
    return this.sessions.get(sessionId);
  }

  /**
   * End session
   */
  async endSession(sessionId: string): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (session) {
      this.emitEvent('session_ended', {
        duration_ms: Date.now() - session.created_at.getTime(),
        exchanges: session.history.length,
      });
      this.sessions.delete(sessionId);
    }
  }

  /**
   * Get capabilities for current variant
   */
  getCapabilities(): typeof VOICE_VARIANT_CAPABILITIES[Variant] {
    const capabilities: Record<Variant, typeof VOICE_VARIANT_CAPABILITIES[Variant]> = {
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
    return capabilities[this.config.variant];
  }

  /**
   * Get statistics
   */
  getStats(): VoiceStats {
    return { ...this.stats };
  }

  /**
   * Subscribe to events
   */
  onEvent(eventType: VoiceEventType, callback: (event: VoiceEvent) => void): () => void {
    if (!this.eventListeners.has(eventType)) {
      this.eventListeners.set(eventType, new Set());
    }
    this.eventListeners.get(eventType)!.add(callback);
    
    // Return unsubscribe function
    return () => {
      this.eventListeners.get(eventType)?.delete(callback);
    };
  }

  /**
   * Shutdown manager
   */
  async shutdown(): Promise<void> {
    // End all sessions
    for (const sessionId of this.sessions.keys()) {
      await this.endSession(sessionId);
    }
    this.eventListeners.clear();
    this.isInitialized = false;
  }

  // ── Private Methods ────────────────────────────────────────────────

  private createSession(userId?: string): VoiceSession {
    const sessionId = `voice_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const session: VoiceSession = {
      id: sessionId,
      tenant_id: this.config.tenant_id,
      variant: this.config.variant,
      user_id: userId,
      state: 'idle',
      history: [],
      created_at: new Date(),
      last_activity: new Date(),
      config: this.config,
    };

    this.sessions.set(sessionId, session);
    this.stats.total_sessions++;

    this.emitEvent('session_started', { session_id: sessionId, user_id: userId });

    return session;
  }

  private updateSessionActivity(session: VoiceSession): void {
    session.last_activity = new Date();
  }

  private async simulateSTT(request: STTRequest): Promise<STTResult> {
    // Simulate processing delay
    await new Promise(resolve => setTimeout(resolve, 100 + Math.random() * 200));

    // Return simulated result
    // In production, this would call actual STT API
    const simulatedTranscripts = [
      'show my open tickets',
      'assign ticket to agent',
      'create a new ticket',
      'what is the status of ticket',
      'show customer history',
    ];

    const transcript = simulatedTranscripts[Math.floor(Math.random() * simulatedTranscripts.length)];
    const confidence = 0.85 + Math.random() * 0.15;

    return {
      id: `stt_${Date.now()}`,
      transcript,
      confidence,
      alternatives: [
        { transcript: transcript.replace('show', 'list'), confidence: confidence - 0.1 },
      ],
      detected_language: request.language || this.config.language,
      processing_time_ms: 150 + Math.random() * 100,
      timestamp: new Date(),
    };
  }

  private async simulateTTS(request: TTSRequest): Promise<TTSResult> {
    // Simulate processing delay
    await new Promise(resolve => setTimeout(resolve, 50 + Math.random() * 100));

    // Calculate duration based on text length (roughly 150 words per minute)
    const words = request.text.split(/\s+/).length;
    const durationSeconds = words / 2.5; // ~150 words per minute

    // Return simulated result with empty audio (base64)
    // In production, this would return actual audio data
    return {
      audio_data: 'UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=', // Empty WAV header
      format: request.output_format || 'wav',
      duration_seconds: durationSeconds,
      voice_id: request.voice_id || 'en-US-Neural2-A',
      processing_time_ms: 100 + Math.random() * 50,
      timestamp: new Date(),
    };
  }

  private calculateAudioLevel(audioData: ArrayBuffer): number {
    // Simplified audio level calculation
    // In production, would analyze actual audio samples
    const bytes = new Uint8Array(audioData);
    let sum = 0;
    const sampleSize = Math.min(bytes.length, 1000);
    for (let i = 0; i < sampleSize; i++) {
      sum += bytes[i];
    }
    const avg = sum / sampleSize;
    // Convert to approximate dB level
    const normalized = Math.abs(avg - 128) / 128;
    return -60 + normalized * 60;
  }

  private detectIntent(text: string): string {
    const intentPatterns: Record<string, string[]> = {
      search_tickets: ['show', 'list', 'find', 'tickets', 'my tickets'],
      view_ticket: ['view', 'ticket', 'status', 'details'],
      create_ticket: ['create', 'new', 'open', 'ticket'],
      assign_ticket: ['assign', 'give', 'transfer', 'to'],
      close_ticket: ['close', 'resolve', 'complete', 'ticket'],
      view_customer: ['customer', 'profile', 'details'],
      get_help: ['help', 'what can you do', 'commands'],
    };

    for (const [intent, keywords] of Object.entries(intentPatterns)) {
      const matches = keywords.filter(kw => text.includes(kw));
      if (matches.length >= 2) {
        return intent;
      }
    }

    return 'unknown';
  }

  private extractEntities(text: string): Array<{
    type: string;
    value: string;
    normalized_value?: string | number;
    start_index: number;
    end_index: number;
    confidence: number;
  }> {
    const entities: Array<{
      type: string;
      value: string;
      normalized_value?: string | number;
      start_index: number;
      end_index: number;
      confidence: number;
    }> = [];

    // Extract ticket IDs
    const ticketMatch = text.match(/ticket\s*#?\s*(\d+)/);
    if (ticketMatch) {
      entities.push({
        type: 'ticket_id',
        value: ticketMatch[1],
        normalized_value: ticketMatch[1],
        start_index: ticketMatch.index!,
        end_index: ticketMatch.index! + ticketMatch[0].length,
        confidence: 0.95,
      });
    }

    // Extract agent names
    const agentMatch = text.match(/(?:agent|to)\s+([a-z]+)/);
    if (agentMatch) {
      entities.push({
        type: 'agent_id',
        value: agentMatch[1],
        normalized_value: agentMatch[1].charAt(0).toUpperCase() + agentMatch[1].slice(1),
        start_index: agentMatch.index!,
        end_index: agentMatch.index! + agentMatch[0].length,
        confidence: 0.9,
      });
    }

    return entities;
  }

  private calculateCommandConfidence(text: string, intent: string): number {
    if (intent === 'unknown') return 0.3;
    
    // Base confidence
    let confidence = 0.7;
    
    // Boost for clear intent indicators
    if (text.includes('ticket') || text.includes('customer')) {
      confidence += 0.1;
    }
    
    // Reduce for vague commands
    if (text.length < 5) {
      confidence -= 0.2;
    }

    return Math.min(1, Math.max(0, confidence));
  }

  private generateResponse(command: VoiceCommand | undefined, transcript: string): string {
    if (!command || command.intent === 'unknown') {
      return "I'm not sure what you'd like me to do. Can you please rephrase that?";
    }

    const responses: Record<string, string> = {
      search_tickets: "Here are your tickets. You have 5 open tickets requiring attention.",
      view_ticket: "I found that ticket. It's currently in progress and assigned to the support team.",
      create_ticket: "I'll create a new ticket for you. What is the subject?",
      assign_ticket: "I'll assign that ticket right away.",
      close_ticket: "I've closed that ticket for you. Is there anything else you need?",
      view_customer: "Here's the customer profile you requested.",
      get_help: "I can help you manage tickets, view customer information, and perform various support tasks. Just ask!",
    };

    return responses[command.intent] || "I understand you want to " + command.intent.replace(/_/g, ' ') + ". Let me help you with that.";
  }

  private updateStats(processingTime: number, confidence: number, audioSeconds: number): void {
    this.stats.avg_confidence = (this.stats.avg_confidence + confidence) / 2;
    this.stats.total_audio_seconds += audioSeconds;
  }

  private calculateAverage(currentAvg: number, newValue: number, count: number): number {
    return ((currentAvg * (count - 1)) + newValue) / count;
  }

  private emitEvent(type: VoiceEventType, payload: Record<string, unknown>): void {
    const event: VoiceEvent = {
      type,
      session_id: '',
      timestamp: new Date(),
      payload,
    };

    const listeners = this.eventListeners.get(type);
    if (listeners) {
      for (const callback of listeners) {
        try {
          callback(event);
        } catch (error) {
          console.error('Voice event callback error:', error);
        }
      }
    }
  }

  private createErrorResponse(sessionId: string, error: string): ProcessVoiceInputResponse {
    this.stats.error_count++;
    return {
      session_id: sessionId,
      transcript: '',
      confidence: 0,
      success: false,
      error,
      timestamp: new Date(),
    };
  }
}

// ── Factory Functions ────────────────────────────────────────────────

export function createVoiceManager(config: VoiceConfig): VoiceManager {
  return new VoiceManager(config);
}

export function getVoiceManager(config: VoiceConfig): VoiceManager {
  return createVoiceManager(config);
}
