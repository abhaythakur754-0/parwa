'use client';

import React, { useState, useMemo } from 'react';
import { useAppStore } from '@/lib/store';
import { NavigationBar } from '@/components/landing';
import { Footer } from '@/components/landing';
import {
  Building2, TicketCheck, TrendingUp, Zap, DollarSign,
  Clock, Target, Sparkles, Check, BarChart3, PiggyBank, Brain,
  Headphones, ThumbsUp, ArrowRight, Shield, Award,
} from 'lucide-react';
import {
  VARIANT_PRICES,
  VARIANT_LIMITS,
  VARIANT_DISPLAY_NAMES,
  VARIANT_TAGLINES,
  OVERAGE_PRICE_PER_TICKET,
  type VariantTier,
} from '@/lib/pricing-config';

// ── Model data from pricing-config.ts (SINGLE SOURCE OF TRUTH) ──
// $1 = 1 ticket. All tiers have the SAME AI capabilities (88% resolution).

interface ParwaModel {
  tier: VariantTier;
  name: string;
  tagline: string;
  price: number;
  ticketLimit: number;
  aiResolution: number;
  aiAgents: number;
  channels: string[];
  description: string;
  bestFor: string;
  tierLabel: string;
  tierColor: string;
  tierBorder: string;
  tierBg: string;
}

const AI_RESOLUTION_PARWA = 0.80;  // 80% — limited by $500 refund cap
const AI_RESOLUTION_HIGH = 0.92;   // 92% — unlimited financial actions
const HUMAN_HANDOFF_FACTOR = 0.25; // Human handles 25% effort on AI-unresolved tickets

const PARWA_MODELS: ParwaModel[] = [
  {
    tier: 'parwa',
    name: VARIANT_DISPLAY_NAMES.parwa,
    tagline: VARIANT_TAGLINES.parwa,
    price: VARIANT_PRICES.parwa,
    ticketLimit: VARIANT_LIMITS.parwa.monthlyTickets,
    aiResolution: AI_RESOLUTION_PARWA,
    channels: ['Email', 'Chat', 'SMS', 'Voice'],
    description: 'Your smartest junior agent. Resolves 80% of tickets autonomously — refunds limited to $500.',
    bestFor: 'Growing businesses needing multi-channel support',
    tierLabel: 'Most Popular',
    tierColor: 'text-orange-400',
    tierBorder: 'border-orange-500/30',
    tierBg: 'bg-orange-500/5',
  },
  {
    tier: 'high',
    name: VARIANT_DISPLAY_NAMES.high,
    tagline: VARIANT_TAGLINES.high,
    price: VARIANT_PRICES.high,
    ticketLimit: VARIANT_LIMITS.high.monthlyTickets,
    aiResolution: AI_RESOLUTION_HIGH,
    aiAgents: VARIANT_LIMITS.high.aiAgents,
    channels: ['Email', 'Chat', 'SMS', 'Voice', 'Social', 'Video'],
    description: 'Your most experienced senior agent. Handles complex cases with unlimited financial actions.',
    bestFor: 'Enterprise teams with complex cases',
    tierLabel: 'Enterprise',
    tierColor: 'text-purple-400',
    tierBorder: 'border-purple-500/30',
    tierBg: 'bg-purple-500/5',
  },
];

const INDUSTRIES = [
  { id: 'ecommerce', label: 'E-Commerce', avgCostPerTicket: 6.5 },
  { id: 'saas', label: 'SaaS / Tech', avgCostPerTicket: 8.2 },
  { id: 'logistics', label: 'Logistics', avgCostPerTicket: 5.8 },
  { id: 'healthcare', label: 'Healthcare', avgCostPerTicket: 7.5 },
  { id: 'finance', label: 'Finance', avgCostPerTicket: 9.0 },
  { id: 'realestate', label: 'Real Estate', avgCostPerTicket: 7.0 },
  { id: 'education', label: 'Education', avgCostPerTicket: 6.0 },
  { id: 'others', label: 'Other', avgCostPerTicket: 7.0 },
];

