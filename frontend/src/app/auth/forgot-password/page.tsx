'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Sparkles, ArrowRight, AlertCircle, Mail, CheckCircle2 } from 'lucide-react';

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.trim()) {
      setError('Please enter your email address');
      return;
    }

    setIsLoading(true);
    // Simulate sending reset email (backend would handle this)
    await new Promise((resolve) => setTimeout(resolve, 1500));
    setSent(true);
    setIsLoading(false);
  };

  return (
    <div className="min-h-screen flex">
      {/* Left side — Decorative */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-[#0A3D2E] to-[#1B5E40] relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 left-20 w-64 h-64 rounded-full bg-[#D4AF37]/10 blur-3xl" />
          <div className="absolute bottom-20 right-20 w-80 h-80 rounded-full bg-white/5 blur-3xl" />
        </div>

        <div className="relative flex flex-col justify-center px-16 text-white">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-lg bg-[#D4AF37] flex items-center justify-center shadow-lg">
              <Sparkles className="h-5 w-5 text-[#1A1A1A]" />
            </div>
            <span className="font-bold text-2xl">PARWA</span>
          </div>

          <h1 className="text-4xl font-bold mb-4 leading-tight">
            Reset Your<br />
            <span className="text-[#D4AF37]">Password</span>
          </h1>

          <p className="text-white/60 text-lg leading-relaxed">
            We&apos;ll send you a secure link to reset your password.
            Your account security is our priority.
          </p>
        </div>
      </div>

      {/* Right side — Form */}
      <div className="flex-1 flex items-center justify-center px-4 sm:px-6 lg:px-8 bg-[#FAFAF8]">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md"
        >
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#0A3D2E] to-[#1B5E40] flex items-center justify-center shadow-md">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-xl text-[#0A3D2E]">PARWA</span>
          </div>

          {sent ? (
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-[#0A3D2E]/10 flex items-center justify-center mx-auto mb-6">
                <CheckCircle2 className="h-8 w-8 text-[#0A3D2E]" />
              </div>
              <h2 className="text-2xl font-bold text-[#0A3D2E] mb-2">Check Your Email</h2>
              <p className="text-[#6B7280] mb-8">
                If an account exists for <strong className="text-[#0A3D2E]">{email}</strong>,
                you&apos;ll receive a password reset link shortly.
              </p>
              <Button
                onClick={() => router.push('/auth/login')}
                className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A] font-semibold"
              >
                Back to Sign In
              </Button>
            </div>
          ) : (
            <>
              <h2 className="text-2xl font-bold text-[#0A3D2E] mb-1">Forgot Password?</h2>
              <p className="text-[#6B7280] mb-8">
                Enter your email and we&apos;ll send you a reset link
              </p>

              {error && (
                <div className="mb-6 p-3 rounded-lg bg-red-50 border border-red-200 flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
                  <span className="text-sm text-red-700">{error}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-sm font-medium text-[#0A3D2E]">
                    Email Address
                  </Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#6B7280]" />
                    <Input
                      id="email"
                      type="email"
                      placeholder="you@company.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="h-11 pl-10 border-[#E5E7EB] focus:border-[#0A3D2E] focus:ring-[#0A3D2E]"
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={isLoading}
                  className="w-full h-11 bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A] font-semibold shadow-md"
                >
                  {isLoading ? (
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 border-2 border-[#1A1A1A]/30 border-t-[#1A1A1A] rounded-full animate-spin" />
                      Sending...
                    </div>
                  ) : (
                    <>
                      Send Reset Link
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </>
                  )}
                </Button>
              </form>
            </>
          )}

          <div className="mt-8 text-center">
            <p className="text-sm text-[#6B7280]">
              Remember your password?{' '}
              <button
                onClick={() => router.push('/auth/login')}
                className="text-[#D4AF37] hover:text-[#E5C860] font-semibold"
              >
                Sign in
              </button>
            </p>
          </div>

          <div className="mt-6">
            <Button
              variant="ghost"
              onClick={() => router.push('/')}
              className="w-full text-[#6B7280] hover:text-[#0A3D2E]"
            >
              &larr; Back to Home
            </Button>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
