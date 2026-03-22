"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check, X } from "lucide-react";

/**
 * Feature item for variant card.
 */
export interface VariantFeature {
  /** Feature name */
  name: string;
  /** Whether feature is included */
  included: boolean;
  /** Optional value (e.g., "2 calls") */
  value?: string;
}

/**
 * Variant card props.
 */
export interface VariantCardProps {
  /** Variant ID (mini, parwa, parwa_high) */
  variantId: string;
  /** Display title */
  title: string;
  /** Tier badge text */
  tier: string;
  /** Tier badge variant */
  tierVariant?: "default" | "secondary" | "outline";
  /** Price in dollars */
  price: number;
  /** Billing period */
  billingPeriod?: "month" | "year";
  /** Target audience description */
  targetAudience: string;
  /** List of features */
  features: VariantFeature[];
  /** Whether this is the recommended/popular plan */
  isPopular?: boolean;
  /** Whether this card is selected */
  isSelected?: boolean;
  /** Select button text */
  selectButtonText?: string;
  /** Callback when select is clicked */
  onSelect?: () => void;
  /** Additional CSS classes */
  className?: string;
  /** Whether the card is in a loading state */
  isLoading?: boolean;
}

/**
 * Base variant card component for PARWA pricing plans.
 *
 * Displays variant information including:
 * - Name and tier badge
 * - Pricing
 * - Feature list with included/excluded items
 * - Select button
 *
 * @example
 * ```tsx
 * <VariantCard
 *   variantId="mini"
 *   title="Mini PARWA"
 *   tier="Light"
 *   price={49}
 *   targetAudience="Small businesses"
 *   features={[
 *     { name: "Concurrent calls", value: "2", included: true },
 *     { name: "Refund limit", value: "$50", included: true },
 *   ]}
 *   onSelect={() => handleSelect("mini")}
 * />
 * ```
 */
export function VariantCard({
  variantId,
  title,
  tier,
  tierVariant = "secondary",
  price,
  billingPeriod = "month",
  targetAudience,
  features,
  isPopular = false,
  isSelected = false,
  selectButtonText = "Get Started",
  onSelect,
  className,
  isLoading = false,
}: VariantCardProps) {
  return (
    <Card
      className={cn(
        "relative flex flex-col transition-all duration-300",
        "hover:shadow-lg hover:scale-[1.02]",
        isPopular && "ring-2 ring-primary shadow-lg",
        isSelected && "ring-2 ring-primary bg-primary/5",
        className
      )}
      data-variant-id={variantId}
      data-testid={`variant-card-${variantId}`}
    >
      {/* Popular badge */}
      {isPopular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <Badge variant="default" className="px-3 py-1">
            Most Popular
          </Badge>
        </div>
      )}

      <CardHeader className="text-center pb-4">
        {/* Tier badge */}
        <Badge variant={tierVariant} className="w-fit mx-auto mb-2">
          {tier}
        </Badge>

        {/* Title */}
        <CardTitle className="text-2xl font-bold">{title}</CardTitle>

        {/* Target audience */}
        <CardDescription className="text-sm">
          {targetAudience}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex-1">
        {/* Pricing */}
        <div className="text-center mb-6">
          <div className="flex items-baseline justify-center gap-1">
            <span className="text-4xl font-bold">${price}</span>
            <span className="text-muted-foreground">
              /{billingPeriod}
            </span>
          </div>
        </div>

        {/* Features list */}
        <ul className="space-y-3" role="list" aria-label={`${title} features`}>
          {features.map((feature, index) => (
            <li
              key={`${feature.name}-${index}`}
              className={cn(
                "flex items-center gap-3 text-sm",
                !feature.included && "text-muted-foreground"
              )}
            >
              {feature.included ? (
                <Check className="h-4 w-4 text-green-500 shrink-0" aria-hidden="true" />
              ) : (
                <X className="h-4 w-4 text-muted-foreground shrink-0" aria-hidden="true" />
              )}
              <span>
                {feature.name}
                {feature.value && (
                  <span className="font-medium ml-1">{feature.value}</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      </CardContent>

      <CardFooter className="pt-4">
        <Button
          className="w-full"
          variant={isPopular ? "default" : "outline"}
          onClick={onSelect}
          disabled={isLoading}
          aria-label={`Select ${title} plan`}
        >
          {isLoading ? "Loading..." : selectButtonText}
        </Button>
      </CardFooter>
    </Card>
  );
}

export default VariantCard;
