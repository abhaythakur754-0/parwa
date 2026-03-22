"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/utils/utils";

export interface OnboardingData {
  // Step 1: Company
  companyName: string;
  industry: string;
  companySize: string;
  website: string;
  // Step 2: Variant
  selectedVariant: "mini" | "parwa" | "parwa_high" | null;
  // Step 3: Integrations
  integrations: {
    shopify: boolean;
    zendesk: boolean;
    twilio: boolean;
    email: boolean;
  };
  // Step 4: Team
  teamMembers: Array<{
    email: string;
    role: string;
  }>;
}

const initialData: OnboardingData = {
  companyName: "",
  industry: "",
  companySize: "",
  website: "",
  selectedVariant: null,
  integrations: {
    shopify: false,
    zendesk: false,
    twilio: false,
    email: false,
  },
  teamMembers: [],
};

interface Step {
  id: number;
  title: string;
  description: string;
}

const steps: Step[] = [
  { id: 1, title: "Company", description: "Tell us about your business" },
  { id: 2, title: "Plan", description: "Choose your PARWA variant" },
  { id: 3, title: "Integrations", description: "Connect your tools" },
  { id: 4, title: "Team", description: "Invite your team members" },
  { id: 5, title: "Complete", description: "You're all set!" },
];

interface OnboardingWizardProps {
  onComplete?: (data: OnboardingData) => void;
  initialStep?: number;
}

