'use client';

import React, { useState, useMemo } from 'react';
import Link from 'next/link';
import NavigationBar from '@/components/landing/NavigationBar';
import Footer from '@/components/landing/Footer';
import {
  Building2,
  Users,
  TicketCheck,
  TrendingUp,
  Zap,
  DollarSign,
  Clock,
  Target,
  Sparkles,
  Check,
  BarChart3,
  PiggyBank,
  Brain,
  Headphones,
  MessageSquare,
  Phone,
  Video,
  Globe,
  Package,
  Layers,
} from 'lucide-react';

// ══════════════════════════════════════════════════════════════════════
// CORRECT PARWA MODEL DATA — matches /models page & system prompt
// ══════════════════════════════════════════════════════════════════════

interface ParwaModel {
  id: string;
  name: string;
  shortName: string;
  tagline: string;
  tier: string;
  price: number;
  aiResolution: number;
  agents: number;
  ticketCapacity: string;
  ticketCapacityNum: number;
  channels: string[];
  description: string;
  bestFor: string;
  tierLabel: string;
  tierColor: string;
  tierBorder: string;
  tierBg: string;
  tierGlow: string;
}

const PARWA_MODELS: ParwaModel[] = [
  {
    id: 'parwa-starter',
    name: 'PARWA Starter',
    shortName: 'Starter',
    tagline: 'The 24/7 Trainee',
    tier: 'Entry',
    price: 999,
    aiResolution: 0.60,
    agents: 3,
    ticketCapacity: '1K tickets/mo',
    ticketCapacityNum: 1000,
    channels: ['Email', 'Chat'],
    description:
      'Your first AI teammate. Handles FAQs, ticket intake, and basic queries autonomously. Perfect for small teams getting started with AI support.',
    bestFor: 'Small teams with FAQ-heavy support, getting started with AI',
    tierLabel: 'Entry Level',
    tierColor: 'text-emerald-400',
    tierBorder: 'border-emerald-500/30',
    tierBg: 'bg-emerald-500/5',
    tierGlow: 'shadow-emerald-500/10',
  },
  {
    id: 'parwa-growth',
    name: 'PARWA Growth',
    shortName: 'Growth',
    tagline: 'The Junior Agent',
    tier: 'Growth',
    price: 2499,
    aiResolution: 0.78,
    agents: 8,
    ticketCapacity: '5K tickets/mo',
    ticketCapacityNum: 5000,
    channels: ['Email', 'Chat', 'SMS', 'Voice'],
    description:
      'Your smartest junior agent. Resolves ~78% of tickets autonomously, supports multi-channel including SMS and voice calls, and always recommends the right path.',
    bestFor: 'Growing businesses needing multi-channel, high-volume support',
    tierLabel: 'Most Popular',
    tierColor: 'text-orange-400',
    tierBorder: 'border-orange-500/30',
    tierBg: 'bg-orange-500/5',
    tierGlow: 'shadow-orange-500/10',
  },
  {
    id: 'parwa-high',
    name: 'PARWA High',
    shortName: 'High',
    tagline: 'The Senior Agent',
    tier: 'Enterprise',
    price: 3999,
    aiResolution: 0.88,
    agents: 15,
    ticketCapacity: '15K tickets/mo',
    ticketCapacityNum: 15000,
    channels: ['Email', 'Chat', 'SMS', 'Voice', 'Social', 'Video'],
    description:
      'Your most experienced senior agent. Handles complex cases, provides strategic insights, predicts churn, and manages up to 15 AI agents across all channels.',
    bestFor: 'Enterprise teams with complex cases, strategic support operations',
    tierLabel: 'Enterprise',
    tierColor: 'text-purple-400',
    tierBorder: 'border-purple-500/30',
    tierBg: 'bg-purple-500/5',
    tierGlow: 'shadow-purple-500/10',
  },
];

// ══════════════════════════════════════════════════════════════════════
// STEP DATA
// ══════════════════════════════════════════════════════════════════════

const INDUSTRIES = [
  { id: 'ecommerce', label: 'E-Commerce' },
  { id: 'saas', label: 'SaaS / Tech' },
  { id: 'logistics', label: 'Logistics' },
  { id: 'healthcare', label: 'Healthcare' },
  { id: 'finance', label: 'Finance' },
  { id: 'realestate', label: 'Real Estate' },
  { id: 'education', label: 'Education' },
  { id: 'others', label: 'Other' },
];

const TEAM_SIZES = [
  { label: '1-5 agents', value: 3 },
  { label: '6-10 agents', value: 8 },
  { label: '11-15 agents', value: 13 },
  { label: '16-30 agents', value: 23 },
  { label: '31-50 agents', value: 40 },
  { label: '50+ agents', value: 75 },
];

// Industry benchmarks — costPerTicket is ALL-IN (labor + tools + overhead)
const BENCHMARKS: Record<
  string,
  { avgTickets: number; avgCostPerTicket: number; avgSalary: number }
> = {
  ecommerce: { avgTickets: 5000, avgCostPerTicket: 6.5, avgSalary: 36000 },
  saas: { avgTickets: 3500, avgCostPerTicket: 8.2, avgSalary: 40000 },
  logistics: { avgTickets: 6000, avgCostPerTicket: 5.8, avgSalary: 34000 },
  healthcare: { avgTickets: 4000, avgCostPerTicket: 7.5, avgSalary: 42000 },
  finance: { avgTickets: 3000, avgCostPerTicket: 9.0, avgSalary: 45000 },
  realestate: { avgTickets: 2500, avgCostPerTicket: 7.0, avgSalary: 38000 },
  education: { avgTickets: 2000, avgCostPerTicket: 6.0, avgSalary: 35000 },
  others: { avgTickets: 3500, avgCostPerTicket: 7.0, avgSalary: 37000 },
};

// ══════════════════════════════════════════════════════════════════════
// HELPERS
// ══════════════════════════════════════════════════════════════════════

