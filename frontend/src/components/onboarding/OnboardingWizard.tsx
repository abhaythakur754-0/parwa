'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { ProgressIndicator } from './ProgressIndicator';
import { LegalCompliance } from './LegalCompliance';
import { IntegrationSetup } from './IntegrationSetup';
import { KnowledgeUpload } from './KnowledgeUpload';
import { AIConfig } from './AIConfig';
import { FirstVictory } from './FirstVictory';
import { Loader2 } from 'lucide-react';
import type { OnboardingState } from '@/types/onboarding';

interface OnboardingWizardProps {
  initialState?: OnboardingState;
}

export function OnboardingWizard({ initialState }: OnboardingWizardProps) {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [onboardingState, setOnboardingState] = useState<OnboardingState | null>(null);
  const [aiName, setAiName] = useState('Jarvis');
  const [aiGreeting, setAiGreeting] = useState<string | null>(null);
  // P6: Track last error so we don't silently advance past failures
  const [stepError, setStepError] = useState<string | null>(null);

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
        // Use initialState prop as fallback
        if (initialState) {
          setOnboardingState(initialState);
          if (initialState.current_step > 1) setCurrentStep(initialState.current_step);
          if (initialState.completed_steps) setCompletedSteps(initialState.completed_steps);
        }
      })
      .finally(() => setLoading(false));
  }, [initialState]);

  // Redirect to dashboard if first victory is done — must be before any early returns (Rules of Hooks)
  useEffect(() => {
    if (onboardingState?.first_victory_completed || onboardingState?.status === 'completed') {
      // Check if first victory API has been called
      if (onboardingState.first_victory_completed) {
        router.replace('/dashboard');
      }
    }
  }, [onboardingState?.first_victory_completed, onboardingState?.status, router]);

  const completeStep = async (step: number, extraData?: Record<string, unknown>) => {
    setStepError(null);
    setCompletedSteps((prev) => [...prev.filter((s) => s !== step), step]);

    // D8-4: Merge extra data from child component (e.g., AI config from activation)
    if (extraData) {
      if (extraData.ai_name) setAiName(extraData.ai_name as string);
      if (extraData.ai_greeting !== undefined) setAiGreeting(extraData.ai_greeting as string | null);
      setOnboardingState((prev) => prev ? {
        ...prev,
        ...(extraData.ai_name && { ai_name: extraData.ai_name as string }),
        ...(extraData.ai_tone && { ai_tone: extraData.ai_tone as string }),
        ...(extraData.ai_response_style && { ai_response_style: extraData.ai_response_style as string }),
        ...(extraData.ai_greeting !== undefined && { ai_greeting: extraData.ai_greeting as string | null }),
      } : prev);
    }

    try {
      const res = await fetch(`/api/onboarding/complete-step?step=${step}`, {
        method: 'POST',
      });
      if (res.ok) {
        // After step 5, show FirstVictory directly (don't advance to step 6)
        if (step >= 5) {
          setOnboardingState((prev) => prev ? { ...prev, status: 'completed' as const } : prev);
          return;
        }
        setCurrentStep(step + 1);
      } else {
        // P6 FIX: Do NOT silently advance on API failure.
        // Parse the error and show it to the user.
        const errorData = await res.json().catch(() => ({ detail: `Step ${step} failed. Please try again.` }));
        setStepError(errorData.detail || `Failed to complete step ${step}.`);
        // Revert the local optimistic step completion
        setCompletedSteps((prev) => prev.filter((s) => s !== step));
      }
    } catch {
      // P6 FIX: On network error, don't advance. Show error instead.
      setStepError(`Network error. Please check your connection and try again.`);
      setCompletedSteps((prev) => prev.filter((s) => s !== step));
    }
  };

  // D8-1: Called by FirstVictory after marking completion on server.
  // Updates local state so the redirect useEffect triggers.
  const handleVictoryComplete = () => {
    setOnboardingState((prev) => prev ? {
      ...prev,
      first_victory_completed: true,
      status: 'completed' as const,
    } : prev);
  };

  // P17 FIX: Listen for changes from other tabs via localStorage.
  // When a user has the onboarding open in two tabs and completes a step
  // in one tab, the other tab should detect the state change and refresh.
  const handleStorageChange = useCallback((e: StorageEvent) => {
    if (e.key?.startsWith('parwa_')) {
      // Re-fetch state when another tab updates onboarding data
      fetch('/api/onboarding/state')
        .then((res) => res.json())
        .then((data) => {
          if (data?.current_step) {
            setOnboardingState(data);
            if (data.current_step > 1) setCurrentStep(data.current_step);
            if (data.completed_steps) setCompletedSteps(data.completed_steps);
          }
        })
        .catch(() => { /* best effort */ });
    }
  }, []);

  useEffect(() => {
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [handleStorageChange]);

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Show first victory if onboarding is completed
  if (onboardingState?.status === 'completed' && !onboardingState.first_victory_completed) {
    return <FirstVictory aiName={aiName} aiGreeting={aiGreeting} onVictoryComplete={handleVictoryComplete} />;
  }

  if (onboardingState?.first_victory_completed) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center text-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground mb-3" />
        <p className="text-muted-foreground">Redirecting to dashboard...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Progress */}
        <div className="mb-8">
          <ProgressIndicator
            currentStep={currentStep}
            completedSteps={completedSteps}
          />
        </div>

        {/* Step Content */}
        <div className="bg-card rounded-xl border p-6 sm:p-8 shadow-sm">
          {currentStep === 1 && (
            <div className="text-center py-8">
              <h2 className="text-2xl font-bold mb-2">Welcome to PARWA</h2>
              <p className="text-muted-foreground mb-6">
                Let&apos;s set up your AI-powered customer support platform in a few steps.
              </p>
              {/* P6: Show step error if any */}
              {stepError && (
                <p className="text-destructive text-sm mb-4">{stepError}</p>
              )}
              {/* D8-5: Use shadcn Button instead of raw <button> */}
              <Button
                onClick={() => completeStep(1)}
                size="lg"
              >
                Let&apos;s Get Started
              </Button>
            </div>
          )}

          {currentStep === 2 && (
            <LegalCompliance onComplete={() => completeStep(2)} />
          )}

          {currentStep === 3 && (
            <IntegrationSetup onComplete={() => completeStep(3)} />
          )}

          {currentStep === 4 && (
            <KnowledgeUpload onComplete={() => completeStep(4)} />
          )}

          {currentStep === 5 && (
            <AIConfig
              onComplete={(config) => completeStep(5, config)}
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
