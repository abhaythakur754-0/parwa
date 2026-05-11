'use client';

import React from 'react';
import { cn } from '@/lib/utils';

// ── KPI Card Types ────────────────────────────────────────────────────

interface KPICardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  trend?: {
    value: number; // positive = up, negative = down
    label?: string;
  };
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  className?: string;
  isLoading?: boolean;
}

// ── Variant Styles ────────────────────────────────────────────────────

const variantStyles = {
  default: {
    card: 'border-white/[0.06] hover:border-white/[0.1]',
    iconBg: 'bg-white/[0.05]',
    iconText: 'text-zinc-400',
  },
  success: {
    card: 'border-emerald-500/20 hover:border-emerald-500/30',
    iconBg: 'bg-emerald-500/10',
    iconText: 'text-emerald-400',
  },
  warning: {
    card: 'border-amber-500/20 hover:border-amber-500/30',
    iconBg: 'bg-amber-500/10',
    iconText: 'text-amber-400',
  },
  danger: {
    card: 'border-red-500/20 hover:border-red-500/30',
    iconBg: 'bg-red-500/10',
    iconText: 'text-red-400',
  },
  info: {
    card: 'border-sky-500/20 hover:border-sky-500/30',
    iconBg: 'bg-sky-500/10',
    iconText: 'text-sky-400',
  },
};

const trendColors = {
  up: 'text-emerald-400',
  down: 'text-red-400',
};

// ── Skeleton Loader ───────────────────────────────────────────────────

function KPISkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-4 w-24 bg-white/[0.06] rounded mb-3" />
      <div className="h-8 w-32 bg-white/[0.06] rounded mb-2" />
      <div className="h-3 w-20 bg-white/[0.06] rounded" />
    </div>
  );
}

// ── KPI Card Component ────────────────────────────────────────────────

export default function KPICard({
  title,
  value,
  subtitle,
  icon,
  trend,
  variant = 'default',
  className,
  isLoading = false,
}: KPICardProps) {
  const style = variantStyles[variant];

  if (isLoading) {
    return (
      <div className={cn(
        'rounded-xl bg-[#1A1A1A] border p-5 transition-all duration-300',
        style.card,
        className
      )}>
        <div className="flex items-start justify-between">
          <KPISkeleton />
          <div className="w-10 h-10 rounded-lg bg-white/[0.06]" />
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'rounded-xl bg-[#1A1A1A] border p-5 transition-all duration-300 hover:shadow-lg hover:shadow-black/20 group',
        style.card,
        className
      )}
    >
      <div className="flex items-start justify-between">
        {/* Left: Title + Value */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
            {title}
          </p>
          <p className="text-2xl font-bold text-white tabular-nums">
            {value}
          </p>
          <div className="flex items-center gap-2">
            {trend && (
              <span className={cn(
                'text-xs font-semibold flex items-center gap-0.5',
                trend.value >= 0 ? trendColors.up : trendColors.down
              )}>
                <svg
                  className={cn('w-3 h-3', trend.value < 0 ? 'rotate-180' : '')}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2.5}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" />
                </svg>
                {Math.abs(trend.value)}%
              </span>
            )}
            {subtitle && (
              <span className="text-xs text-zinc-500">{subtitle}</span>
            )}
          </div>
        </div>

        {/* Right: Icon */}
        <div className={cn(
          'w-10 h-10 rounded-lg flex items-center justify-center shrink-0 transition-colors duration-200',
          style.iconBg,
          'group-hover:scale-110 transition-transform duration-300'
        )}>
          <span className={style.iconText}>{icon}</span>
        </div>
      </div>
    </div>
  );
}
