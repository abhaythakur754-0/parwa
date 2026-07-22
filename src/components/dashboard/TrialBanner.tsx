/**
 * PARWA TrialBanner
 *
 * Persistent banner shown at the top of the dashboard for users on the
 * free trial (24h OR 15 tickets, whichever hits first).
 *
 * Shows:
 *   - "Trial: X/15 tickets · Yh left · Upgrade"
 *   - Color shifts amber at <6h left or >10 tickets used, red when expired.
 *   - Hidden entirely for paid (non-trial) users.
 *
 * Fetches /api/billing/razorpay/trial-status every 60s while visible.
 */

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, Clock, Ticket, X } from 'lucide-react';

interface TrialStatus {
  is_trial: boolean;
  tickets_used: number;
  tickets_limit: number;
  started_at: string | null;
  ends_at: string | null;
  time_remaining_hours: number;
  expired: boolean;
  expired_reason: 'TIME' | 'TICKETS' | null;
}

export function TrialBanner() {
  const [status, setStatus] = useState<TrialStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (dismissed) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function fetchStatus() {
      try {
        const res = await fetch('/api/billing/razorpay/trial-status', {
          credentials: 'include',
          signal: AbortSignal.timeout(5000),
        });
        if (cancelled) return;
        if (!res.ok) {
          setStatus(null);
          return;
        }
        const data = (await res.json()) as TrialStatus;
        setStatus(data);
      } catch {
        if (!cancelled) setStatus(null);
      }
    }

    fetchStatus();
    // Poll every 60s while banner is visible — keeps "Yh left" fresh.
    timer = setInterval(fetchStatus, 60_000);

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [dismissed]);

  // Don't render if: not loaded yet, not in trial, dismissed, or paid user.
  if (!status || !status.is_trial || dismissed) return null;

  const used = status.tickets_used;
  const limit = status.tickets_limit;
  const hoursLeft = status.time_remaining_hours;
  const ticketsLeft = Math.max(0, limit - used);

  // Color tier:
  //   - default (orange): plenty of room
  //   - amber: <6h left OR <5 tickets left
  //   - red: expired
  const isAmber = !status.expired && (hoursLeft < 6 || ticketsLeft < 5);
  const isRed = status.expired;

  const bg = isRed
    ? 'bg-red-500/10 border-red-500/30'
    : isAmber
      ? 'bg-amber-500/10 border-amber-500/30'
      : 'bg-orange-500/10 border-orange-500/30';
  const text = isRed
    ? 'text-red-300'
    : isAmber
      ? 'text-amber-300'
      : 'text-orange-300';
  const cta = isRed
    ? 'bg-red-500 hover:bg-red-600'
    : isAmber
      ? 'bg-amber-500 hover:bg-amber-600'
      : 'bg-orange-500 hover:bg-orange-600';

  let message: React.ReactNode;
  if (status.expired && status.expired_reason === 'TIME') {
    message = (
      <>
        <Clock className="w-4 h-4 shrink-0" />
        <span>Your 24-hour free trial has ended.</span>
      </>
    );
  } else if (status.expired && status.expired_reason === 'TICKETS') {
    message = (
      <>
        <Ticket className="w-4 h-4 shrink-0" />
        <span>You&apos;ve used all {limit} free trial tickets.</span>
      </>
    );
  } else {
    const hoursDisplay =
      hoursLeft >= 1
        ? `${Math.floor(hoursLeft)}h ${Math.round((hoursLeft % 1) * 60)}m`
        : `${Math.round(hoursLeft * 60)}m`;
    message = (
      <>
        <Clock className="w-4 h-4 shrink-0" />
        <span>
          <strong className="font-semibold">Free Trial:</strong> {used}/{limit} tickets · {hoursDisplay} left
        </span>
      </>
    );
  }

  return (
    <div className={`border-b ${bg} ${text}`}>
      <div className="max-w-7xl mx-auto px-4 lg:px-6 py-2 flex items-center gap-3 text-sm">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {isRed && <AlertTriangle className="w-4 h-4 shrink-0" />}
          {message}
        </div>
        <Link
          href="/models"
          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-white text-xs font-medium transition-colors ${cta} shrink-0`}
        >
          Upgrade
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
          </svg>
        </Link>
        {!status.expired && (
          <button
            onClick={() => setDismissed(true)}
            className="text-current opacity-60 hover:opacity-100 transition-opacity p-0.5 shrink-0"
            aria-label="Dismiss"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
