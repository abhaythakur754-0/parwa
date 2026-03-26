"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/utils/utils";
import { Check, Zap, Briefcase, Crown } from "lucide-react";

export interface PricingInput {
  ticketVolume: number;
  channels: string[];
  billingCycle: "monthly" | "annual";
}

export interface PricingCalculatorProps {
  value?: PricingInput;
  onChange?: (value: PricingInput) => void;
  onVariantSelect?: (variant: "mini" | "parwa" | "parwa_high") => void;
  className?: string;
}

interface VariantPricing {
  id: "mini" | "parwa" | "parwa_high";
  name: string;
  tier: string;
  icon: React.ReactNode;
  basePrice: number;
  pricePerTicket: number;
  includedTickets: number;
  maxRefund: number;
  concurrentCalls: number;
  features: string[];
}

const VARIANTS: VariantPricing[] = [
  {
    id: "mini",
    name: "Mini PARWA",
    tier: "Light",
    icon: <Zap className="h-5 w-5" />,
    basePrice: 49,
    pricePerTicket: 0.05,
    includedTickets: 500,
    maxRefund: 50,
    concurrentCalls: 2,
    features: [
      "2 concurrent calls",
      "$50 refund limit",
      "70% escalation threshold",
      "Email support",
      "Basic analytics",
    ],
  },
  {
    id: "parwa",
    name: "PARWA Junior",
    tier: "Medium",
    icon: <Briefcase className="h-5 w-5" />,
    basePrice: 149,
    pricePerTicket: 0.03,
    includedTickets: 2000,
    maxRefund: 500,
    concurrentCalls: 5,
    features: [
      "5 concurrent calls",
      "$500 refund limit",
      "APPROVE/REVIEW/DENY",
      "Priority support",
      "Advanced analytics",
      "Custom workflows",
    ],
  },
  {
    id: "parwa_high",
    name: "PARWA High",
    tier: "Heavy",
    icon: <Crown className="h-5 w-5" />,
    basePrice: 499,
    pricePerTicket: 0.02,
    includedTickets: 5000,
    maxRefund: 2000,
    concurrentCalls: 10,
    features: [
      "10 concurrent calls",
      "$2000 refund limit",
      "Video support",
      "Full analytics suite",
      "API access",
      "Dedicated account manager",
      "Custom integrations",
    ],
  },
];

const CHANNELS = [
  { id: "email", name: "Email", multiplier: 1 },
  { id: "chat", name: "Chat", multiplier: 1.2 },
  { id: "voice", name: "Voice", multiplier: 1.5 },
  { id: "sms", name: "SMS", multiplier: 1.3 },
];

const DEFAULT_INPUT: PricingInput = {
  ticketVolume: 500,
  channels: ["email"],
  billingCycle: "monthly",
};

