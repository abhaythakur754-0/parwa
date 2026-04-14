/**
 * PARWA ChatWindow Component (Week 6 — Day 3 Phase 5)
 *
 * Scrollable message list with auto-scroll behavior.
 * Renders ChatMessage for each message in the history.
 * Shows TypingIndicator when Jarvis is generating a response.
 * Displays an empty state when there are no messages yet.
 */

'use client';

import { useEffect, useRef } from 'react';
import { MessageSquare, Bot } from 'lucide-react';
import type { JarvisMessage, JarvisContext } from '@/types/jarvis';
import { ChatMessage } from './ChatMessage';
import { TypingIndicator } from './TypingIndicator';
import { ScrollArea } from '@/components/ui/scroll-area';

interface ChatWindowProps {
  /** Ordered list of chat messages */
  messages: JarvisMessage[];
  /** Whether Jarvis is currently generating a response */
  isTyping: boolean;
  /** Callback to retry a failed message */
  onRetry?: () => void;
  /** Callback when a quick suggestion chip is clicked */
  onSuggestionClick?: (text: string) => void;
  /** Hook actions passed through to ChatMessage cards */
  hookActions?: {
    sendOtp?: (email: string) => Promise<void>;
    verifyOtp?: (code: string) => Promise<boolean>;
    purchaseDemoPack?: () => Promise<void>;
    createPayment?: (variants: { id: string; name?: string; quantity: number; price?: number; features?: string[] }[], industry: string) => Promise<string | null>;
    initiateDemoCall?: (phone: string) => Promise<void>;
    executeHandoff?: () => Promise<void>;
  };
  /** Session state passed through to ChatMessage cards */
  sessionState?: {
    remainingToday?: number;
    totalMessages?: number;
    isDemoPackActive?: boolean;
    isHandoffComplete?: boolean;
    paymentProcessing?: boolean;
    otpState?: { status: string; email: string };
    demoCallState?: { status: string; phone: string | null; duration: number };
  };
  /** Session context for personalized welcome message */
  sessionContext?: JarvisContext | null;
}

/**
 * Bug #5 Fix: Removed local getWelcomeMessage to prevent dual-welcome conflict.
 * The server-side route.ts generates a rich, context-aware welcome via
 * getContextAwareWelcome(). That message arrives as the first jarvis message.
 * Previously, ChatWindow showed its OWN welcome (above) during the loading gap,
 * then the server welcome appeared — causing confusing duplicate messages.
 *
 * Now: During loading, we show a generic connecting state.
 * After loading: The server's welcome message (already in messages[]) is displayed.
 * Single source of truth = route.ts getContextAwareWelcome().
 */

export function ChatWindow({ messages, isTyping, onRetry, onSuggestionClick, hookActions, sessionState, sessionContext }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  // Track scroll position — user is near bottom if within 80px
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      isNearBottomRef.current = scrollHeight - scrollTop - clientHeight < 80;
    };

    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, []);

  // Auto-scroll to bottom only when user is near bottom
  useEffect(() => {
    if (isNearBottomRef.current && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages.length, isTyping]);

  const isEmpty = messages.length === 0 && !isTyping;

  return (
    <div className="flex-1 overflow-hidden relative bg-[#0D0D0D]" ref={containerRef} role="log" aria-label="Chat messages">
      <ScrollArea className="h-full scrollbar-premium">
        <div className="flex flex-col min-h-full">
          {/* Empty state — Bug #5 Fix: generic loading/connecting state.
              The real context-aware welcome comes from the server (route.ts) */}
          {isEmpty && (
            <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 text-center animate-fade-in max-w-2xl mx-auto">
              {/* Decorative icon */}
              <div className="w-16 h-16 rounded-3xl bg-orange-500/5 border border-orange-500/10 flex items-center justify-center mb-6">
                <Bot className="w-8 h-8 text-orange-400/40" />
              </div>

              <h3 className="text-base font-medium text-white/60 mb-1">
                Connecting to Jarvis...
              </h3>
              <p className="text-sm text-white/30 max-w-xs leading-relaxed">
                Initializing your control center. One moment...
              </p>

              {/* Quick-start suggestions — shown until server welcome arrives */}
              <div className="flex flex-wrap justify-center gap-2 mt-6">
                {SUGGESTIONS.map((s) => (
                  <QuickSuggestion key={s} text={s} onClick={onSuggestionClick} />
                ))}
              </div>
            </div>
          )}

          {/* Message list */}
          {!isEmpty && (
            <div className="flex flex-col">
              {messages.map((msg, idx) => (
                <ChatMessage
                  key={msg.id || `msg-${idx}`}
                  message={msg}
                  onRetry={msg.message_type === 'error' ? onRetry : undefined}
                  hookActions={hookActions}
                  sessionState={sessionState}
                />
              ))}

              {/* Typing indicator */}
              {isTyping && <TypingIndicator />}

              {/* Scroll anchor */}
              <div ref={bottomRef} className="h-1" />
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

// ── Quick Suggestion Chip ───────────────────────────────────────

function QuickSuggestion({ text, onClick }: { text: string; onClick?: (text: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => onClick?.(text)}
      className="text-[11px] text-orange-400/50 bg-orange-500/5 border border-orange-500/10 rounded-full px-3 py-1 cursor-pointer select-none hover:bg-orange-500/10 hover:text-orange-400/70 hover:border-orange-500/20 transition-all duration-150"
    >
      {text}
    </button>
  );
}

/** Starter suggestions shown in the empty state */
const SUGGESTIONS = [
  '💡 What is PARWA?',
  '💰 Show me pricing',
  '🛒 How it works for e-commerce?',
  '🚀 Help me get started',
] as const;
