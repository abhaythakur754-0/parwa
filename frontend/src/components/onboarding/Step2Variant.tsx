"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import { Badge } from "@/components/ui/badge";

interface Step2VariantProps {
  selectedVariant: "mini" | "parwa" | "parwa_high" | null;
  updateData: (updates: { selectedVariant: "mini" | "parwa" | "parwa_high" | null }) => void;
  onValidate?: (isValid: boolean) => void;
}

const variants = [
  {
    id: "mini" as const,
    name: "Mini PARWA",
    tier: "Light",
    price: 49,
    priceDisplay: "$49/mo",
    description: "Perfect for small businesses getting started with AI support",
    features: [
      "2 concurrent calls",
      "$50 refund limit",
      "70% escalation threshold",
      "Email support",
      "Basic analytics",
    ],
    limits: {
      concurrentCalls: 2,
      refundLimit: 50,
      escalationThreshold: 70,
    },
    targetAudience: "Small businesses",
  },
  {
    id: "parwa" as const,
    name: "PARWA Junior",
    tier: "Medium",
    price: 149,
    priceDisplay: "$149/mo",
    description: "Great for growing teams that need more power",
    features: [
      "5 concurrent calls",
      "$500 refund limit",
      "APPROVE/REVIEW/DENY workflow",
      "Priority email support",
      "Advanced analytics",
      "Team collaboration",
    ],
    limits: {
      concurrentCalls: 5,
      refundLimit: 500,
      escalationThreshold: 60,
    },
    targetAudience: "Growing teams",
    recommended: true,
  },
  {
    id: "parwa_high" as const,
    name: "PARWA High",
    tier: "Heavy",
    price: 499,
    priceDisplay: "$499/mo",
    description: "Enterprise-grade support with all features unlocked",
    features: [
      "10 concurrent calls",
      "$2000 refund limit",
      "Video support",
      "HIPAA compliance",
      "24/7 priority support",
      "Custom integrations",
      "Dedicated account manager",
    ],
    limits: {
      concurrentCalls: 10,
      refundLimit: 2000,
      escalationThreshold: 50,
    },
    targetAudience: "Enterprise",
  },
];

export function Step2Variant({ selectedVariant, updateData, onValidate }: Step2VariantProps) {
  React.useEffect(() => {
    onValidate?.(selectedVariant !== null);
  }, [selectedVariant, onValidate]);

  return (
    <div className="space-y-6">
      <div className="text-center mb-6">
        <h2 className="text-lg font-semibold">Choose your plan</h2>
        <p className="text-sm text-muted-foreground">
          Select the PARWA variant that fits your needs
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {variants.map((variant) => (
          <div
            key={variant.id}
            onClick={() => updateData({ selectedVariant: variant.id })}
            className={cn(
              "relative p-4 rounded-xl border-2 cursor-pointer transition-all duration-200",
              "hover:shadow-lg",
              selectedVariant === variant.id
                ? "border-primary bg-primary/5 shadow-md"
                : "border-border hover:border-primary/50"
            )}
          >
            {variant.recommended && (
              <Badge className="absolute -top-2 left-1/2 -translate-x-1/2 bg-primary">
                Most Popular
              </Badge>
            )}

            <div className="text-center">
              {/* Tier Badge */}
              <Badge variant="outline" className="mb-2">
                {variant.tier}
              </Badge>

              {/* Name */}
              <h3 className="font-bold text-lg">{variant.name}</h3>

              {/* Price */}
              <div className="mt-3 mb-4">
                <span className="text-3xl font-bold">${variant.price}</span>
                <span className="text-muted-foreground">/mo</span>
              </div>

              {/* Description */}
              <p className="text-xs text-muted-foreground mb-4 min-h-[2.5rem]">
                {variant.description}
              </p>

              {/* Features */}
              <ul className="space-y-2 text-left text-sm">
                {variant.features.map((feature, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <svg
                      className="w-4 h-4 text-green-500 mt-0.5 shrink-0"
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
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              {/* Target Audience */}
              <div className="mt-4 pt-4 border-t border-border">
                <p className="text-xs text-muted-foreground">
                  Best for: <span className="font-medium text-foreground">{variant.targetAudience}</span>
                </p>
              </div>
            </div>

            {/* Selection Indicator */}
            {selectedVariant === variant.id && (
              <div className="absolute top-3 right-3">
                <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center">
                  <svg
                    className="w-4 h-4 text-primary-foreground"
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
            )}
          </div>
        ))}
      </div>

      {/* Comparison Note */}
      <p className="text-xs text-center text-muted-foreground">
        All plans include a 14-day free trial. No credit card required.
      </p>
    </div>
  );
}

export default Step2Variant;
