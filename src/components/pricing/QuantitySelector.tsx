'use client';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Minus, Plus } from 'lucide-react';

export interface QuantitySelectorProps {
  quantity: number;
  onIncrement: () => void;
  onDecrement: () => void;
  max?: number;
  min?: number;
  pricePerUnit: number;
}

export default function QuantitySelector({
  quantity,
  onIncrement,
  onDecrement,
  max = 10,
  min = 0,
  pricePerUnit,
}: QuantitySelectorProps) {
  const total = quantity * pricePerUnit;

  return (
    <div className="flex items-center justify-between gap-3">
      {/* Quantity Controls */}
      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="icon"
          onClick={onDecrement}
          disabled={quantity <= min}
          className={cn(
            'h-8 w-8 rounded-lg transition-all duration-200',
            quantity > 0
              ? 'border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:border-red-500/50 hover:text-red-300'
              : 'border-white/10 bg-white/5 text-gray-600 hover:bg-white/10 hover:text-gray-400'
          )}
          aria-label="Decrease quantity"
        >
          <Minus className="h-3.5 w-3.5" />
        </Button>

        <span
          className={cn(
            'w-10 text-center text-sm font-semibold tabular-nums transition-colors duration-200',
            quantity > 0 ? 'text-white' : 'text-gray-600'
          )}
        >
          {quantity}
        </span>

        <Button
          variant="outline"
          size="icon"
          onClick={onIncrement}
          disabled={quantity >= max}
          className={cn(
            'h-8 w-8 rounded-lg transition-all duration-200',
            'border-emerald-500/30 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 hover:border-emerald-500/50 hover:text-emerald-300',
            quantity >= max && 'opacity-50 cursor-not-allowed'
          )}
          aria-label="Increase quantity"
        >
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Total for this variant */}
      <span
        className={cn(
          'text-sm font-bold tabular-nums transition-all duration-200',
          quantity > 0 ? 'text-emerald-400' : 'text-gray-700'
        )}
      >
        {quantity > 0 ? `$${total}` : '—'}
      </span>
    </div>
  );
}
