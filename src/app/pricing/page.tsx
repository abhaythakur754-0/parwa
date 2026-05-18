'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { NavigationBar, Footer } from '@/components/landing';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  IndustrySelector,
  VariantCard,
  TotalSummary,
  industries,
} from '@/components/pricing';
import type { IndustryKey } from '@/components/pricing';
import type { VariantData } from '@/components/pricing';
import type { SelectedVariant } from '@/components/pricing';
import {
  Sparkles,
  ArrowRight,
  Zap,
  Shield,
  Clock,
} from 'lucide-react';

// ── Variant Data Per Industry ──────────────────────────────────────────

const variantData: Record<IndustryKey, VariantData[]> = {
  ecommerce: [
    {
      id: 'ecom-order-mgmt',
      name: 'Order Management',
      description: 'Order status, tracking, modifications',
      ticketsPerMonth: 500,
      pricePerMonth: 99,
    },
    {
      id: 'ecom-returns',
      name: 'Returns & Refunds',
      description: 'Return requests, refund processing',
      ticketsPerMonth: 200,
      pricePerMonth: 49,
    },
    {
      id: 'ecom-product-faq',
      name: 'Product FAQ',
      description: 'Product questions, specifications',
      ticketsPerMonth: 1000,
      pricePerMonth: 79,
    },
    {
      id: 'ecom-shipping',
      name: 'Shipping Inquiries',
      description: 'Delivery status, shipping options',
      ticketsPerMonth: 300,
      pricePerMonth: 59,
    },
    {
      id: 'ecom-payment',
      name: 'Payment Issues',
      description: 'Failed payments, billing questions',
      ticketsPerMonth: 150,
      pricePerMonth: 39,
    },
  ],
  saas: [
    {
      id: 'saas-tech-support',
      name: 'Technical Support',
      description: 'Bug reports, troubleshooting',
      ticketsPerMonth: 400,
      pricePerMonth: 129,
    },
    {
      id: 'saas-billing',
      name: 'Billing Support',
      description: 'Subscription, invoice questions',
      ticketsPerMonth: 200,
      pricePerMonth: 69,
    },
    {
      id: 'saas-features',
      name: 'Feature Requests',
      description: 'Feature questions, roadmap',
      ticketsPerMonth: 300,
      pricePerMonth: 89,
    },
    {
      id: 'saas-api',
      name: 'API Support',
      description: 'API documentation, integration help',
      ticketsPerMonth: 250,
      pricePerMonth: 99,
    },
    {
      id: 'saas-account',
      name: 'Account Issues',
      description: 'Login, permissions, settings',
      ticketsPerMonth: 350,
      pricePerMonth: 79,
    },
  ],
  logistics: [
    {
      id: 'log-tracking',
      name: 'Shipment Tracking',
      description: 'Shipment tracking, status updates',
      ticketsPerMonth: 800,
      pricePerMonth: 89,
    },
    {
      id: 'log-delivery',
      name: 'Delivery Issues',
      description: 'Missed deliveries, rescheduling',
      ticketsPerMonth: 400,
      pricePerMonth: 69,
    },
    {
      id: 'log-warehouse',
      name: 'Warehouse Queries',
      description: 'Inventory, storage questions',
      ticketsPerMonth: 300,
      pricePerMonth: 59,
    },
    {
      id: 'log-fleet',
      name: 'Fleet Management',
      description: 'Driver coordination, vehicle issues',
      ticketsPerMonth: 200,
      pricePerMonth: 79,
    },
    {
      id: 'log-customs',
      name: 'Customs & Docs',
      description: 'Import/export, paperwork',
      ticketsPerMonth: 150,
      pricePerMonth: 99,
    },
  ],
  others: [
    {
      id: 'other-general',
      name: 'General Support',
      description: 'Custom AI agent for your general inquiries',
      ticketsPerMonth: 500,
      pricePerMonth: 89,
    },
    {
      id: 'other-custom-1',
      name: 'Custom Module 1',
      description: 'Jarvis will help you configure this after setup',
      ticketsPerMonth: 300,
      pricePerMonth: 69,
    },
    {
      id: 'other-custom-2',
      name: 'Custom Module 2',
      description: 'Jarvis will help you configure this after setup',
      ticketsPerMonth: 300,
      pricePerMonth: 69,
    },
  ],
};

// ── Trust Badges ───────────────────────────────────────────────────────

const trustBadges = [
  { icon: <Zap className="w-4 h-4" />, label: '10x faster responses' },
  { icon: <Shield className="w-4 h-4" />, label: 'SOC 2 compliant' },
  { icon: <Clock className="w-4 h-4" />, label: '24/7 AI availability' },
];

// ── Page Component ─────────────────────────────────────────────────────

