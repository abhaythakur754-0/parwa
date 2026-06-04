/**
 * PARWA Voice Call Store (Zustand)
 *
 * Manages voice call state for the dashboard:
 * - Active calls (in-progress, ringing, queued)
 * - Call history
 * - Real-time updates via Socket.io call:* events
 * - API methods for making calls, ending calls, transferring
 */

import { create } from 'zustand';

// ── Types ────────────────────────────────────────────────────────────

export type CallDirection = 'inbound' | 'outbound';

export type CallStatus =
  | 'queued'
  | 'ringing'
  | 'in-progress'
  | 'completed'
  | 'failed'
  | 'busy'
  | 'no-answer'
  | 'canceled';

export interface VoiceCallItem {
  id: string;
  company_id: string;
  conversation_id?: string;
  ticket_id?: string;
  twilio_call_sid: string;
  twilio_account_sid?: string;
  direction: CallDirection;
  from_number: string;
  to_number: string;
  status: CallStatus;
  variant_tier: string;
  intent_detected?: string;
  resolution?: string;
  duration_seconds: number;
  started_at?: string;
  ended_at?: string;
  recording_url?: string;
  recording_sid?: string;
  recording_enabled: boolean;
  transcript_summary?: string;
  topics_discussed?: string;
  satisfaction_score?: number;
  sender_id?: string;
  sender_role: string;
  created_at: string;
  updated_at?: string;
}

interface CallStoreState {
  /** Active (non-terminal) calls */
  activeCalls: VoiceCallItem[];

  /** Recent call history */
  callHistory: VoiceCallItem[];

  /** Total history count for pagination */
  historyTotal: number;

  /** Current history page */
  historyPage: number;

  /** Total history pages */
  historyTotalPages: number;

  /** Currently selected call ID */
  selectedCallId: string | null;

  /** Loading state */
  isLoading: boolean;

  /** History loading state */
  isHistoryLoading: boolean;

  /** Error message */
  error: string | null;
}

interface CallStoreActions {
  // ── Real-time event handlers ──
  handleCallIncoming: (data: unknown) => void;
  handleCallOutgoing: (data: unknown) => void;
  handleCallStatus: (data: unknown) => void;
  handleCallEnded: (data: unknown) => void;

  // ── API Actions ──
  initiateCall: (to: string, variant?: string, message?: string) => Promise<VoiceCallItem | null>;
  endCall: (callId: string) => Promise<void>;
  transferCall: (callId: string, toNumber: string) => Promise<void>;
  refreshCalls: () => Promise<void>;
  refreshHistory: (page: number) => Promise<void>;
  setCurrentCall: (callId: string | null) => void;
  clearError: () => void;

