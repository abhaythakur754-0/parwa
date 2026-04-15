'use client';

import React, { useState, useMemo } from 'react';
import Link from 'next/link';
import NavigationBar from '@/components/landing/NavigationBar';
import Footer from '@/components/landing/Footer';
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Users,
  TicketCheck,
  TrendingUp,
  Zap,
  DollarSign,
  Clock,
  Target,
  Sparkles,
  ChevronRight,
  Check,
  CircleDot,
  BarChart3,
  PiggyBank,
  Brain,
  Headphones,
  MessageSquare,
  Phone,
  Video,
  Globe,
  ShieldCheck,
  ArrowDownRight,
  ThumbsUp,
} from 'lucide-react';

// ══════════════════════════════════════════════════════════════════════
// CORRECT PARWA MODEL DATA — matches /models page & system prompt
// ══════════════════════════════════════════════════════════════════════

interface ParwaModel {
  id: string;
  name: string;
  tagline: string;
  tier: string;
  price: number;
  aiResolution: number;
  agents: number;
  ticketCapacity: string;
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
    tagline: 'The 24/7 Trainee',
    tier: 'Entry',
    price: 999,
    aiResolution: 0.60,
    agents: 3,
    ticketCapacity: '1K tickets/mo',
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
    tagline: 'The Junior Agent',
    tier: 'Growth',
    price: 2499,
    aiResolution: 0.78,
    agents: 8,
    ticketCapacity: '5K tickets/mo',
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
    tagline: 'The Senior Agent',
    tier: 'Enterprise',
    price: 3999,
    aiResolution: 0.88,
    agents: 15,
    ticketCapacity: '15K tickets/mo',
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
  { id: 'finance', label: 'Finance' },
  { id: 'realestate', label: 'Real Estate' },
  { id: 'education', label: 'Education' },
  { id: 'others', label: 'Other' },
];

const TEAM_SIZES = [
  { label: '3–15 agents', value: 3 },
  { label: '6–10 agents', value: 8 },
  { label: '11–15 agents', value: 13 },
  { label: '16–30 agents', value: 23 },
  { label: '31–50 agents', value: 40 },
  { label: '50+ agents', value: 75 },
];

// Industry benchmarks
const BENCHMARKS: Record<
  string,
  { avgTickets: number; avgCostPerTicket: number; avgSalary: number }
