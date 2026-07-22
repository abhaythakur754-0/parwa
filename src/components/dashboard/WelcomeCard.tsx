/**
 * PARWA WelcomeCard
 *
 * Shows:
 *   - Greeting + company name + unique ID
 *   - Onboarding data: Company URL, Email, Connected KB
 *   - "Your Active Variants" panel — pulled from /api/billing/razorpay/subscriptions
 *     (real data, NOT mock). For each subscribed variant shows:
 *       • Variant name (Mini / PARWA / PARWA High)
 *       • Seats (quantity)
 *       • Monthly ticket limit (quantity × VARIANT_LIMITS[variant].monthlyTickets)
 *       • Combined usage progress bar (tickets used this month / total limit)
 *
 * If no subscriptions exist, the panel is hidden (no fake "Active Agents: 0"
 * fallback — that was misleading and showed mock data).
 *
 * Pricing source of truth: /src/lib/pricing-config.ts (matches backend SSOT)
 */

'use client';

import { Sparkles, Ticket, Globe, Mail, Database, Plug } from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  VARIANT_DISPLAY_NAMES,
  VARIANT_LIMITS,
  VARIANT_PRICES,
  type VariantTier,
} from '@/lib/pricing-config';

interface WelcomeCardProps {
  userName?: string | null;
  companyName?: string | null;
  uniqueId?: string | null;
  industry?: string | null;
  /** @deprecated No longer used — kept for backwards-compatible calls. */
  variantCount?: number;
}

// ── Types ────────────────────────────────────────────────────────────

interface SubscriptionRow {
  variant: string;
  status?: string;
  quantity?: number;
  current_period_end?: string | null;
  cancel_at_period_end?: boolean;
}

interface UsageRow {
  tickets_used?: number;
  ticket_limit?: number;
  ticketsUsed?: number;
  ticketsLimit?: number;
}

interface ActiveVariant {
  tier: VariantTier;
  name: string;
  seats: number;
  ticketLimit: number;
  pricePerSeat: number;
  currentPeriodEnd: string | null;
  status: string;
}

// ── Helpers ──────────────────────────────────────────────────────────

const VARIANT_TIER_KEYS: Record<string, VariantTier> = {
  mini: 'mini',
  parwa: 'parwa',
  high: 'high',
  // Legacy aliases that may still exist in DB rows
  starter: 'mini',
  growth: 'parwa',
  mini_parwa: 'mini',
  parwa_high: 'high',
};

function normalizeVariant(raw: string | undefined | null): VariantTier | null {
  if (!raw) return null;
  return VARIANT_TIER_KEYS[raw.toLowerCase().trim()] ?? null;
}

const VARIANT_DOT: Record<VariantTier, string> = {
  mini: 'bg-emerald-400',
  parwa: 'bg-sky-400',
  high: 'bg-amber-400',
};

function formatDate(dateStr: string | null | undefined): string | null {
  if (!dateStr) return null;
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return null;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return null;
  }
}

interface TrialInfo {
  is_trial: boolean;
  tickets_used: number;
  tickets_limit: number;
  time_remaining_hours: number;
  expired: boolean;
}

// ── Component ────────────────────────────────────────────────────────

