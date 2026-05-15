'use client';

import { useState, useRef, useCallback, KeyboardEvent, ClipboardEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useMFAStore } from '@/lib/mfa-store';
import { Shield, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

const OTP_LENGTH = 6;

export default function MFAVerifyPage() {
  const router = useRouter();
  const { verifyLogin, status, error, resetError } = useMFAStore();
  const [digits, setDigits] = useState<string[]>(Array(OTP_LENGTH).fill(''));
  const [useBackup, setUseBackup] = useState(false);
  const [backupCode, setBackupCode] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  const code = digits.join('');

  const setDigit = useCallback((index: number, value: string) => {
    if (!/^\d*$/.test(value)) return; // only digits
    setDigits((prev) => {
      const next = [...prev];
      next[index] = value.slice(-1); // keep only last digit
      return next;
    });
    // Auto-focus next input
    if (value && index < OTP_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  }, []);

  const handleKeyDown = useCallback(
    (index: number, e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Backspace' && !digits[index] && index > 0) {
        inputRefs.current[index - 1]?.focus();
        setDigits((prev) => {
          const next = [...prev];
          next[index - 1] = '';
          return next;
        });
      }
      if (e.key === 'Enter' && code.length === OTP_LENGTH) {
        handleVerify();
      }
    },
    [digits, code]
  );

  const handlePaste = useCallback((e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, OTP_LENGTH);
    if (pasted.length > 0) {
      const newDigits = [...Array(OTP_LENGTH).fill('')];
      pasted.split('').forEach((d, i) => (newDigits[i] = d));
      setDigits(newDigits);
      inputRefs.current[Math.min(pasted.length, OTP_LENGTH - 1)]?.focus();
    }
  }, []);

  const handleVerify = async () => {
    setLocalError(null);
    resetError();
    if (useBackup) {
      const ok = await verifyLogin(backupCode.trim(), true);
      if (ok) router.push('/dashboard');
    } else {
      if (code.length !== OTP_LENGTH) {
        setLocalError('Please enter all 6 digits');
        return;
      }
      const ok = await verifyLogin(code);
      if (ok) router.push('/dashboard');
    }
  };

  const displayError = localError || error;

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Back link */}
        <Link
          href="/auth/login"
          className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-white transition-colors mb-8"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to login
        </Link>

        {/* Card */}
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8">
          {/* Icon */}
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-orange-500/20 to-amber-400/20 flex items-center justify-center mx-auto mb-6">
            <Shield className="w-7 h-7 text-orange-400" />
          </div>

          <h1 className="text-xl font-bold text-white text-center mb-2">
            Two-Factor Authentication
          </h1>
          <p className="text-sm text-zinc-400 text-center mb-8">
            {useBackup
              ? 'Enter one of your backup codes to sign in'
              : 'Enter the 6-digit code from your authenticator app'}
          </p>

          {!useBackup ? (
            /* OTP Input */
            <div className="flex gap-2 justify-center mb-6">
              {Array.from({ length: OTP_LENGTH }).map((_, i) => (
                <input
                  key={i}
                  ref={(el) => { inputRefs.current[i] = el; }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digits[i]}
                  onChange={(e) => setDigit(i, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(i, e)}
                  onPaste={i === 0 ? handlePaste : undefined}
                  autoFocus={i === 0}
                  className={`w-12 h-14 text-center text-lg font-semibold rounded-lg border transition-all duration-200 outline-none ${
                    digits[i]
                      ? 'border-orange-500/40 bg-orange-500/5 text-white'
                      : 'border-white/[0.08] bg-white/[0.04] text-white'
                  } focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/50 placeholder:text-zinc-600`}
                  placeholder="·"
                />
              ))}
            </div>
          ) : (
            /* Backup Code Input */
            <div className="mb-6">
              <input
                type="text"
                value={backupCode}
                onChange={(e) => setBackupCode(e.target.value.toUpperCase())}
                placeholder="XXXX-XXXX"
                className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-4 py-3 text-sm font-mono text-center tracking-widest focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all placeholder:text-zinc-600"
                autoFocus
              />
            </div>
          )}

          {/* Error */}
          {displayError && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
              {displayError}
            </div>
          )}

          {/* Verify Button */}
          <button
            onClick={handleVerify}
            disabled={status === 'verifying'}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none"
          >
            {status === 'verifying' ? 'Verifying...' : 'Verify'}
          </button>

          {/* Toggle backup */}
          <button
            onClick={() => {
              setUseBackup(!useBackup);
              setLocalError(null);
              resetError();
            }}
            className="w-full mt-4 text-sm text-zinc-500 hover:text-zinc-300 transition-colors text-center"
          >
            {useBackup ? 'Use authenticator code instead' : 'Use a backup code instead'}
          </button>
        </div>
      </div>
    </div>
  );
}
