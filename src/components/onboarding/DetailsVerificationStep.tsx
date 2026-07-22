'use client';

import React, { useState, useEffect } from 'react';
import { Loader2, CheckCircle2, XCircle, Shield, ChevronDown, ChevronUp, Globe, Mail, User } from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';

interface DetailsVerificationStepProps {
  onComplete: (data: {
    full_name: string;
    company_url: string;
    work_email: string;
    accept_terms: boolean;
    accept_privacy: boolean;
    accept_ai_data: boolean;
  }) => void;
  initialFullName?: string;
  isSubmitting?: boolean;
}

export function DetailsVerificationStep({
  onComplete,
  initialFullName = '',
  isSubmitting = false,
}: DetailsVerificationStepProps) {
  // ── Form state ──
  const [fullName, setFullName] = useState(initialFullName);
  const [companyUrl, setCompanyUrl] = useState('');
  const [workEmail, setWorkEmail] = useState('');

  // ── URL validation state ──
  const [urlChecking, setUrlChecking] = useState(false);
  const [urlValid, setUrlValid] = useState<boolean | null>(null);
  const [urlError, setUrlError] = useState<string | null>(null);

  // ── OTP state ──
  const [otpSent, setOtpSent] = useState(false);
  const [otpSending, setOtpSending] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  const [otpVerifying, setOtpVerifying] = useState(false);
  const [otpVerified, setOtpVerified] = useState(false);

  // ── Legal state ──
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);
  const [acceptAiData, setAcceptAiData] = useState(false);
  const [expandedCard, setExpandedCard] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allAccepted = acceptTerms && acceptPrivacy && acceptAiData;

  // ── URL validation (debounced) ──
  useEffect(() => {
    if (!companyUrl || companyUrl.length < 4) {
      setUrlValid(null);
      setUrlError(null);
      return;
    }

    // Add https:// if missing
    let urlToCheck = companyUrl.trim();
    if (!urlToCheck.startsWith('http://') && !urlToCheck.startsWith('https://')) {
      urlToCheck = 'https://' + urlToCheck;
    }

    setUrlChecking(true);
    setUrlValid(null);
    setUrlError(null);

    const timer = setTimeout(async () => {
      try {
        const res = await fetch('/api/onboarding/verify-url', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: urlToCheck }),
        });
        const data = await res.json();
        if (data.valid) {
          setUrlValid(true);
          setUrlError(null);
        } else {
          setUrlValid(false);
          setUrlError(data.message || 'Website not reachable');
        }
      } catch {
        setUrlValid(false);
        setUrlError('Could not verify website');
      } finally {
        setUrlChecking(false);
      }
    }, 800);

    return () => clearTimeout(timer);
  }, [companyUrl]);

  // ── Send OTP ──
  const handleSendOtp = async () => {
    if (!workEmail || !workEmail.includes('@')) {
      toast.error('Please enter a valid email address');
      return;
    }

    setOtpSending(true);
    try {
      const res = await fetch('/api/verification/send-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: workEmail }),
      });

      if (res.ok) {
        setOtpSent(true);
        toast.success('OTP sent to your email!');
      } else {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || data.message || 'Failed to send OTP');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to send OTP');
    } finally {
      setOtpSending(false);
    }
  };

  // ── Verify OTP ──
  const handleVerifyOtp = async () => {
    if (!otpCode || otpCode.length < 4) {
      toast.error('Please enter the OTP code');
      return;
    }

    setOtpVerifying(true);
    try {
      const res = await fetch('/api/verification/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: workEmail, otp: otpCode }),
      });

      if (res.ok) {
        setOtpVerified(true);
        toast.success('Email verified!');
      } else {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || data.message || 'Invalid OTP');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Invalid OTP');
    } finally {
      setOtpVerifying(false);
    }
  };

  // ── Can submit? ──
  const canSubmit =
    fullName.trim().length >= 2 &&
    urlValid === true &&
    otpVerified === true &&
    allAccepted;

  // ── Submit ──
  const handleSubmit = async () => {
    if (!canSubmit) {
      setError('Please complete all fields before continuing.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      // Save legal consent
      await fetch('/api/onboarding/legal-consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          accept_terms: acceptTerms,
          accept_privacy: acceptPrivacy,
          accept_ai_data: acceptAiData,
        }),
      }).catch(() => {}); // non-blocking

      onComplete({
        full_name: fullName.trim(),
        company_url: companyUrl.trim(),
        work_email: workEmail.trim().toLowerCase(),
        accept_terms: acceptTerms,
        accept_privacy: acceptPrivacy,
        accept_ai_data: acceptAiData,
      });
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const isLoading = submitting || isSubmitting;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-2">
        <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center shadow-xl shadow-orange-500/20 mb-4">
          <Shield className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold text-white">Verify Your Business</h2>
        <p className="text-orange-200/50 text-sm max-w-md mx-auto">
          Tell us about yourself and verify your business email to get started.
        </p>
      </div>

      {/* ── Full Name ── */}
      <div className="space-y-2">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
          Full Name
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <User className="w-5 h-5 text-orange-400/50" />
          </div>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="John Doe"
            maxLength={100}
            className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/[0.03] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 focus:ring-1 focus:ring-orange-500/20 transition-colors"
          />
        </div>
        {fullName && fullName.trim().length < 2 && (
          <p className="text-xs text-zinc-600">At least 2 characters required</p>
        )}
      </div>

      {/* ── Company URL ── */}
      <div className="space-y-2">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
          Company Website
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Globe className="w-5 h-5 text-orange-400/50" />
          </div>
          <input
            type="text"
            value={companyUrl}
            onChange={(e) => { setCompanyUrl(e.target.value); setUrlValid(null); }}
            placeholder="acme.com"
            maxLength={255}
            className="w-full pl-10 pr-10 py-3 rounded-xl bg-white/[0.03] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 focus:ring-1 focus:ring-orange-500/20 transition-colors"
          />
          {urlChecking && (
            <div className="absolute inset-y-0 right-3 flex items-center">
              <Loader2 className="w-4 h-4 text-zinc-500 animate-spin" />
            </div>
          )}
          {!urlChecking && urlValid === true && (
            <div className="absolute inset-y-0 right-3 flex items-center">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>
          )}
          {!urlChecking && urlValid === false && (
            <div className="absolute inset-y-0 right-3 flex items-center">
              <XCircle className="w-4 h-4 text-red-400" />
            </div>
          )}
        </div>
        {urlValid === true && <p className="text-xs text-emerald-400">✓ Website verified</p>}
        {urlValid === false && urlError && <p className="text-xs text-red-400">✗ {urlError}</p>}
        {companyUrl && companyUrl.length < 4 && <p className="text-xs text-zinc-600">Enter your company website URL</p>}
      </div>

      {/* ── Work Email + OTP ── */}
      <div className="space-y-2">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
          Work Email
        </label>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Mail className="w-5 h-5 text-orange-400/50" />
            </div>
            <input
              type="email"
              value={workEmail}
              onChange={(e) => { setWorkEmail(e.target.value); setOtpSent(false); setOtpVerified(false); }}
              placeholder="john@acme.com"
              maxLength={254}
              disabled={otpVerified}
              className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/[0.03] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 focus:ring-1 focus:ring-orange-500/20 transition-colors disabled:opacity-60"
            />
            {otpVerified && (
              <div className="absolute inset-y-0 right-3 flex items-center">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              </div>
            )}
          </div>
          {!otpSent && !otpVerified && (
            <button
              onClick={handleSendOtp}
              disabled={!workEmail.includes('@') || otpSending}
              className="px-4 py-3 rounded-xl bg-orange-500/20 text-orange-400 text-xs font-medium border border-orange-500/30 hover:bg-orange-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {otpSending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Send OTP'}
            </button>
          )}
        </div>

        {/* OTP input */}
        {otpSent && !otpVerified && (
          <div className="flex gap-2 mt-2">
            <input
              type="text"
              value={otpCode}
              onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="Enter 6-digit OTP"
              maxLength={6}
              className="flex-1 px-4 py-3 rounded-xl bg-white/[0.03] border border-white/[0.08] text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 focus:ring-1 focus:ring-orange-500/20 transition-colors text-center text-lg tracking-widest"
            />
            <button
              onClick={handleVerifyOtp}
              disabled={otpCode.length < 4 || otpVerifying}
              className="px-4 py-3 rounded-xl bg-emerald-500/20 text-emerald-400 text-xs font-medium border border-emerald-500/30 hover:bg-emerald-500/30 transition-colors disabled:opacity-50"
            >
              {otpVerifying ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Verify'}
            </button>
          </div>
        )}
        {otpSent && !otpVerified && (
          <p className="text-xs text-zinc-600">OTP sent to {workEmail}. Didn't receive it? <button onClick={handleSendOtp} className="text-orange-400 hover:underline">Resend</button></p>
        )}
        {otpVerified && <p className="text-xs text-emerald-400">✓ Email verified</p>}
      </div>

      {/* ── Legal Compliance ── */}
      <div className="space-y-3">
        <label className="text-xs text-orange-200/40 uppercase tracking-wider font-medium">
          Legal Agreements
        </label>

        {/* Terms of Service */}
        <div className="rounded-xl bg-white/[0.02] border border-white/[0.06] overflow-hidden">
          <button
            onClick={() => setExpandedCard(expandedCard === 'terms' ? null : 'terms')}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/[0.02] transition-colors"
          >
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={acceptTerms}
                onChange={(e) => setAcceptTerms(e.target.checked)}
                onClick={(e) => e.stopPropagation()}
                className="w-4 h-4 rounded border-white/20 bg-white/5 text-orange-500 focus:ring-orange-500/20"
              />
              <span className="text-sm text-zinc-300">I accept the Terms of Service</span>
            </div>
            {expandedCard === 'terms' ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
          </button>
          {expandedCard === 'terms' && (
            <div className="px-4 py-3 text-xs text-zinc-500 border-t border-white/[0.04]">
              By accepting, you agree to PARWA's Terms of Service. You consent to use PARWA's AI-powered customer support platform in accordance with our terms. You are responsible for all activity under your account and must not misuse the service.
            </div>
          )}
        </div>

        {/* Privacy Policy */}
        <div className="rounded-xl bg-white/[0.02] border border-white/[0.06] overflow-hidden">
          <button
            onClick={() => setExpandedCard(expandedCard === 'privacy' ? null : 'privacy')}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/[0.02] transition-colors"
          >
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={acceptPrivacy}
                onChange={(e) => setAcceptPrivacy(e.target.checked)}
                onClick={(e) => e.stopPropagation()}
                className="w-4 h-4 rounded border-white/20 bg-white/5 text-orange-500 focus:ring-orange-500/20"
              />
              <span className="text-sm text-zinc-300">I accept the Privacy Policy</span>
            </div>
            {expandedCard === 'privacy' ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
          </button>
          {expandedCard === 'privacy' && (
            <div className="px-4 py-3 text-xs text-zinc-500 border-t border-white/[0.04]">
              PARWA collects and processes your data to provide AI-powered customer support services. We do not sell your data. Your data is stored securely and used only for providing and improving our services. You can request data deletion at any time.
            </div>
          )}
        </div>

        {/* AI Data Processing */}
        <div className="rounded-xl bg-white/[0.02] border border-white/[0.06] overflow-hidden">
          <button
            onClick={() => setExpandedCard(expandedCard === 'ai' ? null : 'ai')}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/[0.02] transition-colors"
          >
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={acceptAiData}
                onChange={(e) => setAcceptAiData(e.target.checked)}
                onClick={(e) => e.stopPropagation()}
                className="w-4 h-4 rounded border-white/20 bg-white/5 text-orange-500 focus:ring-orange-500/20"
              />
              <span className="text-sm text-zinc-300">I consent to AI Data Processing</span>
            </div>
            {expandedCard === 'ai' ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
          </button>
          {expandedCard === 'ai' && (
            <div className="px-4 py-3 text-xs text-zinc-500 border-t border-white/[0.04]">
              PARWA uses AI models to process customer support tickets. Your customer data may be processed by AI to generate responses. We use industry-standard security practices. AI responses are verified before delivery to customers.
            </div>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-xs text-red-400">
          {error}
        </div>
      )}

      {/* Continue button */}
      <button
        onClick={handleSubmit}
        disabled={!canSubmit || isLoading}
        className={cn(
          'w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl text-sm font-bold transition-all',
          canSubmit && !isLoading
            ? 'bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40 hover:-translate-y-0.5'
            : 'bg-white/[0.04] text-zinc-600 cursor-not-allowed'
        )}
      >
        {isLoading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Saving...
          </>
        ) : (
          'Continue'
        )}
      </button>
    </div>
  );
}
