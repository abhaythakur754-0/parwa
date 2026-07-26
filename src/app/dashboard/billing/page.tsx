'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Loader2, Check, Plus, Trash2, CreditCard, Calendar, TrendingUp, Zap, X, Info, AlertCircle, Shield, MessageSquare, Phone, Clock, Sparkles, Ticket, Users, BarChart3, Settings } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { RazorpayCheckout } from '@/components/razorpay/RazorpayCheckout';

interface Subscription {
  variant: string; status: string; razorpay_subscription_id: string | null;
  quantity: number; current_period_start: string | null; current_period_end: string | null;
  cancel_at_period_end: boolean;
}
interface PricingVariant { key: string; name: string; monthly_price: number; description: string; replaces: string; }
interface TicketsByVariant { tickets_by_variant: Record<string, number>; total_resolved: number; }
interface Invoice { id: string; amount: number; currency: string; status: string; invoice_date: string | null; paid_at: string | null; }

const VARIANT_META: Record<string, { name: string; color: string; bg: string; border: string; dot: string }> = {
  parwa: { name: 'PARWA', color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20', dot: 'bg-purple-400' },
  high: { name: 'PARWA High', color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20', dot: 'bg-amber-400' },
};

function formatCurrency(n: number): string { return `$${n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`; }
function formatDate(iso: string | null): string { if (!iso) return '—'; return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }

// ── FlexPay Feature Timeline ──
const FLEXPAY_FEATURES = {
  immediate: [
    { icon: Ticket, label: 'Ticket Management', desc: 'Create, assign & resolve tickets' },
    { icon: Users, label: 'Team Collaboration', desc: 'Full team access & roles' },
    { icon: BarChart3, label: 'Analytics Dashboard', desc: 'Reports & insights' },
    { icon: Settings, label: 'Custom Workflows', desc: 'Automate your processes' },
  ],
  day11: [
    { icon: MessageSquare, label: 'SMS Notifications', desc: 'Text alerts to customers' },
    { icon: Phone, label: 'Calling Features', desc: 'Voice calls & IVR' },
  ],
};
function formatRelativeDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso); const now = new Date(); const diffMs = d.getTime() - now.getTime();
  const days = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  if (days < 0) return `${Math.abs(days)}d ago`;
  if (days === 0) return 'today'; if (days === 1) return 'tomorrow';
  if (days < 30) return `in ${days}d`;
  return formatDate(iso);
}

interface UserData { id?: string; email?: string; name?: string; company_id?: string; }

