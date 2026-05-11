'use client';

import React, { useState, useEffect, useCallback } from 'react';
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
  const [currentStep, setCurrentStep] = useState(1);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [onboardingState, setOnboardingState] = useState<OnboardingState | null>(null);
  const [aiName, setAiName] = useState('Jarvis');
  const [aiGreeting, setAiGreeting] = useState<string | null>(null);

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
    // Only allow going to completed steps (not current)
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
    // Only allow Next if current step is completed
    if (completedSteps.includes(currentStep) && currentStep < 5) {
      setCurrentStep((prev) => prev + 1);
    }
  }, [currentStep, completedSteps]);

  const canGoBack = currentStep > 1;
  const canGoNext = completedSteps.includes(currentStep) && currentStep < 5;

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
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
      <div className="min-h-[60vh] flex items-center justify-center text-center">
        <p className="text-muted-foreground">Redirecting to dashboard...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Progress with inline navigation */}
        <div className="mb-8">
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

        {/* Step Content */}
        <div className="bg-card rounded-xl border p-6 sm:p-8 shadow-sm">
          {currentStep === 1 && (
            <div className="text-center py-8">
              <h2 className="text-2xl font-bold mb-2">Welcome to PARWA</h2>
              <p className="text-muted-foreground mb-6">
                Let&apos;s set up your AI-powered customer support platform in a few steps.
              </p>
              <button
                onClick={() => completeStep(1)}
                className="px-6 py-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors font-medium"
              >
                Let&apos;s Get Started
              </button>
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
