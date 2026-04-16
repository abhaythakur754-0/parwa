/**
 * PARWA Billing API Client
 *
 * Typed client for all billing endpoints consumed by the billing dashboard.
 * Uses the shared apiClient (axios instance with httpOnly cookie auth + CSRF).
 */

import { get, post, patch, del } from '@/lib/api';
import apiClient from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────────

export type VariantType = 'starter' | 'growth' | 'high';
export type SubscriptionStatus = 'active' | 'past_due' | 'paused' | 'canceled' | 'payment_failed';
export type BillingFrequency = 'monthly' | 'yearly';
export type PaymentMethodType = 'card' | 'paypal' | 'wire' | 'apple_pay' | 'google_pay';

export interface VariantLimits {
  variant: VariantType;
  monthly_tickets: number;
  ai_agents: number;
  team_members: number;
  voice_slots: number;
  kb_docs: number;
  price: string;
  yearly_price: string;
}

export interface SubscriptionInfo {
  id: string;
  company_id: string;
  variant: VariantType;
  status: SubscriptionStatus;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  paddle_subscription_id: string | null;
  created_at: string;
  billing_frequency: BillingFrequency;
  pending_downgrade_tier: string | null;
  previous_tier: string | null;
  days_in_period: number | null;
  limits: VariantLimits | null;
}

export interface DashboardSummary {
  subscription_status: string | null;
  current_plan: string | null;
  billing_frequency: string | null;
  current_period_end: string | null;
  usage_summary: Record<string, unknown> | null;
  spending_summary: Record<string, unknown> | null;
  budget_alert: Record<string, unknown> | null;
  trial_status: Record<string, unknown> | null;
  pause_status: Record<string, unknown> | null;
}

export interface UsageResponse {
  current_month: string;
  tickets_used: number;
  ticket_limit: number;
  overage_tickets: number;
  overage_charges: string;
  usage_percentage: number;
}

export interface InvoiceInfo {
  id: string;
  company_id: string;
  paddle_invoice_id: string | null;
  amount: string;
  currency: string;
  status: string;
  invoice_date: string | null;
  due_date: string | null;
  paid_at: string | null;
  created_at: string | null;
}

