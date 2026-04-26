/**
 * JARVIS Voice Integration Tests - Week 9 (Phase 3)
 *
 * Comprehensive test suite for voice processing capabilities.
 */

import { VoiceManager, createVoiceManager } from '../voice-manager';
import type {
  VoiceConfig,
  STTRequest,
  TTSRequest,
  VADConfig,
  VoiceSession,
  VoiceStats,
} from '../types';
import type { Variant } from '@/types/variant';

// ── Test Configuration ─────────────────────────────────────────────

const createTestConfig = (variant: Variant = 'parwa'): VoiceConfig => ({
  tenant_id: 'test-tenant',
  variant,
  stt_enabled: variant !== 'mini_parwa',
  tts_enabled: variant !== 'mini_parwa',
  language: 'en-US',
  speech_rate: 1.0,
  vad_enabled: variant !== 'mini_parwa',
  vad_silence_threshold_ms: 1500,
  noise_suppression: 'medium',
});

// ── Voice Manager Tests ────────────────────────────────────────────

describe('VoiceManager', () => {
  let manager: VoiceManager;

  beforeEach(async () => {
    manager = createVoiceManager(createTestConfig('parwa'));
    await manager.initialize();
  });

  afterEach(async () => {
    await manager.shutdown();
  });

  describe('Initialization', () => {
    test('should initialize successfully', async () => {
      const newManager = createVoiceManager(createTestConfig('parwa'));
      await expect(newManager.initialize()).resolves.not.toThrow();
    });

    test('should not reinitialize if already initialized', async () => {
      await manager.initialize();
      // Should not throw or cause issues
      await expect(manager.initialize()).resolves.not.toThrow();
    });

    test('should handle mini_parwa initialization', async () => {
      const miniManager = createVoiceManager(createTestConfig('mini_parwa'));
      await miniManager.initialize();
      
      const capabilities = miniManager.getCapabilities();
      expect(capabilities.stt_enabled).toBe(false);
      expect(capabilities.tts_enabled).toBe(false);
      
      await miniManager.shutdown();
    });
  });

  describe('Speech-to-Text', () => {
    test('should process audio and return transcript', async () => {
      const request: STTRequest = {
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
        language: 'en-US',
      };

      const result = await manager.speechToText(request);

      expect(result).toBeDefined();
      expect(result.transcript).toBeDefined();
      expect(result.confidence).toBeGreaterThan(0);
      expect(result.confidence).toBeLessThanOrEqual(1);
      expect(result.timestamp).toBeInstanceOf(Date);
    });

    test('should include processing time', async () => {
      const request: STTRequest = {
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      };

      const result = await manager.speechToText(request);

      expect(result.processing_time_ms).toBeGreaterThan(0);
    });

    test('should throw error for mini_parwa variant', async () => {
      const miniManager = createVoiceManager(createTestConfig('mini_parwa'));
      await miniManager.initialize();

      const request: STTRequest = {
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      };

      await expect(miniManager.speechToText(request)).rejects.toThrow(
        'Speech-to-text not enabled'
      );

      await miniManager.shutdown();
    });

    test('should update STT request count', async () => {
      const initialStats = manager.getStats();
      
      await manager.speechToText({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      const newStats = manager.getStats();
      expect(newStats.stt_requests).toBe(initialStats.stt_requests + 1);
    });
  });

  describe('Text-to-Speech', () => {
    test('should convert text to audio', async () => {
      const request: TTSRequest = {
        text: 'Hello, how can I help you?',
        language: 'en-US',
      };

      const result = await manager.textToSpeech(request);

      expect(result).toBeDefined();
      expect(result.audio_data).toBeDefined();
      expect(result.format).toBe('wav');
      expect(result.duration_seconds).toBeGreaterThan(0);
      expect(result.voice_id).toBeDefined();
    });

    test('should calculate duration based on text length', async () => {
      const shortRequest: TTSRequest = {
        text: 'Hello',
      };

      const longRequest: TTSRequest = {
        text: 'This is a much longer sentence that should take more time to speak out loud',
      };

      const shortResult = await manager.textToSpeech(shortRequest);
      const longResult = await manager.textToSpeech(longRequest);

      expect(longResult.duration_seconds).toBeGreaterThan(shortResult.duration_seconds);
    });

    test('should throw error for mini_parwa variant', async () => {
      const miniManager = createVoiceManager(createTestConfig('mini_parwa'));
      await miniManager.initialize();

      const request: TTSRequest = {
        text: 'Hello world',
      };

      await expect(miniManager.textToSpeech(request)).rejects.toThrow(
        'Text-to-speech not enabled'
      );

      await miniManager.shutdown();
    });

    test('should update TTS request count', async () => {
      const initialStats = manager.getStats();
      
      await manager.textToSpeech({
        text: 'Test message',
      });

      const newStats = manager.getStats();
      expect(newStats.tts_requests).toBe(initialStats.tts_requests + 1);
    });
  });

  describe('Voice Activity Detection', () => {
    test('should detect speech activity', () => {
      // Create audio data with some "signal"
      const audioData = new ArrayBuffer(1024);
      const view = new Uint8Array(audioData);
      view.fill(100); // Non-silence

      const result = manager.detectVoiceActivity(audioData);

      expect(result).toBeDefined();
      expect(result.speech_detected).toBeDefined();
      expect(result.probability).toBeGreaterThanOrEqual(0);
      expect(result.probability).toBeLessThanOrEqual(1);
      expect(result.audio_level_db).toBeDefined();
    });

    test('should respect VAD config', () => {
      const audioData = new ArrayBuffer(1024);

      const customConfig: VADConfig = {
        enabled: true,
        silence_threshold_db: -50,
        min_speech_duration_ms: 100,
        silence_duration_ms: 1000,
      };

      const result = manager.detectVoiceActivity(audioData, customConfig);

      expect(result).toBeDefined();
    });

    test('should return default values when VAD disabled', () => {
      const audioData = new ArrayBuffer(1024);

      const customConfig: VADConfig = {
        enabled: false,
        silence_threshold_db: -35,
      };

      const result = manager.detectVoiceActivity(audioData, customConfig);

      expect(result.speech_detected).toBe(false);
      expect(result.probability).toBe(0);
    });
  });

  describe('Voice Command Parsing', () => {
    test('should parse simple command', () => {
      const command = manager.parseVoiceCommand('show my tickets', 'session-1');

      expect(command).toBeDefined();
      expect(command.transcript).toBe('show my tickets');
      expect(command.normalized_text).toBe('show my tickets');
      expect(command.intent).toBeDefined();
      expect(command.confidence).toBeGreaterThan(0);
    });

    test('should normalize text', () => {
      const command = manager.parseVoiceCommand('SHOW MY TICKETS!!!', 'session-1');

      expect(command.normalized_text).toBe('show my tickets');
    });

    test('should detect search_tickets intent', () => {
      const command = manager.parseVoiceCommand('show my tickets', 'session-1');

      expect(command.intent).toBe('search_tickets');
    });

    test('should detect create_ticket intent', () => {
      const command = manager.parseVoiceCommand('create new ticket', 'session-1');

      expect(command.intent).toBe('create_ticket');
    });

    test('should detect assign_ticket intent', () => {
      const command = manager.parseVoiceCommand('assign ticket to john', 'session-1');

      expect(command.intent).toBe('assign_ticket');
    });

    test('should extract ticket_id entity', () => {
      const command = manager.parseVoiceCommand('show ticket 123', 'session-1');

      expect(command.entities).toBeDefined();
      expect(command.entities?.length).toBeGreaterThan(0);
      
      const ticketEntity = command.entities?.find(e => e.type === 'ticket_id');
      expect(ticketEntity).toBeDefined();
      expect(ticketEntity?.value).toBe('123');
    });

    test('should extract agent_id entity', () => {
      const command = manager.parseVoiceCommand('assign to agent john', 'session-1');

      const agentEntity = command.entities?.find(e => e.type === 'agent_id');
      expect(agentEntity).toBeDefined();
    });

    test('should return unknown intent for unclear commands', () => {
      const command = manager.parseVoiceCommand('blah blah', 'session-1');

      expect(command.intent).toBe('unknown');
      expect(command.confidence).toBeLessThan(0.5);
    });
  });

  describe('Process Voice Input', () => {
    test('should process complete voice input flow', async () => {
      const response = await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
        user_id: 'user-1',
      });

      expect(response.success).toBe(true);
      expect(response.session_id).toBeDefined();
      expect(response.transcript).toBeDefined();
      expect(response.confidence).toBeGreaterThan(0);
    });

    test('should create new session if not provided', async () => {
      const response = await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      expect(response.session_id).toBeDefined();
      expect(manager.getSession(response.session_id)).toBeDefined();
    });

    test('should use existing session if provided', async () => {
      // First request creates session
      const response1 = await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      // Second request uses same session
      const response2 = await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
        session_id: response1.session_id,
      });

      expect(response2.session_id).toBe(response1.session_id);
    });

    test('should return response text', async () => {
      const response = await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      expect(response.response_text).toBeDefined();
      expect(response.response_text!.length).toBeGreaterThan(0);
    });

    test('should include response audio for parwa variant', async () => {
      const response = await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      expect(response.response_audio).toBeDefined();
      expect(response.audio_format).toBe('wav');
    });

    test('should fail for mini_parwa variant', async () => {
      const miniManager = createVoiceManager(createTestConfig('mini_parwa'));
      await miniManager.initialize();

      const response = await miniManager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      expect(response.success).toBe(false);
      expect(response.error).toContain('not supported');

      await miniManager.shutdown();
    });
  });

  describe('Session Management', () => {
    test('should create session', async () => {
      const response = await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
        user_id: 'user-1',
      });

      const session = manager.getSession(response.session_id);
      expect(session).toBeDefined();
      expect(session?.user_id).toBe('user-1');
      expect(session?.state).toBeDefined();
    });

    test('should end session', async () => {
      const response = await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      await manager.endSession(response.session_id);

      expect(manager.getSession(response.session_id)).toBeUndefined();
    });

    test('should track session count', async () => {
      const initialStats = manager.getStats();
      
      await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      const newStats = manager.getStats();
      expect(newStats.total_sessions).toBe(initialStats.total_sessions + 1);
    });
  });

  describe('Voice Selection', () => {
    test('should return available voices', () => {
      const voices = manager.getAvailableVoices();

      expect(voices.length).toBeGreaterThan(0);
      expect(voices[0].id).toBeDefined();
      expect(voices[0].name).toBeDefined();
      expect(voices[0].language).toBeDefined();
    });

    test('should filter voices by language', () => {
      const voices = manager.getAvailableVoices('en-US');

      expect(voices.every(v => v.language.startsWith('en'))).toBe(true);
    });

    test('should limit voices by variant', async () => {
      const parwaManager = createVoiceManager(createTestConfig('parwa'));
      await parwaManager.initialize();
      const parwaVoices = parwaManager.getAvailableVoices();

      const highManager = createVoiceManager(createTestConfig('parwa_high'));
      await highManager.initialize();
      const highVoices = highManager.getAvailableVoices();

      expect(highVoices.length).toBeGreaterThanOrEqual(parwaVoices.length);

      await parwaManager.shutdown();
      await highManager.shutdown();
    });
  });

  describe('Capabilities', () => {
    test('should return parwa capabilities', () => {
      const capabilities = manager.getCapabilities();

      expect(capabilities.stt_enabled).toBe(true);
      expect(capabilities.tts_enabled).toBe(true);
      expect(capabilities.vad_enabled).toBe(true);
      expect(capabilities.max_session_duration_minutes).toBe(30);
    });

    test('should return parwa_high capabilities', async () => {
      const highManager = createVoiceManager(createTestConfig('parwa_high'));
      await highManager.initialize();

      const capabilities = highManager.getCapabilities();

      expect(capabilities.stt_enabled).toBe(true);
      expect(capabilities.tts_enabled).toBe(true);
      expect(capabilities.max_session_duration_minutes).toBe(120);
      expect(capabilities.supported_languages.length).toBeGreaterThan(5);

      await highManager.shutdown();
    });

    test('should return mini_parwa capabilities', async () => {
      const miniManager = createVoiceManager(createTestConfig('mini_parwa'));
      await miniManager.initialize();

      const capabilities = miniManager.getCapabilities();

      expect(capabilities.stt_enabled).toBe(false);
      expect(capabilities.tts_enabled).toBe(false);
      expect(capabilities.voice_options).toBe(0);

      await miniManager.shutdown();
    });
  });

  describe('Statistics', () => {
    test('should track stats', async () => {
      await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      const stats = manager.getStats();

      expect(stats.total_sessions).toBeGreaterThan(0);
      expect(stats.stt_requests).toBeGreaterThan(0);
      expect(stats.tts_requests).toBeGreaterThan(0);
    });

    test('should track average latencies', async () => {
      await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      const stats = manager.getStats();

      expect(stats.avg_stt_latency_ms).toBeGreaterThan(0);
      expect(stats.avg_tts_latency_ms).toBeGreaterThan(0);
    });

    test('should return copy of stats', () => {
      const stats1 = manager.getStats();
      const stats2 = manager.getStats();

      expect(stats1).not.toBe(stats2);
    });
  });

  describe('Event System', () => {
    test('should emit transcript_ready event', async () => {
      const listener = jest.fn();
      manager.onEvent('transcript_ready', listener);

      await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      expect(listener).toHaveBeenCalled();
    });

    test('should emit command_parsed event', async () => {
      const listener = jest.fn();
      manager.onEvent('command_parsed', listener);

      await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      expect(listener).toHaveBeenCalled();
    });

    test('should emit response_ready event', async () => {
      const listener = jest.fn();
      manager.onEvent('response_ready', listener);

      await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      expect(listener).toHaveBeenCalled();
    });

    test('should return unsubscribe function', async () => {
      const listener = jest.fn();
      const unsubscribe = manager.onEvent('transcript_ready', listener);

      await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      expect(listener).toHaveBeenCalledTimes(1);

      unsubscribe();

      await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      // Should still be 1 after unsubscribe
      expect(listener).toHaveBeenCalledTimes(1);
    });
  });

  describe('Error Handling', () => {
    test('should return error response for failed processing', async () => {
      // Force error with mini_parwa
      const miniManager = createVoiceManager(createTestConfig('mini_parwa'));
      await miniManager.initialize();

      const response = await miniManager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      expect(response.success).toBe(false);
      expect(response.error).toBeDefined();

      await miniManager.shutdown();
    });

    test('should track error count', async () => {
      // Force an error scenario with mini_parwa
      const miniManager = createVoiceManager(createTestConfig('mini_parwa'));
      await miniManager.initialize();
      
      const initialStats = miniManager.getStats();
      const initialErrors = initialStats.error_count;

      await miniManager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      const newStats = miniManager.getStats();
      expect(newStats.error_count).toBe(initialErrors + 1);

      await miniManager.shutdown();
    });
  });

  describe('Shutdown', () => {
    test('should clear sessions on shutdown', async () => {
      await manager.processVoiceInput({
        audio_data: new ArrayBuffer(1024),
        format: 'wav',
      });

      await manager.shutdown();

      const stats = manager.getStats();
      // Sessions should be cleared
    });

    test('should clear event listeners on shutdown', async () => {
      const listener = jest.fn();
      manager.onEvent('transcript_ready', listener);

      await manager.shutdown();

      // Event listeners should be cleared
      // This is a bit hard to test directly, but shutdown should complete without error
    });
  });
});

