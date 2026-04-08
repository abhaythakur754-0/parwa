'use client';

import React from 'react';
import {
  ShoppingBag,
  Code,
  Truck,
  Sparkles,
} from 'lucide-react';

/**
 * IndustrySelector Component
 *
 * Day 6: Pricing Page - Industry Selection
 * Allows users to select from 4 industries to see relevant pricing variants.
 *
 * Industries:
 * 1. E-commerce - Teal theme
 * 2. SaaS - Navy/Silver theme
 * 3. Logistics - Charcoal/Orange theme
 * 4. Others - Custom flow
 */

export type Industry = 'ecommerce' | 'saas' | 'logistics' | 'others';

export interface IndustryOption {
  id: Industry;
  name: string;
  description: string;
  icon: React.ElementType;
  color: string;
  hoverColor: string;
  borderColor: string;
  selectedBg: string;
  selectedCheckBg: string;
}

// Using static class names for Tailwind JIT compatibility
const industries: IndustryOption[] = [
  {
    id: 'ecommerce',
    name: 'E-commerce',
    description: 'Online retail, marketplaces, D2C brands',
    icon: ShoppingBag,
    color: 'text-teal-400',
    hoverColor: 'hover:border-teal-500/50 hover:bg-teal-500/10',
    borderColor: 'border-teal-500',
    selectedBg: 'bg-teal-500/20',
    selectedCheckBg: 'bg-teal-500',
  },
  {
    id: 'saas',
    name: 'SaaS',
    description: 'Software companies, tech startups',
    icon: Code,
    color: 'text-blue-400',
    hoverColor: 'hover:border-blue-500/50 hover:bg-blue-500/10',
    borderColor: 'border-blue-500',
    selectedBg: 'bg-blue-500/20',
    selectedCheckBg: 'bg-blue-500',
  },
  {
    id: 'logistics',
    name: 'Logistics',
    description: 'Shipping, warehousing, supply chain',
    icon: Truck,
    color: 'text-orange-400',
    hoverColor: 'hover:border-orange-500/50 hover:bg-orange-500/10',
    borderColor: 'border-orange-500',
    selectedBg: 'bg-orange-500/20',
    selectedCheckBg: 'bg-orange-500',
  },
  {
    id: 'others',
    name: 'Others',
    description: 'Healthcare, Finance, Education, etc.',
    icon: Sparkles,
    color: 'text-purple-400',
    hoverColor: 'hover:border-purple-500/50 hover:bg-purple-500/10',
    borderColor: 'border-purple-500',
    selectedBg: 'bg-purple-500/20',
    selectedCheckBg: 'bg-purple-500',
  },
];

interface IndustrySelectorProps {
  selectedIndustry: Industry | null;
  onSelect: (industry: Industry) => void;
  disabled?: boolean;
}

export function IndustrySelector({
  selectedIndustry,
  onSelect,
  disabled = false,
}: IndustrySelectorProps) {
  return (
    <div className="w-full">
      <h2 className="text-xl font-semibold text-white mb-4">
        Select Your Industry
      </h2>
      <p className="text-white/60 mb-6">
        Choose your industry to see relevant support ticket variants
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {industries.map((industry) => {
          const isSelected = selectedIndustry === industry.id;
          const Icon = industry.icon;

          return (
            <button
              key={industry.id}
              type="button"
              disabled={disabled}
              onClick={() => onSelect(industry.id)}
              className={`
                relative p-4 rounded-xl border-2 transition-all duration-300 text-left
                ${isSelected
                  ? `${industry.borderColor} ${industry.selectedBg}`
                  : 'border-white/10 bg-surface/30'
                }
                ${industry.hoverColor}
                ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
              `}
              aria-pressed={isSelected}
              aria-label={`Select ${industry.name} industry`}
            >
              {/* Selected indicator */}
              {isSelected && (
                <div className="absolute top-2 right-2">
                  <div className={`w-6 h-6 rounded-full ${industry.selectedCheckBg} flex items-center justify-center`}>
                    <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                </div>
              )}

              {/* Icon */}
              <div className={`w-12 h-12 rounded-lg bg-white/5 flex items-center justify-center mb-3 ${industry.color}`}>
                <Icon className="w-6 h-6" />
              </div>

              {/* Content */}
              <h3 className="font-semibold text-white mb-1">
                {industry.name}
              </h3>
              <p className="text-sm text-white/50">
                {industry.description}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export { industries };
