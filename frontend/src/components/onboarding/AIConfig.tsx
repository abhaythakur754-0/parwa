'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Bot, CheckCircle2, AlertTriangle, Sparkles } from 'lucide-react';
import type { AITone, AIResponseStyle } from '@/types/onboarding';

const TONE_OPTIONS: Array<{ value: AITone; label: string; description: string }> = [
  { value: 'professional', label: 'Professional', description: 'Formal, polished, business-appropriate' },
  { value: 'friendly', label: 'Friendly', description: 'Warm, approachable, conversational' },
  { value: 'casual', label: 'Casual', description: 'Relaxed, informal, personable' },
];

const STYLE_OPTIONS: Array<{ value: AIResponseStyle; label: string; description: string }> = [
  { value: 'concise', label: 'Concise', description: 'Short, direct answers' },
  { value: 'detailed', label: 'Detailed', description: 'Comprehensive, thorough explanations' },
];

interface AIConfigProps {
  // D8-4: onComplete now receives the server-validated AI config
  // so the wizard can pass it to FirstVictory
  onComplete: (config?: {
    ai_name: string;
    ai_tone: string;
    ai_response_style: string;
    ai_greeting: string | null;
  }) => void;
  initialConfig?: {
    ai_name?: string;
    ai_tone?: AITone;
    ai_response_style?: AIResponseStyle;
    ai_greeting?: string;
  };
}

