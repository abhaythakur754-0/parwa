'use client';

import React, { useState, Suspense } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Loader2,
  ArrowLeft,
  Bot,
  Zap,
  ShieldCheck,
  Check,
  Star,
  ArrowRight,
  Sparkles,
  Info,
  XCircle,
  CalendarClock,
  CreditCard,
  X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { AntiArbitrageMatrix } from '@/components/pricing';
import NavigationBar from '@/components/landing/NavigationBar';
import Footer from '@/components/landing/Footer';

// ──────────────────────────────────────────────────────────────────
// PLAN DATA — CORRECT from PARWA docs
// ──────────────────────────────────────────────────────────────────

interface PlanTier {
  id: string;
  name: string;
  tagline: string;
  monthlyPrice: number;
  annualPrice: number;
  features: string[];
  recommended?: boolean;
  cta: string;
}

const PLAN_TIERS: PlanTier[] = [
  {
    id: 'parwa-starter',
    name: 'PARWA Starter',
    tagline: 'Get started with AI-powered support automation',
    monthlyPrice: 999,
    annualPrice: 799,
    features: [
      'Up to 3 AI agents',
      '1,000 tickets/month',
      'Email & Chat channels',
      'FAQ handling from knowledge base',
      'Order status & tracking automation',
    ],
    cta: 'Get Started',
  },
  {
    id: 'parwa-growth',
    name: 'PARWA Growth',
    tagline: 'AI that thinks, routes, and learns with your team',
    monthlyPrice: 2499,
    annualPrice: 1999,
    recommended: true,
    features: [
      'Up to 8 AI agents',
      '5,000 tickets/month',
      'Email, Chat, SMS & Voice channels',
      'AI decision recommendations (Approve/Review/Deny)',
      'Smart Router — 3-tier LLM routing',
      'Agent Lightning — continuous learning from corrections',
      'Batch approval system with semantic clustering',
      'Advanced analytics & ROI tracking',
    ],
    cta: 'Get Started',
  },
  {
    id: 'parwa-high',
    name: 'PARWA High',
    tagline: 'Full autonomous operations with enterprise-grade intelligence',
    monthlyPrice: 3999,
    annualPrice: 3199,
    features: [
      'Up to 15 AI agents',
      '15,000 tickets/month',
      'All channels including Social Media',
      'Quality coaching system',
      'Churn prediction & proactive retention',
      'Video support & screen sharing',
      'Up to 5 concurrent voice calls',
      'Strategic insights & revenue impact analytics',
      'Custom integrations & API access',
      'Peer review (Junior asks Senior before escalation)',
      'Priority support from PARWA team',
      'Full autonomous operations with approval flows',
    ],
    cta: 'Get Started',
  },
];

// ──────────────────────────────────────────────────────────────────
// CANCELLATION POLICY
// ──────────────────────────────────────────────────────────────────

const cancellationPoints = [
  { icon: CalendarClock, text: 'Cancel anytime — no long-term contracts' },
  { icon: CreditCard, text: 'No refunds once paid' },
  { icon: Info, text: 'Access continues until the end of your billing month' },
  { icon: XCircle, text: 'No free trials — start with confidence from day one' },
  { icon: X, text: 'Payment failure stops service immediately' },
];

// ──────────────────────────────────────────────────────────────────
// TRUST INDICATORS
// ──────────────────────────────────────────────────────────────────

const trustIndicators = [
  { icon: Bot, label: 'AI-Powered' },
  { icon: Zap, label: 'Instant Setup' },
  { icon: ShieldCheck, label: 'Enterprise Ready' },
  { icon: Sparkles, label: 'Continuous Learning' },
];

// ──────────────────────────────────────────────────────────────────
// LOADING STATE
// ──────────────────────────────────────────────────────────────────

function PricingPageLoading() {
  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{
        background:
          'linear-gradient(180deg, #022C22 0%, #064E3B 50%, #022C22 100%)',
      }}
    >
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
        <span className="text-sm text-emerald-200/50">Loading pricing...</span>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// ANNUAL TOGGLE
