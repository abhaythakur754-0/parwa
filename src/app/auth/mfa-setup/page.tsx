'use client';

import { useState, useRef, useCallback, KeyboardEvent, ClipboardEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useMFAStore } from '@/lib/mfa-store';
import { Shield, Copy, Check, ArrowLeft, Key } from 'lucide-react';
import Link from 'next/link';

const OTP_LENGTH = 6;

export default function MFASetupPage() {
  const router = useRouter();
  const { initiateSetup, verifyAndEnroll, setupData, status, isEnrolled, error, resetError } = useMFAStore();
  const [digits, setDigits] = useState<string[]>(Array(OTP_LENGTH).fill(''));
  const [localError, setLocalError] = useState<string | null>(null);
  const [secretCopied, setSecretCopied] = useState(false);
  const [codesCopied, setCodesCopied] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  const code = digits.join('');

  // Initiate setup on mount
  useState(() => {
    if (!setupData) initiateSetup();
  });

  const setDigit = useCallback((index: number, value: string) => {
    if (!/^\d*$/.test(value)) return;
    setDigits((prev) => {
      const next = [...prev];
      next[index] = value.slice(-1);
      return next;
    });
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
    if (code.length !== OTP_LENGTH) {
      setLocalError('Please enter all 6 digits');
      return;
    }
    const ok = await verifyAndEnroll(code);
    if (ok) {
      // Success — show backup codes
    }
  };

  const copySecret = () => {
    if (setupData?.secret) {
      navigator.clipboard.writeText(setupData.secret).then(() => {
        setSecretCopied(true);
        setTimeout(() => setSecretCopied(false), 2000);
      });
    }
  };

  const copyAllCodes = () => {
    if (setupData?.backupCodes) {
      navigator.clipboard.writeText(setupData.backupCodes.join('\n')).then(() => {
        setCodesCopied(true);
        setTimeout(() => setCodesCopied(false), 2000);
      });
    }
  };

  const displayError = localError || error;

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Link
          href="/dashboard/settings"
          className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-white transition-colors mb-8"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to settings
        </Link>

        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-orange-500/20 to-amber-400/20 flex items-center justify-center mx-auto mb-6">
            <Shield className="w-7 h-7 text-orange-400" />
          </div>

          {!isEnrolled ? (
            <>
              <h1 className="text-xl font-bold text-white text-center mb-2">
                Set Up Two-Factor Authentication
              </h1>

              {status === 'enrolling' && !setupData ? (
                <p className="text-sm text-zinc-400 text-center">Loading setup...</p>
              ) : setupData ? (
                <>
                  {/* Step 1: Scan QR */}
                  <p className="text-sm text-zinc-400 text-center mb-6">
                    Scan this QR code with your authenticator app
                  </p>

                  <div className="flex justify-center mb-4">
                    {setupData.qrCodeUrl ? (
                      <img
                        src={setupData.qrCodeUrl}
                        alt="MFA QR Code"
                        className="w-48 h-48 rounded-lg border border-white/[0.08] bg-white p-2"
                      />
                    ) : (
                      <div className="w-48 h-48 rounded-lg border border-white/[0.08] bg-white/[0.04] flex items-center justify-center">
                        <Key className="w-8 h-8 text-zinc-600" />
                      </div>
                    )}
                  </div>

                  {/* Secret key */}
                  <div className="mb-6">
                    <label className="block text-xs font-medium text-zinc-500 mb-1.5">
                      Manual entry key
                    </label>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-sm font-mono text-zinc-300 select-all">
                        {setupData.secret}
                      </code>
                      <button
                        onClick={copySecret}
                        className="p-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-zinc-400 hover:text-white transition-colors"
                      >
                        {secretCopied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Step 2: Verify code */}
                  <div className="pt-4 border-t border-white/[0.06]">
                    <p className="text-sm text-zinc-400 mb-4">
                      Enter the 6-digit code from your authenticator to verify setup
                    </p>

                    <div className="flex gap-2 justify-center mb-4">
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

                    {displayError && (
                      <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
                        {displayError}
                      </div>
                    )}

                    <button
                      onClick={handleVerify}
                      disabled={status === 'verifying' || code.length !== OTP_LENGTH}
                      className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {status === 'verifying' ? 'Verifying...' : 'Verify & Enable 2FA'}
                    </button>
                  </div>
                </>
              ) : null}
            </>
          ) : (
            /* ── Enrolled: Show backup codes ── */
            <>
              <h1 className="text-xl font-bold text-white text-center mb-2">
                2FA Enabled Successfully!
              </h1>
              <p className="text-sm text-zinc-400 text-center mb-6">
                Save these backup codes in a safe place. You can use them to sign in if you lose your device.
              </p>

              <div className="mb-6 p-4 rounded-lg border border-white/[0.08] bg-white/[0.02]">
                <div className="grid grid-cols-2 gap-2">
                  {setupData?.backupCodes.map((code, i) => (
                    <code
                      key={i}
                      className="text-sm font-mono text-zinc-300 bg-white/[0.04] rounded px-2 py-1.5 text-center select-all"
                    >
                      {code}
                    </code>
                  ))}
                </div>
              </div>

              <button
                onClick={copyAllCodes}
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all mb-3"
              >
                {codesCopied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                {codesCopied ? 'Copied!' : 'Copy All Codes'}
              </button>

              <button
                onClick={() => router.push('/dashboard')}
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200"
              >
                Continue to Dashboard
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
