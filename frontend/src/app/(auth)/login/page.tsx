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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#ECFDF5] to-white">
      <Loader2 className="w-8 h-8 animate-spin text-emerald-600" />
    </div>
  );
}

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, loginWithGoogle, isAuthenticated, isLoading: authLoading } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const redirectTo = searchParams.get('redirect') || '/dashboard';

  useEffect(() => {
    if (isAuthenticated && !authLoading) router.push(redirectTo);
  }, [isAuthenticated, authLoading, router, redirectTo]);

  const handleLogin = async (email: string, password: string) => {
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
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
      await loginWithGoogle(idToken);
      toast.success('Welcome back!');
      router.push(redirectTo);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Google sign-in failed. Please try again.';
      setGoogleError(message);
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (authLoading) return <LoginPageLoading />;
  if (isAuthenticated) return null;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-[#ECFDF5] to-white">
      <div className="w-full max-w-md space-y-8">
        {/* Header */}
        <div className="text-center">
          <Link href="/" className="inline-flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-600 to-emerald-700 flex items-center justify-center shadow-lg shadow-emerald-600/25">
              <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
              </svg>
            </div>
            <span className="text-2xl font-bold text-gray-900">PARWA</span>
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">Welcome back</h1>
          <p className="mt-2 text-sm text-gray-500">Sign in to your account to continue</p>
        </div>

        {/* Card */}
        <div className="card card-padding">
          {/* Google Login - AT TOP */}
          <SocialLogin onGoogleLogin={handleGoogleLogin} isLoading={isSubmitting} error={googleError} showDividerAfter={true} />
          {/* Email Login - BELOW */}
          <div className="mt-6">
            <LoginForm onSubmit={handleLogin} isLoading={isSubmitting} error={error} />
          </div>
        </div>

        <div className="text-center text-sm text-gray-400">
          <p>Need help? <Link href="/contact" className="text-emerald-600 hover:text-emerald-700">Contact Support</Link></p>
        </div>
      </div>
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
