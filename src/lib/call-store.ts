/**
 * PARWA Call Store — Zustand State Management
 *
 * Manages real-time call state: active calls, history, current call detail.
 * Polls backend for status updates and supports WebSocket-driven updates.
 */

import { create } from 'zustand';
import { voiceApi } from '@/lib/voice-api';
import type { VoiceCall, CallStatus } from '@/types/voice';

// ── Store Interface ─────────────────────────────────────────────────

interface CallStore {
  // State
  activeCalls: VoiceCall[];
  callHistory: VoiceCall[];
  currentCall: VoiceCall | null;
  isLoading: boolean;
  isHistoryLoading: boolean;
  error: string | null;
  historyPage: number;
  historyTotal: number;
  historyTotalPages: number;

  // Actions
  initiateCall: (to: string, variant?: string, message?: string) => Promise<VoiceCall | null>;
  endCall: (id: string) => Promise<void>;
  transferCall: (id: string, to: string) => Promise<void>;
  refreshCalls: () => Promise<void>;
  refreshHistory: (page?: number) => Promise<void>;
  setCurrentCall: (call: VoiceCall | null) => void;
  clearError: () => void;

  // Real-time (WebSocket-driven)
  addCall: (call: VoiceCall) => void;
  updateCallStatus: (callSid: string, status: CallStatus) => void;
}

// ── Active Statuses ─────────────────────────────────────────────────

const ACTIVE_STATUSES: CallStatus[] = ['queued', 'ringing', 'in-progress'];

function isActiveCall(status: CallStatus): boolean {
  return ACTIVE_STATUSES.includes(status);
}

// ── Store ───────────────────────────────────────────────────────────

export const useCallStore = create<CallStore>((set, get) => ({
  activeCalls: [],
  callHistory: [],
  currentCall: null,
  isLoading: false,
  isHistoryLoading: false,
  error: null,
  historyPage: 1,
  historyTotal: 0,
  historyTotalPages: 1,

  // ── Initiate Call ────────────────────────────────────────────────

  initiateCall: async (to: string, variant?: string, message?: string) => {
    set({ isLoading: true, error: null });
    try {
      const result = await voiceApi.initiateCall({
        to_number: to,
        variant_tier: variant || 'parwa',
        message,
      });

      // Fetch the full call object
      const call = await voiceApi.getCall(result.id);
      set((state) => ({
        activeCalls: isActiveCall(call.status)
          ? [call, ...state.activeCalls]
          : state.activeCalls,
        isLoading: false,
      }));
      return call;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to initiate call';
      set({ error: message, isLoading: false });
      return null;
    }
  },

  // ── End Call ─────────────────────────────────────────────────────

  endCall: async (id: string) => {
    try {
      await voiceApi.endCall(id);
      // Move from active to history
      set((state) => ({
        activeCalls: state.activeCalls.filter((c) => c.id !== id),
      }));
      // Refresh to get updated status
      get().refreshCalls();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to end call';
      set({ error: message });
    }
  },

  // ── Transfer Call ────────────────────────────────────────────────

  transferCall: async (id: string, to: string) => {
    try {
      await voiceApi.transferCall(id, { to_number: to });
      // Refresh to get updated state
      get().refreshCalls();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to transfer call';
      set({ error: message });
    }
  },

  // ── Refresh Active Calls ─────────────────────────────────────────

  refreshCalls: async () => {
    try {
      const result = await voiceApi.listCalls({ page: 1, page_size: 50 });
      const active = result.calls.filter((c) => isActiveCall(c.status));
      set({ activeCalls: active });
    } catch (err) {
      console.error('[CallStore] Failed to refresh calls:', err);
    }
  },

  // ── Refresh Call History ─────────────────────────────────────────

  refreshHistory: async (page = 1) => {
    set({ isHistoryLoading: true });
    try {
      const result = await voiceApi.getHistory({ page, page_size: 20 });
      set({
        callHistory: result.calls,
        historyPage: result.page,
        historyTotal: result.total,
        historyTotalPages: result.total_pages,
        isHistoryLoading: false,
      });
    } catch (err) {
      console.error('[CallStore] Failed to refresh history:', err);
      set({ isHistoryLoading: false });
    }
  },

  // ── Set Current Call ─────────────────────────────────────────────

  setCurrentCall: (call: VoiceCall | null) => {
    set({ currentCall: call });
  },

  // ── Clear Error ──────────────────────────────────────────────────

  clearError: () => set({ error: null }),

  // ── Real-time: Add Call (from WebSocket) ─────────────────────────

  addCall: (call: VoiceCall) => {
    set((state) => ({
      activeCalls: isActiveCall(call.status)
        ? [call, ...state.activeCalls.filter((c) => c.id !== call.id)]
        : state.activeCalls,
    }));
  },

  // ── Real-time: Update Call Status (from WebSocket) ───────────────

  updateCallStatus: (callSid: string, status: CallStatus) => {
    set((state) => {
      const updatedActive = state.activeCalls.map((c) =>
        c.twilio_call_sid === callSid ? { ...c, status } : c
      );

      // If no longer active, move to history
      const stillActive = updatedActive.filter((c) => isActiveCall(c.status));
      const movedToHistory = updatedActive.filter((c) => !isActiveCall(c.status));

      return {
        activeCalls: stillActive,
        callHistory: [...movedToHistory, ...state.callHistory].slice(0, 50),
        currentCall:
          state.currentCall?.twilio_call_sid === callSid
            ? { ...state.currentCall, status }
            : state.currentCall,
      };
    });
  },
}));
