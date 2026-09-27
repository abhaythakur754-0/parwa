/**
 * PARWA ChatWindow Component (Week 6 — Day 3 Phase 5)
 *
 * Scrollable message list with auto-scroll behavior.
 * Renders ChatMessage for each message in the history.
 * Shows TypingIndicator when Jarvis is generating a response.
 * Displays an empty state when there are no messages yet.
 * Welcome messages are context-aware:
 *   - Reads parwa_jarvis_context from localStorage for ROI data (roi_result, industry, variant)
 *   - Uses sessionContext entry_source and pages_visited for page-aware greetings
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import { MessageSquare } from 'lucide-react';
import type { JarvisMessage, JarvisContext } from '@/types/jarvis';
import { ChatMessage } from './ChatMessage';
import { TypingIndicator } from './TypingIndicator';
import { ScrollArea } from '@/components/ui/scroll-area';

// ── ROI context shape (stored in localStorage as parwa_jarvis_context) ──

interface RoiContext {
  roi_result?: number | string | null;
  industry?: string | null;
  variant?: string | null;
  [key: string]: unknown;
}

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

/** Safe localStorage getter — returns null if unavailable (SSR). */
function getLocalStorageJson<T>(key: string): T | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

/** Industry display names for welcome messages. */
const INDUSTRY_LABELS: Record<string, string> = {
  ecommerce: 'e-commerce',
  realestate: 'real estate',
  healthcare: 'healthcare',
  education: 'education',
  finance: 'finance',
  travel: 'travel',
  restaurant: 'restaurant',
  salon: 'salon & beauty',
  fitness: 'fitness',
  legal: 'legal',
};

/** Build a context-aware welcome message combining ROI data and page-visit context. */
function getWelcomeMessage(
  ctx?: JarvisContext | null,
  roiCtx?: RoiContext | null,
): { heading: string; body: string } {
  const entrySource = ctx?.entry_source;
  const pagesVisited = ctx?.pages_visited || [];

  // ── Priority 1: ROI-aware messages (from localStorage parwa_jarvis_context) ──
  if (roiCtx) {
    const hasRoi = roiCtx.roi_result != null;
    const industry = roiCtx.industry
      ? INDUSTRY_LABELS[roiCtx.industry] || roiCtx.industry
      : null;
    const variant = roiCtx.variant || null;

    if (hasRoi && industry) {
      return {
        heading: `Great news for your ${industry} business! 📊`,
        body: `Based on your ROI calculation, you could save significantly. Your selected ${variant ? `"${variant}" ` : ''}plan looks like a great fit. Want me to walk you through the details?`,
      };
    }
    if (hasRoi && !industry) {
      return {
        heading: 'Your ROI results are in! 📊',
        body: `I see you ran the ROI calculator — looks promising! Want to explore the right plan to make those savings a reality?`,
      };
    }
    if (!hasRoi && industry) {
      return {
        heading: `${industry.charAt(0).toUpperCase() + industry.slice(1)} solutions 🏢`,
        body: `I see you're exploring PARWA for ${industry}. Want to see how our AI agents can help your business grow?`,
      };
    }
    if (variant) {
      return {
        heading: `${variant} — great choice! ✨`,
        body: `I see you were checking out the "${variant}" plan. Want me to break down what's included and get you started?`,
      };
    }
  }

  // ── Priority 2: entry_source specific messages ──
  if (entrySource === 'pricing') {
    return {
      heading: 'Pricing questions? I can help! 💰',
      body: "I see you were exploring our pricing! Ready to find the right plan for your business?",
    };
  }
  if (entrySource === 'roi') {
    return {
      heading: 'Welcome back! 📊',
      body: "I see you've been checking out our ROI calculator. Want to see how PARWA can save you money?",
    };
  }
  if (entrySource === 'features' || entrySource === 'models') {
    return {
      heading: 'Explore our AI models! 🤖',
      body: "I see you were browsing our AI models. Which ones caught your eye?",
    };
  }

  // ── Priority 3: pages_visited awareness ──
  if (pagesVisited.includes('pricing_page')) {
    return {
      heading: 'Hey there! 👋',
      body: "Welcome! I see you've been looking at our pricing. I can help you pick the perfect plan.",
    };
  }
  if (pagesVisited.includes('roi_calculator')) {
    return {
      heading: 'Hey there! 👋',
      body: "Welcome! I see you've been using our ROI calculator. Ready to see PARWA in action?",
    };
  }
  if (pagesVisited.includes('models_page')) {
    return {
      heading: 'Hey there! 👋',
      body: "Welcome! I see you were browsing our AI models. I'd love to help you find the right fit.",
    };
  }

  // ── Default / direct / onboarding ──
  return {
    heading: "Hey there! 👋",
    body: "I'm Jarvis, your AI assistant from PARWA. I'll help you find the perfect AI agents for your business. What brings you here today?",
  };
}

export function ChatWindow({ messages, isTyping, onRetry, onSuggestionClick, hookActions, sessionState, sessionContext }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  // ROI context from localStorage (client-only)
  const [roiContext, setRoiContext] = useState<RoiContext | null>(null);

  useEffect(() => {
    const ctx = getLocalStorageJson<RoiContext>('parwa_jarvis_context');
    setRoiContext(ctx);
  }, []);

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
  const welcome = getWelcomeMessage(sessionContext, roiContext);

  return (
    <div className="flex-1 overflow-hidden relative" ref={containerRef} role="log" aria-label="Chat messages">
      <ScrollArea className="h-full scrollbar-premium">
        <div className="flex flex-col min-h-full py-4">
          {/* Empty state */}
          {isEmpty && (
            <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 text-center animate-fade-in">
              {/* Decorative icon */}
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500/10 to-orange-600/10 border border-orange-500/15 flex items-center justify-center mb-4">
                <MessageSquare className="w-8 h-8 text-orange-400/50" />
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
            <div className="flex flex-col gap-1">
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
