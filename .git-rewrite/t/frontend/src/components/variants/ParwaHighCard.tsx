"use client";

import * as React from "react";
import { VariantCard, VariantFeature } from "./VariantCard";

/**
 * PARWA High variant card props.
 */
export interface ParwaHighCardProps {
  /** Whether this card is selected */
  isSelected?: boolean;
  /** Callback when select is clicked */
  onSelect?: () => void;
  /** Additional CSS classes */
  className?: string;
  /** Whether the card is in a loading state */
  isLoading?: boolean;
}

/**
 * PARWA High features configuration.
 *
 * Based on variants/parwa_high/config.py:
 * - 10 concurrent calls max (CRITICAL)
 * - $2000 refund limit (CRITICAL)
 * - 50% escalation threshold (CRITICAL)
 * - Can execute refunds with approval
 * - Channels: FAQ, Email, Chat, SMS, Voice, Video
 * - Heavy tier AI
 * - Customer success with churn prediction
 * - Team coordination (5 teams)
 * - HIPAA compliance support
 */
const HIGH_FEATURES: VariantFeature[] = [
  { name: "Concurrent calls", value: "10", included: true },
  { name: "Refund limit", value: "$2000", included: true },
  { name: "Escalation threshold", value: "50%", included: true },
  { name: "FAQ support", included: true },
  { name: "Email support", included: true },
  { name: "Chat support", included: true },
  { name: "SMS support", included: true },
  { name: "Voice support", included: true },
  { name: "Video support", value: "(60 min)", included: true },
  { name: "Can execute refunds", value: "(with approval)", included: true },
  { name: "Learning from feedback", included: true },
  { name: "Advanced analytics", included: true },
  { name: "HIPAA compliance", included: true },
  { name: "Churn prediction", included: true },
  { name: "Team coordination", value: "(5 teams)", included: true },
  { name: "Priority support", included: true },
];

/**
 * PARWA High variant card component.
 *
 * Enterprise-tier plan with:
 * - $4000/month pricing
 * - Heavy tier AI
 * - All channel support including extended Video
 * - 10 concurrent voice calls
 * - $2000 refund limit (can execute with approval)
 * - 50% escalation threshold
 * - HIPAA compliance
 * - Customer success with churn prediction
 * - Team coordination for up to 5 teams
 *
 * @example
 * ```tsx
 * <ParwaHighCard
 *   isSelected={selectedVariant === "parwa_high"}
 *   onSelect={() => handleSelect("parwa_high")}
 * />
 * ```
 */
export function ParwaHighCard({
  isSelected = false,
  onSelect,
  className,
  isLoading = false,
}: ParwaHighCardProps) {
  return (
    <VariantCard
      variantId="parwa_high"
      title="PARWA High"
      tier="Heavy"
      tierVariant="default"
      price={4000}
      targetAudience="Enterprise-grade support with advanced AI capabilities"
      features={HIGH_FEATURES}
      isSelected={isSelected}
      onSelect={onSelect}
      selectButtonText="Contact Sales"
      className={className}
      isLoading={isLoading}
    />
  );
}

/**
 * Get PARWA High configuration summary.
 */
export function getParwaHighConfig() {
  return {
    variantId: "parwa_high",
    name: "PARWA High",
    tier: "Heavy",
    price: 4000,
    maxConcurrentCalls: 10,
    refundLimit: 2000,
    escalationThreshold: 50,
    supportedChannels: ["faq", "email", "chat", "sms", "voice", "video"],
    aiTier: "heavy",
    targetAudience: "Enterprise",
    features: {
      canExecuteRefunds: true,
      hipaaCompliance: true,
      churnPrediction: true,
      teamCoordination: 5,
      maxVideoDuration: 60,
    },
  };
}

export default ParwaHighCard;
