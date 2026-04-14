'use client';

import React, { useState, useEffect } from 'react';
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
  { value: 'balanced', label: 'Balanced', description: 'Mix of brevity and detail' },
  { value: 'detailed', label: 'Detailed', description: 'Comprehensive, thorough explanations' },
];

interface AIConfigProps {
  onComplete: () => void;
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

  useEffect(() => {
    fetch('/api/onboarding/prerequisites')
      .then((res) => res.json())
      .then(setPrerequisites)
      .catch(() => {
        // Fallback: allow activation if prerequisites endpoint fails
        setPrerequisites({ can_activate: true, missing: [] });
      })
      .finally(() => setLoading(false));
  }, []);

  const handleActivate = async () => {
    setActivating(true);
    setError(null);

    try {
      const res = await fetch('/api/onboarding/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ai_name: aiName,
          ai_tone: aiTone,
          ai_response_style: aiStyle,
          ai_greeting: aiGreeting || undefined,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || data?.error?.message || 'Activation failed');
      }

      setActivated(true);
      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Activation failed');
    } finally {
      setActivating(false);
    }
  };

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

      {/* Prerequisites Warnings */}
      {prerequisites && !prerequisites.can_activate && (
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
          </AlertDescription>
        </Alert>
      )}

      <div className="flex justify-end">
        <Button
          onClick={handleActivate}
          disabled={activating || activated || (prerequisites && !prerequisites.can_activate)}
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
