/**
 * PARWA ChatInput Component (Week 6 — Day 3 Phase 5)
 *
 * Text input area with send button for the Jarvis chat.
 * Handles keyboard shortcuts (Enter to send, Shift+Enter for newline),
 * auto-resize, and disabled states for limit reached / typing / loading.
 * Shows remaining message count indicator.
 */

'use client';

import { useCallback, useRef, useEffect, useState } from 'react';
import { Send, ArrowUp, AlertCircle } from 'lucide-react';

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
}

const MAX_CHARS = 2000;

export function ChatInput({
  onSend,
  isTyping,
  isLimitReached,
  isLoading,
  remainingToday,
  isDemoPackActive,
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

  // Focus textarea when component mounts or after a message is sent
  useEffect(() => {
    if (!isTyping && !isLoading && textareaRef.current) {
      // Don't auto-focus on mount (mobile unfriendly), but refocus after send
    }
  }, [isTyping, isLoading]);

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
    <div className="shrink-0 border-t border-white/10 bg-white/[0.02] backdrop-blur-sm px-4 py-3">
      {/* Limit reached banner */}
      {isLimitReached && (
        <div className="flex items-center gap-2 mb-2 p-2 rounded-lg bg-amber-500/10 border border-amber-500/15">
          <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
          <p className="text-xs text-amber-200/80">
            Daily message limit reached. Come back tomorrow
            {!isDemoPackActive && (
              <span> or upgrade to a demo pack to continue chatting</span>
            )}
            .
          </p>
        </div>
      )}

      {/* Input row */}
      <div className="flex items-end gap-2">
        {/* Textarea */}
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isLoading
                ? 'Connecting to Jarvis...'
                : isLimitReached
                  ? 'Daily limit reached'
                  : 'Type your message...'
            }
            disabled={isTyping || isLoading || isLimitReached}
            rows={1}
            maxLength={MAX_CHARS + 50} // Allow slight overflow for display
            className="w-full resize-none rounded-xl bg-white/[0.05] border border-white/10 text-white text-sm px-4 py-2.5 pr-14 placeholder:text-white/25 focus:outline-none focus:border-emerald-500/30 focus:ring-1 focus:ring-emerald-500/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          />

          {/* Character counter (visible when near limit) */}
          {(isNearLimit || isOverLimit) && (
            <span
              className={`absolute bottom-1.5 right-2 text-[10px] ${
                isOverLimit
                  ? 'text-red-400'
                  : 'text-white/30'
              }`}
            >
              {charCount}/{MAX_CHARS}
            </span>
          )}
        </div>

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={isDisabled || isOverLimit}
          className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-all duration-200 ${
            isDisabled || isOverLimit
              ? 'bg-white/[0.05] text-white/20 cursor-not-allowed'
              : 'bg-gradient-to-br from-emerald-500 to-emerald-600 text-white shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/30 hover:scale-[1.02] active:scale-[0.98]'
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

      {/* Footer hint */}
      <div className="flex items-center justify-between mt-1.5 px-1">
        <p className="text-[10px] text-white/20">
          Press Enter to send · Shift+Enter for new line
        </p>

        {!isLimitReached && remainingToday > 0 && (
          <p className="text-[10px] text-white/20">
            {remainingToday} message{remainingToday !== 1 ? 's' : ''} remaining today
          </p>
        )}
      </div>
    </div>
  );
}
