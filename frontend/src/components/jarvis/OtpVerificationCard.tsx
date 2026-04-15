/**
 * PARWA OtpVerificationCard (Week 6 — Day 4 Phase 6)
 *
 * Full OTP flow: email input → Send OTP → 6-digit input → Verify.
 * Uses useJarvisChat hook actions: sendOtp, verifyOtp.
 * States: idle → sending → sent → verifying → verified | error
 */

'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Mail, ShieldCheck, Loader2, AlertCircle, RefreshCw } from 'lucide-react';

interface OtpVerificationCardProps {
  onSendOtp: (email: string) => Promise<void>;
  onVerifyOtp: (code: string) => Promise<boolean>;
  initialEmail?: string;
  /** Current OTP attempt count from the parent hook (single source of truth) */
  otpAttempts: number;
  maxAttempts?: number;
  onVerified?: () => void;
  /** ISO timestamp when OTP expires (e.g. from server response) */
  expiresAt?: string | null;
}

export function OtpVerificationCard({
  onSendOtp,
  onVerifyOtp,
  initialEmail = '',
  otpAttempts,
  maxAttempts = 3,
  onVerified,
  expiresAt,
}: OtpVerificationCardProps) {
  const [email, setEmail] = useState(initialEmail);
  const [code, setCode] = useState('');
  const [stage, setStage] = useState<'idle' | 'sending' | 'sent' | 'verifying' | 'verified' | 'error'>(
    initialEmail ? 'sent' : 'idle',
  );
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const otpRef = useRef<HTMLInputElement>(null);

  // Gap fix: Expiry countdown timer
  useEffect(() => {
    if (stage !== 'sent' || !expiresAt) {
      setCountdown(null);
      return;
    }
    const expiryMs = new Date(expiresAt).getTime();
    const tick = () => {
      const remaining = Math.max(0, Math.floor((expiryMs - Date.now()) / 1000));
      setCountdown(remaining);
      if (remaining <= 0) {
        setError('Code expired. Please request a new one.');
      }
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [stage, expiresAt]);

  // Focus email input on mount
  useEffect(() => {
    if (stage === 'idle') inputRef.current?.focus();
    if (stage === 'sent') otpRef.current?.focus();
  }, [stage]);

  // Auto-fill code when user types 6 digits
  const handleCodeChange = useCallback((value: string) => {
    const digits = value.replace(/\D/g, '').slice(0, 6);
    setCode(digits);
    setError(null);
  }, []);

  // Handle send OTP
  const handleSend = async () => {
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('Please enter a valid email address');
      return;
    }

    setStage('sending');
    setError(null);

    try {
      await onSendOtp(email.trim());
      setStage('sent');
    } catch {
      setError('Failed to send OTP. Please try again.');
      setStage('error');
    }
  };

  // Handle verify OTP
  const handleVerify = async () => {
    if (code.length < 6) {
      setError('Please enter all 6 digits');
      return;
    }

    setStage('verifying');
    setError(null);

    try {
      const success = await onVerifyOtp(code);
      if (success) {
        setStage('verified');
        onVerified?.();
      } else {
        // D11-P3 Fix: Use otpAttempts prop from parent hook instead of local state
        const newAttempts = otpAttempts + 1;
        if (newAttempts >= maxAttempts) {
          setError(`Too many attempts. Please request a new OTP.`);
          setStage('error');
        } else {
          setError(`Invalid code. ${maxAttempts - newAttempts} attempt${maxAttempts - newAttempts > 1 ? 's' : ''} remaining.`);
          setStage('sent');
          setCode('');
        }
      }
    } catch {
      setError('Verification failed. Please try again.');
      setStage('sent');
    }
  };

  // Handle resend
  const handleResend = async () => {
    setCode('');
    setError(null);
    setStage('sending');
    try {
      await onSendOtp(email.trim());
      setStage('sent');
      // D11-P3 Fix: attempts reset is handled by the parent hook (sendOtp resets otpState.attempts to 0)
    } catch {
      setError('Failed to resend OTP.');
      setStage('error');
    }
  };

  // Verified state
  if (stage === 'verified') {
    return (
      <div className="glass rounded-xl p-4 border border-orange-500/20 max-w-sm w-full">
        <div className="flex items-center gap-2 mb-2">
          <ShieldCheck className="w-5 h-5 text-orange-400" />
          <span className="text-sm font-medium text-orange-200">Email Verified</span>
        </div>
        <p className="text-xs text-white/50">
          Your email <span className="text-white/70">{email}</span> has been verified successfully.
        </p>
      </div>
    );
  }

  return (
    <div className="glass rounded-xl p-4 border border-blue-500/15 max-w-sm w-full">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
          <Mail className="w-4 h-4 text-blue-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Email Verification</h3>
          <p className="text-[10px] text-white/40">
            {stage === 'idle' ? 'Enter your business email' : `Code sent to ${email}`}
          </p>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-1.5 mb-3 p-2 rounded-lg bg-red-500/10 border border-red-500/10">
          <AlertCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" />
          <p className="text-[11px] text-red-200">{error}</p>
        </div>
      )}

      {/* Stage: idle — email input */}
      {stage === 'idle' && (
        <div className="space-y-2.5">
          <input
            ref={inputRef}
            type="email"
            value={email}
            onChange={(e) => { setEmail(e.target.value); setError(null); }}
            placeholder="you@company.com"
            className="w-full px-3 py-2.5 rounded-lg bg-white/[0.05] border border-white/10 text-white text-sm placeholder:text-white/25 focus:outline-none focus:border-blue-500/30"
          />
          <button
            onClick={handleSend}
            disabled={!email.trim()}
            className="w-full py-2.5 rounded-lg bg-gradient-to-r from-blue-500 to-blue-600 text-white text-xs font-medium hover:from-blue-400 hover:to-blue-500 disabled:opacity-40 transition-all active:scale-[0.98]"
          >
            Send Verification Code
          </button>
        </div>
      )}

      {/* Stage: sending */}
      {stage === 'sending' && (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="w-5 h-5 animate-spin text-blue-400 mr-2" />
          <span className="text-xs text-white/50">Sending OTP...</span>
        </div>
      )}

      {/* Stage: sent — OTP input */}
      {(stage === 'sent' || stage === 'verifying') && (
        <div className="space-y-2.5">
          <div className="flex gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className={`w-10 h-12 rounded-lg border flex items-center justify-center text-lg font-mono font-semibold transition-all ${
                  i < code.length
                    ? 'border-blue-400/50 bg-blue-500/10 text-white'
                    : 'border-white/10 bg-white/[0.03] text-white/30'
                }`}
              >
                {code[i] || ''}
              </div>
            ))}
          </div>

          {/* Hidden real input for typing */}
          <input
            ref={otpRef}
            type="text"
            inputMode="numeric"
            value={code}
            onChange={(e) => handleCodeChange(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && code.length === 6) handleVerify(); }}
            className="sr-only"
            aria-label="Enter 6-digit OTP code"
            autoComplete="one-time-code"
          />

          <p className="text-[10px] text-white/30 text-center">
            Type the 6-digit code sent to your email
            {countdown !== null && countdown > 0 && (
              <span className={`ml-1.5 font-mono ${countdown <= 60 ? 'text-amber-400/60' : ''}`}>
                ({Math.floor(countdown / 60)}:{(countdown % 60).toString().padStart(2, '0')})
              </span>
            )}
          </p>

          <button
            onClick={handleVerify}
            disabled={code.length < 6 || stage === 'verifying'}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gradient-to-r from-blue-500 to-blue-600 text-white text-xs font-medium hover:from-blue-400 hover:to-blue-500 disabled:opacity-40 transition-all active:scale-[0.98]"
          >
            {stage === 'verifying' ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Verifying...
              </>
            ) : (
              'Verify Code'
            )}
          </button>

          {/* Resend */}
          <button
            onClick={handleResend}
            disabled={stage === 'verifying'}
            className="w-full flex items-center justify-center gap-1.5 text-[11px] text-white/40 hover:text-white/60 disabled:opacity-40 transition-colors py-1"
          >
            <RefreshCw className="w-3 h-3" />
            Resend code
          </button>
        </div>
      )}
    </div>
  );
}
