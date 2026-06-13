'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { NavigationBar, Footer } from '@/components/landing';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Sparkles,
  ArrowRight,
  Zap,
  Shield,
  Clock,
  Crown,
  CheckCircle2,
} from 'lucide-react';
import {
  VARIANT_PRICES,
  VARIANT_DISPLAY_NAMES,
  VARIANT_TAGLINES,
  VARIANT_LIMITS,
  VARIANT_AI_INFO,
  type VariantTier,
} from '@/lib/pricing-config';
import type { ParwaIndustry } from '@/lib/integration-catalog';

// ── Variant Plan Data (from pricing-config.ts SSOT) ────────────────────

interface PlanData {
  tier: VariantTier;
  onboardingVariant: string;
  name: string;
  price: number;
  priceLabel: string;
  tagline: string;
  icon: React.ElementType;
  iconColor: string;
  borderColor: string;
  bgAccent: string;
  features: string[];
  highlighted?: boolean;
}

const PLANS: PlanData[] = [
  {
    tier: 'starter',
    onboardingVariant: 'mini_parwa',
    name: VARIANT_DISPLAY_NAMES.starter,
    price: VARIANT_PRICES.starter,
    priceLabel: `$${VARIANT_PRICES.starter.toLocaleString()}`,
    tagline: VARIANT_TAGLINES.starter,
    icon: Zap,
    iconColor: 'text-amber-400',
    borderColor: 'border-amber-500/30',
    bgAccent: 'rgba(245,158,11,0.04)',
    features: [
      `${VARIANT_LIMITS.starter.monthlyTickets.toLocaleString()} tickets/mo`,
      `${VARIANT_AI_INFO.starter.pipelineSteps}-step AI pipeline`,
      `${VARIANT_AI_INFO.starter.concurrentCalls} concurrent AI calls`,
      `${VARIANT_LIMITS.starter.aiAgents} AI agent`,
      `${VARIANT_LIMITS.starter.kbDocs} KB documents`,
      `${VARIANT_LIMITS.starter.teamMembers} team members`,
      `${Math.round(VARIANT_AI_INFO.starter.aiResolution * 100)}% AI resolution rate`,
    ],
  },
  {
    tier: 'growth',
    onboardingVariant: 'parwa',
    name: VARIANT_DISPLAY_NAMES.growth,
    price: VARIANT_PRICES.growth,
    priceLabel: `$${VARIANT_PRICES.growth.toLocaleString()}`,
    tagline: VARIANT_TAGLINES.growth,
    icon: Sparkles,
    iconColor: 'text-orange-400',
    borderColor: 'border-orange-500/40',
    bgAccent: 'rgba(249,115,22,0.06)',
    highlighted: true,
    features: [
      `${VARIANT_LIMITS.growth.monthlyTickets.toLocaleString()} tickets/mo`,
      `${VARIANT_AI_INFO.growth.pipelineSteps}-step AI pipeline`,
      `${VARIANT_AI_INFO.growth.concurrentCalls} concurrent AI calls`,
      `${VARIANT_LIMITS.growth.aiAgents} AI agents`,
      `${VARIANT_LIMITS.growth.kbDocs} KB documents`,
      `${VARIANT_LIMITS.growth.teamMembers} team members`,
      `${Math.round(VARIANT_AI_INFO.growth.aiResolution * 100)}% AI resolution rate`,
      'Voice channel included',
      'Custom API connector included',
    ],
  },
  {
    tier: 'high',
    onboardingVariant: 'parwa_high',
    name: VARIANT_DISPLAY_NAMES.high,
    price: VARIANT_PRICES.high,
    priceLabel: `$${VARIANT_PRICES.high.toLocaleString()}`,
    tagline: VARIANT_TAGLINES.high,
    icon: Crown,
    iconColor: 'text-yellow-400',
    borderColor: 'border-yellow-500/30',
    bgAccent: 'rgba(234,179,8,0.04)',
    features: [
      `${VARIANT_LIMITS.high.monthlyTickets.toLocaleString()} tickets/mo`,
      `${VARIANT_AI_INFO.high.pipelineSteps}-step AI pipeline`,
      `${VARIANT_AI_INFO.high.concurrentCalls} concurrent AI calls`,
      `${VARIANT_LIMITS.high.aiAgents} AI agents`,
      `${VARIANT_LIMITS.high.kbDocs} KB documents`,
      `${VARIANT_LIMITS.high.teamMembers} team members`,
      `${Math.round(VARIANT_AI_INFO.high.aiResolution * 100)}% AI resolution rate`,
      'Voice channel included',
      'Custom API connector included',
      'OpenAPI import',
    ],
  },
];

// ── Trust Badges ───────────────────────────────────────────────────────

const trustBadges = [
  { icon: <Zap className="w-4 h-4" />, label: '10x faster responses' },
  { icon: <Shield className="w-4 h-4" />, label: 'SOC 2 compliant' },
  { icon: <Clock className="w-4 h-4" />, label: '24/7 AI availability' },
];

// ── Page Component ─────────────────────────────────────────────────────

