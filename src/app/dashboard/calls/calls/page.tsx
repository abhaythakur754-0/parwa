/**
 * PARWA Calls Dashboard Page
 *
 * Full-featured voice calls dashboard with:
 * - Active Calls Panel — Live call status cards
 * - Call Initiation — "Make Call" button → dialer dialog
 * - Call History Table — Paginated list of past calls
 * - Call Detail Drawer — Slide-out panel with transcript, recording, etc.
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { Phone, PhoneCall, Settings, Plus, RefreshCw, Loader2, PhoneOff as PhoneOffIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useCallStore } from '@/lib/call-store';
import { voiceApi } from '@/lib/voice-api';
import { ActiveCallCard } from '@/components/dashboard/ActiveCallCard';
import { MakeCallDialog } from '@/components/dashboard/MakeCallDialog';
import { CallDetailPanel } from '@/components/dashboard/CallDetailPanel';
import { CallHistoryRow } from '@/components/dashboard/CallHistoryRow';
import { VoiceConfigCard } from '@/components/dashboard/VoiceConfigCard';
import type { VoiceCall } from '@/types/voice';
import toast from 'react-hot-toast';

export default function CallsDashboardPage() {
  const {
    activeCalls,
    callHistory,
    isLoading,
    isHistoryLoading,
    error,
    historyPage,
    historyTotalPages,
    initiateCall,
    endCall,
    transferCall,
    refreshCalls,
    refreshHistory,
    setCurrentCall,
    clearError,
  } = useCallStore();

  const [makeCallOpen, setMakeCallOpen] = useState(false);
  const [detailCall, setDetailCall] = useState<VoiceCall | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [transferDialogId, setTransferDialogId] = useState<string | null>(null);
  const [transferNumber, setTransferNumber] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  // ── Load data on mount ────────────────────────────────────────────

  useEffect(() => {
    refreshCalls();
    refreshHistory(1);
  }, [refreshCalls, refreshHistory]);

  // ── Auto-refresh active calls every 10s ───────────────────────────

  useEffect(() => {
    const interval = setInterval(() => {
      if (activeCalls.length > 0) {
        refreshCalls();
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [activeCalls.length, refreshCalls]);

  // ── Show error toast ──────────────────────────────────────────────

  useEffect(() => {
    if (error) {
      toast.error(error);
      clearError();
    }
  }, [error, clearError]);

  // ── Handlers ──────────────────────────────────────────────────────

  const handleMakeCall = useCallback(async (to: string, variant?: string, message?: string) => {
    const call = await initiateCall(to, variant, message);
    if (call) {
      toast.success(`Calling ${to}...`);
    }
  }, [initiateCall]);

  const handleEndCall = useCallback(async (id: string) => {
    await endCall(id);
    toast.success('Call ended');
  }, [endCall]);

  const handleTransferClick = useCallback((id: string) => {
    setTransferDialogId(id);
    setTransferNumber('');
  }, []);

  const handleTransferConfirm = useCallback(async () => {
    if (!transferDialogId || !transferNumber) return;
    try {
      await transferCall(transferDialogId, transferNumber);
      toast.success(`Call transferred to ${transferNumber}`);
    } catch (err) {
      toast.error('Failed to transfer call');
    }
    setTransferDialogId(null);
    setTransferNumber('');
  }, [transferDialogId, transferNumber, transferCall]);

  const handleCallClick = useCallback((call: VoiceCall) => {
    setDetailCall(call);
    setDetailOpen(true);
  }, []);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([refreshCalls(), refreshHistory(historyPage)]);
    setRefreshing(false);
    toast.success('Refreshed');
  }, [refreshCalls, refreshHistory, historyPage]);

  const handlePageChange = useCallback((page: number) => {
    refreshHistory(page);
  }, [refreshHistory]);

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen jarvis-page-body">
      <div className="p-4 lg:p-6 xl:p-8 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center shadow-lg shadow-orange-500/20">
              <Phone className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Voice Calls</h1>
              <p className="text-sm text-zinc-500 mt-0.5">
                {activeCalls.length > 0
                  ? `${activeCalls.length} active call${activeCalls.length > 1 ? 's' : ''}`
                  : 'Manage AI-powered voice calls'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="w-9 h-9 rounded-lg flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-colors disabled:opacity-50"
              title="Refresh"
            >
              <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin')} />
            </button>
            <button
              onClick={() => setConfigOpen(true)}
              className="w-9 h-9 rounded-lg flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-colors"
              title="Voice Settings"
            >
              <Settings className="w-4 h-4" />
            </button>
            <button
              onClick={() => setMakeCallOpen(true)}
              className="flex items-center gap-2 h-9 px-4 rounded-lg bg-gradient-to-r from-orange-500 to-orange-600 text-sm text-white font-medium hover:from-orange-400 hover:to-orange-500 transition-all shadow-lg shadow-orange-500/20"
            >
              <Plus className="w-4 h-4" />
              Make Call
            </button>
          </div>
        </div>

        {/* Active Calls Section */}
        {activeCalls.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <PhoneCall className="w-4 h-4 text-emerald-400" />
              <h2 className="text-sm font-semibold text-white">
                Active Calls ({activeCalls.length})
              </h2>
              <span className="flex items-center gap-1 text-[10px] text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Live
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {activeCalls.map((call) => (
                <ActiveCallCard
                  key={call.id}
                  call={call}
                  onEnd={handleEndCall}
                  onTransfer={handleTransferClick}
                  onClick={handleCallClick}
                />
              ))}
            </div>
          </div>
        )}

        {/* Empty Active State */}
        {activeCalls.length === 0 && (
          <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-8 text-center">
            <div className="w-12 h-12 rounded-xl bg-white/[0.03] flex items-center justify-center mx-auto mb-3">
              <PhoneOffIcon className="w-6 h-6 text-zinc-600" />
            </div>
            <h3 className="text-sm font-medium text-zinc-400 mb-1">No Active Calls</h3>
            <p className="text-xs text-zinc-600 mb-4">
              Click &quot;Make Call&quot; to initiate an outbound AI voice call
            </p>
            <button
              onClick={() => setMakeCallOpen(true)}
              className="inline-flex items-center gap-2 h-9 px-4 rounded-lg bg-gradient-to-r from-orange-500 to-orange-600 text-sm text-white font-medium hover:from-orange-400 hover:to-orange-500 transition-all"
            >
              <Phone className="w-4 h-4" />
              Start a Call
            </button>
          </div>
        )}

        {/* Call History Section */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-white">Call History</h2>
            {isHistoryLoading && (
              <Loader2 className="w-4 h-4 animate-spin text-zinc-500" />
            )}
          </div>

          <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden">
            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th className="py-2.5 px-3 text-left text-[10px] font-medium text-zinc-600 uppercase tracking-wider w-12">↔</th>
                    <th className="py-2.5 px-3 text-left text-[10px] font-medium text-zinc-600 uppercase tracking-wider">Number</th>
                    <th className="py-2.5 px-3 text-left text-[10px] font-medium text-zinc-600 uppercase tracking-wider">Status</th>
                    <th className="py-2.5 px-3 text-left text-[10px] font-medium text-zinc-600 uppercase tracking-wider">Duration</th>
                    <th className="py-2.5 px-3 text-left text-[10px] font-medium text-zinc-600 uppercase tracking-wider hidden sm:table-cell">Intent</th>
                    <th className="py-2.5 px-3 text-left text-[10px] font-medium text-zinc-600 uppercase tracking-wider hidden md:table-cell">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {callHistory.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-10 text-center text-xs text-zinc-600">
                        No call history yet
                      </td>
                    </tr>
                  ) : (
                    callHistory.map((call) => (
                      <CallHistoryRow
                        key={call.id}
                        call={call}
                        onClick={handleCallClick}
                      />
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {historyTotalPages > 1 && (
              <div className="flex items-center justify-between p-3 border-t border-white/[0.04]">
                <span className="text-[10px] text-zinc-600">
                  Page {historyPage} of {historyTotalPages}
                </span>
                <div className="flex gap-1.5">
                  <button
                    onClick={() => handlePageChange(historyPage - 1)}
                    disabled={historyPage <= 1}
                    className="px-2.5 py-1 rounded text-[10px] text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] disabled:opacity-30 transition-colors"
                  >
                    Prev
                  </button>
                  <button
                    onClick={() => handlePageChange(historyPage + 1)}
                    disabled={historyPage >= historyTotalPages}
                    className="px-2.5 py-1 rounded text-[10px] text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] disabled:opacity-30 transition-colors"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Quick Info */}
        <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
          <div className="flex items-start gap-3">
            <span className="text-lg">📞</span>
            <div>
              <h4 className="text-xs font-semibold text-zinc-300">How Voice Calls Work</h4>
              <p className="text-[10px] text-zinc-500 mt-1 leading-relaxed">
                PARWA&apos;s AI agent handles calls autonomously — answering questions, resolving issues,
                and transferring to humans when needed. All calls are recorded and transcribed for quality.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Dialogs */}
      <MakeCallDialog
        open={makeCallOpen}
        onClose={() => setMakeCallOpen(false)}
        onCall={handleMakeCall}
        defaultNumber="+919652852014"
      />

      <CallDetailPanel
        call={detailCall}
        open={detailOpen}
        onClose={() => { setDetailOpen(false); setDetailCall(null); }}
      />

      <VoiceConfigCard
        open={configOpen}
        onClose={() => setConfigOpen(false)}
      />

      {/* Transfer Dialog */}
      {transferDialogId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setTransferDialogId(null)} />
          <div className="relative w-full max-w-sm mx-4 rounded-xl bg-[#1A1A1A] border border-white/[0.08] shadow-2xl p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Transfer Call</h3>
            <input
              type="tel"
              value={transferNumber}
              onChange={(e) => setTransferNumber(e.target.value)}
              placeholder="+919652852014"
              className="w-full h-10 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 mb-4"
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={() => setTransferDialogId(null)}
                className="flex-1 h-9 rounded-lg bg-white/[0.05] border border-white/[0.06] text-sm text-zinc-400 font-medium hover:bg-white/[0.08] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleTransferConfirm}
                disabled={!transferNumber}
                className="flex-1 h-9 rounded-lg bg-orange-500 text-sm text-white font-medium hover:bg-orange-600 transition-colors disabled:opacity-40"
              >
                Transfer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
