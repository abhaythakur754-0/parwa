'use client';

import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  billingApi,
  PLAN_DATA,
  type VariantType,
  type DashboardSummary,
  type UsageResponse,
  type InvoiceInfo,
  type InvoiceListResponse,
  type ProrationPreview,
  type UpgradeResponse,
  type SaveOfferResponse,
  type CancelConfirmResponse,
  type PaymentFailureStatus,
  type PaymentMethodUpdateResponse,
  type VariantCatalogItem,
  type CompanyVariantInfo,
  type EffectiveLimits,
} from '@/lib/billing-api';

// ── Skeleton Helper ────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-white/[0.06]', className)} />;
}

// ── Inline SVG Icons ───────────────────────────────────────────────────────

function CreditCardIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z" />
    </svg>
  );
}

function BoltIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  );
}

function ChartBarIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
  );
}

function ArrowUpIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" />
    </svg>
  );
}

function ArrowDownIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5L12 21m0 0l-7.5-7.5M12 21V3" />
    </svg>
  );
}

function DocumentArrowDownIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
    </svg>
  );
}

function ExclamationTriangleIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
    </svg>
  );
}

function XMarkIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  );
}

function MinusIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 12h-15" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className={className}>
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

// ── Progress Bar Color Helper ──────────────────────────────────────────────

function usageColor(pct: number): string {
  if (pct > 0.85) return 'bg-red-500';
  if (pct > 0.60) return 'bg-yellow-500';
  return 'bg-emerald-500';
}

function usageTextColor(pct: number): string {
  if (pct > 0.85) return 'text-red-400';
  if (pct > 0.60) return 'text-yellow-400';
  return 'text-emerald-400';
}

// ── Format Helpers ─────────────────────────────────────────────────────────

function formatCurrency(val: string | number | undefined): string {
  if (val === undefined || val === null) return '$0.00';
  const n = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(n)) return '$0.00';
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return 'N/A';
  }
}

function invoiceStatusBadge(status: string) {
  const s = status.toLowerCase();
  if (s === 'paid' || s === 'completed') return 'bg-emerald-500/15 text-emerald-400';
  if (s === 'pending') return 'bg-yellow-500/15 text-yellow-400';
  if (s === 'failed') return 'bg-red-500/15 text-red-400';
  return 'bg-zinc-500/15 text-zinc-400';
}

// ── Error Fallback ─────────────────────────────────────────────────────────

