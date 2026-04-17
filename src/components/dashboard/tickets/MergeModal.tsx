'use client';

import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';

/**
 * MergeModal - Modal for merging duplicate tickets
 *
 * Features:
 * - Select primary ticket
 * - Preview merge impact
 * - Confirmation flow
 * - Success/error states
 */

export interface Ticket {
  id: string;
  subject: string;
  status: string;
  priority?: string;
  category?: string;
  created_at: string;
  customer_id?: string;
  assigned_to?: string;
  message_count?: number;
}

export interface MergePreview {
  primary_ticket: {
    id: string;
    subject: string;
    status: string;
    message_count: number;
  };
  tickets_to_merge: Array<{
    id: string;
    subject: string;
    status: string;
  }>;
  merge_summary: {
    messages_to_transfer: number;
    attachments_to_transfer: number;
    tickets_to_close: number;
  };
  can_merge: boolean;
  missing_ticket_ids: string[];
}

interface MergeModalProps {
  isOpen: boolean;
  onClose: () => void;
  tickets: Ticket[];
  onMerge: (primaryId: string, mergedIds: string[], reason: string) => Promise<void>;
  className?: string;
}

type MergeStep = 'select' | 'preview' | 'merging' | 'success' | 'error';

export default function MergeModal({
  isOpen,
  onClose,
  tickets,
  onMerge,
  className,
}: MergeModalProps) {
  const [selectedPrimary, setSelectedPrimary] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [step, setStep] = useState<MergeStep>('select');
  const [preview, setPreview] = useState<MergePreview | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setSelectedPrimary(null);
      setReason('');
      setStep('select');
      setPreview(null);
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSelectPrimary = (ticketId: string) => {
    setSelectedPrimary(ticketId === selectedPrimary ? null : ticketId);
  };

  const handleContinue = async () => {
    if (!selectedPrimary) return;

    setStep('preview');

    // Fetch merge preview
    const mergedIds = tickets.filter((t) => t.id !== selectedPrimary).map((t) => t.id);

    try {
      const response = await fetch('/api/tickets/export/merge-preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          primary_ticket_id: selectedPrimary,
          merged_ticket_ids: mergedIds,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setPreview(data);
      } else {
        // Use local preview if API fails
        const primary = tickets.find((t) => t.id === selectedPrimary);
        const toMerge = tickets.filter((t) => t.id !== selectedPrimary);

        setPreview({
          primary_ticket: {
            id: primary!.id,
            subject: primary!.subject,
            status: primary!.status,
            message_count: primary!.message_count || 0,
          },
          tickets_to_merge: toMerge.map((t) => ({
            id: t.id,
            subject: t.subject,
            status: t.status,
          })),
          merge_summary: {
            messages_to_transfer: toMerge.reduce((sum, t) => sum + (t.message_count || 0), 0),
            attachments_to_transfer: 0,
            tickets_to_close: toMerge.length,
          },
          can_merge: true,
          missing_ticket_ids: [],
        });
      }
    } catch (err) {
      setError('Failed to load merge preview');
      setStep('error');
    }
  };

  const handleMerge = async () => {
    if (!selectedPrimary) return;

    const mergedIds = tickets.filter((t) => t.id !== selectedPrimary).map((t) => t.id);

    setStep('merging');
    setError(null);

    try {
      await onMerge(selectedPrimary, mergedIds, reason);
      setStep('success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Merge failed');
      setStep('error');
    }
  };

  const handleClose = () => {
    onClose();
  };

  const primaryTicket = tickets.find((t) => t.id === selectedPrimary);
  const mergedTickets = tickets.filter((t) => t.id !== selectedPrimary);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={step === 'merging' ? undefined : handleClose}
      />

      {/* Modal */}
      <div className={cn(
        'relative w-full max-w-2xl bg-[#1A1A1A] rounded-xl border border-white/[0.06] shadow-2xl',
        className
      )}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/[0.06]">
          <h2 className="text-lg font-semibold text-white">Merge Tickets</h2>
          {step !== 'merging' && (
            <button
              onClick={handleClose}
              className="p-1 rounded hover:bg-white/[0.06] text-zinc-400 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Content */}
        <div className="p-4 max-h-[60vh] overflow-y-auto">
          {step === 'select' && (
            <>
              <p className="text-sm text-zinc-400 mb-4">
                Select the primary ticket (this ticket will be kept). Other tickets will be merged into it and closed.
              </p>

              {/* Ticket Cards */}
              <div className="space-y-2 mb-4">
                {tickets.map((ticket) => (
                  <button
                    key={ticket.id}
                    onClick={() => handleSelectPrimary(ticket.id)}
                    className={cn(
                      'w-full p-4 rounded-lg border text-left transition-all',
                      selectedPrimary === ticket.id
                        ? 'bg-violet-500/10 border-violet-500'
                        : 'bg-white/[0.02] border-white/[0.06] hover:border-white/[0.1]'
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs text-zinc-500">#{ticket.id.slice(0, 8)}</span>
                          <span className={cn(
                            'px-1.5 py-0.5 rounded text-[10px] font-medium',
                            ticket.status === 'open' && 'bg-amber-500/20 text-amber-400',
                            ticket.status === 'assigned' && 'bg-blue-500/20 text-blue-400',
                            ticket.status === 'in_progress' && 'bg-violet-500/20 text-violet-400',
                            ticket.status === 'resolved' && 'bg-emerald-500/20 text-emerald-400',
                          )}>
                            {ticket.status}
                          </span>
                          {ticket.priority && (
                            <span className={cn(
                              'px-1.5 py-0.5 rounded text-[10px] font-medium',
                              ticket.priority === 'urgent' && 'bg-red-500/20 text-red-400',
                              ticket.priority === 'high' && 'bg-orange-500/20 text-orange-400',
                              ticket.priority === 'normal' && 'bg-zinc-500/20 text-zinc-400',
                            )}>
                              {ticket.priority}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-white truncate">{ticket.subject}</p>
                        <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
                          {ticket.message_count !== undefined && (
                            <span>{ticket.message_count} messages</span>
                          )}
                          <span>Created {new Date(ticket.created_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                      {selectedPrimary === ticket.id && (
                        <div className="ml-2 shrink-0">
                          <svg className="w-5 h-5 text-violet-400" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm3.857-9.809a.75.75 0 0 0-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 1 0-1.06 1.061l2.5 2.5a.75.75 0 0 0 1.137-.089l4-5.5Z" clipRule="evenodd" />
                          </svg>
                        </div>
                      )}
                    </div>
                  </button>
                ))}
              </div>

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

          {(step === 'preview' || step === 'merging') && preview && (
            <>
              <div className="mb-4 p-4 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <div className="flex items-center gap-2 mb-2">
                  <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                  </svg>
                  <span className="text-sm font-medium text-amber-400">Review Merge</span>
                </div>
                <p className="text-xs text-zinc-400">
                  This action cannot be undone. Merged tickets will be closed.
                </p>
              </div>

              {/* Merge Preview */}
              <div className="space-y-3 mb-4">
                <div className="p-3 rounded-lg bg-violet-500/10 border border-violet-500/20">
                  <p className="text-xs text-violet-400 uppercase tracking-wider mb-2">Primary Ticket (Kept)</p>
                  <p className="text-sm text-white font-medium">{preview.primary_ticket.subject}</p>
                  <p className="text-xs text-zinc-500 mt-1">
                    #{preview.primary_ticket.id.slice(0, 8)} • {preview.primary_ticket.message_count} messages
                  </p>
                </div>

                <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20">
                  <p className="text-xs text-red-400 uppercase tracking-wider mb-2">
                    To Be Merged & Closed ({preview.tickets_to_merge.length})
                  </p>
                  <div className="space-y-1">
                    {preview.tickets_to_merge.map((t) => (
                      <div key={t.id} className="flex items-center justify-between text-sm">
                        <span className="text-zinc-300 truncate">{t.subject}</span>
                        <span className="text-xs text-zinc-500">#{t.id.slice(0, 8)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Summary */}
                <div className="grid grid-cols-3 gap-2">
                  <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] text-center">
                    <p className="text-lg font-semibold text-white">{preview.merge_summary.messages_to_transfer}</p>
                    <p className="text-xs text-zinc-500">Messages</p>
                  </div>
                  <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] text-center">
                    <p className="text-lg font-semibold text-white">{preview.merge_summary.attachments_to_transfer}</p>
                    <p className="text-xs text-zinc-500">Attachments</p>
                  </div>
                  <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] text-center">
                    <p className="text-lg font-semibold text-amber-400">{preview.merge_summary.tickets_to_close}</p>
                    <p className="text-xs text-zinc-500">To Close</p>
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
                  placeholder="e.g., Duplicate ticket from same customer"
                  className="w-full px-3 py-2 bg-white/[0.02] border border-white/[0.06] rounded-lg text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-violet-500"
                  disabled={step === 'merging'}
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
                  disabled={step === 'merging'}
                  className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white transition-colors disabled:opacity-50"
                >
                  Back
                </button>
                <button
                  onClick={handleMerge}
                  disabled={step === 'merging' || !preview.can_merge}
                  className={cn(
                    'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                    step === 'merging'
                      ? 'bg-zinc-700 text-zinc-400 cursor-not-allowed'
                      : 'bg-red-500 hover:bg-red-600 text-white'
                  )}
                >
                  {step === 'merging' ? 'Merging...' : 'Confirm Merge'}
                </button>
              </div>
            </>
          )}

          {step === 'success' && preview && (
            <div className="text-center py-6">
              <div className="w-16 h-16 mx-auto rounded-full bg-emerald-500/20 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">Tickets Merged Successfully</h3>
              <p className="text-sm text-zinc-400 mb-6">
                {preview.merge_summary.tickets_to_close} ticket{preview.merge_summary.tickets_to_close > 1 ? 's' : ''} merged into primary ticket
              </p>
              <button
                onClick={handleClose}
                className="px-6 py-2 bg-violet-500 hover:bg-violet-600 rounded-lg text-sm font-medium text-white transition-colors"
              >
                Done
              </button>
            </div>
          )}

          {step === 'error' && (
            <div className="text-center py-6">
              <div className="w-16 h-16 mx-auto rounded-full bg-red-500/20 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">Merge Failed</h3>
              <p className="text-sm text-zinc-400 mb-6">{error || 'An unexpected error occurred'}</p>
              <button
                onClick={handleClose}
                className="px-6 py-2 bg-zinc-700 hover:bg-zinc-600 rounded-lg text-sm font-medium text-white transition-colors"
              >
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
