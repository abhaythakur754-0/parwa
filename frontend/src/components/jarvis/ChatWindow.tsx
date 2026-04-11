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
import { MessageSquare } from 'lucide-react';
import type { JarvisMessage } from '@/types/jarvis';
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
}

export function ChatWindow({ messages, isTyping, onRetry, onSuggestionClick }: ChatWindowProps) {
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
    <div className="flex-1 overflow-hidden relative" ref={containerRef} role="log" aria-label="Chat messages">
      <ScrollArea className="h-full scrollbar-premium">
        <div className="flex flex-col min-h-full py-4">
          {/* Empty state */}
          {isEmpty && (
            <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 text-center animate-fade-in">
              {/* Decorative icon */}
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500/10 to-emerald-600/10 border border-emerald-500/15 flex items-center justify-center mb-4">
                <MessageSquare className="w-8 h-8 text-emerald-400/50" />
              </div>

              <h3 className="text-base font-medium text-white/60 mb-1">
                Start a conversation
              </h3>
              <p className="text-sm text-white/30 max-w-xs leading-relaxed">
                Ask Jarvis anything about PARWA — features, pricing, how it works
                for your industry, or get help with onboarding.
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
      className="text-[11px] text-emerald-400/50 bg-emerald-500/5 border border-emerald-500/10 rounded-full px-3 py-1 cursor-pointer select-none hover:bg-emerald-500/10 hover:text-emerald-400/70 hover:border-emerald-500/20 transition-all duration-150"
    >
      {text}
    </button>
  );
}

/** Starter suggestions shown in the empty state */
const SUGGESTIONS = [
  'What is PARWA?',
  'Show me pricing',
  'How does it work for e-commerce?',
  'Help me get started',
] as const;