function SectionError({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
      <p className="text-sm text-zinc-500">{message || 'Unable to load data'}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-xs text-[#FF7F11] hover:underline">
          Try again
        </button>
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// Main Billing Page Component
// ════════════════════════════════════════════════════════════════════════════

export default function BillingPage() {
  // ── State: Dashboard Summary (B1) ──────────────────────────────────────
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState(false);

  // ── State: Usage (B2) ──────────────────────────────────────────────────
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [effectiveLimits, setEffectiveLimits] = useState<EffectiveLimits | null>(null);
  const [usageLoading, setUsageLoading] = useState(true);
  const [usageError, setUsageError] = useState(false);

  // ── State: Invoices (B6) ──────────────────────────────────────────────
  const [invoices, setInvoices] = useState<InvoiceInfo[]>([]);
  const [invoicePagination, setInvoicePagination] = useState({ page: 1, total_pages: 1, total: 0 });
  const [invoicesLoading, setInvoicesLoading] = useState(true);
  const [invoicesError, setInvoicesError] = useState(false);

  // ── State: Payment (B7) ───────────────────────────────────────────────
  const [paymentFailure, setPaymentFailure] = useState<PaymentFailureStatus | null>(null);
  const [paymentFailureLoading, setPaymentFailureLoading] = useState(true);

  // ── State: Variant Catalog (B9/B10) ───────────────────────────────────
  const [catalog, setCatalog] = useState<VariantCatalogItem[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState(false);
  const [activeVariants, setActiveVariants] = useState<CompanyVariantInfo[]>([]);
  const [variantLoadingMap, setVariantLoadingMap] = useState<Record<string, boolean>>({});

  // ── State: Modals ──────────────────────────────────────────────────────
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [cancelStep, setCancelStep] = useState<1 | 2 | 3>(1);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelFeedback, setCancelFeedback] = useState('');
  const [cancelConfirmCheck, setCancelConfirmCheck] = useState(false);
  const [saveOfferData, setSaveOfferData] = useState<SaveOfferResponse | null>(null);
  const [prorationPreview, setProrationPreview] = useState<ProrationPreview | null>(null);
  const [prorationLoading, setProrationLoading] = useState(false);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState<VariantType | null>(null);

  // ── Derived ────────────────────────────────────────────────────────────
  const currentVariant: VariantType = (summary?.current_plan as VariantType) || 'starter';
  const currentPlanData = PLAN_DATA[currentVariant];
  const hasSubscription = summary?.subscription_status !== null && summary?.subscription_status !== undefined;
  const isCanceled = summary?.subscription_status === 'canceled';
  const isPaymentFailed = summary?.subscription_status === 'payment_failed';

  // ── Data Loading ───────────────────────────────────────────────────────

  const loadSummary = useCallback(async () => {
    setSummaryLoading(true);
    setSummaryError(false);
    try {
      const data = await billingApi.getDashboardSummary();
      setSummary(data);
    } catch (error) {
      const msg = getErrorMessage(error);
      if (msg.includes('404') || msg.includes('not found')) {
        setSummary(null);
      } else {
        setSummaryError(true);
      }
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  const loadUsage = useCallback(async () => {
    setUsageLoading(true);
    setUsageError(false);
    try {
      const [usageData, limitsData] = await Promise.allSettled([
        billingApi.getCurrentUsage(),
        billingApi.getEffectiveLimits(),
      ]);
      if (usageData.status === 'fulfilled') setUsage(usageData.value);
      else setUsageError(true);
      if (limitsData.status === 'fulfilled') setEffectiveLimits(limitsData.value);
    } catch {
      setUsageError(true);
    } finally {
      setUsageLoading(false);
    }
  }, []);

  const loadInvoices = useCallback(async (page: number = 1) => {
    setInvoicesLoading(true);
    setInvoicesError(false);
    try {
      const data = await billingApi.getInvoices({ page, page_size: 10 });
      setInvoices(data.invoices);
      setInvoicePagination(data.pagination);
    } catch {
      setInvoicesError(true);
    } finally {
      setInvoicesLoading(false);
    }
  }, []);

  const loadPaymentFailure = useCallback(async () => {
    setPaymentFailureLoading(true);
    try {
      const data = await billingApi.getPaymentFailureStatus();
      setPaymentFailure(data);
    } catch {
      /* silent */
    } finally {
      setPaymentFailureLoading(false);
    }
  }, []);

  const loadCatalog = useCallback(async () => {
    setCatalogLoading(true);
    setCatalogError(false);
    try {
      const data = await billingApi.getVariantCatalog();
      setCatalog(data.catalog);
    } catch {
      setCatalogError(true);
    } finally {
      setCatalogLoading(false);
    }
  }, []);

  useEffect(() => {
    Promise.allSettled([loadSummary(), loadUsage(), loadInvoices(1), loadPaymentFailure(), loadCatalog()]);
  }, [loadSummary, loadUsage, loadInvoices, loadPaymentFailure, loadCatalog]);

  // ── Handlers ───────────────────────────────────────────────────────────

  const handlePreviewUpgrade = async (variant: VariantType) => {
    setSelectedVariant(variant);
    setProrationPreview(null);
    setProrationLoading(true);
    try {
      const data = await billingApi.previewUpgrade({ new_variant: variant });
      setProrationPreview(data);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setProrationLoading(false);
    }
  };

  const handleConfirmUpgrade = async () => {
    if (!selectedVariant) return;
    setConfirmLoading(true);
    try {
      const result: UpgradeResponse = await billingApi.updateSubscription({ variant: selectedVariant });
      toast.success(result.message || `Upgraded to ${PLAN_DATA[selectedVariant].name}`);
      setUpgradeModalOpen(false);
      setProrationPreview(null);
      setSelectedVariant(null);
      loadSummary();
      loadUsage();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleConfirmDowngrade = async () => {
    if (!selectedVariant) return;
    setConfirmLoading(true);
    try {
      const result: UpgradeResponse = await billingApi.updateSubscription({ variant: selectedVariant });
      toast.success(result.message || `Downgrade scheduled to ${PLAN_DATA[selectedVariant].name}`);
      setUpgradeModalOpen(false);
      setProrationPreview(null);
      setSelectedVariant(null);
      loadSummary();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleCancelStep1 = async () => {
    try {
      await billingApi.cancelFeedback({ reason: cancelReason, feedback: cancelFeedback });
      setCancelStep(2);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const handleCancelStep2 = async () => {
    try {
      const data = await billingApi.applySaveOffer();
      setSaveOfferData(data);
      toast.success(data.message);
      setCancelModalOpen(false);
      setCancelStep(1);
      setCancelReason('');
      setCancelFeedback('');
      loadSummary();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const handleCancelStep3 = async () => {
    if (!cancelConfirmCheck) {
      toast.error('Please confirm the data retention checkbox');
      return;
    }
    setConfirmLoading(true);
    try {
      await billingApi.cancelConfirm({ accept_data_retention: true });
      toast.success('Subscription canceled successfully');
      setCancelModalOpen(false);
      setCancelStep(1);
      setCancelReason('');
      setCancelFeedback('');
      setCancelConfirmCheck(false);
      loadSummary();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleUpdatePayment = async () => {
    try {
      const data: PaymentMethodUpdateResponse = await billingApi.updatePaymentMethod({
        return_url: window.location.href,
      });
      if (data.paddle_portal_url) {
        window.open(data.paddle_portal_url, '_blank');
        toast.success('Redirecting to payment portal...');
      } else {
        toast.error('Unable to open payment portal');
      }
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const handleAddVariant = async (variantId: string) => {
    setVariantLoadingMap(prev => ({ ...prev, [variantId]: true }));
    try {
      await billingApi.addVariant({ variant_id: variantId });
      toast.success('Add-on activated successfully');
      loadCatalog();
      loadUsage();
      loadSummary();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setVariantLoadingMap(prev => ({ ...prev, [variantId]: false }));
    }
  };

  const handleRemoveVariant = async (variantId: string) => {
    setVariantLoadingMap(prev => ({ ...prev, [variantId]: true }));
    try {
      await billingApi.removeVariant(variantId);
      toast.success('Add-on removal scheduled');
      loadCatalog();
      loadUsage();
      loadSummary();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setVariantLoadingMap(prev => ({ ...prev, [variantId]: false }));
    }
  };

  const handleDownloadPdf = async (invoiceId: string) => {
    try {
      const blob = await billingApi.getInvoicePdf(invoiceId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `invoice_${invoiceId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const handleReactivate = async () => {
    try {
      await billingApi.reactivateSubscription();
      toast.success('Subscription reactivated');
      loadSummary();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  // ── Tier ordering for upgrade/downgrade logic ──────────────────────────
  const tierOrder: Record<VariantType, number> = { starter: 1, growth: 2, high: 3 };
  const isUpgrade = selectedVariant ? tierOrder[selectedVariant] > tierOrder[currentVariant] : false;
  const isDowngrade = selectedVariant ? tierOrder[selectedVariant] < tierOrder[currentVariant] : false;

  // ════════════════════════════════════════════════════════════════════════
  // Render
  // ════════════════════════════════════════════════════════════════════════

  return (
    <div className="jarvis-page-body min-h-screen bg-[#0A0A0A]">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Page Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FF7F11]/10">
              <CreditCardIcon className="h-5 w-5 text-[#FF7F11]" />
            </div>
            <h1 className="text-2xl font-bold text-white">Billing</h1>
          </div>
          <p className="text-sm text-zinc-500 ml-[52px]">
            Manage your subscription, usage, invoices, and payment methods.
          </p>
        </div>

        {/* ── Payment Failure Alert (top) ─────────────────────────────── */}
        {!paymentFailureLoading && paymentFailure?.has_active_failure && (
          <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/5 p-4">
            <div className="flex items-start gap-3">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-400 mt-0.5 shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-red-300">Payment Failed</p>
                <p className="text-sm text-red-400/80 mt-1">{paymentFailure.message}</p>
                <button
                  onClick={handleUpdatePayment}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-red-500/20 px-3 py-1.5 text-xs font-medium text-red-300 hover:bg-red-500/30 transition-colors"
                >
                  Update Payment Method
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── B1: Current Plan Hero Card ──────────────────────────────── */}
        {summaryLoading ? (
          <Skeleton className="h-40 mb-6" />
        ) : summaryError ? (
          <SectionError message="Unable to load subscription details" onRetry={loadSummary} />
        ) : !hasSubscription ? (
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-8 mb-6 text-center">
            <CreditCardIcon className="h-12 w-12 text-zinc-600 mx-auto mb-4" />
            <h2 className="text-lg font-semibold text-zinc-300 mb-2">No Active Subscription</h2>
            <p className="text-sm text-zinc-500 mb-6">
              You don&apos;t have an active subscription. Choose a plan to get started.
            </p>
            <button
              onClick={() => setUpgradeModalOpen(true)}
              className="inline-flex items-center gap-2 rounded-xl bg-[#FF7F11] px-6 py-2.5 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
            >
              <PlusIcon className="h-4 w-4" />
              Choose a Plan
            </button>
          </div>
        ) : (
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6 mb-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#FF7F11]/10">
                  <BoltIcon className="h-7 w-7 text-[#FF7F11]" />
                </div>
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <h2 className="text-xl font-bold text-white">{currentPlanData?.name || 'PARWA'}</h2>
                    <span className={cn('inline-flex rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider', currentPlanData?.badgeColor)}>
                      {currentPlanData?.badge}
                    </span>
                    {isCanceled && (
                      <span className="inline-flex rounded-full bg-red-500/15 border border-red-500/30 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-red-400">
                        Canceled
                      </span>
                    )}
                    {isPaymentFailed && (
                      <span className="inline-flex rounded-full bg-red-500/15 border border-red-500/30 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-red-400">
                        Payment Failed
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-zinc-400">
                    {summary?.billing_frequency === 'yearly' ? 'Yearly' : 'Monthly'} billing
                    {summary?.current_period_end && (
                      <>
                        {' · '}Next billing:{' '}
                        <span className="text-zinc-300">{formatDate(summary.current_period_end)}</span>
                      </>
                    )}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {isCanceled && (
                  <button
                    onClick={handleReactivate}
                    className="rounded-xl bg-emerald-500/15 border border-emerald-500/30 px-4 py-2 text-sm font-medium text-emerald-400 hover:bg-emerald-500/25 transition-colors"
                  >
                    Reactivate
                  </button>
                )}
                {!isCanceled && (
                  <button
                    onClick={() => {
                      setUpgradeModalOpen(true);
                      setSelectedVariant(null);
                      setProrationPreview(null);
                    }}
                    className="inline-flex items-center gap-2 rounded-xl bg-[#FF7F11] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
                  >
                    <ArrowUpIcon className="h-4 w-4" />
                    Change Plan
                  </button>
                )}
              </div>
            </div>
            {/* Pricing info */}
            <div className="mt-5 flex flex-wrap items-center gap-6 text-sm">
              <div>
                <span className="text-zinc-500">Plan price: </span>
                <span className="font-semibold text-white">
                  {summary?.billing_frequency === 'yearly'
                    ? currentPlanData?.yearlyPrice
                    : currentPlanData?.monthlyPrice}
                  <span className="text-zinc-500 font-normal">
                    /{summary?.billing_frequency === 'yearly' ? 'year' : 'mo'}
                  </span>
                </span>
              </div>
              {currentPlanData && (
                <>
                  <div className="text-zinc-600">|</div>
                  <div>
                    <span className="text-zinc-500">Tickets: </span>
                    <span className="text-zinc-300">{currentPlanData.tickets.toLocaleString()}/mo</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">AI Agents: </span>
                    <span className="text-zinc-300">{currentPlanData.aiAgents}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Team: </span>
                    <span className="text-zinc-300">{currentPlanData.teamMembers}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">KB Docs: </span>
                    <span className="text-zinc-300">{currentPlanData.kbDocs.toLocaleString()}</span>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* ── B8: Overage Warning ──────────────────────────────────────── */}
        {usage && usage.overage_tickets > 0 && (
          <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/5 p-5">
            <div className="flex items-start gap-3">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-400 mt-0.5 shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-red-300">Overage Detected</p>
                <p className="text-sm text-zinc-400 mt-1">
                  You&apos;ve exceeded your ticket limit by{' '}
                  <span className="font-semibold text-red-300">{usage.overage_tickets.toLocaleString()}</span> tickets.
                  Additional charge:{' '}
                  <span className="font-semibold text-red-300">{formatCurrency(usage.overage_charges)}</span>
                </p>
                <button
                  onClick={() => setUpgradeModalOpen(true)}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[#FF7F11]/15 px-3 py-1.5 text-xs font-medium text-[#FF7F11] hover:bg-[#FF7F11]/25 transition-colors"
                >
                  <ArrowUpIcon className="h-3 w-3" />
                  Upgrade Plan
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── B2: Usage Meters ─────────────────────────────────────────── */}
        {usageLoading ? (
          <Skeleton className="h-56 mb-6" />
        ) : usageError ? (
          <SectionError message="Unable to load usage data" onRetry={loadUsage} />
        ) : usage && effectiveLimits ? (
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5 mb-6">
            <div className="flex items-center gap-2 mb-5">
              <ChartBarIcon className="h-5 w-5 text-[#FF7F11]" />
              <h3 className="text-base font-semibold text-white">Usage This Month</h3>
              <span className="text-xs text-zinc-500 ml-auto">{usage.current_month}</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {/* Tickets */}
              <UsageMeter
                label="Tickets"
                used={usage.tickets_used}
                limit={effectiveLimits.effective_monthly_tickets}
              />
              {/* AI Agents */}
              <div className="rounded-xl bg-[#141414] border border-white/[0.04] p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-400">AI Agents</span>
                  <span className="text-sm font-medium text-zinc-300">{effectiveLimits.effective_ai_agents} available</span>
                </div>
              </div>
              {/* Team Members */}
              <div className="rounded-xl bg-[#141414] border border-white/[0.04] p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-400">Team Members</span>
                  <span className="text-sm font-medium text-zinc-300">{effectiveLimits.effective_team_members} seats</span>
                </div>
              </div>
              {/* KB Docs */}
              <div className="rounded-xl bg-[#141414] border border-white/[0.04] p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-zinc-400">KB Documents</span>
                  <span className="text-sm font-medium text-zinc-300">{effectiveLimits.effective_kb_docs.toLocaleString()} available</span>
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {/* ── B9/B10: Industry Add-Ons ────────────────────────────────── */}
        <div className="mb-6">
          <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
            <BoltIcon className="h-5 w-5 text-[#FF7F11]" />
            Industry Add-Ons
          </h3>
          {catalogLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Skeleton className="h-44" />
              <Skeleton className="h-44" />
            </div>
          ) : catalogError ? (
            <SectionError message="Unable to load add-ons" onRetry={loadCatalog} />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {catalog.map(item => (
                <VariantCard
                  key={item.variant_id}
                  item={item}
                  loading={!!variantLoadingMap[item.variant_id]}
                  onAdd={() => handleAddVariant(item.variant_id)}
                  onRemove={() => handleRemoveVariant(item.variant_id)}
                  billingFrequency={summary?.billing_frequency as 'monthly' | 'yearly' | undefined}
                />
              ))}
            </div>
          )}
        </div>

        {/* ── B6: Invoice History ─────────────────────────────────────── */}
        <div className="mb-6">
          <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
            <DocumentArrowDownIcon className="h-5 w-5 text-[#FF7F11]" />
            Invoice History
          </h3>
          {invoicesLoading ? (
            <Skeleton className="h-64" />
          ) : invoicesError ? (
            <SectionError message="Unable to load invoices" onRetry={() => loadInvoices(1)} />
          ) : invoices.length === 0 ? (
            <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-8 text-center">
              <DocumentArrowDownIcon className="h-10 w-10 text-zinc-600 mx-auto mb-3" />
              <p className="text-sm text-zinc-500">No invoices yet</p>
            </div>
          ) : (
            <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      <th className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">Date</th>
                      <th className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">Amount</th>
                      <th className="px-5 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wider">Status</th>
                      <th className="px-5 py-3 text-right text-xs font-medium text-zinc-500 uppercase tracking-wider">Invoice</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.04]">
                    {invoices.map(inv => (
                      <tr key={inv.id} className="hover:bg-white/[0.02] transition-colors">
                        <td className="px-5 py-3.5 text-zinc-300 whitespace-nowrap">{formatDate(inv.invoice_date)}</td>
                        <td className="px-5 py-3.5 text-zinc-300 whitespace-nowrap">{formatCurrency(inv.amount)} {inv.currency}</td>
                        <td className="px-5 py-3.5">
                          <span className={cn('inline-flex rounded-full px-2 py-0.5 text-xs font-medium', invoiceStatusBadge(inv.status))}>
                            {inv.status.charAt(0).toUpperCase() + inv.status.slice(1)}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <button
                            onClick={() => handleDownloadPdf(inv.id)}
                            className="inline-flex items-center gap-1 text-xs text-[#FF7F11] hover:text-[#FF7F11]/80 transition-colors"
                          >
                            <DocumentArrowDownIcon className="h-3.5 w-3.5" />
                            PDF
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Pagination */}
              {invoicePagination.total_pages > 1 && (
                <div className="flex items-center justify-between border-t border-white/[0.06] px-5 py-3">
                  <p className="text-xs text-zinc-500">
                    Page {invoicePagination.page} of {invoicePagination.total_pages}
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      disabled={invoicePagination.page <= 1}
                      onClick={() => loadInvoices(invoicePagination.page - 1)}
                      className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1 text-xs text-zinc-400 hover:bg-white/[0.06] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      Previous
                    </button>
                    <button
                      disabled={invoicePagination.page >= invoicePagination.total_pages}
                      onClick={() => loadInvoices(invoicePagination.page + 1)}
                      className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1 text-xs text-zinc-400 hover:bg-white/[0.06] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── B7: Payment Method ──────────────────────────────────────── */}
        <div className="mb-8">
          <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
            <CreditCardIcon className="h-5 w-5 text-[#FF7F11]" />
            Payment Method
          </h3>
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/[0.06]">
                  <CreditCardIcon className="h-5 w-5 text-zinc-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-zinc-300">Payment on File</p>
                  <p className="text-xs text-zinc-500 mt-0.5">Managed via Paddle Billing</p>
                </div>
              </div>
              <button
                onClick={handleUpdatePayment}
                className="inline-flex items-center gap-1.5 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2 text-sm font-medium text-zinc-300 hover:bg-white/[0.08] transition-colors"
              >
                <CreditCardIcon className="h-3.5 w-3.5" />
                Update Payment
              </button>
            </div>
          </div>
        </div>

        {/* ── B5: Cancel Subscription ─────────────────────────────────── */}
        {hasSubscription && !isCanceled && (
          <div className="border-t border-white/[0.06] pt-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <h3 className="text-base font-semibold text-red-400">Cancel Subscription</h3>
                <p className="text-sm text-zinc-500 mt-1">
                  Your access continues until the end of your current billing period.
                </p>
              </div>
              <button
                onClick={() => {
                  setCancelModalOpen(true);
                  setCancelStep(1);
                  setCancelReason('');
                  setCancelFeedback('');
                  setCancelConfirmCheck(false);
                  setSaveOfferData(null);
                }}
                className="shrink-0 inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-2.5 text-sm font-semibold text-red-400 hover:bg-red-500/20 transition-colors"
              >
                Cancel Subscription
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          MODALS
          ══════════════════════════════════════════════════════════════════ */}

      {/* ── Upgrade / Downgrade Modal (B3/B4) ─────────────────────────── */}
      {upgradeModalOpen && (
        <Modal onClose={() => { setUpgradeModalOpen(false); setProrationPreview(null); setSelectedVariant(null); }} title={selectedVariant ? (isUpgrade ? 'Upgrade Plan' : isDowngrade ? 'Downgrade Plan' : 'Change Plan') : 'Choose a Plan'}>
          {!selectedVariant ? (
            /* Plan Comparison Table */
            <div className="space-y-4">
              <p className="text-sm text-zinc-400 mb-4">Select a plan to upgrade or downgrade:</p>
              <div className="space-y-3">
                {(['starter', 'growth', 'high'] as VariantType[]).map(v => {
                  const plan = PLAN_DATA[v];
                  const isCurrent = v === currentVariant;
                  const isUp = tierOrder[v] > tierOrder[currentVariant];
                  const isDown = tierOrder[v] < tierOrder[currentVariant];
                  return (
                    <button
                      key={v}
                      disabled={isCurrent}
                      onClick={() => {
                        setSelectedVariant(v);
                        if (isUp) handlePreviewUpgrade(v);
                      }}
                      className={cn(
                        'w-full rounded-xl border p-4 text-left transition-all',
                        isCurrent
                          ? 'border-[#FF7F11]/30 bg-[#FF7F11]/5 cursor-default'
                          : 'border-white/[0.06] bg-[#1A1A1A] hover:border-[#FF7F11]/30 hover:bg-white/[0.03]',
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#FF7F11]/10">
                            <BoltIcon className="h-4.5 w-4.5 text-[#FF7F11]" />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-semibold text-white">{plan.name}</span>
                              <span className={cn('inline-flex rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase', plan.badgeColor)}>
                                {plan.badge}
                              </span>
                            </div>
                            <div className="flex items-center gap-4 mt-1 text-xs text-zinc-500">
                              <span>{plan.monthlyPrice}/mo</span>
                              <span>{plan.tickets.toLocaleString()} tickets</span>
                              <span>{plan.aiAgents} agents</span>
                              <span>{plan.teamMembers} team</span>
                              <span>{plan.kbDocs} KB docs</span>
                            </div>
                          </div>
                        </div>
                        <div>
                          {isCurrent && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-[#FF7F11]/15 px-3 py-1 text-xs font-medium text-[#FF7F11]">
                              <CheckIcon className="h-3 w-3" />
                              Current
                            </span>
                          )}
                          {isUp && (
                            <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
                              <ArrowUpIcon className="h-3 w-3" />
                              Upgrade
                            </span>
                          )}
                          {isDown && (
                            <span className="inline-flex items-center gap-1 text-xs text-yellow-400">
                              <ArrowDownIcon className="h-3 w-3" />
                              Downgrade
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : selectedVariant && isUpgrade ? (
            /* B3: Upgrade Confirmation with Proration */
            <div className="space-y-5">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-zinc-400">{currentPlanData?.name}</span>
                <ArrowUpIcon className="h-4 w-4 text-emerald-400" />
                <span className="font-semibold text-white">{PLAN_DATA[selectedVariant].name}</span>
              </div>

              {prorationLoading ? (
                <div className="flex items-center justify-center py-8">
                  <SpinnerIcon className="h-6 w-6 animate-spin text-[#FF7F11]" />
                </div>
              ) : prorationPreview ? (
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 space-y-3">
                  <h4 className="text-sm font-semibold text-white">Proration Preview</h4>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="text-zinc-500">Current plan price</div>
                    <div className="text-zinc-300 text-right">{formatCurrency(prorationPreview.estimated_cost.unused_credit + prorationPreview.estimated_cost.new_charge)}</div>
                    <div className="text-zinc-500">Unused credit</div>
                    <div className="text-emerald-400 text-right">-{formatCurrency(prorationPreview.estimated_cost.unused_credit)}</div>
                    <div className="text-zinc-500">New plan charge</div>
                    <div className="text-zinc-300 text-right">{formatCurrency(prorationPreview.estimated_cost.new_charge)}</div>
                    <div className="text-zinc-500">Days remaining</div>
                    <div className="text-zinc-300 text-right">{prorationPreview.estimated_cost.days_remaining} days</div>
                    <div className="text-zinc-500 pt-2 border-t border-white/[0.06] font-medium">Net charge</div>
                    <div className="text-white font-semibold text-right pt-2 border-t border-white/[0.06]">
                      {formatCurrency(prorationPreview.estimated_cost.net_cost)}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-zinc-500">No proration preview available.</p>
              )}

              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={() => { setSelectedVariant(null); setProrationPreview(null); }}
                  className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-zinc-300 hover:bg-white/[0.08] transition-colors"
                >
                  Back
                </button>
                <button
                  onClick={handleConfirmUpgrade}
                  disabled={confirmLoading}
                  className="flex-1 inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50 transition-colors"
                >
                  {confirmLoading ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <CheckIcon className="h-4 w-4" />}
                  Confirm Upgrade
                </button>
              </div>
            </div>
          ) : selectedVariant && isDowngrade ? (
            /* B4: Downgrade Warning */
            <div className="space-y-5">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-zinc-400">{currentPlanData?.name}</span>
                <ArrowDownIcon className="h-4 w-4 text-yellow-400" />
                <span className="font-semibold text-white">{PLAN_DATA[selectedVariant].name}</span>
              </div>

              <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-4">
                <div className="flex items-start gap-3">
                  <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-sm font-semibold text-yellow-300">Downgrade Warning</p>
                    <p className="text-sm text-zinc-400 mt-1">
                      Downgrading will take effect at the start of your next billing period. You will lose access to features included in your current plan that are not available in the {PLAN_DATA[selectedVariant].name} plan.
                    </p>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <h4 className="text-sm font-semibold text-white mb-3">What you&apos;ll keep vs. lose</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-xs text-zinc-500 mb-2 uppercase tracking-wider">Limit Reduction</p>
                    <div className="space-y-1.5">
                      <LimitChange label="Tickets" from={currentPlanData?.tickets || 0} to={PLAN_DATA[selectedVariant].tickets} />
                      <LimitChange label="AI Agents" from={currentPlanData?.aiAgents || 0} to={PLAN_DATA[selectedVariant].aiAgents} />
                      <LimitChange label="Team Members" from={currentPlanData?.teamMembers || 0} to={PLAN_DATA[selectedVariant].teamMembers} />
                      <LimitChange label="KB Docs" from={currentPlanData?.kbDocs || 0} to={PLAN_DATA[selectedVariant].kbDocs} />
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-zinc-500 mb-2 uppercase tracking-wider">New Price</p>
                    <p className="text-lg font-bold text-white">{PLAN_DATA[selectedVariant].monthlyPrice}<span className="text-sm text-zinc-500 font-normal">/mo</span></p>
                    <p className="text-xs text-zinc-500 mt-1">Effective next billing cycle</p>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={() => { setSelectedVariant(null); setProrationPreview(null); }}
                  className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-zinc-300 hover:bg-white/[0.08] transition-colors"
                >
                  Back
                </button>
                <button
                  onClick={handleConfirmDowngrade}
                  disabled={confirmLoading}
                  className="flex-1 inline-flex items-center justify-center gap-2 rounded-xl bg-yellow-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-yellow-500 disabled:opacity-50 transition-colors"
                >
                  {confirmLoading ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <ArrowDownIcon className="h-4 w-4" />}
                  Confirm Downgrade
                </button>
              </div>
            </div>
          ) : null}
        </Modal>
      )}

      {/* ── Cancel Subscription Modal (B5) ─────────────────────────────── */}
      {cancelModalOpen && (
        <Modal
          onClose={() => { setCancelModalOpen(false); setCancelStep(1); }}
          title={cancelStep === 1 ? 'Cancel Subscription' : cancelStep === 2 ? 'Wait — We Have a Deal for You' : 'Final Confirmation'}
        >
          {/* Step 1: Feedback */}
          {cancelStep === 1 && (
            <div className="space-y-5">
              <p className="text-sm text-zinc-400">
                We&apos;re sorry to see you go. Please share your reason to help us improve.
              </p>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">Reason</label>
                <select
                  value={cancelReason}
                  onChange={e => setCancelReason(e.target.value)}
                  className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2.5 text-sm text-zinc-300 focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30"
                >
                  <option value="">Select a reason...</option>
                  <option value="too_expensive">Too expensive</option>
                  <option value="missing_features">Missing features I need</option>
                  <option value="switching">Switching to another service</option>
                  <option value="business_closed">Business closed</option>
                  <option value="poor_support">Poor customer support</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">Additional Feedback</label>
                <textarea
                  value={cancelFeedback}
                  onChange={e => setCancelFeedback(e.target.value)}
                  placeholder="Tell us more about your experience..."
                  rows={4}
                  className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2.5 text-sm text-zinc-300 placeholder-zinc-600 focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 resize-none"
                />
              </div>
              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={() => setCancelModalOpen(false)}
                  className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-zinc-300 hover:bg-white/[0.08] transition-colors"
                >
                  Keep Subscription
                </button>
                <button
                  onClick={handleCancelStep1}
                  className="flex-1 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-semibold text-red-400 hover:bg-red-500/20 transition-colors"
                >
                  Continue
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Save Offer */}
          {cancelStep === 2 && (
            <div className="space-y-5">
              <div className="rounded-xl border border-[#FF7F11]/30 bg-[#FF7F11]/5 p-5 text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[#FF7F11]/10 mb-3">
                  <span className="text-2xl font-bold text-[#FF7F11]">20%</span>
                </div>
                <h4 className="text-lg font-bold text-white mb-1">Stay for 20% Off</h4>
                <p className="text-sm text-zinc-400">
                  We&apos;ll give you 20% off your next 3 billing cycles. That&apos;s a significant saving!
                </p>
              </div>
              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={() => setCancelStep(3)}
                  className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-zinc-300 hover:bg-white/[0.08] transition-colors"
                >
                  No Thanks, Cancel Anyway
                </button>
                <button
                  onClick={handleCancelStep2}
                  className="flex-1 inline-flex items-center justify-center gap-2 rounded-xl bg-[#FF7F11] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
                >
                  <CheckIcon className="h-4 w-4" />
                  Claim 20% Off
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Final Confirmation */}
          {cancelStep === 3 && (
            <div className="space-y-5">
              <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4">
                <div className="flex items-start gap-3">
                  <ExclamationTriangleIcon className="h-5 w-5 text-red-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-sm font-semibold text-red-300">This Action Cannot Be Undone</p>
                    <p className="text-sm text-zinc-400 mt-1">
                      Your subscription will be canceled and access will continue until the end of your current billing period. After that, all data will be retained for 30 days and then permanently deleted.
                    </p>
                  </div>
                </div>
              </div>

              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={cancelConfirmCheck}
                  onChange={e => setCancelConfirmCheck(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-zinc-600 bg-white/[0.04] text-[#FF7F11] focus:ring-[#FF7F11]/30 accent-[#FF7F11]"
                />
                <span className="text-sm text-zinc-400">
                  I understand that my data will be retained for 30 days after service stops, then permanently deleted.
                </span>
              </label>

              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={() => setCancelStep(2)}
                  className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-zinc-300 hover:bg-white/[0.08] transition-colors"
                >
                  Go Back
                </button>
                <button
                  onClick={handleCancelStep3}
                  disabled={confirmLoading || !cancelConfirmCheck}
                  className="flex-1 inline-flex items-center justify-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-50 transition-colors"
                >
                  {confirmLoading ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : null}
                  Confirm Cancellation
                </button>
              </div>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// Sub-Components
// ════════════════════════════════════════════════════════════════════════════

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg rounded-2xl border border-white/[0.08] bg-[#1A1A1A] shadow-2xl">
        <div className="flex items-center justify-between border-b border-white/[0.06] px-6 py-4">
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-zinc-500 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
        <div className="px-6 py-5 max-h-[70vh] overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

function UsageMeter({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = limit > 0 ? Math.min(used / limit, 1) : 0;
  const pctDisplay = Math.round(pct * 100);
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm text-zinc-400">{label}</span>
        <span className={cn('text-sm font-medium', usageTextColor(pct))}>
          {used.toLocaleString()} / {limit.toLocaleString()}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-500', usageColor(pct))}
          style={{ width: `${pctDisplay}%` }}
        />
      </div>
      <p className="text-xs text-zinc-600 mt-1">{pctDisplay}% used</p>
    </div>
  );
}

function LimitChange({ label, from, to }: { label: string; from: number; to: number }) {
  const reduced = to < from;
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-zinc-500">{label}</span>
      <span className={reduced ? 'text-yellow-400' : 'text-zinc-400'}>
        {from.toLocaleString()} → {to.toLocaleString()}
      </span>
    </div>
  );
}

function VariantCard({
  item,
  loading,
  onAdd,
  onRemove,
  billingFrequency,
}: {
  item: VariantCatalogItem;
  loading: boolean;
  onAdd: () => void;
  onRemove: () => void;
  billingFrequency?: 'monthly' | 'yearly';
}) {
  const price = billingFrequency === 'yearly' ? item.price_yearly : item.price_monthly;
  return (
    <div className={cn(
      'rounded-xl border p-5 transition-all',
      item.is_active
        ? 'border-emerald-500/30 bg-emerald-500/[0.03]'
        : 'border-white/[0.06] bg-[#1A1A1A]',
    )}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-white">{item.display_name}</h4>
            {item.is_active && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
                <CheckIcon className="h-2.5 w-2.5" />
                Active
              </span>
            )}
          </div>
          <p className="text-xs text-zinc-500 mt-1">{item.description}</p>
        </div>
      </div>
      <div className="flex items-center gap-4 text-xs text-zinc-400 mb-4">
        <span>+{item.tickets_added} tickets</span>
        <span>+{item.kb_docs_added} KB docs</span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-white">
          {formatCurrency(price)}
          <span className="text-xs text-zinc-500 font-normal">/{billingFrequency === 'yearly' ? 'year' : 'mo'}</span>
        </span>
        {item.is_active ? (
          <button
            disabled={loading}
            onClick={onRemove}
            className="inline-flex items-center gap-1 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-500/20 disabled:opacity-50 transition-colors"
          >
            {loading ? <SpinnerIcon className="h-3 w-3 animate-spin" /> : <MinusIcon className="h-3 w-3" />}
            Remove
          </button>
        ) : (
          <button
            disabled={loading}
            onClick={onAdd}
            className="inline-flex items-center gap-1 rounded-lg bg-[#FF7F11] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#FF7F11]/90 disabled:opacity-50 transition-colors"
          >
            {loading ? <SpinnerIcon className="h-3 w-3 animate-spin" /> : <PlusIcon className="h-3 w-3" />}
            Add
          </button>
        )}
      </div>
    </div>
  );
}
