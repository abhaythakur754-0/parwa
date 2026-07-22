'use client';

import { useEffect, useState } from 'react';
import { VARIANT_PRICES, VARIANT_DISPLAY_NAMES, VARIANT_LIMITS, normalizeTier, type VariantTier } from '@/lib/pricing-config';

// ── Types ────────────────────────────────────────────────────────────

interface PlanInfo {
  name: string;
  tier: string;
  price: string;
  period: string;
  nextBilling: string;
  agents: string;
  tickets: string;
  channels: string;
}

interface Invoice {
  id: string;
  date: string;
  amount: string;
  status: string;
}

interface UsageItem {
  label: string;
  current: number;
  limit: number;
  unit: string;
}

interface BillingState {
  plan: PlanInfo | null;
  invoices: Invoice[];
  usage: UsageItem[];
  isLoading: boolean;
  error: string | null;
}

// ── Helpers ──────────────────────────────────────────────────────────

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return '—';
  }
}

function buildPlanFromStatus(statusData: {
  variant?: string | null;
  current_period_end?: string | null;
  subscription_status?: string;
}): PlanInfo {
  const tier: VariantTier = statusData.variant
    ? normalizeTier(statusData.variant)
    : 'parwa';
  const limits = VARIANT_LIMITS[tier];
  const price = VARIANT_PRICES[tier];
  const name = VARIANT_DISPLAY_NAMES[tier];

  return {
    name,
    tier: tier === 'parwa' ? 'Most Popular' : tier === 'high' ? 'Premium' : 'Starter',
    price: formatCurrency(price),
    period: '/month',
    nextBilling: formatDate(statusData.current_period_end),
    agents: `${limits.aiAgents} AI Agent${limits.aiAgents > 1 ? 's' : ''}`,
    tickets: `${limits.monthlyTickets.toLocaleString()} tickets/month`,
    channels: 'Email, Chat, SMS, Voice',
  };
}

function mapInvoices(rawInvoices: Array<Record<string, unknown>>): Invoice[] {
  if (!Array.isArray(rawInvoices)) return [];
  return rawInvoices.slice(0, 5).map((inv) => ({
    id: String(inv.id ?? inv.paddle_invoice_id ?? '—'),
    date: formatDate(inv.invoice_date as string | null) || formatDate(inv.created_at as string | null),
    amount: (() => {
      const amt = inv.amount;
      if (typeof amt === 'number') return formatCurrency(amt);
      if (typeof amt === 'string') {
        const parsed = parseFloat(amt);
        return isNaN(parsed) ? '—' : formatCurrency(parsed);
      }
      return '—';
    })(),
    status: String(inv.status ?? 'unknown'),
  }));
}

function buildUsageFromData(usageData: {
  tickets_used?: number;
  ticket_limit?: number;
}): UsageItem[] {
  const ticketsUsed = usageData.tickets_used ?? 0;
  const ticketLimit = usageData.ticket_limit ?? 0;

  const items: UsageItem[] = [];

  if (ticketLimit > 0) {
    items.push({
      label: 'Tickets Used',
      current: ticketsUsed,
      limit: ticketLimit,
      unit: '',
    });
  }

  return items;
}

// ── Component ────────────────────────────────────────────────────────