  // ── Basic setters ──
  setActiveCalls: (calls: VoiceCallItem[]) => void;
  setCallHistory: (calls: VoiceCallItem[], total: number) => void;
  selectCall: (callId: string | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  // ── Computed helpers ──
  getActiveCall: (callId: string) => VoiceCallItem | undefined;
  getActiveCallBySid: (callSid: string) => VoiceCallItem | undefined;
}

type CallStore = CallStoreState & CallStoreActions;

// ── Helper ──────────────────────────────────────────────────────────

function isTerminalStatus(status: string): boolean {
  return ['completed', 'failed', 'busy', 'no-answer', 'canceled'].includes(status);
}

// ── Store ────────────────────────────────────────────────────────────

export const useCallStore = create<CallStore>((set, get) => ({
  activeCalls: [],
  callHistory: [],
  historyTotal: 0,
  historyPage: 1,
  historyTotalPages: 1,
  selectedCallId: null,
  isLoading: false,
  isHistoryLoading: false,
  error: null,

  // ── Real-time event handlers ──────────────────────────────────

  handleCallIncoming: (data: unknown) => {
    const call = data as Partial<VoiceCallItem>;
    if (!call?.twilio_call_sid) return;

    set((state) => {
      // Avoid duplicates
      const exists = state.activeCalls.some(
        (c) => c.twilio_call_sid === call.twilio_call_sid
      );
      if (exists) return state;

      const newCall: VoiceCallItem = {
        id: call.id || call.call_id || '',
        company_id: call.company_id || '',
        twilio_call_sid: call.twilio_call_sid || '',
        direction: 'inbound',
        from_number: call.from_number || '',
        to_number: call.to_number || '',
        status: 'ringing',
        variant_tier: call.variant_tier || 'parwa',
        duration_seconds: 0,
        recording_enabled: false,
        sender_role: 'visitor',
        created_at: new Date().toISOString(),
        ...call,
      };

      return {
        activeCalls: [newCall, ...state.activeCalls],
      };
    });
  },

  handleCallOutgoing: (data: unknown) => {
    const call = data as Partial<VoiceCallItem>;
    if (!call?.twilio_call_sid) return;

    set((state) => {
      // Avoid duplicates
      const exists = state.activeCalls.some(
        (c) => c.twilio_call_sid === call.twilio_call_sid
      );
      if (exists) return state;

      const newCall: VoiceCallItem = {
        id: call.id || call.call_id || '',
        company_id: call.company_id || '',
        twilio_call_sid: call.twilio_call_sid || '',
        direction: 'outbound',
        from_number: call.from_number || '',
        to_number: call.to_number || '',
        status: 'queued',
        variant_tier: call.variant_tier || 'parwa',
        duration_seconds: 0,
        recording_enabled: false,
        sender_role: call.sender_role || 'agent',
        created_at: new Date().toISOString(),
        ...call,
      };

      return {
        activeCalls: [newCall, ...state.activeCalls],
      };
    });
  },

  handleCallStatus: (data: unknown) => {
    const update = data as { call_sid?: string; status?: CallStatus; duration?: number; recording_url?: string; recording_sid?: string };
    if (!update?.call_sid) return;

    set((state) => {
      const updatedActive = state.activeCalls.map((call) => {
        if (call.twilio_call_sid === update.call_sid) {
          return {
            ...call,
            status: update.status || call.status,
            duration_seconds: update.duration ?? call.duration_seconds,
            recording_url: update.recording_url ?? call.recording_url,
            recording_sid: update.recording_sid ?? call.recording_sid,
            updated_at: new Date().toISOString(),
          };
        }
        return call;
      });

      // If status is terminal, move from active to history
      if (update.status && isTerminalStatus(update.status)) {
        const terminalCalls = updatedActive.filter(
          (c) => c.twilio_call_sid === update.call_sid
        );
        const remaining = updatedActive.filter(
          (c) => c.twilio_call_sid !== update.call_sid
        );

        return {
          activeCalls: remaining,
          callHistory: [...terminalCalls, ...state.callHistory],
        };
      }

      return { activeCalls: updatedActive };
    });
  },

  handleCallEnded: (data: unknown) => {
    const update = data as { call_sid?: string; status?: CallStatus; duration?: number; ended_by?: string };
    if (!update?.call_sid) return;

    set((state) => {
      const endedCalls = state.activeCalls.filter(
        (c) => c.twilio_call_sid === update.call_sid
      );
      const remaining = state.activeCalls.filter(
        (c) => c.twilio_call_sid !== update.call_sid
      );

      const updatedEnded = endedCalls.map((call) => ({
        ...call,
        status: (update.status || 'completed') as CallStatus,
        duration_seconds: update.duration ?? call.duration_seconds,
        ended_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }));

      return {
        activeCalls: remaining,
        callHistory: [...updatedEnded, ...state.callHistory],
      };
    });
  },

  // ── API Actions ───────────────────────────────────────────────

  initiateCall: async (to: string, variant?: string, message?: string) => {
    try {
      set({ isLoading: true, error: null });
      const { voiceApi } = await import('@/lib/voice-api');
      const result = await voiceApi.initiateCall({
        to_number: to,
        variant_tier: variant || 'parwa',
        message: message,
      });

      const newCall: VoiceCallItem = {
        id: result.id || '',
        company_id: '',
        twilio_call_sid: result.twilio_call_sid || '',
        direction: 'outbound',
        from_number: result.from_number || '',
        to_number: result.to_number || to,
        status: 'queued',
        variant_tier: variant || 'parwa',
        duration_seconds: 0,
        recording_enabled: false,
        sender_role: 'agent',
        created_at: new Date().toISOString(),
      };

      set((state) => ({
        activeCalls: [newCall, ...state.activeCalls],
        isLoading: false,
      }));

      return newCall;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to initiate call';
      set({ isLoading: false, error: msg });
      return null;
    }
  },

  endCall: async (callId: string) => {
    try {
      const { voiceApi } = await import('@/lib/voice-api');
      await voiceApi.endCall(callId);

      set((state) => {
        const ended = state.activeCalls.filter((c) => c.id === callId);
        const remaining = state.activeCalls.filter((c) => c.id !== callId);
        const updated = ended.map((c) => ({
          ...c,
          status: 'completed' as CallStatus,
          ended_at: new Date().toISOString(),
        }));

        return {
          activeCalls: remaining,
          callHistory: [...updated, ...state.callHistory],
        };
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to end call';
      set({ error: msg });
    }
  },

  transferCall: async (callId: string, toNumber: string) => {
    try {
      const { voiceApi } = await import('@/lib/voice-api');
      await voiceApi.transferCall(callId, { to_number: toNumber });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to transfer call';
      set({ error: msg });
    }
  },

  refreshCalls: async () => {
    try {
      set({ isLoading: true });
      const { voiceApi } = await import('@/lib/voice-api');
      const result = await voiceApi.listCalls({ status: 'in-progress' });

      const items = (result as { items?: VoiceCallItem[]; calls?: VoiceCallItem[] }).items
        || (result as { items?: VoiceCallItem[]; calls?: VoiceCallItem[] }).calls
        || [];

      // Also get queued and ringing
      const queued = await voiceApi.listCalls({ status: 'queued' });
      const ringing = await voiceApi.listCalls({ status: 'ringing' });

      const queuedItems = (queued as { items?: VoiceCallItem[] }).items || [];
      const ringingItems = (ringing as { items?: VoiceCallItem[] }).items || [];

      set({
        activeCalls: [...items, ...queuedItems, ...ringingItems],
        isLoading: false,
      });
    } catch (err) {
      set({ isLoading: false });
    }
  },

  refreshHistory: async (page: number) => {
    try {
      set({ isHistoryLoading: true });
      const { voiceApi } = await import('@/lib/voice-api');
      const result = await voiceApi.getHistory({ page, page_size: 20 });

      const items = (result as { items?: VoiceCallItem[]; total?: number; total_pages?: number }).items || [];
      const total = (result as { total?: number }).total || 0;
      const totalPages = (result as { total_pages?: number }).total_pages || 1;

      set({
        callHistory: items,
        historyTotal: total,
        historyPage: page,
        historyTotalPages: totalPages,
        isHistoryLoading: false,
      });
    } catch (err) {
      set({ isHistoryLoading: false });
    }
  },

  setCurrentCall: (callId: string | null) => set({ selectedCallId: callId }),

  clearError: () => set({ error: null }),

  // ── Basic setters ─────────────────────────────────────────────

  setActiveCalls: (calls) => set({ activeCalls: calls }),

  setCallHistory: (calls, total) => set({ callHistory: calls, historyTotal: total }),

  selectCall: (callId) => set({ selectedCallId: callId }),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),

  // ── Computed helpers ──────────────────────────────────────────

  getActiveCall: (callId) => {
    return get().activeCalls.find((c) => c.id === callId);
  },

  getActiveCallBySid: (callSid) => {
    return get().activeCalls.find((c) => c.twilio_call_sid === callSid);
  },
}));

export default useCallStore;