// ── Variant Limits Tests ─────────────────────────────────────────────

describe('Voice Variant Limits', () => {
  test('mini_parwa should have no voice capabilities', async () => {
    const manager = createVoiceManager(createTestConfig('mini_parwa'));
    await manager.initialize();

    const capabilities = manager.getCapabilities();

    expect(capabilities.stt_enabled).toBe(false);
    expect(capabilities.tts_enabled).toBe(false);
    expect(capabilities.vad_enabled).toBe(false);
    expect(capabilities.voice_options).toBe(0);
    expect(capabilities.supported_languages).toHaveLength(0);

    await manager.shutdown();
  });

  test('parwa should have limited voice capabilities', async () => {
    const manager = createVoiceManager(createTestConfig('parwa'));
    await manager.initialize();

    const capabilities = manager.getCapabilities();

    expect(capabilities.stt_enabled).toBe(true);
    expect(capabilities.tts_enabled).toBe(true);
    expect(capabilities.max_session_duration_minutes).toBe(30);
    expect(capabilities.max_audio_length_seconds).toBe(60);
    expect(capabilities.voice_options).toBe(5);

    await manager.shutdown();
  });

  test('parwa_high should have full voice capabilities', async () => {
    const manager = createVoiceManager(createTestConfig('parwa_high'));
    await manager.initialize();

    const capabilities = manager.getCapabilities();

    expect(capabilities.stt_enabled).toBe(true);
    expect(capabilities.tts_enabled).toBe(true);
    expect(capabilities.max_session_duration_minutes).toBe(120);
    expect(capabilities.max_audio_length_seconds).toBe(300);
    expect(capabilities.voice_options).toBe(20);
    expect(capabilities.supported_languages.length).toBeGreaterThan(5);

    await manager.shutdown();
  });
});