// Real salary benchmarks (US Bureau of Labor Statistics 2024-2025)
// Customer Service Representative median: ~$39,680/yr = ~$3,300/mo
// With benefits/overhead: ~$4,500/mo total cost per employee
const DEFAULT_EMPLOYEE_COST = 4500; // $/month per support employee
const TICKETS_PER_EMPLOYEE = 400; // tickets/month a human can handle

function fmtMoney(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
}
function fmtNum(n: number): string { return n.toLocaleString('en-US', { maximumFractionDigits: 0 }); }

function getRecommendedModel(tickets: number) {
  if (tickets <= VARIANT_LIMITS.parwa.monthlyTickets) {
    return { model: PARWA_MODELS[0], reasons: [`Your ${fmtNum(tickets)} tickets/month fits within PARWA's ${fmtNum(VARIANT_LIMITS.parwa.monthlyTickets)} ticket capacity.`] };
  }
  return { model: PARWA_MODELS[1], reasons: [`Your ${fmtNum(tickets)} tickets/month exceeds PARWA's ${fmtNum(VARIANT_LIMITS.parwa.monthlyTickets)} limit — PARWA High gives you ${fmtNum(VARIANT_LIMITS.high.monthlyTickets)} tickets.`] };
}

interface ComparisonResult {
  model: ParwaModel;
  aiTickets: number;
  humanTickets: number;
  overageTickets: number;
  overageCost: number;
  parwaMonthly: number;
  parwaAnnual: number;
  currentMonthly: number;
  currentAnnual: number;
  monthlySavings: number;
  annualSavings: number;
  savingsPercent: number;
  // Quality improvements
  responseTimeCurrent: string;
  responseTimePARWA: string;
  consistencyCurrent: string;
  consistencyPARWA: string;
  availabilityCurrent: string;
  availabilityPARWA: string;
  csatCurrent: number;
  csatPARWA: number;
  isRecommended: boolean;
}

function calculateResults(tickets: number, employeeCost: number, cpt: number, recommendedTier: VariantTier): ComparisonResult[] {
  // Current cost = employees needed × cost per employee
  const employeesNeeded = Math.ceil(tickets / TICKETS_PER_EMPLOYEE);
  const currentMonthly = employeesNeeded * employeeCost;
  const currentAnnual = currentMonthly * 12;

  return PARWA_MODELS.map((model) => {
    const aiTickets = Math.round(tickets * model.aiResolution);
    const humanTickets = tickets - aiTickets;
    const overageTickets = Math.max(0, tickets - model.ticketLimit);
    const overageCost = overageTickets * OVERAGE_PRICE_PER_TICKET;
    const humanHandoffCost = humanTickets * cpt * HUMAN_HANDOFF_FACTOR;
    const parwaMonthly = model.price + overageCost + humanHandoffCost;
    const parwaAnnual = parwaMonthly * 12;
    const monthlySavings = Math.max(0, currentMonthly - parwaMonthly);
    const annualSavings = Math.max(0, currentAnnual - parwaAnnual);
    const savingsPercent = currentAnnual > 0 ? (annualSavings / currentAnnual) * 100 : 0;

    return {
      model,
      aiTickets,
      humanTickets,
      overageTickets,
      overageCost,
      parwaMonthly,
      parwaAnnual,
      currentMonthly,
      currentAnnual,
      monthlySavings,
      annualSavings,
      savingsPercent,
      responseTimeCurrent: '4–6 hours',
      responseTimePARWA: 'Under 30 seconds',
      consistencyCurrent: 'Varies by agent mood/experience',
      consistencyPARWA: '100% consistent every time',
      availabilityCurrent: '8 hours/day, 5 days/week',
      availabilityPARWA: '24/7/365 — never sleeps',
      csatCurrent: 78,
      csatPARWA: 92,
      isRecommended: model.tier === recommendedTier,
    };
  });
}

