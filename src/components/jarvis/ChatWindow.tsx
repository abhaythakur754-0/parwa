/**
 * PARWA ChatWindow Component — ZAI-style Clean Design
 *
 * Scrollable message list with auto-scroll behavior.
 * Renders ChatMessage for each message with consecutive grouping.
 * Shows TypingIndicator when Jarvis is generating a response.
 * Displays an empty state with quick suggestions when no messages.
 * Knowledge base upload section appears when user comes from Free Demo.
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import type { JarvisMessage, JarvisContext } from '@/types/jarvis';
import { ChatMessage } from './ChatMessage';
import { TypingIndicator } from './TypingIndicator';
import { KnowledgeBaseUpload } from './KnowledgeBaseUpload';
import { ScrollArea } from '@/components/ui/scroll-area';

// ── Props ──────────────────────────────────────────────────────

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
  /** Knowledge base upload callback */
  onKnowledgeBaseUpload?: (files: File[]) => Promise<void>;
  /** Whether knowledge base upload is in progress */
  isKnowledgeBaseUploading?: boolean;
  /** Uploaded knowledge base files */
  knowledgeBaseFiles?: Array<{ name: string; size: number; status: 'pending' | 'uploading' | 'done' | 'error' }>;
  /** Entry source for context-aware UI */
  entrySource?: string;
  /** Entry params for variant context */
  entryParams?: Record<string, unknown>;
}

export function ChatWindow({
  messages,
  isTyping,
  onRetry,
  onSuggestionClick,
  hookActions,
  sessionState,
  sessionContext,
  onKnowledgeBaseUpload,
  isKnowledgeBaseUploading,
  knowledgeBaseFiles,
  entrySource,
  entryParams,
}: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const [showKnowledgeBase, setShowKnowledgeBase] = useState(false);

  // Show knowledge base section automatically for Free Demo / Models page entries
  useEffect(() => {
    const isVariantEntry = entrySource?.includes('models_') || entrySource === 'models_page' || entrySource === 'free_chat';
    if (isVariantEntry) {
      setShowKnowledgeBase(true);
    }
  }, [entrySource]);

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

  // Determine if consecutive messages are from the same role (for grouping)
  const isConsecutive = (index: number): boolean => {
    if (index === 0) return false;
    return messages[index].role === messages[index - 1].role && messages[index].role !== 'system';
  };

  // Variant/industry info for knowledge base section
  const variantName = entryParams?.variant ? String(entryParams.variant) : undefined;
  const industryName = entryParams?.industry ? String(entryParams.industry) : undefined;

  return (
    <div className="flex-1 overflow-hidden relative" ref={containerRef} role="log" aria-label="Chat messages">
      <ScrollArea className="h-full scrollbar-premium">
        <div className="flex flex-col min-h-full py-4">
          {/* Empty state */}
          {isEmpty && (
            <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 text-center animate-fade-in">
              {/* Avatar */}
              <div className="w-14 h-14 rounded-full bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center mb-4 shadow-lg shadow-orange-500/20">
                <span className="text-white font-bold text-xl">J</span>
              </div>

              <h3 className="text-lg font-semibold text-white/80 mb-0.5">
                Jarvis
              </h3>
              <p className="text-xs text-white/30 mb-4">
                Your AI control center
              </p>
              <p className="text-sm text-white/40 max-w-xs leading-relaxed mb-6">
                Ask me anything — pricing, demos, setup, or let me show you how a specific variant handles real scenarios.
              </p>

              {/* Quick-start suggestions */}
              <div className="flex flex-wrap justify-center gap-2 mb-6">
                {SUGGESTIONS.map((s) => (
                  <QuickSuggestion key={s} text={s} onClick={onSuggestionClick} />
                ))}
              </div>

              {/* Knowledge base upload in empty state for demo users */}
              {(entrySource?.includes('models_') || entrySource === 'models_page' || entrySource === 'free_chat') && onKnowledgeBaseUpload && (
                <div className="w-full max-w-xs">
                  <KnowledgeBaseUpload
                    onUpload={onKnowledgeBaseUpload}
                    isUploading={isKnowledgeBaseUploading}
                    uploadedFiles={knowledgeBaseFiles}
                    variantName={variantName}
                    industryName={industryName}
                    compact={true}
                  />
                </div>
              )}
            </div>
          )}

          {/* Message list */}
          {!isEmpty && (
            <div className="flex flex-col gap-0.5">
              {messages.map((msg, idx) => (
                <ChatMessage
                  key={msg.id || `msg-${idx}`}
                  message={msg}
                  onRetry={msg.message_type === 'error' ? onRetry : undefined}
                  hookActions={hookActions}
                  sessionState={sessionState}
                  isConsecutive={isConsecutive(idx)}
                />
              ))}

              {/* Typing indicator */}
              {isTyping && <TypingIndicator />}

              {/* Knowledge base upload — shown after messages for demo users */}
              {showKnowledgeBase && onKnowledgeBaseUpload && (
                <div className="px-4 py-2 chat-msg-reveal">
                  <div className="flex items-start gap-2.5">
                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center shrink-0 text-white font-bold text-[10px] shadow-sm shadow-orange-500/15 mt-0.5">
                      J
                    </div>
                    <div className="max-w-[80%]">
                      <KnowledgeBaseUpload
                        onUpload={onKnowledgeBaseUpload}
                        isUploading={isKnowledgeBaseUploading}
                        uploadedFiles={knowledgeBaseFiles}
                        variantName={variantName}
                        industryName={industryName}
                      />
                    </div>
                  </div>
                </div>
              )}

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
      className="text-[11px] text-orange-400/50 bg-orange-500/5 border border-orange-500/10 rounded-full px-3 py-1.5 cursor-pointer select-none hover:bg-orange-500/10 hover:text-orange-400/70 hover:border-orange-500/20 transition-all duration-150"
    >
      {text}
    </button>
  );
}

/** Starter suggestions shown in the empty state */
const SUGGESTIONS = [
  'What can you do?',
  'Show me pricing',
  'Give me a live demo!',
  'How much can I save?',
] as const;
