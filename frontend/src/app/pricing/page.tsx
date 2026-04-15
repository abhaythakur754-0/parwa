'use client';

import { useState } from 'react';
import { NavigationBar, Footer } from '@/components/landing';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import {
  Check,
  X,
  Zap,
  Rocket,
  Crown,
  ArrowRight,
  Sparkles,
} from 'lucide-react';

// ── Pricing Tier Data ───────────────────────────────────────────────

interface PricingFeature {
  name: string;
  starter: boolean | string;
  growth: boolean | string;
  high: boolean | string;
}

interface PricingTier {
  id: string;
  name: string;
  icon: React.ReactNode;
  monthlyPrice: number;
  description: string;
  highlight?: boolean;
  cta: string;
  ctaLink: string;
  badge?: string;
  features: string[];
}

const tiers: PricingTier[] = [
  {
    id: 'starter',
    name: 'Starter',
    icon: <Zap className="w-6 h-6" />,
    monthlyPrice: 999,
    description: 'Perfect for small teams getting started with AI support.',
    cta: 'Get Started',
    ctaLink: '/signup',
    features: [
      '1,000 tickets per month',
      '3 AI Agents',
      'Basic RAG (Knowledge Base)',
      'Email Support',
      'Standard Response Time',
      'Basic Analytics Dashboard',
      '5 Knowledge Base Documents',
      'Email Channel',
      'Web Chat Widget',
    ],
  },
  {
    id: 'growth',
    name: 'Growth',
    icon: <Rocket className="w-6 h-6" />,
    monthlyPrice: 2499,
    description:
      'For scaling teams that need advanced AI capabilities.',
    highlight: true,
    badge: 'Most Popular',
    cta: 'Get Started',
    ctaLink: '/signup',
    features: [
      '5,000 tickets per month',
      '8 AI Agents',
      'Advanced RAG + All Techniques',
      'Priority Support',
      'Faster Response Time',
      'Advanced Analytics & Reports',
      'Unlimited Knowledge Base Docs',
      'All 11 Communication Channels',
      'Custom Brand Voice',
      'SLA Management',
      'API Access',
      'Webhooks & Integrations',
    ],
  },
  {
    id: 'high',
    name: 'PARWA High',
    icon: <Crown className="w-6 h-6" />,
    monthlyPrice: 3999,
    description:
      'Full AI pipeline with unlimited scale and dedicated support.',
    cta: 'Contact Sales',
    ctaLink: '/contact',
    features: [
      '15,000 tickets per month',
      '15 AI Agents',
      'Full AI Pipeline (All Techniques)',
      'Dedicated Support Manager',
      'Fastest Response Time',
      'Enterprise Analytics Suite',
      'Unlimited Knowledge Base Docs',
      'All 11 Communication Channels',
      'Custom Brand Voice + Training',
      'SLA Management + Escalation',
      'Full API Access + Webhooks',
      'Custom Integrations',
      'SSO & Advanced Security',
      'Multi-Team Support',
    ],
  },
];

// Feature comparison matrix
const comparisonFeatures: PricingFeature[] = [
  { name: 'Tickets / Month', starter: '1,000', growth: '5,000', high: '15,000' },
  { name: 'AI Agents', starter: '3', growth: '8', high: '15' },
  { name: 'RAG (Knowledge Base)', starter: 'Basic', growth: 'Advanced + All Techniques', high: 'Full AI Pipeline' },
  { name: 'Communication Channels', starter: '2 (Email, Chat)', growth: 'All 11 Channels', high: 'All 11 + Custom' },
  { name: 'Knowledge Base Documents', starter: '5', growth: 'Unlimited', high: 'Unlimited' },
  { name: 'Custom Brand Voice', starter: false, growth: true, high: true },
  { name: 'AI Training & Fine-tuning', starter: false, growth: false, high: true },
  { name: 'SLA Management', starter: false, growth: true, high: true },
  { name: 'Advanced Analytics', starter: false, growth: true, high: 'Enterprise Suite' },
  { name: 'API Access', starter: false, growth: true, high: 'Full Access' },
  { name: 'Webhooks & Integrations', starter: false, growth: true, high: 'Custom Integrations' },
  { name: 'SSO & Security', starter: false, growth: false, high: true },
  { name: 'Multi-Team Support', starter: false, growth: false, high: true },
  { name: 'Support Level', starter: 'Email', growth: 'Priority', high: 'Dedicated Manager' },
  { name: 'Response SLA', starter: '24h', growth: '4h', high: '1h' },
];

