/**
 * PARWA UsageWarningModal
 *
 * Proactive modal popup that appears when the company's monthly ticket
 * usage crosses 80% of the plan limit. Also surfaces subscription
 * renewal reminders (Netflix-style heads-up before the auto-charge).
 *
 * Behavior:
 * - On dashboard mount, fetches /api/billing/usage
 * - If usage_percentage >= 80, shows the modal once per session
 *   (sessionStorage prevents re-popping on every page navigation)
 * - Also listens for `billing:usage_warning` and `billing:renewal_reminder`
 *   Socket.io events so the modal can be triggered in real time
 * - User can dismiss (remembers dismissal for the session) or click
 *   "Upgrade plan" to navigate to /dashboard/billing
 *
 * Building Codes respected:
 * - BC-001: usage is scoped to the current company via /api/billing/usage
 * - No new Zustand store (uses local state + sessionStorage) — CLAUDE.md #2
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

// ── Constants ─────────────────────────────────────────────────────────

const USAGE_THRESHOLD = 80; // %
const SESSION_STORAGE_KEY = 'parwa_usage_warning_dismissed_at';
const REALTIME_EVENT_TYPES = [
  'billing:usage_warning',
  'billing:usage_limit_exceeded',
  'billing:renewal_reminder',
];

// ── Types ─────────────────────────────────────────────────────────────

interface UsageData {
  usage_percentage?: number;
  tickets_used?: number;
  ticket_limit?: number;
  overage_tickets?: number;
  current_month?: string;
}

interface RealtimeBillingEvent {
  event_type?: string;
  usage_percentage?: number;
  tickets_used?: number;
  ticket_limit?: number;
  variant?: string;
  renewal_date?: string;
  amount?: string;
  message?: string;
}

// ── Helper: check if dismissal is still valid (within last 24h) ───────

function isDismissedRecently(): boolean {
  if (typeof window === 'undefined') return false;
  const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (!raw) return false;
  const ts = Number(raw);
  if (Number.isNaN(ts)) return false;
  // 24-hour dismissal window
  return Date.now() - ts < 24 * 60 * 60 * 1000;
}

function markDismissed(): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(SESSION_STORAGE_KEY, String(Date.now()));
}

// ── Icons ─────────────────────────────────────────────────────────────

const WarningIcon = () => (
  <svg
    className="w-6 h-6 text-amber-400"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
    aria-hidden="true"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
    />
  </svg>
);

const RenewalIcon = () => (
  <svg
    className="w-6 h-6 text-sky-400"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
    aria-hidden="true"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M16.023 9.348h4.992V4.356M19.66 9.348a8.25 8.25 0 0 0-14.527-3.49M3.49 3.49v4.992H8.48M3.49 8.482a8.25 8.25 0 0 0 14.527 3.49M19.66 14.652v4.992h-4.992M16.02 19.652a8.25 8.25 0 0 1-14.527-3.49"
    />
  </svg>
);

// ── Component ─────────────────────────────────────────────────────────

type ModalKind = 'usage' | 'renewal' | null;

interface ModalState {
  kind: ModalKind;
  usage_percentage?: number;
  tickets_used?: number;
  ticket_limit?: number;
  variant?: string;
  renewal_date?: string;
  amount?: string;
  message?: string;
}

export function UsageWarningModal() {
  const router = useRouter();
  const [modal, setModal] = useState<ModalState>({ kind: null });

  // ── Show usage modal if data warrants it ────────────────────────────
  const showUsageModalIfNeeded = useCallback((data: UsageData) => {
    if (isDismissedRecently()) return;
    const pct = Number(data.usage_percentage ?? 0);
    if (pct >= USAGE_THRESHOLD) {
      setModal({
        kind: 'usage',
        usage_percentage: pct,
        tickets_used: data.tickets_used,
        ticket_limit: data.ticket_limit,
      });
    }
  }, []);

  // ── Show renewal modal from realtime event ──────────────────────────
  const showRenewalModal = useCallback((evt: RealtimeBillingEvent) => {
    if (isDismissedRecently()) return;
    setModal({
      kind: 'renewal',
      variant: evt.variant,
      renewal_date: evt.renewal_date,
      amount: evt.amount,
      message: evt.message,
    });
  }, []);

  // ── Fetch usage on mount (dashboard landing) ────────────────────────
  useEffect(() => {
    let cancelled = false;
    async function fetchUsage() {
      try {
        const res = await fetch('/api/billing/usage', {
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
        });
        if (!res.ok) return;
        const data = (await res.json()) as UsageData;
        if (!cancelled) showUsageModalIfNeeded(data);
      } catch {
        // Silent fail — usage modal is non-blocking
      }
    }
    fetchUsage();
    return () => {
      cancelled = true;
    };
  }, [showUsageModalIfNeeded]);

  // ── Subscribe to realtime billing events via Socket.io ──────────────
  // We attach a window-level listener that the SocketProvider dispatches.
  // This avoids coupling to the SocketProvider internals.
  useEffect(() => {
    function handleBillingEvent(e: Event) {
      const detail = (e as CustomEvent<RealtimeBillingEvent>).detail;
      if (!detail) return;
      const et = detail.event_type || '';
      if (et === 'billing:renewal_reminder') {
        showRenewalModal(detail);
      } else if (
        et === 'billing:usage_warning' ||
        et === 'billing:usage_limit_exceeded'
      ) {
        // Realtime usage warning: show modal with provided numbers
        if (isDismissedRecently()) return;
        setModal({
          kind: 'usage',
          usage_percentage: detail.usage_percentage,
          tickets_used: detail.tickets_used,
          ticket_limit: detail.ticket_limit,
        });
      }
    }
    window.addEventListener('parwa:billing-event', handleBillingEvent);
    return () => {
      window.removeEventListener('parwa:billing-event', handleBillingEvent);
    };
  }, [showRenewalModal]);

  // ── Actions ─────────────────────────────────────────────────────────
  const handleDismiss = useCallback(() => {
    markDismissed();
    setModal({ kind: null });
  }, []);

  const handleUpgrade = useCallback(() => {
    markDismissed();
    setModal({ kind: null });
    router.push('/dashboard/billing');
  }, [router]);

  // ── Render ──────────────────────────────────────────────────────────
  const isOpen = modal.kind !== null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleDismiss()}>
      <DialogContent
        data-testid="usage-warning-modal"
        className="bg-[#1A1A1A] border border-white/[0.08] text-white max-w-md"
      >
        <DialogHeader>
          <div className="flex items-center gap-3">
            {modal.kind === 'renewal' ? <RenewalIcon /> : <WarningIcon />}
            <DialogTitle className="text-lg font-semibold">
              {modal.kind === 'renewal'
                ? 'Subscription Renewing Soon'
                : modal.kind === 'usage' && (modal.usage_percentage ?? 0) >= 100
                ? 'Plan Limit Reached'
                : 'Approaching Plan Limit'}
            </DialogTitle>
          </div>
          <DialogDescription className="text-zinc-400 sr-only">
            Billing notification
          </DialogDescription>
        </DialogHeader>

        {modal.kind === 'usage' && (
          <div className="space-y-4">
            <p className="text-sm text-zinc-300">
              You&apos;ve used{' '}
              <span
                data-testid="usage-percentage"
                className="font-semibold text-amber-400"
              >
                {modal.usage_percentage?.toFixed(1)}%
              </span>{' '}
              of your monthly ticket quota.
            </p>

            {typeof modal.tickets_used === 'number' &&
              typeof modal.ticket_limit === 'number' && (
                <div className="text-xs text-zinc-500">
                  {modal.tickets_used.toLocaleString()} /{' '}
                  {modal.ticket_limit.toLocaleString()} tickets used this month
                </div>
              )}

            {/* Progress bar */}
            <div
              className="h-2 rounded-full bg-white/[0.06] overflow-hidden"
              role="progressbar"
              aria-valuenow={Math.min(100, modal.usage_percentage ?? 0)}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="h-full rounded-full bg-gradient-to-r from-amber-500 to-red-500 transition-all"
                style={{
                  width: `${Math.min(100, modal.usage_percentage ?? 0)}%`,
                }}
              />
            </div>

            <p className="text-xs text-zinc-500">
              Additional tickets will be billed at $0.10 each as overage.
              Upgrade your plan to avoid overage charges.
            </p>
          </div>
        )}

        {modal.kind === 'renewal' && (
          <div className="space-y-4">
            <p className="text-sm text-zinc-300">
              {modal.message ||
                `Your ${modal.variant || ''} plan will auto-renew on ${
                  modal.renewal_date || 'soon'
                }.`}
            </p>
            {modal.amount && (
              <div className="text-xs text-zinc-500">
                Amount to be charged: ${modal.amount} {modal.variant ? `(${modal.variant})` : ''}
              </div>
            )}
            <p className="text-xs text-zinc-500">
              This is an automatic charge to your saved payment method —
              just like Netflix. You can cancel anytime from billing settings.
            </p>
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-2">
          <Button
            variant="ghost"
            onClick={handleDismiss}
            className="text-zinc-400 hover:text-zinc-200"
            data-testid="usage-warning-dismiss"
          >
            Remind me later
          </Button>
          <Button
            onClick={handleUpgrade}
            className="bg-orange-500 hover:bg-orange-600 text-white"
            data-testid="usage-warning-upgrade"
          >
            {modal.kind === 'renewal' ? 'Manage subscription' : 'Upgrade plan'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default UsageWarningModal;
