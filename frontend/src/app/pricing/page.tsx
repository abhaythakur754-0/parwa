'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Loader2, ArrowLeft, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';

import {
  IndustrySelector,
  VariantCard,
  TotalSummary,
  type Industry,
  type PricingVariant,
} from '@/components/pricing';
import NavigationBar from '@/components/landing/NavigationBar';
import Footer from '@/components/landing/Footer';
import { useAuth } from '@/hooks/useAuth';

/**
 * Pricing Page
 *
 * Day 6: Industry Selector + Variants
 *
 * User Flow:
 * 1. Select industry (E-commerce, SaaS, Logistics, Others)
 * 2. See variants for selected industry
 * 3. Adjust quantities for each variant
 * 4. Review bill summary
 * 5. Continue to Jarvis Chat (checkout)
 *
 * Based on ONBOARDING_SPEC.md Section 3
 */

// Industry variant data
const INDUSTRY_VARIANTS: Record<Industry, PricingVariant[]> = {
  ecommerce: [
    {
      id: 'ecom-order',
      name: 'Order Management',
      description: 'Order status, tracking, modifications',
      ticketsPerMonth: 500,
      pricePerMonth: 99,
      features: [
        'Order status inquiries',
        'Tracking updates',
        'Order modifications',
        'Cancellation handling',
      ],
      popular: true,
    },
    {
      id: 'ecom-returns',
      name: 'Returns & Refunds',
      description: 'Return requests, refund processing',
      ticketsPerMonth: 200,
      pricePerMonth: 49,
      features: [
        'Return authorization',
        'Refund processing',
        'Exchange handling',
        'Store credit issuance',
      ],
    },
    {
      id: 'ecom-product',
      name: 'Product FAQ',
      description: 'Product questions, specifications',
      ticketsPerMonth: 1000,
      pricePerMonth: 79,
      features: [
        'Product inquiries',
        'Specification questions',
        'Availability checks',
        'Recommendations',
      ],
    },
    {
      id: 'ecom-shipping',
      name: 'Shipping Inquiries',
      description: 'Delivery status, shipping options',
      ticketsPerMonth: 300,
      pricePerMonth: 59,
      features: [
        'Shipping status',
        'Delivery estimates',
        'Carrier coordination',
        'Address changes',
      ],
    },
    {
      id: 'ecom-payment',
      name: 'Payment Issues',
      description: 'Failed payments, billing questions',
      ticketsPerMonth: 150,
      pricePerMonth: 39,
      features: [
        'Payment failures',
        'Billing inquiries',
        'Invoice requests',
        'Promo code issues',
      ],
    },
  ],
  saas: [
    {
      id: 'saas-tech',
      name: 'Technical Support',
      description: 'Bug reports, troubleshooting',
      ticketsPerMonth: 400,
      pricePerMonth: 129,
      features: [
        'Bug triage',
        'Troubleshooting guides',
        'Known issues response',
        'Escalation routing',
      ],
      popular: true,
    },
    {
      id: 'saas-billing',
      name: 'Billing Support',
      description: 'Subscription, invoice questions',
      ticketsPerMonth: 200,
      pricePerMonth: 69,
      features: [
        'Subscription changes',
        'Invoice inquiries',
        'Refund requests',
        'Plan comparisons',
      ],
    },
    {
      id: 'saas-feature',
      name: 'Feature Requests',
      description: 'Feature questions, roadmap',
      ticketsPerMonth: 300,
      pricePerMonth: 89,
      features: [
        'Feature inquiries',
        'Roadmap updates',
        'Workaround guidance',
        'Feedback collection',
      ],
    },
    {
      id: 'saas-api',
      name: 'API Support',
      description: 'API documentation, integration help',
      ticketsPerMonth: 250,
      pricePerMonth: 99,
      features: [
        'API documentation',
        'Integration guidance',
        'Rate limit inquiries',
        'Webhook support',
      ],
    },
    {
      id: 'saas-account',
      name: 'Account Issues',
      description: 'Login, permissions, settings',
      ticketsPerMonth: 350,
      pricePerMonth: 79,
      features: [
        'Account recovery',
        'Permission issues',
        'Settings help',
        'Team management',
      ],
    },
  ],
  logistics: [
    {
      id: 'log-track',
      name: 'Tracking',
      description: 'Shipment tracking, status updates',
      ticketsPerMonth: 800,
      pricePerMonth: 89,
      features: [
        'Real-time tracking',
        'Status notifications',
        'Exception alerts',
        'POD management',
      ],
      popular: true,
    },
    {
      id: 'log-delivery',
      name: 'Delivery Issues',
      description: 'Missed deliveries, rescheduling',
      ticketsPerMonth: 400,
      pricePerMonth: 69,
      features: [
        'Rescheduling',
        'Address corrections',
        'Redelivery requests',
        'Special instructions',
      ],
    },
    {
      id: 'log-warehouse',
      name: 'Warehouse Queries',
      description: 'Inventory, storage questions',
      ticketsPerMonth: 300,
      pricePerMonth: 59,
      features: [
        'Inventory checks',
        'Storage inquiries',
        'Pick/pack status',
        'Stock alerts',
      ],
    },
    {
      id: 'log-fleet',
      name: 'Fleet Management',
      description: 'Driver coordination, vehicle issues',
      ticketsPerMonth: 200,
      pricePerMonth: 79,
      features: [
        'Driver scheduling',
        'Vehicle status',
        'Route inquiries',
        'Maintenance alerts',
      ],
    },
    {
      id: 'log-customs',
      name: 'Customs & Documentation',
      description: 'Import/export, paperwork',
      ticketsPerMonth: 150,
      pricePerMonth: 99,
      features: [
        'Customs clearance',
        'Document requests',
        'Compliance help',
        'Duty inquiries',
      ],
    },
  ],
  others: [
    {
      id: 'other-general',
      name: 'General Support',
      description: 'General customer inquiries',
      ticketsPerMonth: 500,
      pricePerMonth: 79,
      features: [
        'General inquiries',
        'Information requests',
        'Basic troubleshooting',
        'Call routing',
      ],
      popular: true,
    },
    {
      id: 'other-email',
      name: 'Email Support',
      description: 'Email-based ticket handling',
      ticketsPerMonth: 300,
      pricePerMonth: 49,
      features: [
        'Email triage',
        'Auto-responses',
        'Follow-up emails',
        'Template responses',
      ],
    },
    {
      id: 'other-chat',
      name: 'Chat Support',
      description: 'Live chat ticket handling',
      ticketsPerMonth: 400,
      pricePerMonth: 69,
      features: [
        'Chat routing',
        'Quick responses',
        'Handoff protocols',
        'Chat transcripts',
      ],
    },
    {
      id: 'other-phone',
      name: 'Phone Support',
      description: 'Phone call ticket creation',
      ticketsPerMonth: 200,
      pricePerMonth: 89,
      features: [
        'Call logging',
        'Callback scheduling',
        'Voicemail handling',
        'Call notes',
      ],
    },
  ],
};

