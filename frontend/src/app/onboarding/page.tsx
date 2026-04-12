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

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { JarvisChat } from '@/components/jarvis/JarvisChat';
import { ChatErrorBoundary } from '@/components/jarvis/ChatErrorBoundary';

export default function OnboardingPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, hydrate } = useAuth();

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

  // ── Render Chat ──────────────────────────────────────────────

  return (
    <ChatErrorBoundary>
      <JarvisChat entrySource="onboarding" />
    </ChatErrorBoundary>
  );
}
