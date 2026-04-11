'use client';

import React from 'react';
import { Minus, Plus } from 'lucide-react';

/**
 * QuantitySelector Component
 *
 * Premium [-] N [+] quantity selector with:
 * - Min/max bounds
 * - Disabled state
 * - Glass morphism styling
 * - Active glow when value > 0
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
  const isActive = value > 0;

  return (
    <div className="flex items-center gap-1.5">
      {/* Decrement Button */}
      <button
        type="button"
        onClick={handleDecrement}
        disabled={isDecrementDisabled}
        className={`
          w-9 h-9 sm:w-10 sm:h-10 rounded-lg border flex items-center justify-center
          transition-all duration-200 backdrop-blur-sm
          ${
            isDecrementDisabled
              ? 'border-white/10 bg-white/5 text-orange-200/20 cursor-not-allowed'
              : isActive
                ? 'border-orange-500/30 bg-orange-500/10 text-orange-400 hover:border-orange-400 hover:bg-orange-500/20 active:scale-90'
                : 'border-white/10 bg-white/5 text-orange-200/60 hover:border-white/20 hover:bg-white/10 active:scale-90'
          }
        `}
        aria-label="Decrease quantity"
      >
        <Minus className="w-4 h-4" />
      </button>

      {/* Value Display */}
      <div
        className={`
          w-14 h-9 sm:w-16 sm:h-10 rounded-lg border
          flex items-center justify-center
          font-bold text-base sm:text-lg tabular-nums
          transition-all duration-200 backdrop-blur-sm
          ${
            isActive
              ? 'border-orange-500/30 bg-orange-500/10 text-orange-400 shadow-sm shadow-orange-600/10'
              : disabled
                ? 'border-white/10 bg-white/5 text-orange-200/20'
                : 'border-white/10 bg-white/5 text-orange-200/60'
          }
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
          w-9 h-9 sm:w-10 sm:h-10 rounded-lg border flex items-center justify-center
          transition-all duration-200 backdrop-blur-sm
          ${
            isIncrementDisabled
              ? 'border-white/10 bg-white/5 text-orange-200/20 cursor-not-allowed'
              : isActive
                ? 'border-orange-500/30 bg-orange-500/10 text-orange-400 hover:border-orange-400 hover:bg-orange-500/20 active:scale-90'
                : 'border-white/10 bg-white/5 text-orange-200/60 hover:border-white/20 hover:bg-white/10 active:scale-90'
          }
        `}
        aria-label="Increase quantity"
      >
        <Plus className="w-4 h-4" />
      </button>
    </div>
  );
}
