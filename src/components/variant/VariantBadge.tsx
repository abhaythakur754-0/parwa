'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { useVariant } from '@/contexts/VariantContext';
import { VariantType } from '@/types/variant';

// ── Variant Badge Colors ──────────────────────────────────────────────────

const VARIANT_STYLES: Record<VariantType, {
  bg: string;
  text: string;
  border: string;
  icon: string;
}> = {
  mini_parwa: {
    bg: 'bg-gradient-to-r from-orange-500/10 to-amber-500/10',
    text: 'text-orange-400',
    border: 'border-orange-500/20',
    icon: '🚀',
  },
  parwa: {
    bg: 'bg-gradient-to-r from-blue-500/10 to-cyan-500/10',
    text: 'text-blue-400',
    border: 'border-blue-500/20',
    icon: '⚡',
  },
  high_parwa: {
    bg: 'bg-gradient-to-r from-purple-500/10 to-pink-500/10',
    text: 'text-purple-400',
    border: 'border-purple-500/20',
    icon: '👑',
  },
};

// ── Props ────────────────────────────────────────────────────────────────

interface VariantBadgeProps {
  showIcon?: boolean;
  showLimits?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

// ── Component ────────────────────────────────────────────────────────────

export function VariantBadge({ 
  showIcon = true, 
  showLimits = false,
  size = 'md',
  className 
}: VariantBadgeProps) {
  const { variant, variantInfo, limits, usage } = useVariant();
  
  const styles = VARIANT_STYLES[variant];
  const displayName = variantInfo?.display_name || 'Mini Parwa';
  
  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  };

  return (
    <div className={cn(
      'inline-flex items-center gap-1.5 rounded-full border font-medium',
      styles.bg,
      styles.text,
      styles.border,
      sizeClasses[size],
      className
    )}>
      {showIcon && (
        <span className="text-sm">{styles.icon}</span>
      )}
      <span>{displayName}</span>
      
      {showLimits && (
        <span className="text-xs opacity-70 ml-1">
          ({usage.tickets_used.toLocaleString()}/{limits.monthly_tickets.toLocaleString()} tickets)
        </span>
      )}
    </div>
  );
}

// ── Compact Version for Sidebar ───────────────────────────────────────────

export function VariantBadgeCompact({ className }: { className?: string }) {
  const { variant, usage, limits } = useVariant();
  const styles = VARIANT_STYLES[variant];
  
  return (
    <div className={cn(
      'flex items-center justify-between p-2 rounded-lg',
      styles.bg,
      styles.border,
      'border',
      className
    )}>
      <div className="flex items-center gap-2">
        <span className="text-sm">{styles.icon}</span>
        <span className={cn('text-sm font-medium', styles.text)}>
          {variant === 'mini_parwa' ? 'Mini' : variant === 'parwa' ? 'Parwa' : 'High'}
        </span>
      </div>
      
      {/* Mini usage indicator */}
      <div className="flex items-center gap-1">
        <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
          <div 
            className={cn(
              'h-full rounded-full transition-all',
              usage.utilization_pct >= 100 ? 'bg-red-500' :
              usage.utilization_pct >= 80 ? 'bg-yellow-500' : 'bg-green-500'
            )}
            style={{ width: `${Math.min(usage.utilization_pct, 100)}%` }}
          />
        </div>
        <span className="text-[10px] text-zinc-500">
          {usage.utilization_pct}%
        </span>
      </div>
    </div>
  );
}

// ── Detailed Version for Settings/Billing ─────────────────────────────────

export function VariantBadgeDetailed({ className }: { className?: string }) {
  const { variant, variantInfo, limits, usage } = useVariant();
  const styles = VARIANT_STYLES[variant];
  
  return (
    <div className={cn(
      'rounded-xl border p-4',
      styles.bg,
      styles.border,
      className
    )}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">{styles.icon}</span>
          <div>
            <h3 className={cn('font-semibold', styles.text)}>
              {variantInfo?.display_name}
            </h3>
            <p className="text-xs text-zinc-500">Current Plan</p>
          </div>
        </div>
        
        {variant !== 'high_parwa' && (
          <a 
            href="/dashboard/billing"
            className="text-xs px-3 py-1.5 bg-orange-500/20 text-orange-400 rounded-full hover:bg-orange-500/30 transition-colors"
          >
            Upgrade
          </a>
        )}
      </div>
      
      {/* Limits Grid */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="flex justify-between p-2 bg-black/20 rounded-lg">
          <span className="text-zinc-400">Tickets</span>
          <span className="text-white">
            {usage.tickets_used.toLocaleString()}/{limits.monthly_tickets.toLocaleString()}
          </span>
        </div>
        <div className="flex justify-between p-2 bg-black/20 rounded-lg">
          <span className="text-zinc-400">AI Agents</span>
          <span className="text-white">
            {usage.ai_agents_used}/{limits.ai_agents}
          </span>
        </div>
        <div className="flex justify-between p-2 bg-black/20 rounded-lg">
          <span className="text-zinc-400">Team</span>
          <span className="text-white">
            {usage.team_members_used}/{limits.team_members}
          </span>
        </div>
        <div className="flex justify-between p-2 bg-black/20 rounded-lg">
          <span className="text-zinc-400">KB Docs</span>
          <span className="text-white">
            {usage.kb_docs_used}/{limits.kb_docs}
          </span>
        </div>
      </div>
      
      {/* Model Tier */}
      <div className="mt-3 pt-3 border-t border-white/5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-zinc-400">AI Model</span>
          <span className={cn('font-medium', styles.text)}>
            {limits.model_tiers.includes('heavy') ? 'Heavy' :
             limits.model_tiers.includes('medium') ? 'Medium' : 'Light'} Only
          </span>
        </div>
      </div>
    </div>
  );
}

export default VariantBadge;