export function AIConfig({ onComplete, initialConfig }: AIConfigProps) {
  const [aiName, setAiName] = useState(initialConfig?.ai_name || 'Jarvis');
  const [aiTone, setAiTone] = useState<AITone>(initialConfig?.ai_tone || 'professional');
  const [aiStyle, setAiStyle] = useState<AIResponseStyle>(
    (initialConfig?.ai_response_style as AIResponseStyle) || 'concise'
  );
  const [aiGreeting, setAiGreeting] = useState(initialConfig?.ai_greeting || '');
  const [prerequisites, setPrerequisites] = useState<{
    can_activate: boolean;
    missing: string[];
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [activating, setActivating] = useState(false);
  const [activated, setActivated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // P24: Warmup progress state
  const [warmupStatus, setWarmupStatus] = useState<{
    overall_status: string;
    models_ready: number;
    models_total: number;
    message: string;
  } | null>(null);
  const warmupPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [prereqError, setPrereqError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/onboarding/prerequisites')
      .then((res) => res.json())
      .then((data) => {
        if (data && typeof data.can_activate === 'boolean') {
          setPrerequisites(data);
        } else {
          // Malformed response — treat as unknown
          setPrerequisites({ can_activate: false, missing: ['Unable to verify prerequisites. Please refresh.'] });
        }
      })
      .catch(() => {
        // D7-3: On error, BLOCK activation instead of silently allowing it.
        // Previously this fell back to can_activate: true, which bypassed
        // all prerequisite checks if the backend was unreachable.
        setPrereqError('Could not reach server. Check your connection and refresh.');
        setPrerequisites({ can_activate: false, missing: ['Server unreachable — cannot verify prerequisites.'] });
      })
      .finally(() => setLoading(false));
  }, []);

  const handleActivate = async () => {
    // D7-4: Client-side validation before making network request
    const validationErrors: string[] = [];
    const trimmedName = aiName.trim();
    if (!trimmedName) {
      validationErrors.push('Assistant name is required.');
    } else if (trimmedName.length < 2) {
      validationErrors.push('Assistant name must be at least 2 characters.');
    }

    const validTones = ['professional', 'friendly', 'casual'];
    if (!validTones.includes(aiTone)) {
      validationErrors.push(`Invalid tone: ${aiTone}.`);
    }

    const validStyles = ['concise', 'detailed'];
    if (!validStyles.includes(aiStyle)) {
      validationErrors.push(`Invalid response style: ${aiStyle}.`);
    }

    if (aiGreeting && aiGreeting.length > 500) {
      validationErrors.push('Greeting must be 500 characters or fewer.');
    }

    if (validationErrors.length > 0) {
      setError(validationErrors.join(' '));
      return;
    }

    setActivating(true);
    setError(null);

    try {
      const res = await fetch('/api/onboarding/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ai_name: trimmedName,
          ai_tone: aiTone,
          ai_response_style: aiStyle,
          ai_greeting: aiGreeting.trim() || undefined,
        }),
      });

      const responseData = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(responseData?.detail || responseData?.error?.message || 'Activation failed');
      }
      setActivated(true);
      // D8-4: Pass server-validated config back to wizard
      onComplete({
        ai_name: responseData.ai_name || trimmedName,
        ai_tone: responseData.ai_tone || aiTone,
        ai_response_style: responseData.ai_response_style || aiStyle,
        ai_greeting: responseData.ai_greeting || null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Activation failed');
    } finally {
      setActivating(false);
    }
  };

  // P24 FIX: Poll warmup status after activation completes.
  // Shows the user real-time progress as models warm up.
  // D8-P7 FIX: Use exponential backoff (2s → 3s → 5s max) instead of
  // hardcoded 3s, reducing unnecessary polling as warmup progresses.
  useEffect(() => {
    if (!activated) return;

    let pollCount = 0;
    const MAX_POLL_INTERVAL = 5000;
    const INITIAL_POLL_INTERVAL = 2000;

    const pollWarmup = async () => {
      if (!warmupPollRef.current) return; // cancelled
      try {
        const res = await fetch('/api/onboarding/warmup-status');
        if (res.ok) {
          const data = await res.json();
          setWarmupStatus(data);
          // Stop polling once fully warm
          if (data.overall_status === 'warm') {
            if (warmupPollRef.current) {
              clearInterval(warmupPollRef.current);
              warmupPollRef.current = null;
            }
          }
        }
      } catch {
        // Best effort — don't block the user
      }
      pollCount++;
      // D8-P7: Increase interval with each poll (exponential backoff)
      if (warmupPollRef.current) {
        const nextInterval = Math.min(
          INITIAL_POLL_INTERVAL * Math.pow(1.5, pollCount),
          MAX_POLL_INTERVAL
        );
        clearInterval(warmupPollRef.current);
        warmupPollRef.current = setInterval(pollWarmup, nextInterval);
      }
    };

    // Poll immediately
    pollWarmup();
    warmupPollRef.current = setInterval(pollWarmup, INITIAL_POLL_INTERVAL);

    return () => {
      if (warmupPollRef.current) {
        clearInterval(warmupPollRef.current);
        warmupPollRef.current = null;
      }
    };
  }, [activated]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <Bot className="h-12 w-12 mx-auto text-violet-600" />
        <h2 className="text-2xl font-bold">Configure Your AI Assistant</h2>
        <p className="text-muted-foreground">
          Customize your AI assistant&apos;s personality and communication style
          to match your brand voice.
        </p>
      </div>

      {/* Prerequisites fetch error */}
      {prereqError && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{prereqError}</AlertDescription>
        </Alert>
      )}

      {/* Prerequisites Warnings */}
      {prerequisites && !prerequisites.can_activate && !prereqError && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            <p className="font-medium">Complete these before activating:</p>
            <ul className="list-disc ml-4 mt-1">
              {prerequisites.missing.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* AI Name */}
      <div className="space-y-2">
        <Label htmlFor="ai-name">Assistant Name</Label>
        <Input
          id="ai-name"
          value={aiName}
          onChange={(e) => setAiName(e.target.value)}
          placeholder="Jarvis"
          maxLength={50}
        />
        <p className="text-xs text-muted-foreground">
          This is the name your customers will see.
        </p>
      </div>

      {/* AI Tone */}
      <div className="space-y-3">
        <Label>Communication Tone</Label>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {TONE_OPTIONS.map((opt) => (
            <Card
              key={opt.value}
              className={`cursor-pointer transition-all ${
                aiTone === opt.value
                  ? 'border-primary ring-2 ring-primary/20'
                  : 'hover:border-primary/50'
              }`}
              onClick={() => setAiTone(opt.value)}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{opt.label}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-xs">{opt.description}</CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Response Style */}
      <div className="space-y-3">
        <Label>Response Style</Label>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {STYLE_OPTIONS.map((opt) => (
            <Card
              key={opt.value}
              className={`cursor-pointer transition-all ${
                aiStyle === opt.value
                  ? 'border-primary ring-2 ring-primary/20'
                  : 'hover:border-primary/50'
              }`}
              onClick={() => setAiStyle(opt.value)}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{opt.label}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-xs">{opt.description}</CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Custom Greeting */}
      <div className="space-y-2">
        <Label htmlFor="ai-greeting">Custom Greeting (Optional)</Label>
        <Input
          id="ai-greeting"
          value={aiGreeting}
          onChange={(e) => setAiGreeting(e.target.value)}
          placeholder="Hi! I'm Jarvis, your AI assistant. How can I help you today?"
          maxLength={500}
        />
        <p className="text-xs text-muted-foreground">
          The first message your customers see. Leave blank for default.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {activated && (
        <Alert className="bg-green-50 border-green-200">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">
            AI assistant activated successfully!
            {warmupStatus && warmupStatus.overall_status !== 'warm' && (
              <span className="ml-2 text-green-600">
                ({warmupStatus.message || 'Preparing AI models...'})
              </span>
            )}
            {warmupStatus && warmupStatus.overall_status === 'warm' && (
              <span className="ml-2 text-green-600">
                (All models ready — fully operational!)
              </span>
            )}
          </AlertDescription>
        </Alert>
      )}

      <div className="flex justify-end">
        <Button
          onClick={handleActivate}
          disabled={activating || activated || !prerequisites?.can_activate || !!prereqError}
          size="lg"
        >
          {activating ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Activating...
            </>
          ) : activated ? (
            <>
              <CheckCircle2 className="mr-2 h-4 w-4" />
              Activated
            </>
          ) : (
            <>
              <Sparkles className="mr-2 h-4 w-4" />
              Activate AI Assistant
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
