/**
 * PARWA Onboarding Page — /onboarding
 *
 * Full-page onboarding experience where new users set up their account.
 * Uses Jarvis chat for interactive onboarding.
 *
 * Auth-protected: redirects to /login if not authenticated.
 * Post-onboarding: redirects to /dashboard if already onboarded.
 */

'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { OnboardingJarvisChat } from '@/components/onboarding-jarvis/OnboardingJarvisChat';

// ── Loading Fallback ──────────────────────────────────────────────────
function OnboardingLoading() {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="w-12 h-12 animate-spin text-orange-400" />
        <p className="text-gray-400 text-sm">Loading Jarvis&hellip;</p>
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

  // Parse entry context from URL params
  const entrySource = searchParams.get('source') || searchParams.get('entry') || 'direct';
  const entryVariantId = searchParams.get('variant_id') || searchParams.get('variant') || '';
  const entryVariantName = searchParams.get('variant_name') || '';
  const entryIndustry = searchParams.get('industry') || '';

  const entryParams: Record<string, string> = {};
  if (entryVariantId) entryParams.variant_id = entryVariantId;
  if (entryVariantName) entryParams.variant_name = entryVariantName;
  if (entryIndustry) entryParams.industry = entryIndustry;

  useEffect(() => {
    if (authLoading) return;

    if (!user) {
      router.push(`/login?redirect=/onboarding&source=${entrySource}`);
      return;
    }

    // Check if already onboarded (has company with onboarding completed)
    // For now, we let them through — the session type will handle this
    setReady(true);
  }, [user, authLoading, router, entrySource]);

  if (authLoading || !ready) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-12 h-12 animate-spin text-orange-400" />
          <p className="text-gray-400 text-sm">Loading Jarvis&hellip;</p>
        </div>
      </div>
    );
  }

  return (
    <OnboardingJarvisChat
      entrySource={entrySource}
      entryParams={Object.keys(entryParams).length > 0 ? entryParams : undefined}
    />
  );
}

// ── Page Export ────────────────────────────────────────────────────────
export default function OnboardingPage() {
  return (
    <Suspense fallback={<OnboardingLoading />}>
      <OnboardingContent />
    </Suspense>
  );
}
