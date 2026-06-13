'use client';

import React from 'react';
import { Check, ChevronLeft, ChevronRight } from 'lucide-react';
import { ONBOARDING_STEPS } from '@/types/onboarding';

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
    <div className="flex items-center justify-between gap-2 w-full max-w-xl">
      {/* Back Button */}
      <button
        onClick={onBack}
        disabled={!canGoBack}
        className="shrink-0 text-xs text-orange-200/40 hover:text-orange-400 transition-colors flex items-center gap-1 disabled:opacity-30 disabled:cursor-not-allowed"
      >
        <ChevronLeft className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">Back</span>
      </button>

      {/* Step Circles — always show all 6 steps */}
      <div className="flex items-center justify-center gap-0.5 sm:gap-1 flex-1 min-w-0">
        {ONBOARDING_STEPS.map((step, idx) => {
          const isCompleted = completedSteps.includes(step.id);
          const isActive = currentStep === step.id;
          const isPast = step.id < currentStep;
          const isClickable = isCompleted && step.id !== currentStep;

          return (
            <React.Fragment key={step.id}>
              {/* Step Circle */}
              <div className="flex flex-col items-center min-w-0">
                <button
                  type="button"
                  disabled={!isClickable}
                  onClick={() => {
                    if (isClickable && onGoToStep) {
                      onGoToStep(step.id);
                    }
                  }}
                  className={`h-6 w-6 sm:h-7 sm:w-7 rounded-full flex items-center justify-center text-[10px] sm:text-xs font-medium transition-all duration-200 ${
                    isClickable
                      ? 'bg-gradient-to-r from-orange-500 to-amber-400 text-white cursor-pointer hover:scale-110 hover:shadow-lg hover:shadow-orange-500/20'
                      : isCompleted
                      ? 'bg-gradient-to-r from-orange-500 to-amber-400 text-white'
                      : isActive
                      ? 'bg-orange-500/20 text-orange-400 ring-2 ring-orange-500/40'
                      : 'bg-white/[0.06] text-zinc-500'
                  }`}
                  title={isClickable ? `Go back to ${step.title}` : step.title}
                >
                  {isCompleted ? (
                    <Check className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                  ) : (
                    step.id
                  )}
                </button>
                <span
                  className={`text-[8px] sm:text-[10px] mt-0.5 truncate max-w-[48px] sm:max-w-none text-center leading-tight ${
                    isActive ? 'text-orange-400 font-medium' : 'text-zinc-600'
                  }`}
                >
                  {step.title}
                </span>
              </div>
              {/* Connector Line */}
              {idx < ONBOARDING_STEPS.length - 1 && (
                <div
                  className={`h-0.5 w-3 sm:w-6 mt-[-14px] sm:mt-[-16px] transition-colors rounded-full shrink-0 ${
                    isPast || isCompleted ? 'bg-gradient-to-r from-orange-500 to-amber-400' : 'bg-white/[0.06]'
                  }`}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Next Button */}
      <button
        onClick={onNext}
        disabled={!canGoNext}
        className="shrink-0 text-xs text-orange-200/40 hover:text-orange-400 transition-colors flex items-center gap-1 disabled:opacity-30 disabled:cursor-not-allowed"
      >
        <span className="hidden sm:inline">Next</span>
        <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
