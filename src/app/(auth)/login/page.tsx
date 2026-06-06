'use client';

import React, { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Loader2, ArrowLeft } from 'lucide-react';
import toast from 'react-hot-toast';
import { LoginForm } from '@/components/auth/LoginForm';
import { SocialLogin } from '@/components/auth/SocialLogin';
import { useAuth } from '@/hooks/useAuth';
import { getSafeRedirect } from '@/lib/auth-cookies';

// ── Loading Skeleton ──────────────────────────────────────────────────

function LoginPageLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}>
      <Loader2 className="w-8 h-8 animate-spin text-orange-400" />
    </div>
  );
}

// ── Login Content ─────────────────────────────────────────────────────

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading: authLoading, hydrate, logout } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const redirectTo = getSafeRedirect(searchParams.get('redirect'));

  // ── REDIRECT LOOP PROTECTION ──────────────────────────────────────
  // If we're authenticated and try to redirect but end up back here,
  // that means the middleware rejected our token (stale session).
  // Force logout to clear stale data and break the loop.
  const redirectAttempted = useRef(false);
  const loopDetected = useRef(false);

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      // If we already tried redirecting once and we're still here,
      // it means we got bounced back = REDIRECT LOOP
      if (redirectAttempted.current) {
        console.warn('[LoginPage] Redirect loop detected — forcing logout');
        loopDetected.current = true;
        logout();
        return;
      }

      redirectAttempted.current = true;
      router.push(redirectTo);
    }
  }, [isAuthenticated, authLoading, router, redirectTo, logout]);

  // ── After successful login, check onboarding then redirect ──────

  async function redirectAfterLogin(isNewUser?: boolean) {
    // New users always go to onboarding
    if (isNewUser) {
      router.push('/onboarding');
      return;
    }

    // Returning users — check if onboarding is completed
    try {
      const res = await fetch('/api/onboarding/state');
      if (res.ok) {
        const onboardingState = await res.json();
        if (!onboardingState.first_victory_completed) {
          router.push('/onboarding');
          return;
        }
      }
    } catch {
      // Onboarding check failed — go to default redirect
    }

    router.push(redirectTo);
  }

  // ── Email Login Handler ───────────────────────────────────────────

  const handleLogin = async (email: string, password: string) => {
    setError(null);
    setIsSubmitting(true);
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (data.status !== 'success') {
        throw new Error(data.message || 'Login failed. Please try again.');
      }
      // Store non-sensitive user display data
      const user = {
        id: data.user.id,
        email: data.user.email,
        full_name: data.user.fullName,
        is_verified: data.user.isVerified,
      };
      localStorage.setItem('parwa_user', JSON.stringify(user));
      hydrate();
      toast.success('Welcome back!');
      await redirectAfterLogin(data.is_new_user);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed. Please try again.';
      setError(message);
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── Google Login Handler (stable ref via useCallback) ──────────────

  const redirectRef = useRef(redirectAfterLogin);
  redirectRef.current = redirectAfterLogin;

  const handleGoogleLogin = useCallback(async (idToken: string) => {
    setGoogleError(null);
    setIsSubmitting(true);
    try {
      const res = await fetch('/api/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_token: idToken }),
      });
      const result = await res.json();
      if (result.status !== 'success') {
        throw new Error(result.message || 'Google sign-in failed. Please try again.');
      }
      if (result.user) {
        localStorage.setItem('parwa_user', JSON.stringify(result.user));
      }
      hydrate();
      toast.success(result.is_new_user ? 'Account created with Google!' : 'Welcome back!');
      await redirectRef.current(result.is_new_user);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Google sign-in failed. Please try again.';
      setGoogleError(message);
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  }, [hydrate]);

  // ── Render ──────────────────────────────────────────────────────────

  // If authenticated and about to redirect, show loading (but only once)
  if (isAuthenticated && !authLoading && !loopDetected.current) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}>
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-orange-400 mx-auto mb-4" />
          <p className="text-orange-200/60 text-sm">Redirecting&hellip;</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden"
      style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 40%, #3D2A10 70%, #4A3520 100%)' }}
    >
      {/* Background effects */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute w-[400px] h-[400px] rounded-full" style={{
          background: 'radial-gradient(circle, rgba(255,127,17,0.15) 0%, rgba(255,127,17,0.02) 60%, transparent 80%)',
          top: '15%', left: '10%',
          animation: 'orbFloat1 10s ease-in-out infinite',
        }} />
        <div className="absolute w-[300px] h-[300px] rounded-full" style={{
          background: 'radial-gradient(circle, rgba(255,215,0,0.06) 0%, rgba(255,215,0,0.01) 60%, transparent 80%)',
          bottom: '10%', right: '10%',
          animation: 'orbFloat2 12s ease-in-out infinite',
        }} />
      </div>

      <div className="w-full max-w-md space-y-8 relative z-10">
        {/* Back to Home */}
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-orange-400/60 hover:text-orange-400 transition-colors group">
          <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-1" />
          <span>Back to Home</span>
        </Link>

        {/* Header */}
        <div className="text-center">
          <Link href="/" className="inline-flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-600/30">
              <svg className="w-7 h-7" viewBox="0 0 40 40" fill="none">
                <path d="M6 7h24a4 4 0 014 4v13a4 4 0 01-4 4h-8l-3 6-2-6H6a4 4 0 01-4-4V11a4 4 0 014-4z" stroke="white" strokeWidth="2.8" strokeLinejoin="round" />
                <path d="M22 11l-6 8h4.5L17 28l8-10h-4.5l3.5-7z" fill="white" />
              </svg>
            </div>
            <span className="text-2xl font-bold text-white">PARWA</span>
          </Link>
          <h1 className="text-3xl font-bold text-white">Welcome back</h1>
          <p className="mt-2 text-sm text-orange-200/50">Sign in to your account to continue</p>
        </div>

        {/* Glass Card */}
        <div
          className="rounded-2xl p-6 sm:p-8 relative overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)',
            border: '1px solid rgba(255,127,17,0.2)',
            backdropFilter: 'blur(20px)',
            boxShadow: '0 25px 50px rgba(0,0,0,0.3), 0 0 60px rgba(255,127,17,0.06)',
          }}
        >
          <div className="absolute -top-16 -right-16 w-32 h-32 rounded-full blur-[60px] pointer-events-none" style={{ background: 'rgba(255,127,17,0.1)' }} />
          <SocialLogin onGoogleLogin={handleGoogleLogin} isLoading={isSubmitting} error={googleError} showDividerAfter={true} />
          <div className="mt-6">
            <LoginForm onSubmit={handleLogin} isLoading={isSubmitting} error={error} />
          </div>
        </div>

        <div className="text-center text-sm text-orange-200/30">
          <p>Need help? <Link href="/contact" className="text-orange-400 hover:text-orange-300 transition-colors">Contact Support</Link></p>
        </div>
      </div>

      <style jsx global>{`
        @keyframes orbFloat1 {
          0%, 100% { transform: translateY(0) scale(1); }
          50% { transform: translateY(-30px) scale(1.05); }
        }
        @keyframes orbFloat2 {
          0%, 100% { transform: translateY(0) scale(1); }
          50% { transform: translateY(-35px) scale(1.06); }
        }
      `}</style>
    </div>
  );
}

// ── Page Export ────────────────────────────────────────────────────────

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginPageLoading />}>
      <LoginContent />
    </Suspense>
  );
}
