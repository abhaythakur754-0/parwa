/**
 * PARWA Onboarding Page — /onboarding
 *
 * Shows the 6-step onboarding wizard:
 *   1. Legal compliance
 *   2. Integration setup
 *   3. Knowledge base upload
 *   4. AI configuration
 *   5. Cost breakdown & checkout
 *   6. First Victory celebration
 *
 * After completing all steps, the user sees a "First Victory" celebration
 * and is redirected to the dashboard.
 *
 * Auth-protected: redirects to /login if not authenticated.
 *
 * IMPORTANT: The OnboardingWizard is loaded dynamically (ssr: false) because
 * its dependencies (integration-catalog, paddle-js, react-hot-toast, etc.)
 * cause TDZ errors like "Cannot access 'ee' before initialization" when
 * bundled into the main page chunk by Next.js. Dynamic import isolates all
 * onboarding code into a separate chunk that loads independently.
 */

'use client';

import React, { Component, useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';

// ── Lazy-load the ENTIRE onboarding wizard ────────────────────────────
// This isolates ALL onboarding dependencies (integration-catalog, paddle,
// react-hot-toast, pricing-config, etc.) into a separate JavaScript chunk.
// Without this, ESM module evaluation order in the production build causes
// TDZ errors ("Cannot access 'X' before initialization").
const OnboardingWizard = dynamic(
  () => import('@/components/onboarding/OnboardingWizard').then(mod => ({
    default: mod.OnboardingWizard,
  })),
  {
    loading: () => (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}>
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-12 h-12 animate-spin text-orange-400" />
          <p className="text-orange-200/50 text-sm">Loading onboarding&hellip;</p>
        </div>
      </div>
    ),
    ssr: false, // Never SSR — all onboarding modules are client-only
  }
);

// ── Error Boundary ────────────────────────────────────────────────────
// Catches TDZ errors like "Cannot access 'ee' before initialization"
// that can occur from ESM module evaluation in the Next.js production build.

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorCount: number;
}

class OnboardingErrorBoundary extends Component<
  { children: React.ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null, errorCount: 0 };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error, errorCount: 0 };
  }

  handleRetry = () => {
    const nextCount = this.state.errorCount + 1;
    if (nextCount >= 3) {
      // After 3 failed retries, force a hard reload
      if (typeof window !== 'undefined') {
        window.location.href = '/onboarding';
      }
      return;
    }
    this.setState({ hasError: false, error: null, errorCount: nextCount });
  };

  render() {
    if (this.state.hasError) {
      const isTDZError = this.state.error?.message?.includes('before initialization');
      return (
        <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}>
          <div className="max-w-md mx-auto text-center px-6">
            <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-red-500/10 flex items-center justify-center">
              <AlertCircle className="w-8 h-8 text-red-400" />
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">
              {isTDZError ? 'Module Loading Error' : 'Something went wrong'}
            </h2>
            <p className="text-sm text-orange-200/40 mb-1">
              {isTDZError
                ? 'A required module failed to initialize. This usually resolves with a page refresh.'
                : 'An unexpected error occurred.'}
            </p>
            {this.state.error && (
              <p className="text-xs text-orange-200/25 mb-6 font-mono">
                {this.state.error.message}
              </p>
            )}
            <button
              onClick={this.handleRetry}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] font-semibold rounded-xl hover:from-orange-400 hover:to-amber-300 transition-all"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Loading Fallback ──────────────────────────────────────────────────
function OnboardingLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}>
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="w-12 h-12 animate-spin text-orange-400" />
        <p className="text-orange-200/50 text-sm">Loading onboarding&hellip;</p>
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
    <OnboardingErrorBoundary>
      <Suspense fallback={<OnboardingLoading />}>
        <OnboardingContent />
      </Suspense>
    </OnboardingErrorBoundary>
  );
}
