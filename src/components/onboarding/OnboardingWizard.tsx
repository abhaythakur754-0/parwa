"use client";

import { useRouter } from "next/navigation";
import { useOnboardingStore } from "@/store/onboarding-store";
import { IndustryVariantStep } from "./IndustryVariantStep";
import { LegalStep } from "./LegalStep";
import { IntegrationStep } from "./IntegrationStep";
import { KnowledgeStep } from "./KnowledgeStep";
import { AIConfigStep } from "./AIConfigStep";
import { CostBreakdownStep } from "./CostBreakdownStep";
import { Bot } from "lucide-react";

const STEPS = [
  { label: "Industry & Variant", shortLabel: "Industry" },
  { label: "Legal Consent", shortLabel: "Legal" },
  { label: "Integrations", shortLabel: "Integrate" },
  { label: "Knowledge Base", shortLabel: "Knowledge" },
  { label: "AI Configuration", shortLabel: "AI Config" },
  { label: "Cost & Checkout", shortLabel: "Cost" },
  { label: "Go Live!", shortLabel: "Go Live" },
];

export function OnboardingWizard() {
  const { currentStep, nextStep, prevStep } = useOnboardingStore();

  const renderStep = () => {
    switch (currentStep) {
      case 0: return <IndustryVariantStep />;
      case 1: return <LegalStep />;
      case 2: return <IntegrationStep />;
      case 3: return <KnowledgeStep />;
      case 4: return <AIConfigStep />;
      case 5: return <CostBreakdownStep />;
      case 6: return <CompletionStep />;
      default: return <IndustryVariantStep />;
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="flex justify-center mb-4">
          <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
            <Bot className="h-6 w-6 text-white" />
          </div>
        </div>
        <h1 className="text-2xl font-bold">Set up your PARWA workspace</h1>
        <p className="text-muted-foreground mt-1">Step {currentStep + 1} of 7 — {STEPS[currentStep]?.label}</p>
      </div>

      {/* Step Indicator */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-2">
          {STEPS.map((step, idx) => (
            <div key={idx} className="flex items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold transition-all ${
                  idx < currentStep
                    ? "bg-emerald-500 text-white"
                    : idx === currentStep
                    ? "bg-emerald-500 text-white ring-4 ring-emerald-100 dark:ring-emerald-900/30"
                    : "bg-muted text-muted-foreground"
                }`}
                title={step.label}
              >
                {idx < currentStep ? "✓" : idx + 1}
              </div>
              {idx < STEPS.length - 1 && (
                <div
                  className={`h-0.5 w-6 sm:w-12 md:w-16 ${
                    idx < currentStep ? "bg-emerald-500" : "bg-muted"
                  }`}
                />
              )}
            </div>
          ))}
        </div>
        <div className="hidden sm:flex justify-between">
          {STEPS.map((step, idx) => (
            <span
              key={idx}
              className={`text-[10px] md:text-xs ${
                idx <= currentStep ? "text-emerald-600 dark:text-emerald-400 font-medium" : "text-muted-foreground"
              }`}
            >
              {step.shortLabel}
            </span>
          ))}
        </div>
      </div>

      {/* Step Content */}
      <div className="min-h-[400px]">
        {renderStep()}
      </div>

      {/* Navigation */}
      <div className="flex justify-between mt-8">
        <button
          onClick={prevStep}
          disabled={currentStep === 0}
          className="px-6 py-2 text-sm font-medium rounded-lg border border-border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Back
        </button>
        {currentStep < 6 && (
          <button
            onClick={nextStep}
            className="px-6 py-2 text-sm font-medium rounded-lg bg-gradient-to-r from-emerald-500 to-teal-600 text-white hover:from-emerald-600 hover:to-teal-700 transition-all"
          >
            Continue
          </button>
        )}
      </div>
    </div>
  );
}

// Completion step component
function CompletionStep() {
  const router = useRouter();
  const { nextStep } = useOnboardingStore();

  const handleActivate = async () => {
    try {
      const res = await fetch("/api/onboarding/activate", { method: "POST" });
      if (res.ok) {
        nextStep();
        router.push("/dashboard");
      }
    } catch {
      // Handle error silently
    }
  };

  return (
    <div className="text-center py-12">
      <div className="h-20 w-20 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center mx-auto mb-6">
        <Bot className="h-10 w-10 text-white" />
      </div>
      <h2 className="text-2xl font-bold mb-2">You&apos;re all set!</h2>
      <p className="text-muted-foreground mb-8 max-w-md mx-auto">
        Your PARWA workspace is configured and ready. Click below to activate and start handling support tickets with AI.
      </p>
      <button
        onClick={handleActivate}
        className="px-8 py-3 text-base font-semibold rounded-lg bg-gradient-to-r from-emerald-500 to-teal-600 text-white hover:from-emerald-600 hover:to-teal-700 transition-all"
      >
        Activate & Go to Dashboard
      </button>
    </div>
  );
}
