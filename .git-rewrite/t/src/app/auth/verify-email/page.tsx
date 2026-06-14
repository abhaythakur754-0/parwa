'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { MailCheck, MailX, RefreshCw, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type VerifyState = 'loading' | 'success' | 'error' | 'expired';

export default function EmailVerifyPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');
  const email = searchParams.get('email');

  const [state, setState] = useState<VerifyState>(token ? 'loading' : 'error');
  const [resending, setResending] = useState(false);
  const [resendMessage, setResendMessage] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    if (!token) return;
    const verifyEmail = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/auth/verify-email?token=${encodeURIComponent(token)}`, {
          method: 'GET',
          credentials: 'include',
        });
        if (res.ok) setState('success');
        else if (res.status === 410 || res.status === 422) setState('expired');
        else setState('error');
      } catch { setState('error'); }
    };
    verifyEmail();
  }, [token]);

  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
    return () => clearTimeout(timer);
  }, [countdown]);

  const handleResend = async () => {
    if (countdown > 0 || !email) return;
    setResending(true);
    setResendMessage(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/verify-email/resend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email }),
      });
      if (res.ok) {
        setResendMessage('Verification email sent! Check your inbox.');
        setCountdown(60);
      } else if (res.status === 404 || res.status === 502 || res.status === 503) {
        setResendMessage('Email service unavailable — please try again later.');
        setCountdown(30);
      } else {
        const data = await res.json().catch(() => ({}));
        setResendMessage(data.detail || 'Failed to resend verification email.');
      }
    } catch {
      setResendMessage('Network error — please check your connection.');
    } finally {
      setResending(false);
    }
  };

  const icons: Record<VerifyState, { bg: string; color: string; Icon: typeof MailCheck }> = {
    loading: { bg: 'bg-orange-500/10', color: 'text-orange-400', Icon: MailCheck },
    success: { bg: 'bg-emerald-500/10', color: 'text-emerald-400', Icon: MailCheck },
    expired: { bg: 'bg-yellow-500/10', color: 'text-yellow-400', Icon: MailX },
    error: { bg: 'bg-red-500/10', color: 'text-red-400', Icon: MailX },
  };

  const titles: Record<VerifyState, string> = {
    loading: 'Verifying your email...',
    success: 'Email Verified!',
    expired: 'Link Expired',
    error: 'Verification Failed',
  };

  const descriptions: Record<VerifyState, string> = {
    loading: 'Please wait while we verify your email address.',
    success: 'Your email address has been successfully verified. You can now access all features.',
    expired: 'This verification link has expired. Please request a new one.',
    error: "We couldn't verify your email address. The link may be invalid or has expired.",
  };

  const { bg, color, Icon } = icons[state];

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Link href="/auth/login" className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-white transition-colors mb-8">
          <ArrowLeft className="w-4 h-4" /> Back to login
        </Link>
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8">
          <div className={`w-14 h-14 rounded-2xl ${bg} flex items-center justify-center mx-auto mb-6 ${state === 'loading' ? 'animate-pulse' : ''}`}>
            <Icon className={`w-7 h-7 ${color}`} />
          </div>
          <h1 className="text-xl font-bold text-white text-center mb-2">{titles[state]}</h1>
          <p className="text-sm text-zinc-400 text-center mb-6">{descriptions[state]}</p>

          {state === 'success' && (
            <button onClick={() => router.push('/dashboard')} className="w-full inline-flex items-center justify-center px-4 py-3 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200">
              Continue to Dashboard
            </button>
          )}

          {(state === 'expired' || state === 'error') && email && (
            <button onClick={handleResend} disabled={resending || countdown > 0} className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed">
              <RefreshCw className={`w-4 h-4 ${resending ? 'animate-spin' : ''}`} />
              {resending ? 'Sending...' : countdown > 0 ? `Resend in ${countdown}s` : 'Resend Verification Email'}
            </button>
          )}

          {(state === 'expired' || state === 'error') && !email && (
            <Link href="/auth/login" className="w-full inline-flex items-center justify-center px-4 py-3 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 transition-all duration-200">
              Go to Login
            </Link>
          )}

          {resendMessage && <p className="text-sm text-zinc-400 text-center mt-4">{resendMessage}</p>}
        </div>
      </div>
    </div>
  );
}
