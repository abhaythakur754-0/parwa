'use client';

import React from 'react';
import {
  Check,
  Ticket,
  Eye,
  MessageCircle,
  Star,
  Zap,
} from 'lucide-react';
import { QuantitySelector } from './QuantitySelector';

/**
 * VariantCard Component
 *
 * Glass morphism card with:
 * - Name, description, features with checkmarks
 * - Tickets/month (icon + number)
 * - Price/month displayed prominently
 * - "Most Popular" badge
 * - 3 buttons: Demo (Eye), Chat (MessageCircle), QuantitySelector
 * - Active glow when quantity > 0
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
  onDemo?: (variantId: string) => void;
  onChat?: (variantId: string) => void;
  maxQuantity?: number;
  disabled?: boolean;
}

export function VariantCard({
  variant,
  quantity,
  onQuantityChange,
  onDemo,
  onChat,
  maxQuantity = 10,
  disabled = false,
}: VariantCardProps) {
  const monthlyTotal = variant.pricePerMonth * quantity;
  const ticketsTotal = variant.ticketsPerMonth * quantity;
  const isActive = quantity > 0;

  return (
    <div
      className={`
        relative rounded-xl border-2 p-5 sm:p-6
        transition-all duration-300 ease-out
        backdrop-blur-xl
        ${
          isActive
            ? 'border-emerald-500/30 bg-emerald-500/8 shadow-lg shadow-emerald-600/15'
            : variant.popular
              ? 'border-emerald-500/15 bg-white/[0.05] hover:border-emerald-500/30'
              : 'border-white/10 bg-white/[0.05] hover:border-white/20 hover:bg-white/[0.08]'
        }
        ${!isActive && !disabled ? 'hover:-translate-y-0.5' : ''}
      `}
    >
      {/* Popular Badge */}
      {variant.popular && (
        <div className="absolute -top-3 left-4 sm:left-6">
          <span className="inline-flex items-center gap-1 px-3 py-1 text-xs font-bold bg-gradient-to-r from-gold-400 to-gold-500 text-navy-900 rounded-full shadow-md shadow-gold-500/20">
            <Star className="w-3 h-3" fill="currentColor" />
            Most Popular
          </span>
        </div>
      )}

      {/* Header: Name + Description */}
      <div className="mb-4 mt-1">
        <h3 className="text-base sm:text-lg font-bold text-white mb-1">
          {variant.name}
        </h3>
        <p className="text-xs sm:text-sm text-emerald-200/50 leading-relaxed">
          {variant.description}
        </p>
      </div>

      {/* Features with Checkmarks */}
      <div className="space-y-2 mb-5">
        {variant.features.map((feature, index) => (
          <div key={index} className="flex items-center gap-2.5">
            <div
              className={`w-4.5 h-4.5 rounded-full flex items-center justify-center flex-shrink-0 ${
                isActive ? 'bg-emerald-500/20' : 'bg-white/10'
              }`}
            >
              <Check
                className={`w-3 h-3 ${
                  isActive ? 'text-emerald-400' : 'text-emerald-200/30'
                }`}
                strokeWidth={3}
              />
            </div>
            <span
              className={`text-xs sm:text-sm leading-snug ${
                isActive ? 'text-gray-100' : 'text-emerald-200/50'
              }`}
            >
              {feature}
            </span>
          </div>
        ))}
      </div>

      {/* Divider */}
      <div className="h-px bg-gradient-to-r from-transparent via-white/10 to-transparent mb-4" />

      {/* Tickets + Price Row */}
      <div className="flex items-end justify-between mb-5">
        {/* Tickets per month */}
        <div className="flex items-center gap-2">
          <div
            className={`w-8 h-8 rounded-lg flex items-center justify-center ${
              isActive ? 'bg-emerald-500/20' : 'bg-white/10'
            }`}
          >
            <Ticket
              className={`w-4 h-4 ${
                isActive ? 'text-emerald-400' : 'text-emerald-200/30'
              }`}
            />
          </div>
          <div>
            <span
              className={`text-lg sm:text-xl font-bold ${
                isActive ? 'text-emerald-400' : 'text-gray-100'
              }`}
            >
              {variant.ticketsPerMonth.toLocaleString()}
            </span>
            <span className="block text-[10px] sm:text-xs text-emerald-200/30">
              tickets/mo
            </span>
          </div>
        </div>

        {/* Price */}
        <div className="text-right">
          <div className="flex items-baseline gap-0.5">
            <span
              className={`text-xl sm:text-2xl font-extrabold ${
                isActive ? 'text-white' : 'text-gray-100'
              }`}
            >
              ${variant.pricePerMonth}
            </span>
          </div>
          <span className="block text-[10px] sm:text-xs text-emerald-200/30">
            per month
          </span>
        </div>
      </div>

      {/* Divider */}
      <div className="h-px bg-gradient-to-r from-transparent via-white/10 to-transparent mb-4" />

      {/* Action Buttons */}
      <div className="flex items-center gap-2">
        {/* Demo Button */}
        <button
          type="button"
          onClick={() => onDemo?.(variant.id)}
          disabled={disabled}
          className={`
            w-9 h-9 sm:w-10 sm:h-10 rounded-lg border flex items-center justify-center
            transition-all duration-200 flex-shrink-0
            border-white/10 bg-white/5 text-emerald-200/50
            hover:border-sky-500/30 hover:bg-sky-500/10 hover:text-sky-400
            active:scale-90
            ${disabled ? 'opacity-40 cursor-not-allowed' : ''}
          `}
          aria-label={`Try demo for ${variant.name}`}
          title="Try Demo"
        >
          <Eye className="w-4 h-4" />
        </button>

        {/* Chat Button */}
        <button
          type="button"
          onClick={() => onChat?.(variant.id)}
          disabled={disabled}
          className={`
            w-9 h-9 sm:w-10 sm:h-10 rounded-lg border flex items-center justify-center
            transition-all duration-200 flex-shrink-0
            border-white/10 bg-white/5 text-emerald-200/50
            hover:border-emerald-500/30 hover:bg-emerald-500/10 hover:text-emerald-400
            active:scale-90
            ${disabled ? 'opacity-40 cursor-not-allowed' : ''}
          `}
          aria-label={`Chat about ${variant.name}`}
          title="Live Chat"
        >
          <MessageCircle className="w-4 h-4" />
        </button>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Quantity Selector */}
        <QuantitySelector
          value={quantity}
          onChange={(newQty) => onQuantityChange(variant.id, newQty)}
          max={maxQuantity}
          disabled={disabled}
        />
      </div>

      {/* Active state total */}
      {isActive && (
        <div
          className="mt-3 pt-3 border-t border-emerald-600/20 flex items-center justify-between"
        >
          <div className="flex items-center gap-1.5 text-emerald-500/80">
            <Zap className="w-3.5 h-3.5" />
            <span className="text-xs font-medium">Monthly subtotal</span>
          </div>
          <span className="text-sm font-bold text-emerald-400">
            ${monthlyTotal}
            <span className="text-xs font-normal text-emerald-500/60 ml-1">
              /mo
            </span>
          </span>
        </div>
      )}
    </div>
  );
}
