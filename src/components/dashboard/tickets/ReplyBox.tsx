'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import toast from 'react-hot-toast';

interface ReplyBoxProps {
  ticketId: string;
  onSend: (content: string) => void;
  className?: string;
}

export default function ReplyBox({ ticketId, onSend, className }: ReplyBoxProps) {
  const [message, setMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [mode, setMode] = useState<'reply' | 'note'>('reply');

  const handleSend = async () => {
    if (!message.trim()) return;
    setIsSending(true);
    try {
      await onSend(message.trim());
      setMessage('');
      toast.success(mode === 'reply' ? 'Reply sent' : 'Note added');
    } catch {
      toast.error('Failed to send');
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handleSend();
    }
  };

  return (
    <div className={cn('rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden', className)}>
      {/* Mode Toggle */}
      <div className="flex items-center gap-1 px-3 pt-3">
        <button
          onClick={() => setMode('reply')}
          className={cn(
            'px-3 py-1 rounded-lg text-xs font-medium transition-all',
            mode === 'reply'
              ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25'
              : 'text-zinc-500 hover:text-zinc-300'
          )}
        >
          💬 Reply to Customer
        </button>
        <button
          onClick={() => setMode('note')}
          className={cn(
            'px-3 py-1 rounded-lg text-xs font-medium transition-all',
            mode === 'note'
              ? 'bg-amber-500/15 text-amber-400 border border-amber-500/25'
              : 'text-zinc-500 hover:text-zinc-300'
          )}
        >
          📝 Internal Note
        </button>
      </div>

      {/* Textarea */}
      <div className="p-3">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={mode === 'reply' ? 'Type your reply to the customer...' : 'Add an internal note...'}
          rows={3}
          className="w-full px-3 py-2.5 rounded-lg bg-white/[0.04] border border-white/[0.08] text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 focus:ring-1 focus:ring-orange-500/20 resize-none transition-all"
        />

        {/* Bottom toolbar */}
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-2">
            {/* Attachment button */}
            <button
              className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-all"
              title="Attach file"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="m18.375 12.739-7.693 7.693a4.5 4.5 0 0 1-6.364-6.364l10.94-10.94A3 3 0 1 1 19.5 7.372L8.552 18.32m.009-.01-.01.01m5.699-9.941-7.81 7.81a1.5 1.5 0 0 0 2.112 2.13" />
              </svg>
            </button>

            {/* Emoji button */}
            <button
              className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-all"
              title="Insert emoji"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.182 15.182a4.5 4.5 0 0 1-6.364 0M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM9.75 9.75c0 .414-.168.75-.375.75S9 10.164 9 9.75 9.168 9 9.375 9s.375.336.375.75Zm-.375 0h.008v.015h-.008V9.75Zm5.625 0c0 .414-.168.75-.375.75s-.375-.336-.375-.75.168-.75.375-.75.375.336.375.75Zm-.375 0h.008v.015h-.008V9.75Z" />
              </svg>
            </button>

            {/* Template button */}
            <button
              className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-all"
              title="Use template"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
              </svg>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-600 hidden sm:inline">
              ⌘ + Enter to send
            </span>
            <button
              onClick={handleSend}
              disabled={!message.trim() || isSending}
              className={cn(
                'px-4 py-1.5 rounded-lg text-xs font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed',
                mode === 'reply'
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 hover:bg-emerald-500/25'
                  : 'bg-amber-500/15 text-amber-400 border border-amber-500/25 hover:bg-amber-500/25'
              )}
            >
              {isSending ? (
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Sending...
                </span>
              ) : (
                mode === 'reply' ? 'Send Reply' : 'Add Note'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
