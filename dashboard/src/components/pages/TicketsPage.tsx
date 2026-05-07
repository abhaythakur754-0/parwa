'use client';

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import {
  useTicketStore,
  seedIfEmpty,
  CATEGORY_LABELS,
  PRIORITY_LABELS,
  STATUS_LABELS,
  CHANNEL_LABELS,
  VARIANT_LABELS,
  ALL_CATEGORIES,
  ALL_STATUSES,
  ALL_PRIORITIES,
  ALL_CHANNELS,
  ALL_VARIANTS,
  type Ticket,
  type TicketCategory,
  type TicketPriority,
  type TicketStatus,
  type TicketChannel,
  type TicketVariant,
} from '@/lib/ticket-store';

// ── AI Response Templates ──────────────────────────────────────────

const AI_RESPONSES: Record<TicketVariant, Record<TicketCategory, string[]>> = {
  light: {
    billing_payments: [
      "I've reviewed your billing concern. Let me pull up your recent transactions and help resolve this quickly.",
      "Thank you for contacting us about this billing matter. I can see the charges in question and I'm happy to help.",
    ],
    order_management: [
      "I've located your order in our system. Let me check the current status for you right away.",
      "Thanks for providing your order number. I can see the tracking details — let me get that info for you.",
    ],
    account_management: [
      "I can help you with your account settings. Let me verify your identity first for security purposes.",
      "Thanks for reaching out about your account. I'll guide you through the process step by step.",
    ],
    technical_support: [
      "I understand the technical issue you're experiencing. Let me check our knowledge base for known solutions.",
      "Thanks for describing the issue. I have a few troubleshooting steps we can try together.",
    ],
    returns_exchanges: [
      "I can help process your return or exchange. Let me pull up your order details.",
      "Thank you for your patience. I'll get this return/exchange started for you right away.",
    ],
    shipping_delivery: [
      "I've checked your shipping information. Let me look into the delivery status for you.",
      "Thanks for your patience regarding the delivery. I'm checking the tracking details now.",
    ],
    product_information: [
      "I'd be happy to provide information about that product. Let me pull up the specifications.",
      "Great question! Here's what I can tell you about this product.",
    ],
    complaints: [
      "I'm sorry to hear about your experience. Your feedback is important and I want to help make this right.",
      "I understand your frustration and I sincerely apologize. Let me see what I can do to resolve this.",
    ],
    vip_enterprise: [
      "Thank you for reaching out. As a valued enterprise customer, I'm prioritizing your request.",
      "I appreciate you bringing this to our attention. Let me connect you with our enterprise support team.",
    ],
    fraud_security: [
      "I take security concerns very seriously. Let me help secure your account immediately.",
      "Thank you for reporting this. I'm initiating our security protocol right away.",
    ],
  },
  medium: {
    billing_payments: [
      "I've analyzed your billing history and identified the issue. Here's what happened and how I'm going to resolve it: I'll initiate the necessary adjustments and you should see the correction within 2-3 business days.",
      "After reviewing your account, I can see the billing discrepancy. This appears to be caused by a rate change that wasn't properly prorated. I'm correcting this now and will credit your account for the difference.",
    ],
    order_management: [
      "I've traced your order through our fulfillment system and identified where it is in the process. There seems to be a slight delay at our distribution center. I'm expediting this and upgrading your shipping to express at no extra cost.",
      "Your order has been located and I can see it's currently in transit. However, I notice there's been a routing issue that may cause a 1-2 day delay. I'm working with our logistics team to get this resolved as quickly as possible.",
    ],
    account_management: [
      "I've reviewed your account configuration and found the issue. The settings change requires a sync across our systems. I've initiated the update and it should propagate within the hour. I'll also send you a confirmation email once everything is fully updated.",
      "After investigating your account, I can see the root cause of the issue. This is related to a recent system migration that affected a subset of accounts. I'm applying a fix now and adding you to our priority support list to prevent future occurrences.",
    ],
    technical_support: [
      "I've analyzed the error patterns you described and cross-referenced them with our known issues database. This appears to be a compatibility issue between your configuration and our latest release. I have a specific workaround that should resolve this while we prepare a permanent fix.",
      "Based on the technical details you provided, I've identified the root cause. This is related to a change in our API authentication flow. Here are the specific steps to resolve this, along with code examples for your integration.",
    ],
    returns_exchanges: [
      "I've reviewed your return request and verified the item eligibility. I'm processing your return now with our expedited handling. You'll receive a prepaid shipping label via email within 30 minutes, and the refund will be issued within 24 hours of the carrier scanning the return shipment.",
      "Your exchange request has been approved. I've placed the replacement order and it will ship within 24 hours via express delivery. A return label for the original item has been generated and sent to your email. The exchange is being processed at no additional cost to you.",
    ],
    shipping_delivery: [
      "I've contacted the carrier directly and obtained an update on your shipment. It appears there was a sorting error at the regional distribution center. I've filed a priority trace request and the carrier has committed to resolving this within 24 hours. If the package isn't located, I'll ship a replacement immediately.",
      "I've investigated the delivery issue and found that your package was misrouted during transit. I've escalated this with our logistics partner and they've confirmed the package is being redirected to the correct address. Updated delivery estimate is within 48 hours.",
    ],
    product_information: [
      "Here are the comprehensive specifications you requested. Based on your use case, I'd also recommend considering these specific features. Would you like me to schedule a demo or connect you with our product specialist for a more detailed consultation?",
      "I've compiled detailed information about this product including compatibility notes, performance benchmarks, and customer feedback summaries. Based on your requirements, here's my assessment and recommendation.",
    ],
    complaints: [
      "I've carefully reviewed your complaint and the full history of your interactions with our support team. I can see this has been an ongoing frustration, and I want to assure you that I'm taking personal ownership of resolving this. Here's my action plan with specific timelines and commitments.",
      "Your complaint has been escalated to our Customer Experience team with the highest priority. I understand the impact this has had on your experience, and I'm implementing several corrective measures immediately. Here's what I'm doing to make this right.",
    ],
    vip_enterprise: [
      "As an enterprise customer, I'm providing you with dedicated support for this matter. I've reviewed your account in detail and I'm coordinating with our enterprise solutions team to provide a comprehensive resolution. A senior technical consultant will be assigned to your case within the hour.",
      "I understand the business impact this is having on your operations. I'm personally coordinating with our engineering, support, and management teams to ensure a rapid resolution. You'll receive updates every 2 hours until this is fully resolved.",
    ],
    fraud_security: [
      "I've initiated our enhanced security protocol for your account. This includes a full audit of recent account activity, IP address verification, and session analysis. I'm also coordinating with our security engineering team to identify any potential vulnerabilities. A security specialist will contact you within 30 minutes with a detailed report.",
      "Your security concern has been escalated to our Fraud Prevention team with P1 priority. I've taken immediate protective measures including account hardening and activity monitoring. Here's a detailed timeline of the suspicious activity I've identified so far.",
    ],
  },
  heavy: {
    billing_payments: [
      "I've conducted a comprehensive analysis of your billing history spanning the past 12 months. The pattern I've identified indicates a systematic issue with how prorated charges are calculated during mid-cycle plan changes. This has affected approximately 3% of our customer base. I'm implementing a three-pronged approach: (1) immediate credit for all affected charges, (2) escalation to our billing engineering team to fix the root cause, and (3) a 60-day enhanced monitoring period for your account to ensure accuracy.",
      "After a thorough review of your billing records, I've identified a complex interaction between our legacy billing system and the new tax calculation engine that's causing these discrepancies. The issue is specifically triggered when multi-currency transactions are involved with your enterprise account settings. I've created a custom billing adjustment and am working with our finance team to ensure this is permanently resolved. Your account has been credited $X.XX for all overcharges.",
    ],
    order_management: [
      "I've performed a deep-dive analysis of your order lifecycle and identified a cascading failure in our fulfillment pipeline. The root cause is a synchronization issue between our inventory management system and the warehouse management system, which caused your order to be incorrectly flagged as 'pending allocation' for an extended period. I've resolved the immediate issue, escalated the systemic problem to our supply chain engineering team, and implemented a manual monitoring check on your remaining orders. Your order is now being express-shipped with delivery guaranteed within 48 hours.",
    ],
    account_management: [
      "I've conducted a comprehensive audit of your account configuration and identified several interconnected issues stemming from a data migration that occurred during our platform upgrade. The migration affected account metadata, permission structures, and integration tokens. I'm executing a systematic remediation plan that will restore full functionality while preserving your historical data. I've also implemented additional safeguards to prevent similar issues during future migrations. You'll have full access restored within 2 hours, and I'll provide a detailed post-mortem report.",
    ],
    technical_support: [
      "I've performed an in-depth technical analysis of the issues you're experiencing. The root cause is a complex interaction between your API integration architecture and our recent platform changes. Specifically, the issue stems from a breaking change in our webhook event payload structure that wasn't properly documented in our changelog. I've identified the exact API calls affected and have prepared a detailed migration guide with code examples for each affected endpoint. I'm also working with our documentation team to update our API reference. A dedicated integration engineer is being assigned to assist with your migration.",
    ],
    returns_exchanges: [
      "I've reviewed your return/exchange situation holistically, taking into account your purchase history, the product condition report, and our return policy parameters. Given the circumstances, I'm authorizing an exception to our standard return window. Additionally, I'm upgrading your replacement shipment to priority express delivery and including a complimentary care package. I'm also creating a feedback loop with our quality assurance team regarding the specific product defect you experienced to prevent future occurrences.",
    ],
    shipping_delivery: [
      "I've initiated a comprehensive logistics investigation involving our shipping partners, warehouse network, and delivery optimization systems. The delivery failure was caused by an unusual confluence of factors: a regional weather event, a carrier routing algorithm error, and a warehouse inventory allocation issue. I've implemented a custom delivery solution that bypasses the affected routing path. Your replacement package is being shipped via a dedicated courier with real-time GPS tracking, which I'll share with you directly. Expected delivery: 24 hours.",
    ],
    product_information: [
      "I've compiled an exhaustive technical analysis of the product specifications, including compatibility matrices, performance benchmarks across different environments, and a comparison with alternative solutions in the market. Based on your specific requirements and use case, here's my detailed recommendation with a phased implementation strategy. I can also arrange a technical deep-dive session with our product engineering team if you'd like to discuss architecture and integration details.",
    ],
    complaints: [
      "I've conducted a thorough review of your entire customer journey with our company, including every interaction, transaction, and touchpoint. Your frustration is completely justified, and I take full responsibility for the failures in our service delivery. I'm implementing a comprehensive remediation plan that addresses each of your concerns individually, with specific owners and deadlines. Additionally, I'm proposing structural changes to our support processes to prevent similar experiences for any customer. You'll receive a personal follow-up from our VP of Customer Experience within 24 hours.",
    ],
    vip_enterprise: [
      "As a valued enterprise partner, I've engaged our executive response team to provide you with white-glove service for this matter. I've conducted a cross-functional analysis involving our engineering, product, support, and leadership teams. The resolution plan I'm presenting has been reviewed and approved by our CTO and VP of Customer Success. It includes immediate mitigation steps, short-term fixes, and long-term architectural improvements specifically tailored to your enterprise requirements. A dedicated technical account manager will be your single point of contact throughout this process.",
    ],
    fraud_security: [
      "I've activated our highest-tier security response protocol. This involves our Security Operations Center (SOC), fraud investigation team, and external cybersecurity consultants. I've performed a preliminary forensic analysis that reveals a sophisticated attack vector — specifically, a session hijacking exploit that bypassed our standard authentication controls. I've implemented emergency security measures including mandatory session revalidation, enhanced logging, and behavioral analysis monitoring. Our security team is conducting a full forensic investigation, and I'll provide you with a detailed incident report within 4 hours. In the meantime, I recommend additional precautionary steps that I'll walk you through.",
    ],
  },
};

