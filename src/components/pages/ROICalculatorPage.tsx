'use client';

import React, { useState, useMemo } from 'react';
import { useAppStore } from '@/lib/store';
import { NavigationBar } from '@/components/landing';
import { Footer } from '@/components/landing';
import {
  Building2, Users, TicketCheck, TrendingUp, Zap, DollarSign,
  Clock, Target, Sparkles, Check, BarChart3, PiggyBank, Brain,
  Headphones, MessageSquare, Phone, Video, Globe, ArrowDownRight,
  ThumbsUp,
} from 'lucide-react';

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
}

const PARWA_MODELS: ParwaModel[] = [
  { id: 'parwa-starter', name: 'PARWA Starter', tagline: 'The 24/7 Trainee', tier: 'Entry', price: 999, aiResolution: 0.60, agents: 3, ticketCapacity: '1K tickets/mo', channels: ['Email', 'Chat'], description: 'Your first AI teammate. Handles FAQs, ticket intake, and basic queries autonomously.', bestFor: 'Small teams with FAQ-heavy support', tierLabel: 'Entry Level', tierColor: 'text-emerald-400', tierBorder: 'border-emerald-500/30', tierBg: 'bg-emerald-500/5' },
  { id: 'parwa-growth', name: 'PARWA Growth', tagline: 'The Junior Agent', tier: 'Growth', price: 2499, aiResolution: 0.78, agents: 8, ticketCapacity: '5K tickets/mo', channels: ['Email', 'Chat', 'SMS', 'Voice'], description: 'Your smartest junior agent. Resolves ~78% of tickets autonomously with multi-channel support.', bestFor: 'Growing businesses needing multi-channel support', tierLabel: 'Most Popular', tierColor: 'text-orange-400', tierBorder: 'border-orange-500/30', tierBg: 'bg-orange-500/5' },
  { id: 'parwa-high', name: 'PARWA High', tagline: 'The Senior Agent', tier: 'Enterprise', price: 3999, aiResolution: 0.88, agents: 15, ticketCapacity: '15K tickets/mo', channels: ['Email', 'Chat', 'SMS', 'Voice', 'Social', 'Video'], description: 'Your most experienced senior agent. Handles complex cases and provides strategic insights.', bestFor: 'Enterprise teams with complex cases', tierLabel: 'Enterprise', tierColor: 'text-purple-400', tierBorder: 'border-purple-500/30', tierBg: 'bg-purple-500/5' },
];

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
  { label: '1–5 agents', value: 3 },
  { label: '6–10 agents', value: 8 },
  { label: '11–15 agents', value: 13 },
  { label: '16–30 agents', value: 23 },
  { label: '31–50 agents', value: 40 },
  { label: '50+ agents', value: 75 },
];

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

function fmtMoney(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
}
function fmtNum(n: number): string { return n.toLocaleString('en-US', { maximumFractionDigits: 0 }); }
function getChannelIcon(channel: string) {
  switch (channel) {
    case 'Email': return <MessageSquare className="w-3 h-3" />;
    case 'Chat': return <MessageSquare className="w-3 h-3" />;
    case 'SMS': return <Phone className="w-3 h-3" />;
    case 'Voice': return <Headphones className="w-3 h-3" />;
    case 'Social': return <Globe className="w-3 h-3" />;
    case 'Video': return <Video className="w-3 h-3" />;
    default: return <Zap className="w-3 h-3" />;
  }
}

