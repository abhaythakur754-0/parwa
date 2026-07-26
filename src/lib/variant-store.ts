/**
 * PARWA Variant Store
 *
 * Zustand store for multi-tenant variant (tier) management.
 * Tracks the company's current subscription tier, feature availability,
 * and usage limits. Server-verified — never trusts localStorage for tier data.
 *
 * Tiers: parwa ($2,499/mo) | high ($3,999/mo)
 * Pricing model: $1 = 1 ticket
 * All variants have the SAME AI capabilities — only ticket volume differs.
 * Mini PARWA was removed 2026-07-26. Legacy mini values auto-upgrade to parwa.
 * Prices sourced from: /src/lib/pricing-config.ts (matches backend SSOT)
 */

import { create } from 'zustand';
import {
  VARIANT_PRICES,
  VARIANT_DISPLAY_NAMES,
  VARIANT_TIER_ORDER,
  type VariantTier as CanonicalTier,
} from './pricing-config';

// ── Types ────────────────────────────────────────────────────────────

export type VariantTier = 'parwa' | 'high';

export interface FeatureMap {
  // Channels
  chatChannel: boolean;
  emailChannel: boolean;
  smsChannel: boolean;
  voiceChannel: boolean;
  videoChannel: boolean;

  // Agents
  faqAgent: boolean;
  refundAgent: boolean;
  technicalAgent: boolean;
  complaintAgent: boolean;
  fraudDetection: boolean;
  qualityCoach: boolean;
  churnPrediction: boolean;

  // Limits
  maxAgents: number;
  maxKnowledgeDocs: number;
  maxApiKeys: number;
  maxTeamMembers: number;
}

export interface UsageMetrics {
  agentsUsed: number;
  docsUsed: number;
  apiKeysUsed: number;
  teamMembersUsed: number;
  ticketsThisMonth: number;
  messagesThisMonth: number;
}

export interface VariantState {
  tier: VariantTier;
  isLoading: boolean;
  error: string | null;
  lastFetched: number | null;
  usage: UsageMetrics;

  // Actions
  setTier: (tier: VariantTier) => void;
  fetchTier: (companyId?: string) => Promise<void>;
  fetchUsage: (companyId?: string) => Promise<void>;
  isFeatureAvailable: (feature: keyof FeatureMap) => boolean;
  getFeatureMap: () => FeatureMap;
  isAtLimit: (resource: 'agents' | 'docs' | 'apiKeys' | 'teamMembers') => boolean;
  reset: () => void;
}

// ── Feature Map — SAME across all tiers ──────────────────────────
// All variants have identical AI capabilities.
// The only difference is the ticket volume ($1 = 1 ticket).

const ALL_FEATURES: FeatureMap = {
  // Channels — all available on every tier
  chatChannel: true,
  emailChannel: true,
  smsChannel: true,
  voiceChannel: true,
  videoChannel: true,

  // Agents — all available on every tier
  faqAgent: true,
  refundAgent: true,
  technicalAgent: true,
  complaintAgent: true,
  fraudDetection: true,
  qualityCoach: true,
  churnPrediction: true,

  // Limits — differ by tier (defaults for parwa; overridden by TIER_LIMITS)
  maxAgents: 5,
  maxKnowledgeDocs: 500,
  maxApiKeys: 5,
  maxTeamMembers: 10,
};

// ── Tier Limits (only these differ between tiers) ──────────────────

const TIER_LIMITS: Record<VariantTier, Omit<FeatureMap, keyof typeof ALL_FEATURES>> = {
  parwa: {
    maxAgents: 5,
    maxKnowledgeDocs: 500,
    maxApiKeys: 5,
    maxTeamMembers: 10,
  },
  high: {
    maxAgents: 8,       // 8 base, +$3/agent overage
    maxKnowledgeDocs: -1, // unlimited
    maxApiKeys: -1,       // unlimited
    maxTeamMembers: -1,   // unlimited
  },
};

function getFeatureMapForTier(tier: VariantTier): FeatureMap {
  return { ...ALL_FEATURES, ...TIER_LIMITS[tier] };
}

// ── Tier ordering for comparison ──────────────────────────────────

