'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { CheckCircle, Loader2 } from 'lucide-react';

import { useAuth } from '@/hooks/useAuth';
import { DetailsForm } from '@/components/onboarding/DetailsForm';
import { userDetailsApi, onboardingApi } from '@/lib/api';
import { UserDetails, OnboardingState } from '@/types/onboarding';

// ── Loading Fallback ──────────────────────────────────────────────────
function DetailsLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}>
      <div className="text-center">
        <Loader2 className="w-8 h-8 animate-spin text-orange-400 mx-auto mb-4" />
        <p className="text-orange-200/50">Loading...</p>
      </div>
    </div>
  );
}

// ── Details Content ────────────────────────────────────────────────────
function DetailsContent() {
  const { user, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isLoading, setIsLoading] = useState(true);
  const [initialData, setInitialData] = useState<UserDetails | null>(null);
  const [onboardingState, setOnboardingState] = useState<OnboardingState | null>(null);
  const [ready, setReady] = useState(false);

  // Auth gate: redirect to login if not authenticated
  useEffect(() => {
    if (authLoading) return;

    if (!user) {
      // Preserve all query params (source, industry, variants) in the redirect URL
      const currentParams = searchParams.toString();
      const redirectPath = currentParams
        ? `/welcome/details?${currentParams}`
        : '/welcome/details';
      router.push(`/login?redirect=${encodeURIComponent(redirectPath)}`);
      return;
    }

    setReady(true);
  }, [user, authLoading, router, searchParams]);

  // Fetch initial data after auth is confirmed
  useEffect(() => {
    if (!ready) return;

    async function fetchInitialData() {
      try {
        const [details, state] = await Promise.all([
          userDetailsApi.get().catch(() => null),
          onboardingApi.getState().catch(() => null),
        ]);
        setInitialData(details);
        setOnboardingState(state);
        if (state?.details_completed) {
          // Details already done — go to onboarding wizard
          router.push('/onboarding');
        }
      } catch (error) {
        console.error('Failed to fetch initial data:', error);
      } finally {
        setIsLoading(false);
      }
    }
    fetchInitialData();
  }, [ready, router]);

  const handleSubmit = (data: UserDetails) => { setInitialData(data); };
  const handleNext = () => {
    // After details, go to the full onboarding wizard (integrations, knowledge, AI config)
    const source = searchParams.get('source');
    const industry = searchParams.get('industry');
    const variants = searchParams.get('variants');
    const params = new URLSearchParams();
    if (source) params.set('source', source);
    if (industry) params.set('industry', industry);
    if (variants) params.set('variants', variants);
    const qs = params.toString();
    router.push(qs ? `/onboarding?${qs}` : '/onboarding');
  };

  if (authLoading || !ready || isLoading) {
    return <DetailsLoading />;
  }

  return (
    <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #1A1A1A 100%)' }}>
      {/* Background effects */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute w-[400px] h-[400px] rounded-full" style={{ background: 'radial-gradient(circle, rgba(255,127,17,0.12) 0%, transparent 70%)', top: '10%', left: '20%', animation: 'orbFloat 10s ease-in-out infinite' }} />
        <div className="absolute w-[300px] h-[300px] rounded-full" style={{ background: 'radial-gradient(circle, rgba(255,165,0,0.08) 0%, transparent 70%)', bottom: '15%', right: '15%', animation: 'orbFloat 12s ease-in-out infinite' }} />
      </div>

      <div className="max-w-xl mx-auto relative z-10">
        {/* Progress Indicator — matches onboarding wizard's 6 steps */}
        <div className="mb-8">
          <div className="flex items-center justify-center gap-1 sm:gap-2">
            <Step number={1} label="Details" isActive isCompleted={false} />
            <div className="w-4 sm:w-8 h-0.5 bg-white/10" />
            <Step number={2} label="Legal" isActive={false} isCompleted={false} />
            <div className="w-4 sm:w-8 h-0.5 bg-white/10" />
            <Step number={3} label="Integrations" isActive={false} isCompleted={false} />
            <div className="w-4 sm:w-8 h-0.5 bg-white/10" />
            <Step number={4} label="AI Setup" isActive={false} isCompleted={false} />
            <div className="w-4 sm:w-8 h-0.5 bg-white/10" />
            <Step number={5} label="Payment" isActive={false} isCompleted={false} />
            <div className="w-4 sm:w-8 h-0.5 bg-white/10" />
            <Step number={6} label="Launch" isActive={false} isCompleted={false} />
          </div>
        </div>

        {/* Main Card */}
        <div className="rounded-2xl p-6 sm:p-8 relative overflow-hidden" style={{ background: 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)', border: '1px solid rgba(255,127,17,0.2)', backdropFilter: 'blur(20px)', boxShadow: '0 25px 50px rgba(0,0,0,0.3), 0 0 60px rgba(255,127,17,0.06)' }}>
          <div className="absolute -top-16 -right-16 w-32 h-32 rounded-full blur-[60px] pointer-events-none" style={{ background: 'rgba(255,127,17,0.1)' }} />

          {/* Logo */}
          <div className="text-center mb-6">
            <h1 className="text-3xl font-bold text-gradient">PARWA</h1>
            <p className="text-orange-200/50 text-sm mt-1">AI-Powered Customer Support</p>
          </div>

          <DetailsForm initialData={initialData} onSubmit={handleSubmit} onNext={handleNext} />
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-sm text-orange-200/30">
          <p>Need help?{' '}<a href="mailto:support@parwa.buzz" className="text-orange-400 hover:text-orange-300 transition-colors">Contact Support</a></p>
        </div>
      </div>

      <style jsx global>{`@keyframes orbFloat { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-30px); } }`}</style>
    </div>
  );
}

function Step({ number, label, isActive, isCompleted }: { number: number; label: string; isActive: boolean; isCompleted: boolean; }) {
  return (
    <div className="flex flex-col items-center">
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-medium ${
        isCompleted ? 'bg-orange-500 text-white'
          : isActive ? 'bg-orange-600 text-white'
          : 'bg-white/10 text-orange-200/40'
      }`}>
        {isCompleted ? <CheckCircle className="w-3.5 h-3.5" /> : number}
      </div>
      <span className={`mt-1 text-[9px] font-medium hidden sm:block ${isActive ? 'text-orange-400' : 'text-orange-200/30'}`}>{label}</span>
    </div>
  );
}

// ── Page Export ────────────────────────────────────────────────────────
export default function WelcomeDetailsPage() {
  return (
    <Suspense fallback={<DetailsLoading />}>
      <DetailsContent />
    </Suspense>
  );
}
