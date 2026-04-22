'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Bot, CheckCircle2 } from 'lucide-react';
import type { AITone, AIResponseStyle } from '@/types/onboarding';
import { ActivationButton } from './ActivationButton';

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
  const [activated, setActivated] = useState(false);
  const [activationMessage, setActivationMessage] = useState<string | null>(null);

  // Build config object for ActivationButton
  const activationConfig = {
    ai_name: aiName,
    ai_tone: aiTone as 'professional' | 'friendly' | 'casual',
    ai_response_style: aiStyle as 'concise' | 'detailed',
    ai_greeting: aiGreeting || undefined,
  };

  // Determine if form fields should be disabled after activation
  const formDisabled = activated;

  const handleActivationComplete = (result: {
    success: boolean;
    warmup_required: boolean;
    message: string;
  }) => {
    if (result.success) {
      setActivated(true);
      setActivationMessage(result.message);

      // D8-4: Pass server-validated config back to wizard
      onComplete({
        ai_name: activationConfig.ai_name.trim(),
        ai_tone: activationConfig.ai_tone,
        ai_response_style: activationConfig.ai_response_style,
        ai_greeting: activationConfig.ai_greeting?.trim() || null,
      });
    }
  };

  const handleActivationError = (_error: string) => {
    // Error is displayed inline by ActivationButton — no additional action needed
  };

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

      {/* AI Name */}
      <div className="space-y-2">
        <Label htmlFor="ai-name">Assistant Name</Label>
        <Input
          id="ai-name"
          value={aiName}
          onChange={(e) => setAiName(e.target.value)}
          placeholder="Jarvis"
          maxLength={50}
          disabled={formDisabled}
          aria-describedby="ai-name-hint"
        />
        <p id="ai-name-hint" className="text-xs text-muted-foreground">
          This is the name your customers will see.
        </p>
      </div>

      {/* AI Tone */}
      <div className="space-y-3">
        <Label>Communication Tone</Label>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3" role="radiogroup" aria-label="Communication Tone">
          {TONE_OPTIONS.map((opt) => (
            <Card
              key={opt.value}
              className={`cursor-pointer transition-all ${
                aiTone === opt.value
                  ? 'border-primary ring-2 ring-primary/20'
                  : 'hover:border-primary/50'
              } ${formDisabled ? 'pointer-events-none opacity-60' : ''}`}
              onClick={() => !formDisabled && setAiTone(opt.value)}
              role="radio"
              aria-checked={aiTone === opt.value}
              aria-label={`${opt.label}: ${opt.description}`}
              tabIndex={formDisabled ? -1 : 0}
              onKeyDown={(e) => {
                if ((e.key === 'Enter' || e.key === ' ') && !formDisabled) {
                  e.preventDefault();
                  setAiTone(opt.value);
                }
              }}
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
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3" role="radiogroup" aria-label="Response Style">
          {STYLE_OPTIONS.map((opt) => (
            <Card
              key={opt.value}
              className={`cursor-pointer transition-all ${
                aiStyle === opt.value
                  ? 'border-primary ring-2 ring-primary/20'
                  : 'hover:border-primary/50'
              } ${formDisabled ? 'pointer-events-none opacity-60' : ''}`}
              onClick={() => !formDisabled && setAiStyle(opt.value)}
              role="radio"
              aria-checked={aiStyle === opt.value}
              aria-label={`${opt.label}: ${opt.description}`}
              tabIndex={formDisabled ? -1 : 0}
              onKeyDown={(e) => {
                if ((e.key === 'Enter' || e.key === ' ') && !formDisabled) {
                  e.preventDefault();
                  setAiStyle(opt.value);
                }
              }}
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
          disabled={formDisabled}
          aria-describedby="ai-greeting-hint"
        />
        <p id="ai-greeting-hint" className="text-xs text-muted-foreground">
          The first message your customers see. Leave blank for default.
        </p>
      </div>

      {/* Activation Success Message */}
      {activated && activationMessage && (
        <Alert className="bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800 animate-in fade-in duration-300">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800 dark:text-green-300">
            {activationMessage}
          </AlertDescription>
        </Alert>
      )}

      {/* Activation Button — handles prerequisites, activation, and warmup polling */}
      <ActivationButton
        config={activationConfig}
        onActivationComplete={handleActivationComplete}
        onActivationError={handleActivationError}
        disabled={formDisabled}
      />
    </div>
  );
}
