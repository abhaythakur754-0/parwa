'use client';

import React, { useState, useEffect } from 'react';
import { RazorpayCheckout } from '@/components/razorpay/RazorpayCheckout';

export default function TestRazorpayPage() {
  const [amount, setAmount] = useState(100);
  const [lastPayment, setLastPayment] = useState<{ paymentId: string; orderId: string } | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [diagnostics, setDiagnostics] = useState<{
    keyId: string | null;
    cookies: string;
    hasAuth: boolean;
  }>({ keyId: null, cookies: '', hasAuth: false });

  useEffect(() => {
    const keyId = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || null;
    const cookies = document.cookie;
    const hasAuth = cookies.includes('parwa_at');
    setDiagnostics({ keyId, cookies, hasAuth });
    setLogs((l) => [
      ...l,
      `[diag] NEXT_PUBLIC_RAZORPAY_KEY_ID = ${keyId ? keyId.slice(0, 16) + '...' : 'NOT SET'}`,
      `[diag] cookies present: ${cookies ? 'yes' : 'no'}`,
      `[diag] parwa_at cookie present: ${hasAuth ? 'yes' : 'no'}`,
    ]);
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white p-6">
      <div className="max-w-2xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Razorpay Standard Checkout — Test</h1>
          <p className="text-sm text-white/60 mt-1">
            Manual test page for the Razorpay payment flow with inline diagnostics.
          </p>
        </div>

        {/* DIAGNOSTICS PANEL */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-4 text-sm space-y-2">
          <div className="font-semibold text-white">Diagnostics</div>
          <div className={diagnostics.keyId ? 'text-emerald-400' : 'text-red-400'}>
            {diagnostics.keyId
              ? `✓ NEXT_PUBLIC_RAZORPAY_KEY_ID set: ${diagnostics.keyId.slice(0, 16)}...`
              : '✗ NEXT_PUBLIC_RAZORPAY_KEY_ID is NOT set on Vercel — RazorpayCheckout will refuse to open the modal.'}
          </div>
          <div className={diagnostics.hasAuth ? 'text-emerald-400' : 'text-red-400'}>
            {diagnostics.hasAuth
              ? '✓ Logged in (parwa_at cookie present) — create-order should work.'
              : '✗ NOT logged in — /api/razorpay/create-order will return 403. Sign in at parwa.buzz/login first.'}
          </div>
          {!diagnostics.keyId && (
            <div className="mt-2 p-2 bg-red-500/10 border border-red-500/30 rounded text-xs text-red-200">
              <div className="font-semibold">Fix this on Vercel:</div>
              <div>Project → Settings → Environment Variables → add:</div>
              <code className="block mt-1 px-2 py-1 bg-black/50 rounded">
                NEXT_PUBLIC_RAZORPAY_KEY_ID = rzp_test_T9qS49GOrGJG9j
              </code>
              <div className="mt-1">Then redeploy (Deployments → ⋯ → Redeploy).</div>
            </div>
          )}
          {!diagnostics.hasAuth && (
            <div className="mt-2 p-2 bg-red-500/10 border border-red-500/30 rounded text-xs text-red-200">
              <div className="font-semibold">Fix this:</div>
              <a href="/login" className="underline">Sign in to parwa.buzz</a> in another tab, then come back here.
            </div>
          )}
        </div>

        {/* PAY PANEL */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6 space-y-4">
          <label className="block">
            <span className="text-sm text-white/70">Amount (₹)</span>
            <input
              type="number"
              min={1}
              value={amount}
              onChange={(e) => setAmount(Math.max(1, Number(e.target.value)))}
              className="mt-1 w-full px-3 py-2 rounded-lg bg-black/40 border border-white/10 text-white"
            />
            <span className="text-xs text-white/40 mt-1 block">
              = {Math.round(amount * 100)} paise
            </span>
          </label>

          <RazorpayCheckout
            amount={amount}
            name="PARWA Test"
            description="Manual test payment"
            buttonText={`Pay ₹${amount}`}
            onSuccess={(paymentId, orderId) => {
              setLastPayment({ paymentId, orderId });
              setLogs((l) => [...l, `[ok] payment_id=${paymentId} order_id=${orderId}`]);
            }}
          />
        </div>

        {/* LOG PANEL */}
        <div className="bg-black/60 border border-white/10 rounded-2xl p-4">
          <div className="text-xs font-semibold text-white/60 mb-2">Activity log</div>
          <div className="font-mono text-xs text-white/80 space-y-0.5 max-h-48 overflow-y-auto">
            {logs.length === 0 ? (
              <div className="text-white/30">(no activity yet — click Pay to start)</div>
            ) : (
              logs.map((line, i) => <div key={i}>{line}</div>)
            )}
          </div>
        </div>

        {/* RESULT PANEL */}
        {lastPayment && (
          <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-2xl p-4 text-sm">
            <div className="font-semibold text-emerald-400 mb-1">✓ Payment verified</div>
            <div className="text-white/80">
              <div>Payment ID: <code className="text-white">{lastPayment.paymentId}</code></div>
              <div>Order ID: <code className="text-white">{lastPayment.orderId}</code></div>
            </div>
          </div>
        )}

        {/* TEST CREDENTIALS */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-4 text-xs text-white/70 space-y-2">
          <div className="font-semibold text-white">Test credentials</div>
          <div><b>Card:</b> 4111 1111 1111 1111 · CVV 123 · Expiry 12/26</div>
          <div><b>UPI:</b> test@razorpay</div>
        </div>

        <a href="/dashboard/billing" className="block text-center text-sm text-white/50 hover:text-white underline">
          ← Back to billing dashboard
        </a>
      </div>
    </div>
  );
}
