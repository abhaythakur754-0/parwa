'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { jarvisApi } from '@/lib/api';

import { getCurrentTenantId } from '@/lib/auth-context';

export default function VoiceCommandButton() {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [isSupported, setIsSupported] = useState(false);
  const [jarvisResponse, setJarvisResponse] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    // Check for Web Speech API support
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    setIsSupported(!!SpeechRecognition);
  }, []);

  const startListening = useCallback(() => {
    if (!isSupported) return;

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();

    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => setIsListening(true);

    recognition.onresult = (event: any) => {
      const text = event.results[0][0].transcript;
      setTranscript(text);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.onerror = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [isSupported]);

  const sendToJarvis = useCallback(async () => {
    if (!transcript.trim()) return;
    setIsProcessing(true);
    setJarvisResponse('');

    try {
      const data = await jarvisApi.chat(getCurrentTenantId(), transcript);
      const response = data?.chat_response || data?.response || JSON.stringify(data, null, 2);
      setJarvisResponse(response);
    } catch (err: any) {
      setJarvisResponse(`Error: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  }, [transcript]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
  }, []);

  if (!isSupported) {
    return null; // Don't render if voice not supported
  }

  return (
    <div className="jarvis-card">
      <div className="flex items-center gap-2 mb-2">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase">Voice Command</h3>
        <span className="text-[9px] text-jarvis-muted">(Wave 8E)</span>
      </div>

      {/* Microphone Button */}
      <div className="flex items-center gap-3 mb-3">
        <button
          onClick={isListening ? stopListening : startListening}
          className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
            isListening
              ? 'bg-jarvis-red animate-pulse shadow-[0_0_20px_rgba(255,0,0,0.3)]'
              : 'bg-jarvis-border/50 hover:bg-jarvis-cyan/20'
          }`}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={isListening ? 'text-jarvis-red' : 'text-jarvis-text'}>
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
        </button>
        <div>
          <p className="text-xs text-jarvis-text">
            {isListening ? 'Listening...' : 'Tap to speak'}
          </p>
          <p className="text-[9px] text-jarvis-muted">
            Say &quot;Jarvis&quot; then your command
          </p>
        </div>
      </div>

      {/* Transcript */}
      {transcript && (
        <div className="mb-2">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-jarvis-muted uppercase tracking-wider">You said:</span>
            <div className="flex gap-1">
              <button
                onClick={sendToJarvis}
                disabled={isProcessing}
                className="jarvis-btn-primary px-2 py-0.5 text-[10px] disabled:opacity-30"
              >
                {isProcessing ? '...' : 'SEND TO JARVIS'}
              </button>
              <button
                onClick={() => { setTranscript(''); setJarvisResponse(''); }}
                className="text-[10px] text-jarvis-muted hover:text-jarvis-text"
              >
                CLEAR
              </button>
            </div>
          </div>
          <div className="bg-jarvis-bg/50 rounded px-2 py-1.5 border border-jarvis-cyan/20">
            <p className="text-xs text-jarvis-cyan font-mono">{transcript}</p>
          </div>
        </div>
      )}

      {/* Response */}
      {jarvisResponse && (
        <div>
          <span className="text-[10px] text-jarvis-muted uppercase tracking-wider">Jarvis:</span>
          <div className="bg-jarvis-bg/50 rounded px-2 py-1.5 border border-jarvis-green/10 mt-1">
            <p className="text-xs text-jarvis-green font-mono whitespace-pre-wrap">{jarvisResponse}</p>
          </div>
        </div>
      )}
    </div>
  );
}
