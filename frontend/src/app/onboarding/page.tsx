/**
 * PARWA Onboarding Page (Week 6 — Day 3 Phase 5)
 *
 * Full-page route: /onboarding
 *
 * Supports two modes based on ?mode query parameter:
 *   - mode=wizard  → 5-step onboarding wizard (Legal → Integrations → KB → AI Config → First Victory)
 *   - mode=chat    → Jarvis conversational AI chat (default, demo/exploratory experience)
 *
 * Auth guard logic:
 *   1. If loading → show spinner
 *   2. If not authenticated → redirect to /login?redirect=/onboarding
 *   3. If already onboarded → redirect to /dashboard
 *   4. Otherwise → render Wizard or Chat based on mode param
 */

'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { JarvisChat } from '@/components/jarvis/JarvisChat';
import { ChatErrorBoundary } from '@/components/jarvis/ChatErrorBoundary';
import { OnboardingWizard } from '@/components/onboarding/OnboardingWizard';

export default function OnboardingPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, hydrate } = useAuth();

  // ── Determine render mode ──
  // D8-P6 FIX: Avoid SSR hydration mismatch. useState initializer runs on both
  // server and client — server always returns 'chat' (no window.location),
  // but client might read ?mode=wizard from URL, causing a mismatch.
  // Solution: Initialize to 'chat', then read URL in useEffect to update.
  const [mode, setMode] = useState<'wizard' | 'chat'>('chat');
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlMode = (params.get('mode') as 'wizard' | 'chat') || 'chat';
    setMode(urlMode);
    setHydrated(true);
  }, []);

  // ── Context: Read URL params for entry_source, variant, industry ──
  const [entrySource, setEntrySource] = useState('onboarding');
  const [entryParams, setEntryParams] = useState<Record<string, unknown>>({});

  // D8-P6: Read URL params and localStorage only after hydration
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
    // D8-P4: Validate parsed JSON is actually an object (browser extensions
    // can inject non-object values into localStorage, causing runtime errors).
    try {
      const stored = localStorage.getItem('parwa_jarvis_context');
      if (stored) {
        const parsed = JSON.parse(stored);
        const bridged = (parsed && typeof parsed === 'object' && !Array.isArray(parsed))
          ? (parsed as Record<string, unknown>) : null;
        if (bridged && typeof bridged.variant === 'string' && !variant) ctx.variant = bridged.variant;
        if (bridged && typeof bridged.variant_id === 'string' && !params.get('variant_id')) ctx.variant_id = bridged.variant_id;
        if (bridged && typeof bridged.industry === 'string' && !industry) ctx.industry = bridged.industry;
        if (bridged && Array.isArray(bridged.selected_variants)) ctx.selected_variants = bridged.selected_variants;
        if (bridged && typeof bridged.total_price === 'number') ctx.total_price = bridged.total_price;
        if (bridged && typeof bridged.source === 'string') ctx.referral_source = bridged.source;
        if (bridged && typeof bridged.roi_result === 'object' && bridged.roi_result) ctx.roi_result = bridged.roi_result;
        if (bridged && Array.isArray(bridged.interests)) ctx.interests = bridged.interests;
        if (bridged && Array.isArray(bridged.pages_visited)) ctx.pages_visited = bridged.pages_visited;
      }
    } catch { /* ignore */ }
    // Also read pricing selection if available
    // D8-P4: Type-validate pricing selection from localStorage
    try {
      const stored = localStorage.getItem('parwa_pricing_selection');
      if (stored) {
        const parsed = JSON.parse(stored);
        const pricing = (parsed && typeof parsed === 'object' && !Array.isArray(parsed))
          ? (parsed as Record<string, unknown>) : null;
        if (pricing && typeof pricing.plan === 'string' && !ctx.selected_plan) ctx.selected_plan = pricing.plan;
        if (pricing && typeof pricing.industry === 'string' && !ctx.industry) ctx.industry = pricing.industry;
        if (pricing && Array.isArray(pricing.variants) && !ctx.selected_variants) ctx.selected_variants = pricing.variants;
        if (pricing && typeof pricing.totalMonthly === 'number' && !ctx.total_price) ctx.total_price = pricing.totalMonthly;
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

  // ── Render based on mode ─────────────────────────────────────

  // Wizard mode: 5-step onboarding form
  if (mode === 'wizard') {
    return (
      <ChatErrorBoundary>
        <OnboardingWizard />
      </ChatErrorBoundary>
    );
  }

  // Chat mode: Jarvis conversational AI (default)
  return (
    <ChatErrorBoundary>
      <JarvisChat entrySource={entrySource} entryParams={entryParams} />
    </ChatErrorBoundary>
  );
}
