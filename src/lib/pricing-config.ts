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
 * Pricing model: $1 = 1 ticket. What you pay is how many tickets you get.
 *   Parwa:  $2,499/mo = 2,499 tickets/mo  | $29,988/yr
 *   High:   $3,999/mo = 3,999 tickets/mo  | $47,988/yr
 *
 * All variants have the SAME AI capabilities. The only difference
 * is the ticket volume restriction.
 *
 * Mini PARWA was removed on 2026-07-26. Existing Mini subscribers are
 * auto-upgraded to Parwa via normalizeTier().
 *
 * Annual = 12 × monthly. NO discounts. NO free months.
 *
 * Building Codes:
 *   BC-002: All money values use number (cents not needed on frontend,
 *           but never use float arithmetic for billing calculations)
 */

// ── Variant Types ──────────────────────────────────────────────────

export type VariantTier = 'parwa' | 'high';

// ── Prices (Monthly USD) ───────────────────────────────────────────

export const VARIANT_PRICES: Record<VariantTier, number> = {
  parwa: 2499,
  high: 3999,
};

export const VARIANT_ANNUAL_PRICES: Record<VariantTier, number> = {
  parwa: 2499 * 12,   // 29,988
  high: 3999 * 12,    // 47,988
};

// ── Display Names ──────────────────────────────────────────────────

export const VARIANT_DISPLAY_NAMES: Record<VariantTier, string> = {
  parwa: 'PARWA',
  high: 'PARWA High',
};

export const VARIANT_TAGLINES: Record<VariantTier, string> = {
  parwa: 'The Junior Agent',
  high: 'The Senior Agent',
};

// ── Variant Limits — $1 = 1 ticket ────────────────────────────────

export interface VariantLimits {
  monthlyTickets: number;
  aiAgents: number;
  teamMembers: number;
  voiceSlots: number;
  kbDocs: number;
}

/**
 * Pricing model: $1 = 1 ticket.
 * What you pay = how many tickets you get.
 * All variants have the SAME AI capabilities — only ticket volume differs.
 */
export const VARIANT_LIMITS: Record<VariantTier, VariantLimits> = {
  parwa: {
    monthlyTickets: 2499,
    aiAgents: 5,
    teamMembers: 10,
    voiceSlots: 2,
    kbDocs: 500,
  },
  high: {
    monthlyTickets: 3999,
    aiAgents: 8, // 8 base, +$3/agent overage
    teamMembers: 25,
    voiceSlots: 5,
    kbDocs: 2000,
  },
};

// ── AI Pipeline Info ──────────────────────────────────────────────
// All variants have the SAME capabilities. Only ticket volume differs.

export const VARIANT_AI_INFO: Record<VariantTier, {
  pipelineSteps: number;
  aiResolution: number;
  techniques: string;
  concurrentCalls: number;
}> = {
  parwa: {
    pipelineSteps: 9,
    aiResolution: 0.88,
    techniques: 'All 14 techniques (Tier 1+2+3)',
    concurrentCalls: 5,
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
  parwa: 1,
  high: 2,
};

/**
 * Normalize any variant string (including legacy names) to a canonical VariantTier.
 * Mini PARWA was removed 2026-07-26 — legacy 'mini'/'starter'/'mini_parwa' are
 * auto-upgraded to 'parwa' (existing Mini customers get Parwa features for free).
 */
const LEGACY_TIER_MAP: Record<string, VariantTier> = {
  parwa: 'parwa',
  high: 'high',
  // Legacy aliases → auto-upgraded to parwa
  mini: 'parwa',
  starter: 'parwa',
  growth: 'parwa',
  pro: 'parwa',
  mini_parwa: 'parwa',
  parwa_high: 'high',
};

export function normalizeTier(variant: string): VariantTier {
  const lower = variant.toLowerCase().trim();
  return LEGACY_TIER_MAP[lower] || 'parwa';
}

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
    includedIn: ['parwa', 'high'],
  },
  {
    key: 'customApi',
    name: 'Custom API Connector',
    description: 'Connect any REST API with custom auth and schema mapping.',
    price: 49,
    includedIn: ['parwa', 'high'],
  },
];

// ── Overage Pricing ────────────────────────────────────────────────
// $1 per ticket over limit (same as base rate)

export const OVERAGE_PRICE_PER_TICKET = 1.00; // $1 per ticket over limit

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