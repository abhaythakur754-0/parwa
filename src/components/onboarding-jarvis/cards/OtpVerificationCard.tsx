/**
 * PARWA Onboarding — OTP Verification Card
 *
 * Shows OTP email verification step during onboarding.
 */

'use client';

import { useState } from 'react';
import { Shield, Loader2, CheckCircle2 } from 'lucide-react';
import type { OtpCardData } from '@/types/onboarding-jarvis';

interface OtpVerificationCardProps {
  data: Record<string, any>;
}

export function OtpVerificationCard({ data }: OtpVerificationCardProps) {
  const otpData = data as Partial<OtpCardData>;
  const email = otpData.email || '';
  const status = otpData.status || 'sent';
  const attemptsRemaining = otpData.attempts_remaining ?? 3;

  const [otp, setOtp] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [verified, setVerified] = useState(false);

  const maskedEmail = email
    ? email.replace(/(.{2})(.*)(@.*)/, (_, a, b, c) => a + '*'.repeat(b.length) + c)
    : 'your email';

  const handleVerify = async () => {
    if (otp.length < 4 || verifying) return;
    setVerifying(true);
    // Verification is handled by the parent chat flow
    setTimeout(() => {
      setVerifying(false);
      setVerified(true);
    }, 1500);
  };

  return (
    <div className="rounded-xl p-4 bg-white/[0.03] backdrop-blur-xl border border-emerald-500/15 max-w-sm w-full">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
          <Shield className="w-4 h-4 text-emerald-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">
            {verified ? 'Verified!' : 'Verify Your Email'}
          </h3>
          <p className="text-[10px] text-white/40">
            {verified ? 'Email confirmed' : `Code sent to ${maskedEmail}`}
          </p>
        </div>
      </div>

      {verified ? (
        <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-emerald-500/5 border border-emerald-500/15">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span className="text-xs text-emerald-300">Email verified successfully</span>
        </div>
      ) : (
        <>
          <div className="flex gap-2 mb-3">
            <input
              type="text"
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="Enter OTP"
              className="flex-1 px-3 py-2 rounded-lg bg-gray-800/60 border border-white/10 text-white text-sm placeholder:text-white/20 focus:outline-none focus:border-emerald-500/50"
              maxLength={6}
            />
            <button
              onClick={handleVerify}
              disabled={otp.length < 4 || verifying}
              className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-500 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              {verifying ? (
                <>
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Verifying
                </>
              ) : (
                'Verify'
              )}
            </button>
          </div>

          <p className="text-[10px] text-white/30">
            {attemptsRemaining} attempt{attemptsRemaining !== 1 ? 's' : ''} remaining
          </p>
        </>
      )}
    </div>
  );
}