function getRandomAIResponse(variant: TicketVariant, category: TicketCategory): string {
  const responses = AI_RESPONSES[variant]?.[category] ?? AI_RESPONSES.light.billing_payments;
  return responses[Math.floor(Math.random() * responses.length)];
}

// ── Badge Components ────────────────────────────────────────────────

function StatusBadge({ status }: { status: TicketStatus }) {
  const styles: Record<TicketStatus, string> = {
    open: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    in_progress: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    resolved: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    closed: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
    awaiting_client: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    awaiting_human: 'bg-red-500/10 text-red-400 border-red-500/20',
  };
  return (
    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${styles[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}

function PriorityBadge({ priority }: { priority: TicketPriority }) {
  const styles: Record<TicketPriority, string> = {
    low: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
    medium: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    high: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    critical: 'bg-red-500/10 text-red-400 border-red-500/20',
  };
  return (
    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${styles[priority]}`}>
      {PRIORITY_LABELS[priority]}
    </span>
  );
}

function VariantBadge({ variant }: { variant: TicketVariant }) {
  const styles: Record<TicketVariant, string> = {
    light: 'bg-zinc-500/10 text-zinc-300 border-zinc-500/20',
    medium: 'bg-sky-500/10 text-sky-300 border-sky-500/20',
    heavy: 'bg-orange-500/10 text-orange-300 border-orange-500/20',
  };
  return (
    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${styles[variant]}`}>
      {variant.toUpperCase()}
    </span>
  );
}

function ChannelIcon({ channel }: { channel: TicketChannel }) {
  const icons: Record<TicketChannel, React.ReactNode> = {
    email: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" />
      </svg>
    ),
    chat: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
      </svg>
    ),
    sms: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 1.5H8.25A2.25 2.25 0 0 0 6 3.75v16.5a2.25 2.25 0 0 0 2.25 2.25h7.5A2.25 2.25 0 0 0 18 20.25V3.75a2.25 2.25 0 0 0-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3" />
      </svg>
    ),
    voice: (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 0 0 2.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 0 1-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 0 0-1.091-.852H4.5A2.25 2.25 0 0 0 2.25 4.5v2.25Z" />
      </svg>
    ),
  };
  return <span className="text-zinc-500">{icons[channel]}</span>;
}

