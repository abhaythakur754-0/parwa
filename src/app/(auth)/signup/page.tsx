'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';

import { SignupForm, SignupFormData } from '@/components/auth/SignupForm';
import { SocialLogin } from '@/components/auth/SocialLogin';
import { useAuth } from '@/hooks/useAuth';

export default function SignupPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [alreadyLoggedIn, setAlreadyLoggedIn] = useState(false);
  const { hydrate } = useAuth();

  // Check if already logged in via localStorage
  useEffect(() => {
    try {
      const storedUser = localStorage.getItem('parwa_user');
      if (storedUser) {
        const user = JSON.parse(storedUser);
        if (user && user.email) {
          setAlreadyLoggedIn(true);
          return;
        }
      }
    } catch {
      // ignore parse errors
    }
    setIsChecking(false);
  }, []);

  const handleSignup = async (data: SignupFormData) => {
    setError(null);
    setIsSubmitting(true);

    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: data.email,
          password: data.password,
          fullName: data.full_name,
          companyName: data.company_name,
          industry: data.industry,
        }),
      });

      const result = await res.json();

      if (!res.ok) {
        throw new Error(result.message || 'Registration failed. Please try again.');
      }

      toast.success('Account created successfully! Redirecting to login...');

      // Redirect to login page
      router.push('/login');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed. Please try again.';
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

      // Store user in localStorage and sync AuthContext
      if (result.user) {
        localStorage.setItem('parwa_user', JSON.stringify(result.user));
      }
      hydrate();
      toast.success(result.is_new_user ? 'Account created with Google!' : 'Signed in with Google!');
      router.push('/models');
    } catch (err) {
      const message = err instanceof Error
        ? err.message
        : 'Google sign-in failed. Please try again.';
      setGoogleError(message);
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCheckEmail = async (email: string): Promise<boolean> => {
    try {
      const res = await fetch('/api/auth/check-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      return !data.exists;
    } catch {
      return false;
    }
  };

  if (alreadyLoggedIn) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 40%, #3D2A10 70%, #4A3520 100%)' }}>
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div className="absolute w-[350px] h-[350px] rounded-full" style={{ background: 'radial-gradient(circle, rgba(255,127,17,0.15) 0%, rgba(255,127,17,0.02) 60%, transparent 80%)', top: '20%', right: '10%', animation: 'jarvisOrbFloat1 10s ease-in-out infinite' }} />
        </div>
        <div className="w-full max-w-md space-y-6 relative z-10 text-center">
          <Link href="/" className="inline-flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-600/30">
              <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" /></svg>
            </div>
            <span className="text-2xl font-bold text-white">PARWA</span>
          </Link>
          <div className="w-16 h-16 mx-auto rounded-full bg-orange-500/15 border border-orange-500/25 flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-orange-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">You're already signed in! 👋</h1>
          <p className="text-sm text-orange-200/50 mb-6">Looks like you already have an account. No need to sign up again.</p>
          <div className="flex flex-col gap-3 max-w-xs mx-auto">
            <Link href="/models" className="w-full py-3 px-4 bg-gradient-to-r from-orange-500 to-orange-400 hover:from-orange-400 hover:to-orange-300 text-[#1A1A1A] font-semibold rounded-xl transition-all duration-500 shadow-lg shadow-orange-600/25">Go to Dashboard →</Link>
            <Link href="/login" className="text-sm text-orange-400 hover:text-orange-300 transition-colors">Or sign in with a different account</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden"
      style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 40%, #3D2A10 70%, #4A3520 100%)' }}
    >
      {/* Animated background elements */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute w-[400px] h-[400px] rounded-full" style={{
          background: 'radial-gradient(circle, rgba(255,127,17,0.15) 0%, rgba(255,127,17,0.02) 60%, transparent 80%)',
          top: '15%',
          right: '10%',
          animation: 'jarvisOrbFloat1 10s ease-in-out infinite',
        }} />
        <div className="absolute w-[350px] h-[350px] rounded-full" style={{
          background: 'radial-gradient(circle, rgba(255,215,0,0.06) 0%, rgba(255,215,0,0.01) 60%, transparent 80%)',
          bottom: '15%',
          left: '5%',
          animation: 'jarvisOrbFloat2 12s ease-in-out infinite',
        }} />
        <div className="absolute w-[250px] h-[250px] rounded-full" style={{
          background: 'radial-gradient(circle, rgba(255,165,0,0.1) 0%, transparent 70%)',
          top: '50%',
          left: '40%',
          animation: 'jarvisOrbFloat3 9s ease-in-out infinite',
        }} />
        {Array.from({ length: 12 }).map((_, i) => {
          const row = Math.floor(i / 4);
          const col = i % 4;
          return (
            <div
              key={i}
              className="absolute w-1 h-1 rounded-full bg-orange-400"
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
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-600/30">
              <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
              </svg>
            </div>
            <span className="text-2xl font-bold text-white">PARWA</span>
          </Link>

          <h1 className="text-3xl font-bold text-white">
            Create your account
          </h1>
          <p className="mt-2 text-sm text-orange-200/50">
            Create your account to get started with Parwa
          </p>
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
          <div className="absolute -bottom-16 -left-16 w-32 h-32 rounded-full blur-[60px] pointer-events-none" style={{ background: 'rgba(255,215,0,0.05)' }} />

          {/* Social Login */}
          <SocialLogin
            onGoogleLogin={handleGoogleLogin}
            isLoading={isSubmitting}
            error={googleError}
          />

          {/* Signup Form */}
          <div className="mt-6">
            <SignupForm
              onSubmit={handleSignup}
              onCheckEmail={handleCheckEmail}
              isLoading={isSubmitting}
              error={error}
            />
          </div>
        </div>

        {/* Terms */}
        <p className="text-center text-xs text-orange-200/30">
          By creating an account, you agree to our{' '}
          <Link href="/terms" className="text-orange-400 hover:text-orange-300 transition-colors">
            Terms of Service
          </Link>{' '}
          and{' '}
          <Link href="/privacy" className="text-orange-400 hover:text-orange-300 transition-colors">
            Privacy Policy
          </Link>
        </p>
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
