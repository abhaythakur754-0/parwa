"use client";

import * as React from "react";
import { VariantCard, VariantFeature } from "./VariantCard";

/**
 * Mini PARWA variant card props.
 */
export interface MiniCardProps {
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
 * Mini PARWA features configuration.
 *
 * Based on variants/mini/config.py:
 * - 2 concurrent calls max
 * - $50 refund limit
 * - 70% escalation threshold
 * - Channels: FAQ, Email, Chat, SMS
 * - Light tier AI
 */
const MINI_FEATURES: VariantFeature[] = [
  { name: "Concurrent calls", value: "2", included: true },
  { name: "Refund limit", value: "$50", included: true },
  { name: "Escalation threshold", value: "70%", included: true },
  { name: "FAQ support", included: true },
  { name: "Email support", included: true },
  { name: "Chat support", included: true },
  { name: "SMS support", included: true },
  { name: "Voice support", included: false },
  { name: "Video support", included: false },
  { name: "Analytics dashboard", included: false },
  { name: "HIPAA compliance", included: false },
];

/**
 * Mini PARWA variant card component.
 *
 * Entry-level plan for small businesses with:
 * - $1000/month pricing
 * - Light tier AI
 * - Basic channel support (FAQ, Email, Chat, SMS)
 * - 2 concurrent voice calls
 * - $50 refund limit
 * - 70% escalation threshold
 *
 * @example
 * ```tsx
 * <MiniCard
 *   isSelected={selectedVariant === "mini"}
 *   onSelect={() => handleSelect("mini")}
 * />
 * ```
 */
export function MiniCard({
  isSelected = false,
  onSelect,
  className,
  isLoading = false,
}: MiniCardProps) {
  return (
    <VariantCard
      variantId="mini"
      title="Mini PARWA"
      tier="Light"
      tierVariant="outline"
      price={1000}
      targetAudience="Perfect for small businesses getting started with AI support"
      features={MINI_FEATURES}
      isSelected={isSelected}
      onSelect={onSelect}
      selectButtonText="Start Free Trial"
      className={className}
      isLoading={isLoading}
    />
  );
}

/**
 * Get Mini PARWA configuration summary.
 */
export function getMiniConfig() {
  return {
    variantId: "mini",
    name: "Mini PARWA",
    tier: "Light",
    price: 1000,
    maxConcurrentCalls: 2,
    refundLimit: 50,
    escalationThreshold: 70,
    supportedChannels: ["faq", "email", "chat", "sms"],
    aiTier: "light",
    targetAudience: "Small businesses",
  };
}

export default MiniCard;