export interface InvoiceListResponse {
  invoices: InvoiceInfo[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

export interface ProrationPreview {
  current_variant: VariantType;
  new_variant: VariantType;
  estimated_cost: {
    unused_credit: string;
    new_charge: string;
    net_cost: string;
    days_remaining: number;
  };
  proration_preview: {
    old_variant: VariantType;
    new_variant: VariantType;
    old_price: string;
    new_price: string;
    days_remaining: number;
    days_in_period: number;
    unused_amount: string;
    proration_credit: string;
    new_charge: string;
    net_charge: string;
    billing_cycle_start: string;
    billing_cycle_end: string;
  } | null;
  message: string;
}

export interface UpgradeResponse {
  subscription: SubscriptionInfo;
  proration: Record<string, unknown> | null;
  audit_id: string | null;
  message: string;
}

export interface SaveOfferResponse {
  discount_percentage: number;
  discount_months: number;
  message: string;
  original_price: string | null;
  discounted_price: string | null;
}

export interface CancelConfirmResponse {
  subscription: SubscriptionInfo;
  cancellation: Record<string, unknown>;
  message: string;
  data_retention_accepted: boolean;
}

export interface PaymentFailureStatus {
  has_active_failure: boolean;
  failure_id: string | null;
  failure_reason: string | null;
  service_stopped_at: string | null;
  days_since_failure: number | null;
  days_remaining_window: number | null;
  window_expires_at: string | null;
  message: string;
}

export interface PaymentMethodUpdateResponse {
  paddle_portal_url: string | null;
  message: string;
}

export interface VariantCatalogItem {
  variant_id: string;
  display_name: string;
  description: string | null;
  price_monthly: string;
  price_yearly: string;
  tickets_added: number;
  kb_docs_added: number;
  is_active: boolean;
  stacking_rules: {
    tickets_stack: boolean;
    kb_docs_stack: boolean;
    agents_stack: boolean;
    team_stack: boolean;
    voice_stack: boolean;
  };
}

export interface VariantCatalogResponse {
  catalog: VariantCatalogItem[];
  total: number;
  active_count: number;
}

export interface CompanyVariantInfo {
  id: string;
  company_id: string;
  variant_id: string;
  display_name: string;
  status: 'active' | 'inactive' | 'archived';
  price_per_month: string;
  tickets_added: number;
  kb_docs_added: number;
  activated_at: string | null;
  deactivated_at: string | null;
  paddle_subscription_item_id: string | null;
  created_at: string;
}

export interface CompanyVariantList {
  variants: CompanyVariantInfo[];
  total: number;
}

export interface EffectiveLimits {
  base_monthly_tickets: number;
  addon_tickets: number;
  effective_monthly_tickets: number;
  base_ai_agents: number;
  addon_ai_agents: number;
  effective_ai_agents: number;
  base_team_members: number;
  addon_team_members: number;
  effective_team_members: number;
  base_voice_slots: number;
  addon_voice_slots: number;
  effective_voice_slots: number;
  base_kb_docs: number;
  addon_kb_docs: number;
  effective_kb_docs: number;
  active_addons: string[];
}

// ── Plan comparison data (static) ──────────────────────────────────────────

export const PLAN_DATA: Record<VariantType, {
  name: string;
  badge: string;
  badgeColor: string;
  monthlyPrice: string;
  yearlyPrice: string;
  tickets: number;
  aiAgents: number;
  teamMembers: number;
  voiceSlots: number;
  kbDocs: number;
}> = {
  starter: {
    name: 'PARWA Starter',
    badge: 'Silver',
    badgeColor: 'bg-zinc-400/20 text-zinc-300 border-zinc-500/30',
    monthlyPrice: '$999',
    yearlyPrice: '$9,990',
    tickets: 2000,
    aiAgents: 1,
    teamMembers: 3,
    voiceSlots: 0,
    kbDocs: 100,
  },
  growth: {
    name: 'PARWA Growth',
    badge: 'Gold',
    badgeColor: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
    monthlyPrice: '$2,499',
    yearlyPrice: '$24,990',
    tickets: 5000,
    aiAgents: 3,
    teamMembers: 10,
    voiceSlots: 2,
    kbDocs: 500,
  },
  high: {
    name: 'PARWA High',
    badge: 'Platinum',
    badgeColor: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
    monthlyPrice: '$3,999',
    yearlyPrice: '$39,990',
    tickets: 15000,
    aiAgents: 5,
    teamMembers: 25,
    voiceSlots: 5,
    kbDocs: 2000,
  },
};

// ── Billing API Client ────────────────────────────────────────────────────

export const billingApi = {
  /** DI1: Single-call dashboard summary */
  getDashboardSummary: () => get<DashboardSummary>('/api/billing/dashboard-summary'),

  /** Get current subscription details */
  getSubscription: () =>
    get<{ subscription: SubscriptionInfo | null; has_subscription: boolean }>(
      '/api/billing/subscription',
    ),

  /** Get current month usage */
  getCurrentUsage: () => get<UsageResponse>('/api/billing/usage'),

  /** Get effective limits (base + addons stacked) */
  getEffectiveLimits: () => get<EffectiveLimits>('/api/billing/variants/effective-limits'),

  // ── Invoices ───────────────────────────────────────────────────────────

  getInvoices: (params?: { page?: number; page_size?: number }) =>
    get<InvoiceListResponse>('/api/billing/invoices', { params }),

  /** Download invoice PDF as Blob */
  getInvoicePdf: async (invoiceId: string): Promise<Blob> => {
    const response = await apiClient.get(`/api/billing/invoices/${invoiceId}/pdf`, {
      responseType: 'blob',
    });
    return response.data as Blob;
  },

  // ── Upgrade / Downgrade ────────────────────────────────────────────────

  previewUpgrade: (data: { new_variant: VariantType }) =>
    post<ProrationPreview>('/api/billing/proration/preview', data),

  updateSubscription: (data: { variant: VariantType }) =>
    patch<UpgradeResponse>('/api/billing/subscription', data),

  reactivateSubscription: () =>
    post<SubscriptionInfo>('/api/billing/subscription/reactivate'),

  // ── Cancel Flow ────────────────────────────────────────────────────────

  cancelFeedback: (data: { reason?: string; feedback?: string }) =>
    post('/api/billing/cancel/feedback', data),

  applySaveOffer: () => post<SaveOfferResponse>('/api/billing/cancel/save-offer'),

  cancelConfirm: (data: {
    effective_immediately?: boolean;
    accept_data_retention: boolean;
  }) => post<CancelConfirmResponse>('/api/billing/cancel/confirm', data),

  // ── Payment Method ─────────────────────────────────────────────────────

  updatePaymentMethod: (data?: { return_url?: string }) =>
    post<PaymentMethodUpdateResponse>('/api/billing/payment-method', data ?? {}),

  getPaymentFailureStatus: () =>
    get<PaymentFailureStatus>('/api/billing/payment-failure-status'),

  // ── Variant Add-Ons ───────────────────────────────────────────────────

  getVariantCatalog: () =>
    get<VariantCatalogResponse>('/api/billing/variants/catalog'),

  listVariants: () =>
    get<CompanyVariantList>('/api/billing/variants'),

  addVariant: (data: { variant_id: string }) =>
    post<CompanyVariantInfo>('/api/billing/variants', data),

  removeVariant: (variantId: string) =>
    del(`/api/billing/variants/${variantId}`),
};
