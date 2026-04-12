'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Loader2, ArrowLeft, Sparkles, Users, Bot, Zap, ShieldCheck, Headphones, Check, Star, ArrowRight } from 'lucide-react';
import toast from 'react-hot-toast';
import { IndustrySelector, VariantCard, TotalSummary, type Industry, type PricingVariant } from '@/components/pricing';
import NavigationBar from '@/components/landing/NavigationBar';
import Footer from '@/components/landing/Footer';
import { useAuth } from '@/hooks/useAuth';

// ──────────────────────────────────────────────────────────────────
// THREE MAIN PLAN TIERS — mini parwa, parwa, high parwa
// ──────────────────────────────────────────────────────────────────

interface PlanTier {
  id: string;
  name: string;
  tagline: string;
  price: string;
  priceNote: string;
  features: string[];
  popular?: boolean;
  cta: string;
  accent: string;
}

const PLAN_TIERS: PlanTier[] = [
  {
    id: 'mini-parwa',
    name: 'mini parwa',
    tagline: 'For small businesses getting started with AI support',
    price: '$499',
    priceNote: '/month',
    features: [
      'Up to 2 support variants',
      '2,000 tickets/month',
      'Email support channel',
      'Basic analytics dashboard',
      'Knowledge base upload (50 docs)',
      'Business hours support (9-6)',
      '1 team member seat',
    ],
    cta: 'Start with mini parwa',
    accent: 'emerald',
  },
  {
    id: 'parwa',
    name: 'parwa',
    tagline: 'For growing businesses that need full AI power',
    price: '$999',
    priceNote: '/month',
    popular: true,
    features: [
      'Up to 5 support variants',
      '10,000 tickets/month',
      'All channels (Email, Chat, Phone, Social)',
      'Advanced analytics + ROI tracking',
      'Knowledge base upload (500 docs)',
      '24/7/365 AI-powered support',
      'Multi-language support (50+ languages)',
      '5 team member seats',
      'Priority support from PARWA team',
    ],
    cta: 'Start with parwa',
    accent: 'emerald',
  },
  {
    id: 'high-parwa',
    name: 'high parwa',
    tagline: 'For large enterprises with complex support needs',
    price: 'Custom',
    priceNote: 'pricing',
    features: [
      'Unlimited support variants',
      'Unlimited tickets/month',
      'All channels + custom integrations',
      'Enterprise analytics + custom reports',
      'Unlimited knowledge base docs',
      '24/7/365 dedicated AI cluster',
      'Multi-language + custom AI training',
      'Unlimited team member seats',
      'Dedicated success manager',
      '99.99% uptime SLA guarantee',
      'Custom API access + webhooks',
      'On-premise deployment option',
    ],
    cta: 'Contact Sales',
    accent: 'emerald',
  },
];

// ──────────────────────────────────────────────────────────────────
// INDUSTRY-SPECIFIC VARIANTS (shown AFTER plan selection)
// ──────────────────────────────────────────────────────────────────

