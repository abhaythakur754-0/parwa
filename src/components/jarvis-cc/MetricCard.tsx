/**
 * MetricCard — Reusable metric display card for Jarvis CC Dashboard
 *
 * Shows a label, value, optional trend indicator, and color variant.
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';

export interface MetricCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  trend?: 'up' | 'down' | 'flat';
  trendValue?: string;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  icon?: React.ReactNode;
  className?: string;
}

export function MetricCard({
  label,
  value,
  subtitle,
  trend,
  trendValue,
  variant = 'default',
  icon,
  className,
}: MetricCardProps) {
  const variantStyles: Record<string, string> = {
    default: 'bg-[#1A1A1A] border-white/[0.06]',
    success: 'bg-emerald-500/5 border-emerald-500/20',
    warning: 'bg-amber-500/5 border-amber-500/20',
    danger: 'bg-red-500/5 border-red-500/20',
    info: 'bg-blue-500/5 border-blue-500/20',
  };

  const valueStyles: Record<string, string> = {
    default: 'text-white',
    success: 'text-emerald-400',
    warning: 'text-amber-400',
    danger: 'text-red-400',
    info: 'text-blue-400',
  };

  const trendStyles = {
    up: 'text-emerald-400',
    down: 'text-red-400',
    flat: 'text-zinc-500',
  };

  return (
    <div
      className={cn(
        'rounded-xl border p-4 transition-all duration-200 hover:border-white/10',
        variantStyles[variant],
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-1 truncate">
            {label}
          </p>
          <p className={cn('text-2xl font-bold tracking-tight', valueStyles[variant])}>
            {value}
          </p>
          {(subtitle || trend) && (
            <div className="flex items-center gap-2 mt-1">
              {trend && (
                <span className={cn('text-xs font-medium', trendStyles[trend])}>
                  {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→'}
                  {trendValue && ` ${trendValue}`}
                </span>
              )}
              {subtitle && (
                <span className="text-xs text-zinc-500 truncate">{subtitle}</span>
              )}
            </div>
          )}
        </div>
        {icon && (
          <div className="shrink-0 ml-3 text-zinc-600">
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}