// Loading component
function PricingPageLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <Loader2 className="w-8 h-8 animate-spin text-teal-500" />
    </div>
  );
}

// Main pricing content
function PricingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [selectedIndustry, setSelectedIndustry] = useState<Industry | null>(null);
  const [variantQuantities, setVariantQuantities] = useState<Record<string, number>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showOtherForm, setShowOtherForm] = useState(false);
  const [otherIndustry, setOtherIndustry] = useState({
    name: '',
    company: '',
    website: '',
  });

  // Pre-select industry from query param
  useEffect(() => {
    const industryParam = searchParams.get('industry') as Industry | null;
    if (industryParam && ['ecommerce', 'saas', 'logistics', 'others'].includes(industryParam)) {
      setSelectedIndustry(industryParam);
    }
  }, [searchParams]);

  // Get variants for selected industry
  const variants = selectedIndustry ? INDUSTRY_VARIANTS[selectedIndustry] : [];

  // Handle quantity change
  const handleQuantityChange = (variantId: string, quantity: number) => {
    setVariantQuantities((prev) => ({
      ...prev,
      [variantId]: quantity,
    }));
  };

  // Get selected variants for summary
  const selectedVariants = variants
    .filter((v) => (variantQuantities[v.id] || 0) > 0)
    .map((variant) => ({
      variant,
      quantity: variantQuantities[variant.id] || 0,
    }));

  // Handle industry selection
  const handleIndustrySelect = (industry: Industry) => {
    setSelectedIndustry(industry);
    setVariantQuantities({}); // Reset quantities when changing industry
    setShowOtherForm(industry === 'others');
  };

  // Handle continue to checkout
  const handleContinue = async () => {
    if (!selectedIndustry) {
      toast.error('Please select an industry');
      return;
    }

    if (selectedVariants.length === 0) {
      toast.error('Please select at least one variant');
      return;
    }

    // For "Others" industry, validate additional fields
    if (selectedIndustry === 'others') {
      if (!otherIndustry.name.trim()) {
        toast.error('Please enter your industry name');
        return;
      }
      if (!otherIndustry.company.trim()) {
        toast.error('Please enter your company name');
        return;
      }
    }

    setIsSubmitting(true);

    try {
      // Store selection in localStorage for Jarvis Chat
      const selectionData = {
        industry: selectedIndustry,
        variants: selectedVariants.map((v) => ({
          id: v.variant.id,
          name: v.variant.name,
          quantity: v.quantity,
          ticketsPerMonth: v.variant.ticketsPerMonth * v.quantity,
          pricePerMonth: v.variant.pricePerMonth * v.quantity,
        })),
        totalTickets: selectedVariants.reduce(
          (sum, v) => sum + v.variant.ticketsPerMonth * v.quantity,
          0
        ),
        totalMonthly: selectedVariants.reduce(
          (sum, v) => sum + v.variant.pricePerMonth * v.quantity,
          0
        ),
        otherIndustry: selectedIndustry === 'others' ? otherIndustry : null,
      };

      localStorage.setItem('parwa_pricing_selection', JSON.stringify(selectionData));

      // Navigate to Jarvis Chat (or login if not authenticated)
      if (isAuthenticated) {
        router.push('/jarvis');
      } else {
        router.push(`/login?redirect=/jarvis`);
      }
    } catch (error) {
      toast.error('Something went wrong. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Navigation */}
      <NavigationBar onOpenJarvis={() => router.push('/jarvis')} />

      {/* Main Content */}
      <main className="flex-grow py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          {/* Back Button */}
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-white/60 hover:text-white mb-8 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Home
          </Link>

          {/* Page Header */}
          <div className="text-center mb-12">
            <h1 className="text-4xl font-bold text-white mb-4">
              Choose Your Support Package
            </h1>
            <p className="text-lg text-white/60 max-w-2xl mx-auto">
              Select your industry and customize your AI support agent package.
              Pay only for what you need.
            </p>
          </div>

          {/* Main Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Column: Industry + Variants */}
            <div className="lg:col-span-2 space-y-8">
              {/* Industry Selector */}
              <div className="card card-padding">
                <IndustrySelector
                  selectedIndustry={selectedIndustry}
                  onSelect={handleIndustrySelect}
                />
              </div>

              {/* "Others" Industry Form */}
              {showOtherForm && (
                <div className="card card-padding animate-on-scroll is-visible">
                  <div className="flex items-center gap-2 mb-4">
                    <Sparkles className="w-5 h-5 text-purple-400" />
                    <h3 className="text-lg font-semibold text-white">
                      Tell us about your industry
                    </h3>
                  </div>
                  <div className="space-y-4">
                    <div>
                      <label className="label">Industry Name *</label>
                      <input
                        type="text"
                        value={otherIndustry.name}
                        onChange={(e) =>
                          setOtherIndustry({ ...otherIndustry, name: e.target.value })
                        }
                        placeholder="e.g., Healthcare, Finance, Education"
                        className="input"
                      />
                    </div>
                    <div>
                      <label className="label">Company Name *</label>
                      <input
                        type="text"
                        value={otherIndustry.company}
                        onChange={(e) =>
                          setOtherIndustry({ ...otherIndustry, company: e.target.value })
                        }
                        placeholder="Your company name"
                        className="input"
                      />
                    </div>
                    <div>
                      <label className="label">Company Website</label>
                      <input
                        type="url"
                        value={otherIndustry.website}
                        onChange={(e) =>
                          setOtherIndustry({ ...otherIndustry, website: e.target.value })
                        }
                        placeholder="https://yourcompany.com"
                        className="input"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Variant Cards */}
              {selectedIndustry && variants.length > 0 && (
                <div>
                  <h2 className="text-xl font-semibold text-white mb-4">
                    Select Variants
                  </h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {variants.map((variant) => (
                      <VariantCard
                        key={variant.id}
                        variant={variant}
                        quantity={variantQuantities[variant.id] || 0}
                        onQuantityChange={handleQuantityChange}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Right Column: Summary (Sticky) */}
            <div className="lg:col-span-1">
              <div className="sticky top-24">
                <TotalSummary
                  selectedVariants={selectedVariants}
                  onContinue={handleContinue}
                  isSubmitting={isSubmitting}
                />
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
}

// Main page component with Suspense
export default function PricingPage() {
  return (
    <Suspense fallback={<PricingPageLoading />}>
      <PricingContent />
    </Suspense>
  );
}
