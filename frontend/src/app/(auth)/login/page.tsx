'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';

import { LoginForm } from '@/components/auth/LoginForm';
import { SocialLogin } from '@/components/auth/SocialLogin';
import { useAuth } from '@/hooks/useAuth';

/**
 * Login Page
 * 
 * Authentication page for existing users.
 * Based on F-010: Email/password login
 * 
 * Features:
 * - Email/password login
 * - Google OAuth login
 * - Redirect after login
 * - Redirect if already authenticated
 */

// Loading component for Suspense fallback
function LoginPageLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <Loader2 className="w-8 h-8 animate-spin text-teal-500" />
    </div>
  );
}

// Main login content component
function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, loginWithGoogle, isAuthenticated, isLoading: authLoading } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Get redirect URL from query params
  const redirectTo = searchParams.get('redirect') || '/dashboard';

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      router.push(redirectTo);
    }
  }, [isAuthenticated, authLoading, router, redirectTo]);

  // Handle login form submission
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

  // Handle Google OAuth
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

  // Show loading if checking auth status
  if (authLoading) {
    return <LoginPageLoading />;
  }

  // Don't render if already authenticated
  if (isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        {/* Header */}
        <div className="text-center">
          {/* Logo */}
          <Link href="/" className="inline-flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-teal-500 to-teal-600 flex items-center justify-center shadow-lg shadow-teal-500/20">
              <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
              </svg>
            </div>
            <span className="text-2xl font-bold text-white">PARWA</span>
          </Link>
          
          <h1 className="text-3xl font-bold text-white">
            Welcome back
          </h1>
          <p className="mt-2 text-sm text-white/60">
            Sign in to your account to continue
          </p>
        </div>

        {/* Main Card */}
        <div className="card card-padding">
          {/* Social Login */}
          <SocialLogin
            onGoogleLogin={handleGoogleLogin}
            isLoading={isSubmitting}
            error={googleError}
          />

          {/* Login Form */}
          <div className="mt-6">
            <LoginForm
              onSubmit={handleLogin}
              isLoading={isSubmitting}
              error={error}
            />
          </div>
        </div>

        {/* Help Links */}
        <div className="text-center text-sm text-white/40">
          <p>
            Need help?{' '}
            <Link href="/contact" className="text-teal-400 hover:text-teal-300">
              Contact Support
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

// Main page component with Suspense
export default function LoginPage() {
  return (
    <Suspense fallback={<LoginPageLoading />}>
      <LoginContent />
    </Suspense>
  );
}
