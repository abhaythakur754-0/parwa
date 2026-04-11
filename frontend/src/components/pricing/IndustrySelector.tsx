'use client';

import React from 'react';
import {
  ShoppingCart,
  Cloud,
  Truck,
  Layers,
  Check,
} from 'lucide-react';

/**
 * IndustrySelector Component
 *
 * 4 industry cards:
 * - E-commerce (ShoppingCart, orange)
 * - SaaS (Cloud, sky blue)
 * - Logistics (Truck, amber)
 * - Others (Layers, orange)
 *
 * Selected state: glowing colored border + checkmark.
 * Hover: lift effect.
 */

export type Industry = 'ecommerce' | 'saas' | 'logistics' | 'others';

export interface IndustryOption {
  id: Industry;
  name: string;
  description: string;
  icon: React.ElementType;
  color: string;
  iconBg: string;
  glowClass: string;
  borderSelected: string;
  bgSelected: string;
  checkBg: string;
  shadowClass: string;
}

const industries: IndustryOption[] = [
  {
    id: 'ecommerce',
    name: 'E-commerce',
    description: 'Online retail, marketplaces, D2C brands',
    icon: ShoppingCart,
    color: 'text-orange-400',
    iconBg: 'bg-orange-600/15',
    glowClass: 'hover:shadow-orange-600/20',
    borderSelected: 'border-orange-600',
    bgSelected: 'bg-orange-600/10',
    checkBg: 'bg-orange-600',
    shadowClass: 'shadow-orange-600/25',
  },
  {
    id: 'saas',
    name: 'SaaS',
    description: 'Software companies, tech startups',
    icon: Cloud,
    color: 'text-sky-400',
    iconBg: 'bg-sky-500/15',
    glowClass: 'hover:shadow-sky-500/20',
    borderSelected: 'border-sky-400',
    bgSelected: 'bg-sky-400/10',
    checkBg: 'bg-sky-400',
    shadowClass: 'shadow-sky-400/25',
  },
  {
    id: 'logistics',
    name: 'Logistics',
    description: 'Shipping, warehousing, supply chain',
    icon: Truck,
    color: 'text-amber-400',
    iconBg: 'bg-amber-500/15',
    glowClass: 'hover:shadow-amber-500/20',
    borderSelected: 'border-amber-400',
    bgSelected: 'bg-amber-400/10',
    checkBg: 'bg-amber-400',
    shadowClass: 'shadow-amber-400/25',
  },
  {
    id: 'others',
    name: 'Others',
    description: 'Healthcare, Finance, Education, etc.',
    icon: Layers,
    color: 'text-orange-400',
    iconBg: 'bg-orange-500/15',
    glowClass: 'hover:shadow-orange-500/20',
    borderSelected: 'border-orange-400',
    bgSelected: 'bg-orange-400/10',
    checkBg: 'bg-orange-400',
    shadowClass: 'shadow-orange-400/25',
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
      {/* Section Header */}
      <div className="mb-6">
        <h2 className="text-xl sm:text-2xl font-bold text-white mb-2">
          Select Your Industry
        </h2>
        <p className="text-sm sm:text-base text-orange-200/50">
          Choose your industry to see relevant AI support variants
        </p>
      </div>

      {/* Industry Cards Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
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
                relative p-4 sm:p-5 rounded-xl border-2 text-left
                transition-all duration-300 ease-out
                backdrop-blur-sm
                ${
                  isSelected
                    ? `${industry.borderSelected} ${industry.bgSelected} shadow-lg ${industry.shadowClass}`
                    : 'border-white/10 bg-white/5 hover:border-orange-500/30'
                }
                ${
                  !isSelected
                    ? `hover:-translate-y-1 hover:shadow-lg ${industry.glowClass}`
                    : ''
                }
                ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
              `}
              aria-pressed={isSelected}
              aria-label={`Select ${industry.name} industry`}
            >
              {/* Selected Checkmark */}
              {isSelected && (
                <div className="absolute -top-2.5 -right-2.5">
                  <div
                    className={`w-6 h-6 rounded-full ${industry.checkBg} flex items-center justify-center shadow-lg`}
                  >
                    <Check className="w-3.5 h-3.5 text-white" strokeWidth={3} />
                  </div>
                </div>
              )}

              {/* Icon */}
              <div
                className={`w-11 h-11 sm:w-12 sm:h-12 rounded-lg ${industry.iconBg} flex items-center justify-center mb-3 transition-transform duration-300 ${
                  isSelected ? 'scale-110' : ''
                }`}
              >
                <Icon className={`w-5 h-5 sm:w-6 sm:h-6 ${industry.color}`} />
              </div>

              {/* Content */}
              <h3 className="font-semibold text-white text-sm sm:text-base mb-1">
                {industry.name}
              </h3>
              <p className="text-xs sm:text-sm text-orange-200/50 leading-relaxed">
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
