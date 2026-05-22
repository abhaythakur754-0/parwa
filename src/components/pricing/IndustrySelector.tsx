'use client';

import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export type IndustryKey = 'ecommerce' | 'saas' | 'logistics' | 'others';

export interface Industry {
  key: IndustryKey;
  icon: string;
  name: string;
  tagline: string;
  description: string;
}

export const industries: Industry[] = [
  {
    key: 'ecommerce',
    icon: '\uD83D\uDED2',
    name: 'E-commerce',
    tagline: 'Online retail stores, marketplaces, D2C brands',
    description:
      'Tailored AI support for order management, returns, shipping, and payment inquiries.',
  },
  {
    key: 'saas',
    icon: '\u2601\uFE0F',
    name: 'SaaS',
    tagline: 'Software companies, tech startups, cloud services',
    description:
      'AI agents specialized in technical support, billing, API help, and account management.',
  },
  {
    key: 'logistics',
    icon: '\uD83D\uDE9A',
    name: 'Logistics',
    tagline: 'Shipping, delivery, warehouse management',
    description:
      'Intelligent handling of shipment tracking, delivery issues, fleet, and customs queries.',
  },
  {
    key: 'others',
    icon: '\uD83C\uDFE2',
    name: 'Others',
    tagline: 'Custom setup for any industry',
    description:
      'Jarvis will help you customize a solution tailored to your unique business needs.',
  },
];

export interface IndustrySelectorProps {
  selected: IndustryKey | null;
  onSelect: (key: IndustryKey) => void;
}

export default function IndustrySelector({
  selected,
  onSelect,
}: IndustrySelectorProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {industries.map((industry) => {
        const isActive = selected === industry.key;

        return (
          <Card
            key={industry.key}
            onClick={() => onSelect(industry.key)}
            className={cn(
              'relative cursor-pointer rounded-2xl transition-all duration-300 overflow-hidden group select-none',
              isActive
                ? 'bg-[#0F1A16] border-emerald-500/40 shadow-lg shadow-emerald-500/10 scale-[1.02]'
                : 'bg-[#111111] border-white/[0.06] hover:border-white/[0.15] hover:bg-[#141414] hover:scale-[1.01]'
            )}
            role="button"
            tabIndex={0}
            aria-pressed={isActive}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onSelect(industry.key);
              }
            }}
          >
            {/* Top accent line when active */}
            {isActive && (
              <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-emerald-500 via-emerald-400 to-emerald-500" />
            )}

            {/* Glow effect when active */}
            {isActive && (
              <div className="absolute -inset-px bg-gradient-to-b from-emerald-500/10 via-transparent to-emerald-500/5 rounded-2xl pointer-events-none" />
            )}

            <CardContent className="relative p-5 flex flex-col items-center text-center gap-2.5">
              {/* Icon */}
              <span className="text-3xl">{industry.icon}</span>

              {/* Name */}
              <h3
                className={cn(
                  'text-base font-bold transition-colors duration-200',
                  isActive ? 'text-emerald-400' : 'text-white'
                )}
              >
                {industry.name}
              </h3>

              {/* Tagline */}
              <p
                className={cn(
                  'text-xs leading-relaxed transition-colors duration-200',
                  isActive ? 'text-emerald-400/60' : 'text-gray-500'
                )}
              >
                {industry.tagline}
              </p>

              {/* Bottom indicator dot */}
              <div
                className={cn(
                  'w-1.5 h-1.5 rounded-full transition-all duration-300 mt-1',
                  isActive ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' : 'bg-transparent'
                )}
              />
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
