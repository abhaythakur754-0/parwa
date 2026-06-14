'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Sparkles, Eye, EyeOff, ArrowRight, AlertCircle, Check,
  Building2, User, Mail, Lock
} from 'lucide-react';
import { useAuth } from '@/components/providers/auth-provider';

const industries = [
  { value: 'general', label: 'General' },
  { value: 'ecommerce', label: 'E-Commerce' },
  { value: 'saas', label: 'SaaS' },
  { value: 'logistics', label: 'Logistics' },
];

const passwordRequirements = [
  { label: 'At least 8 characters', test: (p: string) => p.length >= 8 },
  { label: 'Contains a number', test: (p: string) => /\d/.test(p) },
  { label: 'Contains uppercase letter', test: (p: string) => /[A-Z]/.test(p) },
];

export default function RegisterPage() {
  const router = useRouter();
  const { register, isAuthenticated, isLoading: authLoading } = useAuth();
  const [form, setForm] = useState({
    company_name: '',
    industry: 'general',
    user_name: '',
    email: '',
    password: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [step, setStep] = useState<1 | 2>(1); // 1 = company, 2 = user

  // Redirect to dashboard if already authenticated
  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.replace('/dashboard');
    }
  }, [isAuthenticated, authLoading, router]);

  if (isAuthenticated) return null;

  const updateField = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const passwordStrength = passwordRequirements.filter((r) => r.test(form.password)).length;

  const handleStep1 = () => {
    if (!form.company_name.trim()) {
      setError('Company name is required');
      return;
    }
    setError('');
    setStep(2);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!form.user_name.trim() || !form.email.trim() || !form.password) {
      setError('All fields are required');
      return;
    }

    if (form.password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setIsLoading(true);
    try {
      await register(form);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
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
            Start Your<br />
            <span className="text-[#D4AF37]">Support Revolution</span>
          </h1>

          <p className="text-white/60 text-lg mb-12 leading-relaxed">
            Create your account and unlock AI-powered customer support.
            Set up in minutes, see results in hours.
          </p>

          <div className="space-y-4">
            {[
              'Free trial — no credit card required',
              'Choose Mini, Standard, or High later',
              'Connect 35+ integrations instantly',
            ].map((text) => (
              <div key={text} className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-[#D4AF37]" />
                <span className="text-white/70 text-sm">{text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right side — Registration Form */}
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

          <h2 className="text-2xl font-bold text-[#0A3D2E] mb-1">Create Account</h2>
          <p className="text-[#6B7280] mb-6">
            {step === 1 ? 'Tell us about your company' : 'Set up your admin account'}
          </p>

          {/* Step indicator */}
          <div className="flex items-center gap-2 mb-8">
            <div className={`h-1.5 flex-1 rounded-full ${step >= 1 ? 'bg-[#0A3D2E]' : 'bg-[#E5E7EB]'}`} />
            <div className={`h-1.5 flex-1 rounded-full ${step >= 2 ? 'bg-[#0A3D2E]' : 'bg-[#E5E7EB]'}`} />
          </div>

          {error && (
            <div className="mb-6 p-3 rounded-lg bg-red-50 border border-red-200 flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
              <span className="text-sm text-red-700">{error}</span>
            </div>
          )}

          <form onSubmit={step === 1 ? (e) => { e.preventDefault(); handleStep1(); } : handleSubmit}>
            {step === 1 ? (
              <div className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="company_name" className="text-sm font-medium text-[#0A3D2E]">
                    Company Name
                  </Label>
                  <div className="relative">
                    <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#6B7280]" />
                    <Input
                      id="company_name"
                      placeholder="Acme Inc."
                      value={form.company_name}
                      onChange={(e) => updateField('company_name', e.target.value)}
                      className="h-11 pl-10 border-[#E5E7EB] focus:border-[#0A3D2E] focus:ring-[#0A3D2E]"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="industry" className="text-sm font-medium text-[#0A3D2E]">
                    Industry
                  </Label>
                  <div className="grid grid-cols-2 gap-3">
                    {industries.map((ind) => (
                      <button
                        key={ind.value}
                        type="button"
                        onClick={() => updateField('industry', ind.value)}
                        className={`p-3 rounded-lg border-2 text-sm font-medium transition-all ${
                          form.industry === ind.value
                            ? 'border-[#0A3D2E] bg-[#0A3D2E]/5 text-[#0A3D2E]'
                            : 'border-[#E5E7EB] text-[#6B7280] hover:border-[#0A3D2E]/30'
                        }`}
                      >
                        {ind.label}
                      </button>
                    ))}
                  </div>
                </div>

                <Button
                  type="submit"
                  className="w-full h-11 bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A] font-semibold shadow-md"
                >
                  Continue
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            ) : (
              <div className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="user_name" className="text-sm font-medium text-[#0A3D2E]">
                    Your Name
                  </Label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#6B7280]" />
                    <Input
                      id="user_name"
                      placeholder="John Doe"
                      value={form.user_name}
                      onChange={(e) => updateField('user_name', e.target.value)}
                      className="h-11 pl-10 border-[#E5E7EB] focus:border-[#0A3D2E] focus:ring-[#0A3D2E]"
                    />
                  </div>
                </div>

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
                      value={form.email}
                      onChange={(e) => updateField('email', e.target.value)}
                      className="h-11 pl-10 border-[#E5E7EB] focus:border-[#0A3D2E] focus:ring-[#0A3D2E]"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password" className="text-sm font-medium text-[#0A3D2E]">
                    Password
                  </Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#6B7280]" />
                    <Input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder="Create a strong password"
                      value={form.password}
                      onChange={(e) => updateField('password', e.target.value)}
                      className="h-11 pl-10 pr-10 border-[#E5E7EB] focus:border-[#0A3D2E] focus:ring-[#0A3D2E]"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#0A3D2E]"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {/* Password strength indicator */}
                  {form.password && (
                    <div className="mt-2 space-y-1.5">
                      <div className="flex gap-1">
                        {[0, 1, 2].map((i) => (
                          <div
                            key={i}
                            className={`h-1 flex-1 rounded-full transition-colors ${
                              i < passwordStrength
                                ? passwordStrength === 3
                                  ? 'bg-[#0A3D2E]'
                                  : passwordStrength === 2
                                    ? 'bg-[#D4AF37]'
                                    : 'bg-red-400'
                                : 'bg-[#E5E7EB]'
                            }`}
                          />
                        ))}
                      </div>
                      {passwordRequirements.map((req) => (
                        <div key={req.label} className="flex items-center gap-1.5">
                          <Check
                            className={`h-3 w-3 ${
                              req.test(form.password) ? 'text-[#0A3D2E]' : 'text-[#E5E7EB]'
                            }`}
                          />
                          <span
                            className={`text-xs ${
                              req.test(form.password) ? 'text-[#0A3D2E]' : 'text-[#6B7280]'
                            }`}
                          >
                            {req.label}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setStep(1)}
                    className="flex-1 h-11 border-[#0A3D2E] text-[#0A3D2E]"
                  >
                    Back
                  </Button>
                  <Button
                    type="submit"
                    disabled={isLoading}
                    className="flex-[2] h-11 bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A] font-semibold shadow-md"
                  >
                    {isLoading ? (
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 border-2 border-[#1A1A1A]/30 border-t-[#1A1A1A] rounded-full animate-spin" />
                        Creating Account...
                      </div>
                    ) : (
                      <>
                        Create Account
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </>
                    )}
                  </Button>
                </div>
              </div>
            )}
          </form>

          <div className="mt-8 text-center">
            <p className="text-sm text-[#6B7280]">
              Already have an account?{' '}
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
