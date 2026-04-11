'use client';

import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Loader2, Mail, ArrowLeft, CheckCircle, Lock, Eye, EyeOff,
  ShieldCheck, KeyRound, RefreshCw,
} from 'lucide-react';
import toast from 'react-hot-toast';

// ─── Step Types ──────────────────────────────────────────────────────────────

type Step = 'email' | 'otp' | 'reset';

// ─── OTP Input Component ─────────────────────────────────────────────────────

function OTPInput({ value, onChange, disabled, error }: {
  value: string;
  onChange: (val: string) => void;
  disabled?: boolean;
  error?: boolean;
}) {
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    // Auto-focus first empty input
    const firstEmpty = value.indexOf('');
    if (firstEmpty >= 0 && inputRefs.current[firstEmpty]) {
      inputRefs.current[firstEmpty]?.focus();
    }
  }, [value]);

  const handleChange = (index: number, char: string) => {
    if (!/^\d*$/.test(char)) return;
    const newVal = value.split('');
    newVal[index] = char;
    const result = newVal.join('');
    onChange(result);
    // Auto-focus next input
    if (char && index < 5 && inputRefs.current[index + 1]) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !value[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (pasted) {
      onChange(pasted);
      const focusIdx = Math.min(pasted.length, 5);
      inputRefs.current[focusIdx]?.focus();
    }
  };

  return (
    <div className="flex justify-center gap-2 sm:gap-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <input
          key={i}
          ref={(el) => { inputRefs.current[i] = el; }}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={value[i] || ''}
          onChange={(e) => handleChange(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
          disabled={disabled}
          className={`w-10 h-12 sm:w-12 sm:h-14 text-center text-lg sm:text-xl font-bold rounded-xl border transition-all duration-300 focus:outline-none focus:ring-2 ${
            error
              ? 'border-rose-500/40 focus:ring-rose-500/30 bg-rose-500/5 text-rose-300'
              : 'border-white/10 focus:ring-orange-500/30 focus:border-orange-500/40 bg-white/5 text-white'
          }`}
          style={{ caretColor: '#FF7F11' }}
        />
      ))}
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function ForgotPasswordPage() {
  const router = useRouter();

  // Step state
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [otpSent, setOtpSent] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);

  // Password strength
  const hasUppercase = /[A-Z]/.test(newPassword);
  const hasLowercase = /[a-z]/.test(newPassword);
  const hasDigit = /\d/.test(newPassword);
  const hasSpecial = /[!@#$%^&*(),.?":{}|<>]/.test(newPassword);
  const isLongEnough = newPassword.length >= 8;
  const passwordsMatch = newPassword === confirmPassword && confirmPassword !== '';
  const isPasswordValid = hasUppercase && hasLowercase && hasDigit && hasSpecial && isLongEnough && passwordsMatch;

  // Resend cooldown timer
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendCooldown]);

  // ─── Step 1: Send OTP ─────────────────────────────────────────────────

  const handleSendOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const res = await fetch('/api/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      const data = await res.json();

      if (data.status === 'success') {
        setOtpSent(true);
        setStep('otp');
        setResendCooldown(60);
        toast.success('OTP sent to your email!', {
          style: {
            background: '#2A1A0A',
            color: '#FFF4E6',
            border: '1px solid rgba(255,127,17,0.25)',
            borderRadius: '12px',
          },
        });
      } else {
        setError(data.message);
        toast.error(data.message);
      }
    } catch {
      setError('Network error. Please try again.');
      toast.error('Network error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // ─── Resend OTP ───────────────────────────────────────────────────────

  const handleResendOTP = async () => {
    if (resendCooldown > 0) return;
    setError(null);
    setIsLoading(true);

    try {
      const res = await fetch('/api/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      const data = await res.json();

      if (data.status === 'success') {
        setOtp('');
        setResendCooldown(60);
        toast.success('New OTP sent!', {
          style: {
            background: '#2A1A0A',
            color: '#FFF4E6',
            border: '1px solid rgba(255,127,17,0.25)',
            borderRadius: '12px',
          },
        });
      } else {
        setError(data.message);
        toast.error(data.message);
      }
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // ─── Step 2: Verify OTP ───────────────────────────────────────────────

  const handleVerifyOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (otp.length !== 6) {
      setError('Please enter all 6 digits.');
      return;
    }

    setIsLoading(true);

    try {
      const res = await fetch('/api/auth/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase(), otp }),
      });
      const data = await res.json();

      if (data.status === 'success') {
        setStep('reset');
        toast.success('OTP verified!', {
          style: {
            background: '#2A1A0A',
            color: '#FFF4E6',
            border: '1px solid rgba(255,127,17,0.25)',
            borderRadius: '12px',
          },
        });
      } else {
        setError(data.message);
        toast.error(data.message);
        setOtp('');
      }
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // ─── Step 3: Reset Password ───────────────────────────────────────────

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!isPasswordValid) {
      setError('Please ensure your password meets all requirements.');
      return;
    }

    setIsLoading(true);

    try {
      const res = await fetch('/api/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          otp,
          new_password: newPassword,
          confirm_password: confirmPassword,
        }),
      });
      const data = await res.json();

      if (data.status === 'success') {
        toast.success('Password reset successfully! Redirecting to login...', {
          style: {
            background: '#2A1A0A',
            color: '#FFF4E6',
            border: '1px solid rgba(255,127,17,0.25)',
            borderRadius: '12px',
          },
          duration: 3000,
        });
        setStep('email');
        setEmail('');
        setOtp('');
        setNewPassword('');
        setConfirmPassword('');
        setOtpSent(false);
        setTimeout(() => router.push('/login'), 2000);
      } else {
        setError(data.message);
        toast.error(data.message);
      }
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // ─── Progress Indicator ───────────────────────────────────────────────

  const getStepNumber = () => {
    if (step === 'email') return 1;
    if (step === 'otp') return 2;
    return 3;
  };

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden"
      style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 40%, #3D2A10 70%, #4A3520 100%)' }}
    >
      {/* Animated background elements */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute w-[350px] h-[350px] rounded-full" style={{
          background: 'radial-gradient(circle, rgba(255,127,17,0.15) 0%, rgba(255,127,17,0.02) 60%, transparent 80%)',
          top: '20%',
          right: '15%',
          animation: 'jarvisOrbFloat1 10s ease-in-out infinite',
        }} />
        <div className="absolute w-[300px] h-[300px] rounded-full" style={{
          background: 'radial-gradient(circle, rgba(255,215,0,0.06) 0%, rgba(255,215,0,0.01) 60%, transparent 80%)',
          bottom: '15%',
          left: '10%',
          animation: 'jarvisOrbFloat2 12s ease-in-out infinite',
        }} />
        {Array.from({ length: 10 }).map((_, i) => {
          const row = Math.floor(i / 4);
          const col = i % 4;
          return (
            <div
              key={i}
              className="absolute w-1 h-1 rounded-full bg-orange-400"
              style={{
                left: `${(col + 0.5) * 25}%`,
                top: `${(row + 0.5) * 25}%`,
                animation: `jarvisDotPulse 3s ease-in-out infinite ${(i * 0.4) % 4}s`,
                opacity: 0,
              }}
            />
          );
        })}
      </div>

      <div className="w-full max-w-md space-y-8 relative z-10">
        {/* Header */}
        <div className="text-center">
          <Link href="/" className="inline-flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-600/30">
              <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
              </svg>
            </div>
            <span className="text-2xl font-bold text-white">PARWA</span>
          </Link>

          {/* Step indicator */}
          <div className="flex items-center justify-center gap-2 mb-4">
            {[1, 2, 3].map((s) => (
              <div key={s} className="flex items-center gap-2">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-500 ${
                    s < getStepNumber()
                      ? 'bg-orange-500 text-[#1A1A1A]'
                      : s === getStepNumber()
                        ? 'bg-orange-500/20 text-orange-400 border-2 border-orange-500/50 shadow-lg shadow-orange-500/20'
                        : 'bg-white/5 text-orange-200/30 border-2 border-white/10'
                  }`}
                >
                  {s < getStepNumber() ? (
                    <CheckCircle className="w-4 h-4" />
                  ) : (
                    s
                  )}
                </div>
                {s < 3 && (
                  <div
                    className={`w-8 h-0.5 rounded-full transition-all duration-500 ${
                      s < getStepNumber() ? 'bg-orange-500' : 'bg-white/10'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>

          <h1 className="text-3xl font-bold text-white">
            {step === 'email' && 'Forgot password?'}
            {step === 'otp' && 'Verify OTP'}
            {step === 'reset' && 'Set new password'}
          </h1>
          <p className="mt-2 text-sm text-orange-200/50">
            {step === 'email' && 'No worries! Enter your email and we\'ll send you an OTP.'}
            {step === 'otp' && `Enter the 6-digit OTP sent to ${email}`}
            {step === 'reset' && 'Choose a strong new password for your account'}
          </p>
        </div>

        {/* Glass Card */}
        <div
          className="rounded-2xl p-6 sm:p-8 relative overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)',
            border: '1px solid rgba(255,127,17,0.2)',
            backdropFilter: 'blur(20px)',
            boxShadow: '0 25px 50px rgba(0,0,0,0.3), 0 0 60px rgba(255,127,17,0.06)',
          }}
        >
          <div className="absolute -top-16 -right-16 w-32 h-32 rounded-full blur-[60px] pointer-events-none" style={{ background: 'rgba(255,127,17,0.1)' }} />

          {/* ═══ STEP 1: Email ═════════════════════════════════════════ */}
          {step === 'email' && (
            <form onSubmit={handleSendOTP} className="space-y-5">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-orange-200/70 mb-2">
                  Email address
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Mail className="h-5 w-5 text-orange-400/50" />
                  </div>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-10 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-orange-200/30 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all duration-300"
                    placeholder="you@example.com"
                    disabled={isLoading}
                  />
                </div>
              </div>

              {error && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
                  <p className="text-sm text-rose-300">{error}</p>
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading || !email}
                className="w-full py-3 px-4 bg-gradient-to-r from-orange-500 to-orange-400 hover:from-orange-400 hover:to-orange-300 text-[#1A1A1A] font-semibold rounded-xl transition-all duration-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-orange-600/25 hover:shadow-orange-600/40"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Sending OTP...
                  </>
                ) : (
                  <>
                    <KeyRound className="w-5 h-5" />
                    Send OTP
                  </>
                )}
              </button>
            </form>
          )}

          {/* ═══ STEP 2: OTP Verification ═══════════════════════════════ */}
          {step === 'otp' && (
            <form onSubmit={handleVerifyOTP} className="space-y-6">
              {/* Masked email display */}
              <div className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-white/5 border border-white/10">
                <Mail className="w-4 h-4 text-orange-400/50" />
                <span className="text-sm text-orange-200/60">{email}</span>
                <button
                  type="button"
                  onClick={() => { setStep('email'); setOtp(''); setError(null); }}
                  className="text-xs text-orange-400 hover:text-orange-300 ml-auto transition-colors"
                >
                  Change
                </button>
              </div>

              {/* OTP Input */}
              <div>
                <label className="block text-sm font-medium text-orange-200/70 mb-3 text-center">
                  Enter 6-digit OTP
                </label>
                <OTPInput
                  value={otp}
                  onChange={setOtp}
                  disabled={isLoading}
                  error={!!error && otp.length === 6}
                />
              </div>

              {error && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
                  <p className="text-sm text-rose-300">{error}</p>
                </div>
              )}

              {/* Verify button */}
              <button
                type="submit"
                disabled={isLoading || otp.length !== 6}
                className="w-full py-3 px-4 bg-gradient-to-r from-orange-500 to-orange-400 hover:from-orange-400 hover:to-orange-300 text-[#1A1A1A] font-semibold rounded-xl transition-all duration-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-orange-600/25 hover:shadow-orange-600/40"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Verifying...
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-5 h-5" />
                    Verify OTP
                  </>
                )}
              </button>

              {/* Resend OTP */}
              <div className="text-center">
                <p className="text-sm text-orange-200/30">
                  Didn&apos;t receive it?{' '}
                  {resendCooldown > 0 ? (
                    <span className="text-orange-400/50">
                      Resend in {resendCooldown}s
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={handleResendOTP}
                      disabled={isLoading}
                      className="inline-flex items-center gap-1 text-orange-400 hover:text-orange-300 font-medium transition-colors disabled:opacity-50"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
                      Resend OTP
                    </button>
                  )}
                </p>
              </div>
            </form>
          )}

          {/* ═══ STEP 3: New Password ═══════════════════════════════════ */}
          {step === 'reset' && (
            <form onSubmit={handleResetPassword} className="space-y-5">
              {/* New Password */}
              <div>
                <label htmlFor="new-password" className="block text-sm font-medium text-orange-200/70 mb-2">
                  New Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-orange-400/50" />
                  </div>
                  <input
                    id="new-password"
                    name="new-password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full pl-10 pr-10 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-orange-200/30 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all duration-300"
                    placeholder="Enter new password"
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-orange-400/50 hover:text-orange-400 transition-colors"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>

              {/* Password Strength Indicator */}
              {newPassword && (
                <div className="grid grid-cols-2 gap-1.5 text-xs">
                  <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors ${isLongEnough ? 'text-orange-400 bg-orange-500/10' : 'text-orange-200/30 bg-white/[0.02]'}`}>
                    <span>{isLongEnough ? '✓' : '○'}</span> 8+ characters
                  </div>
                  <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors ${hasUppercase ? 'text-orange-400 bg-orange-500/10' : 'text-orange-200/30 bg-white/[0.02]'}`}>
                    <span>{hasUppercase ? '✓' : '○'}</span> Uppercase
                  </div>
                  <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors ${hasLowercase ? 'text-orange-400 bg-orange-500/10' : 'text-orange-200/30 bg-white/[0.02]'}`}>
                    <span>{hasLowercase ? '✓' : '○'}</span> Lowercase
                  </div>
                  <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors ${hasDigit ? 'text-orange-400 bg-orange-500/10' : 'text-orange-200/30 bg-white/[0.02]'}`}>
                    <span>{hasDigit ? '✓' : '○'}</span> Number
                  </div>
                  <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors ${hasSpecial ? 'text-orange-400 bg-orange-500/10' : 'text-orange-200/30 bg-white/[0.02]'}`}>
                    <span>{hasSpecial ? '✓' : '○'}</span> Special char
                  </div>
                  <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors ${passwordsMatch ? 'text-orange-400 bg-orange-500/10' : 'text-orange-200/30 bg-white/[0.02]'}`}>
                    <span>{passwordsMatch ? '✓' : '○'}</span> Match
                  </div>
                </div>
              )}

              {/* Confirm Password */}
              <div>
                <label htmlFor="confirm-password" className="block text-sm font-medium text-orange-200/70 mb-2">
                  Confirm Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-orange-400/50" />
                  </div>
                  <input
                    id="confirm-password"
                    name="confirm-password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full pl-10 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-orange-200/30 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all duration-300"
                    placeholder="Confirm new password"
                    disabled={isLoading}
                  />
                </div>
              </div>

              {error && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
                  <p className="text-sm text-rose-300">{error}</p>
                </div>
              )}

              <button
                type="submit"
                disabled={isLoading || !isPasswordValid}
                className="w-full py-3 px-4 bg-gradient-to-r from-orange-500 to-orange-400 hover:from-orange-400 hover:to-orange-300 text-[#1A1A1A] font-semibold rounded-xl transition-all duration-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-orange-600/25 hover:shadow-orange-600/40"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Resetting password...
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-5 h-5" />
                    Reset Password
                  </>
                )}
              </button>
            </form>
          )}
        </div>

        {/* Back to Login */}
        <div className="text-center">
          <Link
            href="/login"
            className="inline-flex items-center gap-2 text-sm text-orange-200/40 hover:text-orange-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to login
          </Link>
        </div>
      </div>

    </div>
  );
}
