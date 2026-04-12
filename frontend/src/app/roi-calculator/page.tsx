'use client';

import React, { useState, useMemo } from 'react';
import Link from 'next/link';
import {
  ArrowLeft, Calculator, TrendingUp, DollarSign,
  Users, Clock, Headphones, BarChart3, Zap, ArrowRight,
  ChevronDown, Sparkles, Target, ShieldCheck
} from 'lucide-react';

// ──────────────────────────────────────────────────────────────────
// CONSTANTS — realistic industry benchmarks
// ──────────────────────────────────────────────────────────────────

const INDUSTRIES = [
  { id: 'ecommerce', label: 'E-Commerce', avgTicketVolume: 5000, avgCostPerTicket: 6.5, avgFcr: 0.68, avgCsat: 3.8 },
  { id: 'saas', label: 'SaaS / Tech', avgTicketVolume: 3500, avgCostPerTicket: 8.2, avgFcr: 0.62, avgCsat: 3.6 },
  { id: 'logistics', label: 'Logistics', avgTicketVolume: 6000, avgCostPerTicket: 5.8, avgFcr: 0.58, avgCsat: 3.5 },
  { id: 'healthcare', label: 'Healthcare', avgTicketVolume: 4000, avgCostPerTicket: 7.5, avgFcr: 0.55, avgCsat: 3.4 },
  { id: 'finance', label: 'Finance / Fintech', avgTicketVolume: 3000, avgCostPerTicket: 9.0, avgFcr: 0.60, avgCsat: 3.7 },
  { id: 'others', label: 'Other', avgTicketVolume: 4000, avgCostPerTicket: 7.0, avgFcr: 0.60, avgCsat: 3.5 },
];

const TEAM_SIZES = [
  { label: '1-5 agents', value: 5 },
  { label: '6-15 agents', value: 15 },
  { label: '16-30 agents', value: 30 },
  { label: '31-50 agents', value: 50 },
  { label: '50+ agents', value: 75 },
];

const SALARY_BENCHMARKS: Record<string, number> = {
  '1-5 agents': 35000,
  '6-15 agents': 38000,
  '16-30 agents': 40000,
  '31-50 agents': 42000,
  '50+ agents': 45000,
};

// ──────────────────────────────────────────────────────────────────
// ROI CALCULATOR TYPES
// ──────────────────────────────────────────────────────────────────

interface ROICalculatorInput {
  industry: string;
  monthlyTickets: string;
  costPerTicket: string;
  teamSize: string;
  avgSalary: string;
  parwaPlan: string;
  currentFcr: string;
  currentCsat: string;
}

interface ROIResult {
  currentMonthlyCost: number;
  currentAnnualCost: number;
  parwaMonthlyCost: number;
  parwaAnnualCost: number;
  monthlySavings: number;
  annualSavings: number;
  savingsPercent: number;
  aiResolutionPercent: number;
  agentTimeReclaimed: number;
  newCsat: number;
  newFcr: number;
  paybackMonths: number;
  threeYearROI: number;
}

// ──────────────────────────────────────────────────────────────────
// HELPER — animated counter effect
// ──────────────────────────────────────────────────────────────────

