/**
 * PARWA Onboarding Page (Week 6 — Day 3 Phase 5)
 *
 * Full-page route: /onboarding
 *
 * Auth guard logic:
 *   1. If loading → show spinner
 *   2. If not authenticated → redirect to /login?redirect=/onboarding
 *   3. If already onboarded → redirect to /dashboard
 *   4. Otherwise → render JarvisChat
 *
 * Uses the useAuth hook for authentication state.
 * Session detection: checks if user has an active Jarvis session
 * (handoff_completed or onboarding_completed flag).
 */

'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { OnboardingWizard } from '@/components/onboarding/OnboardingWizard';
import { ChatErrorBoundary } from '@/components/jarvis/ChatErrorBoundary';

export default function OnboardingPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, hydrate } = useAuth();

  // ── Context: Read URL params for entry_source, variant, industry ──
  // ONB-C06: Initialize with safe defaults to avoid SSR hydration mismatch.
  // Actual URL params and localStorage are read client-side in useEffect.
  const [entrySource, setEntrySource] = useState('onboarding');
  const [entryParams, setEntryParams] = useState<Record<string, unknown>>({});

  // ONB-C06 FIX: Read URL params and localStorage in useEffect (client-only)
  // to prevent SSR hydration mismatch from window.location / localStorage.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setEntrySource(params.get('entry_source') || 'onboarding');

    const ctx: Record<string, unknown> = {};
    const industry = params.get('industry');
    const variant = params.get('variant');
    if (industry) ctx.industry = industry;
    if (variant) ctx.variant = variant;
    // Read bridged context from localStorage (set by other pages)
    // NOTE: Do NOT remove context here — let useJarvisChat's pushContextToBackend handle the sync.
    // Removing it here causes data loss if the push hasn't completed yet.
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
      }
    } catch { /* ignore */ }
    setEntryParams(ctx);
  }, []);

  useEffect(() => {
    // Wait for auth to initialize
    if (isLoading) return;

    // If AuthContext says not authenticated, try hydrating from localStorage
    // (handles case where login was done via Next.js API route)
    if (!isAuthenticated || !user) {
      hydrate();
    }
  }, [isLoading, isAuthenticated, user, hydrate]);

  useEffect(() => {
    // Wait for auth to initialize
    if (isLoading) return;

    // Not logged in → redirect to login with return URL
    if (!isAuthenticated || !user) {
      const redirectUrl = encodeURIComponent('/onboarding');
      router.replace(`/login?redirect=${redirectUrl}`);
      return;
    }

    // Already onboarded → redirect to dashboard
    if (user.onboarding_completed) {
      router.replace('/dashboard');
      return;
    }
  }, [isLoading, isAuthenticated, user, router]);

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

  // ── Render Wizard ──────────────────────────────────────────────

  return (
    <ChatErrorBoundary>
      <OnboardingWizard />
    </ChatErrorBoundary>
  );
}