const INDUSTRY_VARIANTS: Record<Industry, PricingVariant[]> = {
  ecommerce: [
    { id: 'ecom-order', name: 'Order Management', description: 'Order status, tracking, modifications', ticketsPerMonth: 500, pricePerMonth: 99, features: ['Order status inquiries', 'Tracking updates', 'Order modifications', 'Cancellation handling'], popular: true },
    { id: 'ecom-returns', name: 'Returns & Refunds', description: 'Return requests, refund processing', ticketsPerMonth: 200, pricePerMonth: 49, features: ['Return authorization', 'Refund processing', 'Exchange handling', 'Store credit issuance'] },
    { id: 'ecom-product', name: 'Product FAQ', description: 'Product questions, specifications', ticketsPerMonth: 1000, pricePerMonth: 79, features: ['Product inquiries', 'Specification questions', 'Availability checks', 'Recommendations'] },
    { id: 'ecom-shipping', name: 'Shipping Inquiries', description: 'Delivery status, shipping options', ticketsPerMonth: 300, pricePerMonth: 59, features: ['Shipping status', 'Delivery estimates', 'Carrier coordination', 'Address changes'] },
    { id: 'ecom-payment', name: 'Payment Issues', description: 'Failed payments, billing questions', ticketsPerMonth: 150, pricePerMonth: 39, features: ['Payment failures', 'Billing inquiries', 'Invoice requests', 'Promo code issues'] },
  ],
  saas: [
    { id: 'saas-tech', name: 'Technical Support', description: 'Bug reports, troubleshooting', ticketsPerMonth: 400, pricePerMonth: 129, features: ['Bug triage', 'Troubleshooting guides', 'Known issues response', 'Escalation routing'], popular: true },
    { id: 'saas-billing', name: 'Billing Support', description: 'Subscription, invoice questions', ticketsPerMonth: 200, pricePerMonth: 69, features: ['Subscription changes', 'Invoice inquiries', 'Refund requests', 'Plan comparisons'] },
    { id: 'saas-feature', name: 'Feature Requests', description: 'Feature questions, roadmap', ticketsPerMonth: 300, pricePerMonth: 89, features: ['Feature inquiries', 'Roadmap updates', 'Workaround guidance', 'Feedback collection'] },
    { id: 'saas-api', name: 'API Support', description: 'API documentation, integration help', ticketsPerMonth: 250, pricePerMonth: 99, features: ['API documentation', 'Integration guidance', 'Rate limit inquiries', 'Webhook support'] },
    { id: 'saas-account', name: 'Account Issues', description: 'Login, permissions, settings', ticketsPerMonth: 350, pricePerMonth: 79, features: ['Account recovery', 'Permission issues', 'Settings help', 'Team management'] },
  ],
  logistics: [
    { id: 'log-track', name: 'Tracking', description: 'Shipment tracking, status updates', ticketsPerMonth: 800, pricePerMonth: 89, features: ['Real-time tracking', 'Status notifications', 'Exception alerts', 'POD management'], popular: true },
    { id: 'log-delivery', name: 'Delivery Issues', description: 'Missed deliveries, rescheduling', ticketsPerMonth: 400, pricePerMonth: 69, features: ['Rescheduling', 'Address corrections', 'Redelivery requests', 'Special instructions'] },
    { id: 'log-warehouse', name: 'Warehouse Queries', description: 'Inventory, storage questions', ticketsPerMonth: 300, pricePerMonth: 59, features: ['Inventory checks', 'Storage inquiries', 'Pick/pack status', 'Stock alerts'] },
    { id: 'log-fleet', name: 'Fleet Management', description: 'Driver coordination, vehicle issues', ticketsPerMonth: 200, pricePerMonth: 79, features: ['Driver scheduling', 'Vehicle status', 'Route inquiries', 'Maintenance alerts'] },
    { id: 'log-customs', name: 'Customs & Documentation', description: 'Import/export, paperwork', ticketsPerMonth: 150, pricePerMonth: 99, features: ['Customs clearance', 'Document requests', 'Compliance help', 'Duty inquiries'] },
  ],
  others: [
    { id: 'other-general', name: 'General Support', description: 'General customer inquiries', ticketsPerMonth: 500, pricePerMonth: 79, features: ['General inquiries', 'Information requests', 'Basic troubleshooting', 'Call routing'], popular: true },
    { id: 'other-email', name: 'Email Support', description: 'Email-based ticket handling', ticketsPerMonth: 300, pricePerMonth: 49, features: ['Email triage', 'Auto-responses', 'Follow-up emails', 'Template responses'] },
    { id: 'other-chat', name: 'Chat Support', description: 'Live chat ticket handling', ticketsPerMonth: 400, pricePerMonth: 69, features: ['Chat routing', 'Quick responses', 'Handoff protocols', 'Chat transcripts'] },
    { id: 'other-phone', name: 'Phone Support', description: 'Phone call ticket creation', ticketsPerMonth: 200, pricePerMonth: 89, features: ['Call logging', 'Callback scheduling', 'Voicemail handling', 'Call notes'] },
  ],
};

function PricingPageLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#ECFDF5]">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-600" />
        <span className="text-sm text-gray-500">Loading pricing...</span>
      </div>
    </div>
  );
}

const trustIndicators = [
  { icon: Bot, label: 'AI-Powered' },
  { icon: Zap, label: 'Instant Setup' },
  { icon: ShieldCheck, label: 'Enterprise Ready' },
  { icon: Headphones, label: '24/7 Support' },
];

function PricingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [selectedIndustry, setSelectedIndustry] = useState<Industry | null>(null);
  const [variantQuantities, setVariantQuantities] = useState<Record<string, number>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showOtherForm, setShowOtherForm] = useState(false);
  const [otherIndustry, setOtherIndustry] = useState({ name: '', company: '', website: '' });

  useEffect(() => {
    const industryParam = searchParams.get('industry') as Industry | null;
    if (industryParam && ['ecommerce', 'saas', 'logistics', 'others'].includes(industryParam)) {
      setSelectedIndustry(industryParam);
      setShowOtherForm(industryParam === 'others');
    }
    const planParam = searchParams.get('plan');
    if (planParam && ['mini-parwa', 'parwa', 'high-parwa'].includes(planParam)) {
      setSelectedPlan(planParam);
    }

    // Track page visit for context-aware Jarvis routing
    if (typeof window !== 'undefined') {
      try {
        const existing = JSON.parse(localStorage.getItem('parwa_pages_visited') || '[]') as string[];
        if (!existing.includes('pricing_page')) {
          existing.push('pricing_page');
          localStorage.setItem('parwa_pages_visited', JSON.stringify(existing));
        }
      } catch {
        // ignore
      }
    }
  }, [searchParams]);

  const variants = selectedIndustry ? INDUSTRY_VARIANTS[selectedIndustry] : [];

  const handleQuantityChange = (variantId: string, quantity: number) => {
    setVariantQuantities((prev) => ({ ...prev, [variantId]: quantity }));
  };

  const handleDemo = (variantId: string) => {
    const variant = variants.find((v) => v.id === variantId);
    if (variant) toast(`Demo for "${variant.name}" coming soon!`, { icon: '🚀', style: { background: '#fff', color: '#1f2937', border: '1px solid #e5e7eb' } });
  };

  const handleChat = (variantId: string) => {
    const variant = variants.find((v) => v.id === variantId);
    if (variant) toast(`Chat for "${variant.name}" — redirecting...`, { icon: '💬', style: { background: '#fff', color: '#1f2937', border: '1px solid #e5e7eb' } });
  };

  const selectedVariants = variants.filter((v) => (variantQuantities[v.id] || 0) > 0).map((variant) => ({ variant, quantity: variantQuantities[variant.id] || 0 }));

  const handleIndustrySelect = (industry: Industry) => {
    setSelectedIndustry(industry);
    setVariantQuantities({});
    setShowOtherForm(industry === 'others');
  };

  const handleRemoveVariant = (variantId: string) => {
    setVariantQuantities((prev) => ({ ...prev, [variantId]: 0 }));
  };

  const handlePlanSelect = (planId: string) => {
    setSelectedPlan(planId);
    if (planId === 'high-parwa') {
      toast('Our team will reach out within 24 hours!', { icon: '📞', style: { background: '#fff', color: '#1f2937', border: '1px solid #e5e7eb' } });
    }
  };

  const handleContinue = async () => {
    if (!selectedPlan) { toast.error('Please select a plan first'); return; }
    if (!selectedIndustry) { toast.error('Please select an industry'); return; }
    if (selectedVariants.length === 0) { toast.error('Please select at least one variant'); return; }
    if (selectedIndustry === 'others') {
      if (!otherIndustry.name.trim()) { toast.error('Please enter your industry name'); return; }
      if (!otherIndustry.company.trim()) { toast.error('Please enter your company name'); return; }
    }
    setIsSubmitting(true);
    try {
      const selectionData = {
        plan: selectedPlan,
        industry: selectedIndustry,
        variants: selectedVariants.map((v) => ({ id: v.variant.id, name: v.variant.name, quantity: v.quantity, ticketsPerMonth: v.variant.ticketsPerMonth * v.quantity, pricePerMonth: v.variant.pricePerMonth * v.quantity })),
        totalTickets: selectedVariants.reduce((sum, v) => sum + v.variant.ticketsPerMonth * v.quantity, 0),
        totalMonthly: selectedVariants.reduce((sum, v) => sum + v.variant.pricePerMonth * v.quantity, 0),
        otherIndustry: selectedIndustry === 'others' ? otherIndustry : null,
      };
      localStorage.setItem('parwa_pricing_selection', JSON.stringify(selectionData));
      if (isAuthenticated) router.push('/jarvis');
      else router.push(`/login?redirect=/jarvis`);
    } catch { toast.error('Something went wrong. Please try again.'); } finally { setIsSubmitting(false); }
  };

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-[#ECFDF5] to-white">
      <NavigationBar />
      <main className="flex-grow">
        {/* ── Hero Header ── */}
        <section className="relative pt-12 sm:pt-16 pb-8 sm:pb-12 px-4 sm:px-6 lg:px-8">
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-emerald-200/20 blur-[120px] rounded-full" />
          </div>
          <div className="relative max-w-4xl mx-auto text-center">
            <Link href="/" className="inline-flex items-center gap-2 text-gray-400 hover:text-gray-600 mb-8 transition-colors text-sm">
              <ArrowLeft className="w-3.5 h-3.5" /> Back to Home
            </Link>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-gray-900 mb-4 leading-tight">
              Build Your AI <span className="text-gradient">Support Team</span>
            </h1>
            <p className="text-base sm:text-lg text-gray-500 max-w-2xl mx-auto mb-8 leading-relaxed">
              Choose your plan, pick your industry, select your variants. Pay only for what you need.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3 sm:gap-4">
              {trustIndicators.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.label} className="flex items-center gap-2 px-3 sm:px-4 py-2 rounded-full bg-emerald-50 border border-emerald-300/50 text-gray-600">
                    <Icon className="w-3.5 h-3.5 text-emerald-600/70" />
                    <span className="text-xs sm:text-sm font-medium">{item.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════════
            SECTION 1: THREE PLAN TIERS — mini parwa, parwa, high parwa
            ══════════════════════════════════════════════════════════ */}
        <section className="px-4 sm:px-6 lg:px-8 pb-12 sm:pb-16">
          <div className="max-w-6xl mx-auto">
            <div className="text-center mb-8 sm:mb-10">
              <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-900 mb-2">
                Choose Your <span className="text-gradient">PARWA Plan</span>
              </h2>
              <p className="text-sm sm:text-base text-gray-500">
                Three tiers designed for every stage of your business growth
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6 lg:gap-8">
              {PLAN_TIERS.map((plan) => {
                const isSelected = selectedPlan === plan.id;
                return (
                  <div
                    key={plan.id}
                    onClick={() => handlePlanSelect(plan.id)}
                    className={`
                      relative rounded-2xl border-2 p-6 sm:p-8 cursor-pointer
                      transition-all duration-500 backdrop-blur-sm
                      ${isSelected
                        ? 'border-emerald-400 bg-gradient-to-br from-emerald-50 to-white shadow-xl shadow-emerald-200/30 scale-[1.02] md:scale-105'
                        : plan.popular
                          ? 'border-emerald-200 bg-white hover:border-emerald-300 hover:shadow-lg hover:shadow-emerald-100/20'
                          : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-lg'
                      }
                    `}
                  >
                    {/* Popular Badge */}
                    {plan.popular && (
                      <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                        <span className="inline-flex items-center gap-1 px-4 py-1.5 text-xs font-bold bg-gradient-to-r from-amber-400 to-yellow-400 text-gray-900 rounded-full shadow-lg shadow-amber-400/30">
                          <Star className="w-3 h-3" fill="currentColor" />
                          Most Popular
                        </span>
                      </div>
                    )}

                    {/* Plan Name */}
                    <div className="mb-6 mt-1">
                      <h3 className="text-2xl sm:text-3xl font-extrabold text-gray-900 mb-2 tracking-tight">
                        {plan.name}
                      </h3>
                      <p className="text-sm text-gray-500 leading-relaxed">
                        {plan.tagline}
                      </p>
                    </div>

                    {/* Price */}
                    <div className="mb-6 pb-6 border-b border-gray-100">
                      <div className="flex items-baseline gap-1">
                        <span className={`text-4xl sm:text-5xl font-black ${isSelected ? 'text-emerald-600' : 'text-gray-900'}`}>
                          {plan.price}
                        </span>
                        <span className="text-sm text-gray-400 font-medium">{plan.priceNote}</span>
                      </div>
                    </div>

                    {/* Features */}
                    <ul className="space-y-3 mb-8">
                      {plan.features.map((feature, i) => (
                        <li key={i} className="flex items-start gap-3">
                          <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${isSelected ? 'bg-emerald-100' : 'bg-gray-100'}`}>
                            <Check className={`w-3 h-3 ${isSelected ? 'text-emerald-600' : 'text-gray-400'}`} strokeWidth={3} />
                          </div>
                          <span className={`text-sm leading-snug ${isSelected ? 'text-gray-800' : 'text-gray-600'}`}>
                            {feature}
                          </span>
                        </li>
                      ))}
                    </ul>

                    {/* CTA Button */}
                    <button
                      onClick={(e) => { e.stopPropagation(); handlePlanSelect(plan.id); }}
                      className={`
                        w-full py-3.5 rounded-xl text-sm font-bold transition-all duration-500
                        flex items-center justify-center gap-2
                        ${isSelected
                          ? 'bg-gradient-to-r from-emerald-600 to-emerald-500 text-white shadow-lg shadow-emerald-500/30'
                          : plan.popular
                            ? 'bg-gradient-to-r from-emerald-600 to-emerald-500 text-white hover:from-emerald-500 hover:to-emerald-400 shadow-lg shadow-emerald-500/20'
                            : 'bg-gray-900 text-white hover:bg-gray-800 shadow-lg shadow-gray-900/20'
                        }
                      `}
                    >
                      {plan.cta}
                      <ArrowRight className="w-4 h-4" />
                    </button>

                    {/* Selected indicator */}
                    {isSelected && (
                      <div className="absolute top-4 right-4 w-6 h-6 rounded-full bg-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/30">
                        <Check className="w-3.5 h-3.5 text-white" strokeWidth={3} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════════
            SECTION 2: INDUSTRY + VARIANT SELECTION
            ══════════════════════════════════════════════════════════ */}
        <section className="px-4 sm:px-6 lg:px-8 pb-16 sm:pb-24">
          <div className="max-w-7xl mx-auto">
            <div className="text-center mb-8 sm:mb-10">
              <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-900 mb-2">
                Customize Your <span className="text-gradient">AI Variants</span>
              </h2>
              <p className="text-sm sm:text-base text-gray-500">
                Pick your industry and choose exactly which support areas Jarvis handles
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8">
              <div className="lg:col-span-2 space-y-6 lg:space-y-8">
                {/* Plan Selection Reminder */}
                {!selectedPlan && (
                  <div className="rounded-xl border-2 border-dashed border-amber-300 bg-amber-50/50 p-5 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center flex-shrink-0">
                      <ArrowRight className="w-5 h-5 text-amber-600 rotate-[-90deg]" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-amber-800">Select a plan above first</p>
                      <p className="text-xs text-amber-600/80 mt-0.5">Choose mini parwa, parwa, or high parwa before picking variants</p>
                    </div>
                  </div>
                )}

                {/* Industry Selector */}
                <div className="rounded-xl border border-gray-200 bg-white p-5 sm:p-6 shadow-sm">
                  <IndustrySelector selectedIndustry={selectedIndustry} onSelect={handleIndustrySelect} />
                </div>

                {/* Other Industry Form */}
                {showOtherForm && (
                  <div className="rounded-xl border border-emerald-300/50 bg-emerald-50/50 p-5 sm:p-6">
                    <div className="flex items-center gap-2.5 mb-5">
                      <div className="w-9 h-9 rounded-lg bg-emerald-100 flex items-center justify-center"><Sparkles className="w-5 h-5 text-emerald-700" /></div>
                      <div>
                        <h3 className="text-base font-bold text-gray-900">Tell us about your industry</h3>
                        <p className="text-xs text-gray-500">We&apos;ll tailor the experience for you</p>
                      </div>
                    </div>
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">Industry Name <span className="text-red-500">*</span></label>
                        <input type="text" value={otherIndustry.name} onChange={(e) => setOtherIndustry({ ...otherIndustry, name: e.target.value })} placeholder="e.g., Healthcare, Finance, Education"
                          className="input" />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">Company Name <span className="text-red-500">*</span></label>
                        <input type="text" value={otherIndustry.company} onChange={(e) => setOtherIndustry({ ...otherIndustry, company: e.target.value })} placeholder="Your company name"
                          className="input" />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">Company Website</label>
                        <input type="url" value={otherIndustry.website} onChange={(e) => setOtherIndustry({ ...otherIndustry, website: e.target.value })} placeholder="https://yourcompany.com"
                          className="input" />
                      </div>
                    </div>
                  </div>
                )}

                {/* Variant Cards */}
                {selectedIndustry && variants.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-4">
                      <Users className="w-5 h-5 text-emerald-600/70" />
                      <h2 className="text-lg sm:text-xl font-bold text-gray-900">Choose Your Variants</h2>
                      <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 font-semibold ml-1">
                        {selectedIndustry === 'ecommerce' ? 'E-commerce' : selectedIndustry === 'saas' ? 'SaaS' : selectedIndustry === 'logistics' ? 'Logistics' : 'Other'}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
                      {variants.map((variant) => (
                        <VariantCard key={variant.id} variant={variant} quantity={variantQuantities[variant.id] || 0} onQuantityChange={handleQuantityChange} onDemo={handleDemo} onChat={handleChat} />
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Summary Sidebar */}
              <div className="lg:col-span-1">
                <div className="sticky top-20 lg:top-24">
                  <TotalSummary selectedVariants={selectedVariants} onContinue={handleContinue} isSubmitting={isSubmitting} onRemoveVariant={handleRemoveVariant} />
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}

export default function PricingPage() {
  return (
    <Suspense fallback={<PricingPageLoading />}>
      <PricingContent />
    </Suspense>
  );
}
