/**
 * PARWA useJarvisChat Hook (Week 6 — Day 2 Phase 4)
 *
 * React hook managing all Jarvis onboarding chat state.
 * Single source of truth for the chat UI.
 *
 * State:
 *   - messages, session, loading/typing states
 *   - Flow states: otp, payment, handoff, demo call
 *   - Error state
 *
 * Actions:
 *   - initSession(), sendMessage(), retryLastMessage()
 *   - updateContext(), sendOtp(), verifyOtp()
 *   - purchaseDemoPack(), createPayment()
 *   - initiateDemoCall(), executeHandoff()
 *   - clearError()
 *
 * Based on: JARVIS_SPECIFICATION.md v3.0 / JARVIS_ROADMAP.md v4.0
 */

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  JarvisSession,
  JarvisMessage,
  JarvisContext,
  JarvisHistoryResponse,
  JarvisSessionCreateRequest,
  JarvisMessageSendRequest,
  JarvisContextUpdateRequest,
  JarvisEntryContextRequest,
  JarvisOtpRequest,
  JarvisOtpVerifyRequest,
  JarvisPaymentCreateRequest,
  JarvisPaymentCreateResponse,
  JarvisDemoCallRequest,
  JarvisActionTicketCreateRequest,
  JarvisActionTicketUpdateStatusRequest,
  OtpState,
  PaymentState,
  HandoffState,
  DemoCallState,
  MessageType,
  ParwaApiError,
  JarvisPurchaseResponse,
  JarvisDemoPackStatusResponse,
  JarvisDemoCallInitiateResponse,
  JarvisHandoffStatusResponse,
  VariantSelection,
  EntrySource,
} from '@/types/jarvis';

// ── Constants ─────────────────────────────────────────────────────

const DEFAULT_OTP_STATE: OtpState = {
  status: 'idle',
  email: '',
  attempts: 0,
  expires_at: null,
};

const DEFAULT_PAYMENT_STATE: PaymentState = {
  status: 'idle',
  paddle_url: null,
  error: null,
};

const DEFAULT_HANDOFF_STATE: HandoffState = {
  status: 'idle',
  new_session_id: null,
};

const DEFAULT_DEMO_CALL_STATE: DemoCallState = {
  status: 'idle',
  phone: null,
  duration: 0,
};

// ── API Helper ────────────────────────────────────────────────────

const API_BASE = '/api/jarvis';

async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };

  // Add auth token if available
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('parwa_access_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      (errorData as ParwaApiError)?.error?.message ||
        `API error: ${response.status}`,
    );
  }

  return response.json() as Promise<T>;
}

// ── Hook ──────────────────────────────────────────────────────────