export function WelcomeCard({
  userName,
  companyName,
  uniqueId,
  industry,
}: WelcomeCardProps) {
  const firstName = userName?.split(' ')[0] || 'there';
  const displayName = firstName.charAt(0).toUpperCase() + firstName.slice(1);

  const [activeVariants, setActiveVariants] = useState<ActiveVariant[]>([]);
  const [ticketsUsed, setTicketsUsed] = useState<number | null>(null);
  const [trialInfo, setTrialInfo] = useState<TrialInfo | null>(null);
  const [loading, setLoading] = useState(true);
  
  // ── Onboarding Data State ──
  const [onboardingData, setOnboardingData] = useState<{
    companyUrl?: string;
    workEmail?: string;
    kbConnected?: boolean;
    kbName?: string;
    integrationsCount?: number;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function load() {
      const subsPromise = fetch('/api/billing/razorpay/subscriptions', {
        credentials: 'include',
        signal: controller.signal,
      })
        .then((r) => (r.ok ? r.json() : []))
        .catch(() => []);

      const usagePromise = fetch('/api/billing/usage', {
        credentials: 'include',
        signal: controller.signal,
      })
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null);

      const trialPromise = fetch('/api/billing/razorpay/trial-status', {
        credentials: 'include',
        signal: controller.signal,
      })
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null);

      // ── Fetch Onboarding Data ──
      const onboardingPromise = fetch('/api/onboarding/state?user_id=demo', {
        credentials: 'include',
        signal: controller.signal,
      })
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null);

      // Then get user details if we have a session
      const userDetailsPromise = fetch('/api/onboarding/details', {
        credentials: 'include',
        signal: controller.signal,
      })
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null);

      // Get integrations count
      const integrationsPromise = fetch('/api/integrations', {
        credentials: 'include',
        signal: controller.signal,
      })
        .then((r) => (r.ok ? r.json() : []))
        .catch(() => []);

      const [subsRaw, usageRaw, trialRaw, onboardData, userDetails, integrationsData] = await Promise.all([
        subsPromise, 
        usagePromise, 
        trialPromise, 
        onboardingPromise,
        userDetailsPromise,
        integrationsPromise,
      ]);
      
      if (cancelled) return;

      // ── Process Onboarding Data ──
      if (onboardData || userDetails) {
        setOnboardingData({
          companyUrl: userDetails?.company_url || onboardData?.company_url,
          workEmail: userDetails?.work_email || onboardData?.work_email,
          kbConnected: onboardData?.kb_completed || false,
          kbName: onboardData?.kb_name || undefined,
          integrationsCount: Array.isArray(integrationsData) ? integrationsData.length : 0,
        });
      }

      const subs: SubscriptionRow[] = Array.isArray(subsRaw)
        ? subsRaw
        : Array.isArray((subsRaw as any)?.items)
          ? (subsRaw as any).items
          : [];

      const ACTIVE_STATUSES = new Set(['active', 'trialing', 'past_due', 'authenticated']);
      const active: ActiveVariant[] = [];
      for (const s of subs) {
        const status = (s.status || 'active').toLowerCase();
        if (!ACTIVE_STATUSES.has(status)) continue;
        const tier = normalizeVariant(s.variant);
        if (!tier) continue;
        const seats = Math.max(1, Number(s.quantity ?? 1));
        const limits = VARIANT_LIMITS[tier];
        active.push({
          tier,
          name: VARIANT_DISPLAY_NAMES[tier],
          seats,
          ticketLimit: seats * limits.monthlyTickets,
          pricePerSeat: VARIANT_PRICES[tier],
          currentPeriodEnd: s.current_period_end ?? null,
          status,
        });
      }

      // Merge duplicate variant rows (in case backend returns one row per seat)
      const merged: ActiveVariant[] = [];
      for (const a of active) {
        const existing = merged.find((m) => m.tier === a.tier);
        if (existing) {
          existing.seats += a.seats;
          existing.ticketLimit += a.ticketLimit;
        } else {
          merged.push({ ...a });
        }
      }

      setActiveVariants(merged);
      setTrialInfo(trialRaw as TrialInfo | null);

      const usage: UsageRow = (usageRaw as any) || {};
      const used =
        Number(usage.tickets_used ?? usage.ticketsUsed ?? 0) || 0;
      setTicketsUsed(used);

      setLoading(false);
    }

    load();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  // For trial users with no paid subscriptions, show PARWA High (Trial)
  // as their active variant. They get the full High tier experience during
  // the 24h / 15-ticket trial window.
  const isTrial = trialInfo?.is_trial === true && activeVariants.length === 0;
  const displayVariants = isTrial
    ? [{
        tier: 'high' as VariantTier,
        name: 'PARWA High (Trial)',
        seats: 1,
        ticketLimit: trialInfo!.tickets_limit,
        pricePerSeat: VARIANT_PRICES.high,
        currentPeriodEnd: null,
        status: 'trial',
      }]
    : activeVariants;

  const totalLimit = displayVariants.reduce((sum, v) => sum + v.ticketLimit, 0);
  const used = ticketsUsed ?? 0;
  const usagePct =
    totalLimit > 0 ? Math.min(100, Math.round((used / totalLimit) * 100)) : 0;
  const remaining = Math.max(0, totalLimit - used);

  return (
    <div className="glass rounded-2xl p-6 relative overflow-hidden">
      <div className="absolute -top-20 -right-20 w-60 h-60 bg-orange-500/5 rounded-full blur-3xl pointer-events-none" />
      <div className="relative">
        {/* Greeting + company info on right */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500/20 to-orange-600/10 border border-orange-500/20 flex items-center justify-center shrink-0">
              <Sparkles className="w-5 h-5 text-orange-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">
                Welcome back, {displayName}!
              </h2>
              <p className="text-xs text-white/40 mt-0.5">
                {companyName || 'Your company'} &middot; {industry || 'All Industries'}
              </p>
            </div>
          </div>
          {/* Unique ID on right */}
          {uniqueId && (
            <div className="flex flex-col items-end shrink-0">
              <span className="text-[10px] text-white/30 uppercase tracking-wider">Unique ID</span>
              <span className="text-sm font-mono font-semibold text-orange-400">{uniqueId}</span>
            </div>
          )}
        </div>

        {/* ── Onboarding Data Panel ── */}
        {onboardingData && (
          <div className="px-3 py-2.5 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-2">
            <p className="text-[10px] text-white/30 uppercase tracking-wider font-medium">
              Account Details
            </p>
            
            <div className="flex flex-wrap gap-3 text-xs">
              {onboardingData.companyUrl && (
                <a 
                  href={onboardingData.companyUrl.startsWith('http') ? onboardingData.companyUrl : `https://${onboardingData.companyUrl}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-white/[0.03] text-zinc-300 hover:text-orange-400 hover:bg-white/[0.05] transition-colors"
                >
                  <Globe className="w-3 h-3" />
                  <span className="truncate max-w-[150px]">{onboardingData.companyUrl}</span>
                </a>
              )}
              
              {onboardingData.workEmail && (
                <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-white/[0.03] text-zinc-300">
                  <Mail className="w-3 h-3" />
                  <span className="truncate max-w-[180px]">{onboardingData.workEmail}</span>
                </span>
              )}
              
              {onboardingData.kbConnected && (
                <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <Database className="w-3 h-3" />
                  KB: {onboardingData.kbName || 'Connected'}
                </span>
              )}
              
              {onboardingData.integrationsCount !== undefined && onboardingData.integrationsCount > 0 && (
                <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
                  <Plug className="w-3 h-3" />
                  {onboardingData.integrationsCount} Integration{onboardingData.integrationsCount > 1 ? 's' : ''}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Active Variants panel — real data, no mock fallback */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.06] animate-pulse h-16"
              />
            ))}
          </div>
        ) : displayVariants.length === 0 ? (
          // No active subscriptions AND not in trial — show empty state
          <div className="px-3 py-3 rounded-xl bg-white/[0.02] border border-white/[0.06] flex items-center gap-3">
            <Ticket className="w-4 h-4 text-zinc-500 shrink-0" />
            <p className="text-xs text-zinc-500">
              No active variant subscription. Visit{' '}
              <a href="/models" className="text-orange-400 hover:text-orange-300 underline">
                Models
              </a>{' '}
              to subscribe.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Per-variant cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {displayVariants.map((v) => {
                const nextRenewal = formatDate(v.currentPeriodEnd);
                return (
                  <div
                    key={v.tier}
                    className="px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]"
                  >
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className={`w-2 h-2 rounded-full ${VARIANT_DOT[v.tier]} shrink-0`} />
                      <p className="text-[11px] text-white/60 font-medium truncate">{v.name}</p>
                      <span className="ml-auto text-[10px] text-white/40 tabular-nums">
                        ×{v.seats}
                      </span>
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className="text-sm font-semibold text-white tabular-nums">
                        {v.ticketLimit.toLocaleString()}
                      </span>
                      <span className="text-[10px] text-white/40">tickets/mo</span>
                    </div>
                    {nextRenewal && (
                      <p className="text-[10px] text-white/30 mt-0.5">Renews {nextRenewal}</p>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Combined usage bar */}
            {totalLimit > 0 && (
              <div className="px-3 py-2.5 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                <div className="flex items-center justify-between mb-1.5">
                  <p className="text-[10px] text-white/40 uppercase tracking-wider">
                    Monthly Ticket Usage
                  </p>
                  <p className="text-[11px] text-white/60 tabular-nums">
                    {used.toLocaleString()} / {totalLimit.toLocaleString()} used ·{' '}
                    <span className="text-orange-300">{remaining.toLocaleString()} left</span>
                  </p>
                </div>
                <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                  <div
                    className={`h-full rounded-full bg-gradient-to-r ${
                      usagePct >= 90
                        ? 'from-red-500 to-red-400'
                        : usagePct >= 75
                          ? 'from-amber-500 to-orange-400'
                          : 'from-orange-500 to-amber-400'
                    } transition-all duration-500`}
                    style={{ width: `${usagePct}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
