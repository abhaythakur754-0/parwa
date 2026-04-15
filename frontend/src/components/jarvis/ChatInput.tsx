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
import { ArrowUp, AlertCircle, Paperclip } from 'lucide-react';

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
  const [error, setError] = useState<string | null>(null);
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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // D11-P2 Fix: File size guard — reject files over 1MB before any FileReader work
    const MAX_FILE_SIZE = 1 * 1024 * 1024; // 1MB
    if (file.size > MAX_FILE_SIZE) {
      setError('File too large. Maximum 1MB.');
      e.target.value = ''; // clear the input
      return;
    }

    setError(null);

    // For the onboarding demo, we read small text files directly
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (content) {
        onSend(`[DOCUMENT_UPLOAD]: ${file.name}\n\nContent:\n${content.slice(0, 5000)}`);
      }
    };
    reader.readAsText(file);
    // Reset input
    e.target.value = '';
  };

  const fileInputRef = useRef<HTMLInputElement>(null);

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
      {/* File upload error */}
      {error && (
        <div className="flex items-center gap-2 mb-2 p-2 rounded-lg bg-red-500/10 border border-red-500/15">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <p className="text-xs text-red-200/80">{error}</p>
        </div>
      )}

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
      <div className="flex items-end gap-3">
        {/* Hidden file input */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          className="hidden"
          accept=".txt,.json,.md,.csv"
        />
        
        {/* Attachment Button */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isDisabled}
          className="mb-2 w-10 h-10 rounded-xl flex items-center justify-center bg-white/[0.04] border border-white/10 text-white/40 hover:text-white hover:bg-white/[0.08] transition-all disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
          title="Attach document to test Jarvis"
        >
          <Paperclip className="w-5 h-5" />
        </button>

        <div className="flex-1 relative group">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => { setValue(e.target.value); setError(null); }}
            onKeyDown={handleKeyDown}
            placeholder={
              isLoading
                ? 'Connecting to Jarvis...'
                : isLimitReached
                  ? 'Daily limit reached'
                  : 'Message Jarvis...'
            }
            disabled={isTyping || isLoading || isLimitReached}
            rows={1}
            maxLength={MAX_CHARS + 50}
            className="w-full resize-none rounded-2xl bg-white/[0.04] border border-white/10 text-[15px] text-white px-4 py-4 pr-14 placeholder:text-white/20 focus:outline-none focus:border-white/20 focus:ring-1 focus:ring-white/10 transition-all disabled:opacity-40 disabled:cursor-not-allowed leading-relaxed"
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

          {/* Send button - Absolutely positioned inside the textarea area */}
          <div className="absolute right-2 bottom-2">
            <button
              onClick={handleSend}
              disabled={isDisabled || isOverLimit}
              className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-all duration-300 ${
                isDisabled || isOverLimit
                  ? 'bg-white/[0.05] text-white/10 cursor-not-allowed'
                  : 'bg-white text-black hover:bg-orange-500 hover:text-white shadow-lg active:scale-95'
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
                <div className="w-4 h-4 border-2 border-black/40 border-t-black rounded-full animate-spin" />
              ) : (
                <ArrowUp className="w-5 h-5 stroke-[2.5]" />
              )}
            </button>
          </div>
        </div>
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
    </div>
  );
}
