/**
 * PARWA useJarvisChat Hook (Week 6 — Day 2 Phase 4)
 *
 * React hook managing all Jarvis onboarding chat state.
 * Single source of truth for the chat UI.
 *
 * KEY ARCHITECTURE: Frontend is the source of truth.
 * Messages and message count are stored in localStorage.
 * Server sessions are ephemeral (may be lost on serverless cold starts).
 * Conversation history is sent with each API call so the AI always has context.
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

// ── localStorage Keys ─────────────────────────────────────────────
// Frontend is the source of truth. These persist across page navigations.

const LS_SESSION_ID = 'parwa_jarvis_session_id';
const LS_MESSAGES = 'parwa_jarvis_messages';
const LS_TOTAL_SENT = 'parwa_jarvis_total_sent'; // total user messages ever sent (for 20 limit)
const LS_ENTRY_PROCESSED = 'parwa_jarvis_entry_processed'; // last processed entry key

const FREE_MESSAGE_LIMIT = 20;

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

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
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

// ── localStorage Helpers ──────────────────────────────────────────

function lsGet<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback;
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) as T : fallback;
  } catch {
    return fallback;
  }
}

function lsSet(key: string, value: unknown): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // localStorage full or unavailable
  }
}

function lsRemove(key: string): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem(key);
  } catch {}
}

// ── Hook ──────────────────────────────────────────────────────────

export function useJarvisChat(entrySource?: string, entryParams?: Record<string, unknown>) {
  // ── State ───────────────────────────────────────────────────────

  const [messages, setMessages] = useState<JarvisMessage[]>([]);
  const [session, setSession] = useState<JarvisSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isTyping, setIsTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Total user messages sent across ALL sessions (tracked in localStorage)
  const [totalSent, setTotalSent] = useState(0);

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
  const entryProcessedRef = useRef<string>('');
  const sessionReadyRef = useRef(false);

  // ── Computed Values ─────────────────────────────────────────────

  const remainingToday = Math.max(0, FREE_MESSAGE_LIMIT - totalSent);
  const isLimitReached = remainingToday <= 0 && session?.pack_type !== 'demo';
  const isDemoPackActive = session?.pack_type === 'demo';

  // ── Load from localStorage immediately on mount ────────────────
  // This ensures the UI shows previous messages instantly, before any API calls.

  useEffect(() => {
    const storedMessages = lsGet<JarvisMessage[]>(LS_MESSAGES, []);
    const storedSent = lsGet<number>(LS_TOTAL_SENT, 0);
    const storedEntryKey = lsGet<string>(LS_ENTRY_PROCESSED, '');

    if (storedMessages.length > 0) {
      setMessages(storedMessages);
    }
    setTotalSent(storedSent);
    entryProcessedRef.current = storedEntryKey;
    setIsLoading(false); // Show UI immediately with cached data
  }, []);

  // ── Save messages to localStorage whenever they change ──────────

  useEffect(() => {
    if (messages.length > 0) {
      lsSet(LS_MESSAGES, messages);
    }
  }, [messages]);

  // ── Save totalSent to localStorage ──────────────────────────────

  useEffect(() => {
    lsSet(LS_TOTAL_SENT, totalSent);
  }, [totalSent]);

  // ── Init Session ────────────────────────────────────────────────

  const initSession = useCallback(async () => {
    if (initCalledRef.current && !initFailedRef.current) return;
    initCalledRef.current = true;
    initFailedRef.current = false;

    setIsLoading(true);
    setError(null);

    try {
      const storedSessionId = lsGet<string | null>(LS_SESSION_ID, null);
      const storedMessages = lsGet<JarvisMessage[]>(LS_MESSAGES, []);
      const storedSent = lsGet<number>(LS_TOTAL_SENT, 0);
      const hasExistingChat = storedMessages.length > 0;

      // Build entry key to detect if entry context changed
      const currentEntryKey = `${entrySource || 'direct'}_${JSON.stringify(entryParams || {})}`;
      const entryChanged = currentEntryKey !== entryProcessedRef.current && currentEntryKey !== 'direct_{}';

      // ── Try to resume existing server session ──
      if (storedSessionId) {
        try {
          const existingSession = await apiFetch<JarvisSession>(`/session?session_id=${storedSessionId}`);
          if (existingSession && existingSession.is_active) {
            sessionRef.current = existingSession.id;
            sessionReadyRef.current = true;
            setSession(existingSession);

            // Load history from server
            const history = await apiFetch<JarvisHistoryResponse>(`/history?session_id=${existingSession.id}&limit=100`);
            const serverMessages = history.messages || [];

            // Use whichever has more messages (server or local)
            if (serverMessages.length > storedMessages.length) {
              setMessages(serverMessages);
            }
            // If local has more (server lost some), keep local

            // Restore OTP state from context if present
            const ctx = existingSession.context as JarvisContext;
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

            // ── Handle entry context change (e.g. user came from Free Demo) ──
            if (entryChanged && (entrySource?.includes('models_') || entrySource === 'models_page' || entrySource === 'free_chat')) {
              await handleEntryContextUpdate(existingSession.id, entrySource, entryParams, hasExistingChat);
              entryProcessedRef.current = currentEntryKey;
              lsSet(LS_ENTRY_PROCESSED, currentEntryKey);
            }

            setIsLoading(false);
            return; // Session resumed successfully
          }
        } catch {
          // Server session expired/unavailable — will create new below
        }
      }

      // ── No existing server session — create new one ──
      const body: Record<string, unknown> = {
        entry_source: (entrySource as EntrySource) || 'direct',
        entry_params: entryParams,
      };

      // If we have existing chat messages locally, tell server to skip welcome
      // and provide the previous messages so the AI has context
      if (hasExistingChat) {
        body.skip_welcome = true;
        body.previous_messages = storedMessages.slice(-30); // Send last 30 messages for context
        body.total_sent = storedSent;
      }

      const sessionData = await apiFetch<JarvisSession>('/session', {
        method: 'POST',
        body: JSON.stringify(body),
      });

      sessionRef.current = sessionData.id;
      sessionReadyRef.current = true;
      setSession(sessionData);

      // Save session ID to localStorage
      lsSet(LS_SESSION_ID, sessionData.id);

      // If server returned welcome messages and we DON'T have local messages, use server's
      if (!hasExistingChat && sessionData.messages?.length > 0) {
        setMessages(sessionData.messages as JarvisMessage[]);
      }
      // If we have local messages, keep them (server session is just for API compatibility)

      // If this is a Free Demo entry with existing chat, trigger contextual message
      if (hasExistingChat && (entrySource?.includes('models_') || entrySource === 'free_chat')) {
        await handleEntryContextUpdate(sessionData.id, entrySource, entryParams, true);
      }

      entryProcessedRef.current = currentEntryKey;
      lsSet(LS_ENTRY_PROCESSED, currentEntryKey);

      // ── Cross-Page Context Bridge ──────────────────────────────
      // Read pricing/ROI context from localStorage (set by pricing page)
      const storedContext = lsGet<Record<string, unknown>>('parwa_jarvis_context', null);
      if (storedContext) {
        const contextPatch: Partial<JarvisContext> = {};
        if (storedContext.industry) contextPatch.industry = storedContext.industry as string;
        if (storedContext.selected_variants) contextPatch.selected_variants = storedContext.selected_variants as VariantSelection[];
        if (storedContext.total_price) contextPatch.total_price = storedContext.total_price as number;
        if (storedContext.source) contextPatch.referral_source = storedContext.source as string;
        if (storedContext.roi_result) contextPatch.roi_result = storedContext.roi_result as JarvisContext['roi_result'];
        if (storedContext.variant) contextPatch.variant = storedContext.variant as string;
        if (storedContext.variant_id) contextPatch.variant_id = storedContext.variant_id as string;
        if (storedContext.variant_tier) contextPatch.variant_tier = storedContext.variant_tier as string;
        if (storedContext.entry_source) contextPatch.entry_source = storedContext.entry_source as EntrySource;

        const hasPatch = Object.keys(contextPatch).length > 0;
        if (hasPatch) {
          try {
            await apiFetch<JarvisSession>(
              `/context?session_id=${sessionData.id}`,
              { method: 'PATCH', body: JSON.stringify(contextPatch) },
            );
            setSession((prev) => {
              if (!prev) return prev;
              return { ...prev, context: { ...prev.context, ...contextPatch } };
            });
          } catch {
            // Non-critical
          }
        }
      }
    } catch (err) {
      initFailedRef.current = true;
      setError(err instanceof Error ? err.message : 'Failed to initialize session');
    } finally {
      setIsLoading(false);
    }
  }, [entrySource, entryParams]);

  // ── Handle Entry Context Update ────────────────────────────────
  // When user enters from a different page (e.g. Free Demo),
  // update the session context and generate a contextual AI message.

  const handleEntryContextUpdate = useCallback(async (
    sessionId: string,
    source?: string,
    params?: Record<string, unknown>,
    hasExistingChat?: boolean,
  ) => {
    if (!source && !params) return;

    try {
      // First update the session context
      const contextPatch: Record<string, unknown> = {};
      if (source) contextPatch.entry_source = source;
      if (params) {
        for (const [k, v] of Object.entries(params)) {
          if (v !== null && v !== undefined) contextPatch[k] = v;
        }
      }

      try {
        await apiFetch<JarvisSession>(
          `/context?session_id=${sessionId}`,
          { method: 'PATCH', body: JSON.stringify(contextPatch) },
        );
        setSession((prev) => {
          if (!prev) return prev;
          return { ...prev, context: { ...prev.context, ...contextPatch } };
        });
      } catch {
        // Context update failed — still try entry endpoint
      }

      // If this is a Free Demo entry, generate a contextual AI message
      if (source?.includes('models_') || source === 'models_page' || source === 'free_chat') {
        try {
          const result = await apiFetch<{ session: JarvisSession; new_welcome: JarvisMessage }>(
            `/context/entry`,
            {
              method: 'POST',
              body: JSON.stringify({
                session_id: sessionId,
                entry_source: source,
                entry_params: params,
              }),
            },
          );

          if (result.new_welcome) {
            setMessages((prev) => [...prev, result.new_welcome]);
          }

          if (result.session) {
            setSession(result.session);
          }
        } catch {
          // Contextual message failed — non-critical
          // The user can still chat normally
        }
      }
    } catch {
      // Non-critical
    }
  }, []);

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
      if (!content.trim()) return;

      // Check limit using localStorage-tracked count
      if (isLimitReached && session?.pack_type !== 'demo') return;

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

      // Increment total sent count
      setTotalSent((prev) => prev + 1);

      try {
        // ── Send context AND recent messages with every request ──
        // This ensures the AI always has conversation history even if
        // the server session was lost/recreated
        const currentCtx = session?.context || {};
        const currentMessages = lsGet<JarvisMessage[]>(LS_MESSAGES, []);

        const body: Record<string, unknown> = {
          content: content.trim(),
          session_id: sessionId || undefined,
          ...(Object.keys(currentCtx).length > 0 ? { context: currentCtx } : {}),
          // Send recent messages for AI context (critical for serverless)
          recent_messages: currentMessages.slice(-20),
          total_sent: lsGet<number>(LS_TOTAL_SENT, 0),
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
            // Non-critical
          }
        }
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Failed to send message');

        // Decrement total sent on failure
        setTotalSent((prev) => Math.max(0, prev - 1));

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
    [isLimitReached, session?.context, session?.pack_type],
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
    totalSent,

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
