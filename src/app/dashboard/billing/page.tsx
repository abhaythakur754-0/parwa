'use client';

import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';

// ── Types ────────────────────────────────────────────────────────────

type TierKey = 'mini' | 'pro' | 'high';
type BillingCycle = 'monthly' | 'annual';
type InvoiceStatus = 'paid' | 'pending' | 'failed';

interface PlanTier {
  key: TierKey;
  name: string;
  monthlyPrice: number;
  description: string;
  agents: number;
  techniques: string;
  router: string;
  support: string;
  highlight?: string;
}

interface Invoice {
  id: string;
  date: string;
  description: string;
  amount: number;
  status: InvoiceStatus;
}

// ── Plan Data ────────────────────────────────────────────────────────

const PLANS: PlanTier[] = [
  {
    key: 'mini',
    name: 'Mini PARWA',
    monthlyPrice: 999,
    description: 'For small teams getting started with AI support',
    agents: 1,
    techniques: 'Tier 1 only',
    router: 'Light router',
    support: 'Basic support',
  },
  {
    key: 'pro',
    name: 'PARWA',
    monthlyPrice: 2499,
    description: 'For growing teams that need full AI capabilities',
    agents: 3,
    techniques: 'Tier 1 + Tier 2',
    router: 'Light + Medium router',
    support: 'Priority support',
    highlight: 'Most Popular',
  },
  {
    key: 'high',
    name: 'PARWA High',
    monthlyPrice: 3999,
    description: 'For enterprises that demand the best',
    agents: 5,
    techniques: 'All techniques',
    router: 'All router tiers',
    support: 'Dedicated support + Quality Coach',
  },
];

// ── Mock Data ────────────────────────────────────────────────────────

const MOCK_INVOICES: Invoice[] = [
  { id: 'INV-2026-001', date: '2026-02-28', description: 'PARWA Pro — March 2026', amount: 2499, status: 'paid' },
  { id: 'INV-2026-002', date: '2026-01-28', description: 'PARWA Pro — February 2026', amount: 2499, status: 'paid' },
  { id: 'INV-2025-012', date: '2025-12-28', description: 'PARWA Pro — January 2026', amount: 2499, status: 'paid' },
  { id: 'INV-2025-011', date: '2025-11-28', description: 'PARWA Pro — December 2025', amount: 2499, status: 'paid' },
  { id: 'INV-2025-010', date: '2025-10-28', description: 'PARWA Pro — November 2025', amount: 2499, status: 'pending' },
  { id: 'INV-2025-009', date: '2025-09-28', description: 'PARWA Pro — October 2025', amount: 2499, status: 'failed' },
];

// ── Icons ────────────────────────────────────────────────────────────

const CreditCardIcon = ({ className = 'w-6 h-6' }: { className?: string }) => (
  <svg className={cn('text-orange-400', className)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5A2.25 2.25 0 0 0 4.5 19.5Z" />
  </svg>
);

const ShieldIcon = () => (
  <svg className="w-5 h-5 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
  </svg>
);

const BoltIcon = () => (
  <svg className="w-5 h-5 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m3.75 13.5 10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75Z" />
  </svg>
);

const DownloadIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
  </svg>
);

const ArrowUpIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" />
  </svg>
);

const ArrowDownIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 4.5l15 15m0 0V8.25m0 11.25H8.25" />
  </svg>
);

const CheckIcon = () => (
  <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
  </svg>
);

const ClockIcon = () => (
  <svg className="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
  </svg>
);

const XCircleIcon = () => (
  <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
  </svg>
);

// ── Helpers ──────────────────────────────────────────────────────────

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(amount);
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// ── Sub-components ───────────────────────────────────────────────────

