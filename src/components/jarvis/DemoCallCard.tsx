/**
 * PARWA DemoCallCard (Week 6 — Day 4 Phase 6, Gap Fixed)
 *
 * Full demo call flow: Phone input → OTP verification → Call button → Timer.
 * Metadata: { phone?: string, call_id?: string, duration_limit?: number }
 * Uses useJarvisChat: initiateDemoCall, sendOtp (for phone OTP)
 *
 * States: idle → otp_sending → otp_sent → otp_verifying → calling → completed | failed
 */

'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Phone, PhoneOff, Loader2, Shield, Clock, Mail, ShieldCheck, RefreshCw, AlertCircle } from 'lucide-react';

interface DemoCallCardProps {
  metadata: Record<string, unknown>;
  onInitiateCall: (phone: string) => Promise<void>;
  callStatus?: 'idle' | 'initiating' | 'calling' | 'completed' | 'failed';
  callDuration?: number;
  // Gap fix: OTP actions for phone verification
  onSendPhoneOtp?: (phone: string) => Promise<void>;
  onVerifyPhoneOtp?: (code: string) => Promise<boolean>;
}

type CardStage = 'idle' | 'otp_sending' | 'otp_sent' | 'otp_verifying' | 'calling' | 'completed' | 'failed';

export function DemoCallCard({
  metadata,
  onInitiateCall,
  callStatus = 'idle',
  callDuration = 0,
  onSendPhoneOtp,
  onVerifyPhoneOtp,
}: DemoCallCardProps) {
  const [phone, setPhone] = useState((metadata.phone as string) || '');
  const [otpCode, setOtpCode] = useState('');
  const [stage, setStage] = useState<CardStage>(
    callStatus === 'completed' ? 'completed'
    : callStatus === 'failed' ? 'failed'
    : callStatus === 'calling' ? 'calling'
    : 'idle',
  );
  const [otpError, setOtpError] = useState<string | null>(null);
  const [otpAttempts, setOtpAttempts] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const otpInputRef = useRef<HTMLInputElement>(null);

  // Sync stage with callStatus prop changes
  useEffect(() => {
    if (callStatus === 'calling' && stage !== 'calling') setStage('calling');
    if (callStatus === 'completed' && stage !== 'completed') setStage('completed');
    if (callStatus === 'failed' && stage !== 'failed') setStage('failed');
  }, [callStatus, stage]);

  // Timer for active call
  useEffect(() => {
    if (stage === 'calling') {
      startTimeRef.current = Date.now();
      const tick = () => setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
      tick();
      timerRef.current = setInterval(tick, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [stage]);

  // Focus inputs
  useEffect(() => {
    if (stage === 'idle' && !phone) inputRef.current?.focus();
    if (stage === 'otp_sent') otpInputRef.current?.focus();
  }, [stage, phone]);

  const formatPhone = useCallback((value: string) => {
    return value.replace(/\D/g, '').slice(0, 15);
  }, []);

  const formatTime = useCallback((seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  }, []);

  const digits = formatPhone(phone);

  // ── OTP Flow (Gap Fix) ──────────────────────────────────────────

  const handleSendOtp = async () => {
    if (digits.length < 7) return;
    setStage('otp_sending');
    setOtpError(null);

    if (onSendPhoneOtp) {
      try {
        await onSendPhoneOtp(digits);
        setStage('otp_sent');
      } catch {
        setOtpError('Failed to send verification code. Try again.');
        setStage('idle');
      }
    } else {
      // No OTP provider — skip straight to call
      await handleCall();
    }
  };

  const handleVerifyOtp = async () => {
    if (otpCode.length < 4) {
      setOtpError('Enter the full code');
      return;
    }

    setStage('otp_verifying');
    setOtpError(null);

    if (onVerifyPhoneOtp) {
      try {
        const success = await onVerifyPhoneOtp(otpCode);
        if (success) {
          setStage('idle'); // Go back to idle, will transition to calling via callStatus
          await handleCall();
        } else {
          const newAttempts = otpAttempts + 1;
          setOtpAttempts(newAttempts);
          if (newAttempts >= 3) {
            setOtpError('Too many attempts. Request a new code.');
            setStage('idle');
            setOtpCode('');
          } else {
            setOtpError(`Invalid code. ${3 - newAttempts} attempt${3 - newAttempts > 1 ? 's' : ''} left.`);
            setStage('otp_sent');
            setOtpCode('');
          }
        }
      } catch {
        setOtpError('Verification failed. Please try again.');
        setStage('otp_sent');
      }
    } else {
      await handleCall();
    }
  };

  const handleResendOtp = async () => {
    setOtpCode('');
    setOtpError(null);
    setStage('otp_sending');
    setOtpAttempts(0);
    try {
      await onSendPhoneOtp?.(digits);
      setStage('otp_sent');
    } catch {
      setOtpError('Failed to resend code.');
      setStage('idle');
    }
  };

  // ── Call Flow ───────────────────────────────────────────────────

  const handleCall = async () => {
    if (digits.length < 7) return;
    await onInitiateCall(digits);
  };

  const durationLimit = (metadata.duration_limit as number) || 180;

  // ── Calling State ───────────────────────────────────────────────

  if (stage === 'calling') {
    const isTimeUp = elapsed >= durationLimit;

    return (
      <div className="glass rounded-xl p-4 border border-emerald-500/15 max-w-sm w-full">
        <div className="flex items-center gap-2 mb-3">
          <div className={`w-8 h-8 rounded-lg ${isTimeUp ? 'bg-red-500/10' : 'bg-emerald-500/10'} flex items-center justify-center`}>
            <Phone className={`w-4 h-4 ${isTimeUp ? 'text-red-400' : 'text-emerald-400 animate-pulse'}`} />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-white">
              {isTimeUp ? 'Call Ended' : 'Demo Call Active'}
            </h3>
            <p className="text-[10px] text-white/40">{phone}</p>
          </div>
          <div className="flex items-center gap-1 text-xs font-mono text-white/60">
            <Clock className="w-3 h-3" />
            {formatTime(Math.min(elapsed, durationLimit))}
          </div>
        </div>

        <div className="w-full h-1 rounded-full bg-white/5 mb-3 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-1000 ${isTimeUp ? 'bg-red-500' : 'bg-emerald-500'}`}
            style={{ width: `${Math.min((elapsed / durationLimit) * 100, 100)}%` }}
          />
        </div>

        <p className="text-[10px] text-white/30 text-center">
          {isTimeUp
            ? 'Your 3-minute demo call has ended.'
            : `${formatTime(durationLimit - elapsed)} remaining · Max ${formatTime(durationLimit)}`}
        </p>
      </div>
    );
  }

  // ── Completed ───────────────────────────────────────────────────

  if (stage === 'completed') {
    return (
      <div className="glass rounded-xl p-4 border border-emerald-500/15 max-w-sm w-full">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <PhoneOff className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Call Complete</h3>
            <p className="text-[10px] text-white/40">Duration: {formatTime(callDuration || elapsed)}</p>
          </div>
        </div>
        <p className="text-xs text-white/50 text-center">
          Hope you enjoyed the demo! Ask Jarvis for the next steps.
        </p>
      </div>
    );
  }

  // ── Failed ──────────────────────────────────────────────────────

  if (stage === 'failed') {
    return (
      <div className="glass rounded-xl p-4 border border-red-500/15 max-w-sm w-full">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
            <PhoneOff className="w-4 h-4 text-red-400" />
          </div>
          <h3 className="text-sm font-semibold text-red-200">Call Failed</h3>
        </div>
        <p className="text-xs text-white/50 text-center mb-3">
          Could not connect. Please check your phone number and try again.
        </p>
        <button
          onClick={handleCall}
          className="w-full py-2 rounded-lg bg-white/5 border border-white/10 text-xs text-white/60 hover:bg-white/10 transition-all"
        >
          Try Again
        </button>
      </div>
    );
  }

  // ── OTP Sending ─────────────────────────────────────────────────

  if (stage === 'otp_sending' || stage === 'otp_verifying') {
    return (
      <div className="glass rounded-xl p-4 border border-emerald-500/15 max-w-sm w-full">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <Mail className="w-4 h-4 text-blue-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Verify Your Phone</h3>
            <p className="text-[10px] text-white/40">Sending code to {phone}...</p>
          </div>
        </div>
        <div className="flex items-center justify-center py-4">
          <Loader2 className="w-5 h-5 animate-spin text-blue-400 mr-2" />
          <span className="text-xs text-white/50">
            {stage === 'otp_sending' ? 'Sending...' : 'Verifying...'}
          </span>
        </div>
      </div>
    );
  }

  // ── OTP Sent — Code Input (Gap Fix) ─────────────────────────────

  if (stage === 'otp_sent') {
    return (
      <div className="glass rounded-xl p-4 border border-blue-500/15 max-w-sm w-full">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4 text-blue-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Verify Phone Number</h3>
            <p className="text-[10px] text-white/40">Code sent to {phone}</p>
          </div>
        </div>

        {otpError && (
          <div className="flex items-start gap-1.5 mb-3 p-2 rounded-lg bg-red-500/10 border border-red-500/10">
            <AlertCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" />
            <p className="text-[11px] text-red-200">{otpError}</p>
          </div>
        )}

        {/* OTP digit boxes */}
        <div className="flex gap-2 mb-2.5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className={`w-10 h-12 rounded-lg border flex items-center justify-center text-lg font-mono font-semibold transition-all ${
                i < otpCode.length
                  ? 'border-blue-400/50 bg-blue-500/10 text-white'
                  : 'border-white/10 bg-white/[0.03] text-white/30'
              }`}
            >
              {otpCode[i] || ''}
            </div>
          ))}
        </div>

        {/* Hidden input */}
        <input
          ref={otpInputRef}
          type="text"
          inputMode="numeric"
          value={otpCode}
          onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          onKeyDown={(e) => { if (e.key === 'Enter' && otpCode.length >= 4) handleVerifyOtp(); }}
          className="sr-only"
          aria-label="Enter phone verification code"
          autoComplete="one-time-code"
        />

        <p className="text-[10px] text-white/30 text-center mb-2.5">
          Enter the code sent to your phone
        </p>

        <button
          onClick={handleVerifyOtp}
          disabled={otpCode.length < 4}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 text-white text-xs font-medium hover:from-blue-400 hover:to-blue-500 disabled:opacity-40 transition-all active:scale-[0.98]"
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          Verify &amp; Start Call
        </button>

        <button
          onClick={handleResendOtp}
          className="w-full flex items-center justify-center gap-1.5 text-[11px] text-white/40 hover:text-white/60 transition-colors py-1.5 mt-1"
        >
          <RefreshCw className="w-3 h-3" />
          Resend code
        </button>
      </div>
    );
  }

  // ── Idle — Phone Input ──────────────────────────────────────────

  return (
    <div className="glass rounded-xl p-4 border border-emerald-500/15 max-w-sm w-full">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
          <Phone className="w-4 h-4 text-emerald-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Try a Demo Call</h3>
          <p className="text-[10px] text-white/40">3-minute AI-powered demo call</p>
        </div>
      </div>

      <div className="space-y-1 mb-3">
        <DemoFeature text="Hear how PARWA sounds in a real call" />
        <DemoFeature text="Ask questions about features & pricing" />
        <DemoFeature text="Completely free, no commitment" />
      </div>

      <div className="flex gap-2">
        <input
          ref={inputRef}
          type="tel"
          value={phone}
          onChange={(e) => setPhone(formatPhone(e.target.value))}
          placeholder="Enter phone number"
          className="flex-1 px-3 py-2.5 rounded-lg bg-white/[0.05] border border-white/10 text-white text-sm placeholder:text-white/25 focus:outline-none focus:border-emerald-500/30"
        />
        <button
          onClick={handleSendOtp}
          disabled={digits.length < 7 || callStatus === 'initiating'}
          className="px-4 py-2.5 rounded-lg bg-gradient-to-r from-emerald-500 to-emerald-600 text-white text-xs font-medium hover:from-emerald-400 hover:to-emerald-500 disabled:opacity-40 transition-all active:scale-[0.98] flex items-center gap-1.5"
        >
          {callStatus === 'initiating' ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Phone className="w-3.5 h-3.5" />
          )}
          Call
        </button>
      </div>

      <p className="text-[10px] text-white/25 text-center mt-2 flex items-center justify-center gap-1">
        <Shield className="w-3 h-3" />
        Your number is used only for this demo call
      </p>
    </div>
  );
}

function DemoFeature({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 px-1">
      <div className="w-1 h-1 rounded-full bg-emerald-400/60 shrink-0" />
      <span className="text-[11px] text-white/50">{text}</span>
    </div>
  );
}
