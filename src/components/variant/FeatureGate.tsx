'use client';

import React from 'react';
import { useVariant } from '@/contexts/VariantContext';
import { cn } from '@/lib/utils';

// ── Props ────────────────────────────────────────────────────────────────

interface FeatureGateProps {
  feature: string;
  children: React.ReactNode;
  
  /** What to show if feature is blocked */
  fallback?: React.ReactNode;
  
  /** Show upgrade prompt instead of hiding */
  showUpgradePrompt?: boolean;
  
  /** Custom class for upgrade prompt */
  upgradeClassName?: string;
}

// ── Feature Gate Component ────────────────────────────────────────────────

export function FeatureGate({ 
  feature, 
  children, 
  fallback = null,
  showUpgradePrompt = false,
  upgradeClassName,
}: FeatureGateProps) {
  const { isFeatureBlocked, getUpgradePrompt, variant } = useVariant();
  
  const isBlocked = isFeatureBlocked(feature);
  
  if (!isBlocked) {
    return <>{children}</>;
  }
  
  if (showUpgradePrompt) {
    const upgradePrompt = getUpgradePrompt(feature);
    return (
      <UpgradePrompt 
        message={upgradePrompt || 'This feature is not available on your plan.'}
        className={upgradeClassName}
      />
    );
  }
  
  return <>{fallback}</>;
}

// ── Upgrade Prompt Component ──────────────────────────────────────────────

interface UpgradePromptProps {
  message: string;
  feature?: string;
  className?: string;
  compact?: boolean;
}

export function UpgradePrompt({ 
  message, 
  feature,
  className,
  compact = false,
}: UpgradePromptProps) {
  if (compact) {
    return (
      <div className={cn(
        'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg',
        'bg-orange-500/10 border border-orange-500/20',
        className
      )}>
        <svg className="w-4 h-4 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
        </svg>
        <span className="text-sm text-orange-400">{message}</span>
        <a href="/dashboard/billing" className="text-sm text-orange-300 underline">Upgrade</a>
      </div>
    );
  }
  
  return (
    <div className={cn(
      'flex flex-col items-center justify-center p-8 rounded-xl text-center',
      'bg-gradient-to-b from-orange-500/5 to-transparent',
      'border border-orange-500/10',
      className
    )}>
      <div className="w-12 h-12 rounded-full bg-orange-500/10 flex items-center justify-center mb-4">
        <svg className="w-6 h-6 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
        </svg>
      </div>
      
      <h3 className="text-lg font-medium text-zinc-200 mb-2">
        {feature ? `${feature} Locked` : 'Feature Locked'}
      </h3>
      
      <p className="text-sm text-zinc-400 max-w-md mb-4">
        {message}
      </p>
      
      <a 
        href="/dashboard/billing"
        className="inline-flex items-center gap-2 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors text-sm font-medium"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 15.75 7.5-7.5 7.5 7.5" />
        </svg>
        Upgrade Plan
      </a>
    </div>
  );
}

// ── Feature Badge for Nav Items ───────────────────────────────────────────

interface FeatureBadgeProps {
  feature: string;
  className?: string;
}

export function FeatureBadge({ feature, className }: FeatureBadgeProps) {
  const { isFeatureBlocked, variant } = useVariant();
  
  if (!isFeatureBlocked(feature)) return null;
  
  return (
    <span className={cn(
      'text-[8px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded',
      'bg-orange-500/10 text-orange-400',
      className
    )}>
      PRO
    </span>
  );
}

// ── Nav Item Wrapper ──────────────────────────────────────────────────────

interface GatedNavItemProps {
  feature: string;
  href: string;
  children: React.ReactNode;
  className?: string;
}

export function GatedNavItem({ feature, href, children, className }: GatedNavItemProps) {
  const { isFeatureBlocked } = useVariant();
  
  const isBlocked = isFeatureBlocked(feature);
  
  return (
    <a 
      href={isBlocked ? '/dashboard/billing' : href}
      className={cn(
        className,
        isBlocked && 'opacity-50'
      )}
      title={isBlocked ? 'Upgrade to unlock this feature' : undefined}
    >
      {children}
      {isBlocked && (
        <FeatureBadge feature={feature} className="ml-2" />
      )}
    </a>
  );
}

export default FeatureGate;