export function PricingCalculator({
  value = DEFAULT_INPUT,
  onChange,
  onVariantSelect,
  className,
}: PricingCalculatorProps) {
  const [input, setInput] = React.useState<PricingInput>(value);
  const [selectedVariant, setSelectedVariant] = React.useState<
    "mini" | "parwa" | "parwa_high" | null
  >(null);

  React.useEffect(() => {
    setInput(value);
  }, [value]);

  const updateInput = (updates: Partial<PricingInput>) => {
    const newInput = { ...input, ...updates };
    setInput(newInput);
    onChange?.(newInput);
  };

  const calculatePrice = (variant: VariantPricing): number => {
    let price = variant.basePrice;

    // Add overage for tickets beyond included
    if (input.ticketVolume > variant.includedTickets) {
      price += (input.ticketVolume - variant.includedTickets) * variant.pricePerTicket;
    }

    // Apply channel multipliers
    const avgMultiplier =
      input.channels.reduce((sum, ch) => {
        const channel = CHANNELS.find((c) => c.id === ch);
        return sum + (channel?.multiplier || 1);
      }, 0) / input.channels.length || 1;

    price = price * avgMultiplier;

    // Apply annual discount
    if (input.billingCycle === "annual") {
      price = price * 0.8; // 20% discount
    }

    return Math.round(price);
  };

  const getRecommendedVariant = (): VariantPricing => {
    if (input.ticketVolume <= 500) return VARIANTS[0];
    if (input.ticketVolume <= 2000) return VARIANTS[1];
    return VARIANTS[2];
  };

  const handleVariantSelect = (variant: "mini" | "parwa" | "parwa_high") => {
    setSelectedVariant(variant);
    onVariantSelect?.(variant);
  };

  const recommendedVariant = getRecommendedVariant();

  return (
    <div className={cn("space-y-6", className)}>
      {/* Configuration Section */}
      <div className="space-y-6">
        {/* Ticket Volume Slider */}
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <label className="text-sm font-medium">Monthly Ticket Volume</label>
            <span className="text-2xl font-bold text-primary">
              {input.ticketVolume.toLocaleString()}
            </span>
          </div>
          <input
            type="range"
            min="100"
            max="10000"
            step="100"
            value={input.ticketVolume}
            onChange={(e) => updateInput({ ticketVolume: parseInt(e.target.value) })}
            className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>100</span>
            <span>10,000+</span>
          </div>
        </div>

        {/* Channel Selection */}
        <div className="space-y-3">
          <label className="text-sm font-medium">Support Channels</label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {CHANNELS.map((channel) => (
              <button
                key={channel.id}
                type="button"
                onClick={() => {
                  const channels = input.channels.includes(channel.id)
                    ? input.channels.filter((c) => c !== channel.id)
                    : [...input.channels, channel.id];
                  updateInput({ channels });
                }}
                className={cn(
                  "p-3 rounded-lg border text-sm font-medium transition-all",
                  input.channels.includes(channel.id)
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border hover:border-primary/50"
                )}
              >
                {channel.name}
              </button>
            ))}
          </div>
        </div>

        {/* Billing Cycle Toggle */}
        <div className="space-y-3">
          <label className="text-sm font-medium">Billing Cycle</label>
          <div className="flex rounded-lg border p-1">
            {(["monthly", "annual"] as const).map((cycle) => (
              <button
                key={cycle}
                type="button"
                onClick={() => updateInput({ billingCycle: cycle })}
                className={cn(
                  "flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all",
                  input.billingCycle === cycle
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-muted"
                )}
              >
                {cycle.charAt(0).toUpperCase() + cycle.slice(1)}
                {cycle === "annual" && (
                  <Badge variant="secondary" className="ml-2 text-xs">
                    -20%
                  </Badge>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Pricing Cards */}
      <div className="grid sm:grid-cols-3 gap-4">
        {VARIANTS.map((variant) => {
          const price = calculatePrice(variant);
          const isRecommended = variant.id === recommendedVariant.id;
          const isSelected = selectedVariant === variant.id;

          return (
            <Card
              key={variant.id}
              className={cn(
                "relative cursor-pointer transition-all",
                isRecommended && "border-primary ring-2 ring-primary/20",
                isSelected && "bg-primary/5"
              )}
              onClick={() => handleVariantSelect(variant.id)}
            >
              {isRecommended && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge className="bg-primary text-primary-foreground">
                    Recommended
                  </Badge>
                </div>
              )}

              <CardHeader className="text-center pb-2">
                <div
                  className={cn(
                    "mx-auto w-12 h-12 rounded-full flex items-center justify-center",
                    isSelected ? "bg-primary text-primary-foreground" : "bg-muted"
                  )}
                >
                  {variant.icon}
                </div>
                <CardTitle className="text-lg">{variant.name}</CardTitle>
                <p className="text-xs text-muted-foreground">{variant.tier} Tier</p>
              </CardHeader>

              <CardContent className="space-y-4">
                <div className="text-center">
                  <span className="text-3xl font-bold">${price}</span>
                  <span className="text-muted-foreground">/mo</span>
                  {input.billingCycle === "annual" && (
                    <p className="text-xs text-green-600">Billed annually</p>
                  )}
                </div>

                <ul className="space-y-2">
                  {variant.features.map((feature, index) => (
                    <li
                      key={index}
                      className="flex items-start gap-2 text-sm"
                    >
                      <Check className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                      {feature}
                    </li>
                  ))}
                </ul>

                <Button
                  variant={isSelected ? "default" : "outline"}
                  className="w-full"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleVariantSelect(variant.id);
                  }}
                >
                  {isSelected ? "Selected" : "Select Plan"}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Summary */}
      {selectedVariant && (
        <Card className="bg-muted/50">
          <CardContent className="pt-4">
            <div className="flex flex-wrap justify-between gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Selected Plan</p>
                <p className="font-semibold">
                  {VARIANTS.find((v) => v.id === selectedVariant)?.name}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Monthly Price</p>
                <p className="font-semibold">
                  ${calculatePrice(VARIANTS.find((v) => v.id === selectedVariant)!)}
                  /mo
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Max Refund</p>
                <p className="font-semibold">
                  ${VARIANTS.find((v) => v.id === selectedVariant)?.maxRefund}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Concurrent Calls</p>
                <p className="font-semibold">
                  {VARIANTS.find((v) => v.id === selectedVariant)?.concurrentCalls}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default PricingCalculator;
