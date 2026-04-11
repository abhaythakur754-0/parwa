/**
 * PARWA ChatMessage Component (Week 6 — Day 3 Phase 5)
 *
 * Renders a single chat message with support for multiple message types.
 * - text: Markdown-rendered bubble
 * - Card types (bill_summary, payment_card, otp_card, etc.): Phase 6 placeholder
 * - error: Error state with retry prompt
 * - system: Centered muted message
 * - limit_reached / pack_expired: Special CTA banners
 */

'use client';

import { User, Bot, AlertTriangle, CreditCard, Clock, Zap } from 'lucide-react';
import type { JarvisMessage, MessageType, MessageRole } from '@/types/jarvis';
import Markdown from 'react-markdown';
import type { Components } from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';

interface ChatMessageProps {
  message: JarvisMessage;
  onRetry?: () => void;
}

// ── Avatar ───────────────────────────────────────────────────────

function MessageAvatar({ role }: { role: MessageRole }) {
  if (role === 'user') {
    return (
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500/20 to-blue-600/20 border border-blue-400/20 flex items-center justify-center shrink-0">
        <User className="w-4 h-4 text-blue-300" />
      </div>
    );
  }

  return (
    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-400/20 to-emerald-600/20 border border-emerald-400/20 flex items-center justify-center shrink-0">
      <Bot className="w-4 h-4 text-emerald-400" />
    </div>
  );
}

// ── Timestamp ────────────────────────────────────────────────────

function MessageTimestamp({
  timestamp,
  isUser,
}: {
  timestamp?: string | null;
  isUser: boolean;
}) {
  if (!timestamp) return null;

  const time = new Date(timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <p
      className={`text-[10px] mt-1 px-1 ${
        isUser ? 'text-blue-300/40 text-right' : 'text-emerald-300/40'
      }`}
    >
      {time}
    </p>
  );
}

// ── System Message ───────────────────────────────────────────────

function SystemMessage({ message }: { message: JarvisMessage }) {
  return (
    <div className="flex justify-center py-2 px-4">
      <div className="flex items-center gap-2 text-[11px] text-white/30 bg-white/[0.03] px-3 py-1.5 rounded-full border border-white/5">
        <Zap className="w-3 h-3" />
        <span>{message.content}</span>
      </div>
    </div>
  );
}

// ── Card Placeholder (Phase 6 will replace this) ────────────────

const CARD_ICONS: Partial<Record<MessageType, React.ReactNode>> = {
  bill_summary: <CreditCard className="w-5 h-5 text-emerald-400" />,
  payment_card: <CreditCard className="w-5 h-5 text-amber-400" />,
  otp_card: <AlertTriangle className="w-5 h-5 text-blue-400" />,
  handoff_card: <AlertTriangle className="w-5 h-5 text-purple-400" />,
  demo_call_card: <AlertTriangle className="w-5 h-5 text-emerald-400" />,
  action_ticket: <AlertTriangle className="w-5 h-5 text-orange-400" />,
  call_summary: <Clock className="w-5 h-5 text-blue-400" />,
  recharge_cta: <Zap className="w-5 h-5 text-amber-400" />,
};

const CARD_LABELS: Partial<Record<MessageType, string>> = {
  bill_summary: 'Bill Summary',
  payment_card: 'Payment',
  otp_card: 'OTP Verification',
  handoff_card: 'Handoff',
  demo_call_card: 'Demo Call',
  action_ticket: 'Action Ticket',
  call_summary: 'Call Summary',
  recharge_cta: 'Recharge',
};

function CardPlaceholder({ message }: { message: JarvisMessage }) {
  const type = message.message_type;
  const icon = CARD_ICONS[type];
  const label = CARD_LABELS[type] || type;

  return (
    <div className="glass rounded-xl p-4 border border-emerald-500/10 max-w-sm">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-xs font-medium text-white/70">{label}</span>
        <span className="text-[10px] text-white/30 ml-auto">Coming in Phase 6</span>
      </div>
      {message.content && (
        <p className="text-sm text-white/50 leading-relaxed">{message.content}</p>
      )}
    </div>
  );
}

// ── Limit Reached Banner ────────────────────────────────────────

function LimitReachedMessage({ message }: { message: JarvisMessage }) {
  return (
    <div className="glass rounded-xl p-4 border border-amber-500/20 max-w-sm">
      <div className="flex items-center gap-2 mb-2">
        <Clock className="w-5 h-5 text-amber-400" />
        <span className="text-sm font-medium text-amber-200">Daily Limit Reached</span>
      </div>
      <p className="text-sm text-white/60 leading-relaxed">
        {message.content ||
          "You've used all your free messages for today. Come back tomorrow or upgrade to a demo pack to continue."}
      </p>
    </div>
  );
}

// ── Pack Expired Banner ─────────────────────────────────────────

