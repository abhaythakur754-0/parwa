'use client';

import React, { useState, useMemo } from 'react';
import Link from 'next/link';
import { Eye, EyeOff, Loader2, Mail, Lock, User, Building2, Briefcase } from 'lucide-react';

/**
 * SignupForm Component
 * 
 * Registration form with email/password validation and company setup.
 * Based on F-010: User registration
 * 
 * Features:
 * - Email validation with availability check
 * - Password strength meter (L03)
 * - Password confirmation (L01)
 * - Special character requirement (L02)
 * - Company name and industry selection
 * - Loading state
 * - Error display
 */

interface SignupFormProps {
  onSubmit: (data: SignupFormData) => Promise<void>;
  onCheckEmail?: (email: string) => Promise<boolean>;
  isLoading?: boolean;
  error?: string | null;
}

export interface SignupFormData {
  email: string;
  password: string;
  full_name: string;
  company_name: string;
  industry: string;
}

interface FormErrors {
  email?: string;
  password?: string;
  confirm_password?: string;
  full_name?: string;
  company_name?: string;
  industry?: string;
}

// Industry options based on ONBOARDING_SPEC.md
const INDUSTRIES = [
  { value: 'ecommerce', label: 'E-commerce' },
  { value: 'saas', label: 'SaaS' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'finance', label: 'Finance' },
  { value: 'education', label: 'Education' },
  { value: 'real_estate', label: 'Real Estate' },
  { value: 'manufacturing', label: 'Manufacturing' },
  { value: 'consulting', label: 'Consulting' },
  { value: 'agency', label: 'Agency' },
  { value: 'nonprofit', label: 'Non-profit' },
  { value: 'other', label: 'Other' },
];

// Password strength calculation (L03)
function getPasswordStrength(password: string): { strength: string; score: number; color: string } {
  let score = 0;
  
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[a-z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) score += 1;
  if (password.length >= 16) score += 1;

  if (score <= 2) return { strength: 'Weak', score, color: 'bg-error-500' };
  if (score <= 4) return { strength: 'Fair', score, color: 'bg-warning-500' };
  if (score <= 5) return { strength: 'Strong', score, color: 'bg-teal-500' };
  return { strength: 'Very Strong', score, color: 'bg-success-500' };
}

