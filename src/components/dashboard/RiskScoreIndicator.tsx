'use client';

import React from 'react';
import { cn } from '@/lib/utils';

// ── Types ──────────────────────────────────────────────────────────────────

export interface RiskScoreIndicatorProps {
  /** Risk score from 0 to 1 */
  score: number | null;
  /** Show the numeric score value */
  showValue?: boolean;
  /** Optional label text */
  label?: string;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Show as a gauge/progress bar instead of just a badge */
  showBar?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// ── Helper Functions ───────────────────────────────────────────────────────

function getRiskLevel(score: number): 'high' | 'medium' | 'low' {
  if (score > 0.7) return 'high';
  if (score >= 0.3) return 'medium';
  return 'low';
}

function getRiskConfig(level: 'high' | 'medium' | 'low') {
  return {
    high: {
      color: 'text-red-400',
      bgColor: 'bg-red-500/15',
      borderColor: 'border-red-500/25',
      barColor: 'bg-red-500',
      glowColor: 'shadow-red-500/20',
      label: 'High Risk',
    },
    medium: {
      color: 'text-yellow-400',
      bgColor: 'bg-yellow-500/15',
      borderColor: 'border-yellow-500/25',
      barColor: 'bg-yellow-500',
      glowColor: 'shadow-yellow-500/20',
      label: 'Medium Risk',
    },
    low: {
      color: 'text-emerald-400',
      bgColor: 'bg-emerald-500/15',
      borderColor: 'border-emerald-500/25',
      barColor: 'bg-emerald-500',
      glowColor: 'shadow-emerald-500/20',
      label: 'Low Risk',
    },
  }[level];
}

// ── RiskScoreIndicator Component ───────────────────────────────────────────

export default function RiskScoreIndicator({
  score,
  showValue = true,
  label,
  size = 'md',
  showBar = false,
  className,
}: RiskScoreIndicatorProps) {
  // Handle null/undefined score
  if (score === null || score === undefined) {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        <span className="text-zinc-600 text-xs">—</span>
        {label && <span className="text-zinc-600 text-xs">{label}</span>}
      </div>
    );
  }

  // Clamp score to valid range
  const clampedScore = Math.max(0, Math.min(1, score));
  const level = getRiskLevel(clampedScore);
  const config = getRiskConfig(level);
  const percentage = Math.round(clampedScore * 100);

  // Size configurations
  const sizeConfig = {
    sm: {
      dot: 'w-1.5 h-1.5',
      text: 'text-[10px]',
      bar: 'h-1',
    },
    md: {
      dot: 'w-2 h-2',
      text: 'text-xs',
      bar: 'h-1.5',
    },
    lg: {
      dot: 'w-2.5 h-2.5',
      text: 'text-sm',
      bar: 'h-2',
    },
  }[size];

  // ── Bar Variant ──────────────────────────────────────────────────────────
  if (showBar) {
    return (
      <div className={cn('flex items-center gap-2 min-w-[100px]', className)}>
        <div className="flex-1 bg-white/[0.06] rounded-full overflow-hidden">
          <div
            className={cn(
              'rounded-full transition-all duration-300',
              config.barColor,
              sizeConfig.bar
            )}
            style={{ width: `${percentage}%` }}
          />
        </div>
        {showValue && (
          <span className={cn('font-mono font-medium w-8 text-right', config.color, sizeConfig.text)}>
            {percentage}%
          </span>
        )}
        {label && (
          <span className="text-zinc-500 text-xs">{label}</span>
        )}
      </div>
    );
  }

  // ── Badge Variant ────────────────────────────────────────────────────────
  return (
    <div className={cn('inline-flex items-center gap-1.5', className)}>
      {/* Color dot */}
      <span
        className={cn(
          'rounded-full shrink-0',
          config.barColor,
          sizeConfig.dot
        )}
      />

      {/* Score value */}
      {showValue && (
        <span className={cn('font-mono font-medium', config.color, sizeConfig.text)}>
          {percentage}%
        </span>
      )}

      {/* Label */}
      {label && (
        <span className={cn('text-zinc-400', sizeConfig.text)}>
          {label}
        </span>
      )}
    </div>
  );
}

// ── RiskGauge Component (Alternative Circular Display) ─────────────────────

export function RiskGauge({
  score,
  size = 80,
  showLabel = true,
  className,
}: {
  score: number | null;
  size?: number;
  showLabel?: boolean;
  className?: string;
}) {
  if (score === null || score === undefined) {
    return (
      <div className={cn('flex flex-col items-center', className)}>
        <div
          className="rounded-full border-4 border-zinc-800 flex items-center justify-center"
          style={{ width: size, height: size }}
        >
          <span className="text-zinc-600 text-sm">N/A</span>
        </div>
      </div>
    );
  }

  const clampedScore = Math.max(0, Math.min(1, score));
  const level = getRiskLevel(clampedScore);
  const config = getRiskConfig(level);
  const percentage = Math.round(clampedScore * 100);

  // SVG parameters
  const strokeWidth = 6;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clampedScore * circumference);

  return (
    <div className={cn('flex flex-col items-center', className)}>
      <div className="relative" style={{ width: size, height: size }}>
        {/* Background circle */}
        <svg className="transform -rotate-90" width={size} height={size}>
          <circle
            className="text-zinc-800"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            fill="transparent"
            r={radius}
            cx={size / 2}
            cy={size / 2}
          />
          {/* Progress circle */}
          <circle
            className={cn('transition-all duration-500', config.barColor.replace('bg-', 'text-'))}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            fill="transparent"
            r={radius}
            cx={size / 2}
            cy={size / 2}
            style={{
              strokeDasharray: circumference,
              strokeDashoffset: offset,
            }}
            strokeLinecap="round"
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn('text-lg font-bold', config.color)}>
            {percentage}%
          </span>
        </div>
      </div>
      {showLabel && (
        <span className={cn('mt-1 text-xs font-medium', config.color)}>
          {config.label}
        </span>
      )}
    </div>
  );
}

// ── RiskPill Component (Compact Badge) ─────────────────────────────────────

export function RiskPill({
  score,
  className,
}: {
  score: number | null;
  className?: string;
}) {
  if (score === null || score === undefined) {
    return (
      <span className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium',
        'bg-zinc-800 text-zinc-500 border border-zinc-700',
        className
      )}>
        No Risk Score
      </span>
    );
  }

  const clampedScore = Math.max(0, Math.min(1, score));
  const level = getRiskLevel(clampedScore);
  const config = getRiskConfig(level);
  const percentage = Math.round(clampedScore * 100);

  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-semibold border',
      config.bgColor,
      config.color,
      config.borderColor,
      className
    )}>
      <span className={cn('w-1.5 h-1.5 rounded-full', config.barColor)} />
      {percentage}% Risk
    </span>
  );
}