export default function PricingPage() {
  const router = useRouter();
  const [selectedPlan, setSelectedPlan] = useState<PlanData | null>(null);

  const handleSelectPlan = (plan: PlanData) => {
    setSelectedPlan(plan);

    // Store pricing context in localStorage for onboarding to read
    const pricingContext = {
      industry: 'other' as ParwaIndustry,
      variant: plan.onboardingVariant,
      addOns: { voice: false, customApi: false },
      totalMonthly: plan.price,
      timestamp: Date.now(),
    };

    try {
      localStorage.setItem('parwa_pricing_context', JSON.stringify(pricingContext));
    } catch {
      // localStorage unavailable
    }

    // Navigate to onboarding
    router.push(`/onboarding?source=pricing&variant=${plan.onboardingVariant}`);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#0A0A0A]">
      <NavigationBar />

      <main className="flex-grow">
        {/* ── Hero Section ─────────────────────────────────────────── */}
        <section className="relative pt-20 pb-12 sm:pt-28 sm:pb-16 overflow-hidden">
          {/* Background glow */}
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[600px] bg-orange-500/[0.04] rounded-full blur-[150px]" />
            <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-orange-500/20 to-transparent" />
          </div>

          <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <Badge
              variant="outline"
              className="mb-6 bg-orange-500/10 text-orange-400 border-orange-500/25 text-xs font-semibold px-4 py-1.5 rounded-full"
            >
              <Sparkles className="w-3 h-3 mr-1.5" />
              Simple, Transparent Pricing
            </Badge>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white mb-5 tracking-tight">
              Choose Your{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-amber-300">
                AI Agent
              </span>
            </h1>

            <p className="text-gray-400 text-lg sm:text-xl max-w-2xl mx-auto mb-8 leading-relaxed">
              Three plans. Three price points. No hidden fees, no complicated modules.
              Pick the agent that fits your ticket volume and go.
            </p>

            {/* Trust badges */}
            <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6">
              {trustBadges.map((badge) => (
                <div
                  key={badge.label}
                  className="flex items-center gap-2 text-gray-500 text-sm"
                >
                  <span className="text-orange-500/60">{badge.icon}</span>
                  {badge.label}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Pricing Cards ─────────────────────────────────────────── */}
        <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-24">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8 items-stretch">
            {PLANS.map((plan) => {
              const Icon = plan.icon;
              return (
                <div
                  key={plan.tier}
                  className={`relative rounded-2xl border ${plan.borderColor} p-6 sm:p-8 flex flex-col transition-all duration-300 hover:scale-[1.02] hover:shadow-xl hover:shadow-orange-500/5 ${
                    plan.highlighted ? 'ring-2 ring-orange-500/30' : ''
                  }`}
                  style={{ background: plan.bgAccent }}
                >
                  {/* Popular badge */}
                  {plan.highlighted && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                      <span className="px-4 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-gradient-to-r from-orange-500 to-amber-400 text-white shadow-lg shadow-orange-500/25">
                        Most Popular
                      </span>
                    </div>
                  )}

                  {/* Plan icon + name */}
                  <div className="flex items-center gap-3 mb-4">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                      plan.tier === 'starter' ? 'bg-amber-500/10' :
                      plan.tier === 'growth' ? 'bg-orange-500/10' : 'bg-yellow-500/10'
                    }`}>
                      <Icon className={`w-5 h-5 ${plan.iconColor}`} />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-white">{plan.name}</h3>
                      <p className="text-xs text-orange-200/40">{plan.tagline}</p>
                    </div>
                  </div>

                  {/* Price */}
                  <div className="mb-6">
                    <div className="flex items-baseline gap-1">
                      <span className="text-4xl sm:text-5xl font-extrabold text-white">
                        {plan.priceLabel}
                      </span>
                      <span className="text-orange-200/40 text-sm font-medium">/mo</span>
                    </div>
                  </div>

                  {/* Features */}
                  <ul className="space-y-2.5 mb-8 flex-1">
                    {plan.features.map((feature, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <span className="text-sm text-orange-200/60">{feature}</span>
                      </li>
                    ))}
                  </ul>

                  {/* CTA Button */}
                  <Button
                    onClick={() => handleSelectPlan(plan)}
                    className={`w-full py-3 rounded-xl font-semibold text-sm transition-all duration-300 ${
                      plan.highlighted
                        ? 'bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 text-[#1A1A1A] shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40'
                        : 'border border-orange-500/20 text-orange-400 hover:bg-orange-500/10 bg-transparent'
                    }`}
                  >
                    Get {plan.name}
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </div>
              );
            })}
          </div>

          {/* ── Bottom Info ────────────────────────────────────────── */}
          <div className="mt-12 text-center space-y-4">
            <p className="text-gray-500 text-sm">
              All plans include: Unlimited integrations, real-time analytics, audit trail, and 24/7 support.
            </p>
            <p className="text-gray-600 text-xs">
              Overage at $0.10/ticket beyond your plan limit. No contracts. Cancel anytime.
            </p>
          </div>

          {/* ── FAQ-style Note ─────────────────────────────────────── */}
          <div className="mt-8 max-w-2xl mx-auto">
            <div className="rounded-xl border border-white/[0.06] p-6" style={{ background: 'rgba(255,255,255,0.02)' }}>
              <h3 className="text-sm font-semibold text-white mb-3">Need more capacity?</h3>
              <p className="text-xs text-orange-200/40 leading-relaxed">
                You can stack multiple variants during onboarding. For example, add 2x Mini PARWA for 1,000 tickets/mo
                at $1,998/mo, or combine any plans to match your exact needs. Your AI assistant Jarvis will help
                you configure the perfect setup.
              </p>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