// ── Date Formatting ─────────────────────────────────────────────────

function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ── Filter Dropdown ─────────────────────────────────────────────────

function FilterSelect<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: T; label: string }[];
  onChange: (value: T | 'all') => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-[11px] text-zinc-500 whitespace-nowrap hidden sm:block">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T | 'all')}
        className="h-8 bg-[#1A1A1A] border border-white/[0.06] rounded-lg px-2.5 text-xs text-zinc-300 focus:outline-none focus:border-orange-500/40 appearance-none cursor-pointer pr-7"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2371717a' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`,
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'right 8px center',
        }}
      >
        <option value="all">All {label}</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

// ── Create Ticket Modal ─────────────────────────────────────────────

function CreateTicketModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const addTicket = useTicketStore((s) => s.addTicket);

  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState<TicketCategory>('billing_payments');
  const [priority, setPriority] = useState<TicketPriority>('medium');
  const [channel, setChannel] = useState<TicketChannel>('email');
  const [customerName, setCustomerName] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim() || !customerName.trim() || !customerEmail.trim()) {
      toast.error('Please fill in all required fields');
      return;
    }

    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!emailRegex.test(customerEmail.trim())) {
      toast.error('Please enter a valid email address');
      return;
    }

    setIsSubmitting(true);
    // Simulate a brief delay
    await new Promise((r) => setTimeout(r, 300));

    const ticket = addTicket({
      subject: subject.trim(),
      description: description.trim(),
      category,
      priority,
      channel,
      customer_name: customerName.trim(),
      customer_email: customerEmail.trim(),
    });

    // Add initial customer message
    const store = useTicketStore.getState();
    store.addMessage(ticket.id, {
      sender: 'customer',
      sender_name: customerName.trim(),
      content: description.trim() || subject.trim(),
    });

    toast.success(`Ticket ${ticket.ticket_number} created successfully`);
    resetForm();
    setIsSubmitting(false);
    onClose();
  };

  const resetForm = () => {
    setSubject('');
    setDescription('');
    setCategory('billing_payments');
    setPriority('medium');
    setChannel('email');
    setCustomerName('');
    setCustomerEmail('');
  };

  if (!open) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          className="relative w-full max-w-lg bg-[#1A1A1A] border border-white/[0.06] rounded-2xl shadow-2xl max-h-[90vh] overflow-y-auto"
        >
          {/* Header */}
          <div className="sticky top-0 bg-[#1A1A1A] border-b border-white/[0.06] p-5 flex items-center justify-between z-10">
            <div>
              <h2 className="text-white font-semibold">Create New Ticket</h2>
              <p className="text-zinc-500 text-xs mt-0.5">
                AI variant will be auto-assigned based on complexity
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="p-5 space-y-4">
            {/* Customer Info */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-zinc-400 mb-1 block">
                  Customer Name <span className="text-orange-400">*</span>
                </label>
                <input
                  type="text"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  placeholder="John Doe"
                  className="w-full h-9 bg-[#0F0F0F] border border-white/[0.06] rounded-lg px-3 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
                />
              </div>
              <div>
                <label className="text-[11px] text-zinc-400 mb-1 block">
                  Customer Email <span className="text-orange-400">*</span>
                </label>
                <input
                  type="email"
                  value={customerEmail}
                  onChange={(e) => setCustomerEmail(e.target.value)}
                  placeholder="john@example.com"
                  className="w-full h-9 bg-[#0F0F0F] border border-white/[0.06] rounded-lg px-3 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
                />
              </div>
            </div>

            {/* Subject */}
            <div>
              <label className="text-[11px] text-zinc-400 mb-1 block">
                Subject <span className="text-orange-400">*</span>
              </label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Brief description of the issue"
                className="w-full h-9 bg-[#0F0F0F] border border-white/[0.06] rounded-lg px-3 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
              />
            </div>

            {/* Description */}
            <div>
              <label className="text-[11px] text-zinc-400 mb-1 block">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Detailed description of the issue or request..."
                rows={3}
                className="w-full bg-[#0F0F0F] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors resize-none"
              />
            </div>

            {/* Category, Priority, Channel */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-[11px] text-zinc-400 mb-1 block">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value as TicketCategory)}
                  className="w-full h-9 bg-[#0F0F0F] border border-white/[0.06] rounded-lg px-3 text-sm text-zinc-300 focus:outline-none focus:border-orange-500/40 appearance-none cursor-pointer pr-7"
                  style={{
                    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2371717a' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`,
                    backgroundRepeat: 'no-repeat',
                    backgroundPosition: 'right 8px center',
                  }}
                >
                  {ALL_CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {CATEGORY_LABELS[c]}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[11px] text-zinc-400 mb-1 block">Priority</label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as TicketPriority)}
                  className="w-full h-9 bg-[#0F0F0F] border border-white/[0.06] rounded-lg px-3 text-sm text-zinc-300 focus:outline-none focus:border-orange-500/40 appearance-none cursor-pointer pr-7"
                  style={{
                    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2371717a' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`,
                    backgroundRepeat: 'no-repeat',
                    backgroundPosition: 'right 8px center',
                  }}
                >
                  {ALL_PRIORITIES.map((p) => (
                    <option key={p} value={p}>
                      {PRIORITY_LABELS[p]}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[11px] text-zinc-400 mb-1 block">Channel</label>
                <select
                  value={channel}
                  onChange={(e) => setChannel(e.target.value as TicketChannel)}
                  className="w-full h-9 bg-[#0F0F0F] border border-white/[0.06] rounded-lg px-3 text-sm text-zinc-300 focus:outline-none focus:border-orange-500/40 appearance-none cursor-pointer pr-7"
                  style={{
                    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2371717a' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`,
                    backgroundRepeat: 'no-repeat',
                    backgroundPosition: 'right 8px center',
                  }}
                >
                  {ALL_CHANNELS.map((ch) => (
                    <option key={ch} value={ch}>
                      {CHANNEL_LABELS[ch]}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Auto-assign preview */}
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-3 flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-orange-500/10 flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
                </svg>
              </div>
              <div>
                <p className="text-xs text-zinc-300 font-medium">AI Auto-Assignment</p>
                <p className="text-[11px] text-zinc-500">
                  Will be routed to{' '}
                  <span className="text-orange-400 font-medium">
                    {priority === 'critical'
                      ? 'Heavy (Claude 3.5)'
                      : priority === 'high'
                      ? 'Medium (Gemini Pro)'
                      : ['fraud_security', 'vip_enterprise', 'complaints'].includes(category)
                      ? 'Medium (Gemini Pro)'
                      : 'Light (Gemini Flash)'}
                  </span>
                  {' '}based on priority & category rules
                </p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 h-10 rounded-lg border border-white/[0.06] text-sm text-zinc-400 hover:text-zinc-300 hover:border-white/10 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex-1 h-10 rounded-lg bg-orange-500 text-sm text-white font-medium hover:bg-orange-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Creating...
                  </>
                ) : (
                  'Create Ticket'
                )}
              </button>
            </div>
          </form>
        </motion.div>
      </motion.div>
  );
}

// ── Ticket Detail Panel ─────────────────────────────────────────────

function TicketDetailPanel({
  ticketId,
  onClose,
}: {
  ticketId: string;
  onClose: () => void;
}) {
  const ticket = useTicketStore((s) => s.tickets.find(t => t.id === ticketId) ?? null);
  const resolveTicket = useTicketStore((s) => s.resolveTicket);
  const escalateToHuman = useTicketStore((s) => s.escalateToHuman);
  const updatePriority = useTicketStore((s) => s.updatePriority);
  const assignVariant = useTicketStore((s) => s.assignVariant);
  const addMessage = useTicketStore((s) => s.addMessage);
  const [resolutionText, setResolutionText] = useState('');
  const [showResolveInput, setShowResolveInput] = useState(false);
  const [showPriorityMenu, setShowPriorityMenu] = useState(false);
  const [showVariantMenu, setShowVariantMenu] = useState(false);
  const [newMessage, setNewMessage] = useState('');
  const [isAiTyping, setIsAiTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const aiTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const isAiRespondingRef = useRef(false);

  // Cleanup AI timer on unmount
  useEffect(() => () => { if (aiTimerRef.current) clearTimeout(aiTimerRef.current); }, []);

  if (!ticket) return null;

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [ticket.messages.length, isAiTyping, scrollToBottom]);

  // Call REAL LLM API when opening an open ticket with an unanswered customer message
  useEffect(() => {
    if (!ticket || ticket.status !== 'open' || !ticket.assigned_variant || ticket.messages.length === 0) return;
    if (isAiRespondingRef.current) return;
    const lastCustomerMsg = [...ticket.messages].reverse().find(m => m.sender === 'customer');
    if (lastCustomerMsg) {
      const hasAiResponse = ticket.messages.some(
        m => m.sender === 'ai_agent' && new Date(m.created_at) > new Date(lastCustomerMsg.created_at)
      );
      if (!hasAiResponse) {
        isAiRespondingRef.current = true;
        setIsAiTyping(true);
        callRealAI(lastCustomerMsg.content);
      }
    }
  }, [ticket?.id, ticket?.status, ticket?.assigned_variant, ticket?.messages.length]);

  // Call REAL LLM via /api/ticket-solve
  const callRealAI = async (customerText: string) => {
    const currentTicket = useTicketStore.getState().getTicket(ticketId);
    if (!currentTicket) { isAiRespondingRef.current = false; setIsAiTyping(false); return; }

    const variant = currentTicket.assigned_variant ?? 'light';
    try {
      const res = await fetch('/api/ticket-solve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticketId,
          customerMessage: customerText,
          variant,
          category: currentTicket.category,
          priority: currentTicket.priority,
          channel: currentTicket.channel,
          customerName: currentTicket.customer_name,
          conversationHistory: currentTicket.messages.map(m => ({ role: m.sender === 'customer' ? 'user' : 'assistant', content: m.content, sender: m.sender })),
        }),
      });
      const data = await res.json();
      if (data.response) {
        useTicketStore.getState().addMessage(ticketId, {
          sender: 'ai_agent',
          sender_name: 'PARWA AI',
          content: data.response,
          variant,
        });
        if (data.shouldEscalate) {
          useTicketStore.getState().escalateToHuman(ticketId);
          toast('Ticket escalated to human agent', { icon: '⚠️' });
        } else {
          toast.success(`${variant.toUpperCase()} variant responded`);
        }
      }
    } catch (err) {
      console.error('AI solve error:', err);
      toast.error('AI response failed — using fallback');
      // Fallback to canned response only if API fails
      const response = getRandomAIResponse(variant, currentTicket.category);
      useTicketStore.getState().addMessage(ticketId, {
        sender: 'ai_agent', sender_name: 'PARWA AI', content: response, variant,
      });
    } finally {
      setIsAiTyping(false);
      isAiRespondingRef.current = false;
    }
  };

  const handleSendMessage = () => {
    if (!newMessage.trim() || !ticket) return;
    addMessage(ticketId, {
      sender: 'customer',
      sender_name: ticket.customer_name,
      content: newMessage.trim(),
    });
    setNewMessage('');

    // Call REAL LLM API for follow-up messages (skip if one is already in-flight)
    if (ticket.assigned_variant && !isAiRespondingRef.current) {
      isAiRespondingRef.current = true;
      setIsAiTyping(true);
      callRealAI(newMessage.trim());
    }
  };

  const handleResolve = () => {
    if (!resolutionText.trim()) {
      toast.error('Please provide resolution notes');
      return;
    }
    resolveTicket(ticketId, resolutionText.trim());
    setShowResolveInput(false);
    setResolutionText('');
    toast.success('Ticket resolved successfully');
    onClose();
  };

  const handleEscalate = () => {
    escalateToHuman(ticketId);
    toast.success('Ticket escalated to human agent');
    onClose();
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', damping: 30, stiffness: 300 }}
          className="relative w-full max-w-2xl ml-auto bg-[#0F0F0F] border-l border-white/[0.06] flex flex-col h-full"
        >
          {/* Header */}
          <div className="border-b border-white/[0.06] p-4 flex-shrink-0">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3 min-w-0">
                <button
                  onClick={onClose}
                  className="w-8 h-8 flex items-center justify-center rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors flex-shrink-0"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
                  </svg>
                </button>
                <div className="min-w-0">
                  <p className="text-[11px] text-zinc-500 font-mono">{ticket.ticket_number}</p>
                  <h2 className="text-white font-semibold text-sm truncate">{ticket.subject}</h2>
                </div>
              </div>
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <StatusBadge status={ticket.status} />
                <PriorityBadge priority={ticket.priority} />
                {ticket.assigned_variant && <VariantBadge variant={ticket.assigned_variant} />}
              </div>
            </div>

            {/* Meta info */}
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-zinc-500 ml-11">
              <span>{ticket.customer_name}</span>
              <span className="text-zinc-600">•</span>
              <span>{ticket.customer_email}</span>
              <span className="text-zinc-600">•</span>
              <span>{CATEGORY_LABELS[ticket.category]}</span>
              <span className="text-zinc-600">•</span>
              <span className="flex items-center gap-1"><ChannelIcon channel={ticket.channel} />{CHANNEL_LABELS[ticket.channel]}</span>
              <span className="text-zinc-600">•</span>
              <span>{formatRelativeDate(ticket.created_at)}</span>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {ticket.messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex ${msg.sender === 'customer' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                    msg.sender === 'customer'
                      ? 'bg-orange-500/10 border border-orange-500/20'
                      : msg.sender === 'ai_agent'
                      ? 'bg-[#1A1A1A] border border-white/[0.06]'
                      : 'bg-zinc-500/5 border border-zinc-500/10'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[11px] font-medium text-zinc-400">
                      {msg.sender === 'customer'
                        ? ticket.customer_name
                        : msg.sender === 'ai_agent'
                        ? `PARWA AI ${msg.variant ? `(${msg.variant.toUpperCase()})` : ''}`
                        : 'System'}
                    </span>
                    <span className="text-[10px] text-zinc-600">
                      {formatRelativeDate(msg.created_at)}
                    </span>
                  </div>
                  <p className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">
                    {msg.content}
                  </p>
                </div>
              </motion.div>
            ))}

            {/* AI Typing indicator */}
            {isAiTyping && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex justify-start"
              >
                <div className="bg-[#1A1A1A] border border-white/[0.06] rounded-2xl px-4 py-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[11px] font-medium text-zinc-400">
                      PARWA AI {ticket.assigned_variant ? `(${ticket.assigned_variant.toUpperCase()})` : ''}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Resolve Input */}
          {showResolveInput && (
            <div className="border-t border-white/[0.06] p-4 bg-[#1A1A1A]">
              <label className="text-[11px] text-zinc-400 mb-2 block">Resolution Notes</label>
              <textarea
                value={resolutionText}
                onChange={(e) => setResolutionText(e.target.value)}
                placeholder="Describe how the issue was resolved..."
                rows={2}
                className="w-full bg-[#0F0F0F] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 resize-none mb-3"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => setShowResolveInput(false)}
                  className="flex-1 h-9 rounded-lg border border-white/[0.06] text-xs text-zinc-400 hover:text-zinc-300 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleResolve}
                  className="flex-1 h-9 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-medium hover:bg-emerald-500/20 transition-colors"
                >
                  Resolve Ticket
                </button>
              </div>
            </div>
          )}

          {/* Action bar */}
          <div className="border-t border-white/[0.06] p-3 flex-shrink-0">
            {/* Quick actions row */}
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              {(ticket.status === 'open' || ticket.status === 'in_progress' || ticket.status === 'awaiting_client') && (
                <>
                  <button
                    onClick={() => setShowResolveInput(true)}
                    className="h-8 px-3 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[11px] font-medium hover:bg-emerald-500/20 transition-colors flex items-center gap-1.5"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                    </svg>
                    Resolve
                  </button>
                  {(ticket.status === 'open' || ticket.status === 'in_progress') && (
                  <button
                    onClick={handleEscalate}
                    className="h-8 px-3 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 text-[11px] font-medium hover:bg-red-500/20 transition-colors flex items-center gap-1.5"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                    </svg>
                    Escalate
                  </button>
                  )}
                </>
              )}

              {/* Priority dropdown */}
              <div className="relative">
                <button
                  onClick={() => { setShowPriorityMenu(!showPriorityMenu); setShowVariantMenu(false); }}
                  className="h-8 px-3 rounded-lg bg-white/5 text-zinc-400 border border-white/10 text-[11px] font-medium hover:border-white/20 transition-colors"
                >
                  Priority: {PRIORITY_LABELS[ticket.priority]}
                </button>
                {showPriorityMenu && (
                  <div className="absolute bottom-full mb-1 left-0 bg-[#1A1A1A] border border-white/[0.06] rounded-lg shadow-xl py-1 z-20 min-w-[120px]">
                    {ALL_PRIORITIES.map((p) => (
                      <button
                        key={p}
                        onClick={() => {
                          updatePriority(ticket.id, p);
                          setShowPriorityMenu(false);
                          toast.success(`Priority updated to ${PRIORITY_LABELS[p]}`);
                        }}
                        className={`w-full px-3 py-1.5 text-left text-xs hover:bg-white/5 transition-colors flex items-center gap-2 ${
                          ticket.priority === p ? 'text-orange-400' : 'text-zinc-300'
                        }`}
                      >
                        <PriorityBadge priority={p} />
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Variant dropdown */}
              <div className="relative">
                <button
                  onClick={() => { setShowVariantMenu(!showVariantMenu); setShowPriorityMenu(false); }}
                  className="h-8 px-3 rounded-lg bg-white/5 text-zinc-400 border border-white/10 text-[11px] font-medium hover:border-white/20 transition-colors"
                >
                  AI: {ticket.assigned_variant ? ticket.assigned_variant.toUpperCase() : 'None'}
                </button>
                {showVariantMenu && (
                  <div className="absolute bottom-full mb-1 left-0 bg-[#1A1A1A] border border-white/[0.06] rounded-lg shadow-xl py-1 z-20 min-w-[180px]">
                    {ALL_VARIANTS.map((v) => (
                      <button
                        key={v}
                        onClick={() => {
                          assignVariant(ticket.id, v);
                          setShowVariantMenu(false);
                          toast.success(`Reassigned to ${VARIANT_LABELS[v]}`);
                        }}
                        className={`w-full px-3 py-1.5 text-left text-xs hover:bg-white/5 transition-colors ${
                          ticket.assigned_variant === v ? 'text-orange-400' : 'text-zinc-300'
                        }`}
                      >
                        <VariantBadge variant={v} />
                        <span className="ml-2 text-[10px] text-zinc-500">{VARIANT_LABELS[v]}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Info badges */}
              {ticket.ai_confidence && (
                <span className="text-[10px] text-zinc-500 ml-auto hidden sm:block">
                  Confidence: {ticket.ai_confidence}%
                </span>
              )}
              {ticket.cost_per_ticket !== null && (
                <span className="text-[10px] text-zinc-500 hidden sm:block">
                  Cost: ${ticket.cost_per_ticket.toFixed(3)}
                </span>
              )}
            </div>

            {/* Message input */}
            {ticket.status !== 'resolved' && ticket.status !== 'closed' && (
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder={`Message as ${ticket.customer_name}...`}
                  className="flex-1 h-9 bg-[#1A1A1A] border border-white/[0.06] rounded-lg px-3 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!newMessage.trim() || isAiTyping}
                  className="h-9 w-9 rounded-lg bg-orange-500 text-white flex items-center justify-center hover:bg-orange-600 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
                  </svg>
                </button>
              </div>
            )}
          </div>
        </motion.div>
    </motion.div>
  );
}

// ── Main TicketsPage ────────────────────────────────────────────────

export default function TicketsPage() {
  const tickets = useTicketStore((s) => s.tickets);
  const init = useTicketStore((s) => s.init);
  const ticketStats = useTicketStore((s) => s.ticketStats);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const selectedTicket = useTicketStore((s) => selectedTicketId ? s.tickets.find(t => t.id === selectedTicketId) ?? null : null);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<TicketStatus | 'all'>('all');
  const [filterCategory, setFilterCategory] = useState<TicketCategory | 'all'>('all');
  const [filterPriority, setFilterPriority] = useState<TicketPriority | 'all'>('all');
  const [filterChannel, setFilterChannel] = useState<TicketChannel | 'all'>('all');
  const [filterVariant, setFilterVariant] = useState<TicketVariant | 'all'>('all');
  const [initialized, setInitialized] = useState(false);

  // Initialize store and seed
  useEffect(() => {
    const initialize = () => {
      init();
      const wasSeeded = seedIfEmpty();
      if (wasSeeded) {
        // Re-init to load seeded data
        init();
      }
      setInitialized(true);
    };
    initialize();
  }, []);

  const filteredTickets = useMemo(() => {
    return tickets.filter((t) => {
      if (filterStatus !== 'all' && t.status !== filterStatus) return false;
      if (filterCategory !== 'all' && t.category !== filterCategory) return false;
      if (filterPriority !== 'all' && t.priority !== filterPriority) return false;
      if (filterChannel !== 'all' && t.channel !== filterChannel) return false;
      if (filterVariant !== 'all' && t.assigned_variant !== filterVariant) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          t.ticket_number.toLowerCase().includes(q) ||
          t.subject.toLowerCase().includes(q) ||
          t.customer_name.toLowerCase().includes(q) ||
          t.customer_email.toLowerCase().includes(q) ||
          t.description.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [tickets, filterStatus, filterCategory, filterPriority, filterChannel, filterVariant, search]);

  const stats = ticketStats();

  const handleRowClick = (ticket: Ticket) => {
    setSelectedTicketId(ticket.id);
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-white">Tickets</h1>
          {initialized && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/20">
              {stats.total}
            </span>
          )}
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="h-9 px-4 rounded-lg bg-orange-500 text-white text-sm font-medium hover:bg-orange-600 transition-colors flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Ticket
        </button>
      </div>

      {/* Quick Status Overview */}
      {initialized && (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {ALL_STATUSES.map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(filterStatus === status ? 'all' : status)}
              className={`rounded-lg border p-2.5 text-center transition-all ${
                filterStatus === status
                  ? 'border-orange-500/30 bg-orange-500/5'
                  : 'border-white/[0.06] bg-[#1A1A1A] hover:border-white/[0.1]'
              }`}
            >
              <div className={`text-lg font-bold ${
                status === 'open' ? 'text-blue-400' :
                status === 'in_progress' ? 'text-yellow-400' :
                status === 'resolved' ? 'text-emerald-400' :
                status === 'closed' ? 'text-zinc-400' :
                status === 'awaiting_client' ? 'text-purple-400' :
                'text-red-400'
              }`}>
                {stats.byStatus[status]}
              </div>
              <div className="text-[10px] text-zinc-500 mt-0.5 leading-tight">
                {STATUS_LABELS[status]}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Search & Filters */}
      {initialized && (
        <div className="flex flex-wrap gap-2 items-center">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px] max-w-xs">
            <svg
              className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
            </svg>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search tickets..."
              className="w-full h-8 bg-[#1A1A1A] border border-white/[0.06] rounded-lg pl-8 pr-3 text-xs text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors"
            />
          </div>

          {/* Filter Dropdowns */}
          <FilterSelect
            label="Status"
            value={filterStatus}
            options={ALL_STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
            onChange={setFilterStatus}
          />
          <FilterSelect
            label="Category"
            value={filterCategory}
            options={ALL_CATEGORIES.map((c) => ({ value: c, label: CATEGORY_LABELS[c] }))}
            onChange={setFilterCategory}
          />
          <FilterSelect
            label="Priority"
            value={filterPriority}
            options={ALL_PRIORITIES.map((p) => ({ value: p, label: PRIORITY_LABELS[p] }))}
            onChange={setFilterPriority}
          />
          <FilterSelect
            label="Channel"
            value={filterChannel}
            options={ALL_CHANNELS.map((ch) => ({ value: ch, label: CHANNEL_LABELS[ch] }))}
            onChange={setFilterChannel}
          />
          <FilterSelect
            label="Variant"
            value={filterVariant}
            options={ALL_VARIANTS.map((v) => ({ value: v, label: v.toUpperCase() }))}
            onChange={setFilterVariant}
          />

          {/* Clear filters */}
          {(filterStatus !== 'all' || filterCategory !== 'all' || filterPriority !== 'all' || filterChannel !== 'all' || filterVariant !== 'all' || search) && (
            <button
              onClick={() => {
                setFilterStatus('all');
                setFilterCategory('all');
                setFilterPriority('all');
                setFilterChannel('all');
                setFilterVariant('all');
                setSearch('');
              }}
              className="h-8 px-3 rounded-lg text-[11px] text-orange-400 hover:bg-orange-500/10 transition-colors flex items-center gap-1"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
              </svg>
              Clear
            </button>
          )}
        </div>
      )}

      {/* Ticket Table */}
      {!initialized ? (
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] flex items-center justify-center py-20">
          <div className="flex items-center gap-3 text-zinc-500">
            <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-sm">Loading tickets...</span>
          </div>
        </div>
      ) : filteredTickets.length === 0 ? (
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A]">
          <div className="flex flex-col items-center justify-center py-16 px-6">
            <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-white/5 mb-4">
              <svg className="w-7 h-7 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125V6.375c0-.621-.504-1.125-1.125-1.125H3.375Z" />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-zinc-300 mb-1">
              {search || filterStatus !== 'all' || filterCategory !== 'all' || filterPriority !== 'all' || filterChannel !== 'all' || filterVariant !== 'all'
                ? 'No tickets match your filters'
                : 'No tickets yet'}
            </h3>
            <p className="text-xs text-zinc-500 text-center">
              {search || filterStatus !== 'all' || filterCategory !== 'all' || filterPriority !== 'all' || filterChannel !== 'all' || filterVariant !== 'all'
                ? 'Try adjusting your search or filter criteria'
                : 'Create your first ticket to get started'}
            </p>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
          {/* Desktop Table */}
          <div className="hidden lg:block overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="text-left text-[11px] font-medium text-zinc-500 px-4 py-3 whitespace-nowrap">Ticket #</th>
                  <th className="text-left text-[11px] font-medium text-zinc-500 px-4 py-3 whitespace-nowrap">Subject</th>
                  <th className="text-left text-[11px] font-medium text-zinc-500 px-4 py-3 whitespace-nowrap">Customer</th>
                  <th className="text-left text-[11px] font-medium text-zinc-500 px-4 py-3 whitespace-nowrap">Category</th>
                  <th className="text-left text-[11px] font-medium text-zinc-500 px-4 py-3 whitespace-nowrap">Priority</th>
                  <th className="text-left text-[11px] font-medium text-zinc-500 px-4 py-3 whitespace-nowrap">Status</th>
                  <th className="text-left text-[11px] font-medium text-zinc-500 px-4 py-3 whitespace-nowrap">Channel</th>
                  <th className="text-left text-[11px] font-medium text-zinc-500 px-4 py-3 whitespace-nowrap">Variant</th>
                  <th className="text-left text-[11px] font-medium text-zinc-500 px-4 py-3 whitespace-nowrap">Created</th>
                </tr>
              </thead>
              <tbody>
                {filteredTickets.map((ticket) => (
                  <tr
                    key={ticket.id}
                    onClick={() => handleRowClick(ticket)}
                    className="border-b border-white/[0.03] hover:bg-white/[0.02] cursor-pointer transition-colors group"
                  >
                    <td className="px-4 py-3">
                      <span className="text-[11px] font-mono text-orange-400/80">{ticket.ticket_number}</span>
                    </td>
                    <td className="px-4 py-3 max-w-[240px]">
                      <p className="text-xs text-white truncate group-hover:text-orange-300 transition-colors">
                        {ticket.subject}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-xs text-zinc-300">{ticket.customer_name}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[11px] text-zinc-400">{CATEGORY_LABELS[ticket.category]}</span>
                    </td>
                    <td className="px-4 py-3">
                      <PriorityBadge priority={ticket.priority} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={ticket.status} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <ChannelIcon channel={ticket.channel} />
                        <span className="text-[11px] text-zinc-400">{CHANNEL_LABELS[ticket.channel]}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {ticket.assigned_variant ? (
                        <VariantBadge variant={ticket.assigned_variant} />
                      ) : (
                        <span className="text-[10px] text-zinc-600">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[11px] text-zinc-500">{formatRelativeDate(ticket.created_at)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Cards */}
          <div className="lg:hidden divide-y divide-white/[0.03]">
            {filteredTickets.map((ticket) => (
              <button
                key={ticket.id}
                onClick={() => handleRowClick(ticket)}
                className="w-full p-4 text-left hover:bg-white/[0.02] transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-mono text-orange-400/80">{ticket.ticket_number}</span>
                  <div className="flex items-center gap-1.5">
                    <StatusBadge status={ticket.status} />
                    <PriorityBadge priority={ticket.priority} />
                  </div>
                </div>
                <p className="text-sm text-white mb-1.5 line-clamp-1">{ticket.subject}</p>
                <div className="flex items-center gap-2 text-[11px] text-zinc-500">
                  <span>{ticket.customer_name}</span>
                  <span className="text-zinc-700">•</span>
                  <span>{CATEGORY_LABELS[ticket.category]}</span>
                  <span className="text-zinc-700">•</span>
                  <ChannelIcon channel={ticket.channel} />
                  <span>{formatRelativeDate(ticket.created_at)}</span>
                </div>
              </button>
            ))}
          </div>

          {/* Table footer */}
          <div className="border-t border-white/[0.06] px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500">
              Showing {filteredTickets.length} of {stats.total} tickets
            </span>
            <div className="flex items-center gap-3 text-[11px] text-zinc-500">
              <span>Resolution Rate: <span className="text-emerald-400 font-medium">{stats.resolutionRate}%</span></span>
              {stats.avgResolutionTime && (
                <span>Avg Resolution: <span className="text-zinc-300 font-medium">{stats.avgResolutionTime}h</span></span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Create Ticket Modal */}
      <AnimatePresence>
        {showCreateModal && (
          <CreateTicketModal
            open={showCreateModal}
            onClose={() => setShowCreateModal(false)}
          />
        )}
      </AnimatePresence>

      {/* Ticket Detail Panel */}
      <AnimatePresence>
        {selectedTicket && (
          <TicketDetailPanel
            ticketId={selectedTicket.id}
            onClose={() => setSelectedTicketId(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