function getRecommendedModel(tickets: number, agentCount: number, industry: string) {
  let recommended: ParwaModel;
  const reasons: string[] = [];
  const industryLabel = INDUSTRIES.find((i) => i.id === industry)?.label || 'your industry';

  if (tickets <= 1000 && agentCount <= 5) {
    recommended = PARWA_MODELS[0];
    reasons.push(`Your volume of ${fmtNum(tickets)} tickets/month fits within the Starter tier.`);
  } else if (tickets <= 5000 && agentCount <= 15) {
    recommended = PARWA_MODELS[1];
    reasons.push(`Your ${fmtNum(tickets)} tickets/month exceeds Starter — Growth gives room to scale.`);
  } else {
    recommended = PARWA_MODELS[2];
    reasons.push(`Your volume requires High's 15K ticket capacity.`);
  }
  reasons.push(`Growth resolves ~${Math.round(recommended.aiResolution * 100)}% of tickets autonomously.`);
  return { model: recommended, reasons };
}

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
}

function calculateComparisons(tickets: number, agentCount: number, cpt: number, currentMonthly: number, currentAnnual: number, recommendedId: string): ModelComparison[] {
  return PARWA_MODELS.map((model) => {
    const aiTickets = Math.round(tickets * model.aiResolution);
    const humanTickets = tickets - aiTickets;
    const humanCost = humanTickets * cpt * 0.25;
    const parwaMonthly = model.price + humanCost;
    const parwaAnnual = parwaMonthly * 12;
    const monthlySavings = Math.max(0, currentMonthly - parwaMonthly);
    const annualSavings = Math.max(0, currentAnnual - parwaAnnual);
    const savingsPercent = currentAnnual > 0 ? (annualSavings / currentAnnual) * 100 : 0;
    const hoursSavedPerMonth = aiTickets * 0.25;
    const paybackMonths = monthlySavings > 0 ? parwaMonthly / monthlySavings : 999;
    return { model, aiTicketsPerMonth: aiTickets, humanTicketsPerMonth: humanTickets, parwaMonthlyCost: parwaMonthly, parwaAnnualCost: parwaAnnual, currentMonthlyCost: currentMonthly, currentAnnualCost: currentAnnual, monthlySavings, annualSavings, savingsPercent, hoursSavedPerMonth, paybackMonths: Math.min(12, Math.max(1, paybackMonths)), isRecommended: model.id === recommendedId };
  });
}