export default function ROICalculatorPage() {
  const navigate = useAppStore((s) => s.navigate);
  const [step, setStep] = useState(1);
  const [companyName, setCompanyName] = useState('');
  const [industry, setIndustry] = useState('');
  const [monthlyTickets, setMonthlyTickets] = useState('');
  const [employeeCost, setEmployeeCost] = useState('');

  const tickets = Math.max(0, Number(monthlyTickets) || 0);
  const empCost = Number(employeeCost) || DEFAULT_EMPLOYEE_COST;
  const cpt = INDUSTRIES.find((i) => i.id === industry)?.avgCostPerTicket || 7;

  const { model: recommendedModel, reasons: recommendationReasons } = useMemo(
    () => getRecommendedModel(tickets),
    [tickets]
  );

  const results = useMemo(
    () => calculateResults(tickets, empCost, cpt, recommendedModel.tier),
    [tickets, empCost, cpt, recommendedModel.tier]
  );
  const recommended = results.find((r) => r.isRecommended)!;

  const canGoNext = step === 1 ? companyName.trim().length > 0 && industry.length > 0 : tickets > 0;

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 30%, #2D1F0E 60%, #3D2A10 80%, #1A1A1A 100%)' }}>
      <NavigationBar />

      <main className="flex-grow flex items-start justify-center px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        <div className="w-full max-w-4xl">
          {/* Step Indicator */}
          <div className="flex items-center justify-center gap-3 mb-10">
            {[
              { n: 1, label: 'Your Business' },
              { n: 2, label: 'Current Costs' },
              { n: 3, label: 'Your Results' },
            ].map((s, i) => (
              <React.Fragment key={s.n}>
                <div className="flex items-center gap-2">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-500 ${step >= s.n ? 'bg-gradient-to-br from-orange-500 to-orange-600 text-white shadow-lg shadow-orange-500/30' : 'bg-white/5 text-gray-500 border border-white/10'}`}>
                    {step > s.n ? <Check className="w-4 h-4" /> : s.n}
                  </div>
                  <span className={`text-xs font-medium hidden sm:block transition-colors duration-500 ${step >= s.n ? 'text-orange-300' : 'text-gray-600'}`}>{s.label}</span>
                </div>
                {i < 2 && <div className={`w-8 sm:w-20 h-px transition-all duration-500 ${step > s.n ? 'bg-orange-500/50' : 'bg-white/10'}`} />}
              </React.Fragment>
            ))}
          </div>

          {/* ── Step 1: Business Info ── */}
          {step === 1 && (
            <div>
              <div className="text-center mb-8">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/20 mb-4">
                  <Building2 className="w-3.5 h-3.5 text-orange-400" />
                  <span className="text-xs font-semibold text-orange-300">Step 1 of 3</span>
                </div>
                <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white mb-3">Tell us about <span className="text-orange-400">your business</span></h1>
                <p className="text-sm text-gray-400 max-w-lg mx-auto">We&apos;ll calculate your savings and quality improvements.</p>
              </div>
              <div className="rounded-2xl border border-white/10 p-6 sm:p-8 space-y-6" style={{ background: 'rgba(255,255,255,0.03)' }}>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2"><Building2 className="w-4 h-4 inline mr-1.5 text-orange-400/70" />Company Name</label>
                  <input type="text" value={companyName} onChange={(e) => setCompanyName(e.target.value)} placeholder="e.g. Acme Corp" className="w-full px-4 py-3.5 rounded-xl border border-white/10 bg-white/5 text-white text-sm placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/50 transition-all" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-3"><Target className="w-4 h-4 inline mr-1.5 text-orange-400/70" />Industry</label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                    {INDUSTRIES.map((ind) => (
                      <button key={ind.id} onClick={() => setIndustry(ind.id)} className={`flex items-center justify-center gap-2 px-3 py-3.5 rounded-xl text-sm font-medium transition-all duration-300 border ${industry === ind.id ? 'border-orange-500/50 bg-orange-500/10 text-orange-300' : 'border-white/10 bg-white/5 text-gray-400 hover:border-white/20 hover:bg-white/[0.07]'}`}>{ind.label}</button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── Step 2: Tickets + Employee Cost ── */}
          {step === 2 && (
            <div>
              <div className="text-center mb-8">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/20 mb-4">
                  <DollarSign className="w-3.5 h-3.5 text-orange-400" />
                  <span className="text-xs font-semibold text-orange-300">Step 2 of 3</span>
                </div>
                <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white mb-3">Your current <span className="text-orange-400">support costs</span></h1>
                <p className="text-sm text-gray-400 max-w-lg mx-auto">Tell us your ticket volume and how much you pay your support team.</p>
              </div>
              <div className="rounded-2xl border border-white/10 p-6 sm:p-8 space-y-6" style={{ background: 'rgba(255,255,255,0.03)' }}>
                {/* Monthly Tickets */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2"><TicketCheck className="w-4 h-4 inline mr-1.5 text-orange-400/70" />How many support tickets do you get per month?</label>
                  <input type="number" value={monthlyTickets} onChange={(e) => setMonthlyTickets(e.target.value)} placeholder="e.g. 5000" className="w-full px-4 py-3.5 rounded-xl border border-white/10 bg-white/5 text-white text-sm placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/50 transition-all" />
                  <p className="text-xs text-gray-500 mt-2">Include all channels — email, chat, phone, social media.</p>
                </div>
                {/* Employee Cost */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2"><DollarSign className="w-4 h-4 inline mr-1.5 text-orange-400/70" />How much do you pay per support employee per month?</label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 text-sm">$</span>
                    <input type="number" value={employeeCost} onChange={(e) => setEmployeeCost(e.target.value)} placeholder={`${DEFAULT_EMPLOYEE_COST} (US average with benefits)`} className="w-full pl-8 pr-4 py-3.5 rounded-xl border border-white/10 bg-white/5 text-white text-sm placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/50 transition-all" />
                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 text-sm">/month</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">Include salary + benefits + overhead. US average: ~$4,500/month per support rep. Leave blank to use average.</p>
                </div>
                {/* Quick info */}
                <div className="rounded-xl bg-orange-500/5 border border-orange-500/10 p-4">
                  <p className="text-xs text-orange-300/70 leading-relaxed">
                    <strong className="text-orange-400">Why we ask:</strong> A human support rep handles ~400 tickets/month and costs ~$4,500/month (salary + benefits).
                    PARWA resolves 88% of tickets automatically for $2,499–$3,999/month. We&apos;ll show you exactly how much you save.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* ── Step 3: Results ── */}
          {step === 3 && (
            <div className="space-y-6">
              <div className="text-center mb-2">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 mb-4">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-xs font-semibold text-emerald-300">Your Personalized ROI Report</span>
                </div>
                <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white mb-2">Here&apos;s what <span className="text-orange-400">{companyName}</span> saves</h1>
                <p className="text-sm text-gray-400">Based on {fmtNum(tickets)} tickets/month at {fmtMoney(empCost)}/employee in {INDUSTRIES.find((i) => i.id === industry)?.label || 'your industry'}</p>
              </div>

              {/* ── Cost Savings ── */}
              <div className="rounded-2xl border-2 border-orange-500/40 p-6 sm:p-8 relative overflow-hidden" style={{ background: 'linear-gradient(135deg, rgba(255,127,17,0.12) 0%, rgba(26,26,26,0.9) 60%, rgba(255,127,17,0.05) 100%)' }}>
                <div className="absolute -top-20 -right-20 w-60 h-60 bg-orange-500/10 rounded-full blur-[100px] pointer-events-none" />
                <div className="relative">
                  <div className="flex items-center gap-2 mb-5">
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-orange-500/20 border border-orange-500/30">
                      <Sparkles className="w-3.5 h-3.5 text-orange-400" />
                      <span className="text-xs font-bold text-orange-300 uppercase tracking-wider">Recommended for You</span>
                    </div>
                    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${recommendedModel.tierBg} ${recommendedModel.tierBorder} border ${recommendedModel.tierColor}`}>{recommendedModel.tierLabel}</span>
                  </div>
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-4">
                    <div>
                      <h2 className="text-2xl sm:text-3xl font-black text-white mb-1">{recommendedModel.name}</h2>
                      <p className="text-base text-orange-300/80 font-medium">&ldquo;{recommendedModel.tagline}&rdquo;</p>
                    </div>
                    <div className="text-left sm:text-right flex-shrink-0">
                      <div className="text-4xl font-black text-orange-400">${recommendedModel.price.toLocaleString()}</div>
                      <div className="text-sm text-gray-400">/month</div>
                    </div>
                  </div>
                  <p className="text-sm text-gray-400 leading-relaxed mb-5">{recommendedModel.description}</p>

                  {/* Cost breakdown */}
                  <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-4 mb-5">
                    <h3 className="text-sm font-bold text-orange-200 mb-3 flex items-center gap-2"><BarChart3 className="w-4 h-4 text-orange-400" />Monthly Cost Breakdown</h3>
                    <div className="space-y-2.5">
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-400">Your current cost ({Math.ceil(tickets / TICKETS_PER_EMPLOYEE)} employees × {fmtMoney(empCost)})</span>
                        <span className="text-gray-300 font-medium tabular-nums">{fmtMoney(recommended.currentMonthly)}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-400">PARWA {recommendedModel.name} subscription</span>
                        <span className="text-white font-medium tabular-nums">{fmtMoney(recommended.model.price)}</span>
                      </div>
                      {recommended.overageCost > 0 && (
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-400">Overage ({fmtNum(recommended.overageTickets)} tickets × ${OVERAGE_PRICE_PER_TICKET.toFixed(2)})</span>
                          <span className="text-amber-400 font-medium tabular-nums">{fmtMoney(recommended.overageCost)}</span>
                        </div>
                      )}
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-400">Human handoff ({fmtNum(recommended.humanTickets)} tickets × 25% effort)</span>
                        <span className="text-white font-medium tabular-nums">{fmtMoney(recommended.humanHandoffCost || (recommended.humanTickets * cpt * HUMAN_HANDOFF_FACTOR))}</span>
                      </div>
                      <div className="border-t border-white/10 pt-2.5 flex justify-between">
                        <span className="text-sm font-bold text-white">Total PARWA monthly cost</span>
                        <span className="text-orange-400 font-black tabular-nums">{fmtMoney(recommended.parwaMonthly)}</span>
                      </div>
                    </div>
                  </div>

                  {/* Why this model */}
                  <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-4">
                    <div className="flex items-center gap-2 mb-3"><Brain className="w-4 h-4 text-orange-400" /><span className="text-sm font-bold text-orange-200">Why this model for {companyName}?</span></div>
                    <ul className="space-y-2">{recommendationReasons.map((reason, i) => (<li key={i} className="flex items-start gap-2.5"><div className="w-5 h-5 rounded-full bg-orange-500/20 flex items-center justify-center flex-shrink-0 mt-0.5"><Check className="w-3 h-3 text-orange-400" /></div><span className="text-sm text-gray-300 leading-relaxed">{reason}</span></li>))}</ul>
                  </div>
                </div>
              </div>

              {/* ── Savings Cards ── */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-center"><PiggyBank className="w-5 h-5 text-emerald-400 mx-auto mb-2" /><div className="text-2xl sm:text-3xl font-black text-emerald-400">{fmtMoney(recommended.annualSavings)}</div><div className="text-xs text-gray-400 mt-1">Annual Savings</div></div>
                <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-4 text-center"><TrendingUp className="w-5 h-5 text-orange-400 mx-auto mb-2" /><div className="text-2xl sm:text-3xl font-black text-orange-400">{recommended.savingsPercent.toFixed(0)}%</div><div className="text-xs text-gray-400 mt-1">Cost Reduction</div></div>
                <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4 text-center"><Clock className="w-5 h-5 text-blue-400 mx-auto mb-2" /><div className="text-2xl sm:text-3xl font-black text-blue-400">{fmtNum(recommended.aiTickets)}</div><div className="text-xs text-gray-400 mt-1">Tickets Auto-Resolved/mo</div></div>
                <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-4 text-center"><Zap className="w-5 h-5 text-purple-400 mx-auto mb-2" /><div className="text-2xl sm:text-3xl font-black text-purple-400">{Math.ceil(tickets / TICKETS_PER_EMPLOYEE)}</div><div className="text-xs text-gray-400 mt-1">Human Agents Replaced</div></div>
              </div>

              {/* ── Quality Improvements ── */}
              <div className="rounded-2xl border border-white/10 p-5 sm:p-6" style={{ background: 'rgba(255,255,255,0.03)' }}>
                <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2"><Award className="w-4 h-4 text-orange-400" />Quality Improvements with PARWA</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Response Time */}
                  <div className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/5">
                    <Clock className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Response Time</p>
                      <p className="text-sm text-red-400 line-through">{recommended.responseTimeCurrent}</p>
                      <p className="text-sm text-emerald-400 font-medium">{recommended.responseTimePARWA}</p>
                    </div>
                  </div>
                  {/* Consistency */}
                  <div className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/5">
                    <Check className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Consistency</p>
                      <p className="text-sm text-red-400 line-through">{recommended.consistencyCurrent}</p>
                      <p className="text-sm text-emerald-400 font-medium">{recommended.consistencyPARWA}</p>
                    </div>
                  </div>
                  {/* Availability */}
                  <div className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/5">
                    <Headphones className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Availability</p>
                      <p className="text-sm text-red-400 line-through">{recommended.availabilityCurrent}</p>
                      <p className="text-sm text-emerald-400 font-medium">{recommended.availabilityPARWA}</p>
                    </div>
                  </div>
                  {/* CSAT */}
                  <div className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/5">
                    <ThumbsUp className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Customer Satisfaction (CSAT)</p>
                      <p className="text-sm text-red-400 line-through">{recommended.csatCurrent}%</p>
                      <p className="text-sm text-emerald-400 font-medium">{recommended.csatPARWA}% (+{recommended.csatPARWA - recommended.csatCurrent} points)</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* CTA */}
              <div className="text-center pt-4">
                <button onClick={() => navigate('signup')} className="inline-flex items-center gap-2 px-8 py-4 rounded-xl text-sm font-bold bg-gradient-to-r from-orange-500 to-orange-400 text-[#1A1A1A] shadow-lg shadow-orange-500/25 hover:from-orange-400 hover:to-orange-300 hover:shadow-orange-500/40 hover:-translate-y-0.5 transition-all duration-300">
                  Get Started with {recommendedModel.name}
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* Navigation Buttons */}
          <div className="flex justify-between mt-10">
            {step > 1 ? (
              <button onClick={() => setStep(step - 1)} className="px-6 py-3 rounded-xl text-sm font-semibold bg-white/5 text-zinc-300 border border-white/10 hover:border-white/20 hover:bg-white/10 transition-all">Back</button>
            ) : <div />}
            {step < 3 ? (
              <button onClick={() => canGoNext && setStep(step + 1)} disabled={!canGoNext} className="px-6 py-3 rounded-xl text-sm font-bold bg-gradient-to-r from-orange-500 to-orange-400 text-[#1A1A1A] shadow-lg shadow-orange-500/25 disabled:opacity-50 disabled:cursor-not-allowed transition-all">Continue</button>
            ) : (
              <button onClick={() => navigate('landing')} className="px-6 py-3 rounded-xl text-sm font-semibold bg-white/5 text-zinc-300 border border-white/10 hover:border-white/20 hover:bg-white/10 transition-all">Back to Home</button>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