> = {
  ecommerce: { avgTickets: 5000, avgCostPerTicket: 6.5, avgSalary: 36000 },
  saas: { avgTickets: 3500, avgCostPerTicket: 8.2, avgSalary: 40000 },
  logistics: { avgTickets: 6000, avgCostPerTicket: 5.8, avgSalary: 34000 },
  finance: { avgTickets: 4000, avgCostPerTicket: 7.5, avgSalary: 42000 },
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
// SMART RECOMMENDATION ENGINE
// ══════════════════════════════════════════════════════════════════════

function getRecommendedModel(
  tickets: number,
  agentCount: number,
  industry: string
): {
  model: ParwaModel;
  reasons: string[];
} {
  const bench = BENCHMARKS[industry];
  const industryLabel =
    INDUSTRIES.find((i) => i.id === industry)?.label || 'your industry';
  const reasons: string[] = [];

  let recommended: ParwaModel;

  if (tickets <= 1000 && agentCount <= 5) {
    recommended = PARWA_MODELS[0]; // Starter
    reasons.push(
      `Your volume of ${fmtNum(tickets)} tickets/month fits within the Starter tier's 1K ticket capacity.`
    );
    if (agentCount <= 3) {
      reasons.push(
        `With ${agentCount} agent${agentCount > 1 ? 's' : ''}, the Starter's 3-agent configuration covers your entire team.`
      );
    }
    reasons.push(
      `At ${industryLabel}'s average cost of $${bench?.avgCostPerTicket || 7}/ticket, even 60% AI resolution saves you significantly.`
    );
  } else if (tickets <= 5000 && agentCount <= 15) {
    recommended = PARWA_MODELS[1]; // Growth
    if (tickets > 1000) {
      reasons.push(
        `Your ${fmtNum(tickets)} tickets/month exceeds the Starter tier's 1K limit — Growth's 5K capacity gives you room to scale.`
      );
    }
    if (agentCount > 5) {
      reasons.push(
        `With ${agentCount} team members, Growth's 8-agent setup matches your team structure.`
      );
    }
    reasons.push(
      `Growth resolves ~78% of tickets autonomously and adds SMS + Voice channels — critical for ${industryLabel}.`
    );
  } else {
    recommended = PARWA_MODELS[2]; // High
    if (tickets > 5000) {
      reasons.push(
        `Your volume of ${fmtNum(tickets)} tickets/month requires the High plan's 15K capacity.`
      );
    }
    if (agentCount > 15) {
      reasons.push(
        `Your ${agentCount}-person team needs High's 15-agent configuration for full coverage.`
      );
    }
    reasons.push(
      `High's 88% AI resolution and full channel support (Social + Video) are ideal for your ${industryLabel} operation.`
    );
    reasons.push(
      `Enterprise features like churn prediction and strategic insights drive long-term ROI.`
    );
  }

  return { model: recommended, reasons };
}

// ══════════════════════════════════════════════════════════════════════
// ROI CALCULATIONS
// ══════════════════════════════════════════════════════════════════════

interface ModelComparison {
  model: ParwaModel;
  aiTicketsPerMonth: number;
  humanTicketsPerMonth: number;
  parwaMonthlyCost: number;
  parwaAnnualCost: number;
  currentMonthlyCost: number;
  currentAnnualCost: number;
  monthlySavings: number;
  annualSavings: number;
  savingsPercent: number;
  hoursSavedPerMonth: number;
  paybackMonths: number;
  isRecommended: boolean;
  quantity: number;
}

function calculateComparisons(
  tickets: number,
  agentCount: number,
  cpt: number,
  currentMonthly: number,
  currentAnnual: number,
  recommendedId: string
): ModelComparison[] {
  return PARWA_MODELS.map((model) => {
    // ── Quantity Scaling Logic ──
    const quantity = Math.max(1, Math.ceil(tickets / (Number(model.ticketCapacity.replace(/[^0-9]/g, '')) || 1000)));
    
    // Split volume into AI-resolved and human-handled
    const aiTickets = Math.round(tickets * model.aiResolution);
    const humanTickets = tickets - aiTickets;

    // PARWA cost = (platform fee * quantity) + remaining human ticket costs (at 25% efficiency gain)
    const humanCost = humanTickets * cpt * 0.25;
    const platformCost = model.price * quantity;
    const parwaMonthly = platformCost + humanCost;
    const parwaAnnual = parwaMonthly * 12;
    const monthlySavings = Math.max(0, currentMonthly - parwaMonthly);
    const annualSavings = Math.max(0, currentAnnual - parwaAnnual);
    const savingsPercent =
      currentAnnual > 0 ? (annualSavings / currentAnnual) * 100 : 0;
    const hoursSavedPerMonth = aiTickets * 0.25; // ~15min per ticket
    const paybackMonths =
      monthlySavings > 0 ? parwaMonthly / monthlySavings : 999;

    return {
      model,
      aiTicketsPerMonth: aiTickets,
      humanTicketsPerMonth: humanTickets,
      parwaMonthlyCost: parwaMonthly,
      parwaAnnualCost: parwaAnnual,
      currentMonthlyCost: currentMonthly,
      currentAnnualCost: currentAnnual,
      monthlySavings,
      annualSavings,
      savingsPercent,
      hoursSavedPerMonth,
      paybackMonths: Math.min(12, Math.max(1, paybackMonths)),
      isRecommended: model.id === recommendedId,
      quantity,
    };
  });
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

  // ── Derived values ──
  const tickets = Math.max(0, Number(monthlyTickets) || 0);
  const agentCount =
    TEAM_SIZES.find((t) => t.label === teamSizeLabel)?.value || 0;
  const cpt =
    Number(costPerTicket) ||
    BENCHMARKS[industry]?.avgCostPerTicket ||
    7;
  const avgSalary = BENCHMARKS[industry]?.avgSalary || 37000;

  // Current costs
  const currentLaborMonthly =
    agentCount > 0 ? (avgSalary / 12) * agentCount : 0;
  const currentTicketCostMonthly = tickets * cpt;
  const currentTotalMonthly = currentLaborMonthly + currentTicketCostMonthly;
  const currentTotalAnnual = currentTotalMonthly * 12;

  // ── Recommendation ──
  const { model: recommendedModel, reasons: recommendationReasons } =
    useMemo(
      () => getRecommendedModel(tickets, agentCount, industry),
      [tickets, agentCount, industry]
    );

  // ── Comparisons ──
  const comparisons = useMemo(
    () =>
      calculateComparisons(
        tickets,
        agentCount,
        cpt,
        currentTotalMonthly,
        currentTotalAnnual,
        recommendedModel.id
      ),
    [tickets, agentCount, cpt, currentTotalMonthly, currentTotalAnnual, recommendedModel.id]
  );

  const recommendedComparison = comparisons.find((c) => c.isRecommended)!;

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

  // Max current cost for bar chart scaling
  const maxCostForChart = Math.max(currentTotalAnnual, ...comparisons.map((c) => c.currentAnnualCost));

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
                  Help us understand your support volume and team to calculate
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
                    <span className="text-gray-600 font-normal">(optional)</span>
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
                      {BENCHMARKS[industry].avgCostPerTicket}/ticket
                    </p>
                  )}
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
                  A. RECOMMENDED MODEL — BIG HERO CARD
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
                  <div className="flex items-center gap-2 mb-5">
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-orange-500/20 border border-orange-500/30">
                      <Sparkles className="w-3.5 h-3.5 text-orange-400" />
                      <span className="text-xs font-bold text-orange-300 uppercase tracking-wider">
                        Recommended for You
                      </span>
                    </div>
                    <span
                      className={`text-xs font-semibold px-2.5 py-1 rounded-full ${recommendedModel.tierBg} ${recommendedModel.tierBorder} border ${recommendedModel.tierColor}`}
                    >
                      {recommendedModel.tierLabel}
                    </span>
                  </div>

                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-4">
                    <div>
                      <h2 className="text-2xl sm:text-3xl font-black text-white mb-1">
                        {recommendedComparison.quantity > 1 ? `${recommendedComparison.quantity}x ` : ''}
                        {recommendedModel.name}
                      </h2>
                      <p className="text-base text-orange-300/80 font-medium">
                        &ldquo;{recommendedModel.tagline}&rdquo;
                      </p>
                    </div>
                    <div className="text-left sm:text-right flex-shrink-0">
                      <div className="text-4xl font-black text-orange-400">
                        ${(recommendedModel.price * recommendedComparison.quantity).toLocaleString()}
                      </div>
                      <div className="text-sm text-gray-400">/month</div>
                    </div>
                  </div>

                  <p className="text-sm text-gray-400 leading-relaxed mb-5">
                    {recommendedModel.description}
                  </p>

                  {/* Quick specs */}
                  <div className="flex flex-wrap gap-2 mb-5">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300">
                      <Brain className="w-3 h-3 text-orange-400" />
                      {Math.round(recommendedModel.aiResolution * 100)}% AI Resolution
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300">
                      <Users className="w-3 h-3 text-orange-400" />
                      {recommendedModel.agents} AI Agents
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-orange-500/10 border border-orange-500/20 text-xs text-orange-300 font-bold">
                      <TicketCheck className="w-3 h-3 text-orange-400" />
                      Total Capacity: {fmtNum(recommendedModel.ticketCapacity * recommendedComparison.quantity)}
                    </span>
                    {recommendedModel.channels.map((ch) => (
                      <span
                        key={ch}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300"
                      >
                        {getChannelIcon(ch)}
                        {ch}
                      </span>
                    ))}
                  </div>

                  {/* WHY reasons — SMART explanation */}
                  <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Brain className="w-4 h-4 text-orange-400" />
                      <span className="text-sm font-bold text-orange-200">
                        Why this model for {companyName}?
                      </span>
                    </div>
                    <ul className="space-y-2">
                      {recommendationReasons.map((reason, i) => (
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
                    {fmtNum(recommendedComparison.hoursSavedPerMonth)}h
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    Hours Saved/Month
                  </div>
                </div>
                <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-4 text-center">
                  <Zap className="w-5 h-5 text-purple-400 mx-auto mb-2" />
                  <div className="text-2xl sm:text-3xl font-black text-purple-400">
                    {recommendedComparison.paybackMonths.toFixed(1)}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    Month Payback
                  </div>
                </div>
              </div>

              {/* ════════════════════════════════════════
                  C. SIDE-BY-SIDE COMPARISON TABLE
                  ════════════════════════════════════════ */}
              <div
                className="rounded-2xl border border-white/10 overflow-hidden"
                style={{ background: 'rgba(255,255,255,0.03)' }}
              >
                <div className="px-5 py-4 border-b border-white/10 flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-orange-400" />
                  <h3 className="text-base sm:text-lg font-bold text-white">
                    Cost Comparison: Before vs After PARWA
                  </h3>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/5">
                        <th className="text-left px-5 py-3.5 text-gray-500 font-medium text-xs uppercase tracking-wider">
                          Metric
                        </th>
                        <th className="text-right px-5 py-3.5 text-gray-500 font-medium text-xs uppercase tracking-wider">
                          <span className="inline-flex items-center gap-1.5">
                            <ArrowDownRight className="w-3 h-3 text-red-400" />
                            Your Current Setup
                          </span>
                        </th>
                        <th className="text-right px-5 py-3.5 text-orange-400 font-medium text-xs uppercase tracking-wider">
                          <span className="inline-flex items-center gap-1.5">
                            <ThumbsUp className="w-3 h-3" />
                            With {recommendedModel.name}
                          </span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {/* Agent headcount */}
                      <tr className="border-b border-white/5">
                        <td className="px-5 py-3.5 text-gray-300 font-medium">
                          Support Agents
                        </td>
                        <td className="px-5 py-3.5 text-right text-gray-400">
                          {agentCount} humans
                        </td>
                        <td className="px-5 py-3.5 text-right text-gray-300 font-semibold">
                          {recommendedModel.agents} AI +{' '}
                          {Math.max(
                            1,
                            Math.round(agentCount * (1 - recommendedModel.aiResolution))
                          )}{' '}
                          humans
                        </td>
                      </tr>
                      {/* Tickets breakdown */}
                      <tr className="border-b border-white/5">
                        <td className="px-5 py-3.5 text-gray-300 font-medium">
                          Monthly Tickets
                        </td>
                        <td className="px-5 py-3.5 text-right text-gray-400">
                          {fmtNum(tickets)} manual
                        </td>
                        <td className="px-5 py-3.5 text-right text-gray-300 font-semibold">
                          {fmtNum(recommendedComparison.aiTicketsPerMonth)} AI +{' '}
                          {fmtNum(recommendedComparison.humanTicketsPerMonth)} human
                        </td>
                      </tr>
                      {/* AI Resolution */}
                      <tr className="border-b border-white/5">
                        <td className="px-5 py-3.5 text-gray-300 font-medium">
                          AI Resolution Rate
                        </td>
                        <td className="px-5 py-3.5 text-right text-gray-400">
                          0%
                        </td>
                        <td className="px-5 py-3.5 text-right text-orange-400 font-bold">
                          {Math.round(recommendedModel.aiResolution * 100)}%
                        </td>
                      </tr>
                      {/* Agent labor cost */}
                      <tr className="border-b border-white/5">
                        <td className="px-5 py-3.5 text-gray-300 font-medium">
                          Agent Labor Cost
                        </td>
                        <td className="px-5 py-3.5 text-right text-gray-400">
                          {fmtMoney(currentLaborMonthly)}/mo
                        </td>
                        <td className="px-5 py-3.5 text-right text-gray-300 font-semibold">
                          {fmtMoney(
                            recommendedComparison.humanTicketsPerMonth * cpt * 0.25
                          )}
                          /mo
                        </td>
                      </tr>
                      {/* Platform cost */}
                      <tr className="border-b border-white/5">
                        <td className="px-5 py-3.5 text-gray-300 font-medium">
                          Platform Cost
                        </td>
                        <td className="px-5 py-3.5 text-right text-gray-400">
                          {currentTicketCostMonthly > 0
                            ? fmtMoney(currentTicketCostMonthly) + '/mo'
                            : '—'}
                        </td>
                        <td className="px-5 py-3.5 text-right text-gray-300 font-semibold">
                          ${(recommendedModel.price * recommendedComparison.quantity).toLocaleString()}/mo
                          {recommendedComparison.quantity > 1 && (
                            <div className="text-[10px] text-gray-500 font-normal">
                              ({recommendedComparison.quantity}x ${recommendedModel.price.toLocaleString()})
                            </div>
                          )}
                        </td>
                      </tr>
                      {/* TOTAL MONTHLY */}
                      <tr className="border-b border-white/5 bg-white/[0.04]">
                        <td className="px-5 py-4 text-white font-bold">
                          Total Monthly Cost
                        </td>
                        <td className="px-5 py-4 text-right text-red-300 font-bold text-base">
                          {fmtMoney(currentTotalMonthly)}
                        </td>
                        <td className="px-5 py-4 text-right text-emerald-400 font-black text-base">
                          {fmtMoney(recommendedComparison.parwaMonthlyCost)}
                        </td>
                      </tr>
                      {/* TOTAL ANNUAL */}
                      <tr className="border-b border-white/5 bg-white/[0.06]">
                        <td className="px-5 py-4 text-white font-bold">
                          Total Annual Cost
                        </td>
                        <td className="px-5 py-4 text-right text-red-300 font-bold text-base">
                          {fmtMoney(currentTotalAnnual)}
                        </td>
                        <td className="px-5 py-4 text-right text-emerald-400 font-black text-base">
                          {fmtMoney(recommendedComparison.parwaAnnualCost)}
                        </td>
                      </tr>
                      {/* SAVINGS ROW */}
                      <tr className="bg-emerald-500/5">
                        <td className="px-5 py-4 text-emerald-300 font-bold">
                          💰 Your Annual Savings
                        </td>
                        <td
                          className="px-5 py-4 text-right text-emerald-400 font-black text-xl"
                          colSpan={2}
                        >
                          {fmtMoney(recommendedComparison.annualSavings)}/year{' '}
                          <span className="text-sm font-bold text-emerald-300/70 ml-1">
                            ({recommendedComparison.savingsPercent.toFixed(0)}% less)
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* ════════════════════════════════════════
                  D. VISUAL BAR CHART — Cost Difference
                  ════════════════════════════════════════ */}
              <div
                className="rounded-2xl border border-white/10 p-6 sm:p-8"
                style={{ background: 'rgba(255,255,255,0.03)' }}
              >
                <h3 className="text-base sm:text-lg font-bold text-white mb-6 flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-orange-400" />
                  Visual Cost Breakdown (Annual)
                </h3>

                {/* Current Cost Bar */}
                <div className="mb-5">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-400 font-medium">
                      Your Current Cost
                    </span>
                    <span className="text-sm font-bold text-red-400">
                      {fmtMoney(currentTotalAnnual)}
                    </span>
                  </div>
                  <div className="w-full h-10 rounded-xl bg-red-500/10 border border-red-500/20 overflow-hidden relative">
                    <div
                      className="h-full rounded-xl bg-gradient-to-r from-red-500/40 to-red-500/20 transition-all duration-1000 ease-out"
                      style={{ width: '100%' }}
                    />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-xs font-bold text-red-300">
                        {fmtMoney(currentTotalAnnual)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* PARWA Cost Bars — all 3 */}
                <div className="space-y-3 mb-6">
                  {comparisons.map((comp) => (
                    <div key={comp.model.id}>
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-sm font-medium ${
                              comp.isRecommended ? 'text-orange-300' : 'text-gray-400'
                            }`}
                          >
                            {comp.model.name}
                          </span>
                          {comp.isRecommended && (
                            <span className="text-[10px] font-bold text-orange-400 uppercase tracking-wider bg-orange-500/15 px-1.5 py-0.5 rounded">
                              Best
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3">
                          <span
                            className={`text-xs font-semibold ${
                              comp.annualSavings > 0 ? 'text-emerald-400' : 'text-gray-500'
                            }`}
                          >
                            Save {fmtMoney(comp.annualSavings)}/yr
                          </span>
                          <span
                            className={`text-sm font-bold ${
                              comp.isRecommended ? 'text-emerald-400' : 'text-gray-300'
                            }`}
                          >
                            {fmtMoney(comp.parwaAnnualCost)}
                          </span>
                        </div>
                      </div>
                      <div className="w-full h-8 rounded-lg bg-white/5 border border-white/10 overflow-hidden relative">
                        <div
                          className={`h-full rounded-lg transition-all duration-1000 ease-out ${
                            comp.isRecommended
                              ? 'bg-gradient-to-r from-emerald-500/50 to-emerald-500/20'
                              : 'bg-gradient-to-r from-white/15 to-white/5'
                          }`}
                          style={{
                            width: `${Math.min(
                              100,
                              (comp.parwaAnnualCost / maxCostForChart) * 100
                            )}%`,
                          }}
                        />
                        <div className="absolute inset-0 flex items-center justify-center">
                          <span className="text-[11px] font-semibold text-gray-300">
                            {comp.savingsPercent.toFixed(0)}% cheaper
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Savings callout */}
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 flex items-center gap-3">
                  <PiggyBank className="w-6 h-6 text-emerald-400 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-bold text-emerald-300">
                      By choosing {recommendedModel.name}, you save{' '}
                      {fmtMoney(recommendedComparison.annualSavings)} every year
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      That&apos;s{' '}
                      {fmtMoney(
                        recommendedComparison.annualSavings / 12
                      )}{' '}
                      back in your pocket every month — while handling{' '}
                      {fmtNum(recommendedComparison.aiTicketsPerMonth)} more
                      tickets with AI.
                    </p>
                  </div>
                </div>
              </div>

              {/* ════════════════════════════════════════
                  E. ALL 3 MODELS — Detailed Comparison
                  ════════════════════════════════════════ */}
              <div
                className="rounded-2xl border border-white/10 p-6 sm:p-8"
                style={{ background: 'rgba(255,255,255,0.03)' }}
              >
                <h3 className="text-base sm:text-lg font-bold text-white mb-2 flex items-center gap-2">
                  <Zap className="w-5 h-5 text-orange-400" />
                  Compare All PARWA Models
                </h3>
                <p className="text-sm text-gray-400 mb-5">
                  See how each model performs with your data. The recommended
                  model is highlighted.
                </p>

                <div className="space-y-3">
                  {comparisons.map((comp) => (
                    <div
                      key={comp.model.id}
                      className={`rounded-xl border p-5 transition-all duration-300 ${
                        comp.isRecommended
                          ? 'border-orange-500/40 bg-orange-500/5 shadow-lg shadow-orange-500/5'
                          : 'border-white/5 bg-white/[0.02] hover:border-white/10'
                      }`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
                        <div className="flex items-center gap-3">
                          {comp.isRecommended && (
                            <span className="px-2.5 py-1 rounded-full bg-orange-500/20 text-orange-300 text-[10px] font-bold uppercase tracking-wider border border-orange-500/20">
                              ★ Recommended
                            </span>
                          )}
                          <div>
                            <span className="text-sm font-bold text-white">
                              {comp.model.name}
                            </span>
                            <span className="text-xs text-gray-500 ml-2">
                              &ldquo;{comp.model.tagline}&rdquo;
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className="text-lg font-black text-orange-400">
                            ${comp.model.price.toLocaleString()}
                            <span className="text-xs text-gray-500 font-normal">
                              /mo
                            </span>
                          </span>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="rounded-lg bg-white/5 px-3 py-2">
                          <div className="text-lg font-bold text-white">
                            {Math.round(comp.model.aiResolution * 100)}%
                          </div>
                          <div className="text-[10px] text-gray-500 uppercase tracking-wider">
                            AI Resolved
                          </div>
                        </div>
                        <div className="rounded-lg bg-white/5 px-3 py-2">
                          <div className="text-lg font-bold text-white">
                            {fmtNum(comp.aiTicketsPerMonth)}
                          </div>
                          <div className="text-[10px] text-gray-500 uppercase tracking-wider">
                            AI Tickets/Mo
                          </div>
                        </div>
                        <div className="rounded-lg bg-white/5 px-3 py-2">
                          <div className="text-lg font-bold text-emerald-400">
                            {fmtMoney(comp.annualSavings)}
                          </div>
                          <div className="text-[10px] text-gray-500 uppercase tracking-wider">
                            Annual Savings
                          </div>
                        </div>
                        <div className="rounded-lg bg-white/5 px-3 py-2">
                          <div className="text-lg font-bold text-blue-400">
                            {comp.savingsPercent.toFixed(0)}%
                          </div>
                          <div className="text-[10px] text-gray-500 uppercase tracking-wider">
                            Cost Reduction
                          </div>
                        </div>
                      </div>

                      {/* Channels */}
                      <div className="flex flex-wrap items-center gap-1.5 mt-3">
                        {comp.model.channels.map((ch) => (
                          <span
                            key={ch}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-white/5 text-[10px] text-gray-400 border border-white/5"
                          >
                            {getChannelIcon(ch)}
                            {ch}
                          </span>
                        ))}
                        <span className="text-[10px] text-gray-600 ml-1">
                          — {comp.model.ticketCapacity}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* ════════════════════════════════════════
                  F. CTAs
                  ════════════════════════════════════════ */}
              <div className="flex flex-col sm:flex-row gap-3 pt-2">
                <Link
                  href="/models"
                  className="flex-1 flex items-center justify-center gap-2 py-4 rounded-xl bg-gradient-to-r from-orange-600 to-orange-500 text-white text-sm font-bold shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40 transition-all duration-300 hover:-translate-y-0.5"
                >
                  Explore All AI Models
                  <ChevronRight className="w-4 h-4" />
                </Link>
                <button
                  onClick={() => {
                    if (typeof window !== 'undefined') {
                      window.localStorage.setItem(
                        'parwa_jarvis_context',
                        JSON.stringify({
                          source: 'roi',
                          industry: industry,
                          variant: recommendedModel.id,
                          roi_result: {
                            monthly_tickets: tickets,
                            team_size: agentCount,
                            current_monthly: currentTotalMonthly,
                            current_annual: currentTotalAnnual,
                            parwa_monthly: recommendedComparison.parwaMonthlyCost,
                            parwa_annual: recommendedComparison.parwaAnnualCost,
                            savings_annual: recommendedComparison.annualSavings,
                            savings_pct: recommendedComparison.savingsPercent,
                            suggested_model: recommendedModel.id,
                          },
                        })
                      );
                      try {
                        const visited = JSON.parse(
                          localStorage.getItem('parwa_pages_visited') || '[]'
                        ) as string[];
                        if (!visited.includes('roi_calculator')) {
                          visited.push('roi_calculator');
                          localStorage.setItem(
                            'parwa_pages_visited',
                            JSON.stringify(visited)
                          );
                        }
                      } catch {
                        /* ignore */
                      }
                      try {
                        const roiCtx = {
                          industry,
                          roi_result: {
                            monthly_savings: recommendedComparison.monthlySavings,
                            annual_savings: recommendedComparison.annualSavings,
                            parwa_monthly: recommendedComparison.parwaMonthlyCost,
                            current_monthly: recommendedComparison.currentMonthlyCost,
                            quantity: recommendedComparison.quantity
                          },
                          variant: recommendedModel.id,
                          quantity: recommendedComparison.quantity,
                          entry_source: 'roi'
                        };
                        // Gap #10 Fix: MERGE into existing context
                        try {
                          const existing = JSON.parse(localStorage.getItem('parwa_jarvis_context') || '{}');
                          localStorage.setItem('parwa_jarvis_context', JSON.stringify({ ...existing, ...roiCtx }));
                        } catch {
                          localStorage.setItem('parwa_jarvis_context', JSON.stringify(roiCtx));
                        }
                      } catch (e) { /* ignore */ }
                    }
                    window.location.href =
                      '/jarvis?entry_source=roi&industry=' +
                      encodeURIComponent(industry) +
                      '&variant=' +
                      encodeURIComponent(recommendedModel.id) +
                      '&qty=' + recommendedComparison.quantity;
                  }}
                  className="flex-1 flex items-center justify-center gap-2 py-4 rounded-xl border border-white/10 text-gray-300 text-sm font-bold hover:border-orange-500/30 hover:bg-white/5 transition-all duration-300"
                >
                  Try Jarvis Live
                  <Sparkles className="w-4 h-4" />
                </button>
              </div>

              <p className="text-center text-[11px] text-gray-600 px-4">
                * Estimates based on industry benchmarks and typical AI resolution rates. Actual results may vary depending on ticket complexity, implementation, and team utilization. PARWA pricing is current as of 2025.
              </p>
            </div>
          )}

          {/* ══════════════════════════════════════════════
              NAVIGATION BUTTONS
              ══════════════════════════════════════════════ */}
          {step < 3 && (
            <div className="flex items-center justify-between mt-8">
              {step > 1 ? (
                <button
                  onClick={handleBack}
                  className="flex items-center gap-2 px-5 py-3 rounded-xl border border-white/10 text-gray-400 text-sm font-medium hover:border-white/20 hover:text-gray-300 transition-all duration-300"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back
                </button>
              ) : (
                <Link
                  href="/"
                  className="flex items-center gap-2 px-5 py-3 text-gray-500 text-sm font-medium hover:text-gray-400 transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Home
                </Link>
              )}

              <button
                onClick={handleNext}
                disabled={!canGoNext}
                className={`flex items-center gap-2 px-8 py-3.5 rounded-xl text-sm font-bold transition-all duration-300 ${
                  canGoNext
                    ? 'bg-gradient-to-r from-orange-600 to-orange-500 text-white shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40 hover:-translate-y-0.5'
                    : 'bg-white/5 text-gray-600 cursor-not-allowed'
                }`}
              >
                {step === 2 ? 'See My Results' : 'Continue'}
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {step === 3 && (
            <div className="mt-6">
              <button
                onClick={() => setStep(1)}
                className="flex items-center gap-2 px-5 py-3 rounded-xl border border-white/10 text-gray-400 text-sm font-medium hover:border-white/20 hover:text-gray-300 transition-all duration-300 mx-auto"
              >
                <ArrowLeft className="w-4 h-4" />
                Start Over
              </button>
            </div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  );
}