const TIER_ORDER: Record<VariantTier, number> = {
  parwa: 1,
  high: 2,
};

export function isTierAtLeast(current: VariantTier, required: VariantTier): boolean {
  return TIER_ORDER[current] >= TIER_ORDER[required];
}

export function getTierLabel(tier: VariantTier): string {
  const labels: Record<VariantTier, string> = {
    parwa: 'PARWA',
    high: 'PARWA High',
  };
  return labels[tier];
}

export function getTierPrice(tier: VariantTier): string {
  return `$${VARIANT_PRICES[tier].toLocaleString()}/mo`;
}

export function getTierColor(tier: VariantTier): string {
  const colors: Record<VariantTier, string> = {
    parwa: 'from-purple-500 to-purple-400',
    high: 'from-orange-500 to-amber-400',
  };
  return colors[tier];
}

// ── Default Usage ──────────────────────────────────────────────────

const DEFAULT_USAGE: UsageMetrics = {
  agentsUsed: 0,
  docsUsed: 0,
  apiKeysUsed: 0,
  teamMembersUsed: 0,
  ticketsThisMonth: 0,
  messagesThisMonth: 0,
};

// ── Store ───────────────────────────────────────────────────────────

export const useVariantStore = create<VariantState>((set, get) => ({
  tier: 'parwa',
  isLoading: false,
  error: null,
  lastFetched: null,
  usage: DEFAULT_USAGE,

  setTier: (tier: VariantTier) => {
    set({ tier, lastFetched: Date.now() });
  },

  fetchTier: async (_companyId?: string) => {
    set({ isLoading: true, error: null });
    try {
      // Lazy import to avoid circular dependency with billing-store
      const { useBillingStore } = await import('./billing-store');
      const billingState = useBillingStore.getState();
      await billingState.fetchBilling();

      const updatedTier = useBillingStore.getState().currentTier;
      set({ tier: updatedTier, isLoading: false, lastFetched: Date.now() });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch tier',
      });
    }
  },

  fetchUsage: async (_companyId?: string) => {
    try {
      // Lazy import to avoid circular dependency with billing-store
      const { useBillingStore } = await import('./billing-store');
      await useBillingStore.getState().fetchUsage();
      // Re-read state AFTER fetchUsage resolves — capturing the snapshot before
      // the await would yield stale usage values (zustand replaces state on set).
      const usage = useBillingStore.getState().usage;
      set({
        usage: {
          agentsUsed: 0,
          docsUsed: usage.storageUsed > 0 ? Math.floor(usage.storageUsed / 10) : 0,
          apiKeysUsed: 0,
          teamMembersUsed: 0,
          ticketsThisMonth: usage.ticketsUsed,
          messagesThisMonth: usage.messagesUsed,
        },
      });
    } catch {
      // Silently fail — usage is non-critical
    }
  },

  isFeatureAvailable: (feature: keyof FeatureMap): boolean => {
    const features = getFeatureMapForTier(get().tier);
    const value = features[feature];
    return typeof value === 'boolean' ? value : true;
  },

  getFeatureMap: (): FeatureMap => {
    return getFeatureMapForTier(get().tier);
  },

  isAtLimit: (resource: 'agents' | 'docs' | 'apiKeys' | 'teamMembers'): boolean => {
    const { tier, usage } = get();
    const features = getFeatureMapForTier(tier);
    const limitMap = {
      agents: features.maxAgents,
      docs: features.maxKnowledgeDocs,
      apiKeys: features.maxApiKeys,
      teamMembers: features.maxTeamMembers,
    };
    const usageMap = {
      agents: usage.agentsUsed,
      docs: usage.docsUsed,
      apiKeys: usage.apiKeysUsed,
      teamMembers: usage.teamMembersUsed,
    };
    const limit = limitMap[resource];
    if (limit === -1) return false; // unlimited
    return usageMap[resource] >= limit;
  },

  reset: () => {
    set({ tier: 'parwa', isLoading: false, error: null, lastFetched: null, usage: DEFAULT_USAGE });
  },
}));

// ── Export for direct access ──────────────────────────────────────

export { TIER_ORDER, ALL_FEATURES, TIER_LIMITS, getFeatureMapForTier };