/**
 * PARWA Onboarding Page — /onboarding
 *
 * Shows the 4-step onboarding wizard:
 *   1. Details (Name, Website, Email OTP, Legal Docs)
 *   2. Integration Setup (Connect channels & CRM)
 *   3. Knowledge Base (Upload or connect existing KB)
 *   4. First Victory Celebration 🎉
 *
 * After completing all steps, the user sees a "First Victory" celebration
 * and is redirected to the dashboard.
 *
 * Auth-protected: redirects to /login if not authenticated.
 */

'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { OnboardingWizard } from '@/components/onboarding/OnboardingWizard';

// ── Loading Fallback ──────────────────────────────────────────────────
function OnboardingLoading() {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="w-12 h-12 animate-spin text-orange-400" />
        <p className="text-gray-400 text-sm">Loading onboarding&hellip;</p>
      </div>
    </div>
  );
}

// ── Onboarding Content ────────────────────────────────────────────────
function OnboardingContent() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (authLoading) return;

    if (!user) {
      const entrySource = searchParams.get('source') || 'direct';
      router.push(`/login?redirect=/onboarding&source=${entrySource}`);
      return;
    }

    setReady(true);
  }, [user, authLoading, router, searchParams]);

  if (authLoading || !ready) {
    return <OnboardingLoading />;
  }

  return <OnboardingWizard />;
}

// ── Page Export ────────────────────────────────────────────────────────
export default function OnboardingPage() {
  return (
    <Suspense fallback={<OnboardingLoading />}>
      <OnboardingContent />
    </Suspense>
  );
}