// ── Component ───────────────────────────────────────────────────────

function AnimatedPrice({
  monthly,
  isAnnual,
}: {
  monthly: number;
  isAnnual: boolean;
}) {
  const annual = Math.round(monthly * 0.8 * 12);
  const annualMonthly = Math.round(monthly * 0.8);
  const displayPrice = isAnnual ? annualMonthly : monthly;

  return (
    <div className="flex items-baseline gap-1">
      <span className="text-lg text-gray-400 font-medium">$</span>
      <span className="text-5xl font-extrabold text-white tracking-tight tabular-nums">
        {displayPrice.toLocaleString()}
      </span>
      <span className="text-gray-400 font-medium">/mo</span>
    </div>
  );
}

function FeatureCheck({
  value,
}: {
  value: boolean | string;
}) {
  if (typeof value === 'string') {
    return <span className="text-white font-medium text-sm">{value}</span>;
  }
  if (value) {
    return (
      <div className="flex justify-center">
        <div className="w-6 h-6 rounded-full bg-[#FF7F11]/15 flex items-center justify-center">
          <Check className="w-3.5 h-3.5 text-[#FF7F11]" />
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-center">
      <div className="w-6 h-6 rounded-full bg-white/5 flex items-center justify-center">
        <X className="w-3.5 h-3.5 text-gray-600" />
      </div>
    </div>
  );
}

function PricingCard({
  tier,
  isAnnual,
}: {
  tier: PricingTier;
  isAnnual: boolean;
}) {
  return (
    <Card
      className={cn(
        'relative flex flex-col bg-[#1A1A1A] border border-white/[0.08] rounded-2xl overflow-hidden transition-all duration-500 hover:border-white/[0.15] hover:shadow-2xl hover:shadow-black/40',
        tier.highlight && 'border-[#FF7F11]/40 shadow-xl shadow-[#FF7F11]/5 scale-[1.02] lg:scale-105',
      )}
    >
      {/* Badge */}
      {tier.badge && (
        <div className="absolute top-0 left-0 right-0">
          <div className="bg-gradient-to-r from-[#FF7F11] to-orange-500 text-white text-xs font-bold uppercase tracking-wider text-center py-2">
            {tier.badge}
          </div>
        </div>
      )}

      {/* Glow effect for highlighted tier */}
      {tier.highlight && (
        <div className="absolute -inset-px bg-gradient-to-b from-[#FF7F11]/20 via-transparent to-[#FF7F11]/10 rounded-2xl pointer-events-none" />
      )}

      <CardHeader className={cn('p-6 pb-2', tier.badge && 'pt-12')}>
        {/* Icon + Name */}
        <div className="flex items-center gap-3 mb-3">
          <div
            className={cn(
              'w-10 h-10 rounded-xl flex items-center justify-center transition-colors duration-300',
              tier.highlight
                ? 'bg-[#FF7F11]/15 text-[#FF7F11]'
                : 'bg-white/[0.06] text-gray-400',
            )}
          >
            {tier.icon}
          </div>
          <h3 className="text-xl font-bold text-white">{tier.name}</h3>
        </div>

        {/* Description */}
        <p className="text-gray-400 text-sm leading-relaxed mb-4">
          {tier.description}
        </p>

        {/* Price */}
        <AnimatedPrice monthly={tier.monthlyPrice} isAnnual={isAnnual} />

        {isAnnual && (
          <p className="text-[#FF7F11] text-xs font-medium mt-2 flex items-center gap-1">
            <Sparkles className="w-3 h-3" />
            Save ${(tier.monthlyPrice * 0.2).toFixed(0)}/month with annual billing
          </p>
        )}
      </CardHeader>

      {/* CTA Button */}
      <div className="px-6 pt-4 pb-2">
        <Link href={tier.ctaLink}>
          <Button
            className={cn(
              'w-full rounded-xl font-semibold text-sm transition-all duration-300 py-3',
              tier.highlight
                ? 'bg-gradient-to-r from-[#FF7F11] to-orange-500 hover:from-orange-500 hover:to-orange-400 text-white shadow-lg shadow-[#FF7F11]/25 hover:shadow-[#FF7F11]/40'
                : 'bg-white/[0.08] hover:bg-white/[0.14] text-white border border-white/[0.1]',
            )}
          >
            {tier.cta}
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </Link>
      </div>

      {/* Features */}
      <CardContent className="flex-1 p-6 pt-4">
        <p className="text-xs uppercase tracking-wider text-gray-500 font-semibold mb-3">
          What&apos;s included
        </p>
        <ul className="space-y-2.5">
          {tier.features.map((feature) => (
            <li
              key={feature}
              className="flex items-start gap-2.5 text-sm text-gray-300"
            >
              <Check className="w-4 h-4 text-[#FF7F11] mt-0.5 shrink-0" />
              <span>{feature}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export default function PricingPage() {
  const [isAnnual, setIsAnnual] = useState(false);
  const [showComparison, setShowComparison] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-[#0D0D0D]">
      <NavigationBar />

      <main className="flex-grow">
        {/* Hero */}
        <section className="relative pt-20 pb-16 sm:pt-28 sm:pb-20 overflow-hidden">
          {/* Background glow */}
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[600px] bg-[#FF7F11]/[0.04] rounded-full blur-[120px]" />
          </div>

          <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <Badge
              variant="outline"
              className="mb-6 bg-[#FF7F11]/10 text-[#FF7F11] border-[#FF7F11]/25 text-xs font-semibold px-4 py-1.5 rounded-full"
            >
              Simple, Transparent Pricing
            </Badge>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white mb-5 tracking-tight">
              Choose Your{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#FF7F11] to-orange-400">
                AI Workforce
              </span>
            </h1>

            <p className="text-gray-400 text-lg sm:text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
              Deploy intelligent AI agents that handle customer support
              24/7. Start small, scale as you grow.
            </p>

            {/* Billing Toggle */}
            <div className="flex items-center justify-center gap-4 mb-4">
              <span
                className={cn(
                  'text-sm font-medium transition-colors duration-300',
                  !isAnnual ? 'text-white' : 'text-gray-500',
                )}
              >
                Monthly
              </span>

              <button
                onClick={() => setIsAnnual(!isAnnual)}
                className="relative focus-visible-ring rounded-full"
                aria-label="Toggle annual billing"
                role="switch"
                aria-checked={isAnnual}
              >
                <div className="w-14 h-8 rounded-full bg-white/[0.1] border border-white/[0.15] p-1 transition-colors duration-300 hover:bg-white/[0.15]">
                  <div
                    className={cn(
                      'w-6 h-6 rounded-full transition-all duration-300 shadow-lg',
                      isAnnual
                        ? 'bg-[#FF7F11] translate-x-6 shadow-[#FF7F11]/40'
                        : 'bg-gray-400 translate-x-0',
                    )}
                  />
                </div>
              </button>

              <span
                className={cn(
                  'text-sm font-medium transition-colors duration-300 flex items-center gap-2',
                  isAnnual ? 'text-white' : 'text-gray-500',
                )}
              >
                Annual
                <Badge className="bg-[#FF7F11]/15 text-[#FF7F11] border-[#FF7F11]/25 text-[10px] font-bold px-2 py-0.5 rounded-full">
                  -20%
                </Badge>
              </span>
            </div>

            {isAnnual && (
              <p className="text-gray-500 text-xs">
                Billed annually. Cancel anytime.
              </p>
            )}
          </div>
        </section>

        {/* Pricing Cards */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-20">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8 items-start">
            {tiers.map((tier) => (
              <PricingCard
                key={tier.id}
                tier={tier}
                isAnnual={isAnnual}
              />
            ))}
          </div>
        </section>

        {/* Feature Comparison */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-24">
          <div className="text-center mb-10">
            <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
              Feature{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#FF7F11] to-orange-400">
                Comparison
              </span>
            </h2>
            <p className="text-gray-400 text-lg">
              See exactly what you get with each plan
            </p>
          </div>

          {/* Mobile: Toggle comparison table */}
          <div className="block lg:hidden mb-6">
            <Button
              variant="outline"
              onClick={() => setShowComparison(!showComparison)}
              className="w-full bg-[#1A1A1A] border-white/[0.1] text-gray-300 hover:text-white hover:bg-[#1A1A1A]/80 rounded-xl py-3"
            >
              {showComparison ? 'Hide' : 'Show'} Feature Comparison
            </Button>
          </div>

          <div
            className={cn(
              'rounded-2xl border border-white/[0.08] bg-[#1A1A1A] overflow-hidden',
              'lg:block',
              showComparison ? 'block' : 'hidden',
            )}
          >
            {/* Table Header */}
            <div className="grid grid-cols-4 gap-0 bg-white/[0.03] border-b border-white/[0.08]">
              <div className="p-4 sm:p-5">
                <span className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
                  Feature
                </span>
              </div>
              <div className="p-4 sm:p-5 text-center">
                <span className="text-sm font-semibold text-gray-300">
                  Starter
                </span>
              </div>
              <div className="p-4 sm:p-5 text-center bg-[#FF7F11]/[0.04]">
                <span className="text-sm font-semibold text-[#FF7F11]">
                  Growth
                </span>
              </div>
              <div className="p-4 sm:p-5 text-center">
                <span className="text-sm font-semibold text-gray-300">
                  PARWA High
                </span>
              </div>
            </div>

            {/* Table Rows */}
            {comparisonFeatures.map((feature, index) => (
              <div
                key={feature.name}
                className={cn(
                  'grid grid-cols-4 gap-0 border-b border-white/[0.04] last:border-0 transition-colors duration-200 hover:bg-white/[0.02]',
                  index % 2 === 0 && 'bg-white/[0.01]',
                )}
              >
                <div className="p-4 sm:p-5">
                  <span className="text-sm text-gray-300">
                    {feature.name}
                  </span>
                </div>
                <div className="p-4 sm:p-5 flex items-center justify-center">
                  <FeatureCheck value={feature.starter} />
                </div>
                <div
                  className="p-4 sm:p-5 flex items-center justify-center bg-[#FF7F11]/[0.02]"
                >
                  <FeatureCheck value={feature.growth} />
                </div>
                <div className="p-4 sm:p-5 flex items-center justify-center">
                  <FeatureCheck value={feature.high} />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Trust Section */}
        <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-24 text-center">
          <div className="bg-[#1A1A1A] rounded-2xl border border-white/[0.08] p-8 sm:p-12">
            <h3 className="text-2xl sm:text-3xl font-bold text-white mb-4">
              Trusted by 2,400+ Businesses
            </h3>
            <p className="text-gray-400 text-lg mb-8 max-w-xl mx-auto">
              Join the companies that have reduced support costs by 60%
              while improving response times by 10x.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/signup">
                <Button className="bg-gradient-to-r from-[#FF7F11] to-orange-500 hover:from-orange-500 hover:to-orange-400 text-white font-semibold px-8 py-3 rounded-xl shadow-lg shadow-[#FF7F11]/25 hover:shadow-[#FF7F11]/40 transition-all duration-300">
                  Start Free Trial
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
              <Link href="/jarvis">
                <Button
                  variant="outline"
                  className="bg-white/[0.06] border-white/[0.1] text-gray-300 hover:text-white hover:bg-white/[0.1] font-semibold px-8 py-3 rounded-xl transition-all duration-300"
                >
                  Try Jarvis Demo
                </Button>
              </Link>
            </div>
          </div>
        </section>

        {/* FAQ Section */}
        <section className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pb-24">
          <h2 className="text-3xl font-bold text-white text-center mb-10">
            Frequently Asked Questions
          </h2>
          <div className="space-y-4">
            {[
              {
                q: 'Can I switch plans at any time?',
                a: 'Yes! You can upgrade or downgrade your plan at any time. When upgrading, you\'ll be prorated for the remainder of your billing cycle. When downgrading, the change takes effect at the start of your next billing period.',
              },
              {
                q: 'What happens if I exceed my ticket limit?',
                a: 'You\'ll receive a notification when you reach 80% of your limit. If you exceed it, additional tickets are billed at a per-ticket rate. You can upgrade your plan at any time to increase your limit.',
              },
              {
                q: 'How does the free trial work?',
                a: 'Start with a 14-day free trial of the Growth plan. No credit card required. You\'ll have access to all Growth features. At the end of the trial, choose the plan that works best for you.',
              },
              {
                q: 'What is the AI pipeline?',
                a: 'The AI pipeline includes advanced techniques like Chain of Thought, Tree of Thoughts, RAG retrieval with re-ranking, sentiment analysis, and multi-variant AI models working together to deliver the most accurate and contextual responses.',
              },
              {
                q: 'Do you offer custom enterprise plans?',
                a: 'Absolutely! Our Enterprise plan can be customized to your specific needs, including custom integrations, dedicated infrastructure, SLA guarantees, and volume pricing. Contact our sales team to discuss.',
              },
            ].map((faq) => (
              <div
                key={faq.q}
                className="bg-[#1A1A1A] rounded-xl border border-white/[0.08] p-6"
              >
                <h4 className="text-white font-semibold mb-2">{faq.q}</h4>
                <p className="text-gray-400 text-sm leading-relaxed">
                  {faq.a}
                </p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
