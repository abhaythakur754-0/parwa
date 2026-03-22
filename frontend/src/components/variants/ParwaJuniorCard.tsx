"use client";

import * as React from "react";
import { VariantCard, VariantFeature } from "./VariantCard";

/**
 * PARWA Junior variant card props.
 */
export interface ParwaJuniorCardProps {
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
 * PARWA Junior features configuration.
 *
 * Based on variants/parwa/config.py:
 * - 5 concurrent calls max
 * - $500 refund limit
 * - 60% escalation threshold
 * - Channels: FAQ, Email, Chat, SMS, Voice, Video
 * - Medium tier AI
 * - Returns APPROVE/REVIEW/DENY with reasoning
 */
const JUNIOR_FEATURES: VariantFeature[] = [
  { name: "Concurrent calls", value: "5", included: true },
  { name: "Refund limit", value: "$500", included: true },
  { name: "Escalation threshold", value: "60%", included: true },
  { name: "FAQ support", included: true },
  { name: "Email support", included: true },
  { name: "Chat support", included: true },
  { name: "SMS support", included: true },
  { name: "Voice support", included: true },
  { name: "Video support", included: true },
  { name: "APPROVE/REVIEW/DENY decisions", included: true },
  { name: "Learning from feedback", included: true },
  { name: "Analytics dashboard", included: true },
  { name: "HIPAA compliance", included: false },
  { name: "Churn prediction", included: false },
  { name: "Team coordination", included: false },
];

/**
 * PARWA Junior variant card component.
 *
 * Medium-tier plan for growing teams with:
 * - $2500/month pricing
 * - Medium tier AI
 * - All channel support including Voice and Video
 * - 5 concurrent voice calls
 * - $500 refund limit
 * - 60% escalation threshold
 * - Returns APPROVE/REVIEW/DENY with reasoning
 *
 * @example
 * ```tsx
 * <ParwaJuniorCard
 *   isSelected={selectedVariant === "parwa"}
 *   onSelect={() => handleSelect("parwa")}
 * />
 * ```
 */
export function ParwaJuniorCard({
  isSelected = false,
  onSelect,
  className,
  isLoading = false,
}: ParwaJuniorCardProps) {
  return (
    <VariantCard
      variantId="parwa"
      title="PARWA Junior"
      tier="Medium"
      tierVariant="secondary"
      price={2500}
      targetAudience="Ideal for growing teams that need more power"
      features={JUNIOR_FEATURES}
      isPopular={true}
      isSelected={isSelected}
      onSelect={onSelect}
      selectButtonText="Start Free Trial"
      className={className}
      isLoading={isLoading}
    />
  );
}

/**
 * Get PARWA Junior configuration summary.
 */
export function getParwaJuniorConfig() {
  return {
    variantId: "parwa",
    name: "PARWA Junior",
    tier: "Medium",
    price: 2500,
    maxConcurrentCalls: 5,
    refundLimit: 500,
    escalationThreshold: 60,
    supportedChannels: ["faq", "email", "chat", "sms", "voice", "video"],
    aiTier: "medium",
    targetAudience: "Growing teams",
    features: {
      approveReviewDeny: true,
      learning: true,
      analytics: true,
    },
  };
}

export default ParwaJuniorCard;
