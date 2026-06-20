/**
 * PARWA useVariant Hook
 *
 * React hook for accessing multi-tenant variant (tier) data.
 * Wraps the variant Zustand store with React lifecycle management
 * and automatic fetching on mount.
 *
 * Usage:
 *   const { tier, features, isFeatureAvailable, isAtLimit } = useVariant();
 */

'use client';

import { useEffect, useCallback } from 'react';
import {
  useVariantStore,
  VariantTier,
  FeatureMap,
  isTierAtLeast,
  getTierLabel,
  getTierPrice,
  getTierColor,
} from '@/lib/variant-store';

export interface UseVariantReturn {
  /** Current subscription tier */
  tier: VariantTier;
  /** Feature map for the current tier */
  features: FeatureMap;
  /** Whether the tier is currently being fetched */
  isLoading: boolean;
  /** Error message if tier fetch failed */
  error: string | null;
  /** Check if a specific feature is available on the current tier */
  isFeatureAvailable: (feature: keyof FeatureMap) => boolean;
  /** Check if a resource limit has been reached */
  isAtLimit: (resource: 'agents' | 'docs' | 'apiKeys' | 'teamMembers') => boolean;
  /** Check if the current tier meets or exceeds a required tier */
  isTierAtLeast: (required: VariantTier) => boolean;
  /** Manually refetch the tier from the server */
  refetch: () => Promise<void>;
  /** Get display label for the current tier */
  tierLabel: string;
  /** Get price string for the current tier */
  tierPrice: string;
  /** Get Tailwind gradient class for the current tier */
  tierColor: string;
  /** Usage metrics for the current company */
  usage: {
    agentsUsed: number;
    docsUsed: number;
    apiKeysUsed: number;
    teamMembersUsed: number;
    ticketsThisMonth: number;
    messagesThisMonth: number;
  };
}

export function useVariant(): UseVariantReturn {
  const tier = useVariantStore((s) => s.tier);
  const isLoading = useVariantStore((s) => s.isLoading);
  const error = useVariantStore((s) => s.error);
  const usage = useVariantStore((s) => s.usage);
  const fetchTier = useVariantStore((s) => s.fetchTier);
  const fetchUsage = useVariantStore((s) => s.fetchUsage);
  const getFeatureMap = useVariantStore((s) => s.getFeatureMap);
  const storeIsFeatureAvailable = useVariantStore((s) => s.isFeatureAvailable);
  const storeIsAtLimit = useVariantStore((s) => s.isAtLimit);

  const features = getFeatureMap();

  // Fetch tier and usage on mount
  useEffect(() => {
    fetchTier();
    fetchUsage();
  }, [fetchTier, fetchUsage]);

  const refetch = useCallback(async () => {
    await Promise.all([fetchTier(), fetchUsage()]);
  }, [fetchTier, fetchUsage]);

  const isFeatureAvailableFn = useCallback(
    (feature: keyof FeatureMap) => storeIsFeatureAvailable(feature),
    [storeIsFeatureAvailable]
  );

  const isAtLimitFn = useCallback(
    (resource: 'agents' | 'docs' | 'apiKeys' | 'teamMembers') => storeIsAtLimit(resource),
    [storeIsAtLimit]
  );

  return {
    tier,
    features,
    isLoading,
    error,
    isFeatureAvailable: isFeatureAvailableFn,
    isAtLimit: isAtLimitFn,
    isTierAtLeast: (required: VariantTier) => isTierAtLeast(tier, required),
    refetch,
    tierLabel: getTierLabel(tier),
    tierPrice: getTierPrice(tier),
    tierColor: getTierColor(tier),
    usage,
  };
}