export default function ROICalculatorPage() {
  const navigate = useAppStore((s) => s.navigate);
  const [step, setStep] = useState(1);
  const [companyName, setCompanyName] = useState('');
  const [industry, setIndustry] = useState('');
  const [monthlyTickets, setMonthlyTickets] = useState('');
  const [teamSizeLabel, setTeamSizeLabel] = useState('');
  const [costPerTicket, setCostPerTicket] = useState('');

  const tickets = Math.max(0, Number(monthlyTickets) || 0);
  const agentCount = TEAM_SIZES.find((t) => t.label === teamSizeLabel)?.value || 0;
  const cpt = Number(costPerTicket) || BENCHMARKS[industry]?.avgCostPerTicket || 7;
  const avgSalary = BENCHMARKS[industry]?.avgSalary || 37000;

  const currentLaborMonthly = agentCount > 0 ? (avgSalary / 12) * agentCount : 0;
  const currentTicketCostMonthly = tickets * cpt;
  const currentTotalMonthly = currentLaborMonthly + currentTicketCostMonthly;
  const currentTotalAnnual = currentTotalMonthly * 12;

  const { model: recommendedModel, reasons: recommendationReasons } = useMemo(
    () => getRecommendedModel(tickets, agentCount, industry),
    [tickets, agentCount, industry]
  );

  const comparisons = useMemo(
    () => calculateComparisons(tickets, agentCount, cpt, currentTotalMonthly, currentTotalAnnual, recommendedModel.id),
    [tickets, agentCount, cpt, currentTotalMonthly, currentTotalAnnual, recommendedModel.id]
  );
  const recommendedComparison = comparisons.find((c) => c.isRecommended)!;

  const canGoNext = step === 1 ? companyName.trim().length > 0 && industry.length > 0 : step === 2 ? tickets > 0 && teamSizeLabel.length > 0 : true;

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'linear-gradient(180deg, #0D0D0D 0%, #1A1A1A 50%, #0D0D0D 100%)' }}>
      <NavigationBar />

      <main className="flex-grow flex items-start justify-center px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        <div className="w-full max-w-4xl">
          {/* Step Indicator */}
          <div className="flex items-center justify-center gap-3 mb-10">
            {[{ n: 1, label: 'Company Info' }, { n: 2, label: 'Support Setup' }, { n: 3, label: 'Your Results' }].map((s, i) => (
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

          {/* Step 1 */}
          {step === 1 && (
            <div>
              <div className="text-center mb-8">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/20 mb-4">
                  <Building2 className="w-3.5 h-3.5 text-orange-400" />
                  <span className="text-xs font-semibold text-orange-300">Step 1 of 3</span>
                </div>
                <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white mb-3">Tell us about <span className="text-orange-400">your business</span></h1>
                <p className="text-sm text-gray-400 max-w-lg mx-auto">We&apos;ll analyze your profile to recommend the perfect PARWA AI model.</p>
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
                      <button key={ind.id} onClick={() => setIndustry(ind.id)} className={`flex items-center justify-center gap-2 px-3 py-3.5 rounded-xl text-sm font-medium transition-all duration-300 border ${industry === ind.id ? 'border-orange-500/50 bg-orange-500/10 text-orange-300 shadow-sm shadow-orange-500/10' : 'border-white/10 bg-white/5 text-gray-400 hover:border-white/20 hover:bg-white/[0.07]'}`}>{ind.label}</button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 2 */}
          {step === 2 && (
            <div>
              <div className="text-center mb-8">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/20 mb-4">
                  <Users className="w-3.5 h-3.5 text-orange-400" />
                  <span className="text-xs font-semibold text-orange-300">Step 2 of 3</span>
                </div>
                <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white mb-3">Your current <span className="text-orange-400">support setup</span></h1>
                <p className="text-sm text-gray-400 max-w-lg mx-auto">Help us understand your support volume and team.</p>
              </div>
              <div className="rounded-2xl border border-white/10 p-6 sm:p-8 space-y-6" style={{ background: 'rgba(255,255,255,0.03)' }}>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2"><TicketCheck className="w-4 h-4 inline mr-1.5 text-orange-400/70" />Monthly Support Tickets</label>
                  <input type="number" value={monthlyTickets} onChange={(e) => setMonthlyTickets(e.target.value)} placeholder={BENCHMARKS[industry] ? `${BENCHMARKS[industry].avgTickets} (industry avg)` : 'e.g. 5000'} className="w-full px-4 py-3.5 rounded-xl border border-white/10 bg-white/5 text-white text-sm placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/50 transition-all" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-3"><Users className="w-4 h-4 inline mr-1.5 text-orange-400/70" />Support Team Size</label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                    {TEAM_SIZES.map((ts) => (
                      <button key={ts.label} onClick={() => setTeamSizeLabel(ts.label)} className={`px-4 py-3.5 rounded-xl text-sm font-medium transition-all duration-300 border text-center ${teamSizeLabel === ts.label ? 'border-orange-500/50 bg-orange-500/10 text-orange-300' : 'border-white/10 bg-white/5 text-gray-400 hover:border-white/20 hover:bg-white/[0.07]'}`}>{ts.label}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2"><DollarSign className="w-4 h-4 inline mr-1.5 text-orange-400/70" />Average Cost per Ticket <span className="text-gray-600 font-normal">(optional)</span></label>
                  <input type="number" step="0.50" value={costPerTicket} onChange={(e) => setCostPerTicket(e.target.value)} placeholder={BENCHMARKS[industry] ? `$${BENCHMARKS[industry].avgCostPerTicket} (industry avg)` : 'e.g. 6.50'} className="w-full px-4 py-3.5 rounded-xl border border-white/10 bg-white/5 text-white text-sm placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/50 transition-all" />
                </div>
              </div>
            </div>
          )}

          {/* Step 3 */}
          {step === 3 && (
            <div className="space-y-6">
              <div className="text-center mb-2">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 mb-4">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-xs font-semibold text-emerald-300">Your Personalized ROI Report</span>
                </div>
                <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white mb-2">Here&apos;s what <span className="text-orange-400">{companyName}</span> saves</h1>
                <p className="text-sm text-gray-400">Based on {fmtNum(tickets)} tickets/mo and a {teamSizeLabel} team in {INDUSTRIES.find((i) => i.id === industry)?.label || 'your industry'}</p>
              </div>

              {/* Recommended Model */}
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
                  <div className="flex flex-wrap gap-2 mb-5">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300"><Brain className="w-3 h-3 text-orange-400" />{Math.round(recommendedModel.aiResolution * 100)}% AI Resolution</span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300"><Users className="w-3 h-3 text-orange-400" />{recommendedModel.agents} AI Agents</span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300"><TicketCheck className="w-3 h-3 text-orange-400" />{recommendedModel.ticketCapacity}</span>
                    {recommendedModel.channels.map((ch) => (<span key={ch} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300">{getChannelIcon(ch)}{ch}</span>))}
                  </div>
                  <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-4">
                    <div className="flex items-center gap-2 mb-3"><Brain className="w-4 h-4 text-orange-400" /><span className="text-sm font-bold text-orange-200">Why this model for {companyName}?</span></div>
                    <ul className="space-y-2">{recommendationReasons.map((reason, i) => (<li key={i} className="flex items-start gap-2.5"><div className="w-5 h-5 rounded-full bg-orange-500/20 flex items-center justify-center flex-shrink-0 mt-0.5"><Check className="w-3 h-3 text-orange-400" /></div><span className="text-sm text-gray-300 leading-relaxed">{reason}</span></li>))}</ul>
                  </div>
                </div>
              </div>

              {/* Savings */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-center"><PiggyBank className="w-5 h-5 text-emerald-400 mx-auto mb-2" /><div className="text-2xl sm:text-3xl font-black text-emerald-400">{fmtMoney(recommendedComparison.annualSavings)}</div><div className="text-xs text-gray-400 mt-1">Annual Savings</div></div>
                <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-4 text-center"><TrendingUp className="w-5 h-5 text-orange-400 mx-auto mb-2" /><div className="text-2xl sm:text-3xl font-black text-orange-400">{recommendedComparison.savingsPercent.toFixed(0)}%</div><div className="text-xs text-gray-400 mt-1">Cost Reduction</div></div>
                <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4 text-center"><Clock className="w-5 h-5 text-blue-400 mx-auto mb-2" /><div className="text-2xl sm:text-3xl font-black text-blue-400">{fmtNum(recommendedComparison.hoursSavedPerMonth)}h</div><div className="text-xs text-gray-400 mt-1">Hours Saved/Month</div></div>
                <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-4 text-center"><Zap className="w-5 h-5 text-purple-400 mx-auto mb-2" /><div className="text-2xl sm:text-3xl font-black text-purple-400">{recommendedComparison.paybackMonths.toFixed(1)}</div><div className="text-xs text-gray-400 mt-1">Month Payback</div></div>
              </div>

              {/* CTA */}
              <div className="text-center pt-4">
                <button onClick={() => navigate('signup')} className="inline-flex items-center gap-2 px-8 py-4 rounded-xl text-sm font-bold bg-gradient-to-r from-orange-500 to-orange-400 text-[#1A1A1A] shadow-lg shadow-orange-500/25 hover:from-orange-400 hover:to-orange-300 hover:shadow-orange-500/40 hover:-translate-y-0.5 transition-all duration-300">
                  Get Started with {recommendedModel.name}
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
              <button onClick={() => navigate('landing')} className="px-6 py-3 rounded-xl text-sm font-semibold bg-white/5 text-zinc-300 border border-white/10 hover:border-white/20 transition-all">Back to Home</button>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