export default function BillingPage() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [pricing, setPricing] = useState<PricingVariant[]>([]);
  const [ticketsByVariant, setTicketsByVariant] = useState<TicketsByVariant>({ tickets_by_variant: {}, total_resolved: 0 });
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [subscribing, setSubscribing] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [updatingQty, setUpdatingQty] = useState<string | null>(null);
  const [user, setUser] = useState<UserData>({});
  const [flexPayPlans, setFlexPayPlans] = useState<Record<string, string>>({}); // variant -> planId
  const [showFlexPayConfirm, setShowFlexPayConfirm] = useState<{variant: PricingVariant; planId: string} | null>(null); // Pre-checkout confirmation modal

  const fetchAll = useCallback(async () => {
    try {
      setLoading(true); setError(null);
      const [subsRes, pricingRes, ticketsRes, invoicesRes, userRes] = await Promise.all([
        fetch('/api/billing/razorpay/subscriptions', { credentials: 'include' }).catch(() => null),
        fetch('/api/billing/razorpay/pricing', { credentials: 'include' }).catch(() => null),
        fetch('/api/billing/razorpay/tickets-by-variant', { credentials: 'include' }).catch(() => null),
        fetch('/api/billing/invoices', { credentials: 'include' }).catch(() => null),
        fetch('/api/auth/me-proxy', { credentials: 'include' }).catch(() => null),
      ]);
      if (subsRes?.ok) { const d = await subsRes.json(); setSubscriptions(Array.isArray(d) ? d : []); }
      if (pricingRes?.ok) { const d = await pricingRes.json(); setPricing(d.variants || []); }
      if (ticketsRes?.ok) setTicketsByVariant(await ticketsRes.json());
      if (invoicesRes?.ok) { const d = await invoicesRes.json(); setInvoices(d.items || d.invoices || []); }
      if (userRes?.ok) { const u = await userRes.json(); setUser({ id: u.id, email: u.email, name: u.name || u.full_name, company_id: u.company_id }); }
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed to load billing data'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleSubscribe = async (variantKey: string, quantity: number = 1) => {
    setSubscribing(variantKey);
    try {
      const res = await fetch('/api/billing/razorpay/subscribe', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ variant: variantKey, quantity }) });
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `Failed (${res.status})`); }
      const data = await res.json();
      if (data.short_url) { toast.success('Redirecting to Razorpay checkout...'); window.open(data.short_url, '_blank'); }
      else { toast.success('Subscription created! Activating...'); }
      setTimeout(() => fetchAll(), 3000);
    } catch (err) { toast.error(err instanceof Error ? err.message : 'Failed to subscribe'); }
    finally { setSubscribing(null); }
  };

  const handleCancel = async (variantKey: string) => {
    if (!confirm(`Cancel ${VARIANT_META[variantKey]?.name || variantKey} subscription?\n\nYou'll keep access until the end of the current billing cycle.`)) return;
    setCancelling(variantKey);
    try {
      const res = await fetch('/api/billing/razorpay/cancel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ variant: variantKey, cancel_at_cycle_end: true }) });
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `Failed (${res.status})`); }
      toast.success('Subscription cancelled. Access continues until end of billing cycle.');
      fetchAll();
    } catch (err) { toast.error(err instanceof Error ? err.message : 'Failed to cancel'); }
    finally { setCancelling(null); }
  };

  const handleUpdateQuantity = async (variantKey: string, newQty: number) => {
    setUpdatingQty(variantKey);
    try {
      const res = await fetch('/api/billing/razorpay/update-quantity', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ variant: variantKey, quantity: newQty }) });
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `Failed (${res.status})`); }
      toast.success(`Quantity updated to ${newQty}`);
      fetchAll();
    } catch (err) { toast.error(err instanceof Error ? err.message : 'Failed to update quantity'); }
    finally { setUpdatingQty(null); }
  };

  // ── FLEXPAY: Create plan before tokenization ──
  const createFlexPayPlan = async (variantKey: string, monthlyPrice: number): Promise<string | null> => {
    // Return existing plan if already created for this variant
    if (flexPayPlans[variantKey]) return flexPayPlans[variantKey];
    
    try {
      const companyId = user.company_id || user.id;
      if (!companyId) throw new Error('User not authenticated');
      
      const res = await fetch('/api/flexpay/create-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          companyId,
          tier: variantKey as 'parwa' | 'high',
          totalAmount: monthlyPrice,
          customerEmail: user.email,
          customerName: user.name,
        }),
      });
      
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `Failed to create plan (${res.status})`);
      }
      
      const data = await res.json();
      const planId = data.plan?.id;
      
      if (planId) {
        setFlexPayPlans(prev => ({ ...prev, [variantKey]: planId }));
        setSubscribing(null); // ✅ Reset loading state so checkout button shows
        console.log('[FlexPay] Plan created:', planId, 'for variant:', variantKey);
        return planId;
      }
      
      throw new Error('No plan ID in response');
    } catch (err) {
      console.error('[FlexPay] Failed to create plan:', err);
      toast.error(err instanceof Error ? err.message : 'Failed to create payment plan');
      return null;
    }
  };

  const activeSubs = subscriptions.filter(s => s.status === 'active' || s.status === 'created' || s.status === 'authenticated');
  const totalMonthlyCost = activeSubs.reduce((sum, sub) => { const price = pricing.find(p => p.key === sub.variant)?.monthly_price || 0; return sum + (price * sub.quantity); }, 0);
  const nextRenewalDate = activeSubs.map(s => s.current_period_end).filter(Boolean).sort()[0] || null;
  const totalVariants = activeSubs.reduce((sum, s) => sum + s.quantity, 0);

  if (loading) {
    return (<div className="space-y-6"><div><h1 className="text-2xl font-bold text-white">Billing</h1><p className="text-sm text-zinc-500 mt-1">Manage your subscription and payment</p></div><div className="flex items-center justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-orange-400" /></div></div>);
  }
  if (error) {
    return (<div className="space-y-6"><div><h1 className="text-2xl font-bold text-white">Billing</h1><p className="text-sm text-zinc-500 mt-1">Manage your subscription and payment</p></div><div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-8 text-center"><p className="text-sm text-amber-400 mb-2">Unable to load billing data</p><p className="text-xs text-zinc-500 mb-4">{error}</p><button onClick={fetchAll} className="text-xs font-medium px-4 py-2 rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/20 hover:bg-orange-500/20 transition-colors">Retry</button></div></div>);
  }

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
        <h1 className="text-2xl font-bold text-white">Billing</h1>
        <p className="text-sm text-zinc-500 mt-1">Manage your subscription and payment</p>
      </motion.div>

      {/* Section 1: Subscription Summary */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.05 }} className="rounded-xl bg-gradient-to-br from-orange-500/10 to-amber-500/5 border border-orange-500/20 p-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div><div className="flex items-center gap-2 mb-1"><CreditCard className="w-4 h-4 text-orange-400" /><span className="text-[10px] text-zinc-600 uppercase tracking-wider">Monthly Cost</span></div><p className="text-2xl font-bold text-white tabular-nums">{formatCurrency(totalMonthlyCost)}</p><p className="text-[10px] text-zinc-600">per month</p></div>
          <div><div className="flex items-center gap-2 mb-1"><Calendar className="w-4 h-4 text-orange-400" /><span className="text-[10px] text-zinc-600 uppercase tracking-wider">Next Renewal</span></div><p className="text-2xl font-bold text-white">{formatRelativeDate(nextRenewalDate)}</p><p className="text-[10px] text-zinc-600">{formatDate(nextRenewalDate)}</p></div>
          <div><div className="flex items-center gap-2 mb-1"><TrendingUp className="w-4 h-4 text-orange-400" /><span className="text-[10px] text-zinc-600 uppercase tracking-wider">Active Variants</span></div><p className="text-2xl font-bold text-white tabular-nums">{totalVariants}</p><p className="text-[10px] text-zinc-600">{activeSubs.length} subscription{activeSubs.length === 1 ? '' : 's'}</p></div>
          <div><div className="flex items-center gap-2 mb-1"><Check className="w-4 h-4 text-orange-400" /><span className="text-[10px] text-zinc-600 uppercase tracking-wider">Tickets Solved</span></div><p className="text-2xl font-bold text-white tabular-nums">{ticketsByVariant.total_resolved}</p><p className="text-[10px] text-zinc-600">by AI variants</p></div>
        </div>
      </motion.div>

      {/* Section 2: Your Variants */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.1 }} className="space-y-4">
        <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider">Your Variants</h2>
        {activeSubs.length === 0 ? (
          <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-8 text-center"><p className="text-sm text-zinc-400 mb-1">No active subscriptions</p><p className="text-xs text-zinc-600">Subscribe to a variant below to get started.</p></div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {activeSubs.map((sub) => {
              const meta = VARIANT_META[sub.variant] || { name: sub.variant, color: 'text-zinc-400', bg: 'bg-zinc-500/10', border: 'border-zinc-500/20', dot: 'bg-zinc-400' };
              const price = pricing.find(p => p.key === sub.variant)?.monthly_price || 0;
              const ticketsSolved = ticketsByVariant.tickets_by_variant[sub.variant] || 0;
              return (
                <div key={sub.variant} className={cn('rounded-xl border p-5', meta.border, 'bg-[#1A1A1A]')}>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2"><span className={cn('w-2 h-2 rounded-full', meta.dot)} /><span className={cn('text-sm font-semibold', meta.color)}>{meta.name}</span></div>
                    <span className={cn('text-[10px] px-2 py-0.5 rounded-full border', sub.status === 'active' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : sub.status === 'cancelled' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20')}>{sub.cancel_at_period_end ? 'cancelling' : sub.status}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div><p className="text-[10px] text-zinc-600 uppercase tracking-wider">Quantity</p><p className="text-xl font-bold text-white tabular-nums">{sub.quantity}</p></div>
                    <div><p className="text-[10px] text-zinc-600 uppercase tracking-wider">Tickets Solved</p><p className="text-xl font-bold text-white tabular-nums">{ticketsSolved}</p></div>
                    <div><p className="text-[10px] text-zinc-600 uppercase tracking-wider">Price/unit</p><p className="text-sm font-medium text-zinc-300 tabular-nums">{formatCurrency(price)}/mo</p></div>
                    <div><p className="text-[10px] text-zinc-600 uppercase tracking-wider">Subtotal</p><p className="text-sm font-medium text-zinc-300 tabular-nums">{formatCurrency(price * sub.quantity)}/mo</p></div>
                  </div>
                  <div className="text-[10px] text-zinc-600 mb-4 flex items-center gap-1.5"><Calendar className="w-3 h-3" /> Renews {formatRelativeDate(sub.current_period_end)}</div>
                  <div className="flex items-center gap-2 pt-3 border-t border-white/[0.04]">
                    <button onClick={() => handleUpdateQuantity(sub.variant, sub.quantity + 1)} disabled={updatingQty === sub.variant} className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/[0.04] text-zinc-300 hover:bg-white/[0.08] transition-colors disabled:opacity-50">{updatingQty === sub.variant ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />} Add Seat</button>
                    {sub.quantity > 1 && <button onClick={() => handleUpdateQuantity(sub.variant, sub.quantity - 1)} disabled={updatingQty === sub.variant} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white/[0.04] text-zinc-400 hover:bg-white/[0.08] transition-colors disabled:opacity-50" title="Remove a seat">−</button>}
                    <button onClick={() => handleCancel(sub.variant)} disabled={cancelling === sub.variant || sub.cancel_at_period_end} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50" title={sub.cancel_at_period_end ? 'Already cancelling' : 'Cancel subscription'}>{cancelling === sub.variant ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}</button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </motion.div>

      {/* ── FlexPay Info Banner ── */}
      <motion.div 
        initial={{ opacity: 0, y: 8 }} 
        animate={{ opacity: 1, y: 0 }} 
        transition={{ duration: 0.35, delay: 0.12 }} 
        className="rounded-xl bg-gradient-to-r from-blue-500/10 via-indigo-500/10 to-purple-500/10 border border-blue-500/20 p-5"
      >
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-blue-400" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-white mb-2">FlexPay Payment Plan</h3>
            <p className="text-xs text-zinc-400 mb-3 leading-relaxed">
              Due to <strong className="text-blue-300">banking transaction limits</strong>, we can only process <strong className="text-emerald-400">$100 USD per day</strong>. 
              Your subscription will be split into daily automatic charges. Here's what you get:
            </p>
            
            {/* Feature Timeline */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
              {/* Day 1 Features */}
              <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Zap className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-semibold text-emerald-400">✓ Available from Day 1</span>
                </div>
                <div className="space-y-1.5">
                  {FLEXPAY_FEATURES.immediate.map((feat) => (
                    <div key={feat.label} className="flex items-center gap-2">
                      <feat.icon className="w-3.5 h-3.5 text-zinc-500" />
                      <span className="text-xs text-zinc-300">{feat.label}</span>
                    </div>
                  ))}
                </div>
              </div>
              
              {/* Day 11 Features */}
              <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Clock className="w-4 h-4 text-amber-400" />
                  <span className="text-xs font-semibold text-amber-400">Unlocks on Day 11</span>
                </div>
                <div className="space-y-1.5">
                  {FLEXPAY_FEATURES.day11.map((feat) => (
                    <div key={feat.label} className="flex items-center gap-2">
                      <feat.icon className="w-3.5 h-3.5 text-zinc-500" />
                      <span className="text-xs text-zinc-300">{feat.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* ⚡ PARWA HIGH Special Schedule - Only for $3,999 tier ⚡ */}
            <div className="mt-3 rounded-lg bg-gradient-to-r from-amber-500/15 via-orange-500/10 to-red-500/15 border border-amber-500/30 p-3.5">
              <div className="flex items-center gap-2 mb-2.5">
                <div className="w-6 h-6 rounded-md bg-amber-500/20 flex items-center justify-center">
                  <TrendingUp className="w-3.5 h-3.5 text-amber-400" />
                </div>
                <span className="text-xs font-bold text-amber-300">⚡ PARWA HIGH ($3,999) - Accelerated Plan</span>
              </div>
              <div className="space-y-2 text-[11px]">
                <p className="text-zinc-300 leading-relaxed">
                  <strong className="text-amber-300">Special schedule:</strong> Every <strong className="text-white">3rd day</strong>, we charge <strong className="text-emerald-400">$200</strong> instead of $100:
                </p>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <div className="rounded bg-black/20 p-2">
                    <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Normal Days</div>
                    <div className="text-zinc-300 font-medium">$100/day at midnight</div>
                  </div>
                  <div className="rounded bg-amber-500/10 border border-amber-500/20 p-2">
                    <div className="text-[10px] text-amber-400/80 uppercase tracking-wider mb-1">Every 3rd Day 💰</div>
                    <div className="text-amber-200 font-medium">$100 @ 12:00 AM<br/>+ $100 @ 01:00 AM</div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 mt-2 pt-2 border-t border-amber-500/20">
                  <CreditCard className="w-3 h-3 text-amber-400" />
                  <span className="text-zinc-400"><strong className="text-amber-300">Result:</strong> Full $3,999 collected in <strong className="text-white">~30 days</strong> instead of 40!</span>
                </div>
              </div>
            </div>
            
            {/* Future Renewals Note */}
            <div className="flex items-start gap-2 rounded-lg bg-purple-500/10 border border-purple-500/20 p-2.5 mt-3">
              <Shield className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
              <p className="text-[11px] text-zinc-400 leading-relaxed">
                <strong className="text-purple-300">Good news:</strong> After your first month, all future renewals will have <strong className="text-white">instant full access from Day 1</strong> — no waiting period!
              </p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Section 3: Pricing Plans */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.15 }} className="space-y-4">
        <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider">Choose Your Plan</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {pricing.map((variant) => {
            const meta = VARIANT_META[variant.key] || { name: variant.name, color: 'text-zinc-400', bg: 'bg-zinc-500/10', border: 'border-zinc-500/20', dot: 'bg-zinc-400' };
            const alreadySubscribed = activeSubs.some(s => s.variant === variant.key);
            return (
              <div key={variant.key} className={cn('rounded-xl border p-5 flex flex-col', alreadySubscribed ? 'border-white/[0.04] bg-white/[0.01] opacity-60' : cn(meta.border, 'bg-[#1A1A1A]'))}>
                <div className="flex items-center gap-2 mb-2"><span className={cn('w-2 h-2 rounded-full', meta.dot)} /><span className={cn('text-sm font-semibold', meta.color)}>{variant.name}</span>{alreadySubscribed && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 ml-auto">Active</span>}</div>
                <p className="text-xs text-zinc-500 mb-3 flex-1">{variant.description}</p>
                <p className="text-[10px] text-zinc-600 mb-3">Replaces: <span className="text-zinc-400">{variant.replaces}</span></p>
                <div className="mb-4"><span className="text-2xl font-bold text-white tabular-nums">{formatCurrency(variant.monthly_price)}</span><span className="text-xs text-zinc-600">/mo</span></div>
                {alreadySubscribed ? (
                  <button disabled className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-medium bg-white/[0.04] text-zinc-600 cursor-default">
                    <Check className="w-3.5 h-3.5" /> Subscribed
                  </button>
                ) : (
                  subscribing === variant.key ? (
                    // Show loading while creating plan
                    <button disabled className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-medium bg-gradient-to-r from-emerald-500 to-teal-400 text-white cursor-wait">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Setting up FlexPay...
                    </button>
                  ) : flexPayPlans[variant.key] ? (
                    // Plan created - show confirmation modal before checkout
                    <button
                      onClick={() => setShowFlexPayConfirm({ variant, planId: flexPayPlans[variant.key] })}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-bold bg-gradient-to-r from-emerald-500 to-teal-400 text-white shadow-emerald-500/20 hover:shadow-emerald-500/30 hover:-translate-y-0.5 transition-all"
                    >
                      <Zap className="w-3.5 h-3.5" />
                      Activate · ${variant.monthly_price.toLocaleString()}/mo
                    </button>
                  ) : (
                    // Initial subscribe button - creates plan first
                    <button
                      onClick={() => {
                        setSubscribing(variant.key);
                        createFlexPayPlan(variant.key, variant.monthly_price).then((planId) => {
                          if (!planId) setSubscribing(null);
                        });
                      }}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-bold bg-gradient-to-r from-emerald-500 to-teal-400 text-white shadow-emerald-500/20 hover:shadow-emerald-500/30 hover:-translate-y-0.5 transition-all"
                    >
                      <Zap className="w-3.5 h-3.5" />
                      Subscribe · ${variant.monthly_price.toLocaleString()}/mo
                    </button>
                  )
                )}
              </div>
            );
          })}
        </div>
      </motion.div>

      {/* Section 4: Invoice History */}
      {invoices.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.2 }} className="space-y-4">
          <h2 className="text-sm font-medium text-zinc-500 uppercase tracking-wider">Invoice History</h2>
          <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden">
            <table className="w-full text-left">
              <thead><tr className="border-b border-white/[0.06] text-[10px] text-zinc-600 uppercase tracking-wider"><th className="px-4 py-3">Date</th><th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3 text-center">Status</th></tr></thead>
              <tbody>
                {invoices.slice(0, 10).map((inv, i) => (
                  <tr key={inv.id || i} className="border-b border-white/[0.03] text-sm">
                    <td className="px-4 py-3 text-zinc-300">{formatDate(inv.invoice_date || inv.paid_at)}</td>
                    <td className="px-4 py-3 text-right text-zinc-300 tabular-nums">{formatCurrency(Number(inv.amount) || 0)} {inv.currency || 'USD'}</td>
                    <td className="px-4 py-3 text-center"><span className={cn('inline-flex px-2 py-0.5 rounded-full text-[10px] border', inv.status === 'paid' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : inv.status === 'failed' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20')}>{inv.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}

      {/* ── FLEXPAY CONFIRMATION MODAL ── */}
      {showFlexPayConfirm && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => setShowFlexPayConfirm(null)}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="bg-[#1A1A1A] border border-white/10 rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="bg-gradient-to-r from-emerald-500/20 to-teal-500/10 px-6 py-4 border-b border-white/5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                    <Zap className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">FlexPay Activation</h3>
                    <p className="text-xs text-zinc-400">{showFlexPayConfirm.variant.name} Plan</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowFlexPayConfirm(null)}
                  className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors"
                >
                  <X className="w-4 h-4 text-zinc-400" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="px-6 py-5 space-y-4">
              {/* Info Banner */}
              <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
                <div className="flex gap-3">
                  <Info className="w-5 h-5 text-blue-400 mt-0.5 shrink-0" />
                  <div className="text-sm text-blue-200">
                    <p className="font-medium mb-1">How FlexPay Works</p>
                    <p className="text-xs text-blue-300/80 leading-relaxed">
                      Instead of one large payment, your card will be charged in small daily installments. 
                      Each charge is under $100 for easier approval.
                    </p>
                  </div>
                </div>
              </div>

              {/* Price Breakdown */}
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">Payment Schedule (USD)</h4>
                
                <div className="bg-white/[0.03] rounded-xl divide-y divide-white/5">
                  {Array.from({ length: Math.ceil(showFlexPayConfirm.variant.monthly_price / 100) }, (_, i) => {
                    const dayNum = i + 1;
                    const amount = dayNum === Math.ceil(showFlexPayConfirm.variant.monthly_price / 100) 
                      ? showFlexPayConfirm.variant.monthly_price - ((dayNum - 1) * 100)
                      : 100;
                    const isToday = dayNum === 1;
                    return (
                      <div key={i} className={`flex items-center justify-between px-4 py-3 ${isToday ? 'bg-orange-500/10' : ''}`}>
                        <div className="flex items-center gap-3">
                          {isToday && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-orange-500/20 text-orange-400 font-medium">TODAY</span>
                          )}
                          <span className={`text-sm ${isToday ? 'text-white font-medium' : 'text-zinc-400'}`}>
                            Day {dayNum}{isToday ? ' • First Installment' : ''}
                          </span>
                        </div>
                        <span className={`text-sm font-semibold tabular-nums ${isToday ? 'text-orange-400' : 'text-zinc-300'}`}>
                          ${amount.toLocaleString()}
                        </span>
                      </div>
                    );
                  })}
                </div>

                {/* Total */}
                <div className="flex items-center justify-between pt-3 border-t border-white/10">
                  <span className="text-sm font-bold text-white">Total You'll Pay</span>
                  <span className="text-lg font-bold text-emerald-400 tabular-nums">
                    ${showFlexPayConfirm.variant.monthly_price.toLocaleString()} USD
                  </span>
                </div>
              </div>

              {/* Currency Note - Clear USD Explanation */}
              <div className="bg-blue-500/10 rounded-lg px-4 py-3 border border-blue-500/20">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                  <div className="text-xs text-zinc-300 leading-relaxed">
                    <p className="font-medium text-blue-300 mb-1">About the Payment Display</p>
                    <p>
                      You will be charged <strong className="text-white">${showFlexPayConfirm.variant.monthly_price.toLocaleString()} USD total</strong> in daily ~$100 installments. 
                      Your bank statement may show the local currency equivalent, but the charge is <strong className="text-emerald-400">exactly $100/day in USD</strong>.
                    </p>
                    <p className="mt-1.5 text-zinc-500">
                      📅 <strong>Day 1:</strong> Full ticket features active immediately<br/>
                      📱 <strong>Day 11:</strong> SMS & Calling features unlock<br/>
                      🔄 <strong>Month 2+:</strong> All features active from Day 1
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="px-6 pb-6 flex gap-3">
              <button
                onClick={() => setShowFlexPayConfirm(null)}
                className="flex-1 px-4 py-3 rounded-xl text-sm font-medium bg-white/5 text-zinc-300 hover:bg-white/10 transition-colors"
              >
                Cancel
              </button>
              <RazorpayCheckout
                amount={100}
                currency="INR"
                isFlexPayMode={true}
                companyId={user.company_id || user.id || ''}
                tier={showFlexPayConfirm.variant.key as 'parwa' | 'high'}
                totalAmount={showFlexPayConfirm.variant.monthly_price}
                planId={showFlexPayConfirm.planId}
                customerEmail={user.email || ''}
                customerName={user.name || 'Customer'}
                name={`PARWA — ${showFlexPayConfirm.variant.name}`}
                description={`${showFlexPayConfirm.variant.name}: $${showFlexPayConfirm.variant.monthly_price}/mo via FlexPay`}
                buttonText={`Pay $100 • Start FlexPay`}
                onSuccess={() => {
                  setShowFlexPayConfirm(null);
                  toast.success(`${showFlexPayConfirm.variant.name} activated! Daily charges begin.`);
                  setTimeout(() => fetchAll(), 1500);
                }}
                onTokenizationComplete={(tokenData) => {
                  console.log('[FlexPay] Token saved:', tokenData);
                  setShowFlexPayConfirm(null);
                }}
              />
            </div>
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}
