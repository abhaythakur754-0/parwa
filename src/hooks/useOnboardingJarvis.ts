/**
 * PARWA Onboarding Jarvis — Chat Hook
 *
 * Custom hook managing all onboarding chat state.
 * Wraps the onboarding-jarvis-api client with React state management.
 */

'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  OnboardingSession,
  OnboardingMessage,
  ConversationStage,
  OtpState,
  PaymentState,
  DemoCallState,
  MessageType,
} from '@/types/onboarding-jarvis';
import * as api from '@/lib/onboarding-jarvis-api';

const MAX_FREE_MESSAGES = 20;
const MAX_DEMO_MESSAGES = 500;

export function useOnboardingJarvis() {
  const [session, setSession] = useState<OnboardingSession | null>(null);
  const [messages, setMessages] = useState<OnboardingMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Flow states
  const [otpState, setOtpState] = useState<OtpState>({
    status: 'idle', email: '', attempts: 0, expires_at: null,
  });
  const [paymentState, setPaymentState] = useState<PaymentState>({
    status: 'idle', paddle_url: null, error: null,
  });
  const [demoCallState, setDemoCallState] = useState<DemoCallState>({
    status: 'idle', phone: null, duration: 0,
  });

  // Refs
  const abortRef = useRef<AbortController | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  // ── Derived state ──────────────────────────────────────────────

  const remainingToday = session?.remaining_today ?? MAX_FREE_MESSAGES;
  const isLimitReached = remainingToday <= 0;
  const isDemoPackActive = session?.pack_type === 'demo';
  const detectedStage: ConversationStage = session?.detected_stage ?? 'welcome';

  // ── Init session ───────────────────────────────────────────────

  const initSession = useCallback(async (
    entrySource = 'direct',
    entryParams?: Record<string, any>,
  ) => {
    setIsLoading(true);
    setError(null);
    try {
      const sess = await api.createOrResumeSession(entrySource, entryParams);
      setSession(sess);

      // Load history
      try {
        const hist = await api.getHistory(sess.session_id, 100, 0);
        const mapped: OnboardingMessage[] = hist.messages.map((m: any) => ({
          id: m.id,
          session_id: sess.session_id,
          role: m.role,
          content: m.content,
          message_type: m.message_type as MessageType,
          metadata: m.metadata || {},
          timestamp: m.timestamp || new Date().toISOString(),
        }));
        setMessages(mapped);
      } catch {
        // History load failure is non-fatal
      }
    } catch (e: any) {
      setError(e.message || 'Failed to create session');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ── Send message ───────────────────────────────────────────────

  const sendMessage = useCallback(async (content: string) => {
    if (!session || !content.trim()) return;
    if (isLimitReached) {
      setError('Daily message limit reached. Upgrade to Demo Pack for more messages.');
      return;
    }

    // Add user message optimistically
    const userMsg: OnboardingMessage = {
      id: `temp-${Date.now()}`,
      session_id: session.session_id,
      role: 'user',
      content: content.trim(),
      message_type: 'text',
      metadata: {},
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);
    setIsTyping(true);
    setError(null);

    try {
      const result = await api.sendMessage(session.session_id, content.trim());

      // Add Jarvis response
      const jarvisMsg: OnboardingMessage = {
        id: `jarvis-${Date.now()}`,
        session_id: session.session_id,
        role: 'jarvis',
        content: result.content,
        message_type: (result.card_type !== 'none' ? result.card_type : result.message_type) as MessageType,
        metadata: result.card_data || {},
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, jarvisMsg]);

      // Update session state
      setSession(prev => prev ? {
        ...prev,
        remaining_today: result.remaining_today,
        detected_stage: result.stage as ConversationStage,
        message_count_today: prev.message_count_today + 1,
        total_message_count: prev.total_message_count + 1,
      } : null);

      // Update flow states based on card type
      if (result.card_type === 'otp_card') {
        setOtpState(prev => ({ ...prev, status: 'sent', email: result.card_data?.email || '' }));
      } else if (result.card_type === 'payment_card') {
        if (result.card_data?.checkout_url) {
          setPaymentState({ status: 'success', paddle_url: result.card_data.checkout_url, error: null });
        }
      } else if (result.card_type === 'demo_call_card') {
        setDemoCallState(prev => ({
          ...prev,
          status: result.card_data?.call_phase === 'completed' ? 'completed' : 'booking',
          phone: result.card_data?.phone_number || prev.phone,
          duration: result.card_data?.duration_seconds || 0,
        }));
      } else if (result.card_type === 'handoff_card') {
        // Handoff completed
        setSession(prev => prev ? { ...prev, handoff_completed: true } : null);
      }
    } catch (e: any) {
      setError(e.message || 'Failed to get response');
    } finally {
      setIsTyping(false);
    }
  }, [session, isLimitReached]);

  // ── Retry last message ─────────────────────────────────────────

  const retryLastMessage = useCallback(async () => {
    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
    if (lastUserMsg) {
      // Remove last error message if any
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.role === 'jarvis' && last.message_type === 'error') {
          return prev.slice(0, -1);
        }
        return prev;
      });
      await sendMessage(lastUserMsg.content);
    }
  }, [messages, sendMessage]);

  // ── Update context ─────────────────────────────────────────────

  const updateContext = useCallback(async (updates: Record<string, any>) => {
    if (!session) return;
    try {
      const updated = await api.updateContext(session.session_id, updates);
      setSession(updated);
    } catch (e: any) {
      // Context update failure is non-fatal
      console.error('Context update failed:', e);
    }
  }, [session]);

  // ── OTP flow ───────────────────────────────────────────────────

  const sendOtp = useCallback(async (email: string) => {
    if (!session) return;
    setOtpState(prev => ({ ...prev, status: 'sending', email }));
    try {
      const result = await api.sendOtp(session.session_id, email);
      setOtpState(prev => ({
        ...prev,
        status: 'sent',
        attempts: result.attempts_remaining ?? 3,
        expires_at: result.expires_at ?? null,
      }));
    } catch (e: any) {
      setOtpState(prev => ({ ...prev, status: 'error' }));
      setError(e.message || 'Failed to send OTP');
    }
  }, [session]);

  const verifyOtp = useCallback(async (code: string) => {
    if (!session || !otpState.email) return false;
    setOtpState(prev => ({ ...prev, status: 'verifying' }));
    try {
      const result = await api.verifyOtp(session.session_id, otpState.email, code);
      if (result.status === 'verified') {
        setOtpState(prev => ({ ...prev, status: 'verified' }));
        setSession(prev => prev ? { ...prev, context: { ...prev.context, email_verified: true } } : null);
        return true;
      }
      setOtpState(prev => ({
        ...prev,
        status: 'error',
        attempts: result.attempts_remaining ?? 0,
      }));
      return false;
    } catch (e: any) {
      setOtpState(prev => ({ ...prev, status: 'error' }));
      setError(e.message || 'OTP verification failed');
      return false;
    }
  }, [session, otpState.email]);

  // ── Demo pack ──────────────────────────────────────────────────

  const purchaseDemoPack = useCallback(async () => {
    if (!session) return;
    try {
      await api.purchaseDemoPack(session.session_id);
      setSession(prev => prev ? {
        ...prev,
        pack_type: 'demo',
        remaining_today: MAX_DEMO_MESSAGES,
      } : null);
    } catch (e: any) {
      setError(e.message || 'Failed to purchase demo pack');
    }
  }, [session]);

  // ── Payment ────────────────────────────────────────────────────

  const createPayment = useCallback(async (
    planId: string,
    variantIds: string[],
    email: string,
  ): Promise<string | null> => {
    if (!session) return null;
    setPaymentState({ status: 'processing', paddle_url: null, error: null });
    try {
      const result = await api.createPayment(session.session_id, planId, variantIds, email);
      const url = result.checkout_url || result.data?.checkout_url || null;
      setPaymentState({ status: 'success', paddle_url: url, error: null });
      return url;
    } catch (e: any) {
      setPaymentState({ status: 'failed', paddle_url: null, error: e.message });
      return null;
    }
  }, [session]);

  // ── Demo call ──────────────────────────────────────────────────

  const initiateDemoCall = useCallback(async (phone: string) => {
    if (!session) return;
    setDemoCallState({ status: 'initiating', phone, duration: 0 });
    // The actual call initiation is handled through sendMessage
    // which the LLM routes to the call_agent
  }, [session]);

  // ── Handoff ────────────────────────────────────────────────────

  const executeHandoff = useCallback(async () => {
    if (!session) return;
    try {
      const result = await api.executeHandoff(session.session_id);
      if (result.handoff_completed) {
        setSession(prev => prev ? { ...prev, handoff_completed: true } : null);
      }
    } catch (e: any) {
      setError(e.message || 'Handoff failed');
    }
  }, [session]);

  // ── Clear error ────────────────────────────────────────────────

  const clearError = useCallback(() => setError(null), []);

  return {
    // State
    session,
    messages,
    isLoading,
    isTyping,
    remainingToday,
    isLimitReached,
    isDemoPackActive,
    otpState,
    paymentState,
    demoCallState,
    error,
    detectedStage,

    // Actions
    initSession,
    sendMessage,
    retryLastMessage,
    updateContext,
    sendOtp,
    verifyOtp,
    purchaseDemoPack,
    createPayment,
    initiateDemoCall,
    executeHandoff,
    clearError,
  };
}
