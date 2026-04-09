'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';

import { SignupForm, SignupFormData } from '@/components/auth/SignupForm';
import { SocialLogin } from '@/components/auth/SocialLogin';
import { useAuth } from '@/hooks/useAuth';

/**
 * Signup Page
 * 
 * Registration page for new users.
 * Based on F-010: User registration
 * 
 * Flow:
 * 1. User enters email, password, name, company, industry
 * 2. On success, redirects to pricing page or demo
 * 3. If already authenticated, redirects to dashboard
 */

export default function SignupPage() {
  const router = useRouter();
  const { register, loginWithGoogle, checkEmailAvailability, isAuthenticated, isLoading: authLoading } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      router.push('/models');
    }
  }, [isAuthenticated, authLoading, router]);

  // Handle signup form submission
  const handleSignup = async (data: SignupFormData) => {
    setError(null);
    setIsSubmitting(true);

    try {
      const response = await register({
        email: data.email,
        password: data.password,
        confirm_password: data.password,
        full_name: data.full_name,
        company_name: data.company_name,
        industry: data.industry,
      });

      toast.success('Account created successfully!');

      // Redirect based on whether user is new
      if (response.is_new_user) {
        // New users go to pricing/plan selection
        router.push('/models');
      } else {
        // Existing users go to dashboard
        router.push('/dashboard');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed. Please try again.';
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
      const response = await loginWithGoogle(idToken);

      toast.success('Signed in with Google!');

      // Redirect based on whether user is new
      if (response.is_new_user) {
        // New users from Google OAuth need to complete profile
        router.push('/welcome/details');
      } else {
        router.push('/dashboard');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Google sign-in failed. Please try again.';
      setGoogleError(message);
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle email availability check
  const handleCheckEmail = async (email: string): Promise<boolean> => {
    return checkEmailAvailability(email);
  };

  // Show loading if checking auth status
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
      </div>
    );
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
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-600 to-emerald-700 flex items-center justify-center shadow-lg shadow-emerald-600/20">
              <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
              </svg>
            </div>
            <span className="text-2xl font-bold text-gray-900">PARWA</span>
          </Link>
          
          <h1 className="text-3xl font-bold text-gray-900">
            Create your account
          </h1>
          <p className="mt-2 text-sm text-gray-500">
            Start your 14-day free trial. No credit card required.
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
        <p className="text-center text-xs text-gray-400">
          By creating an account, you agree to our{' '}
          <Link href="/terms" className="text-emerald-400 hover:text-emerald-300">
            Terms of Service
          </Link>{' '}
          and{' '}
          <Link href="/privacy" className="text-emerald-400 hover:text-emerald-300">
            Privacy Policy
          </Link>
        </p>
      </div>
    </div>
  );
}
