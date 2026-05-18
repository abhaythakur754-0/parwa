'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import QuantitySelector from './QuantitySelector';
import { Ticket, DollarSign } from 'lucide-react';

export interface VariantData {
  id: string;
  name: string;
  description: string;
  ticketsPerMonth: number;
  pricePerMonth: number;
}

export interface VariantCardProps {
  variant: VariantData;
  quantity: number;
  onQuantityChange: (quantity: number) => void;
}

export default function VariantCard({
  variant,
  quantity,
  onQuantityChange,
}: VariantCardProps) {
  const isSelected = quantity > 0;

  return (
    <Card
      className={cn(
        'relative flex flex-col rounded-2xl transition-all duration-300 overflow-hidden',
        isSelected
          ? 'bg-[#0F1A16] border-emerald-500/30 shadow-lg shadow-emerald-500/5'
          : 'bg-[#111111] border-white/[0.06] hover:border-white/[0.12] hover:bg-[#141414]'
      )}
    >
      {/* Top accent line when selected */}
      {isSelected && (
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-emerald-500 via-emerald-400 to-emerald-500" />
      )}

      <CardContent className="p-5 flex flex-col gap-3.5">
        {/* Header: Name + Badge */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h4
              className={cn(
                'text-base font-semibold leading-tight transition-colors duration-200',
                isSelected ? 'text-white' : 'text-gray-300'
              )}
            >
              {variant.name}
            </h4>
            <p className="text-gray-500 text-xs mt-1 leading-relaxed line-clamp-2">
              {variant.description}
            </p>
          </div>

          {isSelected && (
            <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/25 text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0">
              Active
            </Badge>
          )}
        </div>

        {/* Specs Row */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <Ticket className="w-3.5 h-3.5 text-gray-500" />
            <span className="text-xs text-gray-400 tabular-nums">
              {variant.ticketsPerMonth.toLocaleString()}/mo
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <DollarSign className="w-3.5 h-3.5 text-emerald-500/60" />
            <span className="text-xs text-emerald-400/80 font-medium tabular-nums">
              ${variant.pricePerMonth}/unit
            </span>
          </div>
        </div>

        {/* Quantity Selector */}
        <div className="pt-1 border-t border-white/[0.04]">
          <QuantitySelector
            quantity={quantity}
            onIncrement={() => onQuantityChange(Math.min(quantity + 1, 10))}
            onDecrement={() => onQuantityChange(Math.max(quantity - 1, 0))}
            max={10}
            min={0}
            pricePerUnit={variant.pricePerMonth}
          />
        </div>
      </CardContent>
    </Card>
  );
}
