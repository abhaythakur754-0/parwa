'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ProgressIndicator } from './ProgressIndicator';
import { DetailsVerificationStep } from './DetailsVerificationStep';
import { IntegrationStep } from './IntegrationStep';
import { KnowledgeUpload } from './KnowledgeUpload';
import { FirstVictory } from './FirstVictory';
import { Loader2, ArrowLeft, LogOut } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import Link from 'next/link';
import type { OnboardingState } from '@/types/onboarding';
import type { ParwaVariant } from './IndustryVariantStep';
import { mapIndustryToParwaIndustry, type ParwaIndustry } from '@/lib/integration-catalog';

const TOTAL_STEPS = 4;

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

  // Phase 4: industry + variant from Step 1
  const [selectedIndustry, setSelectedIndustry] = useState<ParwaIndustry | null>(null);
  const [selectedVariant, setSelectedVariant] = useState<ParwaVariant | null>(null);

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
        const fallback = initialState || ({
          status: 'pending',
          current_step: 1,
          completed_steps: [],
          first_victory_completed: false,
        } as unknown as OnboardingState);
        setOnboardingState(fallback);
        if (fallback.current_step > 1) setCurrentStep(fallback.current_step);
        if (fallback.completed_steps) setCompletedSteps(fallback.completed_steps);
      })
      .finally(() => setLoading(false));

    // Restore industry/variant from localStorage
    try {
      const stored = localStorage.getItem('parwa_pricing_context');
      if (stored) {
        const ctx = JSON.parse(stored) as { industry?: ParwaIndustry; variant?: ParwaVariant };
        if (ctx.industry) setSelectedIndustry(ctx.industry);
        if (ctx.variant) setSelectedVariant(ctx.variant);
      }
    } catch {
      // ignore
    }
  }, [initialState]);

  const completeStep = useCallback(async (step: number) => {
    setCompletedSteps((prev) => [...prev.filter((s) => s !== step), step]);

    // Step 3 (Knowledge Base) completes the onboarding and goes to FirstVictory (Step 4)
    if (step === 3) {
      // Mark onboarding as completed — send variant + industry so backend can create instance
      try {
        const pricingContext = localStorage.getItem('parwa_pricing_context');
        const ctx = pricingContext ? JSON.parse(pricingContext) : {};
        await fetch('/api/onboarding/activate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            variant: selectedVariant || ctx.variant || 'parwa',
            industry: selectedIndustry || ctx.industry || 'other',
          }),
        });
      } catch {
        // Continue locally even if API fails
      }
      setCurrentStep(4);
    } else {
      setCurrentStep(step + 1);
    }

    try {
      await fetch(`/api/onboarding/complete-step?step=${step}`, {
        method: 'POST',
      });
    } catch {
      // Step completed locally even if API fails
    }
  }, [selectedVariant, selectedIndustry]);

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
    if (completedSteps.includes(currentStep) && currentStep < TOTAL_STEPS) {
      setCurrentStep((prev) => prev + 1);
    }
  }, [currentStep, completedSteps]);

  const canGoBack = currentStep > 1;
  const canGoNext = completedSteps.includes(currentStep) && currentStep < TOTAL_STEPS;

  const handleLogout = async () => {
    try { await logout(); } catch { /* ignore */ }
    router.push('/');
  };

  // Read pricing context from URL params (from models page)
  const source = searchParams.get('source');
  const industryParam = searchParams.get('industry');
  const variantIdParam = searchParams.get('variant_id');
  const cameFromPricing = source === 'pricing';

  // Map variant_id from URL to ParwaVariant type
  // Models page sends: 'mini' | 'parwa' | 'high'
  // ParwaVariant type is: 'mini' | 'parwa' | 'high'
  React.useEffect(() => {
    if (variantIdParam && !selectedVariant) {
      const variantMap: Record<string, ParwaVariant> = {
        'mini': 'mini',
        'parwa': 'parwa',
        'high': 'high',
      };
      const mapped = variantMap[variantIdParam];
      if (mapped) {
        setSelectedVariant(mapped);
        // Also save to localStorage so it persists
        const existing = localStorage.getItem('parwa_pricing_context');
        const ctx = existing ? JSON.parse(existing) : {};
        ctx.variant = mapped;
        if (industryParam) {
          const mapped_industry = mapIndustryToParwaIndustry(industryParam);
          if (mapped_industry) {
            ctx.industry = mapped_industry;
            setSelectedIndustry(mapped_industry);
          }
        }
        localStorage.setItem('parwa_pricing_context', JSON.stringify(ctx));

        // Save variant + industry to backend (creates VariantInstance + updates company)
        fetch('/api/onboarding/industry-variant', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            industry: industryParam || 'other',
            variant: mapped,
          }),
        }).catch(() => {});
      }
    }
  }, [variantIdParam, selectedVariant, industryParam]);

  // Resolve industry: URL param > localStorage > undefined
  const resolvedIndustry = selectedIndustry || (industryParam ? mapIndustryToParwaIndustry(industryParam) : undefined);

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

  // Step 4: Show FirstVictory directly (outside the card wrapper)
  if (currentStep === 4 || (onboardingState?.status === 'completed' && !onboardingState.first_victory_completed)) {
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

          {/* Step 1: Details + Verification (name, URL, email OTP, legal) */}
          {currentStep === 1 && (
            <DetailsVerificationStep
              initialFullName={user?.full_name || ''}
              onComplete={(data) => {
                // Save details to onboarding session
                fetch('/api/onboarding/details', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(data),
                }).catch(() => {});
                completeStep(1);
              }}
            />
          )}

          {/* Step 2: Integration Setup */}
          {currentStep === 2 && (
            <IntegrationStep onNext={() => completeStep(2)} industry={resolvedIndustry} />
          )}

          {/* Step 3: Knowledge Upload */}
          {currentStep === 3 && (
            <KnowledgeUpload onComplete={() => completeStep(3)} />
          )}
        </div>
      </div>
    </div>
  );
}
