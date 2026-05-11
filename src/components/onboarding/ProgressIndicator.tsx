'use client';

import React from 'react';
import { Check, ChevronLeft, ChevronRight } from 'lucide-react';
import { ONBOARDING_STEPS } from '@/types/onboarding';
import { Button } from '@/components/ui/button';

interface ProgressIndicatorProps {
  currentStep: number;
  completedSteps: number[];
  onGoToStep?: (step: number) => void;
  onBack?: () => void;
  onNext?: () => void;
  canGoBack?: boolean;
  canGoNext?: boolean;
}

export function ProgressIndicator({
  currentStep,
  completedSteps,
  onGoToStep,
  onBack,
  onNext,
  canGoBack = false,
  canGoNext = false,
}: ProgressIndicatorProps) {
  return (
    <div className="flex items-center justify-between gap-2">
      {/* Back Button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onBack}
        disabled={!canGoBack}
        className="shrink-0 text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="h-4 w-4 mr-1" />
        Back
      </Button>

      {/* Step Circles */}
      <div className="flex items-center justify-center gap-1 sm:gap-2">
        {ONBOARDING_STEPS.map((step, idx) => {
          const isCompleted = completedSteps.includes(step.id);
          const isActive = currentStep === step.id;
          const isPast = step.id < currentStep;
          const isClickable = isCompleted && step.id !== currentStep;

          return (
            <React.Fragment key={step.id}>
              {/* Step Circle */}
              <div className="flex flex-col items-center">
                <button
                  type="button"
                  disabled={!isClickable && !onGoToStep}
                  onClick={() => {
                    if ((isClickable || isCompleted) && onGoToStep) {
                      onGoToStep(step.id);
                    }
                  }}
                  className={`h-8 w-8 rounded-full flex items-center justify-center text-sm font-medium transition-all ${
                    isClickable
                      ? 'bg-primary text-primary-foreground cursor-pointer hover:ring-2 hover:ring-primary/30 hover:scale-110'
                      : isCompleted
                      ? 'bg-primary text-primary-foreground'
                      : isActive
                      ? 'bg-primary/20 text-primary ring-2 ring-primary'
                      : 'bg-muted text-muted-foreground'
                  } ${isClickable ? 'hover:shadow-md' : ''}`}
                  title={isClickable ? `Go back to ${step.title}` : step.title}
                >
                  {isCompleted ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    step.id
                  )}
                </button>
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

      {/* Next Button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onNext}
        disabled={!canGoNext}
        className="shrink-0 text-muted-foreground hover:text-foreground"
      >
        Next
        <ChevronRight className="h-4 w-4 ml-1" />
      </Button>
    </div>
  );
}
