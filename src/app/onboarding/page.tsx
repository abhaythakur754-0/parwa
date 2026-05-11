/**
 * PARWA Onboarding Page
 *
 * Full-page route: /onboarding
 *
 * Supports two modes:
 *   - ?mode=wizard → 5-step OnboardingWizard (structured setup)
 *   - default → JarvisChat (conversational onboarding)
 *
 * Auth guard logic:
 *   1. If loading → show spinner
 *   2. If not authenticated → redirect to /login?redirect=/onboarding
 *   3. If already onboarded → redirect to /dashboard (variant-aware)
 *   4. Otherwise → render selected onboarding mode
 *
 * MINI PARWA INTEGRATION:
 *   - Maps variant_id from Models page to variant_tier for pipeline routing
 *     starter → mini_parwa, growth → parwa, high → parwa_high
 *   - This tier flows through session context to the handoff, where a
 *     VariantInstance is created for the correct pipeline
 */

'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { JarvisChat } from '@/components/jarvis/JarvisChat';
import { ChatErrorBoundary } from '@/components/jarvis/ChatErrorBoundary';
import { OnboardingWizard } from '@/components/onboarding/OnboardingWizard';

/**
 * Maps frontend variant_id to backend pipeline tier.
 * Starter (mini_parwa): 10-node pipeline, Tier 1 techniques
 * Growth (parwa):       15-node pipeline, Tier 1+2 techniques
 * High (parwa_high):    20-node pipeline, all techniques
 */
const VARIANT_ID_TO_TIER: Record<string, string> = {
  starter: 'mini_parwa',
  growth: 'parwa',
  high: 'parwa_high',
};

/**
 * Maps variant_tier to dashboard route for variant-specific redirect.
 */
const TIER_TO_DASHBOARD: Record<string, string> = {
  mini_parwa: '/dashboard?variant=mini',
  parwa: '/dashboard?variant=pro',
  parwa_high: '/dashboard?variant=high',
};

export default function OnboardingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isAuthenticated, isLoading, hydrate } = useAuth();

  // ── Determine onboarding mode ──
  const mode = searchParams.get('mode') || 'wizard'; // default to wizard now

  // ── Context: Read URL params for entry_source, variant, industry ──
  const [entrySource] = useState(() => {
    if (typeof window === 'undefined') return 'onboarding';
    const params = new URLSearchParams(window.location.search);
    return params.get('entry_source') || 'onboarding';
  });
  const [entryParams] = useState<Record<string, unknown>>(() => {
    if (typeof window === 'undefined') return {};
    const params = new URLSearchParams(window.location.search);
    const ctx: Record<string, unknown> = {};
    const industry = params.get('industry');
    const variant = params.get('variant');
    if (industry) ctx.industry = industry;
    if (variant) ctx.variant = variant;

    // ── MINI PARWA: Map variant_id to pipeline tier ──
    if (variant) {
      const tier = VARIANT_ID_TO_TIER[variant.toLowerCase()];
      if (tier) ctx.variant_tier = tier;
    }

    // Read bridged context from localStorage (set by other pages)
    try {
      const stored = localStorage.getItem('parwa_jarvis_context');
      if (stored) {
        const bridged = JSON.parse(stored) as Record<string, unknown>;
        if (bridged.variant && !variant) ctx.variant = bridged.variant;
        if (bridged.variant_id && !params.get('variant_id')) ctx.variant_id = bridged.variant_id;
        if (bridged.industry && !industry) ctx.industry = bridged.industry;
        if (bridged.selected_variants) ctx.selected_variants = bridged.selected_variants;
        if (bridged.total_price) ctx.total_price = bridged.total_price;
        if (bridged.source) ctx.referral_source = bridged.source;
        if (bridged.roi_result) ctx.roi_result = bridged.roi_result;
        if (bridged.interests) ctx.interests = bridged.interests;
        if (bridged.pages_visited) ctx.pages_visited = bridged.pages_visited;
        if (bridged.variant_id && !ctx.variant_tier) {
          const tier = VARIANT_ID_TO_TIER[String(bridged.variant_id).toLowerCase()];
          if (tier) ctx.variant_tier = tier;
        }
      }
    } catch { /* ignore */ }
    // Also read pricing selection if available
    try {
      const stored = localStorage.getItem('parwa_pricing_selection');
      if (stored) {
        const pricing = JSON.parse(stored) as Record<string, unknown>;
        if (pricing.plan && !ctx.selected_plan) ctx.selected_plan = pricing.plan;
        if (pricing.industry && !ctx.industry) ctx.industry = pricing.industry;
        if (pricing.variants && !ctx.selected_variants) ctx.selected_variants = pricing.variants;
        if (pricing.totalMonthly && !ctx.total_price) ctx.total_price = pricing.totalMonthly;
        if (pricing.plan && !ctx.variant_tier) {
          const tier = VARIANT_ID_TO_TIER[String(pricing.plan).toLowerCase()];
          if (tier) ctx.variant_tier = tier;
        }
      }
    } catch { /* ignore */ }
    return ctx;
  });

  // ── Get variant_tier for dashboard redirect ──
  const variantTier = (entryParams.variant_tier as string) || '';

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated || !user) {
      hydrate();
    }
  }, [isLoading, isAuthenticated, user, hydrate]);

  useEffect(() => {
    if (isLoading) return;

    if (!isAuthenticated || !user) {
      const redirectUrl = encodeURIComponent('/onboarding');
      router.replace(`/login?redirect=${redirectUrl}`);
      return;
    }

    // Already onboarded → redirect to variant-specific dashboard
    if (user.onboarding_completed) {
      const dashboardUrl = TIER_TO_DASHBOARD[variantTier] || '/dashboard';
      router.replace(dashboardUrl);
      return;
    }
  }, [isLoading, isAuthenticated, user, router, variantTier]);

  // ── Auth Loading ─────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-[#1A1A1A]">
        <Loader2 className="w-8 h-8 animate-spin text-orange-400 mb-4" />
        <p className="text-sm text-orange-200/50">Loading...</p>
      </div>
    );
  }

  // ── Not authenticated (redirect will fire) ───────────────────

  if (!isAuthenticated || !user) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-[#1A1A1A]">
        <Loader2 className="w-6 h-6 animate-spin text-orange-400/50 mb-3" />
        <p className="text-sm text-white/30">Redirecting to login...</p>
      </div>
    );
  }

  // ── Render Onboarding Mode ───────────────────────────────────

  if (mode === 'jarvis') {
    return (
      <ChatErrorBoundary>
        <JarvisChat entrySource={entrySource} entryParams={entryParams} />
      </ChatErrorBoundary>
    );
  }

  // Default: Wizard mode
  return <OnboardingWizard />;
}