export default function BillingPage() {
  const [state, setState] = useState<BillingState>({
    plan: null,
    invoices: [],
    usage: [],
    isLoading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function loadBilling() {
      try {
        // Fetch billing status, invoices, and usage in parallel
        const [statusRes, invoicesRes, usageRes] = await Promise.allSettled([
          fetch('/api/billing/status', { credentials: 'include' }),
          fetch('/api/billing/invoices?page=1&page_size=5', { credentials: 'include' }),
          fetch('/api/billing/usage', { credentials: 'include' }),
        ]);

        if (cancelled) return;

        let plan: PlanInfo | null = null;
        let invoices: Invoice[] = [];
        let usage: UsageItem[] = [];
        const errors: string[] = [];

        // Status
        if (statusRes.status === 'fulfilled' && statusRes.value.ok) {
          const data = await statusRes.value.json();
          plan = buildPlanFromStatus(data);
        } else if (statusRes.status === 'rejected') {
          errors.push('billing status unavailable');
        }

        // Invoices
        if (invoicesRes.status === 'fulfilled' && invoicesRes.value.ok) {
          const data = await invoicesRes.value.json();
          invoices = mapInvoices(data.invoices ?? []);
        } else if (invoicesRes.status === 'rejected') {
          errors.push('invoices unavailable');
        }

        // Usage
        if (usageRes.status === 'fulfilled' && usageRes.value.ok) {
          const data = await usageRes.value.json();
          usage = buildUsageFromData(data);
        } else if (usageRes.status === 'rejected') {
          errors.push('usage unavailable');
        }

        if (cancelled) return;

        setState({
          plan,
          invoices,
          usage,
          isLoading: false,
          error: errors.length > 0 ? errors.join('; ') : null,
        });
      } catch (err) {
        if (cancelled) return;
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: err instanceof Error ? err.message : 'Failed to load billing data',
        }));
      }
    }

    loadBilling();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Loading State ───────────────────────────────────────────────────
  if (state.isLoading) {
    return (
      <div className="space-y-6">
        <div className="pb-6 border-b border-white/[0.06]">
          <h1 className="text-xl font-bold text-white">Billing</h1>
          <p className="text-sm text-zinc-500 mt-0.5">Loading billing information…</p>
        </div>
        <div className="rounded-2xl border border-white/[0.06] bg-[#1A1A1A] p-6">
          <div className="h-4 w-32 bg-white/5 rounded animate-pulse mb-4" />
          <div className="h-8 w-48 bg-white/5 rounded animate-pulse" />
        </div>
      </div>
    );
  }

  const plan = state.plan;
  const invoices = state.invoices;
  const usage = state.usage;

  return (
    <div className="space-y-6">
      <div className="pb-6 border-b border-white/[0.06]">
        <h1 className="text-xl font-bold text-white">Billing</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Manage your subscription, invoices, and payment methods
        </p>
      </div>

      {/* Error banner (non-blocking — partial data still shown) */}
      {state.error && (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3">
          <p className="text-xs text-amber-400">
            Some billing data could not be loaded: {state.error}
          </p>
        </div>
      )}

      {/* Current Plan */}
      {plan ? (
        <div className="rounded-2xl border-2 border-orange-500/30 bg-gradient-to-br from-orange-500/5 to-transparent p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h2 className="text-lg font-bold text-white">{plan.name}</h2>
                <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-orange-500/20 text-orange-400 border border-orange-500/30">
                  {plan.tier}
                </span>
              </div>
              <p className="text-sm text-zinc-400">Next billing date: {plan.nextBilling}</p>
            </div>
            <div className="text-right">
              <span className="text-3xl font-black text-orange-400">{plan.price}</span>
              <span className="text-sm text-zinc-400">{plan.period}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 mt-4">
            <span className="text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-zinc-300">{plan.agents}</span>
            <span className="text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-zinc-300">{plan.tickets}</span>
            <span className="text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-zinc-300">{plan.channels}</span>
          </div>
          <div className="flex gap-3 mt-5">
            <button className="text-xs font-medium px-4 py-2 rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/20 hover:bg-orange-500/20 transition-colors">
              Upgrade Plan
            </button>
            <button className="text-xs font-medium px-4 py-2 rounded-lg bg-white/5 text-zinc-400 border border-white/10 hover:border-white/20 hover:text-zinc-300 transition-colors">
              View All Plans
            </button>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-white/[0.06] bg-[#1A1A1A] p-6">
          <p className="text-sm text-zinc-400">
            No active subscription found.{' '}
            <a href="/pricing" className="text-orange-400 hover:underline">View plans</a>
          </p>
        </div>
      )}

      {/* Usage */}
      {usage.length > 0 && (
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
          <h3 className="text-sm font-semibold text-white mb-4">Current Usage</h3>
          <div className="space-y-4">
            {usage.map((item) => {
              const percent = item.limit > 0 ? Math.round((item.current / item.limit) * 100) : 0;
              return (
                <div key={item.label}>
                  <div className="flex items-center justify-between text-sm mb-1.5">
                    <span className="text-zinc-400">{item.label}</span>
                    <span className="text-zinc-300 font-medium">
                      {item.current.toLocaleString()} / {item.limit.toLocaleString()}{item.unit}
                    </span>
                  </div>
                  <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        percent > 80 ? 'bg-rose-500' : percent > 60 ? 'bg-yellow-500' : 'bg-emerald-500'
                      }`}
                      style={{ width: `${Math.min(percent, 100)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Invoices */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
        <div className="px-5 py-4 border-b border-white/[0.06]">
          <h3 className="text-sm font-semibold text-white">Recent Invoices</h3>
        </div>
        <div className="overflow-x-auto">
          {invoices.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.04]">
                  <th className="text-left px-5 py-3 text-zinc-500 font-medium text-xs uppercase">Invoice</th>
                  <th className="text-left px-5 py-3 text-zinc-500 font-medium text-xs uppercase">Date</th>
                  <th className="text-left px-5 py-3 text-zinc-500 font-medium text-xs uppercase">Amount</th>
                  <th className="text-left px-5 py-3 text-zinc-500 font-medium text-xs uppercase">Status</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id} className="border-b border-white/[0.04]">
                    <td className="px-5 py-3 text-zinc-300 font-medium">{inv.id}</td>
                    <td className="px-5 py-3 text-zinc-400">{inv.date}</td>
                    <td className="px-5 py-3 text-zinc-300">{inv.amount}</td>
                    <td className="px-5 py-3">
                      <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${
                        inv.status === 'paid'
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : inv.status === 'pending'
                          ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                          : inv.status === 'failed' || inv.status === 'refunded'
                          ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                          : 'bg-white/5 text-zinc-400 border-white/10'
                      }`}>
                        {inv.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="px-5 py-8 text-center">
              <p className="text-sm text-zinc-500">No invoices yet. Invoices will appear here after your first billing cycle.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