export function useJarvisChat(entrySource?: string, entryParams?: Record<string, unknown>) {
  // ── State ───────────────────────────────────────────────────────

  const [messages, setMessages] = useState<JarvisMessage[]>([]);
  const [session, setSession] = useState<JarvisSession | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Flow states
  const [otpState, setOtpState] = useState<OtpState>(DEFAULT_OTP_STATE);
  const [paymentState, setPaymentState] = useState<PaymentState>(DEFAULT_PAYMENT_STATE);
  const [handoffState, setHandoffState] = useState<HandoffState>(DEFAULT_HANDOFF_STATE);
  const [demoCallState, setDemoCallState] = useState<DemoCallState>(DEFAULT_DEMO_CALL_STATE);

  // Refs
  const sessionRef = useRef<string | null>(null);
  const initCalledRef = useRef(false);
  const initFailedRef = useRef(false);
  const isSendingRef = useRef(false);
  const msgCounterRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  // ── Computed Values ─────────────────────────────────────────────

  const remainingToday = session?.remaining_today ?? 20;
  const isLimitReached = remainingToday <= 0;
  const isDemoPackActive = session?.pack_type === 'demo';

  // ── Init Session ────────────────────────────────────────────────

  const initSession = useCallback(async () => {
    if (initCalledRef.current && !initFailedRef.current) return;
    initCalledRef.current = true;
    initFailedRef.current = false;

    setIsLoading(true);
    setError(null);

    try {
      const body: JarvisSessionCreateRequest = {
        entry_source: (entrySource as EntrySource) || 'direct',
        entry_params: entryParams,
      };

      const sessionData = await apiFetch<JarvisSession>('/session', {
        method: 'POST',
        body: JSON.stringify(body),
      });

      sessionRef.current = sessionData.id;
      setSession(sessionData);

      // Load history
      const history = await apiFetch<JarvisHistoryResponse>(
        `/history?session_id=${sessionData.id}&limit=100`,
      );

      setMessages(history.messages || []);

      // Restore OTP state from context if present
      const ctx = sessionData.context as JarvisContext;
      if (ctx?.otp?.status === 'sent') {
        setOtpState({
          status: 'sent',
          email: ctx.otp.email || ctx.business_email || '',
          attempts: ctx.otp.attempts || 0,
          expires_at: ctx.otp.expires_at || null,
        });
      } else if (ctx?.email_verified) {
        setOtpState((prev) => ({ ...prev, status: 'verified' }));
      }

      // ── Phase 9: Cross-Page Context Bridge ──────────────────────
      // Read pricing/ROI context from localStorage (set by pricing page)
      if (typeof window !== 'undefined') {
        try {
          const storedContext = localStorage.getItem('parwa_jarvis_context');
          if (storedContext) {
            const bridgedContext = JSON.parse(storedContext) as Record<string, unknown>;
            // Transfer pricing selection into session context via API
            const contextPatch: Partial<JarvisContext> = {};
            if (bridgedContext.industry) {
              contextPatch.industry = bridgedContext.industry as string;
            }
            if (bridgedContext.selected_variants) {
              contextPatch.selected_variants = bridgedContext.selected_variants as VariantSelection[];
            }
            if (bridgedContext.total_price) {
              contextPatch.total_price = bridgedContext.total_price as number;
            }
            if (bridgedContext.source) {
              contextPatch.referral_source = bridgedContext.source as string;
            }
            if (bridgedContext.roi_result) {
              contextPatch.roi_result = bridgedContext.roi_result as JarvisContext['roi_result'];
            }
            // Push context to backend
            const hasPatch = Object.keys(contextPatch).length > 0;
            if (hasPatch) {
              await apiFetch<JarvisSession>(
                `/context?session_id=${sessionData.id}`,
                { method: 'PATCH', body: JSON.stringify(contextPatch) },
              );
              // Update local session state
              setSession((prev) => {
                if (!prev) return prev;
                return { ...prev, context: { ...prev.context, ...contextPatch } };
              });
            }
            // One-time transfer — clear after reading
            localStorage.removeItem('parwa_jarvis_context');
          }

          // Track pages visited for context awareness
          const visitedRaw = localStorage.getItem('parwa_pages_visited');
          const visited: string[] = visitedRaw ? JSON.parse(visitedRaw) : [];
          if (visited.length > 0) {
            await apiFetch<JarvisSession>(
              `/context?session_id=${sessionData.id}`,
              { method: 'PATCH', body: JSON.stringify({ pages_visited: visited } as Partial<JarvisContext>) },
            ).catch(() => { /* non-critical */ });
          }
        } catch {
          // Non-critical — localStorage bridge failure
        }
      }
    } catch (err) {
      initFailedRef.current = true;
      setError(err instanceof Error ? err.message : 'Failed to initialize session');
    } finally {
      setIsLoading(false);
    }
  }, [entrySource, entryParams]);

  // Auto-init on mount, abort on unmount
  useEffect(() => {
    initSession();
    return () => {
      abortRef.current?.abort();
    };
  }, [initSession]);

  // ── Send Message ────────────────────────────────────────────────

  const sendMessage = useCallback(
    async (content: string) => {
      if (isLimitReached) return;
      if (!content.trim()) return;
      if (!sessionRef.current) {
        setError('Session not ready. Please wait or reload.');
        return;
      }
      if (isSendingRef.current) return;
      isSendingRef.current = true;

      setError(null);
      setIsTyping(true);

      const sessionId = sessionRef.current;
      const abortController = new AbortController();
      abortRef.current = abortController;
      const { signal } = abortController;

      // Optimistically add user message
      const optimisticUserMsg: JarvisMessage = {
        id: `temp_${Date.now()}_${++msgCounterRef.current}`,
        session_id: sessionId || '',
        role: 'user',
        content: content.trim(),
        message_type: 'text' as MessageType,
        metadata: {},
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimisticUserMsg]);

      try {
        const body: JarvisMessageSendRequest = {
          content: content.trim(),
          session_id: sessionId || undefined,
        };

        const aiMessage = await apiFetch<JarvisMessage>('/message', {
          method: 'POST',
          body: JSON.stringify(body),
          signal,
        });

        // Update session ref if new session was created
        if (aiMessage.session_id && !sessionRef.current) {
          sessionRef.current = aiMessage.session_id;
        }

        // Replace optimistic user message + add AI response
        setMessages((prev) => {
          const filtered = prev.filter((m) => m.id !== optimisticUserMsg.id);
          const realUserMsg: JarvisMessage = {
            ...optimisticUserMsg,
            id: `user_${Date.now()}`,
          };
          return [...filtered, realUserMsg, aiMessage];
        });

        // Refresh session for updated limits
        if (sessionId) {
          try {
            const updatedSession = await apiFetch<JarvisSession>(
              `/session?session_id=${sessionId}`,
            );
            setSession(updatedSession);
          } catch {
            // Non-critical — session state update failed
          }
        }
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Failed to send message');

        // Mark optimistic message as error
        setMessages((prev) =>
          prev.map((m) =>
            m.id === optimisticUserMsg.id
              ? { ...m, message_type: 'error' as MessageType }
              : m,
          ),
        );
      } finally {
        setIsTyping(false);
        isSendingRef.current = false;
      }
    },
    [isLimitReached],
  );

  // ── Retry Last Message ──────────────────────────────────────────

  const retryLastMessage = useCallback(async () => {
    // Find last user message that resulted in error
    const lastUserMsg = [...messages].reverse().find(
      (m) => m.role === 'user',
    );
    if (!lastUserMsg) return;

    // Remove the error message
    setMessages((prev) => {
      const lastIdx = prev.length - 1;
      if (lastIdx >= 0 && prev[lastIdx].message_type === 'error') {
        return prev.slice(0, -1);
      }
      // Also remove last user message (will be re-added by sendMessage)
      const userMsgIdx = prev.length - 1;
      if (userMsgIdx >= 0 && prev[userMsgIdx].role === 'user') {
        return prev.slice(0, -1);
      }
      return prev;
    });

    await sendMessage(lastUserMsg.content);
  }, [messages, sendMessage]);

  // ── Update Context ──────────────────────────────────────────────

  const updateContext = useCallback(
    async (partial: JarvisContextUpdateRequest) => {
      const sessionId = sessionRef.current;
      if (!sessionId) return;

      try {
        await apiFetch<JarvisSession>(
          `/context?session_id=${sessionId}`,
          {
            method: 'PATCH',
            body: JSON.stringify(partial),
          },
        );

        // Update local session state
        setSession((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            context: { ...prev.context, ...partial },
          };
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update context');
      }
    },
    [],
  );

  // ── OTP Flow ────────────────────────────────────────────────────

  const sendOtp = useCallback(async (email: string) => {
    const sessionId = sessionRef.current;
    if (!sessionId) return;

    setOtpState((prev) => ({ ...prev, status: 'sending', email }));
    setError(null);

    try {
      const body: JarvisOtpRequest = { email };
      const result = await apiFetch<{
        message: string;
        status: string;
        attempts_remaining: number | null;
        expires_at: string | null;
      }>(`/verify/send-otp?session_id=${sessionId}`, {
        method: 'POST',
        body: JSON.stringify(body),
      });

      setOtpState({
        status: 'sent',
        email,
        attempts: 0,
        expires_at: result.expires_at,
      });
    } catch (err) {
      setOtpState((prev) => ({ ...prev, status: 'error' }));
      setError(err instanceof Error ? err.message : 'Failed to send OTP');
    }
  }, []);

  const verifyOtp = useCallback(
    async (code: string): Promise<boolean> => {
      if (!code || code.trim().length < 4) {
        setError('Please enter a valid OTP code (at least 4 digits).');
        return false;
      }
      const sessionId = sessionRef.current;
      if (!sessionId) return false;

      setOtpState((prev) => ({ ...prev, status: 'verifying' }));
      setError(null);

      try {
        const body: JarvisOtpVerifyRequest = { code, email: otpState.email };
        const result = await apiFetch<{
          message: string;
          status: string;
          attempts_remaining: number | null;
        }>(`/verify/verify-otp?session_id=${sessionId}`, {
          method: 'POST',
          body: JSON.stringify(body),
        });

        if (result.status === 'verified') {
          setOtpState((prev) => ({
            ...prev,
            status: 'verified',
            attempts: prev.attempts + 1,
          }));

          // Update context
          setSession((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              context: { ...prev.context, email_verified: true },
            };
          });

          return true;
        }

        setOtpState((prev) => ({
          ...prev,
          status: 'sent', // Allow retry
          attempts: prev.attempts + 1,
        }));

        return false;
      } catch (err) {
        setOtpState((prev) => ({ ...prev, status: 'error' }));
        setError(err instanceof Error ? err.message : 'OTP verification failed');
        return false;
      }
    },
    [otpState.email],
  );

  // ── Demo Pack ───────────────────────────────────────────────────

  const purchaseDemoPack = useCallback(async () => {
    const sessionId = sessionRef.current;
    if (!sessionId) return;

    setError(null);

    try {
      const result = await apiFetch<JarvisPurchaseResponse>(
        `/demo-pack/purchase?session_id=${sessionId}`,
        { method: 'POST' },
      );

      // Refresh session
      const updatedSession = await apiFetch<JarvisSession>(
        `/session?session_id=${sessionId}`,
      );
      setSession(updatedSession);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to purchase demo pack',
      );
    }
  }, []);

  const getDemoPackStatus = useCallback(async () => {
    const sessionId = sessionRef.current;
    if (!sessionId) return;

    try {
      return await apiFetch<JarvisDemoPackStatusResponse>(
        `/demo-pack/status?session_id=${sessionId}`,
      );
    } catch {
      return null;
    }
  }, []);

  // ── Payment ─────────────────────────────────────────────────────

  const createPayment = useCallback(
    async (
      variants: VariantSelection[],
      industry: string,
    ): Promise<string | null> => {
      const sessionId = sessionRef.current;
      if (!sessionId) return null;

      setPaymentState({ status: 'processing', paddle_url: null, error: null });
      setError(null);

      try {
        const body: JarvisPaymentCreateRequest = { variants, industry };
        const result = await apiFetch<JarvisPaymentCreateResponse>(
          `/payment/create?session_id=${sessionId}`,
          { method: 'POST', body: JSON.stringify(body) },
        );

        setPaymentState({
          status: 'processing',
          paddle_url: result.checkout_url,
          error: null,
        });

        return result.checkout_url;
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Payment creation failed';
        setPaymentState({ status: 'failed', paddle_url: null, error: msg });
        setError(msg);
        return null;
      }
    },
    [],
  );

  // ── Demo Call ───────────────────────────────────────────────────

  const initiateDemoCall = useCallback(async (phone: string) => {
    const sessionId = sessionRef.current;
    if (!sessionId) return;

    setDemoCallState({ status: 'initiating', phone, duration: 0 });
    setError(null);

    try {
      const body: JarvisDemoCallRequest = { phone };
      const result = await apiFetch<JarvisDemoCallInitiateResponse>(
        `/demo-call/initiate?session_id=${sessionId}`,
        { method: 'POST', body: JSON.stringify(body) },
      );

      setDemoCallState({
        status: 'calling',
        phone,
        duration: result.duration_limit,
        call_id: result.call_id,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to initiate call';
      setDemoCallState((prev) => ({
        ...prev,
        status: 'failed',
      }));
      setError(msg);
    }
  }, []);

  // ── Handoff ─────────────────────────────────────────────────────

  const executeHandoff = useCallback(async () => {
    const sessionId = sessionRef.current;
    if (!sessionId) return;

    setHandoffState({ status: 'in_progress' });
    setError(null);

    try {
      const result = await apiFetch<JarvisHandoffStatusResponse>(
        `/handoff?session_id=${sessionId}`,
        { method: 'POST', body: JSON.stringify({}) },
      );

      setHandoffState({
        status: 'completed',
        new_session_id: result.new_session_id,
      });

      // Refresh session
      const updatedSession = await apiFetch<JarvisSession>(
        `/session?session_id=${sessionId}`,
      );
      setSession(updatedSession);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Handoff failed';
      setHandoffState((prev) => ({ ...prev, status: 'idle' }));
      setError(msg);
    }
  }, []);

  // ── Clear Error ─────────────────────────────────────────────────

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // ── Return Everything ───────────────────────────────────────────

  return {
    // State
    messages,
    session,
    isLoading,
    isTyping,
    remainingToday,
    isLimitReached,
    isDemoPackActive,
    otpState,
    paymentState,
    handoffState,
    demoCallState,
    error,

    // Actions
    initSession,
    sendMessage,
    retryLastMessage,
    updateContext,
    sendOtp,
    verifyOtp,
    purchaseDemoPack,
    getDemoPackStatus,
    createPayment,
    initiateDemoCall,
    executeHandoff,
    clearError,
  };
}

export default useJarvisChat;
