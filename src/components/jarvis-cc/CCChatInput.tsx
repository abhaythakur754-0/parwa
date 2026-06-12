/**
 * CCChatInput — Input component for Jarvis CC chat
 *
 * Supports text messages and command input (/command format).
 * Auto-detects commands starting with "/" or "jarvis ".
 */

'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { cn } from '@/lib/utils';

export interface CCChatInputProps {
  onSendMessage: (content: string) => void;
  onSendCommand: (rawInput: string) => void;
  disabled?: boolean;
  placeholder?: string;
  remainingToday?: number;
  className?: string;
}

export function CCChatInput({
  onSendMessage,
  onSendCommand,
  disabled = false,
  placeholder = 'Message Jarvis or type / for commands...',
  remainingToday,
  className,
}: CCChatInputProps) {
  const [value, setValue] = useState('');
  const [isCommand, setIsCommand] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`;
    }
  }, [value]);

  // Detect command mode
  useEffect(() => {
    const trimmed = value.trimStart();
    setIsCommand(trimmed.startsWith('/') || trimmed.toLowerCase().startsWith('jarvis '));
  }, [value]);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;

    if (trimmed.startsWith('/') || trimmed.toLowerCase().startsWith('jarvis ')) {
      // Strip leading slash or "jarvis " prefix for commands
      const cmdInput = trimmed.startsWith('/')
        ? trimmed.slice(1)
        : trimmed.slice(7); // "jarvis ".length
      onSendCommand(cmdInput || trimmed);
    } else {
      onSendMessage(trimmed);
    }

    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [value, disabled, onSendMessage, onSendCommand]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={cn('border-t border-white/[0.06] bg-[#111111]', className)}>
      {/* Command mode indicator */}
      {isCommand && (
        <div className="flex items-center gap-1.5 px-4 pt-2">
          <span className="text-[10px] text-orange-400 bg-orange-500/10 px-1.5 py-0.5 rounded">Command Mode</span>
          <span className="text-[10px] text-zinc-600">Type a natural language command</span>
        </div>
      )}

      {/* Remaining count */}
      {remainingToday !== undefined && remainingToday <= 10 && remainingToday > 0 && (
        <div className="px-4 pt-2">
          <span className="text-[10px] text-amber-400">{remainingToday} messages remaining today</span>
        </div>
      )}

      <div className="flex items-end gap-2 p-3">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={placeholder}
            rows={1}
            maxLength={10000}
            className={cn(
              'w-full bg-white/[0.04] border border-white/[0.06] rounded-xl px-4 py-2.5 text-sm text-white placeholder-zinc-600 outline-none resize-none transition-colors',
              'focus:border-orange-500/30 focus:bg-white/[0.06]',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              isCommand && 'border-orange-500/20 bg-orange-500/5'
            )}
          />
        </div>

        <button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className={cn(
            'shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200',
            value.trim() && !disabled
              ? 'bg-gradient-to-r from-orange-500 to-amber-400 text-white shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30'
              : 'bg-white/5 text-zinc-600 cursor-not-allowed'
          )}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
          </svg>
        </button>
      </div>
    </div>
  );
}
