/**
 * PARWA PaymentCard (Week 6 — Day 4 Phase 6)
 *
 * Shows $1 demo pack OR variant payment with Paddle checkout button.
 * Metadata: { type: 'demo_pack' | 'variant', amount: number, currency: string,
 *             paddle_url?: string, checkout_url?: string }
 */

'use client';

import { CreditCard, ExternalLink, Loader2, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

interface PaymentCardProps {
  metadata: Record<string, unknown>;
  onCreatePayment?: () => Promise<string | null>;
  onPurchaseDemoPack?: () => Promise<void>;
  isDemoPackActive?: boolean;
}

export function PaymentCard({
  metadata,
  onCreatePayment,
  onPurchaseDemoPack,
  isDemoPackActive,
}: PaymentCardProps) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const type = (metadata.type as string) || 'demo_pack';
  const amount = (metadata.amount as number) || 1;
  const currency = (metadata.currency as string) || 'USD';
  const paddleUrl = (metadata.paddle_url || metadata.checkout_url) as string | null;

  const isDemoPack = type === 'demo_pack';
  const title = isDemoPack ? 'Demo Pack' : 'Payment';
  const description = isDemoPack
    ? 'Get 500 messages + 1 AI demo call for just $1'
    : `Pay ${currency} ${amount.toLocaleString()} for your selected variants`;

  const handlePay = async () => {
    if (isProcessing) return;
    setIsProcessing(true);
    setError(null);

    try {
      if (paddleUrl) {
        const opened = window.open(paddleUrl, '_blank', 'noopener,noreferrer');
        if (!opened) window.location.href = paddleUrl;
      } else if (isDemoPack && onPurchaseDemoPack) {
        await onPurchaseDemoPack();
      } else if (!isDemoPack && onCreatePayment) {
        const url = await onCreatePayment();
        if (url) {
          const opened = window.open(url, '_blank', 'noopener,noreferrer');
          if (!opened) window.location.href = url;
        }
        else setError('Failed to create payment. Please try again.');
      }
    } catch {
      setError('Payment failed. Please try again.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="glass rounded-xl p-4 border border-amber-500/15 max-w-sm w-full">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
          <CreditCard className="w-4 h-4 text-amber-400" />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-white">{title}</h3>
          <p className="text-[10px] text-white/40">{description}</p>
        </div>
        <span className="text-lg font-bold text-amber-300">
          {currency} {amount}
        </span>
      </div>

      {/* Features */}
      <div className="space-y-1.5 mb-3">
        {isDemoPack ? (
          <>
            <FeatureItem text="500 messages per day" />
            <FeatureItem text="1 AI-powered demo call (3 min)" />
            <FeatureItem text="Full onboarding guidance" />
          </>
        ) : (
          <>
            <FeatureItem text="Secure checkout via Paddle" />
            <FeatureItem text="Instant activation" />
            <FeatureItem text="Cancel anytime" />
          </>
        )}
      </div>

      {/* Error */}
      {error && (
        <p className="text-[11px] text-red-300 mb-2 px-1">{error}</p>
      )}

      {/* Pay button */}
      <button
        onClick={handlePay}
        disabled={isProcessing || isDemoPackActive}
        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 text-white text-xs font-medium hover:from-amber-400 hover:to-amber-500 transition-all disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98]"
      >
        {isProcessing ? (
          <>
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Processing...
          </>
        ) : isDemoPackActive ? (
          <>
            <ShieldCheck className="w-3.5 h-3.5" />
            Pack Active
          </>
        ) : (
          <>
            <CreditCard className="w-3.5 h-3.5" />
            Pay {currency} {amount}
            <ExternalLink className="w-3 h-3 ml-1 opacity-60" />
          </>
        )}
      </button>

      {/* Secure badge */}
      <p className="text-[10px] text-white/25 text-center mt-2 flex items-center justify-center gap-1">
        <ShieldCheck className="w-3 h-3" />
        Secured by Paddle · SSL encrypted
        {isDemoPack && (
          <span className="ml-1 text-white/20">· 24-hour validity</span>
        )}
      </p>
    </div>
  );
}

function FeatureItem({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 px-1">
      <div className="w-1 h-1 rounded-full bg-amber-400/60 shrink-0" />
      <span className="text-[11px] text-white/50">{text}</span>
    </div>
  );
}