export default function PricingPage() {
  const router = useRouter();
  const [selectedIndustry, setSelectedIndustry] = useState<IndustryKey | null>(
    null
  );
  const [quantities, setQuantities] = useState<Record<string, number>>({});

  // Get current industry's variants
  const currentVariants = useMemo(
    () => (selectedIndustry ? variantData[selectedIndustry] : []),
    [selectedIndustry]
  );

  // Compute selected variants with quantities > 0
  const selectedVariants: SelectedVariant[] = useMemo(() => {
    return currentVariants
      .filter((v) => (quantities[v.id] ?? 0) > 0)
      .map((v) => ({ variant: v, quantity: quantities[v.id] }));
  }, [currentVariants, quantities]);

  // Total monthly cost
  const totalMonthly = useMemo(
    () =>
      selectedVariants.reduce(
        (sum, sv) => sum + sv.variant.pricePerMonth * sv.quantity,
        0
      ),
    [selectedVariants]
  );

  // Handle industry change — reset quantities
  const handleIndustryChange = (key: IndustryKey) => {
    setSelectedIndustry(key);
    setQuantities({});
  };

  // Handle quantity change
  const handleQuantityChange = (variantId: string, qty: number) => {
    setQuantities((prev) => ({ ...prev, [variantId]: qty }));
  };

  // Continue with Jarvis — navigate to onboarding with context
  const handleContinue = () => {
    if (!selectedIndustry || selectedVariants.length === 0) return;

    // Build variant string: "returns_3x,faq_2x"
    const variantString = selectedVariants
      .map((sv) => `${sv.variant.id}_${sv.quantity}x`)
      .join(',');

    // Store in localStorage for onboarding to read
    const pricingContext = {
      industry: selectedIndustry,
      variants: selectedVariants.map((sv) => ({
        id: sv.variant.id,
        name: sv.variant.name,
        quantity: sv.quantity,
        pricePerMonth: sv.variant.pricePerMonth,
      })),
      totalMonthly,
      timestamp: Date.now(),
    };

    try {
      localStorage.setItem(
        'parwa_pricing_context',
        JSON.stringify(pricingContext)
      );
    } catch {
      // localStorage unavailable — URL params still work
    }

    // Navigate with URL params as well
    router.push(
      `/onboarding?source=pricing&industry=${selectedIndustry}&variants=${encodeURIComponent(variantString)}`
    );
  };

  // Get industry display name
  const industryName = selectedIndustry
    ? industries.find((i) => i.key === selectedIndustry)?.name
    : null;

  return (
    <div className="min-h-screen flex flex-col bg-[#0A0A0A]">
      <NavigationBar />

      <main className="flex-grow">
        {/* ── Hero Section ─────────────────────────────────────────── */}
        <section className="relative pt-20 pb-12 sm:pt-28 sm:pb-16 overflow-hidden">
          {/* Background glow */}
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[600px] bg-emerald-500/[0.04] rounded-full blur-[150px]" />
            <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/20 to-transparent" />
          </div>

          <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <Badge
              variant="outline"
              className="mb-6 bg-emerald-500/10 text-emerald-400 border-emerald-500/25 text-xs font-semibold px-4 py-1.5 rounded-full"
            >
              <Sparkles className="w-3 h-3 mr-1.5" />
              Industry-Specific Pricing
            </Badge>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white mb-5 tracking-tight">
              Build Your{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-emerald-300">
                AI Support Stack
              </span>
            </h1>

            <p className="text-gray-400 text-lg sm:text-xl max-w-2xl mx-auto mb-8 leading-relaxed">
              Choose your industry, select the support modules you need, and
              let Jarvis handle the rest. Pay only for what you use.
            </p>

            {/* Trust badges */}
            <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6">
              {trustBadges.map((badge) => (
                <div
                  key={badge.label}
                  className="flex items-center gap-2 text-gray-500 text-sm"
                >
                  <span className="text-emerald-500/60">{badge.icon}</span>
                  {badge.label}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Industry Selector ────────────────────────────────────── */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-10">
          <div className="mb-6">
            <h2 className="text-xl sm:text-2xl font-bold text-white mb-2">
              1. Choose Your Industry
            </h2>
            <p className="text-gray-500 text-sm">
              We&apos;ll show you pre-configured AI modules tailored to your
              business.
            </p>
          </div>

          <IndustrySelector
            selected={selectedIndustry}
            onSelect={handleIndustryChange}
          />
        </section>

        {/* ── Variant Cards + Summary ──────────────────────────────── */}
        {selectedIndustry && (
          <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-24">
            <div className="mb-6">
              <h2 className="text-xl sm:text-2xl font-bold text-white mb-2">
                2. Configure Your Modules
              </h2>
              <p className="text-gray-500 text-sm">
                Add the{' '}
                <span className="text-emerald-400/80">{industryName}</span>{' '}
                support modules you need. Adjust quantities to scale capacity.
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
              {/* Variant Cards Grid */}
              <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
                {currentVariants.map((variant) => (
                  <VariantCard
                    key={variant.id}
                    variant={variant}
                    quantity={quantities[variant.id] ?? 0}
                    onQuantityChange={(qty) =>
                      handleQuantityChange(variant.id, qty)
                    }
                  />
                ))}
              </div>

              {/* Summary Sidebar */}
              <div className="lg:col-span-1">
                <div className="lg:sticky lg:top-24">
                  <TotalSummary
                    selectedVariants={selectedVariants}
                    onContinue={handleContinue}
                  />

                  {/* Extra info card */}
                  {selectedVariants.length > 0 && (
                    <div className="mt-4 p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/10">
                      <p className="text-xs text-emerald-400/70 leading-relaxed">
                        <strong className="text-emerald-400">
                          Need more capacity?
                        </strong>{' '}
                        Increase the quantity of any module. Each unit adds the
                        listed ticket capacity to your monthly allowance.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ── Bottom CTA (when no industry selected) ───────────────── */}
        {!selectedIndustry && (
          <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-24 text-center">
            <div className="bg-[#111111] rounded-2xl border border-white/[0.06] p-8 sm:p-12">
              <h3 className="text-2xl sm:text-3xl font-bold text-white mb-4">
                Not Sure Which Industry?
              </h3>
              <p className="text-gray-400 text-lg mb-8 max-w-xl mx-auto">
                Select &quot;Others&quot; and Jarvis will help you customize a
                solution tailored to your unique business needs after setup.
              </p>
              <Button
                onClick={() => handleIndustryChange('others')}
                className="bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white font-semibold px-8 py-3 rounded-xl shadow-lg shadow-emerald-500/25 hover:shadow-emerald-500/40 transition-all duration-300"
              >
                Start with Custom Setup
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </section>
        )}
      </main>

      <Footer />
    </div>
  );
}
