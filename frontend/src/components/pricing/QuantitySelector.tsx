'use client';

import React from 'react';
import { Minus, Plus } from 'lucide-react';

/**
 * QuantitySelector Component
 *
 * Day 6: Pricing Page - Quantity Selector
 * Simple [-] N [+] style quantity selector with:
 * - Min/max bounds
 * - Disabled state
 * - Accessible controls
 */

interface QuantitySelectorProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  disabled?: boolean;
}

export function QuantitySelector({
  value,
  onChange,
  min = 0,
  max = 10,
  disabled = false,
}: QuantitySelectorProps) {
  const handleDecrement = () => {
    if (value > min && !disabled) {
      onChange(value - 1);
    }
  };

  const handleIncrement = () => {
    if (value < max && !disabled) {
      onChange(value + 1);
    }
  };

  const isDecrementDisabled = disabled || value <= min;
  const isIncrementDisabled = disabled || value >= max;

  return (
    <div className="flex items-center gap-1">
      {/* Decrement Button */}
      <button
        type="button"
        onClick={handleDecrement}
        disabled={isDecrementDisabled}
        className={`
          w-10 h-10 rounded-lg border flex items-center justify-center
          transition-all duration-200
          ${isDecrementDisabled
            ? 'border-white/10 bg-white/5 text-white/30 cursor-not-allowed'
            : 'border-white/20 bg-surface hover:border-teal-500/50 hover:bg-teal-500/10 text-white active:scale-95'
          }
        `}
        aria-label="Decrease quantity"
      >
        <Minus className="w-4 h-4" />
      </button>

      {/* Value Display */}
      <div
        className={`
          w-16 h-10 rounded-lg border border-white/10 bg-surface/50
          flex items-center justify-center
          font-semibold text-lg
          ${disabled ? 'text-white/30' : 'text-white'}
        `}
        aria-label={`Current quantity: ${value}`}
        role="status"
      >
        {value}
      </div>

      {/* Increment Button */}
      <button
        type="button"
        onClick={handleIncrement}
        disabled={isIncrementDisabled}
        className={`
          w-10 h-10 rounded-lg border flex items-center justify-center
          transition-all duration-200
          ${isIncrementDisabled
            ? 'border-white/10 bg-white/5 text-white/30 cursor-not-allowed'
            : 'border-white/20 bg-surface hover:border-teal-500/50 hover:bg-teal-500/10 text-white active:scale-95'
          }
        `}
        aria-label="Increase quantity"
      >
        <Plus className="w-4 h-4" />
      </button>
    </div>
  );
}