function formatCurrency(num: number): string {
  if (num >= 1000000) return `$${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `$${(num / 1000).toFixed(1)}K`;
  return `$${num.toFixed(0)}`;
}

function formatNumber(num: number): string {
  return num.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

// ──────────────────────────────────────────────────────────────────
// MAIN ROI CALCULATOR PAGE
// ──────────────────────────────────────────────────────────────────

export default function ROICalculatorPage() {
  const [input, setInput] = useState<ROICalculatorInput>({
    industry: 'ecommerce',
    monthlyTickets: '5000',
    costPerTicket: '6.5',
    teamSize: '6-15 agents',
    avgSalary: '38000',
    parwaPlan: 'parwa',
    currentFcr: '68',
    currentCsat: '3.8',
  });

  const [showResults, setShowResults] = useState(false);

  // ── Compute ROI ──
  const result: ROIResult = useMemo(() => {
    const tickets = Math.max(1, Number(input.monthlyTickets) || 0);
    const costPerTicket = Number(input.costPerTicket) || 0;
    const agentCount = TEAM_SIZES.find((t) => t.label === input.teamSize)?.value || 15;
    const avgSalary = Number(input.avgSalary) || 38000;

    // PARWA plan pricing
    const parwaPlanCost: Record<string, number> = {
      'mini-parwa': 499,
      'parwa': 999,
      'high-parwa': 1499,
    };
    const monthlyPlanCost = parwaPlanCost[input.parwaPlan] || 999;

    // Current monthly support cost = tickets * cost per ticket + agent salaries
    const currentMonthlyLabor = (avgSalary / 12) * agentCount;
    const currentMonthlyCost = (tickets * costPerTicket) + currentMonthlyLabor;
    const currentAnnualCost = currentMonthlyCost * 12;

    // PARWA resolves 70-80% of tickets with AI
    const aiResolutionPercent = input.parwaPlan === 'mini-parwa' ? 0.65 : input.parwaPlan === 'parwa' ? 0.78 : 0.85;
    const ticketsHandledByAI = tickets * aiResolutionPercent;
    const ticketsHandledByAgents = tickets - ticketsHandledByAI;

    // PARWA cost = plan cost + reduced agent tickets * lower cost
    const parwaMonthlyCost = monthlyPlanCost + (ticketsHandledByAgents * costPerTicket * 0.3);
    const parwaAnnualCost = parwaMonthlyCost * 12;

    // Savings
    const monthlySavings = currentMonthlyCost - parwaMonthlyCost;
    const annualSavings = monthlySavings * 12;
    const savingsPercent = currentMonthlyCost > 0 ? (monthlySavings / currentMonthlyCost) * 100 : 0;

    // Agent time reclaimed (hours per month)
    const hoursPerTicket = 0.25; // ~15 min avg per ticket
    const agentTimeReclaimed = ticketsHandledByAI * hoursPerTicket;

    // Improved metrics
    const currentFcr = Number(input.currentFcr) || 68;
    const currentCsat = Number(input.currentCsat) || 3.8;
    const newFcr = Math.min(95, currentFcr + (95 - currentFcr) * 0.6);
    const newCsat = Math.min(5, currentCsat + (5 - currentCsat) * 0.45);

    // Payback period
    const paybackMonths = monthlySavings > 0 ? monthlyPlanCost / monthlySavings : 0;

    // 3-year ROI
    const threeYearROI = (annualSavings * 3 - parwaAnnualCost * 3) / (parwaAnnualCost * 3) * 100;

    return {
      currentMonthlyCost,
      currentAnnualCost,
      parwaMonthlyCost,
      parwaAnnualCost,
      monthlySavings,
      annualSavings,
      savingsPercent: Math.max(0, savingsPercent),
      aiResolutionPercent: aiResolutionPercent * 100,
      agentTimeReclaimed,
      newCsat,
      newFcr,
      paybackMonths: Math.max(1, paybackMonths),
      threeYearROI: Math.max(0, threeYearROI),
    };
  }, [input]);

  // ── Handlers ──
  const updateInput = (key: keyof ROICalculatorInput, value: string) => {
    setInput((prev) => ({ ...prev, [key]: value }));
    // Auto-fill industry defaults
    if (key === 'industry') {
      const ind = INDUSTRIES.find((i) => i.id === value);
      if (ind) {
        setInput((prev) => ({
          ...prev,
          monthlyTickets: String(ind.avgTicketVolume),
          costPerTicket: String(ind.avgCostPerTicket),
          currentFcr: String(Math.round(ind.avgFcr * 100)),
          currentCsat: String(ind.avgCsat),
        }));
      }
    }
    if (key === 'teamSize') {
      const salary = SALARY_BENCHMARKS[value];
      if (salary) setInput((prev) => ({ ...prev, avgSalary: String(salary) }));
    }
  };

  const handleCalculate = () => {
    setShowResults(true);
    // Smooth scroll to results
    setTimeout(() => {
      document.getElementById('roi-results')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  };

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-[#ECFDF5] to-white">
      {/* Navigation */}
      <nav className="sticky top-0 z-50 bg-white/95 backdrop-blur-2xl shadow-lg shadow-gray-900/5 border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-600 to-emerald-700 flex items-center justify-center shadow-lg shadow-emerald-600/25">
                <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
                </svg>
              </div>
              <span className="text-lg font-bold text-gray-900">PARWA</span>
            </Link>
            <div className="hidden md:flex items-center gap-1">
              {[
                { name: 'Home', href: '/' },
                { name: 'Models', href: '/models' },
                { name: 'Pricing', href: '/pricing' },
                { name: 'ROI Calculator', href: '/roi-calculator' },
                { name: 'Try Jarvis', href: '/jarvis' },
              ].map((link) => (
                <Link key={link.name} href={link.href} className={`px-3.5 lg:px-4 py-2 text-sm font-medium transition-all duration-300 rounded-xl ${link.name === 'ROI Calculator' ? 'text-emerald-700 bg-emerald-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'}`}>
                  {link.name}
                </Link>
              ))}
            </div>
            <Link href="/login" className="bg-gradient-to-r from-emerald-600 to-emerald-500 text-white px-5 py-2.5 rounded-xl text-sm font-semibold shadow-lg shadow-emerald-600/25">
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      <main className="flex-grow">
        {/* ── Hero ── */}
        <section className="relative pt-10 sm:pt-14 pb-6 px-4 sm:px-6 lg:px-8">
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[350px] bg-emerald-200/20 blur-[120px] rounded-full" />
          </div>
          <div className="relative max-w-4xl mx-auto text-center">
            <Link href="/" className="inline-flex items-center gap-2 text-gray-400 hover:text-gray-600 mb-6 transition-colors text-sm">
              <ArrowLeft className="w-3.5 h-3.5" /> Back to Home
            </Link>
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 mb-5">
              <Calculator className="w-4 h-4 text-emerald-600" />
              <span className="text-xs font-semibold text-emerald-700">Free ROI Estimator</span>
            </div>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-gray-900 mb-4 leading-tight">
              Calculate Your <span className="text-gradient">ROI with PARWA</span>
            </h1>
            <p className="text-base sm:text-lg text-gray-500 max-w-2xl mx-auto leading-relaxed">
              See exactly how much time and money PARWA AI can save your support team. Enter your numbers below and get instant results.
            </p>
          </div>
        </section>

        {/* ── Calculator Form ── */}
        <section className="px-4 sm:px-6 lg:px-8 pb-8">
          <div className="max-w-5xl mx-auto">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-8">
              {/* Left Column — Inputs */}
              <div className="space-y-5">
                {/* Industry */}
                <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 shadow-sm">
                  <div className="flex items-center gap-2.5 mb-5">
                    <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center">
                      <BarChart3 className="w-5 h-5 text-emerald-700" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-gray-900">Industry</h3>
                      <p className="text-xs text-gray-400">Auto-fills benchmarks below</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {INDUSTRIES.map((ind) => (
                      <button
                        key={ind.id}
                        onClick={() => updateInput('industry', ind.id)}
                        className={`px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-300 border ${
                          input.industry === ind.id
                            ? 'border-emerald-400 bg-emerald-50 text-emerald-700 shadow-sm'
                            : 'border-gray-200 bg-white text-gray-600 hover:border-emerald-200 hover:bg-gray-50'
                        }`}
                      >
                        {ind.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Support Volume */}
                <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 shadow-sm">
                  <div className="flex items-center gap-2.5 mb-5">
                    <div className="w-9 h-9 rounded-xl bg-blue-100 flex items-center justify-center">
                      <Users className="w-5 h-5 text-blue-700" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-gray-900">Support Volume</h3>
                      <p className="text-xs text-gray-400">Your current ticket volume</p>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">Monthly Tickets</label>
                      <input
                        type="number"
                        value={input.monthlyTickets}
                        onChange={(e) => updateInput('monthlyTickets', e.target.value)}
                        className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-400 transition-all"
                        placeholder="e.g. 5000"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">Cost per Ticket ($)</label>
                      <input
                        type="number"
                        step="0.5"
                        value={input.costPerTicket}
                        onChange={(e) => updateInput('costPerTicket', e.target.value)}
                        className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-400 transition-all"
                        placeholder="e.g. 6.50"
                      />
                    </div>
                  </div>
                </div>

                {/* Team */}
                <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 shadow-sm">
                  <div className="flex items-center gap-2.5 mb-5">
                    <div className="w-9 h-9 rounded-xl bg-purple-100 flex items-center justify-center">
                      <Headphones className="w-5 h-5 text-purple-700" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-gray-900">Your Team</h3>
                      <p className="text-xs text-gray-400">Agent headcount &amp; salary</p>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">Team Size</label>
                      <div className="relative">
                        <select
                          value={input.teamSize}
                          onChange={(e) => updateInput('teamSize', e.target.value)}
                          className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 text-sm font-medium bg-white appearance-none focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-400 transition-all"
                        >
                          {TEAM_SIZES.map((t) => (
                            <option key={t.label} value={t.label}>{t.label}</option>
                          ))}
                        </select>
                        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">Avg. Agent Salary (Annual $)</label>
                      <input
                        type="number"
                        value={input.avgSalary}
                        onChange={(e) => updateInput('avgSalary', e.target.value)}
                        className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-400 transition-all"
                        placeholder="e.g. 38000"
                      />
                    </div>
                  </div>
                </div>

                {/* Current Metrics */}
                <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 shadow-sm">
                  <div className="flex items-center gap-2.5 mb-5">
                    <div className="w-9 h-9 rounded-xl bg-amber-100 flex items-center justify-center">
                      <Target className="w-5 h-5 text-amber-700" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-gray-900">Current Metrics</h3>
                      <p className="text-xs text-gray-400">Your existing KPIs</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">FCR (%)</label>
                      <input
                        type="number"
                        value={input.currentFcr}
                        onChange={(e) => updateInput('currentFcr', e.target.value)}
                        className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-400 transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">CSAT (out of 5)</label>
                      <input
                        type="number"
                        step="0.1"
                        value={input.currentCsat}
                        onChange={(e) => updateInput('currentCsat', e.target.value)}
                        className="w-full px-4 py-3 rounded-xl border border-gray-200 text-gray-900 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-400 transition-all"
                      />
                    </div>
                  </div>
                </div>

                {/* Plan Selection */}
                <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 shadow-sm">
                  <div className="flex items-center gap-2.5 mb-5">
                    <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center">
                      <Zap className="w-5 h-5 text-emerald-700" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-gray-900">PARWA Plan</h3>
                      <p className="text-xs text-gray-400">Choose your plan tier</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { id: 'mini-parwa', name: 'Mini', price: '$499' },
                      { id: 'parwa', name: 'Parwa', price: '$999' },
                      { id: 'high-parwa', name: 'High', price: '$1,499' },
                    ].map((plan) => (
                      <button
                        key={plan.id}
                        onClick={() => updateInput('parwaPlan', plan.id)}
                        className={`px-3 py-3 rounded-xl text-center transition-all duration-300 border ${
                          input.parwaPlan === plan.id
                            ? 'border-emerald-400 bg-emerald-50 shadow-sm'
                            : 'border-gray-200 bg-white hover:border-emerald-200 hover:bg-gray-50'
                        }`}
                      >
                        <div className={`text-xs font-bold mb-0.5 ${input.parwaPlan === plan.id ? 'text-emerald-700' : 'text-gray-700'}`}>{plan.name}</div>
                        <div className={`text-sm font-extrabold ${input.parwaPlan === plan.id ? 'text-emerald-600' : 'text-gray-900'}`}>{plan.price}</div>
                        <div className="text-[10px] text-gray-400 mt-0.5">/month</div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Calculate Button */}
                <button
                  onClick={handleCalculate}
                  className="w-full py-4 rounded-xl bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white text-base font-bold shadow-lg shadow-emerald-500/30 hover:shadow-emerald-500/40 transition-all duration-500 flex items-center justify-center gap-2.5"
                >
                  <Calculator className="w-5 h-5" />
                  Calculate My ROI
                  <ArrowRight className="w-5 h-5" />
                </button>
              </div>

              {/* Right Column — Results */}
              <div id="roi-results">
                {/* Savings Hero Card */}
                <div className="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-6 sm:p-8 shadow-lg shadow-emerald-100/30 mb-5">
                  <div className="flex items-center gap-2 mb-3">
                    <TrendingUp className="w-5 h-5 text-emerald-600" />
                    <span className="text-sm font-semibold text-emerald-700">Estimated Annual Savings</span>
                  </div>
                  <div className="text-5xl sm:text-6xl font-black text-emerald-600 mb-1">
                    {formatCurrency(result.annualSavings)}
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    <span className="font-medium">{result.savingsPercent.toFixed(0)}% cost reduction</span>
                    <span className="text-gray-300">|</span>
                    <span>with PARWA {input.parwaPlan === 'mini-parwa' ? 'Mini' : input.parwaPlan === 'parwa' ? '' : 'High'}</span>
                  </div>

                  {/* Mini comparison bar */}
                  <div className="mt-6 space-y-3">
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-medium text-gray-600">Current Annual Cost</span>
                        <span className="font-bold text-gray-900">{formatCurrency(result.currentAnnualCost)}</span>
                      </div>
                      <div className="h-3 rounded-full bg-gray-200 overflow-hidden">
                        <div className="h-full rounded-full bg-gray-400 transition-all duration-700" style={{ width: '100%' }} />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-medium text-gray-600">With PARWA</span>
                        <span className="font-bold text-emerald-600">{formatCurrency(result.parwaAnnualCost)}</span>
                      </div>
                      <div className="h-3 rounded-full bg-gray-200 overflow-hidden">
                        <div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-700" style={{ width: `${Math.max(5, 100 - result.savingsPercent)}%` }} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Key Metrics Grid */}
                <div className="grid grid-cols-2 gap-3 mb-5">
                  {[
                    { icon: Zap, label: 'AI Resolution Rate', value: `${result.aiResolutionPercent.toFixed(0)}%`, color: 'emerald', desc: 'of tickets auto-resolved' },
                    { icon: Clock, label: 'Agent Hours Saved', value: `${formatNumber(result.agentTimeReclaimed)}h`, color: 'blue', desc: 'per month reclaimed' },
                    { icon: Target, label: 'New FCR', value: `${result.newFcr.toFixed(0)}%`, color: 'purple', desc: `from ${input.currentFcr}%` },
                    { icon: Sparkles, label: 'New CSAT', value: `${result.newCsat.toFixed(1)}/5`, color: 'amber', desc: `from ${input.currentCsat}` },
                  ].map((metric) => {
                    const Icon = metric.icon;
                    const colorMap: Record<string, string> = {
                      emerald: 'bg-emerald-100 text-emerald-700',
                      blue: 'bg-blue-100 text-blue-700',
                      purple: 'bg-purple-100 text-purple-700',
                      amber: 'bg-amber-100 text-amber-700',
                    };
                    return (
                      <div key={metric.label} className="rounded-2xl border border-gray-200 bg-white p-4 sm:p-5 shadow-sm">
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-3 ${colorMap[metric.color]}`}>
                          <Icon className="w-4 h-4" />
                        </div>
                        <div className="text-2xl sm:text-3xl font-black text-gray-900 mb-0.5">{metric.value}</div>
                        <div className="text-xs font-semibold text-gray-700">{metric.label}</div>
                        <div className="text-[11px] text-gray-400 mt-0.5">{metric.desc}</div>
                      </div>
                    );
                  })}
                </div>

                {/* Payback + 3-Year ROI */}
                <div className="grid grid-cols-2 gap-3 mb-5">
                  <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                    <div className="text-xs font-semibold text-gray-500 mb-1">Payback Period</div>
                    <div className="text-3xl font-black text-gray-900">{result.paybackMonths.toFixed(1)}</div>
                    <div className="text-xs text-gray-400">months to break even</div>
                  </div>
                  <div className="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-5 shadow-sm">
                    <div className="text-xs font-semibold text-emerald-600 mb-1">3-Year ROI</div>
                    <div className="text-3xl font-black text-emerald-600">{result.threeYearROI.toFixed(0)}%</div>
                    <div className="text-xs text-gray-400">return on investment</div>
                  </div>
                </div>

                {/* Monthly Breakdown */}
                <div className="rounded-2xl border border-gray-200 bg-white p-5 sm:p-6 shadow-sm mb-5">
                  <div className="flex items-center gap-2.5 mb-5">
                    <DollarSign className="w-5 h-5 text-gray-500" />
                    <h3 className="text-base font-bold text-gray-900">Monthly Cost Breakdown</h3>
                  </div>
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="text-sm font-medium text-gray-700">Current Monthly Cost</div>
                        <div className="text-xs text-gray-400">Agents + infrastructure</div>
                      </div>
                      <span className="text-lg font-bold text-gray-900">{formatCurrency(result.currentMonthlyCost)}</span>
                    </div>
                    <div className="border-t border-gray-100" />
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="text-sm font-medium text-gray-700">PARWA Monthly Cost</div>
                        <div className="text-xs text-gray-400">Plan + reduced agent load</div>
                      </div>
                      <span className="text-lg font-bold text-emerald-600">{formatCurrency(result.parwaMonthlyCost)}</span>
                    </div>
                    <div className="border-t border-gray-100" />
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="text-sm font-bold text-emerald-700">You Save Monthly</div>
                      </div>
                      <span className="text-xl font-black text-emerald-600">{formatCurrency(result.monthlySavings)}</span>
                    </div>
                  </div>
                </div>

                {/* CTA */}
                <div className="rounded-2xl border-2 border-dashed border-emerald-300 bg-emerald-50/50 p-5 sm:p-6 text-center">
                  <h3 className="text-base font-bold text-gray-900 mb-2">Ready to start saving?</h3>
                  <p className="text-sm text-gray-500 mb-4">Get started with PARWA today and see results in weeks, not months.</p>
                  <div className="flex flex-col sm:flex-row gap-3 justify-center">
                    <Link href="/pricing" className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-emerald-600 to-emerald-500 text-white text-sm font-bold shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40 transition-all duration-300">
                      View Pricing
                      <ArrowRight className="w-4 h-4" />
                    </Link>
                    <Link href="/jarvis" className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl border border-gray-200 bg-white text-gray-700 text-sm font-bold hover:border-emerald-300 hover:bg-emerald-50 transition-all duration-300">
                      Try Jarvis Free
                      <Sparkles className="w-4 h-4" />
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── Trust Section ── */}
        <section className="px-4 sm:px-6 lg:px-8 pb-12 sm:pb-16">
          <div className="max-w-4xl mx-auto">
            <div className="rounded-2xl bg-gray-900 p-6 sm:p-8 text-center">
              <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6 mb-6">
                {[
                  { icon: ShieldCheck, text: 'SOC 2 Compliant' },
                  { icon: Zap, text: 'Setup in 24 Hours' },
                  { icon: Users, text: '2,400+ Businesses' },
                  { icon: TrendingUp, text: 'Avg 60% Cost Savings' },
                ].map((item) => {
                  const Icon = item.icon;
                  return (
                    <div key={item.text} className="flex items-center gap-2 text-gray-300">
                      <Icon className="w-4 h-4 text-emerald-400" />
                      <span className="text-sm font-medium">{item.text}</span>
                    </div>
                  );
                })}
              </div>
              <p className="text-gray-400 text-xs max-w-xl mx-auto">
                * ROI estimates are based on industry benchmarks and averages. Actual results may vary based on your specific use case, ticket complexity, and implementation. PARWA guarantees measurable improvement within 90 days.
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="relative bg-[#1A0F08]">
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-orange-400/60 to-transparent" />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center">
                <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
                </svg>
              </div>
              <span className="text-sm font-bold text-white">PARWA</span>
            </div>
            <p className="text-gray-500 text-xs">&copy; 2026 PARWA. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
