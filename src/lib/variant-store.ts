/**
 * PARWA Variant Store
 *
 * Zustand store for multi-tenant variant (tier) management.
 * Tracks the company's current subscription tier, feature availability,
 * and usage limits. Server-verified — never trusts localStorage for tier data.
 *
 * Tiers: mini ($999/mo) | pro ($2,499/mo) | high ($3,999/mo)
 */

import { create } from 'zustand';

// ── Types ────────────────────────────────────────────────────────────

export type VariantTier = 'mini' | 'pro' | 'high';

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

// ── Feature Maps per Tier ──────────────────────────────────────────

const TIER_FEATURES: Record<VariantTier, FeatureMap> = {
  mini: {
    chatChannel: true,
    emailChannel: true,
    smsChannel: false,
    voiceChannel: false,
    videoChannel: false,
    faqAgent: true,
    refundAgent: false,
    technicalAgent: false,
    complaintAgent: false,
    fraudDetection: false,
    qualityCoach: false,
    churnPrediction: false,
    maxAgents: 5,
    maxKnowledgeDocs: 50,
    maxApiKeys: 1,
    maxTeamMembers: 1,
  },
  pro: {
    chatChannel: true,
    emailChannel: true,
    smsChannel: true,
    voiceChannel: true,
    videoChannel: false,
    faqAgent: true,
    refundAgent: true,
    technicalAgent: true,
    complaintAgent: true,
    fraudDetection: false,
    qualityCoach: false,
    churnPrediction: false,
    maxAgents: 15,
    maxKnowledgeDocs: 500,
    maxApiKeys: 5,
    maxTeamMembers: 5,
  },
  high: {
    chatChannel: true,
    emailChannel: true,
    smsChannel: true,
    voiceChannel: true,
    videoChannel: true,
    faqAgent: true,
    refundAgent: true,
    technicalAgent: true,
    complaintAgent: true,
    fraudDetection: true,
    qualityCoach: true,
    churnPrediction: true,
    maxAgents: 50,
    maxKnowledgeDocs: -1, // unlimited
    maxApiKeys: -1,       // unlimited
    maxTeamMembers: -1,   // unlimited
  },
};

// ── Tier ordering for comparison ──────────────────────────────────

const TIER_ORDER: Record<VariantTier, number> = {
  mini: 0,
  pro: 1,
  high: 2,
};

export function isTierAtLeast(current: VariantTier, required: VariantTier): boolean {
  return TIER_ORDER[current] >= TIER_ORDER[required];
}

export function getTierLabel(tier: VariantTier): string {
  const labels: Record<VariantTier, string> = {
    mini: 'Mini PARWA',
    pro: 'PARWA Pro',
    high: 'PARWA High',
  };
  return labels[tier];
}

export function getTierPrice(tier: VariantTier): string {
  const prices: Record<VariantTier, string> = {
    mini: '$999/mo',
    pro: '$2,499/mo',
    high: '$3,999/mo',
  };
  return prices[tier];
}

export function getTierColor(tier: VariantTier): string {
  const colors: Record<VariantTier, string> = {
    mini: 'from-blue-500 to-blue-400',
    pro: 'from-purple-500 to-purple-400',
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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const useVariantStore = create<VariantState>((set, get) => ({
  tier: 'mini',
  isLoading: false,
  error: null,
  lastFetched: null,
  usage: DEFAULT_USAGE,

  setTier: (tier: VariantTier) => {
    set({ tier, lastFetched: Date.now() });
  },

  fetchTier: async (companyId?: string) => {
    set({ isLoading: true, error: null });
    try {
      const res = await fetch(`${API_BASE}/api/v1/billing/subscription`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        // If endpoint not available, default to mini tier
        if (res.status === 404 || res.status === 502 || res.status === 503) {
          set({ tier: 'mini', isLoading: false, lastFetched: Date.now() });
          return;
        }
        throw new Error(`Failed to fetch subscription: ${res.status}`);
      }

      const data = await res.json();
      const tier = (data.variant_tier || data.tier || 'mini') as VariantTier;

      // Validate tier value
      if (!['mini', 'pro', 'high'].includes(tier)) {
        set({ tier: 'mini', isLoading: false, lastFetched: Date.now() });
        return;
      }

      set({ tier, isLoading: false, lastFetched: Date.now() });
    } catch (error) {
      // On error, keep existing tier (don't reset to mini)
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch tier',
      });
    }
  },

  fetchUsage: async (companyId?: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/billing/usage`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) return;

      const data = await res.json();
      set({
        usage: {
          agentsUsed: data.agents_used ?? data.agentsUsed ?? 0,
          docsUsed: data.docs_used ?? data.docsUsed ?? 0,
          apiKeysUsed: data.api_keys_used ?? data.apiKeysUsed ?? 0,
          teamMembersUsed: data.team_members_used ?? data.teamMembersUsed ?? 0,
          ticketsThisMonth: data.tickets_this_month ?? data.ticketsThisMonth ?? 0,
          messagesThisMonth: data.messages_this_month ?? data.messagesThisMonth ?? 0,
        },
      });
    } catch {
      // Silently fail — usage is non-critical
    }
  },

  isFeatureAvailable: (feature: keyof FeatureMap): boolean => {
    const features = TIER_FEATURES[get().tier];
    const value = features[feature];
    return typeof value === 'boolean' ? value : true;
  },

  getFeatureMap: (): FeatureMap => {
    return TIER_FEATURES[get().tier];
  },

  isAtLimit: (resource: 'agents' | 'docs' | 'apiKeys' | 'teamMembers'): boolean => {
    const { tier, usage } = get();
    const features = TIER_FEATURES[tier];
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
    set({ tier: 'mini', isLoading: false, error: null, lastFetched: null, usage: DEFAULT_USAGE });
  },
}));

// ── Export feature maps for direct access ──────────────────────────

export { TIER_FEATURES, TIER_ORDER };
