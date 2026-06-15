/**
 * PARWA LockedFeature Component
 *
 * Tier-gated feature wrapper. Shows children if the user's current tier
 * meets or exceeds the required tier. Otherwise shows an upgrade CTA
 * or a custom fallback.
 *
 * Usage:
 *   <LockedFeature requiredTier="pro">
 *     <SMSChannelToggle />
 *   </LockedFeature>
 *
 *   <LockedFeature requiredTier="high" fallback={<div>Not available</div>}>
 *     <QualityCoach />
 *   </LockedFeature>
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { useVariant } from '@/hooks/useVariant';
import { VariantTier, getTierLabel, getTierPrice, isTierAtLeast } from '@/lib/variant-store';
import { Lock, Crown, ArrowRight } from 'lucide-react';

interface LockedFeatureProps {
  /** Minimum tier required to see this feature */
  requiredTier: VariantTier;
  /** Custom fallback content when feature is locked (overrides default upgrade CTA) */
  fallback?: React.ReactNode;
  /** Whether to show the upgrade CTA when locked (default: true) */
  showUpgrade?: boolean;
  /** Feature name displayed in the upgrade CTA */
  featureName?: string;
  /** Children rendered when feature is available */
  children: React.ReactNode;
  /** Optional CSS class for the locked overlay container */
  className?: string;
}

export function LockedFeature({
  requiredTier,
  fallback,
  showUpgrade = true,
  featureName,
  children,
  className,
}: LockedFeatureProps) {
  const { tier, isTierAtLeast: checkTier } = useVariant();

  const hasAccess = checkTier(requiredTier);

  if (hasAccess) {
    return <>{children}</>;
  }

  // Custom fallback
  if (fallback) {
    return <>{fallback}</>;
  }

  // No upgrade CTA — show nothing
  if (!showUpgrade) {
    return null;
  }

  // Default: Show upgrade CTA
  return (
    <div className={`relative ${className || ''}`}>
      {/* Blurred preview of the content */}
      <div className="blur-[6px] opacity-40 pointer-events-none select-none" aria-hidden="true">
        {children}
      </div>

      {/* Lock overlay */}
      <div className="absolute inset-0 flex items-center justify-center z-10">
        <div className="max-w-sm w-full mx-4 rounded-xl border border-orange-500/20 bg-[#1A1A1A]/95 backdrop-blur-xl p-6 text-center shadow-2xl shadow-orange-500/5">
          <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center mx-auto mb-4">
            <Lock className="w-6 h-6 text-orange-400" />
          </div>

          <h3 className="text-base font-semibold text-white mb-1">
            {featureName ? `${featureName}` : 'Premium Feature'}
          </h3>

          <p className="text-sm text-zinc-400 mb-4">
            Available on{' '}
            <span className="text-orange-400 font-medium">
              {getTierLabel(requiredTier)}
            </span>{' '}
            ({getTierPrice(requiredTier)}) and above
          </p>

          <Link
            href="/dashboard/billing"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200"
          >
            <Crown className="w-4 h-4" />
            Upgrade Now
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>

          {tier === 'mini' && requiredTier === 'pro' && (
            <p className="text-xs text-zinc-500 mt-3">
              Pro unlocks SMS & Voice channels, 15 AI agents, and more
            </p>
          )}
          {requiredTier === 'high' && (
            <p className="text-xs text-zinc-500 mt-3">
              High unlocks Video channel, Fraud Detection, Quality Coach, and more
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Simple tier badge for sidebar items and cards.
 * Shows a lock icon for features not available on the current tier.
 */
export function TierBadge({ requiredTier }: { requiredTier: VariantTier }) {
  const { tier } = useVariant();

  if (isTierAtLeast(tier, requiredTier)) {
    return null;
  }

  return (
    <span className="inline-flex items-center gap-1 ml-auto text-[10px] text-zinc-500 uppercase tracking-wider">
      <Lock className="w-3 h-3" />
      {getTierLabel(requiredTier).split(' ')[0]}
    </span>
  );
}

/**
 * Inline lock indicator for table rows and list items.
 * Shows a subtle lock icon next to the item name.
 */
export function InlineLock({ requiredTier }: { requiredTier: VariantTier }) {
  const { tier } = useVariant();

  if (isTierAtLeast(tier, requiredTier)) {
    return null;
  }

  return (
    <span className="inline-flex items-center gap-1 text-zinc-500 cursor-help" title={`Requires ${getTierLabel(requiredTier)} (${getTierPrice(requiredTier)})`}>
      <Lock className="w-3 h-3" />
    </span>
  );
}

export default LockedFeature;
