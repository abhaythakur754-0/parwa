'use client';

import React, { useState, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { Eye, EyeOff, Loader2, Mail, Lock, User, Building2, Briefcase } from 'lucide-react';

const MAX_EMAIL_LENGTH = 255;
const MAX_NAME_LENGTH = 255;
const MAX_COMPANY_NAME_LENGTH = 255;
const MAX_PASSWORD_LENGTH = 128;

function sanitizeInput(text: string): string {
  if (!text || typeof text !== 'string') return '';
  let sanitized = text;
  sanitized = sanitized.replace(/<[^>]*>/g, '');
  sanitized = sanitized.replace(/javascript:/gi, '');
  sanitized = sanitized.replace(/on\w+\s*=/gi, '');
  sanitized = sanitized.replace(/data:/gi, '');
  sanitized = sanitized.replace(/vbscript:/gi, '');
  return sanitized.trim();
}

function truncateText(text: string, maxLength: number): string {
  if (!text) return '';
  return text.length > maxLength ? text.slice(0, maxLength) : text;
}

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

function getPasswordStrength(password: string): { strength: string; score: number; color: string } {
  let score = 0;
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[a-z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) score += 1;
  if (password.length >= 16) score += 1;
  if (score <= 2) return { strength: 'Weak', score, color: 'bg-rose-500' };
  if (score <= 4) return { strength: 'Fair', score, color: 'bg-amber-500' };
  if (score <= 5) return { strength: 'Strong', score, color: 'bg-emerald-500' };
  return { strength: 'Very Strong', score, color: 'bg-emerald-400' };
}

const darkInputClass = "w-full pl-10 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-emerald-200/30 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500/40 transition-all duration-300 appearance-none";
const darkInputErrorClass = "w-full pl-10 pr-4 py-3 bg-white/5 border border-rose-500/40 rounded-xl text-white placeholder-emerald-200/30 focus:outline-none focus:ring-2 focus:ring-rose-500/30 focus:border-rose-500/40 transition-all duration-300 appearance-none";
const darkSelectClass = "w-full pl-10 pr-10 py-3 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500/40 transition-all duration-300 appearance-none";
const darkSelectErrorClass = "w-full pl-10 pr-10 py-3 bg-white/5 border border-rose-500/40 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-rose-500/30 focus:border-rose-500/40 transition-all duration-300 appearance-none";

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

  const passwordStrength = useMemo(() => getPasswordStrength(password), [password]);

  const validateEmail = (value: string): string | undefined => {
    if (!value) return 'Email is required';
    if (value.length > MAX_EMAIL_LENGTH) return `Email must be less than ${MAX_EMAIL_LENGTH} characters`;
    if (/<|>|javascript:|data:/i.test(value)) return 'Invalid characters in email';
    const emailRegex = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(value)) return 'Please enter a valid email address';
    return undefined;
  };

  const validatePassword = (value: string): string | undefined => {
    if (!value) return 'Password is required';
    if (value.length < 8) return 'Password must be at least 8 characters';
    if (value.length > MAX_PASSWORD_LENGTH) return `Password must be less than ${MAX_PASSWORD_LENGTH} characters`;
    if (!/[A-Z]/.test(value)) return 'Password must contain at least one uppercase letter';
    if (!/[a-z]/.test(value)) return 'Password must contain at least one lowercase letter';
    if (!/\d/.test(value)) return 'Password must contain at least one digit';
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(value)) return 'Password must contain at least one special character';
    return undefined;
  };

  const validateConfirmPassword = (value: string): string | undefined => {
    if (!value) return 'Please confirm your password';
    if (value !== password) return 'Passwords do not match';
    return undefined;
  };

  const validateFullName = (value: string): string | undefined => {
    if (!value) return 'Full name is required';
    if (value.length < 2) return 'Name must be at least 2 characters';
    if (value.length > MAX_NAME_LENGTH) return `Name must be less than ${MAX_NAME_LENGTH} characters`;
    if (/<|>|javascript:|on\w+=/i.test(value)) return 'Invalid characters in name';
    return undefined;
  };

  const validateCompanyName = (value: string): string | undefined => {
    if (!value) return 'Company name is required';
    if (value.length < 2) return 'Company name must be at least 2 characters';
    if (value.length > MAX_COMPANY_NAME_LENGTH) return `Company name must be less than ${MAX_COMPANY_NAME_LENGTH} characters`;
    if (/<|>|javascript:|on\w+=/i.test(value)) return 'Invalid characters in company name';
    return undefined;
  };

  const validateIndustry = (value: string): string | undefined => {
    if (!value) return 'Please select an industry';
    return undefined;
  };

  const handleEmailBlur = async () => {
    const emailError = validateEmail(email);
    if (emailError) { setFormErrors(prev => ({ ...prev, email: emailError })); return; }
    if (onCheckEmail) {
      setEmailChecking(true);
      try {
        const available = await onCheckEmail(email);
        setEmailAvailable(available);
        if (!available) setFormErrors(prev => ({ ...prev, email: 'This email is already registered' }));
        else setFormErrors(prev => ({ ...prev, email: undefined }));
      } catch { } finally { setEmailChecking(false); }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting || isLoading) return;
    const errors: FormErrors = {
      email: validateEmail(email), password: validatePassword(password),
      confirm_password: validateConfirmPassword(confirmPassword),
      full_name: validateFullName(fullName), company_name: validateCompanyName(companyName),
      industry: validateIndustry(industry),
    };
    Object.keys(errors).forEach(key => { if (errors[key as keyof FormErrors] === undefined) delete errors[key as keyof FormErrors]; });
    if (emailAvailable === false) errors.email = 'This email is already registered';
    if (Object.keys(errors).length > 0) { setFormErrors(errors); return; }
    setIsSubmitting(true);
    try {
      const sanitizedData = {
        email: sanitizeInput(truncateText(email, MAX_EMAIL_LENGTH)),
        password: truncateText(password, MAX_PASSWORD_LENGTH),
        full_name: sanitizeInput(truncateText(fullName, MAX_NAME_LENGTH)),
        company_name: sanitizeInput(truncateText(companyName, MAX_COMPANY_NAME_LENGTH)),
        industry: industry,
      };
      await onSubmit(sanitizedData);
    } catch (submitError) {
      setPassword(''); setConfirmPassword('');
    } finally { setIsSubmitting(false); }
  };

  const isDisabled = isLoading || isSubmitting || emailChecking;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Email Field */}
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-emerald-200/70 mb-1.5">Email address</label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Mail className="h-5 w-5 text-emerald-400/50" />
          </div>
          <input id="email" name="email" type="email" autoComplete="email" required value={email}
            onChange={(e) => { setEmail(e.target.value); setEmailAvailable(null); if (formErrors.email) setFormErrors(prev => ({ ...prev, email: undefined })); }}
            onBlur={handleEmailBlur}
            className={formErrors.email ? darkInputErrorClass : darkInputClass}
            placeholder="you@example.com" disabled={isDisabled} maxLength={MAX_EMAIL_LENGTH} />
          {emailChecking && (
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
              <Loader2 className="h-5 w-5 text-emerald-400 animate-spin" />
            </div>
          )}
          {emailAvailable === true && !emailChecking && (
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
              <svg className="h-5 w-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
          )}
        </div>
        {formErrors.email && <p className="mt-1 text-sm text-rose-300">{formErrors.email}</p>}
      </div>

      {/* Full Name */}
      <div>
        <label htmlFor="full_name" className="block text-sm font-medium text-emerald-200/70 mb-1.5">Full name</label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <User className="h-5 w-5 text-emerald-400/50" />
          </div>
          <input id="full_name" name="full_name" type="text" autoComplete="name" required value={fullName}
            onChange={(e) => { setFullName(e.target.value); if (formErrors.full_name) setFormErrors(prev => ({ ...prev, full_name: undefined })); }}
            className={formErrors.full_name ? darkInputErrorClass : darkInputClass}
            placeholder="John Doe" disabled={isDisabled} maxLength={MAX_NAME_LENGTH} />
        </div>
        {formErrors.full_name && <p className="mt-1 text-sm text-rose-300">{formErrors.full_name}</p>}
      </div>

      {/* Company Name */}
      <div>
        <label htmlFor="company_name" className="block text-sm font-medium text-emerald-200/70 mb-1.5">Company name</label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Building2 className="h-5 w-5 text-emerald-400/50" />
          </div>
          <input id="company_name" name="company_name" type="text" autoComplete="organization" required value={companyName}
            onChange={(e) => { setCompanyName(e.target.value); if (formErrors.company_name) setFormErrors(prev => ({ ...prev, company_name: undefined })); }}
            className={formErrors.company_name ? darkInputErrorClass : darkInputClass}
            placeholder="Acme Inc." disabled={isDisabled} maxLength={MAX_COMPANY_NAME_LENGTH} />
        </div>
        {formErrors.company_name && <p className="mt-1 text-sm text-rose-300">{formErrors.company_name}</p>}
      </div>

      {/* Industry */}
      <div>
        <label htmlFor="industry" className="block text-sm font-medium text-emerald-200/70 mb-1.5">Industry</label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Briefcase className="h-5 w-5 text-emerald-400/50" />
          </div>
          <select id="industry" name="industry" required value={industry}
            onChange={(e) => { setIndustry(e.target.value); if (formErrors.industry) setFormErrors(prev => ({ ...prev, industry: undefined })); }}
            className={formErrors.industry ? darkSelectErrorClass : darkSelectClass}
            disabled={isDisabled}>
            <option value="" className="bg-[#022C22] text-white">Select your industry</option>
            {INDUSTRIES.map((ind) => (
              <option key={ind.value} value={ind.value} className="bg-[#022C22] text-white">{ind.label}</option>
            ))}
          </select>
          <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
            <svg className="h-5 w-5 text-emerald-400/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
        {formErrors.industry && <p className="mt-1 text-sm text-rose-300">{formErrors.industry}</p>}
      </div>

      {/* Password */}
      <div>
        <label htmlFor="password" className="block text-sm font-medium text-emerald-200/70 mb-1.5">Password</label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Lock className="h-5 w-5 text-emerald-400/50" />
          </div>
          <input id="password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="new-password" required value={password}
            onChange={(e) => { setPassword(e.target.value); if (formErrors.password) setFormErrors(prev => ({ ...prev, password: undefined })); }}
            className={`w-full pl-10 pr-10 bg-white/5 border rounded-xl text-white placeholder-emerald-200/30 focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-300 ${
              formErrors.password ? 'border-rose-500/40 focus:ring-rose-500/30' : 'border-white/10 focus:ring-emerald-500/30 focus:border-emerald-500/40'
            }`}
            placeholder="Create a strong password" disabled={isDisabled} maxLength={MAX_PASSWORD_LENGTH} />
          <button type="button" onClick={() => setShowPassword(!showPassword)}
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-emerald-400/50 hover:text-emerald-400 transition-colors" tabIndex={-1}>
            {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
          </button>
        </div>
        {password && (
          <div className="mt-2 space-y-1">
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div className={`h-full transition-all duration-300 ${passwordStrength.color}`} style={{ width: `${(passwordStrength.score / 7) * 100}%` }} />
              </div>
              <span className="text-xs text-emerald-200/40">{passwordStrength.strength}</span>
            </div>
            <p className="text-xs text-emerald-200/25">Use 8+ characters with uppercase, lowercase, numbers, and special characters</p>
          </div>
        )}
        {formErrors.password && <p className="mt-1 text-sm text-rose-300">{formErrors.password}</p>}
      </div>

      {/* Confirm Password */}
      <div>
        <label htmlFor="confirm_password" className="block text-sm font-medium text-emerald-200/70 mb-1.5">Confirm password</label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Lock className="h-5 w-5 text-emerald-400/50" />
          </div>
          <input id="confirm_password" name="confirm_password" type={showConfirmPassword ? 'text' : 'password'} autoComplete="new-password" required value={confirmPassword}
            onChange={(e) => { setConfirmPassword(e.target.value); if (formErrors.confirm_password) setFormErrors(prev => ({ ...prev, confirm_password: undefined })); }}
            className={`w-full pl-10 pr-10 bg-white/5 border rounded-xl text-white placeholder-emerald-200/30 focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-300 ${
              formErrors.confirm_password ? 'border-rose-500/40 focus:ring-rose-500/30' : 'border-white/10 focus:ring-emerald-500/30 focus:border-emerald-500/40'
            }`}
            placeholder="Confirm your password" disabled={isDisabled} maxLength={MAX_PASSWORD_LENGTH} />
          <button type="button" onClick={() => setShowConfirmPassword(!showConfirmPassword)}
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-emerald-400/50 hover:text-emerald-400 transition-colors" tabIndex={-1}>
            {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
          </button>
        </div>
        {formErrors.confirm_password && <p className="mt-1 text-sm text-rose-300">{formErrors.confirm_password}</p>}
      </div>

      {/* Error */}
      {error && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
          <p className="text-sm text-rose-300">{error}</p>
        </div>
      )}

      {/* Submit */}
      <button type="submit" disabled={isDisabled}
        className="w-full py-3 px-4 bg-gradient-to-r from-emerald-500 to-emerald-400 hover:from-emerald-400 hover:to-emerald-300 text-[#022C22] font-semibold rounded-xl transition-all duration-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/25 hover:shadow-emerald-600/40">
        {isDisabled ? (
          <><Loader2 className="w-5 h-5 animate-spin" /> Creating account...</>
        ) : 'Create account'}
      </button>

      {/* Sign In Link */}
      <p className="text-center text-sm text-emerald-200/40">
        Already have an account?{' '}
        <Link href="/login" className="text-emerald-400 hover:text-emerald-300 font-medium transition-colors">Sign in</Link>
      </p>
    </form>
  );
}

export default SignupForm;