function fmt(n: number): string {
  if (n >= 1000000) return `$${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

function fmtMoney(n: number): string {
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  });
}

function fmtNum(n: number): string {
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function getChannelIcon(channel: string) {
  switch (channel) {
    case 'Email':
      return <MessageSquare className="w-3 h-3" />;
    case 'Chat':
      return <MessageSquare className="w-3 h-3" />;
    case 'SMS':
      return <Phone className="w-3 h-3" />;
    case 'Voice':
      return <Headphones className="w-3 h-3" />;
    case 'Social':
      return <Globe className="w-3 h-3" />;
    case 'Video':
      return <Video className="w-3 h-3" />;
    default:
      return <Zap className="w-3 h-3" />;
  }
}

// ══════════════════════════════════════════════════════════════════════
// SMART RECOMMENDATION ENGINE — supports MULTI-TIER COMBINATIONS
// ══════════════════════════════════════════════════════════════════════
// Instead of just stacking the same plan (2x High), this engine finds
// the OPTIMAL COMBINATION of different tiers (e.g., Growth + High)
// that covers all tickets at the LOWEST COST with BEST savings.

interface ComboItem {
  model: ParwaModel;
  quantity: number;
}

interface ComboRecommendation {
  combo: ComboItem[];           // e.g., [{ model: Growth, quantity: 1 }, { model: High, quantity: 1 }]
  label: string;                // e.g., "1x Growth + 1x High"
  totalMonthlyPrice: number;    // subscription cost only
  totalCapacity: number;        // total tickets capacity
  totalAiAgents: number;        // total AI agents across all instances
  coversAllTickets: boolean;
  // Weighted AI resolution based on how tickets are distributed
  weightedAiResolution: number; // e.g., 0.85 for Growth+High combo
  totalAiTickets: number;       // AI-resolved tickets per month
  totalHumanTickets: number;    // tickets needing human attention
  humanCost: number;            // cost of human-handled tickets
  parwaMonthly: number;         // subscription + human cost
  netSavingsPerMonth: number;   // current cost - parwa cost
  reasons: string[];
}

function getOptimalCombo(
  tickets: number,
  agentCount: number,
  industry: string,
  cpt: number,
  currentMonthly: number
): {
  primary: ComboRecommendation;
  alternatives: ComboRecommendation[];
} {
  const bench = BENCHMARKS[industry];
  const industryLabel =
    INDUSTRIES.find((i) => i.id === industry)?.label || 'your industry';

  // Model references for convenience
  const starter = PARWA_MODELS[0]; // 1K capacity, $999, 60% AI
  const growth = PARWA_MODELS[1];   // 5K capacity, $2,499, 78% AI
  const high = PARWA_MODELS[2];     // 15K capacity, $3,999, 88% AI

  // Calculate max instances needed for each model to cover ticket volume
  const maxStarter = Math.ceil(tickets / starter.ticketCapacityNum);
  const maxGrowth = Math.ceil(tickets / growth.ticketCapacityNum);
  const maxHigh = Math.ceil(tickets / high.ticketCapacityNum);

  const combinations: ComboRecommendation[] = [];

  // Edge case: no tickets — return a default recommendation
  if (tickets <= 0) {
    const defaultModel = growth; // Default to Growth as a sensible starting point
    const defaultCombo: ComboRecommendation = {
      combo: [{ model: defaultModel, quantity: 1 }],
      label: defaultModel.shortName,
      totalMonthlyPrice: defaultModel.price,
      totalCapacity: defaultModel.ticketCapacityNum,
      totalAiAgents: defaultModel.agents,
      coversAllTickets: true,
      weightedAiResolution: defaultModel.aiResolution,
      totalAiTickets: 0,
      totalHumanTickets: 0,
      humanCost: 0,
      parwaMonthly: defaultModel.price,
      netSavingsPerMonth: 0,
      reasons: ['Enter your ticket volume to see personalized recommendations.'],
    };
    return { primary: defaultCombo, alternatives: [] };
  }

  // Brute force all valid combinations of Starter/Growth/High instances
  // With 3 models, even for 50K tickets this is only ~140 combos — very fast
  for (let s = 0; s <= maxStarter; s++) {
    for (let g = 0; g <= maxGrowth; g++) {
      for (let h = 0; h <= maxHigh; h++) {
        // Skip empty combination
        if (s === 0 && g === 0 && h === 0) continue;

        const totalCapacity = s * starter.ticketCapacityNum + g * growth.ticketCapacityNum + h * high.ticketCapacityNum;

        // Must cover all tickets
        if (totalCapacity < tickets) continue;

        const totalMonthlyPrice = s * starter.price + g * growth.price + h * high.price;
        const totalAiAgents = s * starter.agents + g * growth.agents + h * high.agents;

        // Distribute tickets to models — best AI resolution first (High > Growth > Starter)
        // This gives the maximum AI resolution for the combination
        let remainingTickets = tickets;

        const highTickets = Math.min(remainingTickets, h * high.ticketCapacityNum);
        const aiHigh = Math.round(highTickets * high.aiResolution);
        remainingTickets -= highTickets;

        const growthTickets = Math.min(remainingTickets, g * growth.ticketCapacityNum);
        const aiGrowth = Math.round(growthTickets * growth.aiResolution);
        remainingTickets -= growthTickets;

        const starterTickets = Math.min(remainingTickets, s * starter.ticketCapacityNum);
        const aiStarter = Math.round(starterTickets * starter.aiResolution);

        const totalAiTickets = aiHigh + aiGrowth + aiStarter;
        const totalHumanTickets = tickets - totalAiTickets;
        const weightedAiResolution = tickets > 0 ? totalAiTickets / tickets : 0;

        // Human cost: remaining tickets cost 25% of original (AI handles triage, context, replies)
        const humanCost = totalHumanTickets * cpt * 0.25;
        const parwaMonthly = totalMonthlyPrice + humanCost;
        const netSavingsPerMonth = Math.max(0, currentMonthly - parwaMonthly);

        // Build label
        const combo: ComboItem[] = [];
        if (s > 0) combo.push({ model: starter, quantity: s });
        if (g > 0) combo.push({ model: growth, quantity: g });
        if (h > 0) combo.push({ model: high, quantity: h });

        const label = combo
          .map((c) => (c.quantity > 1 ? `${c.quantity}x ${c.model.shortName}` : c.model.shortName))
          .join(' + ');

        // Generate smart reasons
        const reasons: string[] = [];

        if (combo.length === 1 && combo[0].quantity === 1) {
          reasons.push(
            `Your volume of ${fmtNum(tickets)} tickets/month fits perfectly within a single ${combo[0].model.name} (${combo[0].model.ticketCapacity} capacity).`
          );
        } else {
          reasons.push(
            `With ${fmtNum(tickets)} tickets/month, the optimal mix is ${label} — total capacity of ${fmtNum(totalCapacity)} tickets at the best price.`
          );
        }

        const aiPct = Math.round(weightedAiResolution * 100);
        if (aiPct >= 85) {
          reasons.push(
            `At ${aiPct}% combined AI resolution, only ${fmtNum(totalHumanTickets)} tickets need human attention — the rest is fully automated.`
          );
        } else if (aiPct >= 75) {
          reasons.push(
            `At ${aiPct}% combined AI resolution, ${fmtNum(totalAiTickets)} of your ${fmtNum(tickets)} tickets are handled automatically.`
          );
        } else {
          reasons.push(
            `At ${aiPct}% AI resolution, ${fmtNum(totalAiTickets)} tickets are auto-resolved — a solid starting point.`
          );
        }

        if (agentCount > 0) {
          const agentsNeeded = Math.max(1, Math.round(agentCount * (1 - weightedAiResolution)));
          if (agentsNeeded < agentCount) {
            reasons.push(
              `Your team of ${agentCount} can be reduced to ~${agentsNeeded} human agents — ${totalAiAgents} AI agents handle the rest.`
            );
          }
        }

        if (netSavingsPerMonth > 0) {
          reasons.push(
            `You save ${fmtMoney(netSavingsPerMonth)}/month — that's ${fmtMoney(netSavingsPerMonth * 12)} back every year.`
          );
        }

        reasons.push(
          `${industryLabel} businesses typically spend $${bench?.avgCostPerTicket || 7}/ticket — ${aiPct}% AI resolution means massive savings.`
        );

        combinations.push({
          combo,
          label,
          totalMonthlyPrice,
          totalCapacity,
          totalAiAgents,
          coversAllTickets: totalCapacity >= tickets,
          weightedAiResolution,
          totalAiTickets,
          totalHumanTickets,
          humanCost,
          parwaMonthly,
          netSavingsPerMonth,
          reasons,
        });
      }
    }
  }

  // ══════════════════════════════════════════════════════════
  // SMART SORTING — recommend the best VALUE combination
  // ══════════════════════════════════════════════════════════
  // Priority:
  // 1. Must save money (PARWA cheaper than current cost)
  // 2. BUSINESS RULE: Never stack lower tiers when a single higher-tier
  //    instance covers all tickets (better AI resolution, simpler setup)
  // 3. Highest net savings (best value for customer)
  // 4. Fewer total instances (simpler setup)
  // 5. Higher AI resolution (better support quality)

  const totalInstances = (c: ComboRecommendation) =>
    c.combo.reduce((sum, item) => sum + item.quantity, 0);

  // BUSINESS RULE: Filter out "anti-recommendations"
  // Stacking lower tiers (e.g., 2x Starter) is worse than one higher tier
  // (e.g., 1x Growth) because: worse AI %, more instances to manage, less headroom
  // Only keep a combo if NO single-tier option exists that covers all tickets
  // with fewer instances AND higher AI resolution at a reasonable price.
  const isBadStack = (c: ComboRecommendation): boolean => {
    // Check if this combo stacks a lower tier when a single higher tier covers all tickets
    // A "bad stack" is when: combo has multiple instances of a low tier AND
    // a single instance of a higher tier covers all tickets AND costs < 2x the combo price
    for (const model of PARWA_MODELS) {
      if (model.ticketCapacityNum >= tickets) {
        // This single model covers all tickets
        const singlePrice = model.price;
        const singleAI = model.aiResolution;
        const comboInst = totalInstances(c);
        const comboAI = c.weightedAiResolution;

        // If the single higher-tier option has better AI AND fewer instances
        // AND isn't outrageously more expensive, the stack is bad
        if (singleAI > comboAI && comboInst > 1 && singlePrice <= c.totalMonthlyPrice * 1.5) {
          return true;
        }
      }
    }
    return false;
  };

  const filtered = combinations.filter((c) => !isBadStack(c));

  // If filtering removed everything (shouldn't happen), fall back to all combinations
  const pool = filtered.length > 0 ? filtered : combinations;

  const saving = pool.filter((c) => c.netSavingsPerMonth > 0);
  const notSaving = pool.filter((c) => c.netSavingsPerMonth <= 0);

  let sorted: ComboRecommendation[];

  if (saving.length > 0) {
    sorted = [...saving].sort((a, b) => {
      // Best savings first
      if (b.netSavingsPerMonth !== a.netSavingsPerMonth)
        return b.netSavingsPerMonth - a.netSavingsPerMonth;
      // Fewer instances = simpler
      const aInst = totalInstances(a);
      const bInst = totalInstances(b);
      if (aInst !== bInst) return aInst - bInst;
      // Higher AI resolution
      if (a.weightedAiResolution !== b.weightedAiResolution)
        return b.weightedAiResolution - a.weightedAiResolution;
      // Cheaper price
      return a.totalMonthlyPrice - b.totalMonthlyPrice;
    });
    // Append non-saving as alternatives
    sorted.push(
      ...notSaving.sort((a, b) => a.totalMonthlyPrice - b.totalMonthlyPrice)
    );
  } else {
    // None save money — pick cheapest covering option
    sorted = [...pool].sort((a, b) => a.totalMonthlyPrice - b.totalMonthlyPrice);
  }

  const primary = sorted[0];
  // For alternatives, pick the top 3 that are DIFFERENT (not just minor variations)
  const alternatives: ComboRecommendation[] = [];
  const seenLabels = new Set([primary.label]);
  for (const opt of sorted.slice(1)) {
    if (!seenLabels.has(opt.label) && alternatives.length < 3) {
      seenLabels.add(opt.label);
      alternatives.push(opt);
    }
  }

  return { primary, alternatives };
}

