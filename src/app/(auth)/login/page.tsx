'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { LoginForm } from '@/components/auth/LoginForm';
import { SocialLogin } from '@/components/auth/SocialLogin';
import { useAuth } from '@/hooks/useAuth';

function LoginPageLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(165deg, #022C22 0%, #064E3B 50%, #047857 100%)' }}>
      <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
    </div>
  );
}

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, loginWithGoogle, isAuthenticated, isLoading: authLoading, hydrate } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const redirectTo = searchParams.get('redirect') || '/models';

  useEffect(() => {
    if (isAuthenticated && !authLoading) router.push(redirectTo);
  }, [isAuthenticated, authLoading, router, redirectTo]);

  const handleLogin = async (email: string, password: string) => {
    setError(null);
    setIsSubmitting(true);
    try {
      // Call Next.js API route directly (external backend may not be available)
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (data.status !== 'success') {
        throw new Error(data.message || 'Login failed. Please try again.');
      }
      // Store minimal auth state in context
      const user = {
        id: data.user.id,
        email: data.user.email,
        full_name: data.user.fullName,
        is_verified: data.user.isVerified,
      };
      if (typeof window !== 'undefined') {
        localStorage.setItem('parwa_user', JSON.stringify(user));
      }
      // Sync AuthContext state from localStorage
      hydrate();
      toast.success('Welcome back!');
      router.push(redirectTo);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed. Please try again.';
      setError(message);
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleLogin = async (idToken: string) => {
    setGoogleError(null);
    setIsSubmitting(true);
    try {
      // Call local Next.js Google auth route
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
      // Sync AuthContext state from localStorage
      hydrate();
      toast.success(result.is_new_user ? 'Account created with Google!' : 'Welcome back!');
      router.push(redirectTo);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Google sign-in failed. Please try again.';
      setGoogleError(message);
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Don't block on authLoading — show the form immediately so users can always log in
  if (isAuthenticated && !authLoading) return null;

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden"
      style={{ background: 'linear-gradient(165deg, #022C22 0%, #064E3B 40%, #065F46 70%, #047857 100%)' }}
    >
      {/* Animated background elements */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute w-[400px] h-[400px] rounded-full" style={{
          background: 'radial-gradient(circle, rgba(16,185,129,0.15) 0%, rgba(16,185,129,0.02) 60%, transparent 80%)',
          top: '15%',
          left: '10%',
          animation: 'jarvisOrbFloat1 10s ease-in-out infinite',
        }} />
        <div className="absolute w-[300px] h-[300px] rounded-full" style={{
          background: 'radial-gradient(circle, rgba(255,215,0,0.06) 0%, rgba(255,215,0,0.01) 60%, transparent 80%)',
          bottom: '10%',
          right: '10%',
          animation: 'jarvisOrbFloat2 12s ease-in-out infinite',
        }} />
        <div className="absolute w-[200px] h-[200px] rounded-full" style={{
          background: 'radial-gradient(circle, rgba(52,211,153,0.1) 0%, transparent 70%)',
          top: '60%',
          left: '60%',
          animation: 'jarvisOrbFloat3 9s ease-in-out infinite',
        }} />
        {/* Particle dots */}
        {Array.from({ length: 12 }).map((_, i) => {
          const row = Math.floor(i / 4);
          const col = i % 4;
          return (
            <div
              key={i}
              className="absolute w-1 h-1 rounded-full bg-emerald-400"
              style={{
                left: `${(col + 0.5) * 25}%`,
                top: `${(row + 0.5) * 25}%`,
                animation: `jarvisDotPulse 3s ease-in-out infinite ${(i * 0.4) % 4}s`,
                opacity: 0,
              }}
            />
          );
        })}
      </div>

      <div className="w-full max-w-md space-y-8 relative z-10">
        {/* Header */}
        <div className="text-center">
          <Link href="/" className="inline-flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-600/30">
              <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
              </svg>
            </div>
            <span className="text-2xl font-bold text-white">PARWA</span>
          </Link>
          <h1 className="text-3xl font-bold text-white">Welcome back</h1>
          <p className="mt-2 text-sm text-emerald-200/50">Sign in to your account to continue</p>
        </div>

        {/* Glass Card */}
        <div
          className="rounded-2xl p-6 sm:p-8 relative overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)',
            border: '1px solid rgba(16,185,129,0.2)',
            backdropFilter: 'blur(20px)',
            boxShadow: '0 25px 50px rgba(0,0,0,0.3), 0 0 60px rgba(16,185,129,0.06)',
          }}
        >
          <div className="absolute -top-16 -right-16 w-32 h-32 rounded-full blur-[60px] pointer-events-none" style={{ background: 'rgba(16,185,129,0.1)' }} />
          {/* Google Login */}
          <SocialLogin onGoogleLogin={handleGoogleLogin} isLoading={isSubmitting} error={googleError} showDividerAfter={true} />
          {/* Email Login */}
          <div className="mt-6">
            <LoginForm onSubmit={handleLogin} isLoading={isSubmitting} error={error} />
          </div>
        </div>

        <div className="text-center text-sm text-emerald-200/30">
          <p>Need help? <Link href="/contact" className="text-emerald-400 hover:text-emerald-300 transition-colors">Contact Support</Link></p>
        </div>
      </div>

      <style jsx global>{`
        @keyframes jarvisOrbFloat1 {
          0%, 100% { transform: translateY(0) scale(1); }
          50% { transform: translateY(-30px) scale(1.05); }
        }
        @keyframes jarvisOrbFloat2 {
          0%, 100% { transform: translateY(0) scale(1); }
          50% { transform: translateY(-35px) scale(1.06); }
        }
        @keyframes jarvisOrbFloat3 {
          0%, 100% { transform: translateY(0) scale(1); }
          50% { transform: translateY(-20px) scale(1.03); }
        }
        @keyframes jarvisDotPulse {
          0%, 100% { opacity: 0; transform: scale(0.5); }
          50% { opacity: 0.6; transform: scale(1.2); }
        }
      `}</style>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginPageLoading />}>
      <LoginContent />
    </Suspense>
  );
}
