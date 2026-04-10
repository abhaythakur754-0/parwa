'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Eye, EyeOff, Loader2, Mail, Lock } from 'lucide-react';

interface LoginFormProps {
  onSubmit: (email: string, password: string) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
}

interface FormErrors {
  email?: string;
  password?: string;
}

export function LoginForm({ onSubmit, isLoading = false, error }: LoginFormProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validateEmail = (value: string): string | undefined => {
    if (!value) return 'Email is required';
    const emailRegex = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(value)) return 'Please enter a valid email address';
    return undefined;
  };

  const validatePassword = (value: string): string | undefined => {
    if (!value) return 'Password is required';
    return undefined;
  };

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setEmail(value);
    if (formErrors.email) setFormErrors(prev => ({ ...prev, email: validateEmail(value) }));
  };

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setPassword(value);
    if (formErrors.password) setFormErrors(prev => ({ ...prev, password: validatePassword(value) }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors: FormErrors = { email: validateEmail(email), password: validatePassword(password) };
    Object.keys(errors).forEach(key => { if (errors[key as keyof FormErrors] === undefined) delete errors[key as keyof FormErrors]; });
    if (Object.keys(errors).length > 0) { setFormErrors(errors); return; }
    setIsSubmitting(true);
    try { await onSubmit(email, password); } finally { setIsSubmitting(false); }
  };

  const isDisabled = isLoading || isSubmitting;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Email Field */}
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-emerald-200/70 mb-1.5">
          Email address
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Mail className="h-5 w-5 text-emerald-400/50" />
          </div>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={handleEmailChange}
            className={`w-full pl-10 pr-4 py-3 bg-white/5 border rounded-xl text-white placeholder-emerald-200/30 focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-300 ${
              formErrors.email
                ? 'border-rose-500/40 focus:ring-rose-500/30'
                : 'border-white/10 focus:ring-emerald-500/30 focus:border-emerald-500/40'
            }`}
            placeholder="you@example.com"
            disabled={isDisabled}
          />
        </div>
        {formErrors.email && <p className="mt-1 text-sm text-rose-300">{formErrors.email}</p>}
      </div>

      {/* Password Field */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label htmlFor="password" className="block text-sm font-medium text-emerald-200/70">
            Password
          </label>
          <Link href="/forgot-password" className="text-sm text-emerald-400 hover:text-emerald-300 transition-colors">
            Forgot password?
          </Link>
        </div>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Lock className="h-5 w-5 text-emerald-400/50" />
          </div>
          <input
            id="password"
            name="password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="current-password"
            required
            value={password}
            onChange={handlePasswordChange}
            className={`w-full pl-10 pr-10 py-3 bg-white/5 border rounded-xl text-white placeholder-emerald-200/30 focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-300 ${
              formErrors.password
                ? 'border-rose-500/40 focus:ring-rose-500/30'
                : 'border-white/10 focus:ring-emerald-500/30 focus:border-emerald-500/40'
            }`}
            placeholder="Enter your password"
            disabled={isDisabled}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-emerald-400/50 hover:text-emerald-400 transition-colors"
            tabIndex={-1}
          >
            {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
          </button>
        </div>
        {formErrors.password && <p className="mt-1 text-sm text-rose-300">{formErrors.password}</p>}
      </div>

      {/* Error Message */}
      {error && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
          <p className="text-sm text-rose-300">{error}</p>
        </div>
      )}

      {/* Submit Button */}
      <button
        type="submit"
        disabled={isDisabled}
        className="w-full py-3 px-4 bg-gradient-to-r from-emerald-500 to-emerald-400 hover:from-emerald-400 hover:to-emerald-300 text-[#022C22] font-semibold rounded-xl transition-all duration-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/25 hover:shadow-emerald-600/40"
      >
        {isDisabled ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Signing in...
          </>
        ) : (
          'Sign in'
        )}
      </button>

      {/* Sign Up Link */}
      <p className="text-center text-sm text-emerald-200/40">
        Don&apos;t have an account?{' '}
        <Link href="/signup" className="text-emerald-400 hover:text-emerald-300 font-medium transition-colors">
          Sign up
        </Link>
      </p>
    </form>
  );
}

export default LoginForm;