// ══════════════════════════════════════════════════════════════════════
// ROI CALCULATIONS for the per-tier comparison table
// ══════════════════════════════════════════════════════════════════════

interface ModelComparison {
  model: ParwaModel;
  quantity: number;
  displayLabel: string;
  aiTicketsPerMonth: number;
  humanTicketsPerMonth: number;
  parwaSubscriptionCost: number;
  parwaHumanCost: number;
  parwaMonthlyCost: number;
  parwaAnnualCost: number;
  currentMonthlyCost: number;
  currentAnnualCost: number;
  monthlySavings: number;
  annualSavings: number;
  savingsPercent: number;
  hoursSavedPerMonth: number;
  roiMultiple: number;
  isRecommended: boolean;
}

function calculateComparisons(
  tickets: number,
  cpt: number,
  currentMonthly: number,
  currentAnnual: number,
  primaryCombo: ComboRecommendation
): ModelComparison[] {
  // Show per-tier options (each tier stacked to cover tickets)
  // Plus the optimal combo as a special entry
  const results: ModelComparison[] = [];

  // Per-tier options
  for (const model of PARWA_MODELS) {
    const quantity = Math.max(1, Math.ceil(tickets / model.ticketCapacityNum));
    const aiTickets = Math.round(tickets * model.aiResolution);
    const humanTickets = tickets - aiTickets;
    const parwaSubscription = quantity * model.price;
    const humanCost = humanTickets * cpt * 0.25;
    const parwaMonthly = parwaSubscription + humanCost;
    const parwaAnnual = parwaMonthly * 12;
    const monthlySavings = Math.max(0, currentMonthly - parwaMonthly);
    const annualSavings = Math.max(0, currentAnnual - parwaAnnual);
    const savingsPercent = currentAnnual > 0 ? (annualSavings / currentAnnual) * 100 : 0;
    const hoursSavedPerMonth = aiTickets * 0.25;
    const roiMultiple = parwaAnnual > 0 ? annualSavings / parwaAnnual : 0;

    const displayLabel = quantity > 1 ? `${quantity}x ${model.shortName}` : model.shortName;

    results.push({
      model,
      quantity,
      displayLabel,
      aiTicketsPerMonth: aiTickets,
      humanTicketsPerMonth: humanTickets,
      parwaSubscriptionCost: parwaSubscription,
      parwaHumanCost: humanCost,
      parwaMonthlyCost: parwaMonthly,
      parwaAnnualCost: parwaAnnual,
      currentMonthlyCost: currentMonthly,
      currentAnnualCost: currentAnnual,
      monthlySavings,
      annualSavings,
      savingsPercent,
      hoursSavedPerMonth,
      roiMultiple,
      isRecommended: false,
    });
  }

  // Add the optimal combo as a special entry
  const comboSubCost = primaryCombo.totalMonthlyPrice;
  const comboHumanCost = primaryCombo.humanCost;
  const comboMonthly = primaryCombo.parwaMonthly;
  const comboAnnual = comboMonthly * 12;
  const comboMonthlySavings = Math.max(0, currentMonthly - comboMonthly);
  const comboAnnualSavings = Math.max(0, currentAnnual - comboAnnual);
  const comboSavingsPercent = currentAnnual > 0 ? (comboAnnualSavings / currentAnnual) * 100 : 0;
  const comboHoursSaved = primaryCombo.totalAiTickets * 0.25;
  const comboRoiMultiple = comboAnnual > 0 ? comboAnnualSavings / comboAnnual : 0;

  results.unshift({
    model: PARWA_MODELS[2], // Use High as the "primary model" for styling
    quantity: 1, // Not used for combo
    displayLabel: primaryCombo.label,
    aiTicketsPerMonth: primaryCombo.totalAiTickets,
    humanTicketsPerMonth: primaryCombo.totalHumanTickets,
    parwaSubscriptionCost: comboSubCost,
    parwaHumanCost: comboHumanCost,
    parwaMonthlyCost: comboMonthly,
    parwaAnnualCost: comboAnnual,
    currentMonthlyCost: currentMonthly,
    currentAnnualCost: currentAnnual,
    monthlySavings: comboMonthlySavings,
    annualSavings: comboAnnualSavings,
    savingsPercent: comboSavingsPercent,
    hoursSavedPerMonth: comboHoursSaved,
    roiMultiple: comboRoiMultiple,
    isRecommended: true,
  });

  return results;
}

