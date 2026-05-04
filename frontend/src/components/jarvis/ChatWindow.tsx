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

/** Build a context-aware welcome message based on session context. */
function getWelcomeMessage(ctx?: JarvisContext | null): { heading: string; body: string } {
  const entrySource = ctx?.entry_source;
  const industry = ctx?.industry || 'your business';
  const roi = ctx?.roi_result;
  const variant = ctx?.variant || ctx?.entry_params?.variant || ctx?.entry_params?.model;

  // ROI awareness (The 'Wow' factor)
  if (entrySource === 'roi' && roi) {
    const savings = roi.savings_annual || roi.annual_savings || 0;
    const model = roi.suggested_model || 'PARWA Growth';
    return {
      heading: 'Control Center active. ⚡',
      body: `I've analyzed your ${industry} metrics. With estimated annual savings of $${Number(savings).toLocaleString()} using our ${model}, your operational efficiency is poised for a major upgrade. Shall we run a live simulation on your data now?`,
    };
  }

  // Match entry_source to specific messages
  if (entrySource === 'pricing') {
    return {
      heading: 'Strategy initiated. 💰',
      body: `I see you were exploring our pricing for ${industry}. I can help you find the exact variant that maximizes your vertical leverage. Shall we explore the specific capabilities of our plans?`,
    };
  }
  
  if (entrySource === 'models' || entrySource === 'models_page') {
    return {
      heading: 'Model identified. 🤖',
      body: `I noticed you were examining the ${variant || 'our models'} for ${industry}. Smart selection — that specific agent is highly optimized for your vertical's specific workflow demands. Would you like to try a 3-minute demo call for $1 to see it in action?`,
    };
  }

  // Default / direct / onboarding
  return {
    heading: 'Control Center active. 👋',
    body: `I'm Jarvis — your control center from here. You can do anything just by chatting with me. From deploying agents to routing tickets, I have total leverage over your support workflow. What would you like to explore?`,
  };
}

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
  const welcome = getWelcomeMessage(sessionContext);

  return (
    <div className="flex-1 overflow-hidden relative bg-[#0D0D0D]" ref={containerRef} role="log" aria-label="Chat messages">
      <ScrollArea className="h-full scrollbar-premium">
        <div className="flex flex-col min-h-full">
          {/* Empty state */}
          {isEmpty && (
            <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 text-center animate-fade-in max-w-2xl mx-auto">
              {/* Decorative icon */}
              <div className="w-16 h-16 rounded-3xl bg-orange-500/5 border border-orange-500/10 flex items-center justify-center mb-6">
                <Bot className="w-8 h-8 text-orange-400/40" />
              </div>

              <h3 className="text-base font-medium text-white/60 mb-1">
                {welcome.heading}
              </h3>
              <p className="text-sm text-white/30 max-w-xs leading-relaxed">
                {welcome.body}
              </p>

              {/* Quick-start suggestions */}
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