function UsageBar({ used, total, label, unit, color }: { used: number; total: number; label: string; unit: string; color: string }) {
  const pct = Math.min((used / total) * 100, 100);
  const isNearLimit = pct >= 80;
  const isOverLimit = pct >= 100;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-zinc-400">{label}</span>
        <span className={cn('text-xs font-medium', isOverLimit ? 'text-red-400' : isNearLimit ? 'text-amber-400' : 'text-zinc-300')}>
          {used.toLocaleString()} / {total.toLocaleString()} {unit}
        </span>
      </div>
      <div className="h-2 bg-white/5 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-700', color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      {isOverLimit && (
        <p className="text-[10px] text-red-400 flex items-center gap-1">
          <XCircleIcon /> Over limit — overage charges apply
        </p>
      )}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6 space-y-4">
      <Skeleton className="h-4 w-32 bg-white/5" />
      <Skeleton className="h-8 w-48 bg-white/5" />
      <div className="space-y-2">
        <Skeleton className="h-3 w-full bg-white/5" />
        <Skeleton className="h-3 w-3/4 bg-white/5" />
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: InvoiceStatus }) {
  const config = {
    paid: { label: 'Paid', icon: <CheckIcon />, classes: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
    pending: { label: 'Pending', icon: <ClockIcon />, classes: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
    failed: { label: 'Failed', icon: <XCircleIcon />, classes: 'bg-red-500/10 text-red-400 border-red-500/20' },
  }[status];

  return (
    <span className={cn('inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full border', config.classes)}>
      {config.icon}
      {config.label}
    </span>
  );
}

// ── Billing Page ─────────────────────────────────────────────────────

export default function BillingPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [currentTier, setCurrentTier] = useState<TierKey>('pro');
  const [billingCycle, setBillingCycle] = useState<BillingCycle>('monthly');
  const [showPaymentModal, setShowPaymentModal] = useState(false);

  // Simulate loading
  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  const currentPlan = PLANS.find(p => p.key === currentTier)!;
  const annualDiscount = 0.2;
  const annualPrice = (plan: PlanTier) => Math.round(plan.monthlyPrice * (1 - annualDiscount));
  const activePrice = billingCycle === 'annual' ? annualPrice(currentPlan) : currentPlan.monthlyPrice;

  // Usage data
  const tokensUsed = 145_000;
  const tokensTotal = 500_000;
  const agentHoursUsed = 187;
  const agentHoursTotal = 300;
  const agentsUsed = 2;
  const agentsMax = currentPlan.agents;
  const ticketsThisMonth = 4_287;
  const overageTokens = 0;
  const overageCost = overageTokens > 0 ? (overageTokens / 1_000) * 0.02 : 0;

  // Token cost breakdown
  const baseCost = activePrice;
  const overageTotal = overageCost;
  const totalThisMonth = baseCost + overageTotal;
  const totalSpentThisYear = MOCK_INVOICES.reduce((sum, inv) => sum + inv.amount, 0);

  // Next billing date (demo: 15 days from now)
  const nextBillingDate = new Date();
  nextBillingDate.setDate(nextBillingDate.getDate() + 15);

  const handleUpgrade = () => {
    const tiers: TierKey[] = ['mini', 'pro', 'high'];
    const idx = tiers.indexOf(currentTier);
    if (idx < tiers.length - 1) {
      setCurrentTier(tiers[idx + 1]);
    }
  };

  const handleDowngrade = () => {
    const tiers: TierKey[] = ['mini', 'pro', 'high'];
    const idx = tiers.indexOf(currentTier);
    if (idx > 0) {
      setCurrentTier(tiers[idx - 1]);
    }
  };

  // ── Loading State ───────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="pb-6 border-b border-white/[0.06]">
          <Skeleton className="h-6 w-24 bg-white/5" />
          <Skeleton className="h-4 w-72 bg-white/5 mt-2" />
        </div>
        <SkeletonCard />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
        <SkeletonCard />
      </div>
    );
  }

  // ── Rendered Page ──────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* ─── Header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between pb-6 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-bold text-white">Billing</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Manage your subscription, invoices, and payment methods
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs text-zinc-500">Active</span>
        </div>
      </div>

      {/* ─── Current Plan Card ──────────────────────────────────── */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
        {/* Gradient header band */}
        <div className={cn(
          'h-1.5',
          currentTier === 'mini' ? 'bg-gradient-to-r from-blue-500 to-blue-400' :
          currentTier === 'pro' ? 'bg-gradient-to-r from-purple-500 to-purple-400' :
          'bg-gradient-to-r from-orange-500 to-amber-400'
        )} />
        <div className="p-6">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
            {/* Left: plan info */}
            <div className="space-y-4 flex-1">
              <div className="flex items-center gap-3">
                <div className={cn(
                  'w-10 h-10 rounded-xl flex items-center justify-center',
                  currentTier === 'mini' ? 'bg-blue-500/10' :
                  currentTier === 'pro' ? 'bg-purple-500/10' :
                  'bg-orange-500/10'
                )}>
                  <ShieldIcon />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-semibold text-white">{currentPlan.name}</h2>
                    {currentTier === 'pro' && (
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
                        Current Plan
                      </span>
                    )}
                    {currentTier === 'high' && (
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/20">
                        Premium
                      </span>
                    )}
                    {currentTier === 'mini' && (
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                        Starter
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-2xl font-bold text-white">
                      {formatCurrency(billingCycle === 'annual' ? annualPrice(currentPlan) : currentPlan.monthlyPrice)}
                    </span>
                    <span className="text-sm text-zinc-500">/mo</span>
                    {billingCycle === 'annual' && (
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        Save 20%
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Billing cycle toggle */}
              <div className="flex items-center gap-3">
                <span className={cn('text-xs font-medium', billingCycle === 'monthly' ? 'text-white' : 'text-zinc-500')}>
                  Monthly
                </span>
                <button
                  onClick={() => setBillingCycle(prev => prev === 'monthly' ? 'annual' : 'monthly')}
                  className={cn(
                    'relative w-10 h-5 rounded-full transition-colors',
                    billingCycle === 'annual' ? 'bg-orange-500' : 'bg-white/10'
                  )}
                  aria-label="Toggle billing cycle"
                >
                  <span
                    className={cn(
                      'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform',
                      billingCycle === 'annual' ? 'translate-x-5' : 'translate-x-0.5'
                    )}
                  />
                </button>
                <span className={cn('text-xs font-medium', billingCycle === 'annual' ? 'text-white' : 'text-zinc-500')}>
                  Annual
                </span>
                {billingCycle === 'annual' && (
                  <span className="text-[10px] text-emerald-400 ml-1">
                    ({formatCurrency(currentPlan.monthlyPrice - annualPrice(currentPlan))}/mo savings)
                  </span>
                )}
              </div>

              {/* Next billing date */}
              <div className="flex items-center gap-2 text-xs text-zinc-500">
                <ClockIcon />
                <span>Next billing date: <span className="text-zinc-300">{formatDate(nextBillingDate.toISOString())}</span></span>
              </div>
            </div>

            {/* Right: usage stats */}
            <div className="flex-1 max-w-md space-y-4 bg-[#0A0A0A] rounded-lg p-4 border border-white/[0.04]">
              <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Usage This Period</h3>

              {/* AI Agents */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-zinc-400">AI Agents</span>
                  <span className={cn(
                    'text-xs font-medium',
                    agentsUsed >= agentsMax ? 'text-red-400' : 'text-zinc-300'
                  )}>
                    {agentsUsed} / {agentsMax}
                  </span>
                </div>
                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all duration-700',
                      agentsUsed >= agentsMax ? 'bg-red-500' : 'bg-gradient-to-r from-purple-500 to-purple-400'
                    )}
                    style={{ width: `${(agentsUsed / agentsMax) * 100}%` }}
                  />
                </div>
              </div>

              {/* Tickets */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-400">Tickets Processed</span>
                <span className="text-xs font-medium text-zinc-300">{ticketsThisMonth.toLocaleString()}</span>
              </div>

              {/* Token usage */}
              <UsageBar
                used={tokensUsed}
                total={tokensTotal}
                label="Token Usage"
                unit="tokens"
                color={tokensUsed / tokensTotal >= 0.8 ? 'bg-gradient-to-r from-amber-500 to-red-500' : 'bg-gradient-to-r from-emerald-500 to-emerald-400'}
              />
            </div>
          </div>

          {/* Upgrade / Downgrade buttons */}
          <div className="flex items-center gap-3 mt-6 pt-4 border-t border-white/[0.06]">
            {currentTier !== 'high' && (
              <button
                onClick={handleUpgrade}
                className="inline-flex items-center gap-1.5 text-xs font-medium px-4 py-2 rounded-lg bg-gradient-to-r from-orange-500 to-amber-400 text-white shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30 transition-all"
              >
                <ArrowUpIcon />
                Upgrade to {PLANS.find(p => p.key === currentTier) ? PLANS[PLANS.findIndex(p => p.key === currentTier) + 1]?.name : ''}
              </button>
            )}
            {currentTier !== 'mini' && (
              <button
                onClick={handleDowngrade}
                className="inline-flex items-center gap-1.5 text-xs font-medium px-4 py-2 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] border border-white/[0.06] transition-colors"
              >
                <ArrowDownIcon />
                Downgrade
              </button>
            )}
            <button className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors ml-auto">
              Cancel Subscription
            </button>
          </div>
        </div>
      </div>

      {/* ─── Plan Comparison Section ───────────────────────────── */}
      <div>
        <h2 className="text-sm font-semibold text-white mb-4">Plan Comparison</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {PLANS.map(plan => {
            const isCurrent = plan.key === currentTier;
            const price = billingCycle === 'annual' ? annualPrice(plan) : plan.monthlyPrice;

            return (
              <div
                key={plan.key}
                className={cn(
                  'rounded-xl border bg-[#1A1A1A] p-6 transition-all relative',
                  isCurrent
                    ? 'border-orange-500/40 ring-1 ring-orange-500/20'
                    : 'border-white/[0.06] hover:border-white/[0.12]'
                )}
              >
                {/* Popular badge */}
                {plan.highlight && (
                  <div className="absolute -top-2.5 left-1/2 -translate-x-1/2">
                    <span className="text-[10px] font-semibold px-3 py-0.5 rounded-full bg-gradient-to-r from-orange-500 to-amber-400 text-white shadow-lg shadow-orange-500/20">
                      {plan.highlight}
                    </span>
                  </div>
                )}

                {/* Current plan badge */}
                {isCurrent && (
                  <div className="absolute -top-2.5 right-4">
                    <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/20">
                      Current
                    </span>
                  </div>
                )}

                <div className="space-y-4">
                  {/* Plan name and price */}
                  <div>
                    <h3 className="text-base font-semibold text-white">{plan.name}</h3>
                    <p className="text-xs text-zinc-500 mt-0.5">{plan.description}</p>
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-white">{formatCurrency(price)}</span>
                    <span className="text-sm text-zinc-500">/mo</span>
                  </div>
                  {billingCycle === 'annual' && (
                    <p className="text-[10px] text-zinc-600 line-through">
                      {formatCurrency(plan.monthlyPrice)}/mo — save {formatCurrency(plan.monthlyPrice - price)}/mo
                    </p>
                  )}

                  {/* Features list */}
                  <div className="space-y-2.5 pt-2 border-t border-white/[0.06]">
                    <div className="flex items-center gap-2">
                      <BoltIcon />
                      <span className="text-xs text-zinc-300">{plan.agents} AI Agent{plan.agents > 1 ? 's' : ''}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <svg className="w-5 h-5 text-orange-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />
                      </svg>
                      <span className="text-xs text-zinc-300">{plan.techniques}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <svg className="w-5 h-5 text-orange-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                      </svg>
                      <span className="text-xs text-zinc-300">{plan.router}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <svg className="w-5 h-5 text-orange-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 0 1-.825-.242m9.345-8.334a2.126 2.126 0 0 0-.476-.095 48.64 48.64 0 0 0-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0 0 11.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155" />
                      </svg>
                      <span className="text-xs text-zinc-300">{plan.support}</span>
                    </div>
                  </div>

                  {/* Action button */}
                  {isCurrent ? (
                    <div className="pt-4 border-t border-white/[0.06]">
                      <button
                        disabled
                        className="w-full text-xs font-medium py-2.5 rounded-lg bg-white/[0.04] text-zinc-500 border border-white/[0.06] cursor-not-allowed"
                      >
                        Current Plan
                      </button>
                    </div>
                  ) : (
                    <div className="pt-4 border-t border-white/[0.06]">
                      <button
                        onClick={() => setCurrentTier(plan.key)}
                        className={cn(
                          'w-full text-xs font-medium py-2.5 rounded-lg transition-all',
                          PLANS.findIndex(p => p.key === plan.key) > PLANS.findIndex(p => p.key === currentTier)
                            ? 'bg-gradient-to-r from-orange-500 to-amber-400 text-white shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30'
                            : 'bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] border border-white/[0.06]'
                        )}
                      >
                        {PLANS.findIndex(p => p.key === plan.key) > PLANS.findIndex(p => p.key === currentTier) ? 'Upgrade' : 'Downgrade'}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ─── Payment Method & Invoice History (2-col) ──────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Payment Method Card */}
        <div className="lg:col-span-2 rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6 space-y-5">
          <h2 className="text-sm font-semibold text-white">Payment Method</h2>

          <div className="flex items-center gap-4 bg-[#0A0A0A] rounded-lg p-4 border border-white/[0.04]">
            <div className="w-12 h-8 rounded bg-gradient-to-br from-blue-600 to-blue-400 flex items-center justify-center">
              <span className="text-[8px] font-bold text-white tracking-widest">VISA</span>
            </div>
            <div className="flex-1">
              <p className="text-sm text-white font-medium">Visa ending in 4242</p>
              <p className="text-xs text-zinc-500">Expires 12/25</p>
            </div>
            <CreditCardIcon className="w-5 h-5" />
          </div>

          <button
            onClick={() => setShowPaymentModal(true)}
            className="w-full text-xs font-medium py-2.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] border border-white/[0.06] transition-colors"
          >
            Update Payment Method
          </button>

          <div className="space-y-2 pt-3 border-t border-white/[0.06]">
            <h3 className="text-xs text-zinc-500 uppercase tracking-wider font-medium">Billing Email</h3>
            <p className="text-sm text-zinc-300">billing@acmecorp.com</p>
            <button className="text-[10px] text-orange-400 hover:text-orange-300 transition-colors">
              Change email
            </button>
          </div>
        </div>

        {/* Invoice History */}
        <div className="lg:col-span-3 rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
          <div className="flex items-center justify-between p-6 pb-4">
            <h2 className="text-sm font-semibold text-white">Invoice History</h2>
            <div className="text-xs text-zinc-500">
              Total this year: <span className="text-white font-medium">{formatCurrency(totalSpentThisYear)}</span>
            </div>
          </div>

          {/* Invoice table */}
          <div className="overflow-x-auto max-h-80 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-[#1A1A1A] z-10">
                <tr className="border-b border-white/[0.06]">
                  <th className="text-left px-6 py-2.5 text-zinc-500 font-medium">Invoice</th>
                  <th className="text-left px-4 py-2.5 text-zinc-500 font-medium">Date</th>
                  <th className="text-left px-4 py-2.5 text-zinc-500 font-medium hidden sm:table-cell">Description</th>
                  <th className="text-right px-4 py-2.5 text-zinc-500 font-medium">Amount</th>
                  <th className="text-center px-4 py-2.5 text-zinc-500 font-medium">Status</th>
                  <th className="text-right px-6 py-2.5 text-zinc-500 font-medium w-10" />
                </tr>
              </thead>
              <tbody>
                {MOCK_INVOICES.map((invoice) => (
                  <tr key={invoice.id} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                    <td className="px-6 py-3 text-zinc-300 font-mono">{invoice.id}</td>
                    <td className="px-4 py-3 text-zinc-400">{formatDate(invoice.date)}</td>
                    <td className="px-4 py-3 text-zinc-400 hidden sm:table-cell">{invoice.description}</td>
                    <td className="px-4 py-3 text-zinc-300 text-right font-medium">{formatCurrency(invoice.amount)}</td>
                    <td className="px-4 py-3 text-center">
                      <StatusBadge status={invoice.status} />
                    </td>
                    <td className="px-6 py-3 text-right">
                      {invoice.status === 'paid' ? (
                        <button
                          className="p-1 rounded hover:bg-white/[0.06] text-zinc-500 hover:text-zinc-300 transition-colors"
                          title="Download invoice"
                        >
                          <DownloadIcon />
                        </button>
                      ) : (
                        <span className="inline-block w-4" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ─── Usage Metering Section ────────────────────────────── */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-sm font-semibold text-white">Usage Metering</h2>
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Current Period</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Left: Usage bars */}
          <div className="space-y-5">
            <UsageBar
              used={tokensUsed}
              total={tokensTotal}
              label="Token Usage"
              unit="tokens"
              color={tokensUsed / tokensTotal >= 0.8 ? 'bg-gradient-to-r from-amber-500 to-red-500' : 'bg-gradient-to-r from-emerald-500 to-emerald-400'}
            />
            <UsageBar
              used={agentHoursUsed}
              total={agentHoursTotal}
              label="AI Agent Hours"
              unit="hrs"
              color="bg-gradient-to-r from-purple-500 to-purple-400"
            />
            <UsageBar
              used={agentsUsed}
              total={agentsMax}
              label="Active AI Agents"
              unit="agents"
              color={agentsUsed >= agentsMax ? 'bg-red-500' : 'bg-gradient-to-r from-blue-500 to-blue-400'}
            />

            {overageTokens > 0 && (
              <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
                <p className="text-xs font-medium text-red-400">Overage Alert</p>
                <p className="text-[10px] text-zinc-500 mt-0.5">
                  You have exceeded your token allowance by {overageTokens.toLocaleString()} tokens.
                  Overage is billed at $0.02 per 1K tokens.
                </p>
              </div>
            )}
          </div>

          {/* Right: Cost breakdown */}
          <div className="bg-[#0A0A0A] rounded-lg p-4 border border-white/[0.04] space-y-3">
            <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Cost Breakdown</h3>

            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-400">Base Subscription</span>
                <span className="text-xs text-zinc-300 font-medium">{formatCurrency(baseCost)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-400">Token Overage</span>
                <span className="text-xs text-zinc-300 font-medium">{overageTotal > 0 ? formatCurrency(overageTotal) : '$0'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-400">Add-ons</span>
                <span className="text-xs text-zinc-300 font-medium">$0</span>
              </div>

              <div className="border-t border-white/[0.06] pt-2 mt-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-white font-semibold">Estimated Total</span>
                  <span className="text-sm text-white font-bold">{formatCurrency(totalThisMonth)}</span>
                </div>
                {billingCycle === 'annual' && (
                  <p className="text-[10px] text-zinc-500 mt-1">
                    Billed annually at {formatCurrency(totalThisMonth * 12)}/yr
                  </p>
                )}
              </div>
            </div>

            <div className="pt-3 border-t border-white/[0.06] space-y-1.5">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-400" />
                <span className="text-[10px] text-zinc-500">Tokens: {Math.round((tokensUsed / tokensTotal) * 100)}% used</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-purple-400" />
                <span className="text-[10px] text-zinc-500">Agent Hours: {Math.round((agentHoursUsed / agentHoursTotal) * 100)}% used</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-blue-400" />
                <span className="text-[10px] text-zinc-500">Agents: {agentsUsed}/{agentsMax} deployed</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ─── Payment Modal (simple) ────────────────────────────── */}
      {showPaymentModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#1A1A1A] rounded-xl border border-white/[0.06] w-full max-w-md p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-sm font-semibold text-white">Update Payment Method</h3>
              <button
                onClick={() => setShowPaymentModal(false)}
                className="text-zinc-500 hover:text-white transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-zinc-500 mb-1.5 block">Card Number</label>
                <div className="bg-[#0A0A0A] border border-white/[0.06] rounded-lg px-3 py-2.5 text-sm text-zinc-400">
                  4242 4242 4242 4242
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-zinc-500 mb-1.5 block">Expiry</label>
                  <div className="bg-[#0A0A0A] border border-white/[0.06] rounded-lg px-3 py-2.5 text-sm text-zinc-400">
                    12/25
                  </div>
                </div>
                <div>
                  <label className="text-xs text-zinc-500 mb-1.5 block">CVC</label>
                  <div className="bg-[#0A0A0A] border border-white/[0.06] rounded-lg px-3 py-2.5 text-sm text-zinc-400">
                    &bull;&bull;&bull;
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={() => setShowPaymentModal(false)}
                  className="flex-1 text-xs font-medium py-2.5 rounded-lg bg-gradient-to-r from-orange-500 to-amber-400 text-white shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30 transition-all"
                >
                  Save Card
                </button>
                <button
                  onClick={() => setShowPaymentModal(false)}
                  className="flex-1 text-xs font-medium py-2.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] border border-white/[0.06] transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
