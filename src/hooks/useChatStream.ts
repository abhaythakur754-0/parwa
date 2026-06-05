'use client';

/**
 * useChatStream — Real-Time Chat Streaming Hook (RT-005)
 * ======================================================
 * Replaces the aiStateStorePlaceholder in useRealtimeEvents with
 * a real Zustand store that consumes Socket.io ai:chunk events
 * for token-level streaming in chat UIs.
 *
 * Features:
 *   - Accumulates ai:chunk tokens into a streaming message
 *   - Tracks AI thinking state (ai:thinking events)
 *   - Handles draft-ready events (ai:draft_ready)
 *   - Shows confidence warnings (ai:confidence_low)
 *   - Falls back to HTTP when Socket.io is unavailable
 *   - Auto-resets stream on new request
 *
 * Phase 20: Real-Time Feature Completion
 */

import { create } from 'zustand';
import { useCallback, useEffect, useRef } from 'react';
import { socketClient } from '@/lib/socket-client';

// ── AI Streaming Store ────────────────────────────────────────────────

interface StreamingMessage {
  id: string;
  requestId: string;
  content: string;
  isComplete: boolean;
  startedAt: string;
  completedAt: string | null;
  confidence: number | null;
  ticketId: string | null;
}

interface AIStreamingState {
  // Current stream
  currentStream: StreamingMessage | null;
  isThinking: boolean;
  thinkingTicketId: string | null;
  draftReady: { content: string; ticketId?: string } | null;
  confidenceWarning: { confidence: number; ticketId?: string; reason?: string } | null;

  // History of completed streams (last 10)
  streamHistory: StreamingMessage[];

  // Actions
  startStream: (requestId: string, ticketId?: string) => void;
  appendChunk: (chunk: string, requestId?: string) => void;
  completeStream: (requestId?: string) => void;
  setThinking: (isThinking: boolean, ticketId?: string) => void;
  setDraftReady: (draft: { content: string; ticketId?: string }) => void;
  showConfidenceWarning: (info: { confidence: number; ticketId?: string; reason?: string }) => void;
  resetStream: () => void;
}

export const useAIStreamingStore = create<AIStreamingState>((set, get) => ({
  currentStream: null,
  isThinking: false,
  thinkingTicketId: null,
  draftReady: null,
  confidenceWarning: null,
  streamHistory: [],

  startStream: (requestId, ticketId) => {
    set({
      currentStream: {
        id: `stream_${Date.now()}`,
        requestId,
        content: '',
        isComplete: false,
        startedAt: new Date().toISOString(),
        completedAt: null,
        confidence: null,
        ticketId: ticketId || null,
      },
      isThinking: false,
      draftReady: null,
      confidenceWarning: null,
    });
  },

  appendChunk: (chunk, requestId) => {
    const stream = get().currentStream;
    if (!stream) {
      // Auto-start stream if chunk arrives without startStream
      set({
        currentStream: {
          id: `stream_${Date.now()}`,
          requestId: requestId || 'auto',
          content: chunk,
          isComplete: false,
          startedAt: new Date().toISOString(),
          completedAt: null,
          confidence: null,
          ticketId: null,
        },
      });
      return;
    }
    set({
      currentStream: {
        ...stream,
        content: stream.content + chunk,
      },
    });
  },

  completeStream: (requestId) => {
    const stream = get().currentStream;
    if (!stream) return;

    const completed: StreamingMessage = {
      ...stream,
      isComplete: true,
      completedAt: new Date().toISOString(),
    };

    set({
      currentStream: null,
      isThinking: false,
      streamHistory: [completed, ...get().streamHistory.slice(0, 9)],
    });
  },

  setThinking: (isThinking, ticketId) => {
    set({
      isThinking,
      thinkingTicketId: ticketId || null,
    });
  },

  setDraftReady: (draft) => {
    set({ draftReady: draft });
  },

  showConfidenceWarning: (info) => {
    set({ confidenceWarning: info });
  },

  resetStream: () => {
    set({
      currentStream: null,
      isThinking: false,
      thinkingTicketId: null,
      draftReady: null,
      confidenceWarning: null,
    });
  },
}));

