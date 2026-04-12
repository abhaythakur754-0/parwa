'use client';

import React, { useState, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft, ArrowRight, Building2, Users, TicketCheck,
  TrendingUp, Zap, DollarSign, Clock, Target, Sparkles,
  ChevronRight, Check, CircleDot
} from 'lucide-react';

// ──────────────────────────────────────────────────────────────────
// STEP DATA
// ──────────────────────────────────────────────────────────────────

const INDUSTRIES = [
  { id: 'ecommerce', label: 'E-Commerce', icon: '🛒' },
  { id: 'saas', label: 'SaaS / Tech', icon: '💻' },
  { id: 'logistics', label: 'Logistics', icon: '🚚' },
  { id: 'healthcare', label: 'Healthcare', icon: '🏥' },
  { id: 'finance', label: 'Finance', icon: '🏦' },
  { id: 'realestate', label: 'Real Estate', icon: '🏠' },
  { id: 'education', label: 'Education', icon: '🎓' },
  { id: 'others', label: 'Other', icon: '🏢' },
];

const TEAM_SIZES = [
  { label: '1–5 agents', value: 3 },
  { label: '6–15 agents', value: 10 },
  { label: '16–30 agents', value: 23 },
  { label: '31–50 agents', value: 40 },
  { label: '50+ agents', value: 75 },
];

// Industry benchmarks for realistic calculations
const BENCHMARKS: Record<string, { avgTickets: number; avgCostPerTicket: number; avgSalary: number }> = {
  ecommerce: { avgTickets: 5000, avgCostPerTicket: 6.5, avgSalary: 36000 },
  saas: { avgTickets: 3500, avgCostPerTicket: 8.2, avgSalary: 40000 },
  logistics: { avgTickets: 6000, avgCostPerTicket: 5.8, avgSalary: 34000 },
  healthcare: { avgTickets: 4000, avgCostPerTicket: 7.5, avgSalary: 42000 },
  finance: { avgTickets: 3000, avgCostPerTicket: 9.0, avgSalary: 45000 },
  realestate: { avgTickets: 2500, avgCostPerTicket: 7.0, avgSalary: 38000 },
  education: { avgTickets: 2000, avgCostPerTicket: 6.0, avgSalary: 35000 },
  others: { avgTickets: 3500, avgCostPerTicket: 7.0, avgSalary: 37000 },
};

// PARWA models data (matches /models page)
const PARWA_MODELS = {
  'mini-parwa': {
    name: 'Mini PARWA',
    tagline: 'The Freshy',
    tier: 'Entry Level',
    price: 499,
    aiResolution: 0.60,
    concurrentCalls: 2,
    description: 'Perfect for businesses just getting started with AI support. Handles FAQs, ticket intake, and basic queries.',
    bestFor: 'Small teams, FAQ-heavy support, getting started with AI',
  },
  parwa: {
    name: 'PARWA',
    tagline: 'The Junior',
    tier: 'Most Popular',
    price: 999,
    aiResolution: 0.78,
    concurrentCalls: 3,
    description: 'Resolves 70-80% of tickets autonomously. Recommends actions, verifies complex processes, and supports 50+ languages.',
    bestFor: 'Growing businesses, multi-channel support, high ticket volumes',
  },
  'parwa-high': {
    name: 'PARWA High',
    tagline: 'The Senior',
    tier: 'Enterprise',
    price: 1499,
    aiResolution: 0.88,
    concurrentCalls: 5,
    description: 'Handles the most complex cases. Predicts churn, provides strategic insights, and manages 5 concurrent conversations.',
    bestFor: 'Enterprise teams, complex cases, strategic support operations',
  },
};

// ──────────────────────────────────────────────────────────────────
// HELPERS
// ──────────────────────────────────────────────────────────────────

