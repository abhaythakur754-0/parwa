/**
 * PARWA Billing Store
 *
 * Zustand store for billing and subscription data.
 * Manages current plan, invoices, usage, and payment methods.
 */

import { create } from 'zustand';
import { VariantTier } from './variant-store';

// ── Types ────────────────────────────────────────────────────────────

export interface Invoice {
  id: string;
  amount: number;
  currency: string;
  status: 'paid' | 'pending' | 'failed' | 'refunded';
  date: string;
  description: string;
  downloadUrl: string | null;
}

export interface PaymentMethod {
  id: string;
  type: 'card' | 'bank_transfer';
  last4: string;
  brand: string;
  expiryMonth: number;
  expiryYear: number;
  isDefault: boolean;
}

export interface BillingUsage {
  ticketsUsed: number;
  ticketsLimit: number;
  messagesUsed: number;
  messagesLimit: number;
  storageUsed: number; // MB
  storageLimit: number; // MB
  apiCallsUsed: number;
  apiCallsLimit: number;
}

export interface BillingState {
  currentTier: VariantTier;
  currentPrice: number;
  renewalDate: string | null;
  invoices: Invoice[];
  paymentMethods: PaymentMethod[];
  usage: BillingUsage;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchBilling: () => Promise<void>;
  fetchInvoices: () => Promise<void>;
  fetchUsage: () => Promise<void>;
  changePlan: (newTier: VariantTier) => Promise<void>;
  cancelSubscription: () => Promise<void>;
}

// ── Helpers ──────────────────────────────────────────────────────────

const TIER_PRICES: Record<VariantTier, number> = {
  mini: 999,
  pro: 2499,
  high: 3999,
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Store ───────────────────────────────────────────────────────────

export const useBillingStore = create<BillingState>((set, get) => ({
  currentTier: 'mini',
  currentPrice: 999,
  renewalDate: null,
  invoices: [],
  paymentMethods: [],
  usage: {
    ticketsUsed: 0,
    ticketsLimit: 1000,
    messagesUsed: 0,
    messagesLimit: 10000,
    storageUsed: 0,
    storageLimit: 500,
    apiCallsUsed: 0,
    apiCallsLimit: 5000,
  },
  isLoading: false,
  error: null,

  fetchBilling: async () => {
    set({ isLoading: true, error: null });
    try {
      const res = await fetch(`${API_BASE}/api/v1/billing/subscription`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        // Default to mini on 404/5xx
        if (res.status >= 400) {
          set({
            currentTier: 'mini',
            currentPrice: 999,
            isLoading: false,
          });
          return;
        }
      }

      const data = await res.json();
      const tier = (data.variant_tier || data.tier || 'mini') as VariantTier;

      set({
        currentTier: tier,
        currentPrice: TIER_PRICES[tier] || 999,
        renewalDate: data.renewal_date || data.current_period_end || null,
        isLoading: false,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch billing',
      });
    }
  },

  fetchInvoices: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/billing/invoices`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) return;

      const data = await res.json();
      const invoices = Array.isArray(data) ? data : (data.invoices || []);

      set({
        invoices: invoices.map((inv: Record<string, unknown>) => ({
          id: String(inv.id || ''),
          amount: Number(inv.amount || 0),
          currency: String(inv.currency || 'USD'),
          status: (inv.status || 'pending') as Invoice['status'],
          date: String(inv.date || inv.created_at || ''),
          description: String(inv.description || ''),
          downloadUrl: inv.download_url ? String(inv.download_url) : null,
        })),
      });
    } catch {
      // Silently fail — invoices are non-critical
    }
  },

  fetchUsage: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/billing/usage`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) return;

      const data = await res.json();

      set({
        usage: {
          ticketsUsed: Number(data.tickets_used ?? data.ticketsUsed ?? 0),
          ticketsLimit: Number(data.tickets_limit ?? data.ticketsLimit ?? 1000),
          messagesUsed: Number(data.messages_used ?? data.messagesUsed ?? 0),
          messagesLimit: Number(data.messages_limit ?? data.messagesLimit ?? 10000),
          storageUsed: Number(data.storage_used ?? data.storageUsed ?? 0),
          storageLimit: Number(data.storage_limit ?? data.storageLimit ?? 500),
          apiCallsUsed: Number(data.api_calls_used ?? data.apiCallsUsed ?? 0),
          apiCallsLimit: Number(data.api_calls_limit ?? data.apiCallsLimit ?? 5000),
        },
      });
    } catch {
      // Silently fail
    }
  },

  changePlan: async (newTier: VariantTier) => {
    set({ isLoading: true, error: null });
    try {
      const res = await fetch(`${API_BASE}/api/v1/billing/subscription`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ variant_tier: newTier }),
      });

      if (!res.ok) {
        throw new Error(`Failed to change plan: ${res.status}`);
      }

      set({
        currentTier: newTier,
        currentPrice: TIER_PRICES[newTier],
        isLoading: false,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to change plan',
      });
      throw error;
    }
  },

  cancelSubscription: async () => {
    set({ isLoading: true, error: null });
    try {
      const res = await fetch(`${API_BASE}/api/v1/billing/subscription`, {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        throw new Error(`Failed to cancel subscription: ${res.status}`);
      }

      set({
        currentTier: 'mini',
        currentPrice: 999,
        isLoading: false,
        renewalDate: null,
      });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to cancel subscription',
      });
      throw error;
    }
  },
}));
