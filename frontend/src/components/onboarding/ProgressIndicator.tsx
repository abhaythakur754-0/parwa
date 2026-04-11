'use client';

import React from 'react';
import { Check } from 'lucide-react';
import { ONBOARDING_STEPS } from '@/types/onboarding';

interface ProgressIndicatorProps {
  currentStep: number;
  completedSteps: number[];
}

export function ProgressIndicator({ currentStep, completedSteps }: ProgressIndicatorProps) {
  return (
    <div className="flex items-center justify-center gap-1 sm:gap-2">
      {ONBOARDING_STEPS.map((step, idx) => {
        const isCompleted = completedSteps.includes(step.id);
        const isActive = currentStep === step.id;
        const isPast = step.id < currentStep;

        return (
          <React.Fragment key={step.id}>
            {/* Step Circle */}
            <div className="flex flex-col items-center">
              <div
                className={`h-8 w-8 rounded-full flex items-center justify-center text-sm font-medium transition-all ${
                  isCompleted
                    ? 'bg-primary text-primary-foreground'
                    : isActive
                    ? 'bg-primary/20 text-primary ring-2 ring-primary'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                {isCompleted ? (
                  <Check className="h-4 w-4" />
                ) : (
                  step.id
                )}
              </div>
              <span
                className={`text-xs mt-1 hidden sm:block ${
                  isActive ? 'text-primary font-medium' : 'text-muted-foreground'
                }`}
              >
                {step.title}
              </span>
            </div>
            {/* Connector Line */}
            {idx < ONBOARDING_STEPS.length - 1 && (
              <div
                className={`h-0.5 w-8 sm:w-16 transition-colors ${
                  isPast || isCompleted ? 'bg-primary' : 'bg-muted'
                }`}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
