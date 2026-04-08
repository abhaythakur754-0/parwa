'use client';

import React from 'react';
import { Check, Ticket } from 'lucide-react';
import { QuantitySelector } from './QuantitySelector';

/**
 * VariantCard Component
 *
 * Day 6: Pricing Page - Variant Card
 * Displays a pricing variant with:
 * - Variant name and description
 * - Tickets per month
 * - Price per month
 * - Quantity selector
 * - Features list
 */

export interface PricingVariant {
  id: string;
  name: string;
  description: string;
  ticketsPerMonth: number;
  pricePerMonth: number;
  features: string[];
  popular?: boolean;
}

interface VariantCardProps {
  variant: PricingVariant;
  quantity: number;
  onQuantityChange: (variantId: string, quantity: number) => void;
  maxQuantity?: number;
  disabled?: boolean;
}

export function VariantCard({
  variant,
  quantity,
  onQuantityChange,
  maxQuantity = 10,
  disabled = false,
}: VariantCardProps) {
  const monthlyTotal = variant.pricePerMonth * quantity;
  const ticketsTotal = variant.ticketsPerMonth * quantity;

  return (
    <div
      className={`
        relative card card-padding transition-all duration-300
        ${variant.popular
          ? 'border-teal-500/50 bg-teal-500/5'
          : 'border-white/10 bg-surface/30'
        }
        ${quantity > 0 ? 'ring-2 ring-teal-500/30' : ''}
        hover:border-teal-500/30
      `}
    >
      {/* Popular Badge */}
      {variant.popular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="px-3 py-1 text-xs font-semibold bg-teal-500 text-white rounded-full">
            Most Popular
          </span>
        </div>
      )}

      {/* Header */}
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-white mb-1">
          {variant.name}
        </h3>
        <p className="text-sm text-white/50">
          {variant.description}
        </p>
      </div>

      {/* Ticket Allowance */}
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-teal-500/20 flex items-center justify-center">
          <Ticket className="w-4 h-4 text-teal-400" />
        </div>
        <div>
          <span className="text-2xl font-bold text-white">
            {ticketsTotal.toLocaleString()}
          </span>
          <span className="text-white/50 text-sm ml-1">tickets/month</span>
        </div>
      </div>

      {/* Price */}
      <div className="mb-6">
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold text-white">
            ${monthlyTotal}
          </span>
          <span className="text-white/50 text-sm">/month</span>
        </div>
        {quantity > 1 && (
          <p className="text-xs text-white/40 mt-1">
            ${variant.pricePerMonth} each × {quantity} variants
          </p>
        )}
      </div>

      {/* Quantity Selector */}
      <div className="mb-6">
        <label className="label">Quantity</label>
        <QuantitySelector
          value={quantity}
          onChange={(newQty) => onQuantityChange(variant.id, newQty)}
          max={maxQuantity}
          disabled={disabled}
        />
      </div>

      {/* Features */}
      <div className="space-y-2">
        {variant.features.map((feature, index) => (
          <div key={index} className="flex items-start gap-2">
            <Check className="w-4 h-4 text-teal-400 mt-0.5 flex-shrink-0" />
            <span className="text-sm text-white/70">{feature}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