function PackExpiredMessage({ message }: { message: JarvisMessage }) {
  return (
    <div className="glass rounded-xl p-4 border border-red-500/20 max-w-sm">
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle className="w-5 h-5 text-red-400" />
        <span className="text-sm font-medium text-red-200">Demo Pack Expired</span>
      </div>
      <p className="text-sm text-white/60 leading-relaxed">
        {message.content ||
          'Your demo pack has expired. Purchase a new pack or contact sales to continue using Jarvis.'}
      </p>
    </div>
  );
}

// ── Error Message ───────────────────────────────────────────────

function ErrorMessage({
  message,
  onRetry,
}: {
  message: JarvisMessage;
  onRetry?: () => void;
}) {
  return (
    <div className="glass rounded-xl p-3 border border-red-500/15 max-w-sm">
      <div className="flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
        <div className="flex-1">
          <p className="text-sm text-red-200 leading-relaxed">
            {message.content || 'Something went wrong. Please try again.'}
          </p>
          {onRetry && (
            <button
              onClick={onRetry}
              aria-label="Retry last message"
              className="mt-2 text-xs text-red-300/70 hover:text-red-200 underline underline-offset-2 transition-colors"
            >
              Tap to retry
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────

// ── Markdown Components (XSS-safe) ────────────────────────────────

const markdownComponents: Components = {
  a: ({ href, children, ...props }) => {
    if (
      typeof href === 'string' &&
      (/^(javascript|data|vbscript):/i.test(href))
    ) {
      return <span {...props}>{children}</span>;
    }
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
        {children}
      </a>
    );
  },
};

// ── Main Component ──────────────────────────────────────────────

export function ChatMessage({ message, onRetry }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  // System messages — centered, no avatar
  if (isSystem) {
    return <SystemMessage message={message} />;
  }

  // Error messages — show inline error card
  if (message.message_type === 'error') {
    return (
      <div className="flex items-end gap-2 px-4 py-2 chat-msg-reveal">
        <MessageAvatar role={message.role} />
        <div className="max-w-[75%]">
          <ErrorMessage message={message} onRetry={onRetry} />
          <MessageTimestamp timestamp={message.timestamp} isUser={false} />
        </div>
      </div>
    );
  }

  // Card types — special rendering
  const cardTypes: MessageType[] = [
    'bill_summary',
    'payment_card',
    'otp_card',
    'handoff_card',
    'demo_call_card',
    'action_ticket',
    'call_summary',
    'recharge_cta',
  ];

  if (cardTypes.includes(message.message_type)) {
    return (
      <div
        className={`flex items-end gap-2 px-4 py-2 chat-msg-reveal ${
          isUser ? 'flex-row-reverse' : ''
        }`}
      >
        <MessageAvatar role={message.role} />
        <div className="max-w-[75%]">
          <CardPlaceholder message={message} />
          <MessageTimestamp timestamp={message.timestamp} isUser={isUser} />
        </div>
      </div>
    );
  }

  // Special banners
  if (message.message_type === 'limit_reached') {
    return (
      <div className="flex items-end gap-2 px-4 py-2 chat-msg-reveal">
        <MessageAvatar role="jarvis" />
        <div className="max-w-[75%]">
          <LimitReachedMessage message={message} />
          <MessageTimestamp timestamp={message.timestamp} isUser={false} />
        </div>
      </div>
    );
  }

  if (message.message_type === 'pack_expired') {
    return (
      <div className="flex items-end gap-2 px-4 py-2 chat-msg-reveal">
        <MessageAvatar role="jarvis" />
        <div className="max-w-[75%]">
          <PackExpiredMessage message={message} />
          <MessageTimestamp timestamp={message.timestamp} isUser={false} />
        </div>
      </div>
    );
  }

  // Standard text message
  return (
    <div
      className={`flex items-end gap-2 px-4 py-2 chat-msg-reveal ${
        isUser ? 'flex-row-reverse' : ''
      }`}
    >
      <MessageAvatar role={message.role} />

      <div className={`max-w-[75%] flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Message bubble */}
        <div
          className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
            isUser
              ? 'bg-gradient-to-br from-blue-600/90 to-blue-700/90 text-white rounded-br-md shadow-lg shadow-blue-500/10'
              : 'glass text-white/90 rounded-bl-md border border-white/[0.06]'
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none prose-p:text-white/90 prose-p:leading-relaxed prose-headings:text-white prose-strong:text-white prose-code:text-emerald-300 prose-a:text-emerald-400 prose-li:text-white/80">
              <Markdown rehypePlugins={[rehypeSanitize]} components={markdownComponents}>{message.content}</Markdown>
            </div>
          )}
        </div>

        <MessageTimestamp timestamp={message.timestamp} isUser={isUser} />
      </div>
    </div>
  );
}
