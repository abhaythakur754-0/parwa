'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ProgressIndicator } from './ProgressIndicator';
import { LegalCompliance } from './LegalCompliance';
import { IntegrationStep } from './IntegrationStep';
import { KnowledgeUpload } from './KnowledgeUpload';
import { AIConfig } from './AIConfig';
import { FirstVictory } from './FirstVictory';
import { Loader2, ArrowLeft, LogOut } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import Link from 'next/link';
import type { OnboardingState } from '@/types/onboarding';

interface OnboardingWizardProps {
  initialState?: OnboardingState;
}

export function OnboardingWizard({ initialState }: OnboardingWizardProps) {
  const [currentStep, setCurrentStep] = useState(1);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [onboardingState, setOnboardingState] = useState<OnboardingState | null>(null);
  const [aiName, setAiName] = useState('Jarvis');
  const [aiGreeting, setAiGreeting] = useState<string | null>(null);

  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, logout } = useAuth();

  // Fetch initial state
  useEffect(() => {
    fetch('/api/onboarding/state')
      .then((res) => res.json())
      .then((data) => {
        setOnboardingState(data);
        if (data.current_step > 1) setCurrentStep(data.current_step);
        if (data.completed_steps) setCompletedSteps(data.completed_steps);
        if (data.ai_name) setAiName(data.ai_name);
        if (data.ai_greeting) setAiGreeting(data.ai_greeting);
      })
      .catch(() => {
        // Use initialState prop as fallback — this is the default for demo mode
        const fallback: OnboardingState = initialState || {
          status: 'pending',
          current_step: 1,
          completed_steps: [],
          first_victory_completed: false,
        };
        setOnboardingState(fallback);
        if (fallback.current_step > 1) setCurrentStep(fallback.current_step);
        if (fallback.completed_steps) setCompletedSteps(fallback.completed_steps);
      })
      .finally(() => setLoading(false));
  }, [initialState]);

  const completeStep = useCallback(async (step: number) => {
    setCompletedSteps((prev) => [...prev.filter((s) => s !== step), step]);
    setCurrentStep(step + 1);

    try {
      await fetch(`/api/onboarding/complete-step?step=${step}`, {
        method: 'POST',
      });
    } catch {
      // Step completed locally even if API fails
    }
  }, []);

  const handleGoToStep = useCallback((step: number) => {
    if (completedSteps.includes(step) && step !== currentStep) {
      setCurrentStep(step);
    }
  }, [completedSteps, currentStep]);

  const handleBack = useCallback(() => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
    }
  }, [currentStep]);

  const handleNext = useCallback(() => {
    if (completedSteps.includes(currentStep) && currentStep < 5) {
      setCurrentStep((prev) => prev + 1);
    }
  }, [currentStep, completedSteps]);

  const canGoBack = currentStep > 1;
  const canGoNext = completedSteps.includes(currentStep) && currentStep < 5;

  const handleLogout = async () => {
    try { await logout(); } catch { /* ignore */ }
    router.push('/');
  };

  // Read pricing context from URL params
  const source = searchParams.get('source');
  const industry = searchParams.get('industry');
  const cameFromPricing = source === 'pricing';

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}>
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-10 h-10 animate-spin text-orange-400" />
          <p className="text-orange-200/50 text-sm">Loading onboarding...</p>
        </div>
      </div>
    );
  }

  // Show first victory if onboarding is completed
  if (onboardingState?.status === 'completed' && !onboardingState.first_victory_completed) {
    return <FirstVictory aiName={aiName} aiGreeting={aiGreeting} />;
  }

  // Show dashboard redirect if first victory is done
  if (onboardingState?.first_victory_completed) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}>
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-orange-400" />
          <p className="text-orange-200/50 text-sm">Redirecting to dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #1A1A1A 100%)' }}>
      {/* ── Top Header Bar ─────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-white/[0.06]" style={{ background: 'rgba(26,26,26,0.9)', backdropFilter: 'blur(20px)' }}>
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          {/* Left: Back to pricing or logo */}
          <div className="flex items-center gap-3">
            {cameFromPricing && currentStep <= 1 ? (
              <button
                onClick={() => router.push('/pricing')}
                className="flex items-center gap-2 text-sm text-orange-400/70 hover:text-orange-400 transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Back to Pricing</span>
              </button>
            ) : (
              <Link href="/" className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-500/20">
                  <svg className="w-5 h-5" viewBox="0 0 40 40" fill="none">
                    <path d="M6 7h24a4 4 0 014 4v13a4 4 0 01-4 4h-8l-3 6-2-6H6a4 4 0 01-4-4V11a4 4 0 014-4z" stroke="white" strokeWidth="2.8" strokeLinejoin="round" />
                    <path d="M22 11l-6 8h4.5L17 28l8-10h-4.5l3.5-7z" fill="white" />
                  </svg>
                </div>
                <span className="text-white font-semibold text-sm tracking-tight">PARWA</span>
              </Link>
            )}
          </div>

          {/* Center: Progress */}
          <div className="hidden sm:flex">
            <ProgressIndicator
              currentStep={currentStep}
              completedSteps={completedSteps}
              onGoToStep={handleGoToStep}
              onBack={handleBack}
              onNext={handleNext}
              canGoBack={canGoBack}
              canGoNext={canGoNext}
            />
          </div>

          {/* Right: User + Logout */}
          <div className="flex items-center gap-3">
            {user && (
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center text-white text-xs font-semibold">
                  {user.full_name?.charAt(0)?.toUpperCase() || 'U'}
                </div>
                <span className="text-sm text-orange-200/60 hidden sm:inline max-w-[120px] truncate">{user.full_name || user.email}</span>
              </div>
            )}
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-red-400 transition-colors px-2 py-1.5 rounded-lg hover:bg-white/[0.04]"
              title="Logout"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </div>
      </header>

      {/* ── Mobile Progress ────────────────────────────────────────── */}
      <div className="sm:hidden px-4 pt-4">
        <ProgressIndicator
          currentStep={currentStep}
          completedSteps={completedSteps}
          onGoToStep={handleGoToStep}
          onBack={handleBack}
          onNext={handleNext}
          canGoBack={canGoBack}
          canGoNext={canGoNext}
        />
      </div>

      {/* ── Step Content ───────────────────────────────────────────── */}
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="rounded-2xl p-6 sm:p-8 relative overflow-hidden" style={{
          background: 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)',
          border: '1px solid rgba(255,127,17,0.15)',
          backdropFilter: 'blur(20px)',
          boxShadow: '0 25px 50px rgba(0,0,0,0.3), 0 0 60px rgba(255,127,17,0.04)',
        }}>
          {/* Decorative glow */}
          <div className="absolute -top-16 -right-16 w-32 h-32 rounded-full blur-[60px] pointer-events-none" style={{ background: 'rgba(255,127,17,0.08)' }} />

          {currentStep === 1 && (
            <div className="text-center py-8">
              <div className="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center shadow-xl shadow-orange-500/20 mb-6">
                <svg className="w-10 h-10" viewBox="0 0 40 40" fill="none">
                  <path d="M6 7h24a4 4 0 014 4v13a4 4 0 01-4 4h-8l-3 6-2-6H6a4 4 0 01-4-4V11a4 4 0 014-4z" stroke="white" strokeWidth="2.8" strokeLinejoin="round" />
                  <path d="M22 11l-6 8h4.5L17 28l8-10h-4.5l3.5-7z" fill="white" />
                </svg>
              </div>
              <h2 className="text-3xl font-bold text-white mb-3">Welcome to PARWA</h2>
              <p className="text-orange-200/50 mb-2 max-w-md mx-auto">
                Let&apos;s set up your AI-powered customer support platform in a few simple steps.
              </p>
              {industry && (
                <p className="text-sm text-orange-400/60 mb-6">
                  Industry: <span className="text-orange-400 font-medium capitalize">{industry}</span>
                </p>
              )}
              <button
                onClick={() => completeStep(1)}
                className="px-8 py-3 bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 text-[#1A1A1A] font-semibold rounded-xl transition-all duration-300 shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40 text-sm"
              >
                Let&apos;s Get Started
              </button>
            </div>
          )}

          {currentStep === 2 && (
            <LegalCompliance onComplete={() => completeStep(2)} />
          )}

          {currentStep === 3 && (
            <IntegrationStep onNext={() => completeStep(3)} industry={industry || undefined} />
          )}

          {currentStep === 4 && (
            <KnowledgeUpload onComplete={() => completeStep(4)} />
          )}

          {currentStep === 5 && (
            <AIConfig
              onComplete={() => completeStep(5)}
              initialConfig={{
                ai_name: onboardingState?.ai_name || 'Jarvis',
                ai_tone: onboardingState?.ai_tone || 'professional',
                ai_response_style: onboardingState?.ai_response_style || 'concise',
                ai_greeting: onboardingState?.ai_greeting || undefined,
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
