/**
 * PARWA Pricing Configuration — Frontend Single Source of Truth
 * ═══════════════════════════════════════════════════════════════════
 *
 * This module is the ONLY place where pricing data and variant info
 * should be defined on the frontend. Every other component MUST
 * import from here — never hard-code its own copy.
 *
 * Matches backend: /backend/app/core/pricing_config.py
 *
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║  DO NOT duplicate these constants anywhere else.               ║
 * ║  If you need pricing data → import from pricing-config.        ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 * Correct prices (matching backend SSOT + roadmap D5):
 *   Starter/Mini:  $999/mo   | $11,988/yr   | 500 tickets/mo
 *   Growth/Pro:    $2,499/mo | $29,988/yr   | 2,000 tickets/mo
 *   High:          $4,999/mo | $59,988/yr   | 10,000 tickets/mo
 *
 * Annual = 12 × monthly. NO discounts. NO free months.
 *
 * Building Codes:
 *   BC-002: All money values use number (cents not needed on frontend,
 *           but never use float arithmetic for billing calculations)
 */

// ── Variant Types ──────────────────────────────────────────────────

export type VariantTier = 'starter' | 'growth' | 'high';

/** Legacy aliases still used in some components */
export type LegacyTier = 'mini' | 'pro' | 'high';

/** Onboarding step uses these */
export type OnboardingVariant = 'mini_parwa' | 'parwa' | 'parwa_high';

// ── Name Mappings ──────────────────────────────────────────────────

export const LEGACY_TO_CANONICAL: Record<string, VariantTier> = {
  mini: 'starter',
  pro: 'growth',
  high: 'high',
  mini_parwa: 'starter',
  parwa: 'growth',
  parwa_high: 'high',
  starter: 'starter',
  growth: 'growth',
};

export const CANONICAL_TO_LEGACY: Record<VariantTier, LegacyTier> = {
  starter: 'mini',
  growth: 'pro',
  high: 'high',
};

export const CANONICAL_TO_ONBOARDING: Record<VariantTier, OnboardingVariant> = {
  starter: 'mini_parwa',
  growth: 'parwa',
  high: 'parwa_high',
};

export function normalizeTier(tier: string): VariantTier {
  return LEGACY_TO_CANONICAL[tier.toLowerCase()] || 'starter';
}

// ── Prices (Monthly USD) ───────────────────────────────────────────

export const VARIANT_PRICES: Record<VariantTier, number> = {
  starter: 999,
  growth: 2499,
  high: 4999,
};

export const VARIANT_ANNUAL_PRICES: Record<VariantTier, number> = {
  starter: 999 * 12,    // 11,988
  growth: 2499 * 12,    // 29,988
  high: 4999 * 12,      // 59,988
};

// ── Display Names ──────────────────────────────────────────────────

export const VARIANT_DISPLAY_NAMES: Record<VariantTier, string> = {
  starter: 'Mini PARWA',
  growth: 'PARWA',
  high: 'PARWA High',
};

export const VARIANT_TAGLINES: Record<VariantTier, string> = {
  starter: 'The 24/7 Trainee',
  growth: 'The Junior Agent',
  high: 'The Senior Agent',
};

// ── Variant Limits (matches backend VARIANT_LIMITS) ────────────────

export interface VariantLimits {
  monthlyTickets: number;
  aiAgents: number;
  teamMembers: number;
  voiceSlots: number;
  kbDocs: number;
}

export const VARIANT_LIMITS: Record<VariantTier, VariantLimits> = {
  starter: {
    monthlyTickets: 500,
    aiAgents: 1,
    teamMembers: 3,
    voiceSlots: 0,
    kbDocs: 100,
  },
  growth: {
    monthlyTickets: 2000,
    aiAgents: 3,
    teamMembers: 10,
    voiceSlots: 2,
    kbDocs: 500,
  },
  high: {
    monthlyTickets: 10000,
    aiAgents: 5,
    teamMembers: 25,
    voiceSlots: 5,
    kbDocs: 2000,
  },
};

// ── AI Pipeline Info (from variant_tier_mapper.py) ─────────────────

export const VARIANT_AI_INFO: Record<VariantTier, {
  pipelineSteps: number;
  aiResolution: number;
  techniques: string;
  concurrentCalls: number;
}> = {
  starter: {
    pipelineSteps: 3,
    aiResolution: 0.60,
    techniques: 'Tier 1 (CLARA, CRP, GSD)',
    concurrentCalls: 2,
  },
  growth: {
    pipelineSteps: 6,
    aiResolution: 0.78,
    techniques: 'Tier 1 + Tier 2 (+CoT, ReAct, Reverse Thinking)',
    concurrentCalls: 3,
  },
  high: {
    pipelineSteps: 9,
    aiResolution: 0.88,
    techniques: 'All 14 techniques (Tier 1+2+3)',
    concurrentCalls: 5,
  },
};

// ── Tier Ordering ──────────────────────────────────────────────────

export const VARIANT_TIER_ORDER: Record<VariantTier, number> = {
  starter: 1,
  growth: 2,
  high: 3,
};

export function isUpgrade(oldTier: VariantTier, newTier: VariantTier): boolean {
  return VARIANT_TIER_ORDER[newTier] > VARIANT_TIER_ORDER[oldTier];
}

