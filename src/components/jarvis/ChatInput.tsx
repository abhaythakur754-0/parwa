/**
 * PARWA ChatInput Component — ZAI-style Clean Design
 *
 * Text input area with send button and knowledge base upload.
 * Handles keyboard shortcuts (Enter to send, Shift+Enter for newline),
 * auto-resize, and disabled states for limit reached / typing / loading.
 */

'use client';

import { useCallback, useRef, useEffect, useState } from 'react';
import { Send, ArrowUp, Sparkles, Zap, Paperclip, BookOpen } from 'lucide-react';

interface ChatInputProps {
  /** Send message callback */
  onSend: (content: string) => void;
  /** Whether Jarvis is currently typing (disables send) */
  isTyping: boolean;
  /** Whether the user has reached the daily message limit */
  isLimitReached: boolean;
  /** Whether the session is still initializing */
  isLoading: boolean;
  /** Number of messages remaining today */
  remainingToday: number;
  /** Whether a demo pack is active */
  isDemoPackActive: boolean;
  /** Whether the user has paid for the upgrade */
  isPaid: boolean;
  /** Number of paid messages remaining */
  paidRemaining: number;
  /** Upgrade callback (triggers $1 purchase) */
  onUpgrade: () => void;
  /** Callback when knowledge base upload is requested */
  onKnowledgeBaseClick?: () => void;
  /** Whether knowledge base is available */
  hasKnowledgeBase?: boolean;
}

const MAX_CHARS = 2000;

export function ChatInput({
  onSend,
  isTyping,
  isLimitReached,
  isLoading,
  remainingToday,
  isDemoPackActive,
  isPaid,
  paidRemaining,
  onUpgrade,
  onKnowledgeBaseClick,
  hasKnowledgeBase,
}: ChatInputProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendingRef = useRef(false);

  const isDisabled = isTyping || isLoading || isLimitReached || !value.trim();
  const charCount = value.length;
  const isNearLimit = charCount > MAX_CHARS * 0.85;
  const isOverLimit = charCount > MAX_CHARS;

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = 'auto';
    const maxHeight = 120;
    const scrollH = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = `${scrollH}px`;

    if (textarea.scrollHeight > maxHeight) {
      textarea.style.overflowY = 'auto';
    } else {
      textarea.style.overflowY = 'hidden';
    }
  }, [value]);

  // Reset sending guard when typing completes
  useEffect(() => {
    if (!isTyping) sendingRef.current = false;
  }, [isTyping]);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isDisabled || isOverLimit) return;
    if (sendingRef.current) return;
    sendingRef.current = true;

    onSend(trimmed);
    setValue('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // Re-focus after send
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
    });
  }, [value, isDisabled, isOverLimit, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Enter to send (without Shift)
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
        return;
      }

      // Ctrl/Cmd + Enter as alternative send
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  return (
    <div className="shrink-0 bg-[#0D0D0D] px-4 pb-8 pt-2">
      <div className="max-w-3xl mx-auto">
        {/* Limit reached banner — $1 paywall CTA */}
        {isLimitReached && (
          <div className="mb-2 p-3 rounded-xl bg-gradient-to-br from-orange-500/10 to-amber-500/10 border border-orange-500/20">
            {!isPaid ? (
              <>
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="w-4 h-4 text-orange-400 shrink-0" />
                  <p className="text-sm font-medium text-white/90">
                    Free messages completed for today
                  </p>
                </div>
                <p className="text-xs text-white/50 mb-3">
                  Upgrade for 40 more messages + a 2-min AI voice call
                </p>
                <button
                  onClick={onUpgrade}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-gradient-to-r from-orange-500 to-amber-500 text-white text-sm font-semibold hover:from-orange-400 hover:to-amber-400 transition-all shadow-lg shadow-orange-500/20 active:scale-[0.98]"
                >
                  <Zap className="w-4 h-4" />
                  Upgrade — $1
                </button>
                <p className="text-[10px] text-white/30 mt-2 text-center">
                  Resets in 24hrs
                </p>
              </>
            ) : (
              <>
                <div className="flex items-center gap-2 mb-1">
                  <Zap className="w-4 h-4 text-amber-400 shrink-0" />
                  <p className="text-sm font-medium text-amber-200/90">
                    Pro messages: {paidRemaining} remaining
                  </p>
                </div>
                {paidRemaining <= 5 && (
                  <p className="text-[10px] text-amber-400/50 mt-1">
                    Resets in 24hrs
                  </p>
                )}
              </>
            )}
          </div>
        )}

        {/* Input row */}
        <div className="flex items-end gap-2">
          {/* Knowledge base upload button */}
          {onKnowledgeBaseClick && (
            <button
              onClick={onKnowledgeBaseClick}
              className={`shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200 mb-0.5 ${
                hasKnowledgeBase
                  ? 'bg-orange-500/15 border border-orange-500/25 text-orange-400'
                  : 'bg-white/[0.04] border border-white/10 text-white/30 hover:text-white/50 hover:bg-white/[0.06]'
              }`}
              title="Upload Knowledge Base"
              aria-label="Upload knowledge base files"
            >
              <BookOpen className="w-4 h-4" />
            </button>
          )}

          <div className="flex-1 relative group">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isLoading
                  ? 'Connecting...'
                  : isLimitReached
                    ? 'Taking a break — back soon!'
                    : 'Ask Jarvis anything...'
              }
              disabled={isTyping || isLoading || isLimitReached}
              rows={1}
              maxLength={MAX_CHARS + 50}
              className="w-full resize-none rounded-2xl bg-white/[0.04] border border-white/10 text-[15px] text-white px-4 py-4 pr-14 placeholder:text-white/20 focus:outline-none focus:border-orange-500/30 focus:ring-1 focus:ring-orange-500/10 transition-all disabled:opacity-40 disabled:cursor-not-allowed leading-relaxed"
            />

            {/* Character counter (visible when near limit) */}
            {(isNearLimit || isOverLimit) && (
              <span
                className={`absolute bottom-3 right-14 text-[10px] ${
                  isOverLimit
                    ? 'text-red-400'
                    : 'text-white/30'
                }`}
              >
                {charCount}/{MAX_CHARS}
              </span>
            )}

            {/* Send button */}
            <div className="absolute right-2 bottom-2">
              <button
                onClick={handleSend}
                disabled={isDisabled || isOverLimit}
                className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-all duration-200 ${
                  isDisabled || isOverLimit
                    ? 'bg-white/[0.05] text-white/20 cursor-not-allowed'
                    : 'bg-gradient-to-br from-orange-500 to-orange-600 text-white shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30 hover:scale-[1.02] active:scale-[0.98]'
                }`}
                title={
                  isLimitReached
                    ? 'Daily limit reached'
                    : isTyping
                      ? 'Jarvis is typing...'
                      : 'Send message'
                }
                aria-label="Send message"
              >
                {isTyping ? (
                  <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                ) : value.trim() ? (
                  <ArrowUp className="w-4 h-4" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Remaining messages hint */}
        <div className="flex items-center justify-between mt-1.5 px-1">
          {!isLimitReached && remainingToday > 0 && (
            <p className="text-[10px] text-white/20">
              {isPaid
                ? `${paidRemaining} Pro message${paidRemaining !== 1 ? 's' : ''} remaining`
                : `${remainingToday} message${remainingToday !== 1 ? 's' : ''} remaining today`}
            </p>
          )}
          {hasKnowledgeBase && (
            <p className="text-[10px] text-orange-400/40">
              Knowledge base active
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
