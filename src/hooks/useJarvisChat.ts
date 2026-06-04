/**
 * PARWA useJarvisChat Hook
 *
 * React hook managing all Jarvis chat state.
 *
 * ARCHITECTURE:
 *   - Messages are the PRIMARY source of truth, stored in localStorage
 *   - Server sessions are ephemeral (lost on serverless cold starts)
 *   - Conversation history is sent with each API call (RAG-lite)
 *   - Entry context is handled AFTER session is ready, not during init
 *
 * Flow:
 *   1. On mount: Load messages + count from localStorage SYNCHRONOUSLY
 *   2. Create or resume server session (async)
 *   3. When entrySource/entryParams change AFTER session is ready:
 *      - Send context to server
 *      - Generate contextual AI message if user came from Free Demo
 *   4. All messages saved to localStorage on every change
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
  MessageType,
  ParwaApiError,
  JarvisPurchaseResponse,
  JarvisDemoPackStatusResponse,
  JarvisDemoCallInitiateResponse,
  JarvisHandoffStatusResponse,
  VariantSelection,
  EntrySource,
  OtpState,
  PaymentState,
  HandoffState,
  DemoCallState,
} from '@/types/jarvis';

// ── Constants ─────────────────────────────────────────────────────

const FREE_MESSAGE_LIMIT = 20;

const DEFAULT_OTP_STATE: OtpState = { status: 'idle', email: '', attempts: 0, expires_at: null };
const DEFAULT_PAYMENT_STATE: PaymentState = { status: 'idle', paddle_url: null, error: null };
const DEFAULT_HANDOFF_STATE: HandoffState = { status: 'idle', new_session_id: null };
const DEFAULT_DEMO_CALL_STATE: DemoCallState = { status: 'idle', phone: null, duration: 0 };

// ── localStorage Keys ─────────────────────────────────────────────

const LS_SESSION_ID = 'parwa_jarvis_session_id';
const LS_MESSAGES = 'parwa_jarvis_messages';
const LS_TOTAL_SENT = 'parwa_jarvis_total_sent';
const LS_LAST_ENTRY = 'parwa_jarvis_last_entry';

// ── localStorage Helpers ──────────────────────────────────────────

function lsGet<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback;
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) as T : fallback;
  } catch { return fallback; }
}

function lsSet(key: string, value: unknown): void {
  if (typeof window === 'undefined') return;
  try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
}

// ── Synchronous localStorage readers (for useState initializers) ──

function readStoredMessages(): JarvisMessage[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(LS_MESSAGES);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function readStoredTotalSent(): number {
  if (typeof window === 'undefined') return 0;
  try {
    const raw = localStorage.getItem(LS_TOTAL_SENT);
    return raw ? parseInt(raw, 10) || 0 : 0;
  } catch { return 0; }
}

// ── API Helper ────────────────────────────────────────────────────

const API_BASE = '/api/jarvis';

async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };
  const response = await fetch(url, { ...options, headers, credentials: 'include' });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error((errorData as ParwaApiError)?.error?.message || `API error: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

// ── Hook ──────────────────────────────────────────────────────────

export function useJarvisChat(entrySource?: string, entryParams?: Record<string, unknown>) {
  // ── State — initialized SYNCHRONOUSLY from localStorage ────────
  // This prevents flash of empty state. Messages appear instantly.

  const [messages, setMessages] = useState<JarvisMessage[]>(() => readStoredMessages());
  const [totalSent, setTotalSent] = useState<number>(() => readStoredTotalSent());
  const [session, setSession] = useState<JarvisSession | null>(null);
  const [isLoading, setIsLoading] = useState(false); // Not loading — messages already from localStorage
  const [isTyping, setIsTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Flow states
  const [otpState, setOtpState] = useState<OtpState>(DEFAULT_OTP_STATE);
  const [paymentState, setPaymentState] = useState<PaymentState>(DEFAULT_PAYMENT_STATE);
  const [handoffState, setHandoffState] = useState<HandoffState>(DEFAULT_HANDOFF_STATE);
  const [demoCallState, setDemoCallState] = useState<DemoCallState>(DEFAULT_DEMO_CALL_STATE);

  // Refs
  const sessionRef = useRef<string | null>(null);
  const sessionReadyRef = useRef(false);
  const isSendingRef = useRef(false);
  const msgCounterRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const lastProcessedEntryRef = useRef<string>('');

  // ── Computed ─────────────────────────────────────────────────────

  const remainingToday = Math.max(0, FREE_MESSAGE_LIMIT - totalSent);
  const isLimitReached = remainingToday <= 0 && session?.pack_type !== 'demo';
  const isDemoPackActive = session?.pack_type === 'demo';

  // ── Save messages to localStorage on every change ────────────────

  useEffect(() => {
    if (messages.length > 0) {
      lsSet(LS_MESSAGES, messages);
    }
  }, [messages]);

  useEffect(() => {
    lsSet(LS_TOTAL_SENT, totalSent);
  }, [totalSent]);

  // ── Phase 1: Create or resume server session (runs ONCE) ────────

  const initSession = useCallback(async () => {
    // Only run once
    if (sessionReadyRef.current) return;

    setIsLoading(true);

    try {
      const storedSessionId = lsGet<string | null>(LS_SESSION_ID, null);
      const hasExistingChat = readStoredMessages().length > 0;

      // Try to resume existing server session
      if (storedSessionId) {
        try {
          const existingSession = await apiFetch<JarvisSession>(`/session?session_id=${storedSessionId}`);
          if (existingSession && existingSession.is_active) {
            sessionRef.current = existingSession.id;
            sessionReadyRef.current = true;
            setSession(existingSession);

            // Merge server messages with local (use whichever has more)
            const history = await apiFetch<JarvisHistoryResponse>(`/history?session_id=${existingSession.id}&limit=200`);
            const serverMessages = history.messages || [];
            setMessages(prev => {
              if (serverMessages.length > prev.length) return serverMessages;
              return prev; // Keep local if it has more
            });

            setIsLoading(false);
            return; // Session resumed!
          }
        } catch {
          // Server session expired — create new one below
        }
      }

      // Create new server session
      const hasMessages = readStoredMessages().length > 0;
      const body: Record<string, unknown> = {};

      // If we have existing messages locally, tell server to skip welcome
      // and seed with our messages so the AI has context
      if (hasMessages) {
        body.skip_welcome = true;
        body.previous_messages = readStoredMessages().slice(-50);
        body.total_sent = readStoredTotalSent();
      }

      const sessionData = await apiFetch<JarvisSession>('/session', {
        method: 'POST',
        body: JSON.stringify(body),
      });

      sessionRef.current = sessionData.id;
      sessionReadyRef.current = true;
      setSession(sessionData);
      lsSet(LS_SESSION_ID, sessionData.id);

      // If server returned a welcome message and we have NO local messages, use it
      if (!hasMessages && sessionData.messages?.length > 0) {
        setMessages(sessionData.messages as JarvisMessage[]);
      }

      setIsLoading(false);
    } catch (err) {
      sessionReadyRef.current = false;
      setError(err instanceof Error ? err.message : 'Failed to initialize session');
      setIsLoading(false);
    }
  }, []);

  // Run init once on mount
  useEffect(() => {
    initSession();
    return () => { abortRef.current?.abort(); };
  }, [initSession]);

  // ── Phase 2: Handle entry context changes (runs whenever entrySource/entryParams change) ──
  // This is SEPARATE from session init. It watches for entry context and
  // sends it to the server AFTER the session is ready.

  useEffect(() => {
    if (!sessionReadyRef.current || !sessionRef.current) return;
    if (!entrySource && !entryParams) return;

    // Build entry key to detect if this entry was already processed
    const entryKey = `${entrySource || 'none'}_${JSON.stringify(entryParams || {})}`;
    if (entryKey === lastProcessedEntryRef.current) return;
    if (entryKey === 'none_{}') return; // No real entry context

    lastProcessedEntryRef.current = entryKey;
    lsSet(LS_LAST_ENTRY, entryKey);

    const sessionId = sessionRef.current;
    const hasExistingChat = readStoredMessages().length > 0;
    const isVariantEntry = entrySource?.includes('models_') || entrySource === 'models_page' || entrySource === 'free_chat';

    // Update server session context with entry info
    const contextPatch: Record<string, unknown> = {};
    if (entrySource) contextPatch.entry_source = entrySource;
    if (entryParams) {
      for (const [k, v] of Object.entries(entryParams)) {
        if (v !== null && v !== undefined) contextPatch[k] = v;
      }
    }

    // Patch context on server
    apiFetch<JarvisSession>(`/context?session_id=${sessionId}`, {
      method: 'PATCH',
      body: JSON.stringify(contextPatch),
    }).then(updated => {
      setSession(updated);
    }).catch(() => {});

    // If user came from Free Demo / Models page, generate a contextual AI message
    if (isVariantEntry) {
      setIsTyping(true);
      apiFetch<{ session: JarvisSession; new_welcome: JarvisMessage }>('/context/entry', {
        method: 'POST',
        body: JSON.stringify({
          session_id: sessionId,
          entry_source: entrySource,
          entry_params: entryParams,
        }),
      }).then(result => {
        if (result.new_welcome) {
          setMessages(prev => [...prev, result.new_welcome]);
        }
        if (result.session) {
          setSession(result.session);
        }
      }).catch(() => {
        // Contextual message failed — non-critical
      }).finally(() => {
        setIsTyping(false);
      });
    }
  }, [entrySource, entryParams]);

  // ── Send Message ────────────────────────────────────────────────

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim()) return;
    if (isLimitReached && session?.pack_type !== 'demo') return;

    // If session isn't ready yet, wait a bit
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
    const { signal } = abortController.signal;

    // Optimistically add user message
    const tempId = `temp_${Date.now()}_${++msgCounterRef.current}`;
    const optimisticUserMsg: JarvisMessage = {
      id: tempId,
      session_id: sessionId || '',
      role: 'user',
      content: content.trim(),
      message_type: 'text' as MessageType,
      metadata: {},
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, optimisticUserMsg]);
    setTotalSent(prev => prev + 1);

    try {
      // Send context + recent messages with each request (RAG-lite)
      // This ensures the AI always has full conversation history
      const currentCtx = session?.context || {};
      const currentMessages = lsGet<JarvisMessage[]>(LS_MESSAGES, []);

      const body: Record<string, unknown> = {
        content: content.trim(),
        session_id: sessionId,
        context: currentCtx,
        // ── RAG-lite: Send full conversation history with each request ──
        // This gives the AI complete awareness of the entire conversation
        recent_messages: currentMessages.slice(-50),
        total_sent: lsGet<number>(LS_TOTAL_SENT, 0),
      };

      const aiMessage = await apiFetch<JarvisMessage>('/message', {
        method: 'POST',
        body: JSON.stringify(body),
        signal: abortController.signal,
      });

      // Replace optimistic user message + add AI response
      setMessages(prev => {
        const filtered = prev.filter(m => m.id !== tempId);
        const realUserMsg: JarvisMessage = {
          ...optimisticUserMsg,
          id: `user_${Date.now()}`,
        };
        return [...filtered, realUserMsg, aiMessage];
      });

      // Refresh session state
      try {
        const updatedSession = await apiFetch<JarvisSession>(`/session?session_id=${sessionId}`);
        setSession(updatedSession);
      } catch {}

    } catch (err) {
      if ((err as Error)?.name === 'AbortError') return;
      setError(err instanceof Error ? err.message : 'Failed to send message');
      setTotalSent(prev => Math.max(0, prev - 1));
      setMessages(prev =>
        prev.map(m => m.id === tempId ? { ...m, message_type: 'error' as MessageType } : m)
      );
    } finally {
      setIsTyping(false);
      isSendingRef.current = false;
    }
  }, [isLimitReached, session?.context, session?.pack_type]);

  // ── Retry Last Message ──────────────────────────────────────────

  const retryLastMessage = useCallback(async () => {
    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
    if (!lastUserMsg) return;
    setMessages(prev => {
      const lastIdx = prev.length - 1;
      if (lastIdx >= 0 && (prev[lastIdx].message_type === 'error' || prev[lastIdx].role === 'user')) {
        return prev.slice(0, -1);
      }
      return prev;
    });
    await sendMessage(lastUserMsg.content);
  }, [messages, sendMessage]);

  // ── Update Context ──────────────────────────────────────────────

  const updateContext = useCallback(async (partial: JarvisContextUpdateRequest) => {
    const sessionId = sessionRef.current;
    if (!sessionId) return;
    try {
      const updated = await apiFetch<JarvisSession>(`/context?session_id=${sessionId}`, {
        method: 'PATCH',
        body: JSON.stringify(partial),
      });
      setSession(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update context');
    }
  }, []);

  // ── OTP Flow ────────────────────────────────────────────────────

  const sendOtp = useCallback(async (email: string) => {
    const sessionId = sessionRef.current;
    if (!sessionId) return;
    setOtpState(prev => ({ ...prev, status: 'sending', email }));
    setError(null);
    try {
      const result = await apiFetch<{ message: string; status: string; attempts_remaining: number | null; expires_at: string | null }>(
        `/verify/send-otp?session_id=${sessionId}`,
        { method: 'POST', body: JSON.stringify({ email }) },
      );
      setOtpState({ status: 'sent', email, attempts: 0, expires_at: result.expires_at });
    } catch (err) {
      setOtpState(prev => ({ ...prev, status: 'error' }));
      setError(err instanceof Error ? err.message : 'Failed to send OTP');
    }
  }, []);

  const verifyOtp = useCallback(async (code: string): Promise<boolean> => {
    if (!code || code.trim().length < 4) { setError('Please enter a valid OTP code.'); return false; }
    const sessionId = sessionRef.current;
    if (!sessionId) return false;
    setOtpState(prev => ({ ...prev, status: 'verifying' }));
    setError(null);
    try {
      const result = await apiFetch<{ message: string; status: string; attempts_remaining: number | null }>(
        `/verify/verify-otp?session_id=${sessionId}`,
        { method: 'POST', body: JSON.stringify({ code, email: otpState.email }) },
      );
      if (result.status === 'verified') {
        setOtpState(prev => ({ ...prev, status: 'verified', attempts: prev.attempts + 1 }));
        setSession(prev => prev ? { ...prev, context: { ...prev.context, email_verified: true } } : prev);
        return true;
      }
      setOtpState(prev => ({ ...prev, status: 'sent', attempts: prev.attempts + 1 }));
      return false;
    } catch (err) {
      setOtpState(prev => ({ ...prev, status: 'error' }));
      setError(err instanceof Error ? err.message : 'OTP verification failed');
      return false;
    }
  }, [otpState.email]);

  // ── Demo Pack ───────────────────────────────────────────────────

  const purchaseDemoPack = useCallback(async () => {
    const sessionId = sessionRef.current;
    if (!sessionId) return;
    setError(null);
    try {
      await apiFetch<JarvisPurchaseResponse>(`/demo-pack/purchase?session_id=${sessionId}`, { method: 'POST' });
      const updatedSession = await apiFetch<JarvisSession>(`/session?session_id=${sessionId}`);
      setSession(updatedSession);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to purchase demo pack');
    }
  }, []);

  const getDemoPackStatus = useCallback(async () => {
    const sessionId = sessionRef.current;
    if (!sessionId) return null;
    try {
      return await apiFetch<JarvisDemoPackStatusResponse>(`/demo-pack/status?session_id=${sessionId}`);
    } catch { return null; }
  }, []);

  // ── Payment ─────────────────────────────────────────────────────

  const createPayment = useCallback(async (variants: VariantSelection[], industry: string): Promise<string | null> => {
    const sessionId = sessionRef.current;
    if (!sessionId) return null;
    setPaymentState({ status: 'processing', paddle_url: null, error: null });
    setError(null);
    try {
      const result = await apiFetch<JarvisPaymentCreateResponse>(
        `/payment/create?session_id=${sessionId}`,
        { method: 'POST', body: JSON.stringify({ variants, industry }) },
      );
      setPaymentState({ status: 'processing', paddle_url: result.checkout_url, error: null });
      return result.checkout_url;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Payment creation failed';
      setPaymentState({ status: 'failed', paddle_url: null, error: msg });
      setError(msg);
      return null;
    }
  }, []);

  // ── Demo Call ───────────────────────────────────────────────────

  const initiateDemoCall = useCallback(async (phone: string) => {
    const sessionId = sessionRef.current;
    if (!sessionId) return;
    setDemoCallState({ status: 'initiating', phone, duration: 0 });
    setError(null);
    try {
      const result = await apiFetch<JarvisDemoCallInitiateResponse>(
        `/demo-call/initiate?session_id=${sessionId}`,
        { method: 'POST', body: JSON.stringify({ phone }) },
      );
      setDemoCallState({ status: 'calling', phone, duration: result.duration_limit, call_id: result.call_id });
    } catch (err) {
      setDemoCallState(prev => ({ ...prev, status: 'failed' }));
      setError(err instanceof Error ? err.message : 'Failed to initiate call');
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
      setHandoffState({ status: 'completed', new_session_id: result.new_session_id });
      const updatedSession = await apiFetch<JarvisSession>(`/session?session_id=${sessionId}`);
      setSession(updatedSession);
    } catch (err) {
      setHandoffState(prev => ({ ...prev, status: 'idle' }));
      setError(err instanceof Error ? err.message : 'Handoff failed');
    }
  }, []);

  // ── Clear Error ─────────────────────────────────────────────────

  const clearError = useCallback(() => { setError(null); }, []);

  // ── Return ───────────────────────────────────────────────────────

  return {
    messages, session, isLoading, isTyping,
    remainingToday, isLimitReached, isDemoPackActive,
    otpState, paymentState, handoffState, demoCallState,
    error, totalSent,
    initSession, sendMessage, retryLastMessage, updateContext,
    sendOtp, verifyOtp, purchaseDemoPack, getDemoPackStatus,
    createPayment, initiateDemoCall, executeHandoff, clearError,
  };
}

export default useJarvisChat;