export function SignupForm({ onSubmit, onCheckEmail, isLoading = false, error }: SignupFormProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [industry, setIndustry] = useState('');
  
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [emailChecking, setEmailChecking] = useState(false);
  const [emailAvailable, setEmailAvailable] = useState<boolean | null>(null);

  // Password strength memoized
  const passwordStrength = useMemo(() => getPasswordStrength(password), [password]);

  // Validate email format
  const validateEmail = (value: string): string | undefined => {
    if (!value) return 'Email is required';
    const emailRegex = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(value)) return 'Please enter a valid email address';
    return undefined;
  };

  // Validate password (L02: must include special character)
  const validatePassword = (value: string): string | undefined => {
    if (!value) return 'Password is required';
    if (value.length < 8) return 'Password must be at least 8 characters';
    if (!/[A-Z]/.test(value)) return 'Password must contain at least one uppercase letter';
    if (!/[a-z]/.test(value)) return 'Password must contain at least one lowercase letter';
    if (!/\d/.test(value)) return 'Password must contain at least one digit';
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(value)) return 'Password must contain at least one special character';
    return undefined;
  };

  // Validate confirm password (L01)
  const validateConfirmPassword = (value: string): string | undefined => {
    if (!value) return 'Please confirm your password';
    if (value !== password) return 'Passwords do not match';
    return undefined;
  };

  // Validate full name
  const validateFullName = (value: string): string | undefined => {
    if (!value) return 'Full name is required';
    if (value.length < 2) return 'Name must be at least 2 characters';
    return undefined;
  };

  // Validate company name
  const validateCompanyName = (value: string): string | undefined => {
    if (!value) return 'Company name is required';
    if (value.length < 2) return 'Company name must be at least 2 characters';
    return undefined;
  };

  // Validate industry
  const validateIndustry = (value: string): string | undefined => {
    if (!value) return 'Please select an industry';
    return undefined;
  };

  // Check email availability on blur
  const handleEmailBlur = async () => {
    const emailError = validateEmail(email);
    if (emailError) {
      setFormErrors(prev => ({ ...prev, email: emailError }));
      return;
    }

    if (onCheckEmail) {
      setEmailChecking(true);
      try {
        const available = await onCheckEmail(email);
        setEmailAvailable(available);
        if (!available) {
          setFormErrors(prev => ({ ...prev, email: 'This email is already registered' }));
        } else {
          setFormErrors(prev => ({ ...prev, email: undefined }));
        }
      } catch {
        // If check fails, continue anyway
      } finally {
        setEmailChecking(false);
      }
    }
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate all fields
    const errors: FormErrors = {
      email: validateEmail(email),
      password: validatePassword(password),
      confirm_password: validateConfirmPassword(confirmPassword),
      full_name: validateFullName(fullName),
      company_name: validateCompanyName(companyName),
      industry: validateIndustry(industry),
    };

    // Remove undefined errors
    Object.keys(errors).forEach(key => {
      if (errors[key as keyof FormErrors] === undefined) {
        delete errors[key as keyof FormErrors];
      }
    });

    // Check if email was verified as available
    if (emailAvailable === false) {
      errors.email = 'This email is already registered';
    }

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    setIsSubmitting(true);
    try {
      await onSubmit({
        email,
        password,
        full_name: fullName,
        company_name: companyName,
        industry,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const isDisabled = isLoading || isSubmitting || emailChecking;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Email Field */}
      <div>
        <label htmlFor="email" className="label">
          Email address
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Mail className="h-5 w-5 text-white/40" />
          </div>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setEmailAvailable(null);
              if (formErrors.email) {
                setFormErrors(prev => ({ ...prev, email: undefined }));
              }
            }}
            onBlur={handleEmailBlur}
            className={`input pl-10 ${formErrors.email ? 'input-error' : ''}`}
            placeholder="you@example.com"
            disabled={isDisabled}
          />
          {emailChecking && (
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
              <Loader2 className="h-5 w-5 text-teal-400 animate-spin" />
            </div>
          )}
          {emailAvailable === true && !emailChecking && (
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
              <svg className="h-5 w-5 text-success-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
          )}
        </div>
        {formErrors.email && (
          <p className="error-text">{formErrors.email}</p>
        )}
      </div>

      {/* Full Name Field */}
      <div>
        <label htmlFor="full_name" className="label">
          Full name
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <User className="h-5 w-5 text-white/40" />
          </div>
          <input
            id="full_name"
            name="full_name"
            type="text"
            autoComplete="name"
            required
            value={fullName}
            onChange={(e) => {
              setFullName(e.target.value);
              if (formErrors.full_name) {
                setFormErrors(prev => ({ ...prev, full_name: undefined }));
              }
            }}
            className={`input pl-10 ${formErrors.full_name ? 'input-error' : ''}`}
            placeholder="John Doe"
            disabled={isDisabled}
          />
        </div>
        {formErrors.full_name && (
          <p className="error-text">{formErrors.full_name}</p>
        )}
      </div>

      {/* Company Name Field */}
      <div>
        <label htmlFor="company_name" className="label">
          Company name
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Building2 className="h-5 w-5 text-white/40" />
          </div>
          <input
            id="company_name"
            name="company_name"
            type="text"
            autoComplete="organization"
            required
            value={companyName}
            onChange={(e) => {
              setCompanyName(e.target.value);
              if (formErrors.company_name) {
                setFormErrors(prev => ({ ...prev, company_name: undefined }));
              }
            }}
            className={`input pl-10 ${formErrors.company_name ? 'input-error' : ''}`}
            placeholder="Acme Inc."
            disabled={isDisabled}
          />
        </div>
        {formErrors.company_name && (
          <p className="error-text">{formErrors.company_name}</p>
        )}
      </div>

      {/* Industry Field */}
      <div>
        <label htmlFor="industry" className="label">
          Industry
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Briefcase className="h-5 w-5 text-white/40" />
          </div>
          <select
            id="industry"
            name="industry"
            required
            value={industry}
            onChange={(e) => {
              setIndustry(e.target.value);
              if (formErrors.industry) {
                setFormErrors(prev => ({ ...prev, industry: undefined }));
              }
            }}
            className={`input pl-10 appearance-none ${formErrors.industry ? 'input-error' : ''}`}
            disabled={isDisabled}
          >
            <option value="">Select your industry</option>
            {INDUSTRIES.map((ind) => (
              <option key={ind.value} value={ind.value}>
                {ind.label}
              </option>
            ))}
          </select>
          <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
            <svg className="h-5 w-5 text-white/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
        {formErrors.industry && (
          <p className="error-text">{formErrors.industry}</p>
        )}
      </div>

      {/* Password Field */}
      <div>
        <label htmlFor="password" className="label">
          Password
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Lock className="h-5 w-5 text-white/40" />
          </div>
          <input
            id="password"
            name="password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            required
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (formErrors.password) {
                setFormErrors(prev => ({ ...prev, password: undefined }));
              }
            }}
            className={`input pl-10 pr-10 ${formErrors.password ? 'input-error' : ''}`}
            placeholder="••••••••"
            disabled={isDisabled}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-white/40 hover:text-white/60 transition-colors"
            tabIndex={-1}
          >
            {showPassword ? (
              <EyeOff className="h-5 w-5" />
            ) : (
              <Eye className="h-5 w-5" />
            )}
          </button>
        </div>
        
        {/* Password Strength Meter (L03) */}
        {password && (
          <div className="mt-2 space-y-1">
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 ${passwordStrength.color}`}
                  style={{ width: `${(passwordStrength.score / 7) * 100}%` }}
                />
              </div>
              <span className="text-xs text-white/60">{passwordStrength.strength}</span>
            </div>
            <p className="text-xs text-white/40">
              Use 8+ characters with uppercase, lowercase, numbers, and special characters
            </p>
          </div>
        )}
        
        {formErrors.password && (
          <p className="error-text">{formErrors.password}</p>
        )}
      </div>

      {/* Confirm Password Field */}
      <div>
        <label htmlFor="confirm_password" className="label">
          Confirm password
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Lock className="h-5 w-5 text-white/40" />
          </div>
          <input
            id="confirm_password"
            name="confirm_password"
            type={showConfirmPassword ? 'text' : 'password'}
            autoComplete="new-password"
            required
            value={confirmPassword}
            onChange={(e) => {
              setConfirmPassword(e.target.value);
              if (formErrors.confirm_password) {
                setFormErrors(prev => ({ ...prev, confirm_password: undefined }));
              }
            }}
            className={`input pl-10 pr-10 ${formErrors.confirm_password ? 'input-error' : ''}`}
            placeholder="••••••••"
            disabled={isDisabled}
          />
          <button
            type="button"
            onClick={() => setShowConfirmPassword(!showConfirmPassword)}
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-white/40 hover:text-white/60 transition-colors"
            tabIndex={-1}
          >
            {showConfirmPassword ? (
              <EyeOff className="h-5 w-5" />
            ) : (
              <Eye className="h-5 w-5" />
            )}
          </button>
        </div>
        {formErrors.confirm_password && (
          <p className="error-text">{formErrors.confirm_password}</p>
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
            Creating account...
          </>
        ) : (
          'Create account'
        )}
      </button>

      {/* Sign In Link */}
      <p className="text-center text-sm text-white/60">
        Already have an account?{' '}
        <Link
          href="/login"
          className="text-teal-400 hover:text-teal-300 font-medium transition-colors"
        >
          Sign in
        </Link>
      </p>
    </form>
  );
}

export default SignupForm;