// ──────────────────────────────────────────────────────────────────

function AnnualToggle({
  isAnnual,
  onToggle,
}: {
  isAnnual: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="inline-flex items-center gap-3 px-5 py-2.5 rounded-full bg-white/5 border border-white/10 backdrop-blur-sm">
      <span
        className={`text-sm font-medium transition-colors duration-300 ${
          !isAnnual ? 'text-white' : 'text-emerald-200/40'
        }`}
      >
        Monthly
      </span>
      <button
        onClick={onToggle}
        className="relative w-12 h-7 rounded-full transition-colors duration-300 focus:outline-none focus-visible-ring"
        style={{
          background: isAnnual
            ? 'linear-gradient(to right, #10b981, #34d399)'
            : 'rgba(255,255,255,0.15)',
        }}
        aria-label="Toggle annual billing"
        role="switch"
        aria-checked={isAnnual}
      >
        <div
          className={`absolute top-0.5 left-0.5 w-6 h-6 rounded-full bg-white shadow-md transition-transform duration-300 ${
            isAnnual ? 'translate-x-5' : 'translate-x-0'
          }`}
        />
      </button>
      <span
        className={`text-sm font-medium transition-colors duration-300 ${
          isAnnual ? 'text-white' : 'text-emerald-200/40'
        }`}
      >
        Annual
      </span>
      {isAnnual && (
        <span className="ml-1 px-2.5 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-xs font-bold text-emerald-400">
          Save 20%
        </span>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// PRICING CARD
// ──────────────────────────────────────────────────────────────────

function PricingCard({
  plan,
  isAnnual,
  isSelected,
  onSelect,
}: {
  plan: PlanTier;
  isAnnual: boolean;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const price = isAnnual ? plan.annualPrice : plan.monthlyPrice;
  const annualSavings = plan.monthlyPrice - plan.annualPrice;

  return (
    <div
      onClick={onSelect}
      className={`
        relative rounded-2xl border-2 p-6 sm:p-8 cursor-pointer
        transition-all duration-500 backdrop-blur-sm
        ${
          isSelected
            ? 'border-emerald-400 bg-emerald-500/10 shadow-xl shadow-emerald-500/10 scale-[1.02] md:scale-105'
            : plan.recommended
              ? 'border-emerald-500/15 bg-white/[0.05] hover:border-emerald-500/30 hover:shadow-lg hover:shadow-emerald-500/5'
              : 'border-white/10 bg-white/[0.05] hover:border-white/20 hover:shadow-lg'
        }
      `}
    >
      {/* Recommended Badge */}
      {plan.recommended && (
        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
          <span className="inline-flex items-center gap-1 px-4 py-1.5 text-xs font-bold bg-gradient-to-r from-amber-400 to-yellow-400 text-gray-900 rounded-full shadow-lg shadow-amber-400/30">
            <Star className="w-3 h-3" fill="currentColor" />
            Recommended
          </span>
        </div>
      )}

      {/* Plan Name */}
      <div className="mb-6 mt-1">
        <h3 className="text-2xl sm:text-3xl font-extrabold text-white mb-2 tracking-tight">
          {plan.name}
        </h3>
        <p className="text-sm text-emerald-200/50 leading-relaxed">
          {plan.tagline}
        </p>
      </div>

      {/* Price */}
      <div className="mb-6 pb-6 border-b border-white/10">
        <div className="flex items-baseline gap-1">
          <span
            className={`text-4xl sm:text-5xl font-black ${
              isSelected ? 'text-emerald-400' : 'text-white'
            }`}
          >
            ${price.toLocaleString()}
          </span>
          <span className="text-sm text-emerald-200/30 font-medium">/month</span>
        </div>
        {isAnnual && (
          <p className="text-xs text-emerald-400 mt-1.5">
            Billed annually — save ${annualSavings}/mo
          </p>
        )}
      </div>

      {/* Features */}
      <ul className="space-y-3 mb-8">
        {plan.features.map((feature, i) => (
          <li key={i} className="flex items-start gap-3">
            <div
              className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
                isSelected ? 'bg-emerald-500/20' : 'bg-white/10'
              }`}
            >
              <Check
                className={`w-3 h-3 ${
                  isSelected ? 'text-emerald-400' : 'text-emerald-200/30'
                }`}
                strokeWidth={3}
              />
            </div>
            <span
              className={`text-sm leading-snug ${
                isSelected ? 'text-gray-100' : 'text-emerald-200/50'
              }`}
            >
              {feature}
            </span>
          </li>
        ))}
      </ul>

      {/* CTA Button */}
      <Link
        href="/signup"
        onClick={(e) => e.stopPropagation()}
        className={`
          w-full py-3.5 rounded-xl text-sm font-bold transition-all duration-500
          flex items-center justify-center gap-2 no-underline
          ${
            isSelected
              ? 'bg-gradient-to-r from-emerald-500 to-emerald-400 text-[#022C22] shadow-lg shadow-emerald-500/30'
              : plan.recommended
                ? 'bg-gradient-to-r from-emerald-500 to-emerald-400 text-[#022C22] hover:from-emerald-400 hover:to-emerald-300 shadow-lg shadow-emerald-500/20'
                : 'bg-white/10 text-white hover:bg-white/15 border border-white/10'
          }
        `}
      >
        {plan.cta}
        <ArrowRight className="w-4 h-4" />
      </Link>

      {/* Selected indicator */}
      {isSelected && (
        <div className="absolute top-4 right-4 w-6 h-6 rounded-full bg-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/30">
          <Check className="w-3.5 h-3.5 text-white" strokeWidth={3} />
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// MAIN CONTENT
// ──────────────────────────────────────────────────────────────────

function PricingContent() {
  const router = useRouter();
  const [isAnnual, setIsAnnual] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(
    'parwa-growth'
  );
  const handlePlanSelect = (planId: string) => {
    setSelectedPlanId(planId);
    toast.success(`${PLAN_TIERS.find((p) => p.id === planId)?.name} selected!`, {
      icon: '✨',
      style: {
        background: '#064E3B',
        color: '#d1fae5',
        border: '1px solid rgba(16,185,129,0.25)',
        borderRadius: '12px',
      },
    });
  };

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{
        background:
          'linear-gradient(180deg, #022C22 0%, #064E3B 50%, #022C22 100%)',
      }}
    >
      <NavigationBar onOpenJarvis={() => router.push('/jarvis')} />
      <main className="flex-grow">
        {/* ── Hero Header ── */}
        <section className="relative pt-12 sm:pt-16 pb-8 sm:pb-12 px-4 sm:px-6 lg:px-8">
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-emerald-500/10 blur-[120px] rounded-full" />
          </div>
          <div className="relative max-w-4xl mx-auto text-center">
            <Link
              href="/"
              className="inline-flex items-center gap-2 text-emerald-200/40 hover:text-emerald-200/60 mb-8 transition-colors text-sm"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to Home
            </Link>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white mb-4 leading-tight">
              Simple, Transparent{' '}
              <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
                Pricing
              </span>
            </h1>
            <p className="text-base sm:text-lg text-emerald-200/50 max-w-2xl mx-auto mb-8 leading-relaxed">
              No hidden fees. No per-seat charges. Choose the tier that matches
              your ticket volume and let AI handle the rest.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3 sm:gap-4">
              {trustIndicators.map((item) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.label}
                    className="flex items-center gap-2 px-3 sm:px-4 py-2 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-100/70"
                  >
                    <Icon className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-xs sm:text-sm font-medium">
                      {item.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════════
            SECTION 1: ANNUAL TOGGLE + 3 PRICING CARDS
            ══════════════════════════════════════════════════════════ */}
        <section className="px-4 sm:px-6 lg:px-8 pb-16 sm:pb-24">
          <div className="max-w-6xl mx-auto">
            {/* Annual Toggle */}
            <div className="flex justify-center mb-8 sm:mb-10">
              <AnnualToggle
                isAnnual={isAnnual}
                onToggle={() => setIsAnnual(!isAnnual)}
              />
            </div>

            <div className="text-center mb-8 sm:mb-10">
              <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-white mb-2">
                Choose Your{' '}
                <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
                  PARWA Plan
                </span>
              </h2>
              <p className="text-sm sm:text-base text-emerald-200/50">
                Scale from FAQ deflection to full autonomous operations
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6 lg:gap-8">
              {PLAN_TIERS.map((plan) => (
                <PricingCard
                  key={plan.id}
                  plan={plan}
                  isAnnual={isAnnual}
                  isSelected={selectedPlanId === plan.id}
                  onSelect={() => handlePlanSelect(plan.id)}
                />
              ))}
            </div>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════════
            SECTION 3: ANTI-ARBITRAGE MATRIX
            ══════════════════════════════════════════════════════════ */}
        <section className="px-4 sm:px-6 lg:px-8 pb-16 sm:pb-24">
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-8 sm:mb-10">
              <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-white mb-2">
                The Real{' '}
                <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
                  Cost Comparison
                </span>
              </h2>
              <p className="text-sm sm:text-base text-emerald-200/50 max-w-xl mx-auto">
                Why buying two Starters costs more than you think — and why
                Growth is the smarter choice.
              </p>
            </div>

            <AntiArbitrageMatrix />
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════════
            SECTION 4: CANCELLATION POLICY (Netflix Style)
            ══════════════════════════════════════════════════════════ */}
        <section className="px-4 sm:px-6 lg:px-8 pb-16 sm:pb-24">
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-8 sm:mb-10">
              <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-white mb-2">
                Cancellation{' '}
                <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
                  Policy
                </span>
              </h2>
              <p className="text-sm sm:text-base text-emerald-200/50 max-w-xl mx-auto">
                Simple, fair, and transparent — just like our pricing.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {cancellationPoints.map((point) => {
                const Icon = point.icon;
                return (
                  <div
                    key={point.text}
                    className="flex items-start gap-3 p-4 rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm hover:border-emerald-500/20 transition-all duration-300"
                  >
                    <div className="w-9 h-9 rounded-lg bg-emerald-500/10 flex items-center justify-center flex-shrink-0">
                      <Icon className="w-4.5 h-4.5 text-emerald-400" />
                    </div>
                    <p className="text-sm text-emerald-200/50 leading-relaxed">
                      {point.text}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════════
            FINAL CTA
            ══════════════════════════════════════════════════════════ */}
        <section className="px-4 sm:px-6 lg:px-8 pb-16 sm:pb-24">
          <div className="max-w-3xl mx-auto text-center">
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 backdrop-blur-xl p-8 sm:p-12">
              <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
                Ready to automate your support?
              </h2>
              <p className="text-sm sm:text-base text-emerald-200/50 mb-8 max-w-lg mx-auto leading-relaxed">
                Join thousands of businesses using PARWA to handle tickets
                faster, learn continuously, and scale effortlessly.
              </p>
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 px-8 py-4 rounded-xl text-base font-bold bg-gradient-to-r from-emerald-500 to-emerald-400 text-[#022C22] shadow-lg shadow-emerald-500/30 hover:from-emerald-400 hover:to-emerald-300 hover:shadow-emerald-500/50 hover:-translate-y-0.5 transition-all duration-500 no-underline"
              >
                Get Started Now
                <ArrowRight className="w-5 h-5" />
              </Link>
              <p className="text-xs text-emerald-200/30 mt-4">
                No credit card required to explore. Full setup in under 5
                minutes.
              </p>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────
// PAGE EXPORT
// ──────────────────────────────────────────────────────────────────

export default function PricingPage() {
  return (
    <Suspense fallback={<PricingPageLoading />}>
      <PricingContent />
    </Suspense>
  );
}
