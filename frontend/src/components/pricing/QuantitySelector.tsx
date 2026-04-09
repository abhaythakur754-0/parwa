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
              ? 'border-gray-200 bg-gray-50 text-gray-300 cursor-not-allowed'
              : isActive
                ? 'border-emerald-300 bg-emerald-50 text-emerald-700 hover:border-emerald-400 hover:bg-emerald-100 active:scale-90'
                : 'border-gray-200 bg-gray-50 text-gray-700 hover:border-gray-300 hover:bg-gray-100 active:scale-90'
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
              ? 'border-emerald-300 bg-emerald-50 text-emerald-700 shadow-sm shadow-emerald-600/10'
              : disabled
                ? 'border-gray-200 bg-gray-50 text-gray-300'
                : 'border-gray-200 bg-gray-50 text-gray-700'
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
              ? 'border-gray-200 bg-gray-50 text-gray-300 cursor-not-allowed'
              : isActive
                ? 'border-emerald-300 bg-emerald-50 text-emerald-700 hover:border-emerald-400 hover:bg-emerald-100 active:scale-90'
                : 'border-gray-200 bg-gray-50 text-gray-700 hover:border-gray-300 hover:bg-gray-100 active:scale-90'
          }
        `}
        aria-label="Increase quantity"
      >
        <Plus className="w-4 h-4" />
      </button>
    </div>
  );
}
