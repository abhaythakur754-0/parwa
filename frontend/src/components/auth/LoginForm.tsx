'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Eye, EyeOff, Loader2, Mail, Lock } from 'lucide-react';

/**
 * LoginForm Component
 * 
 * Email/password login form with validation.
 * Based on F-010: Email/password login
 * 
 * Features:
 * - Email validation
 * - Password visibility toggle
 * - Loading state
 * - Error display
 * - Link to signup
 * - Link to forgot password
 */

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

  // Validate email format
  const validateEmail = (value: string): string | undefined => {
    if (!value) {
      return 'Email is required';
    }
    const emailRegex = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(value)) {
      return 'Please enter a valid email address';
    }
    return undefined;
  };

  // Validate password
  const validatePassword = (value: string): string | undefined => {
    if (!value) {
      return 'Password is required';
    }
    return undefined;
  };

  // Handle email change
  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setEmail(value);
    if (formErrors.email) {
      setFormErrors(prev => ({ ...prev, email: validateEmail(value) }));
    }
  };

  // Handle password change
  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setPassword(value);
    if (formErrors.password) {
      setFormErrors(prev => ({ ...prev, password: validatePassword(value) }));
    }
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate all fields
    const errors: FormErrors = {
      email: validateEmail(email),
      password: validatePassword(password),
    };

    // Remove undefined errors
    Object.keys(errors).forEach(key => {
      if (errors[key as keyof FormErrors] === undefined) {
        delete errors[key as keyof FormErrors];
      }
    });

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    setIsSubmitting(true);
    try {
      await onSubmit(email, password);
    } finally {
      setIsSubmitting(false);
    }
  };

  const isDisabled = isLoading || isSubmitting;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Email Field */}
      <div>
        <label htmlFor="email" className="label">
          Email address
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Mail className="h-5 w-5 text-gray-400" />
          </div>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={handleEmailChange}
            className={`input pl-10 ${formErrors.email ? 'input-error' : ''}`}
            placeholder="you@example.com"
            disabled={isDisabled}
          />
        </div>
        {formErrors.email && (
          <p className="error-text">{formErrors.email}</p>
        )}
      </div>

      {/* Password Field */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label htmlFor="password" className="label mb-0">
            Password
          </label>
          <Link
            href="/forgot-password"
            className="text-sm text-emerald-600 hover:text-emerald-500 transition-colors"
          >
            Forgot password?
          </Link>
        </div>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Lock className="h-5 w-5 text-gray-400" />
          </div>
          <input
            id="password"
            name="password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="current-password"
            required
            value={password}
            onChange={handlePasswordChange}
            className={`input pl-10 pr-10 ${formErrors.password ? 'input-error' : ''}`}
            placeholder="••••••••"
            disabled={isDisabled}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-500 transition-colors"
            tabIndex={-1}
          >
            {showPassword ? (
              <EyeOff className="h-5 w-5" />
            ) : (
              <Eye className="h-5 w-5" />
            )}
          </button>
        </div>
        {formErrors.password && (
          <p className="error-text">{formErrors.password}</p>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="p-3 rounded-lg bg-error-500/10 border border-error-500/20">
          <p className="text-sm text-error-400">{error}</p>
        </div>
      )}

      {/* Submit Button */}
      <button
        type="submit"
        disabled={isDisabled}
        className="btn btn-primary w-full py-3"
      >
        {isDisabled ? (
          <>
            <Loader2 className="w-5 h-5 mr-2 animate-spin" />
            Signing in...
          </>
        ) : (
          'Sign in'
        )}
      </button>

      {/* Sign Up Link */}
      <p className="text-center text-sm text-gray-500">
        Don&apos;t have an account?{' '}
        <Link
          href="/signup"
          className="text-emerald-600 hover:text-emerald-500 font-medium transition-colors"
        >
          Sign up
        </Link>
      </p>
    </form>
  );
}

export default LoginForm;