function fmt(n: number): string {
  if (n >= 1000000) return `$${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

function fmtNum(n: number): string {
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

// ──────────────────────────────────────────────────────────────────
// MAIN PAGE
// ──────────────────────────────────────────────────────────────────

export default function ROICalculatorPage() {
  const [step, setStep] = useState(1);
  const [companyName, setCompanyName] = useState('');
  const [industry, setIndustry] = useState('');
  const [monthlyTickets, setMonthlyTickets] = useState('');
  const [teamSizeLabel, setTeamSizeLabel] = useState('');
  const [costPerTicket, setCostPerTicket] = useState('');

  // ── Derived values ──
  const tickets = Math.max(0, Number(monthlyTickets) || 0);
  const agentCount = TEAM_SIZES.find((t) => t.label === teamSizeLabel)?.value || 0;
  const cpt = Number(costPerTicket) || BENCHMARKS[industry]?.avgCostPerTicket || 7;
  const avgSalary = BENCHMARKS[industry]?.avgSalary || 37000;

  // Current costs
  const currentLaborMonthly = agentCount > 0 ? (avgSalary / 12) * agentCount : 0;
  const currentTicketCostMonthly = tickets * cpt;
  const currentTotalMonthly = currentLaborMonthly + currentTicketCostMonthly;
  const currentTotalAnnual = currentTotalMonthly * 12;

  // ── Suggested model based on inputs ──
  const suggestedModel = useMemo(() => {
    if (tickets === 0 && agentCount === 0) return 'parwa';
    if (tickets <= 2000 && agentCount <= 5) return 'mini-parwa';
    if (tickets <= 5000 && agentCount <= 15) return 'parwa';
    return 'parwa-high';
  }, [tickets, agentCount]);

  // ── Calculate comparison for all models ──
  const comparisons = useMemo(() => {
    return Object.entries(PARWA_MODELS).map(([key, model]) => {
      const aiTickets = Math.round(tickets * model.aiResolution);
      const humanTickets = tickets - aiTickets;
      const parwaMonthly = model.price + (humanTickets * cpt * 0.25);
      const parwaAnnual = parwaMonthly * 12;
      const savings = currentTotalAnnual - parwaAnnual;
      const savingsPct = currentTotalAnnual > 0 ? (savings / currentTotalAnnual) * 100 : 0;
      const hoursSaved = aiTickets * 0.25;
      const paybackMonths = savings > 0 ? (parwaMonthly / (savings / 12)) : 0;
      return { key, ...model, aiTickets, humanTickets, parwaMonthly, parwaAnnual, savings: Math.max(0, savings), savingsPct: Math.max(0, savingsPct), hoursSaved, paybackMonths: Math.max(1, paybackMonths) };
    });
  }, [tickets, cpt, currentTotalAnnual]);

  // ── Step validation ──
  const canGoNext = step === 1
    ? companyName.trim().length > 0 && industry.length > 0
    : step === 2
      ? tickets > 0 && teamSizeLabel.length > 0
      : true;

  const handleNext = () => { if (canGoNext && step < 3) setStep(step + 1); };
  const handleBack = () => { if (step > 1) setStep(step - 1); };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'linear-gradient(180deg, #0D0D0D 0%, #1A1A1A 50%, #0D0D0D 100%)' }}>

      {/* ── Top Bar ── */}
      <nav className="sticky top-0 z-50 border-b border-white/5" style={{ background: 'rgba(13,13,13,0.9)', backdropFilter: 'blur(20px)' }}>
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <Link href="/" className="flex items-center gap-2 group">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center">
                <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
                </svg>
              </div>
              <span className="text-sm font-bold text-white group-hover:text-orange-300 transition-colors">PARWA</span>
            </Link>
            <span className="text-xs text-gray-500 font-medium">ROI Calculator</span>
          </div>
        </div>
      </nav>

      <main className="flex-grow flex items-start justify-center px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        <div className="w-full max-w-2xl">

          {/* ── Step Indicator ── */}
          <div className="flex items-center justify-center gap-3 mb-10">
            {[
              { n: 1, label: 'Your Business' },
              { n: 2, label: 'Support Details' },
              { n: 3, label: 'Your Results' },
            ].map((s, i) => (
              <React.Fragment key={s.n}>
                <div className="flex items-center gap-2">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 ${
                    step >= s.n ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30' : 'bg-white/5 text-gray-500 border border-white/10'
                  }`}>
                    {step > s.n ? <Check className="w-3.5 h-3.5" /> : s.n}
                  </div>
                  <span className={`text-xs font-medium hidden sm:block transition-colors duration-300 ${step >= s.n ? 'text-orange-300' : 'text-gray-600'}`}>
                    {s.label}
                  </span>
                </div>
                {i < 2 && (
                  <div className={`w-8 sm:w-16 h-px transition-colors duration-300 ${step > s.n ? 'bg-orange-500/50' : 'bg-white/10'}`} />
                )}
              </React.Fragment>
            ))}
          </div>

          {/* ══════════════════════════════════════════════
              STEP 1: Company Details
              ══════════════════════════════════════════════ */}
          {step === 1 && (
            <div className="animate-fadeIn">
              <div className="text-center mb-8">
                <h1 className="text-2xl sm:text-3xl font-bold text-white mb-2">
                  Tell us about your business
                </h1>
                <p className="text-sm text-gray-400">
                  We&apos;ll use this to find the perfect PARWA model for you
                </p>
              </div>

              <div className="space-y-5">
                {/* Company Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <Building2 className="w-3.5 h-3.5 inline mr-1.5 text-orange-400/70" />
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
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Industry
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {INDUSTRIES.map((ind) => (
                      <button
                        key={ind.id}
                        onClick={() => setIndustry(ind.id)}
                        className={`flex items-center gap-2 px-3 py-3 rounded-xl text-sm font-medium transition-all duration-300 border ${
                          industry === ind.id
                            ? 'border-orange-500/50 bg-orange-500/10 text-orange-300 shadow-sm shadow-orange-500/10'
                            : 'border-white/10 bg-white/5 text-gray-400 hover:border-white/20 hover:bg-white/[0.07]'
                        }`}
                      >
                        <span className="text-base">{ind.icon}</span>
                        {ind.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ══════════════════════════════════════════════
              STEP 2: Support Details
              ══════════════════════════════════════════════ */}
          {step === 2 && (
            <div className="animate-fadeIn">
              <div className="text-center mb-8">
                <h1 className="text-2xl sm:text-3xl font-bold text-white mb-2">
                  Your current support setup
                </h1>
                <p className="text-sm text-gray-400">
                  Help us understand your support volume and team size
                </p>
              </div>

              <div className="space-y-5">
                {/* Monthly Tickets */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <TicketCheck className="w-3.5 h-3.5 inline mr-1.5 text-orange-400/70" />
                    Monthly Support Tickets
                  </label>
                  <input
                    type="number"
                    value={monthlyTickets}
                    onChange={(e) => setMonthlyTickets(e.target.value)}
                    placeholder={BENCHMARKS[industry] ? `${BENCHMARKS[industry].avgTickets} (avg for your industry)` : 'e.g. 5000'}
                    className="w-full px-4 py-3.5 rounded-xl border border-white/10 bg-white/5 text-white text-sm placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/50 transition-all"
                  />
                  <p className="text-xs text-gray-600 mt-1.5">
                    {BENCHMARKS[industry] && `Industry average: ~${fmtNum(BENCHMARKS[industry].avgTickets)} tickets/month`}
                  </p>
                </div>

                {/* Team Size */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <Users className="w-3.5 h-3.5 inline mr-1.5 text-orange-400/70" />
                    Support Team Size
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {TEAM_SIZES.map((ts) => (
                      <button
                        key={ts.label}
                        onClick={() => setTeamSizeLabel(ts.label)}
                        className={`px-4 py-3 rounded-xl text-sm font-medium transition-all duration-300 border text-center ${
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

                {/* Cost Per Ticket (optional) */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <DollarSign className="w-3.5 h-3.5 inline mr-1.5 text-orange-400/70" />
                    Average Cost per Ticket <span className="text-gray-600 font-normal">(optional)</span>
                  </label>
                  <input
                    type="number"
                    step="0.50"
                    value={costPerTicket}
                    onChange={(e) => setCostPerTicket(e.target.value)}
                    placeholder={BENCHMARKS[industry] ? `$${BENCHMARKS[industry].avgCostPerTicket} (industry avg)` : 'e.g. 6.50'}
                    className="w-full px-4 py-3.5 rounded-xl border border-white/10 bg-white/5 text-white text-sm placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/50 transition-all"
                  />
                  <p className="text-xs text-gray-600 mt-1.5">
                    {BENCHMARKS[industry] && `Industry average: ~$${BENCHMARKS[industry].avgCostPerTicket}/ticket`}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* ══════════════════════════════════════════════
              STEP 3: Results — Model Suggestion + Comparison
              ══════════════════════════════════════════════ */}
          {step === 3 && (
            <div className="animate-fadeIn space-y-6">

              {/* Recommended Model */}
              <div className="rounded-2xl border border-orange-500/30 p-5 sm:p-6" style={{ background: 'linear-gradient(135deg, rgba(255,127,17,0.08) 0%, rgba(13,13,13,0.5) 100%)' }}>
                <div className="flex items-center gap-2 mb-4">
                  <Sparkles className="w-4 h-4 text-orange-400" />
                  <span className="text-xs font-bold text-orange-400 uppercase tracking-wider">Recommended for {companyName}</span>
                </div>
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div>
                    <h2 className="text-xl sm:text-2xl font-bold text-white mb-1">
                      {PARWA_MODELS[suggestedModel as keyof typeof PARWA_MODELS].name}
                    </h2>
                    <p className="text-sm text-orange-300/70">{PARWA_MODELS[suggestedModel as keyof typeof PARWA_MODELS].tagline}</p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="text-2xl font-black text-orange-400">${PARWA_MODELS[suggestedModel as keyof typeof PARWA_MODELS].price}</div>
                    <div className="text-xs text-gray-500">/month</div>
                  </div>
                </div>
                <p className="text-sm text-gray-400 leading-relaxed mb-3">
                  {PARWA_MODELS[suggestedModel as keyof typeof PARWA_MODELS].description}
                </p>
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-orange-500/10 border border-orange-500/20">
                  <CircleDot className="w-3.5 h-3.5 text-orange-400 flex-shrink-0" />
                  <span className="text-xs text-orange-200/80">
                    <strong>Why:</strong> Based on your {fmtNum(tickets)} monthly tickets and {teamSizeLabel}, this model resolves {Math.round(PARWA_MODELS[suggestedModel as keyof typeof PARWA_MODELS].aiResolution * 100)}% of queries autonomously — the best fit for your scale.
                  </span>
                </div>
              </div>

              {/* ── Cost Comparison Table ── */}
              <div className="rounded-2xl border border-white/10 overflow-hidden" style={{ background: 'rgba(255,255,255,0.03)' }}>
                <div className="px-5 py-4 border-b border-white/10">
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-orange-400" />
                    Cost Comparison: You vs PARWA
                  </h3>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/5">
                        <th className="text-left px-5 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Metric</th>
                        <th className="text-right px-5 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">Your Current</th>
                        <th className="text-right px-5 py-3 text-orange-400 font-medium text-xs uppercase tracking-wider">With PARWA</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { label: 'Monthly Tickets', current: fmtNum(tickets), parwa: `${fmtNum(comparisons[Object.keys(PARWA_MODELS).indexOf(suggestedModel)].humanTickets)} + ${fmtNum(comparisons[Object.keys(PARWA_MODELS).indexOf(suggestedModel)].aiTickets)} AI` },
                        { label: 'Agent Labor Cost', current: fmt(currentLaborMonthly) + '/mo', parwa: fmt(comparisons[Object.keys(PARWA_MODELS).indexOf(suggestedModel)].humanTickets * cpt * 0.25) + '/mo' },
                        { label: 'Platform Cost', current: '—', parwa: `$${PARWA_MODELS[suggestedModel as keyof typeof PARWA_MODELS].price}/mo` },
                        { label: 'Total Monthly', current: fmt(currentTotalMonthly), parwa: fmt(comparisons[Object.keys(PARWA_MODELS).indexOf(suggestedModel)].parwaMonthly), highlight: true },
                        { label: 'Total Annual', current: fmt(currentTotalAnnual), parwa: fmt(comparisons[Object.keys(PARWA_MODELS).indexOf(suggestedModel)].parwaAnnual), highlight: true },
                      ].map((row, i) => (
                        <tr key={i} className={`border-b border-white/5 ${row.highlight ? 'bg-white/[0.03]' : ''}`}>
                          <td className="px-5 py-3 text-gray-300 font-medium">{row.label}</td>
                          <td className="px-5 py-3 text-right text-gray-400">{row.current}</td>
                          <td className={`px-5 py-3 text-right font-semibold ${row.highlight ? 'text-orange-400' : 'text-gray-300'}`}>{row.parwa}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Savings banner */}
                {(() => {
                  const rec = comparisons[Object.keys(PARWA_MODELS).indexOf(suggestedModel)];
                  return (
                    <div className="px-5 py-4 border-t border-orange-500/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3" style={{ background: 'rgba(255,127,17,0.06)' }}>
                      <div>
                        <div className="text-xs text-orange-300/70 font-medium mb-0.5">Your Estimated Annual Savings</div>
                        <div className="text-2xl sm:text-3xl font-black text-orange-400">{fmt(rec.savings)}</div>
                      </div>
                      <div className="flex items-center gap-4 text-xs">
                        <div className="text-center">
                          <div className="text-lg font-bold text-white">{rec.savingsPct.toFixed(0)}%</div>
                          <div className="text-gray-500">cost reduction</div>
                        </div>
                        <div className="w-px h-8 bg-white/10" />
                        <div className="text-center">
                          <div className="text-lg font-bold text-white">{fmtNum(rec.hoursSaved)}h</div>
                          <div className="text-gray-500">saved/month</div>
                        </div>
                        <div className="w-px h-8 bg-white/10" />
                        <div className="text-center">
                          <div className="text-lg font-bold text-white">{rec.paybackMonths.toFixed(1)}</div>
                          <div className="text-gray-500">mo payback</div>
                        </div>
                      </div>
                    </div>
                  );
                })()}
              </div>

              {/* ── All Models Comparison ── */}
              <div className="rounded-2xl border border-white/10 p-5 sm:p-6" style={{ background: 'rgba(255,255,255,0.03)' }}>
                <h3 className="text-base font-bold text-white mb-4 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-orange-400" />
                  Compare All PARWA Models
                </h3>
                <div className="space-y-3">
                  {comparisons.map((c) => (
                    <div
                      key={c.key}
                      className={`rounded-xl border p-4 transition-all ${
                        c.key === suggestedModel
                          ? 'border-orange-500/40 bg-orange-500/5'
                          : 'border-white/5 bg-white/[0.02] hover:border-white/10'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {c.key === suggestedModel && (
                            <span className="px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-300 text-[10px] font-bold uppercase tracking-wider">Recommended</span>
                          )}
                          <span className="text-sm font-bold text-white">{c.name}</span>
                          <span className="text-xs text-gray-500">{c.tagline}</span>
                        </div>
                        <span className="text-sm font-bold text-orange-400">${c.price}/mo</span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-gray-400">
                        <span><strong className="text-gray-300">{c.aiResolution * 100}%</strong> AI resolved</span>
                        <span><strong className="text-gray-300">{c.concurrentCalls}</strong> concurrent calls</span>
                        <span><strong className="text-emerald-400">{fmt(c.savings)}/yr</strong> savings</span>
                        <span className="text-gray-600">{c.bestFor}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* CTA */}
              <div className="flex flex-col sm:flex-row gap-3">
                <Link
                  href="/models"
                  className="flex-1 flex items-center justify-center gap-2 py-4 rounded-xl bg-gradient-to-r from-orange-600 to-orange-500 text-white text-sm font-bold shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40 transition-all duration-300"
                >
                  Explore Our AI Models
                  <ChevronRight className="w-4 h-4" />
                </Link>
                <button
                  onClick={() => {
                    // Pass full ROI context to Jarvis via localStorage bridge
                    if (typeof window !== 'undefined') {
                      const rec = comparisons[Object.keys(PARWA_MODELS).indexOf(suggestedModel)];
                      window.localStorage.setItem('parwa_jarvis_context', JSON.stringify({
                        source: 'roi',
                        industry: industry,
                        variant: suggestedModel,
                        roi_result: {
                          monthly_tickets: tickets,
                          team_size: agentCount,
                          current_monthly: currentTotalMonthly,
                          current_annual: currentTotalAnnual,
                          parwa_monthly: rec?.parwaMonthly,
                          parwa_annual: rec?.parwaAnnual,
                          savings_annual: rec?.savings,
                          savings_pct: rec?.savingsPct,
                          suggested_model: suggestedModel,
                        },
                      }));
                      // Also track page visit
                      try {
                        const visited = JSON.parse(localStorage.getItem('parwa_pages_visited') || '[]') as string[];
                        if (!visited.includes('roi_calculator')) { visited.push('roi_calculator'); localStorage.setItem('parwa_pages_visited', JSON.stringify(visited)); }
                      } catch { /* ignore */ }
                    }
                    window.location.href = '/jarvis?entry_source=roi&industry=' + encodeURIComponent(industry) + '&variant=' + encodeURIComponent(suggestedModel);
                  }}
                  className="flex-1 flex items-center justify-center gap-2 py-4 rounded-xl border border-white/10 text-gray-300 text-sm font-bold hover:border-orange-500/30 hover:bg-white/5 transition-all duration-300"
                >
                  Try Jarvis Live
                  <Sparkles className="w-4 h-4" />
                </button>
              </div>

              <p className="text-center text-[11px] text-gray-600 px-4">
                * Estimates based on industry benchmarks. Actual results may vary depending on ticket complexity and implementation.
              </p>
            </div>
          )}

          {/* ── Navigation Buttons ── */}
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
                <Link href="/" className="flex items-center gap-2 px-5 py-3 text-gray-500 text-sm font-medium hover:text-gray-400 transition-colors">
                  <ArrowLeft className="w-4 h-4" />
                  Home
                </Link>
              )}

              <button
                onClick={handleNext}
                disabled={!canGoNext}
                className={`flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-bold transition-all duration-300 ${
                  canGoNext
                    ? 'bg-gradient-to-r from-orange-600 to-orange-500 text-white shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40'
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
                Start Over
              </button>
            </div>
          )}
        </div>
      </main>

      {/* ── Minimal Footer ── */}
      <footer className="border-t border-white/5 py-6">
        <p className="text-center text-xs text-gray-600">&copy; 2026 PARWA. All rights reserved.</p>
      </footer>
    </div>
  );
}
