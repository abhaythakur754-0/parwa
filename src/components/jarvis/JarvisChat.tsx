/**
 * PARWA JarvisChat — Main Container Component (Week 6 — Day 3 Phase 5)
 *
 * Root-level component that composes all chat sub-components and
 * manages the useJarvisChat hook. Acts as the single integration
 * point between the hook (state) and the UI (presentation).
 *
 * Responsibilities:
 *   - Calls useJarvisChat to manage all chat state
 *   - Composes ChatHeader, ErrorBanner, ChatWindow, ChatInput
 *   - Handles initial loading state
 *   - Wires up retry, clear error, and send message callbacks
 *   - Responsive layout (full-height on desktop, mobile-aware)
 */

'use client';

import { useMemo } from 'react';
import { Loader2, WifiOff } from 'lucide-react';
import { useJarvisChat } from '@/hooks/useJarvisChat';
import { ChatHeader } from './ChatHeader';
import { ChatWindow } from './ChatWindow';
import { ChatInput } from './ChatInput';
import { ErrorBanner } from './ErrorBanner';

interface JarvisChatProps {
  /** Entry source for analytics (e.g. 'pricing', 'demo', 'direct') */
  entrySource?: string;
  /** Additional entry parameters for context tracking */
  entryParams?: Record<string, unknown>;
}

export function JarvisChat({ entrySource, entryParams }: JarvisChatProps) {
  const {
    // State
    messages,
    session,
    isLoading,
    isTyping,
    remainingToday,
    isLimitReached,
    isDemoPackActive,
    error,

    // Actions
    sendMessage,
    retryLastMessage,
    clearError,
    sendOtp,
    verifyOtp,
    purchaseDemoPack,
    createPayment,
    initiateDemoCall,
    executeHandoff,
    otpState,
    paymentState,
    demoCallState,
    handoffState,
  } = useJarvisChat(entrySource, entryParams);

  // Memoize hookActions to prevent re-renders
  const hookActions = useMemo(() => ({
    sendOtp,
    verifyOtp,
    purchaseDemoPack,
    createPayment,
    initiateDemoCall,
    executeHandoff,
  }), [sendOtp, verifyOtp, purchaseDemoPack, createPayment, initiateDemoCall, executeHandoff]);

  const sessionState = useMemo(() => ({
    remainingToday,
    totalMessages: 20,
    isDemoPackActive,
    isHandoffComplete: handoffState.status === 'completed',
    paymentProcessing: paymentState.status === 'processing',
    otpState,
    demoCallState,
  }), [remainingToday, isDemoPackActive, handoffState.status, paymentState.status, otpState, demoCallState]);

  // ── Loading State ────────────────────────────────────────────

  if (isLoading && messages.length === 0) {
    return (
      <div className="h-dvh [height:100dvh] flex flex-col bg-[#1A1A1A]">
        <ChatHeader session={null} isLoading={true} />

        <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6">
          <div className="relative">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500/10 to-orange-600/10 border border-orange-500/15 flex items-center justify-center">
              <Loader2 className="w-8 h-8 animate-spin text-orange-400" />
            </div>
            {/* Pulse ring */}
            <div className="absolute inset-0 rounded-2xl border border-orange-500/20 animate-ping opacity-30" />
          </div>

          <div className="text-center">
            <p className="text-sm font-medium text-white/60 mb-1">
              Connecting to Jarvis
            </p>
            <p className="text-xs text-white/30">
              Setting up your onboarding session...
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ── Error State (failed to init) ─────────────────────────────

  if (error && messages.length === 0 && !session) {
    return (
      <div className="h-dvh [height:100dvh] flex flex-col bg-[#1A1A1A]">
        <ChatHeader session={null} isLoading={false} />

        <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6">
          <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/15 flex items-center justify-center">
            <WifiOff className="w-8 h-8 text-red-400/60" />
          </div>

          <div className="text-center max-w-sm">
            <p className="text-sm font-medium text-white/60 mb-1">
              Unable to connect
            </p>
            <p className="text-xs text-white/30 mb-4">{error}</p>

            <button
              onClick={() => window.location.reload()}
              className="text-xs text-orange-400 hover:text-orange-300 underline underline-offset-2 transition-colors"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Main Chat Layout ─────────────────────────────────────────

  return (
    <div className="h-dvh [height:100dvh] flex flex-col bg-[#1A1A1A]">
      {/* Header */}
      <ChatHeader session={session} isLoading={false} />

      {/* Error banner (dismissible, inline) */}
      <ErrorBanner
        error={error}
        onDismiss={clearError}
        onRetry={retryLastMessage}
      />

      {/* Message window (scrollable, flex-1) */}
      <ChatWindow
        messages={messages}
        isTyping={isTyping}
        onRetry={retryLastMessage}
        onSuggestionClick={sendMessage}
        hookActions={hookActions}
        sessionState={sessionState}
      />

      {/* Input area (pinned to bottom) */}
      <ChatInput
        onSend={sendMessage}
        isTyping={isTyping}
        isLimitReached={isLimitReached}
        isLoading={isLoading}
        remainingToday={remainingToday}
        isDemoPackActive={isDemoPackActive}
      />
    </div>
  );
}