// ══════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ══════════════════════════════════════════════════════════════════════

export default function ROICalculatorPage() {
  const [step, setStep] = useState(1);
  const [companyName, setCompanyName] = useState('');
  const [industry, setIndustry] = useState('');
  const [monthlyTickets, setMonthlyTickets] = useState('');
  const [teamSizeLabel, setTeamSizeLabel] = useState('');
  const [costPerTicket, setCostPerTicket] = useState('');
  const [currentMonthlyBudget, setCurrentMonthlyBudget] = useState('');

  // ── Derived values ──
  const tickets = Math.max(0, Number(monthlyTickets) || 0);
  const agentCount =
    TEAM_SIZES.find((t) => t.label === teamSizeLabel)?.value || 0;
  const cpt =
    Number(costPerTicket) ||
    BENCHMARKS[industry]?.avgCostPerTicket ||
    7;

  // ── Current monthly cost ──
  // Use user-provided monthly budget if available, otherwise tickets * cpt
  // Cost per ticket is ALL-IN (includes labor, tools, overhead) — NO double counting
  const userBudget = Number(currentMonthlyBudget) || 0;
  const currentTotalMonthly = userBudget > 0 ? userBudget : tickets * cpt;
  const currentTotalAnnual = currentTotalMonthly * 12;

  // ── Recommendation ──
  const { primary: primaryRecommendation, alternatives: alternativeRecommendations } =
    useMemo(
      () => getOptimalCombo(tickets, agentCount, industry, cpt, currentTotalMonthly),
      [tickets, agentCount, industry, cpt, currentTotalMonthly]
    );

  // ── Comparisons ──
  const comparisons = useMemo(
    () =>
      calculateComparisons(
        tickets,
        cpt,
        currentTotalMonthly,
        currentTotalAnnual,
        primaryRecommendation
      ),
    [tickets, cpt, currentTotalMonthly, currentTotalAnnual, primaryRecommendation]
  );

  const recommendedComparison = comparisons.find((c) => c.isRecommended) || comparisons[0];

  // ── Step validation ──
  const canGoNext =
    step === 1
      ? companyName.trim().length > 0 && industry.length > 0
      : step === 2
        ? tickets > 0 && teamSizeLabel.length > 0
        : true;

  const handleNext = () => {
    if (canGoNext && step < 3) setStep(step + 1);
  };
  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  // Max cost for bar chart scaling
  const maxCostForChart = Math.max(currentTotalAnnual, ...comparisons.map((c) => c.parwaAnnualCost));

  // Determine if primary recommendation is a combo (multiple tiers)
  const isCombo = primaryRecommendation.combo.length > 1 ||
    primaryRecommendation.combo.some((c) => c.quantity > 1);

  // Get the "best" model in the combo for display purposes (highest tier)
  const bestModelInCombo = primaryRecommendation.combo[primaryRecommendation.combo.length - 1]?.model || PARWA_MODELS[2];

  // Collect all unique channels from combo
  const comboChannels = [...new Set(primaryRecommendation.combo.flatMap((c) => c.model.channels))];

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: 'linear-gradient(180deg, #0D0D0D 0%, #1A1A1A 50%, #0D0D0D 100%)' }}
    >
      <NavigationBar />

      <main className="flex-grow flex items-start justify-center px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        <div className="w-full max-w-4xl">
          {/* ══════════════════════════════════════════════
              STEP INDICATOR
              ══════════════════════════════════════════════ */}
          <div className="flex items-center justify-center gap-3 mb-10">
            {[
              { n: 1, label: 'Company Info' },
              { n: 2, label: 'Support Setup' },
              { n: 3, label: 'Your Results' },
            ].map((s, i) => (
              <React.Fragment key={s.n}>
                <div className="flex items-center gap-2">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-500 ${
                      step >= s.n
                        ? 'bg-gradient-to-br from-orange-500 to-orange-600 text-white shadow-lg shadow-orange-500/30'
                        : 'bg-white/5 text-gray-500 border border-white/10'
                    }`}
                  >
                    {step > s.n ? (
                      <Check className="w-4 h-4" />
                    ) : (
                      s.n
                    )}
                  </div>
                  <span
                    className={`text-xs font-medium hidden sm:block transition-colors duration-500 ${
                      step >= s.n ? 'text-orange-300' : 'text-gray-600'
                    }`}
                  >
                    {s.label}
                  </span>
                </div>
                {i < 2 && (
                  <div
                    className={`w-8 sm:w-20 h-px transition-all duration-500 ${
                      step > s.n ? 'bg-orange-500/50' : 'bg-white/10'
                    }`}
                  />
                )}
              </React.Fragment>
            ))}
          </div>

          {/* ══════════════════════════════════════════════
              STEP 1: Company Info
              ══════════════════════════════════════════════ */}
          {step === 1 && (
            <div className="animate-[fadeIn_0.4s_ease-out]">
              <div className="text-center mb-8">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/20 mb-4">
                  <Building2 className="w-3.5 h-3.5 text-orange-400" />
                  <span className="text-xs font-semibold text-orange-300">
                    Step 1 of 3
                  </span>
                </div>
                <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white mb-3">
                  Tell us about{' '}
                  <span className="text-orange-400">your business</span>
                </h1>
                <p className="text-sm text-gray-400 max-w-lg mx-auto">
                  We&apos;ll analyze your profile to recommend the perfect PARWA
                  AI model for your support operation.
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 p-6 sm:p-8 space-y-6" style={{ background: 'rgba(255,255,255,0.03)' }}>
                {/* Company Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <Building2 className="w-4 h-4 inline mr-1.5 text-orange-400/70" />
                    Company Name
                  </label>
                  <input
                    type="text"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="e.g. Acme Corp"
                    className="w-full px-4 py-3.5 rounded-xl border border-white/10 bg-white/5 text-white text-sm placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/50 transition-all"
                  />
                </div>

                {/* Industry */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-3">
                    <Target className="w-4 h-4 inline mr-1.5 text-orange-400/70" />
                    Industry
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                    {INDUSTRIES.map((ind) => (
                      <button
                        key={ind.id}
                        onClick={() => setIndustry(ind.id)}
                        className={`flex items-center justify-center gap-2 px-3 py-3.5 rounded-xl text-sm font-medium transition-all duration-300 border ${
                          industry === ind.id
                            ? 'border-orange-500/50 bg-orange-500/10 text-orange-300 shadow-sm shadow-orange-500/10'
                            : 'border-white/10 bg-white/5 text-gray-400 hover:border-white/20 hover:bg-white/[0.07]'
                        }`}
                      >
                        {ind.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ══════════════════════════════════════════════
              STEP 2: Current Support Setup
              ══════════════════════════════════════════════ */}
          {step === 2 && (
            <div className="animate-[fadeIn_0.4s_ease-out]">
              <div className="text-center mb-8">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/20 mb-4">
                  <Users className="w-3.5 h-3.5 text-orange-400" />
                  <span className="text-xs font-semibold text-orange-300">
                    Step 2 of 3
                  </span>
                </div>
                <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white mb-3">
                  Your current{' '}
                  <span className="text-orange-400">support setup</span>
                </h1>
                <p className="text-sm text-gray-400 max-w-lg mx-auto">
                  Help us understand your support volume and costs to calculate
                  accurate savings.
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 p-6 sm:p-8 space-y-6" style={{ background: 'rgba(255,255,255,0.03)' }}>
                {/* Monthly Tickets */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <TicketCheck className="w-4 h-4 inline mr-1.5 text-orange-400/70" />
                    Monthly Support Tickets
                  </label>
                  <input
                    type="number"
                    value={monthlyTickets}
                    onChange={(e) => setMonthlyTickets(e.target.value)}
                    placeholder={
                      BENCHMARKS[industry]
                        ? `${BENCHMARKS[industry].avgTickets} (industry avg)`
                        : 'e.g. 5000'
                    }
                    className="w-full px-4 py-3.5 rounded-xl border border-white/10 bg-white/5 text-white text-sm placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/50 transition-all"
                  />
                  {BENCHMARKS[industry] && (
                    <p className="text-xs text-gray-500 mt-1.5">
                      Industry average:{' '}
                      ~{fmtNum(BENCHMARKS[industry].avgTickets)} tickets/month
                    </p>
                  )}
                </div>

                {/* Team Size */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-3">
                    <Users className="w-4 h-4 inline mr-1.5 text-orange-400/70" />
                    Support Team Size
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                    {TEAM_SIZES.map((ts) => (
                      <button
                        key={ts.label}
                        onClick={() => setTeamSizeLabel(ts.label)}
                        className={`px-4 py-3.5 rounded-xl text-sm font-medium transition-all duration-300 border text-center ${
                          teamSizeLabel === ts.label
                            ? 'border-orange-500/50 bg-orange-500/10 text-orange-300'
                            : 'border-white/10 bg-white/5 text-gray-400 hover:border-white/20 hover:bg-white/[0.07]'
                        }`}
                      >
                        {ts.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Cost Per Ticket */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <DollarSign className="w-4 h-4 inline mr-1.5 text-orange-400/70" />
                    Average Cost per Ticket{' '}
                    <span className="text-gray-600 font-normal">(all-in: labor + tools + overhead)</span>
                  </label>
                  <input
                    type="number"
                    step="0.50"
                    value={costPerTicket}
                    onChange={(e) => setCostPerTicket(e.target.value)}
                    placeholder={
                      BENCHMARKS[industry]
                        ? `$${BENCHMARKS[industry].avgCostPerTicket} (industry avg)`
                        : 'e.g. 6.50'
                    }
                    className="w-full px-4 py-3.5 rounded-xl border border-white/10 bg-white/5 text-white text-sm placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/50 transition-all"
                  />
                  {BENCHMARKS[industry] && (
                    <p className="text-xs text-gray-500 mt-1.5">
                      Industry average: ~$
                      {BENCHMARKS[industry].avgCostPerTicket}/ticket (includes labor, tools, overhead)
                    </p>
                  )}
                </div>

                {/* Current Monthly Support Budget */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <DollarSign className="w-4 h-4 inline mr-1.5 text-orange-400/70" />
                    Current Monthly Support Spend{' '}
                    <span className="text-gray-600 font-normal">(optional — overrides cost/ticket calc)</span>
                  </label>
                  <input
                    type="number"
                    step="100"
                    value={currentMonthlyBudget}
                    onChange={(e) => setCurrentMonthlyBudget(e.target.value)}
                    placeholder="e.g. 35000"
                    className="w-full px-4 py-3.5 rounded-xl border border-white/10 bg-white/5 text-white text-sm placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/50 transition-all"
                  />
                  <p className="text-xs text-gray-500 mt-1.5">
                    {userBudget > 0
                      ? `Using your budget of ${fmtMoney(userBudget)}/mo as current cost`
                      : `Using tickets x cost/ticket = ${fmtMoney(tickets * cpt)}/mo as current cost`
                    }
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* ══════════════════════════════════════════════════════════
              STEP 3: RESULTS — THE HERO
              ══════════════════════════════════════════════════════════ */}
          {step === 3 && (
            <div className="animate-[fadeIn_0.4s_ease-out] space-y-6">
              {/* ── Section Title ── */}
              <div className="text-center mb-2">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 mb-4">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-xs font-semibold text-emerald-300">
                    Your Personalized ROI Report
                  </span>
                </div>
                <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white mb-2">
                  Here&apos;s what{' '}
                  <span className="text-orange-400">{companyName}</span> saves
                </h1>
                <p className="text-sm text-gray-400">
                  Based on {fmtNum(tickets)} tickets/mo and a{' '}
                  {teamSizeLabel} team in{' '}
                  {INDUSTRIES.find((i) => i.id === industry)?.label || 'your industry'}
                </p>
              </div>

              {/* ════════════════════════════════════════
                  A. RECOMMENDED COMBO — BIG HERO CARD
                  ════════════════════════════════════════ */}
              <div
                className="rounded-2xl border-2 border-orange-500/40 p-6 sm:p-8 relative overflow-hidden"
                style={{
                  background:
                    'linear-gradient(135deg, rgba(255,127,17,0.12) 0%, rgba(26,26,26,0.9) 60%, rgba(255,127,17,0.05) 100%)',
                }}
              >
                {/* Decorative glow */}
                <div className="absolute -top-20 -right-20 w-60 h-60 bg-orange-500/10 rounded-full blur-[100px] pointer-events-none" />

                <div className="relative">
                  {/* Badge */}
                  <div className="flex items-center gap-2 mb-5 flex-wrap">
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-orange-500/20 border border-orange-500/30">
                      <Sparkles className="w-3.5 h-3.5 text-orange-400" />
                      <span className="text-xs font-bold text-orange-300 uppercase tracking-wider">
                        Best Value for You
                      </span>
                    </div>
                    {isCombo && (
                      <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-300">
                        <Layers className="w-3 h-3 inline mr-1" />
                        Multi-Tier Combo
                      </span>
                    )}
                  </div>

                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-4">
                    <div>
                      <h2 className="text-2xl sm:text-3xl font-black text-white mb-1">
                        {primaryRecommendation.label}
                      </h2>
                      <p className="text-base text-orange-300/80 font-medium">
                        {isCombo
                          ? `Optimal mix for ${fmtNum(tickets)} tickets/mo`
                          : `&ldquo;${bestModelInCombo.tagline}&rdquo;`}
                      </p>
                    </div>
                    <div className="text-left sm:text-right flex-shrink-0">
                      <div className="text-4xl font-black text-orange-400">
                        ${primaryRecommendation.totalMonthlyPrice.toLocaleString()}
                      </div>
                      <div className="text-sm text-gray-400">/month
                        {isCombo && (
                          <span className="text-gray-500">
                            {' '}
                            ({primaryRecommendation.combo.map((c) => `${c.quantity}x $${c.model.price.toLocaleString()}`).join(' + ')})
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Combo breakdown cards */}
                  {isCombo && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-5">
                      {primaryRecommendation.combo.map((item) => (
                        <div
                          key={item.model.id}
                          className={`rounded-xl border ${item.model.tierBorder} ${item.model.tierBg} p-3`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className={`text-sm font-bold ${item.model.tierColor}`}>
                              {item.quantity > 1 ? `${item.quantity}x ` : ''}{item.model.shortName}
                            </span>
                            <span className="text-xs text-gray-400">
                              ${item.model.price.toLocaleString()}/mo
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-gray-500">
                            <span>
                              <TicketCheck className="w-3 h-3 inline mr-0.5" />
                              {item.model.ticketCapacity}
                            </span>
                            <span>
                              <Brain className="w-3 h-3 inline mr-0.5" />
                              {Math.round(item.model.aiResolution * 100)}% AI
                            </span>
                            <span>
                              <Users className="w-3 h-3 inline mr-0.5" />
                              {item.model.agents * item.quantity} agents
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Quick specs */}
                  <div className="flex flex-wrap gap-2 mb-5">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300">
                      <Brain className="w-3 h-3 text-orange-400" />
                      {Math.round(primaryRecommendation.weightedAiResolution * 100)}% AI Resolution
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300">
                      <Users className="w-3 h-3 text-orange-400" />
                      {primaryRecommendation.totalAiAgents} AI Agents
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300">
                      <TicketCheck className="w-3 h-3 text-orange-400" />
                      {fmtNum(primaryRecommendation.totalCapacity)} tickets/mo capacity
                    </span>
                    {comboChannels.slice(0, 4).map((ch) => (
                      <span
                        key={ch}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300"
                      >
                        {getChannelIcon(ch)}
                        {ch}
                      </span>
                    ))}
                    {comboChannels.length > 4 && (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300">
                        +{comboChannels.length - 4} more
                      </span>
                    )}
                  </div>

                  {/* WHY reasons — SMART explanation */}
                  <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Brain className="w-4 h-4 text-orange-400" />
                      <span className="text-sm font-bold text-orange-200">
                        Why {primaryRecommendation.label} for {companyName}?
                      </span>
                    </div>
                    <ul className="space-y-2">
                      {primaryRecommendation.reasons.map((reason, i) => (
                        <li key={i} className="flex items-start gap-2.5">
                          <div className="w-5 h-5 rounded-full bg-orange-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <Check className="w-3 h-3 text-orange-400" />
                          </div>
                          <span className="text-sm text-gray-300 leading-relaxed">
                            {reason}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>

              {/* ════════════════════════════════════════
                  B. BIG SAVINGS HERO — Headline numbers
                  ════════════════════════════════════════ */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-center">
                  <PiggyBank className="w-5 h-5 text-emerald-400 mx-auto mb-2" />
                  <div className="text-2xl sm:text-3xl font-black text-emerald-400">
                    {fmtMoney(recommendedComparison.annualSavings)}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    Annual Savings
                  </div>
                </div>
                <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-4 text-center">
                  <TrendingUp className="w-5 h-5 text-orange-400 mx-auto mb-2" />
                  <div className="text-2xl sm:text-3xl font-black text-orange-400">
                    {recommendedComparison.savingsPercent.toFixed(0)}%
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    Cost Reduction
                  </div>
                </div>
                <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4 text-center">
                  <Clock className="w-5 h-5 text-blue-400 mx-auto mb-2" />
                  <div className="text-2xl sm:text-3xl font-black text-blue-400">
                    {fmtNum(recommendedComparison.hoursSavedPerMonth)}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    Hours Saved/Mo
                  </div>
                </div>
                <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-4 text-center">
                  <BarChart3 className="w-5 h-5 text-purple-400 mx-auto mb-2" />
                  <div className="text-2xl sm:text-3xl font-black text-purple-400">
                    {recommendedComparison.roiMultiple.toFixed(1)}x
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    ROI Multiple
                  </div>
                </div>
              </div>

              {/* ════════════════════════════════════════
                  C. COST COMPARISON — Before vs After
                  ════════════════════════════════════════ */}
              <div className="rounded-2xl border border-white/10 p-6 sm:p-8" style={{ background: 'rgba(255,255,255,0.03)' }}>
                <div className="flex items-center gap-2 mb-6">
                  <BarChart3 className="w-5 h-5 text-orange-400" />
                  <h3 className="text-lg font-bold text-white">
                    Cost Comparison
                  </h3>
                </div>

                {/* Current cost bar */}
                <div className="mb-6">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-300">
                      Current Monthly Cost
                    </span>
                    <span className="text-sm font-bold text-red-400">
                      {fmtMoney(currentTotalMonthly)}/mo
                    </span>
                  </div>
                  <div className="w-full h-4 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-red-500/80 to-red-400/80 transition-all duration-1000"
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>

                {/* PARWA cost bar */}
                <div className="mb-2">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-300">
                      With {primaryRecommendation.label}
                    </span>
                    <span className="text-sm font-bold text-emerald-400">
                      {fmtMoney(recommendedComparison.parwaMonthlyCost)}/mo
                    </span>
                  </div>
                  <div className="w-full h-4 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-emerald-500/80 to-emerald-400/80 transition-all duration-1000"
                      style={{
                        width: `${Math.max(5, (recommendedComparison.parwaMonthlyCost / currentTotalMonthly) * 100)}%`,
                      }}
                    />
                  </div>
                </div>

                <div className="mt-4 flex items-center gap-2 px-4 py-3 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
                  <PiggyBank className="w-4 h-4 text-emerald-400" />
                  <span className="text-sm text-emerald-300 font-medium">
                    You save {fmtMoney(recommendedComparison.monthlySavings)}/month = {fmtMoney(recommendedComparison.annualSavings)}/year
                  </span>
                </div>
              </div>

              {/* ════════════════════════════════════════
                  D. ALL OPTIONS COMPARISON TABLE
                  ════════════════════════════════════════ */}
              <div className="rounded-2xl border border-white/10 p-6 sm:p-8" style={{ background: 'rgba(255,255,255,0.03)' }}>
                <div className="flex items-center gap-2 mb-6">
                  <Layers className="w-5 h-5 text-orange-400" />
                  <h3 className="text-lg font-bold text-white">
                    All Options Compared
                  </h3>
                </div>

                <div className="space-y-3">
                  {comparisons.map((comp, i) => (
                    <div
                      key={i}
                      className={`rounded-xl border p-4 transition-all ${
                        comp.isRecommended
                          ? 'border-orange-500/40 bg-orange-500/5'
                          : 'border-white/10 bg-white/[0.02] hover:border-white/20'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          {comp.isRecommended && (
                            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-300 text-xs font-bold">
                              <Sparkles className="w-3 h-3" />
                              Best Value
                            </span>
                          )}
                          <span className={`text-sm font-bold ${comp.isRecommended ? 'text-orange-300' : 'text-white'}`}>
                            {comp.displayLabel}
                          </span>
                        </div>
                        <span className={`text-lg font-black ${comp.isRecommended ? 'text-orange-400' : 'text-white'}`}>
                          ${comp.parwaSubscriptionCost.toLocaleString()}
                          <span className="text-xs text-gray-500 font-normal">/mo</span>
                        </span>
                      </div>

                      {/* Stats row */}
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400">
                        <span>
                          <Brain className="w-3 h-3 inline mr-0.5 text-orange-400/60" />
                          {comp.displayLabel === primaryRecommendation.label
                            ? `${Math.round(primaryRecommendation.weightedAiResolution * 100)}% AI`
                            : `${Math.round(comp.model.aiResolution * 100)}% AI`}
                        </span>
                        <span>
                          <TicketCheck className="w-3 h-3 inline mr-0.5 text-orange-400/60" />
                          {comp.displayLabel === primaryRecommendation.label
                            ? `${fmtNum(primaryRecommendation.totalCapacity)} capacity`
                            : `${fmtNum(comp.quantity * comp.model.ticketCapacityNum)} capacity`}
                        </span>
                        <span className="text-emerald-400">
                          Saves {fmtMoney(comp.annualSavings)}/yr
                        </span>
                        <span className="text-gray-500">
                          ROI {comp.roiMultiple.toFixed(1)}x
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* ════════════════════════════════════════
                  E. ALTERNATIVE COMBOS
                  ════════════════════════════════════════ */}
              {alternativeRecommendations.length > 0 && (
                <div className="rounded-2xl border border-white/10 p-6 sm:p-8" style={{ background: 'rgba(255,255,255,0.03)' }}>
                  <div className="flex items-center gap-2 mb-5">
                    <Package className="w-5 h-5 text-blue-400" />
                    <h3 className="text-lg font-bold text-white">
                      Other Configurations
                    </h3>
                  </div>

                  <div className="space-y-3">
                    {alternativeRecommendations.map((alt, i) => (
                      <div
                        key={i}
                        className="rounded-xl border border-white/10 bg-white/[0.02] p-4 hover:border-white/20 transition-all"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-bold text-white">
                            {alt.label}
                          </span>
                          <div className="text-right">
                            <span className="text-sm font-bold text-white">
                              ${alt.totalMonthlyPrice.toLocaleString()}
                            </span>
                            <span className="text-xs text-gray-500">/mo</span>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400">
                          <span>
                            <Brain className="w-3 h-3 inline mr-0.5" />
                            {Math.round(alt.weightedAiResolution * 100)}% AI
                          </span>
                          <span>
                            <TicketCheck className="w-3 h-3 inline mr-0.5" />
                            {fmtNum(alt.totalCapacity)} capacity
                          </span>
                          <span className="text-emerald-400">
                            Saves {fmtMoney(alt.netSavingsPerMonth)}/mo
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ════════════════════════════════════════
                  F. CTA
                  ════════════════════════════════════════ */}
              <div className="text-center pt-4 pb-8">
                <Link
                  href="/models"
                  className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-gradient-to-r from-orange-500 to-orange-600 text-white font-bold text-base hover:from-orange-600 hover:to-orange-700 transition-all shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40"
                >
                  Get Started with {primaryRecommendation.label}
                  <Zap className="w-5 h-5" />
                </Link>
                <p className="text-xs text-gray-500 mt-3">
                  No credit card required. 14-day free trial on all plans.
                </p>
              </div>
            </div>
          )}

          {/* ── Navigation Buttons ── */}
          {step < 3 && (
            <div className="flex items-center justify-between mt-8">
              <button
                onClick={handleBack}
                disabled={step === 1}
                className={`flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-medium transition-all ${
                  step === 1
                    ? 'opacity-0 pointer-events-none'
                    : 'border border-white/10 text-gray-400 hover:bg-white/5 hover:text-white'
                }`}
              >
                Back
              </button>
              <button
                onClick={handleNext}
                disabled={!canGoNext}
                className={`flex items-center gap-2 px-8 py-3 rounded-xl text-sm font-bold transition-all ${
                  canGoNext
                    ? 'bg-gradient-to-r from-orange-500 to-orange-600 text-white shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40'
                    : 'bg-white/5 text-gray-600 cursor-not-allowed'
                }`}
              >
                {step === 2 ? 'Calculate ROI' : 'Continue'}
                <Zap className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Back button on step 3 */}
          {step === 3 && (
            <div className="flex items-center justify-start mt-6">
              <button
                onClick={handleBack}
                className="flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-medium border border-white/10 text-gray-400 hover:bg-white/5 hover:text-white transition-all"
              >
                Back
              </button>
            </div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  );
}
