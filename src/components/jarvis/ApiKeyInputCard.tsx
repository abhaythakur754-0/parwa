/**
 * PARWA ApiKeyInputCard (Integration Setup)
 *
 * Input card for API key with auto-detection, test connection, and connect flow.
 * States: idle → detecting → detected → testing → tested (success/error) → connecting → connected
 * Rendered inline in the Jarvis chat stream during onboarding.
 */

'use client';

import { useState, useCallback, useRef } from 'react';
import {
  Key, Eye, EyeOff, Loader2, CheckCircle2, XCircle,
  Sparkles, ArrowRight, SkipForward, AlertCircle,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────

export interface DetectionResult {
  providerType: string;
  providerName: string;
  icon?: string;
  confidence: number; // 0-1
}

export interface TestResult {
  success: boolean;
  message?: string;
  details?: Record<string, unknown>;
}

export interface ApiKeyInputCardProps {
  category: string;
  providerType?: string;  // pre-selected or auto-detected
  onDetect: (apiKey: string) => Promise<DetectionResult>;
  onTest: (credentials: Record<string, unknown>) => Promise<TestResult>;
  onConnect: (credentials: Record<string, unknown>) => void;
  onSkip: () => void;
}

type CardStage = 'idle' | 'detecting' | 'detected' | 'testing' | 'tested_ok' | 'tested_fail' | 'connecting' | 'connected';

// ── Component ──────────────────────────────────────────────────────

export function ApiKeyInputCard({
  category,
  providerType,
  onDetect,
  onTest,
  onConnect,
  onSkip,
}: ApiKeyInputCardProps) {
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [stage, setStage] = useState<CardStage>('idle');
  const [detection, setDetection] = useState<DetectionResult | null>(null);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-detect provider from API key pattern
  const handleDetect = useCallback(async () => {
    if (!apiKey.trim()) return;

    setStage('detecting');
    setError(null);
    setDetection(null);

    try {
      const result = await onDetect(apiKey.trim());
      setDetection(result);
      setStage('detected');
    } catch {
      setError('Could not detect provider from this key. You can still test the connection manually.');
      setStage('idle');
    }
  }, [apiKey, onDetect]);

  // Test connection
  const handleTest = useCallback(async () => {
    if (!apiKey.trim()) return;

    setStage('testing');
    setError(null);
    setTestResult(null);

    const credentials: Record<string, unknown> = {
      api_key: apiKey.trim(),
      category,
      provider_type: detection?.providerType || providerType || 'unknown',
    };

    try {
      const result = await onTest(credentials);
      setTestResult(result);
      setStage(result.success ? 'tested_ok' : 'tested_fail');
    } catch {
      setError('Connection test failed. Please check your API key and try again.');
      setTestResult({ success: false, message: 'Network error during test' });
      setStage('tested_fail');
    }
  }, [apiKey, category, detection, providerType, onTest]);

  // Connect
  const handleConnect = useCallback(() => {
    setStage('connecting');
    const credentials: Record<string, unknown> = {
      api_key: apiKey.trim(),
      category,
      provider_type: detection?.providerType || providerType || 'unknown',
    };
    onConnect(credentials);
  }, [apiKey, category, detection, providerType, onConnect]);

  // Connected state
  if (stage === 'connected') {
    return (
      <div className="glass rounded-xl p-4 border border-emerald-500/15 max-w-sm w-full">
        <div className="flex items-center gap-2 mb-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          <span className="text-sm font-medium text-emerald-200">Connected</span>
        </div>
        <p className="text-xs text-white/50">
          {detection?.providerName || providerType || 'Provider'} is now connected to your account.
        </p>
      </div>
    );
  }

  // Determine the display provider
  const effectiveProvider = detection?.providerName || providerType || 'Provider';

  return (
    <div className="glass rounded-xl p-4 border border-violet-500/15 max-w-sm w-full">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center">
          <Key className="w-4 h-4 text-violet-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Enter API Key</h3>
          <p className="text-[10px] text-white/40">
            {providerType ? `For ${effectiveProvider}` : `Auto-detect your ${category} provider`}
          </p>
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="flex items-start gap-1.5 mb-3 p-2 rounded-lg bg-red-500/10 border border-red-500/10">
          <AlertCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" />
          <p className="text-[11px] text-red-200">{error}</p>
        </div>
      )}

      {/* Detection result */}
      {detection && stage !== 'idle' && (
        <div className="flex items-center gap-2 mb-3 p-2 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
          <Sparkles className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-[11px] text-emerald-200 font-medium">
              Detected: {detection.providerName}
              {detection.icon && <span className="ml-1">{detection.icon}</span>}
            </p>
            <p className="text-[10px] text-white/30">
              Confidence: {Math.round(detection.confidence * 100)}%
            </p>
          </div>
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400/60 shrink-0" />
        </div>
      )}

      {/* Test result - success */}
      {testResult?.success && stage === 'tested_ok' && (
        <div className="flex items-center gap-2 mb-3 p-2 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <p className="text-[11px] text-emerald-200">
            {testResult.message || 'Connection successful!'}
          </p>
        </div>
      )}

      {/* Test result - failure */}
      {testResult && !testResult.success && stage === 'tested_fail' && (
        <div className="flex items-start gap-1.5 mb-3 p-2 rounded-lg bg-red-500/5 border border-red-500/10">
          <XCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" />
          <p className="text-[11px] text-red-200">
            {testResult.message || 'Connection test failed. Check your API key.'}
          </p>
        </div>
      )}

      {/* API Key input */}
      <div className="relative mb-2.5">
        <input
          ref={inputRef}
          type={showKey ? 'text' : 'password'}
          value={apiKey}
          onChange={(e) => { setApiKey(e.target.value); setError(null); }}
          placeholder="Paste your API key here..."
          className="w-full px-3 py-2.5 pr-10 rounded-lg bg-white/[0.05] border border-white/10 text-white text-sm font-mono placeholder:text-white/20 focus:outline-none focus:border-violet-500/30 focus:ring-1 focus:ring-violet-500/20 transition-all"
          disabled={stage === 'connecting'}
        />
        <button
          type="button"
          onClick={() => setShowKey(!showKey)}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
          aria-label={showKey ? 'Hide API key' : 'Show API key'}
        >
          {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>

      {/* Action buttons */}
      <div className="space-y-2">
        {/* Detect + Test row */}
        {!providerType && !detection && stage !== 'testing' && stage !== 'tested_ok' && (
          <button
            onClick={handleDetect}
            disabled={!apiKey.trim() || stage === 'detecting'}
            className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-white/[0.05] border border-white/10 text-white/60 text-xs font-medium hover:bg-white/[0.08] hover:text-white/80 disabled:opacity-30 transition-all"
          >
            {stage === 'detecting' ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Detecting...
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                Auto-detect Provider
              </>
            )}
          </button>
        )}

        {/* Test connection */}
        {stage !== 'testing' && stage !== 'tested_ok' && stage !== 'connecting' && (
          <button
            onClick={handleTest}
            disabled={!apiKey.trim() || stage === 'detecting'}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gradient-to-r from-violet-500 to-violet-600 text-white text-xs font-medium hover:from-violet-400 hover:to-violet-500 disabled:opacity-40 transition-all active:scale-[0.98]"
          >
            Test Connection
          </button>
        )}

        {/* Testing spinner */}
        {stage === 'testing' && (
          <div className="flex items-center justify-center py-3">
            <Loader2 className="w-4 h-4 animate-spin text-violet-400 mr-2" />
            <span className="text-xs text-white/50">Testing connection...</span>
          </div>
        )}

        {/* Connect button (after successful test) */}
        {(stage === 'tested_ok' || stage === 'connecting') && (
          <button
            onClick={handleConnect}
            disabled={stage === 'connecting'}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 text-white text-xs font-medium hover:from-emerald-400 hover:to-emerald-500 disabled:opacity-40 transition-all active:scale-[0.98]"
          >
            {stage === 'connecting' ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Connecting...
              </>
            ) : (
              <>
                Connect {effectiveProvider}
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        )}

        {/* Retry test (on failure) */}
        {stage === 'tested_fail' && (
          <button
            onClick={handleTest}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gradient-to-r from-violet-500 to-violet-600 text-white text-xs font-medium hover:from-violet-400 hover:to-violet-500 transition-all active:scale-[0.98]"
          >
            Try Again
          </button>
        )}
      </div>

      {/* Skip */}
      {!['connecting', 'connected'].includes(stage) && (
        <button
          onClick={onSkip}
          className="w-full flex items-center justify-center gap-1.5 text-[11px] text-white/35 hover:text-white/55 transition-colors py-1.5 mt-1"
        >
          <SkipForward className="w-3 h-3" />
          Skip for now
        </button>
      )}

      {/* Security note */}
      <p className="text-[10px] text-white/20 text-center mt-2">
        Your API key is encrypted and stored securely. We never share your credentials.
      </p>
    </div>
  );
}
