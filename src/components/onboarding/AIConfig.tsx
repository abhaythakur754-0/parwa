'use client';

import React, { useState, useEffect } from 'react';
import { Loader2, Bot, CheckCircle2, Sparkles, Phone } from 'lucide-react';
import { toast } from '@/lib/dynamic-toast';
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
  const [phoneNumber, setPhoneNumber] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load any existing config on mount — don't block if backend is down
  useEffect(() => {
    async function loadConfig() {
      try {
        const res = await fetch('/api/onboarding/ai-config');
        if (res.ok) {
          const data = await res.json();
          if (data.ai_name) setAiName(data.ai_name);
          if (data.ai_tone) setAiTone(data.ai_tone as AITone);
          if (data.ai_response_style) setAiStyle(data.ai_response_style as AIResponseStyle);
          if (data.ai_greeting) setAiGreeting(data.ai_greeting);
          if (data.phone_number) setPhoneNumber(data.phone_number);
        }
        // If res not ok (503, etc.), just use defaults — don't show error
      } catch {
        // API unavailable — use defaults/initialConfig silently
      } finally {
        setLoading(false);
      }
    }
    loadConfig();
  }, []);

  const handleSave = async () => {
    if (!aiName.trim()) {
      setError('Please enter a name for your AI assistant');
      return;
    }

    setSaving(true);
    setError(null);

    // Save config to localStorage as fallback
    try {
      const localConfig = {
        ai_name: aiName.trim(),
        ai_tone: aiTone,
        ai_response_style: aiStyle,
        ai_greeting: aiGreeting.trim() || undefined,
        phone_number: phoneNumber.trim() || undefined,
      };
      localStorage.setItem('parwa_ai_config', JSON.stringify(localConfig));
    } catch { /* ignore */ }

    try {
      const res = await fetch('/api/onboarding/ai-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ai_name: aiName.trim(),
          ai_tone: aiTone,
          ai_response_style: aiStyle,
          ai_greeting: aiGreeting.trim() || undefined,
          phone_number: phoneNumber.trim() || undefined,
        }),
      });

      if (!res.ok) {
        // Backend returned error — config saved locally, continue
        console.warn('[AIConfig] Save returned non-ok, config saved locally');
      }

      setSaved(true);
      toast.success('AI configuration saved!');
      onComplete();
    } catch {
      // API unavailable — config already saved locally above
      console.warn('[AIConfig] Backend unreachable, config saved locally');
      setSaved(true);
      toast.success('AI configuration saved locally — will sync when server is available');
      onComplete();
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-orange-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
          <Bot className="w-7 h-7 text-violet-400" />
        </div>
        <h2 className="text-2xl font-bold text-white">Configure Your AI Assistant</h2>
        <p className="text-orange-200/40 text-sm">
          Customize your AI assistant&apos;s personality, communication style, and contact details
          to match your brand voice.
        </p>
      </div>

      {/* AI Name */}
      <div className="space-y-2">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider">Assistant Name</label>
        <input
          value={aiName}
          onChange={(e) => setAiName(e.target.value)}
          placeholder="Jarvis"
          maxLength={50}
          className="w-full px-3 py-2.5 rounded-lg text-sm bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:outline-none transition-colors"
        />
        <p className="text-[10px] text-orange-200/20">This is the name your customers will see.</p>
      </div>

      {/* Phone Number */}
      <div className="space-y-2">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider flex items-center gap-1.5">
          <Phone className="w-3 h-3" />
          Support Phone Number <span className="text-zinc-600">(optional)</span>
        </label>
        <input
          value={phoneNumber}
          onChange={(e) => setPhoneNumber(e.target.value)}
          placeholder="+1 (555) 123-4567"
          maxLength={20}
          type="tel"
          className="w-full px-3 py-2.5 rounded-lg text-sm bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:outline-none transition-colors"
        />
        <p className="text-[10px] text-orange-200/20">Used for voice channel and escalation. Include country code.</p>
      </div>

      {/* AI Tone */}
      <div className="space-y-3">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider">Communication Tone</label>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {TONE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setAiTone(opt.value)}
              className={`text-left p-3 rounded-xl border transition-all duration-200 ${
                aiTone === opt.value
                  ? 'border-orange-500/40 bg-orange-500/5'
                  : 'border-white/[0.06] hover:border-orange-500/20'
              }`}
              style={aiTone !== opt.value ? { background: 'rgba(255,255,255,0.03)' } : undefined}
            >
              <p className={`text-sm font-medium ${aiTone === opt.value ? 'text-orange-400' : 'text-white'}`}>{opt.label}</p>
              <p className="text-[10px] text-orange-200/30 mt-0.5">{opt.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Response Style */}
      <div className="space-y-3">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider">Response Style</label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {STYLE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setAiStyle(opt.value)}
              className={`text-left p-3 rounded-xl border transition-all duration-200 ${
                aiStyle === opt.value
                  ? 'border-orange-500/40 bg-orange-500/5'
                  : 'border-white/[0.06] hover:border-orange-500/20'
              }`}
              style={aiStyle !== opt.value ? { background: 'rgba(255,255,255,0.03)' } : undefined}
            >
              <p className={`text-sm font-medium ${aiStyle === opt.value ? 'text-orange-400' : 'text-white'}`}>{opt.label}</p>
              <p className="text-[10px] text-orange-200/30 mt-0.5">{opt.description}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Custom Greeting */}
      <div className="space-y-2">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider">Custom Greeting (Optional)</label>
        <input
          value={aiGreeting}
          onChange={(e) => setAiGreeting(e.target.value)}
          placeholder="Hi! I'm Jarvis, your AI assistant. How can I help you today?"
          maxLength={500}
          className="w-full px-3 py-2.5 rounded-lg text-sm bg-white/[0.04] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:outline-none transition-colors"
        />
        <p className="text-[10px] text-orange-200/20">The first message your customers see. Leave blank for default.</p>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          {error}
        </div>
      )}

      {saved && (
        <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          AI assistant configured successfully!
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving || saved}
          className="px-6 py-3 bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 disabled:from-zinc-700 disabled:to-zinc-700 text-[#1A1A1A] disabled:text-zinc-500 font-semibold rounded-xl transition-all duration-300 shadow-lg shadow-orange-500/25 disabled:shadow-none text-sm flex items-center gap-2"
        >
          {saving ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Saving...
            </>
          ) : saved ? (
            <>
              <CheckCircle2 className="w-4 h-4" />
              Saved
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Save & Continue
            </>
          )}
        </button>
      </div>
    </div>
  );
}
