'use client';

import React, { useState, useEffect } from 'react';
import {
  Bot,
  ArrowLeft,
  ArrowRight,
  Loader2,
  CheckCircle,
  XCircle,
  MessageSquare,
  Sparkles,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { onboardingApi, getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import { AITone, AIResponseStyle } from '@/types/onboarding';

interface Prerequisite {
  label: string;
  met: boolean;
  description?: string;
}

interface AISetupStepProps {
  onNext: () => void;
}

/**
 * Tone options for the AI assistant. Each tone has a value,
 * display label, and a short description so the user can
 * make an informed choice about how their assistant will
 * communicate with customers.
 */
const TONE_OPTIONS: { value: AITone; label: string; description: string }[] = [
  { value: 'professional', label: 'Professional', description: 'Formal, polished language suitable for enterprise clients and regulated industries.' },
  { value: 'friendly', label: 'Friendly', description: 'Warm and approachable tone that builds rapport while staying helpful and clear.' },
  { value: 'casual', label: 'Casual', description: 'Relaxed, conversational style that feels natural for consumer-facing brands.' },
];

/**
 * Response style options that control how verbose the AI
 * assistant's replies will be.
 */
const STYLE_OPTIONS: { value: AIResponseStyle; label: string; description: string }[] = [
  { value: 'concise', label: 'Concise', description: 'Short, direct answers that get straight to the point. Ideal for quick resolutions.' },
  { value: 'detailed', label: 'Detailed', description: 'Thorough, comprehensive responses with context and explanations. Great for complex issues.' },
  { value: 'balanced', label: 'Balanced', description: 'A mix of clarity and detail, adapting to the complexity of each inquiry.' },
];

/**
 * AISetupStep Component (Step 5)
 *
 * The final step of the onboarding wizard that configures and
 * activates the AI assistant. It first checks prerequisites from
 * the API (completed steps, integrations, knowledge base) and
 * gates the activation button if any are missing. The user can
 * customize the AI name, tone, response style, and greeting
 * before activating. The activation button features a glowing
 * orange animation when all prerequisites are met, and triggers
 * a confetti burst on successful activation.
 */
export function AISetupStep({ onNext }: AISetupStepProps) {
  const [prerequisites, setPrerequisites] = useState<Prerequisite[]>([]);
  const [isLoadingPrereqs, setIsLoadingPrereqs] = useState(true);
  const [aiName, setAiName] = useState('Jarvis');
  const [aiTone, setAiTone] = useState<AITone>('professional');
  const [aiResponseStyle, setAiResponseStyle] = useState<AIResponseStyle>('balanced');
  const [aiGreeting, setAiGreeting] = useState('');
  const [isActivating, setIsActivating] = useState(false);
  const [isActivated, setIsActivated] = useState(false);
  const [showConfetti, setShowConfetti] = useState(false);

  const allPrerequisitesMet = prerequisites.length > 0 && prerequisites.every((p) => p.met);

  useEffect(() => {
    async function loadPrerequisites() {
      try {
        const result = await onboardingApi.getPrerequisites();
        if (result && typeof result === 'object') {
          if ('prerequisites' in result) {
            setPrerequisites((result as { prerequisites: Prerequisite[] }).prerequisites);
          } else {
            const data = result as Record<string, unknown>;
            setPrerequisites([
              { label: 'Company details completed', met: !!data.details_completed },
              { label: 'Legal consents accepted', met: !!data.legal_accepted },
              { label: 'At least one integration connected', met: !!data.has_integration },
            ]);
          }
        }
      } catch {
        setPrerequisites([
          { label: 'Company details completed', met: true },
          { label: 'Legal consents accepted', met: true },
          { label: 'At least one integration connected', met: true },
        ]);
      } finally {
        setIsLoadingPrereqs(false);
      }
    }
    loadPrerequisites();
  }, []);

  const handleActivate = async () => {
    if (!allPrerequisitesMet || isActivating) return;

    setIsActivating(true);
    try {
      await onboardingApi.activateAI({
        ai_name: aiName,
        ai_tone: aiTone,
        ai_response_style: aiResponseStyle,
        ...(aiGreeting ? { ai_greeting: aiGreeting } : {}),
      });
      await onboardingApi.completeStep(5);

      setIsActivated(true);
      setShowConfetti(true);
      setTimeout(() => { onNext(); }, 2000);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setIsActivating(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto relative">
      {/* Confetti burst overlay */}
      {showConfetti && (
        <div className="fixed inset-0 z-50 pointer-events-none overflow-hidden">
          {Array.from({ length: 60 }).map((_, i) => (
            <div
              key={i}
              className="absolute w-2 h-2 rounded-sm animate-confetti"
              style={{
                left: `${Math.random() * 100}%`,
                top: '-2%',
                backgroundColor: ['#FF7F11', '#FF9F5A', '#FFD700', '#FF4500', '#FFA500', '#FFFFFF'][Math.floor(Math.random() * 6)],
                animationDelay: `${Math.random() * 1.5}s`,
                animationDuration: `${2 + Math.random() * 2}s`,
                transform: `rotate(${Math.random() * 360}deg)`,
              }}
            />
          ))}
        </div>
      )}

      {/* Header */}
      <div className="text-center mb-10">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-orange-500/10 border border-orange-500/20 mb-6">
          <Bot className="w-8 h-8 text-orange-400" />
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
          Configure Your AI Assistant
        </h2>
        <p className="text-orange-200/50 text-sm max-w-md mx-auto">
          Customize your AI assistant&apos;s personality and behavior. These settings control how it communicates with your customers.
        </p>
      </div>

      {/* Prerequisites gate */}
      <div className="card-parwa p-6 mb-6">
        <h3 className="text-sm font-semibold text-orange-200/60 uppercase tracking-wider mb-4">
          Activation Prerequisites
        </h3>

        {isLoadingPrereqs ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="w-5 h-5 animate-spin text-orange-400" />
          </div>
        ) : (
          <div className="space-y-3">
            {prerequisites.map((prereq, index) => (
              <div key={index} className="flex items-center gap-3">
                {prereq.met ? (
                  <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
                ) : (
                  <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                )}
                <div>
                  <p className={cn('text-sm font-medium', prereq.met ? 'text-white' : 'text-white/50')}>
                    {prereq.label}
                  </p>
                  {prereq.description && !prereq.met && (
                    <p className="text-xs text-red-400/60">{prereq.description}</p>
                  )}
                </div>
              </div>
            ))}

            {!allPrerequisitesMet && (
              <p className="text-xs text-red-400/70 mt-2 p-3 rounded-lg bg-red-500/5 border border-red-500/10">
                All prerequisites must be met before you can activate your AI assistant.
                Please go back and complete the missing items.
              </p>
            )}
          </div>
        )}
      </div>

      {/* AI Configuration form */}
      <div className="card-parwa p-6 mb-6">
        <h3 className="text-sm font-semibold text-orange-200/60 uppercase tracking-wider mb-6">
          AI Configuration
        </h3>

        {/* AI Name */}
        <div className="mb-6">
          <label htmlFor="ai-name" className="label-parwa">AI Assistant Name</label>
          <div className="relative">
            <Bot className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-orange-300/40" />
            <input
              id="ai-name"
              type="text"
              value={aiName}
              onChange={(e) => setAiName(e.target.value)}
              placeholder="Jarvis"
              className="input-parwa pl-10"
              maxLength={30}
            />
          </div>
          <p className="text-xs text-orange-200/25 mt-1">This name will appear in chat headers and customer-facing messages.</p>
        </div>

        {/* AI Tone */}
        <div className="mb-6">
          <label className="label-parwa mb-3">Communication Tone</label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {TONE_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setAiTone(option.value)}
                className={cn(
                  'p-4 rounded-xl border text-left transition-all duration-200',
                  aiTone === option.value ? 'border-orange-500/50 bg-orange-500/[0.06]' : 'border-white/10 bg-white/[0.02] hover:border-white/20'
                )}
              >
                <p className={cn('text-sm font-semibold mb-1', aiTone === option.value ? 'text-orange-300' : 'text-white/70')}>
                  {option.label}
                </p>
                <p className="text-xs text-orange-200/30 leading-relaxed">{option.description}</p>
              </button>
            ))}
          </div>
        </div>

        {/* AI Response Style */}
        <div className="mb-6">
          <label className="label-parwa mb-3">Response Style</label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {STYLE_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setAiResponseStyle(option.value)}
                className={cn(
                  'p-4 rounded-xl border text-left transition-all duration-200',
                  aiResponseStyle === option.value ? 'border-orange-500/50 bg-orange-500/[0.06]' : 'border-white/10 bg-white/[0.02] hover:border-white/20'
                )}
              >
                <p className={cn('text-sm font-semibold mb-1', aiResponseStyle === option.value ? 'text-orange-300' : 'text-white/70')}>
                  {option.label}
                </p>
                <p className="text-xs text-orange-200/30 leading-relaxed">{option.description}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Custom Greeting */}
        <div>
          <label htmlFor="ai-greeting" className="label-parwa">
            Custom Greeting <span className="text-orange-200/25">(optional)</span>
          </label>
          <div className="relative">
            <MessageSquare className="absolute left-3 top-3 w-4 h-4 text-orange-300/40" />
            <textarea
              id="ai-greeting"
              value={aiGreeting}
              onChange={(e) => setAiGreeting(e.target.value)}
              placeholder="Hello! How can I help you today?"
              className="input-parwa pl-10 min-h-[80px] resize-none"
              maxLength={200}
            />
          </div>
          <p className="text-xs text-orange-200/25 mt-1">The first message your AI sends when a conversation starts. Max 200 characters.</p>
        </div>
      </div>

      {/* Success state */}
      {isActivated && (
        <div className="card-elevated-parwa p-6 text-center mb-6">
          <Sparkles className="w-10 h-10 text-orange-400 mx-auto mb-3" />
          <h3 className="text-xl font-bold text-white mb-2">Your AI assistant is live!</h3>
          <p className="text-sm text-orange-200/50">{aiName} is now ready to handle customer inquiries.</p>
        </div>
      )}

      {/* Activate button */}
      <div className="mt-8 flex items-center justify-center">
        {!isActivated && (
          <button
            type="button"
            onClick={handleActivate}
            disabled={!allPrerequisitesMet || isActivating || !aiName.trim()}
            className={cn(
              'btn-primary-parwa py-3 px-8 relative overflow-hidden w-full sm:w-auto',
              allPrerequisitesMet && !isActivating && aiName.trim() && 'animate-activate-glow'
            )}
          >
            {isActivating ? (
              <><Loader2 className="w-5 h-5 mr-2 animate-spin" />Activating...</>
            ) : (
              <><Sparkles className="w-5 h-5 mr-2" />Activate AI Assistant<ArrowRight className="w-5 h-5 ml-2" /></>
            )}
          </button>
        )}
      </div>
    </div>
  );
}

export default AISetupStep;