// ── useChatStream Hook ────────────────────────────────────────────────

interface UseChatStreamOptions {
  /** Called when a streaming message is complete */
  onStreamComplete?: (content: string, ticketId?: string) => void;
  /** Called when AI is thinking */
  onThinkingChange?: (isThinking: boolean) => void;
  /** Called when a draft is ready for review */
  onDraftReady?: (draft: { content: string; ticketId?: string }) => void;
  /** Called when confidence is low */
  onConfidenceWarning?: (info: { confidence: number; ticketId?: string }) => void;
}

interface UseChatStreamReturn {
  /** Current streaming content (accumulates as ai:chunk events arrive) */
  streamingContent: string;
  /** Whether AI is currently thinking */
  isThinking: boolean;
  /** Whether a stream is active */
  isStreaming: boolean;
  /** Draft ready for review */
  draftReady: { content: string; ticketId?: string } | null;
  /** Confidence warning info */
  confidenceWarning: { confidence: number; ticketId?: string; reason?: string } | null;
  /** Start a new stream manually (usually auto-started by ai:chunk) */
  startStream: (requestId: string, ticketId?: string) => void;
  /** Complete the current stream manually */
  completeStream: () => void;
  /** Reset all streaming state */
  resetStream: () => void;
  /** Send a message via HTTP and track with streaming (fallback) */
  sendWithStreamTracking: <T>(
    httpFn: () => Promise<T>,
    requestId: string,
  ) => Promise<T>;
}

export function useChatStream(options: UseChatStreamOptions = {}): UseChatStreamReturn {
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Subscribe to AI streaming store
  const currentStream = useAIStreamingStore((s) => s.currentStream);
  const isThinking = useAIStreamingStore((s) => s.isThinking);
  const draftReady = useAIStreamingStore((s) => s.draftReady);
  const confidenceWarning = useAIStreamingStore((s) => s.confidenceWarning);

  // React to state changes with callbacks
  useEffect(() => {
    if (currentStream?.isComplete && currentStream.content) {
      options.onStreamComplete?.(currentStream.content, currentStream.ticketId || undefined);
    }
  }, [currentStream?.isComplete]);

  useEffect(() => {
    options.onThinkingChange?.(isThinking);
  }, [isThinking]);

  useEffect(() => {
    if (draftReady) {
      options.onDraftReady?.(draftReady);
    }
  }, [draftReady]);

  useEffect(() => {
    if (confidenceWarning) {
      options.onConfidenceWarning?.(confidenceWarning);
    }
  }, [confidenceWarning]);

  const startStream = useCallback((requestId: string, ticketId?: string) => {
    useAIStreamingStore.getState().startStream(requestId, ticketId);
  }, []);

  const completeStream = useCallback(() => {
    useAIStreamingStore.getState().completeStream();
  }, []);

  const resetStream = useCallback(() => {
    useAIStreamingStore.getState().resetStream();
  }, []);

  const sendWithStreamTracking = useCallback(
    async <T>(httpFn: () => Promise<T>, requestId: string): Promise<T> => {
      // Mark thinking state
      useAIStreamingStore.getState().setThinking(true);

      try {
        const result = await httpFn();
        // Stream complete (HTTP response arrived)
        useAIStreamingStore.getState().setThinking(false);
        return result;
      } catch (error) {
        useAIStreamingStore.getState().setThinking(false);
        throw error;
      }
    },
    [],
  );

  return {
    streamingContent: currentStream?.content || '',
    isThinking,
    isStreaming: currentStream !== null && !currentStream.isComplete,
    draftReady,
    confidenceWarning,
    startStream,
    completeStream,
    resetStream,
    sendWithStreamTracking,
  };
}

export default useChatStream;
