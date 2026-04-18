'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';

/**
 * MergeCustomersModal - Modal for merging duplicate customers
 *
 * Features:
 * - Shows both customer profiles side by side
 * - Select primary customer (surviving record)
 * - Preview what will be merged
 * - Merge confirmation with reason
 */

export interface Customer {
  id: string;
  email?: string;
  phone?: string;
  name?: string;
  created_at: string;
  total_tickets?: number;
  channels?: { channel_type: string; external_id: string }[];
}

export interface MergePreview {
  primary_customer_id: string;
  merged_customer_ids: string[];
  tickets_to_transfer: number;
  channels_to_transfer: number;
  emails_to_merge: string[];
  phones_to_merge: string[];
}

interface MergeCustomersModalProps {
  isOpen: boolean;
  onClose: () => void;
  customers: Customer[];
  onMerge: (primaryId: string, mergedIds: string[], reason: string) => Promise<void>;
  className?: string;
}

export default function MergeCustomersModal({
  isOpen,
  onClose,
  customers,
  onMerge,
  className,
}: MergeCustomersModalProps) {
  const [selectedPrimary, setSelectedPrimary] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'select' | 'confirm' | 'success'>('select');

  if (!isOpen) return null;

  const handleSelectPrimary = (customerId: string) => {
    setSelectedPrimary(customerId === selectedPrimary ? null : customerId);
  };

  const handleContinue = () => {
    if (!selectedPrimary) return;
    setStep('confirm');
  };

  const handleMerge = async () => {
    if (!selectedPrimary) return;

    const mergedIds = customers.filter((c) => c.id !== selectedPrimary).map((c) => c.id);

    setLoading(true);
    setError(null);

    try {
      await onMerge(selectedPrimary, mergedIds, reason);
      setStep('success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to merge customers');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setStep('select');
    setSelectedPrimary(null);
    setReason('');
    setError(null);
    onClose();
  };

  const primaryCustomer = customers.find((c) => c.id === selectedPrimary);
  const mergedCustomers = customers.filter((c) => c.id !== selectedPrimary);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className={cn(
        'relative w-full max-w-2xl bg-[#1A1A1A] rounded-xl border border-white/[0.06] shadow-2xl',
        className
      )}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/[0.06]">
          <h2 className="text-lg font-semibold text-white">Merge Customers</h2>
          <button
            onClick={handleClose}
            className="p-1 rounded hover:bg-white/[0.06] text-zinc-400 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          {step === 'select' && (
            <>
              <p className="text-sm text-zinc-400 mb-4">
                Select the primary customer (this record will be kept). Other customers will be merged into it.
              </p>

              {/* Customer Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                {customers.map((customer) => (
                  <button
                    key={customer.id}
                    onClick={() => handleSelectPrimary(customer.id)}
                    className={cn(
                      'p-4 rounded-lg border text-left transition-all',
                      selectedPrimary === customer.id
                        ? 'bg-violet-500/10 border-violet-500'
                        : 'bg-white/[0.02] border-white/[0.06] hover:border-white/[0.1]'
                    )}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <div className={cn(
                        'w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold',
                        selectedPrimary === customer.id
                          ? 'bg-gradient-to-br from-violet-500 to-purple-400'
                          : 'bg-zinc-700'
                      )}>
                        {(customer.name || '??').split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-white truncate">
                          {customer.name || 'Unknown'}
                        </p>
                        <p className="text-xs text-zinc-500">ID: {customer.id.slice(0, 8)}...</p>
                      </div>
                      {selectedPrimary === customer.id && (
                        <div className="ml-auto">
                          <svg className="w-5 h-5 text-violet-400" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm3.857-9.809a.75.75 0 0 0-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 1 0-1.06 1.061l2.5 2.5a.75.75 0 0 0 1.137-.089l4-5.5Z" clipRule="evenodd" />
                          </svg>
                        </div>
                      )}
                    </div>

                    <div className="space-y-1 text-xs text-zinc-400">
                      {customer.email && (
                        <p className="truncate">{customer.email}</p>
                      )}
                      {customer.phone && (
                        <p>{customer.phone}</p>
                      )}
                      <p className="text-zinc-500">
                        {customer.total_tickets || 0} tickets • Created {new Date(customer.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </button>
                ))}
              </div>

              {/* Error */}
              {error && (
                <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              )}

              {/* Actions */}
              <div className="flex justify-end gap-2">
                <button
                  onClick={handleClose}
                  className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleContinue}
                  disabled={!selectedPrimary}
                  className={cn(
                    'px-4 py-2 rounded-lg text-sm font-medium transition-all',
                    selectedPrimary
                      ? 'bg-violet-500 hover:bg-violet-600 text-white'
                      : 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                  )}
                >
                  Continue
                </button>
              </div>
            </>
          )}

          {step === 'confirm' && primaryCustomer && (
            <>
              <div className="mb-4 p-4 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <div className="flex items-center gap-2 mb-2">
                  <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                  </svg>
                  <span className="text-sm font-medium text-amber-400">Review Merge</span>
                </div>
                <p className="text-xs text-zinc-400">
                  This action cannot be undone. Merged customer records will be marked as deleted.
                </p>
              </div>

              {/* Merge Preview */}
              <div className="space-y-3 mb-4">
                <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.06]">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Primary Customer (Kept)</p>
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-purple-400 flex items-center justify-center text-white text-xs font-bold">
                      {(primaryCustomer.name || '??').slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">{primaryCustomer.name || 'Unknown'}</p>
                      <p className="text-xs text-zinc-500">{primaryCustomer.email || primaryCustomer.phone}</p>
                    </div>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">
                    To Be Merged ({mergedCustomers.length} customer{mergedCustomers.length > 1 ? 's' : ''})
                  </p>
                  {mergedCustomers.map((c) => (
                    <div key={c.id} className="flex items-center gap-3 py-1">
                      <div className="w-6 h-6 rounded-full bg-zinc-700 flex items-center justify-center text-white text-[10px] font-bold">
                        {(c.name || '??').slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-sm text-zinc-300">{c.name || 'Unknown'}</p>
                        <p className="text-xs text-zinc-500">{c.email || c.phone}</p>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Summary */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] text-center">
                    <p className="text-lg font-semibold text-white">
                      {mergedCustomers.reduce((sum, c) => sum + (c.total_tickets || 0), 0)}
                    </p>
                    <p className="text-xs text-zinc-500">Tickets to Transfer</p>
                  </div>
                  <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] text-center">
                    <p className="text-lg font-semibold text-white">
                      {mergedCustomers.reduce((sum, c) => sum + (c.channels?.length || 0), 0)}
                    </p>
                    <p className="text-xs text-zinc-500">Channels to Transfer</p>
                  </div>
                </div>
              </div>

              {/* Reason */}
              <div className="mb-4">
                <label className="block text-sm text-zinc-400 mb-1">Merge Reason (Optional)</label>
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g., Duplicate accounts identified"
                  className="w-full px-3 py-2 bg-white/[0.02] border border-white/[0.06] rounded-lg text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-violet-500"
                />
              </div>

              {/* Error */}
              {error && (
                <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              )}

              {/* Actions */}
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setStep('select')}
                  className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white transition-colors"
                >
                  Back
                </button>
                <button
                  onClick={handleMerge}
                  disabled={loading}
                  className="px-4 py-2 bg-red-500 hover:bg-red-600 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
                >
                  {loading ? 'Merging...' : 'Confirm Merge'}
                </button>
              </div>
            </>
          )}

          {step === 'success' && primaryCustomer && (
            <div className="text-center py-6">
              <div className="w-16 h-16 mx-auto rounded-full bg-emerald-500/20 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">Customers Merged Successfully</h3>
              <p className="text-sm text-zinc-400 mb-6">
                {mergedCustomers.length} customer{mergedCustomers.length > 1 ? 's' : ''} merged into {primaryCustomer.name || 'Primary Customer'}
              </p>
              <button
                onClick={handleClose}
                className="px-6 py-2 bg-violet-500 hover:bg-violet-600 rounded-lg text-sm font-medium text-white transition-colors"
              >
                Done
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
