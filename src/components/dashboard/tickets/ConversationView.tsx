'use client';

import React, { useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import type { TicketMessage, SenderRole, TicketSentiment, TicketAttachment } from '@/types/ticket';
import ConfidenceBar from './ConfidenceBar';

interface ConversationViewProps {
  messages: TicketMessage[];
  className?: string;
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  if (isToday) return 'Today';
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function sentimentEmoji(s: TicketSentiment | null): string {
  switch (s) {
    case 'positive': return '😊';
    case 'neutral': return '😐';
    case 'negative': return '😤';
    case 'mixed': return '😕';
    default: return '';
  }
}

const senderConfig: Record<SenderRole, { label: string; avatarClass: string; bubbleClass: string; nameColor: string }> = {
  customer: {
    label: 'Customer',
    avatarClass: 'from-violet-500 to-purple-400',
    bubbleClass: 'bg-white/[0.04] border-white/[0.06]',
    nameColor: 'text-violet-400',
  },
  ai_agent: {
    label: 'PARWA AI',
    avatarClass: 'from-orange-500 to-amber-400',
    bubbleClass: 'bg-orange-500/[0.06] border-orange-500/10',
    nameColor: 'text-orange-400',
  },
  human_agent: {
    label: 'Agent',
    avatarClass: 'from-emerald-500 to-teal-400',
    bubbleClass: 'bg-emerald-500/[0.06] border-emerald-500/10',
    nameColor: 'text-emerald-400',
  },
  system: {
    label: 'System',
    avatarClass: 'from-zinc-500 to-zinc-400',
    bubbleClass: 'bg-white/[0.02] border-white/[0.04]',
    nameColor: 'text-zinc-500',
  },
};

function AttachmentChip({ attachment }: { attachment: TicketAttachment }) {
  const icon = {
    image: '🖼️',
    document: '📄',
    video: '🎬',
    audio: '🎵',
    other: '📎',
  }[attachment.file_type];

  const sizeKB = Math.round(attachment.file_size_bytes / 1024);
  const sizeStr = sizeKB > 1024 ? `${(sizeKB / 1024).toFixed(1)} MB` : `${sizeKB} KB`;

  return (
    <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06] hover:bg-white/[0.06] transition-colors cursor-pointer">
      <span className="text-sm">{icon}</span>
      <div className="min-w-0">
        <p className="text-[11px] font-medium text-zinc-300 truncate max-w-[160px]">{attachment.filename}</p>
        <p className="text-[10px] text-zinc-600">{sizeStr}</p>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: TicketMessage }) {
  const config = senderConfig[message.sender_role];
  const isSystem = message.sender_role === 'system';

  return (
    <div className={cn('flex gap-3', isSystem && 'justify-center')}>
      {/* Avatar */}
      {!isSystem && (
        <div className={cn(
          'w-8 h-8 rounded-full bg-gradient-to-br flex items-center justify-center text-white text-xs font-bold shrink-0 mt-0.5',
          config.avatarClass
        )}>
          {message.sender_role === 'ai_agent' ? 'P' : message.sender_name.charAt(0)}
        </div>
      )}

      {/* Content */}
      <div className={cn('flex-1 min-w-0', isSystem && 'text-center')}>
        {!isSystem && (
          <div className="flex items-center gap-2 mb-1">
            <span className={cn('text-xs font-semibold', config.nameColor)}>{message.sender_name}</span>
            <span className="text-[10px] text-zinc-600">{formatTime(message.created_at)}</span>
            {message.ai_technique && message.sender_role === 'ai_agent' && (
              <span className="px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400/70 text-[9px] font-medium border border-orange-500/15">
                {message.ai_technique.replace(/_/g, ' ')}
              </span>
            )}
            {message.sentiment && message.sender_role === 'customer' && (
              <span className="text-xs" title={message.sentiment}>{sentimentEmoji(message.sentiment)}</span>
            )}
          </div>
        )}

        {isSystem ? (
          <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.03] border border-white/[0.04]">
            <svg className="w-3 h-3 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z" />
            </svg>
            <span className="text-[11px] text-zinc-500">{message.content}</span>
          </div>
        ) : (
          <div className={cn('rounded-xl border p-3', config.bubbleClass)}>
            <p className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">{message.content}</p>
            {message.attachments.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {message.attachments.map((att) => (
                  <AttachmentChip key={att.id} attachment={att} />
                ))}
              </div>
            )}
            {message.ai_confidence !== null && message.sender_role === 'ai_agent' && (
              <div className="mt-2 pt-2 border-t border-white/[0.04] flex items-center justify-between">
                <span className="text-[10px] text-zinc-600">AI Confidence</span>
                <ConfidenceBar value={message.ai_confidence} size="sm" className="w-[100px]" />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ConversationView({ messages, className }: ConversationViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Group messages by date
  const grouped: { date: string; messages: TicketMessage[] }[] = [];
  let currentDate = '';

  for (const msg of messages) {
    const date = formatDate(msg.created_at);
    if (date !== currentDate) {
      currentDate = date;
      grouped.push({ date, messages: [msg] });
    } else {
      grouped[grouped.length - 1].messages.push(msg);
    }
  }

  return (
    <div className={cn('flex flex-col h-full', className)}>
      <div className="flex-1 overflow-y-auto space-y-1">
        {grouped.map((group) => (
          <div key={group.date}>
            {/* Date separator */}
            <div className="sticky top-0 z-10 py-2 bg-[#1A1A1A]/80 backdrop-blur-sm">
              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-white/[0.04]" />
                <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-wider">{group.date}</span>
                <div className="flex-1 h-px bg-white/[0.04]" />
              </div>
            </div>

            {/* Messages */}
            <div className="space-y-4 px-1">
              {group.messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