export function OnboardingWizard({ onComplete, initialStep = 1 }: OnboardingWizardProps) {
  const [currentStep, setCurrentStep] = React.useState(initialStep);
  const [data, setData] = React.useState<OnboardingData>(initialData);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const updateData = (updates: Partial<OnboardingData>) => {
    setData((prev) => ({ ...prev, ...updates }));
  };

  const goToNextStep = () => {
    if (currentStep < 5) {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const goToPreviousStep = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleComplete = async () => {
    setIsSubmitting(true);
    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 1000));

      if (onComplete) {
        onComplete(data);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const progressPercentage = ((currentStep - 1) / (steps.length - 1)) * 100;

  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* Step Indicator */}
      <div className="mb-8">
        <div className="flex justify-between items-center mb-4">
          {steps.map((step, index) => (
            <div
              key={step.id}
              className="flex flex-col items-center flex-1"
            >
              <div
                className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium transition-colors",
                  currentStep > step.id
                    ? "bg-primary text-primary-foreground"
                    : currentStep === step.id
                    ? "bg-primary text-primary-foreground ring-2 ring-primary ring-offset-2"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {currentStep > step.id ? (
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                ) : (
                  step.id
                )}
              </div>
              <div className="mt-2 text-center hidden sm:block">
                <p
                  className={cn(
                    "text-sm font-medium",
                    currentStep >= step.id ? "text-foreground" : "text-muted-foreground"
                  )}
                >
                  {step.title}
                </p>
                <p className="text-xs text-muted-foreground">{step.description}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Progress Bar */}
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-300 ease-in-out"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>
      </div>

      {/* Step Content */}
      <Card className="shadow-lg">
        <CardHeader>
          <CardTitle className="text-xl">
            {steps[currentStep - 1]?.title}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            {steps[currentStep - 1]?.description}
          </p>
        </CardHeader>

        <CardContent>
          <OnboardingStepContent
            step={currentStep}
            data={data}
            updateData={updateData}
            onNext={goToNextStep}
            onComplete={handleComplete}
            isSubmitting={isSubmitting}
          />
        </CardContent>

        {currentStep < 5 && (
          <CardFooter className="flex justify-between">
            <Button
              variant="outline"
              onClick={goToPreviousStep}
              disabled={currentStep === 1}
            >
              Back
            </Button>
            <Button onClick={goToNextStep}>
              {currentStep === 4 ? "Complete Setup" : "Continue"}
            </Button>
          </CardFooter>
        )}
      </Card>
    </div>
  );
}

interface OnboardingStepContentProps {
  step: number;
  data: OnboardingData;
  updateData: (updates: Partial<OnboardingData>) => void;
  onNext: () => void;
  onComplete: () => void;
  isSubmitting: boolean;
}

function OnboardingStepContent({
  step,
  data,
  updateData,
  onNext,
  onComplete,
  isSubmitting,
}: OnboardingStepContentProps) {
  switch (step) {
    case 1:
      return <Step1CompanyContent data={data} updateData={updateData} />;
    case 2:
      return <Step2VariantContent data={data} updateData={updateData} />;
    case 3:
      return <Step3IntegrationsContent data={data} updateData={updateData} />;
    case 4:
      return <Step4TeamContent data={data} updateData={updateData} />;
    case 5:
      return <Step5CompleteContent data={data} onComplete={onComplete} isSubmitting={isSubmitting} />;
    default:
      return null;
  }
}

// Placeholder components - will be replaced by individual step files
function Step1CompanyContent({
  data,
  updateData,
}: {
  data: OnboardingData;
  updateData: (updates: Partial<OnboardingData>) => void;
}) {
  const industries = [
    "E-commerce",
    "SaaS",
    "Healthcare",
    "Logistics",
    "Finance",
    "Education",
    "Other",
  ];

  const companySizes = [
    "1-10 employees",
    "11-50 employees",
    "51-200 employees",
    "201-500 employees",
    "500+ employees",
  ];

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label htmlFor="companyName" className="text-sm font-medium">
          Company Name
        </label>
        <input
          id="companyName"
          type="text"
          placeholder="Acme Inc."
          value={data.companyName}
          onChange={(e) => updateData({ companyName: e.target.value })}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        />
      </div>

      <div className="space-y-2">
        <label htmlFor="industry" className="text-sm font-medium">
          Industry
        </label>
        <select
          id="industry"
          value={data.industry}
          onChange={(e) => updateData({ industry: e.target.value })}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <option value="">Select an industry</option>
          {industries.map((industry) => (
            <option key={industry} value={industry}>
              {industry}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <label htmlFor="companySize" className="text-sm font-medium">
          Company Size
        </label>
        <select
          id="companySize"
          value={data.companySize}
          onChange={(e) => updateData({ companySize: e.target.value })}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <option value="">Select company size</option>
          {companySizes.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <label htmlFor="website" className="text-sm font-medium">
          Website (optional)
        </label>
        <input
          id="website"
          type="url"
          placeholder="https://example.com"
          value={data.website}
          onChange={(e) => updateData({ website: e.target.value })}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        />
      </div>
    </div>
  );
}

function Step2VariantContent({
  data,
  updateData,
}: {
  data: OnboardingData;
  updateData: (updates: Partial<OnboardingData>) => void;
}) {
  const variants = [
    {
      id: "mini" as const,
      name: "Mini PARWA",
      tier: "Light",
      price: "$1000/mo",
      features: ["2 concurrent calls", "$50 refund limit", "70% escalation threshold"],
    },
    {
      id: "parwa" as const,
      name: "PARWA Junior",
      tier: "Medium",
      price: "$2500/mo",
      features: ["5 concurrent calls", "$500 refund limit", "APPROVE/REVIEW/DENY"],
      recommended: true,
    },
    {
      id: "parwa_high" as const,
      name: "PARWA High",
      tier: "Heavy",
      price: "$4000/mo",
      features: ["10 concurrent calls", "$2000 refund limit", "Video + Analytics"],
    },
  ];

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Choose the plan that best fits your business needs.
      </p>
      <div className="grid gap-4 sm:grid-cols-3">
        {variants.map((variant) => (
          <div
            key={variant.id}
            onClick={() => updateData({ selectedVariant: variant.id })}
            className={cn(
              "relative p-4 rounded-lg border-2 cursor-pointer transition-all",
              data.selectedVariant === variant.id
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/50"
            )}
          >
            {variant.recommended && (
              <div className="absolute -top-2 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground text-xs px-2 py-0.5 rounded-full">
                Recommended
              </div>
            )}
            <div className="text-center">
              <h3 className="font-semibold">{variant.name}</h3>
              <p className="text-xs text-muted-foreground">{variant.tier}</p>
              <p className="text-xl font-bold mt-2">{variant.price}</p>
              <ul className="mt-4 space-y-2 text-xs text-left">
                {variant.features.map((feature, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    {feature}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Step3IntegrationsContent({
  data,
  updateData,
}: {
  data: OnboardingData;
  updateData: (updates: Partial<OnboardingData>) => void;
}) {
  const integrations = [
    {
      id: "shopify" as const,
      name: "Shopify",
      description: "Connect your Shopify store for order management",
      icon: "🛒",
    },
    {
      id: "zendesk" as const,
      name: "Zendesk",
      description: "Sync with your Zendesk support tickets",
      icon: "🎫",
    },
    {
      id: "twilio" as const,
      name: "Twilio",
      description: "Enable voice and SMS capabilities",
      icon: "📞",
    },
    {
      id: "email" as const,
      name: "Email Provider",
      description: "Connect your email for notifications",
      icon: "📧",
    },
  ];

  const toggleIntegration = (id: keyof typeof data.integrations) => {
    updateData({
      integrations: {
        ...data.integrations,
        [id]: !data.integrations[id],
      },
    });
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Connect your existing tools to get the most out of PARWA. You can skip this and set up later.
      </p>
      <div className="space-y-3">
        {integrations.map((integration) => (
          <div
            key={integration.id}
            onClick={() => toggleIntegration(integration.id)}
            className={cn(
              "flex items-center justify-between p-4 rounded-lg border cursor-pointer transition-all",
              data.integrations[integration.id]
                ? "border-primary bg-primary/5"
                : "border-border hover:border-primary/50"
            )}
          >
            <div className="flex items-center gap-4">
              <span className="text-2xl">{integration.icon}</span>
              <div>
                <h4 className="font-medium">{integration.name}</h4>
                <p className="text-sm text-muted-foreground">{integration.description}</p>
              </div>
            </div>
            <div
              className={cn(
                "w-12 h-6 rounded-full transition-colors relative",
                data.integrations[integration.id] ? "bg-primary" : "bg-muted"
              )}
            >
              <div
                className={cn(
                  "absolute top-1 w-4 h-4 rounded-full bg-white transition-transform",
                  data.integrations[integration.id] ? "translate-x-7" : "translate-x-1"
                )}
              />
            </div>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground text-center">
        You can connect more integrations later from your dashboard settings.
      </p>
    </div>
  );
}

function Step4TeamContent({
  data,
  updateData,
}: {
  data: OnboardingData;
  updateData: (updates: Partial<OnboardingData>) => void;
}) {
  const roles = ["Admin", "Agent", "Viewer"];

  const addTeamMember = () => {
    if (data.teamMembers.length < 5) {
      updateData({
        teamMembers: [...data.teamMembers, { email: "", role: "Agent" }],
      });
    }
  };

  const removeTeamMember = (index: number) => {
    updateData({
      teamMembers: data.teamMembers.filter((_, i) => i !== index),
    });
  };

  const updateTeamMember = (index: number, field: "email" | "role", value: string) => {
    const newMembers = [...data.teamMembers];
    newMembers[index] = { ...newMembers[index], [field]: value };
    updateData({ teamMembers: newMembers });
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Invite team members to join your workspace. You can add up to 5 members now.
      </p>

      {data.teamMembers.length > 0 && (
        <div className="space-y-3">
          {data.teamMembers.map((member, index) => (
            <div key={index} className="flex gap-2 items-start">
              <input
                type="email"
                placeholder="colleague@example.com"
                value={member.email}
                onChange={(e) => updateTeamMember(index, "email", e.target.value)}
                className="flex-1 h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              />
              <select
                value={member.role}
                onChange={(e) => updateTeamMember(index, "role", e.target.value)}
                className="h-10 w-28 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                {roles.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
              <Button
                variant="outline"
                size="icon"
                onClick={() => removeTeamMember(index)}
                className="h-10 w-10"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </Button>
            </div>
          ))}
        </div>
      )}

      {data.teamMembers.length < 5 && (
        <Button variant="outline" onClick={addTeamMember} className="w-full">
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Team Member ({5 - data.teamMembers.length} remaining)
        </Button>
      )}

      <p className="text-xs text-muted-foreground text-center">
        Team members will receive an email invitation to join your workspace.
      </p>
    </div>
  );
}

function Step5CompleteContent({
  data,
  onComplete,
  isSubmitting,
}: {
  data: OnboardingData;
  onComplete: () => void;
  isSubmitting: boolean;
}) {
  const variantNames = {
    mini: "Mini PARWA",
    parwa: "PARWA Junior",
    parwa_high: "PARWA High",
  };

  return (
    <div className="space-y-6 text-center">
      {/* Success Animation */}
      <div className="flex justify-center">
        <div className="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center">
          <svg
            className="w-10 h-10 text-green-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
      </div>

      <div>
        <h2 className="text-2xl font-bold">You&apos;re all set!</h2>
        <p className="text-muted-foreground mt-2">
          Your workspace has been configured and is ready to use.
        </p>
      </div>

      {/* Summary */}
      <div className="bg-muted rounded-lg p-4 text-left space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Company:</span>
          <span className="font-medium">{data.companyName || "Not specified"}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Industry:</span>
          <span className="font-medium">{data.industry || "Not specified"}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Plan:</span>
          <span className="font-medium">
            {data.selectedVariant ? variantNames[data.selectedVariant] : "Not selected"}
          </span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Integrations:</span>
          <span className="font-medium">
            {Object.values(data.integrations).filter(Boolean).length} connected
          </span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Team Members:</span>
          <span className="font-medium">{data.teamMembers.length} invited</span>
        </div>
      </div>

      <Button onClick={onComplete} disabled={isSubmitting} className="w-full" size="lg">
        {isSubmitting ? (
          <>
            <svg
              className="animate-spin -ml-1 mr-2 h-4 w-4"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            Setting up workspace...
          </>
        ) : (
          "Go to Dashboard"
        )}
      </Button>

      <p className="text-xs text-muted-foreground">
        Want to learn more?{" "}
        <a href="/docs" className="text-primary hover:underline">
          Start the tutorial
        </a>
      </p>
    </div>
  );
}

export default OnboardingWizard;
