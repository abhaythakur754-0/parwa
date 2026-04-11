/**
 * PARWA Onboarding Page (Week 6 — Day 3 Phase 5)
 *
 * Full-page route: /onboarding
 *
 * Auth guard logic:
 *   1. If loading → show spinner
 *   2. If not authenticated → redirect to /login?redirect=/onboarding
 *   3. If already onboarded → redirect to /dashboard
 *   4. Otherwise → render OnboardingWizard (multi-step wizard)
 *
 * The wizard replaces the old Jarvis-only view. It provides a structured
 * 5-step flow: Welcome → Legal → Integrations → Knowledge Base → AI Setup.
 * After completion, the FirstVictory celebration is shown.
 */

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { OnboardingWizard } from '@/components/onboarding/OnboardingWizard';

export default function OnboardingPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, hydrate } = useAuth();

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

    if (user.onboarding_completed) {
      router.replace('/dashboard');
      return;
    }
  }, [isLoading, isAuthenticated, user, router]);

  if (isLoading) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-[#1A1A1A]">
        <Loader2 className="w-8 h-8 animate-spin text-orange-400 mb-4" />
        <p className="text-sm text-orange-200/50">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-[#1A1A1A]">
        <Loader2 className="w-6 h-6 animate-spin text-orange-400/50 mb-3" />
        <p className="text-sm text-white/30">Redirecting to login...</p>
      </div>
    );
  }

  return <OnboardingWizard />;
}