// ── Add-Ons ────────────────────────────────────────────────────────

export interface AddOn {
  key: 'voice' | 'customApi';
  name: string;
  description: string;
  price: number;
  /** Which variants already include this feature (no extra charge) */
  includedIn: VariantTier[];
}

export const ADD_ONS: AddOn[] = [
  {
    key: 'voice',
    name: 'Voice Channel',
    description: 'AI-powered inbound & outbound voice calls with real-time transcription.',
    price: 199,
    includedIn: ['growth', 'high'],
  },
  {
    key: 'customApi',
    name: 'Custom API Connector',
    description: 'Connect any REST API with custom auth and schema mapping.',
    price: 49,
    includedIn: ['growth', 'high'],
  },
];

// ── Overage Pricing (D7, D10) ──────────────────────────────────────

export const OVERAGE_PRICE_PER_TICKET = 0.10; // $0.10 per ticket over limit

// ── Human Cost Benchmarks (for savings calculation, matches ROI Calculator) ──

export const AGENT_COST_MONTHLY = 4500;
export const TICKETS_PER_AGENT = 400;

// ── Helper: Calculate Overage ──────────────────────────────────────

export function calculateOverage(
  ticketsUsed: number,
  activeVariants: VariantTier[]
): { totalOverageTickets: number; overageCost: number; totalTicketLimit: number } {
  const totalTicketLimit = activeVariants.reduce(
    (sum, tier) => sum + VARIANT_LIMITS[tier].monthlyTickets,
    0
  );
  const totalOverageTickets = Math.max(0, ticketsUsed - totalTicketLimit);
  const overageCost = totalOverageTickets * OVERAGE_PRICE_PER_TICKET;
  return { totalOverageTickets, overageCost, totalTicketLimit };
}

// ── Helper: Calculate Monthly Total ────────────────────────────────

export interface CostBreakdownResult {
  baseSubscription: number;
  addOns: { voice: number; customApi: number };
  overageCost: number;
  totalMonthly: number;
  totalAnnual: number;
  savingsVsHumans: number;
  savingsPercent: number;
  agentsReplaced: number;
  totalTicketLimit: number;
}

export function calculateCostBreakdown(
  activeVariants: VariantTier[],
  addOns: { voice: boolean; customApi: boolean },
  ticketsUsed: number
): CostBreakdownResult {
  // Base subscription
  const baseSubscription = activeVariants.reduce(
    (sum, tier) => sum + VARIANT_PRICES[tier],
    0
  );

  // Add-ons (only charge if not included in any active variant)
  const voiceIncluded = activeVariants.some(t => ADD_ONS[0].includedIn.includes(t));
  const customApiIncluded = activeVariants.some(t => ADD_ONS[1].includedIn.includes(t));
  const voiceCost = addOns.voice && !voiceIncluded ? ADD_ONS[0].price : 0;
  const customApiCost = addOns.customApi && !customApiIncluded ? ADD_ONS[1].price : 0;

  // Overage
  const { overageCost, totalTicketLimit } = calculateOverage(ticketsUsed, activeVariants);

  // Total
  const totalMonthly = baseSubscription + voiceCost + customApiCost + overageCost;
  const totalAnnual = totalMonthly * 12;

  // Savings vs humans
  const agentsReplaced = Math.max(1, Math.round(totalTicketLimit / TICKETS_PER_AGENT));
  const humanCost = agentsReplaced * AGENT_COST_MONTHLY;
  const savingsVsHumans = Math.max(0, humanCost - totalMonthly);
  const savingsPercent = humanCost > 0 ? Math.round((savingsVsHumans / humanCost) * 100) : 0;

  return {
    baseSubscription,
    addOns: { voice: voiceCost, customApi: customApiCost },
    overageCost,
    totalMonthly,
    totalAnnual,
    savingsVsHumans,
    savingsPercent,
    agentsReplaced,
    totalTicketLimit,
  };
}

// ── Helper: "What If" Upgrade Preview ──────────────────────────────

export interface WhatIfPreview {
  currentTotal: number;
  newTotal: number;
  difference: number;
  newTicketLimit: number;
  ticketIncrease: number;
  savingsVsHumans: number;
}

export function calculateWhatIfUpgrade(
  currentVariants: VariantTier[],
  addOns: { voice: boolean; customApi: boolean },
  ticketsUsed: number,
  targetTier: VariantTier
): WhatIfPreview {
  const current = calculateCostBreakdown(currentVariants, addOns, ticketsUsed);

  // Add the target tier if not already present
  const newVariants = currentVariants.includes(targetTier)
    ? currentVariants
    : [...currentVariants, targetTier];
  const upgraded = calculateCostBreakdown(newVariants, addOns, ticketsUsed);

  return {
    currentTotal: current.totalMonthly,
    newTotal: upgraded.totalMonthly,
    difference: upgraded.totalMonthly - current.totalMonthly,
    newTicketLimit: upgraded.totalTicketLimit,
    ticketIncrease: upgraded.totalTicketLimit - current.totalTicketLimit,
    savingsVsHumans: upgraded.savingsVsHumans,
  };
}
