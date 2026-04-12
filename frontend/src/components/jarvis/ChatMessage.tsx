/**
 * PARWA ChatMessage Component (Week 6 — Day 3 Phase 5, Updated Day 4 Phase 6)
 *
 * Renders a single chat message with support for multiple message types.
 * - text: Markdown-rendered bubble
 * - Card types: Rich interactive cards (Phase 6)
 * - error: Error state with retry prompt
 * - system: Centered muted message
 */

'use client';

import { User, Bot, AlertTriangle, Clock, Zap } from 'lucide-react';
import type { JarvisMessage, MessageType, MessageRole } from '@/types/jarvis';

// Phase 6 card imports
import { BillSummaryCard } from './BillSummaryCard';
import { PaymentCard } from './PaymentCard';
import { OtpVerificationCard } from './OtpVerificationCard';
import { HandoffCard } from './HandoffCard';
import { DemoCallCard } from './DemoCallCard';
import { ActionTicketCard } from './ActionTicketCard';
import { PostCallSummaryCard } from './PostCallSummaryCard';
import { RechargeCTACard } from './RechargeCTACard';
import { LimitReachedCard } from './LimitReachedCard';
import { PackExpiredCard } from './PackExpiredCard';
import { MessageCounter } from './MessageCounter';
import { DemoPackCTA } from './DemoPackCTA';

interface ChatMessageProps {
  message: JarvisMessage;
  onRetry?: () => void;
  // Hook actions for interactive cards
  hookActions?: {
    sendOtp?: (email: string) => Promise<void>;
    verifyOtp?: (code: string) => Promise<boolean>;
    purchaseDemoPack?: () => Promise<void>;
    createPayment?: (variants: { id: string; name?: string; quantity: number; price?: number; features?: string[] }[], industry: string) => Promise<string | null>;
    initiateDemoCall?: (phone: string) => Promise<void>;
    executeHandoff?: () => Promise<void>;
  };
  // Session state for card props
  sessionState?: {
    remainingToday?: number;
    totalMessages?: number;
    isDemoPackActive?: boolean;
    isHandoffComplete?: boolean;
    paymentProcessing?: boolean;
    otpState?: { status: string; email: string };
    demoCallState?: { status: string; phone: string | null; duration: number };
  };
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
    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-400/20 to-orange-600/20 border border-orange-400/20 flex items-center justify-center shrink-0">
      <Bot className="w-4 h-4 text-orange-400" />
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
        isUser ? 'text-blue-300/40 text-right' : 'text-orange-300/40'
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

// ── Inline Content Renderer (bullet-point aware, XSS-safe) ──────────

function isEmojiChar(ch: string): boolean {
  // Must use codePointAt for emoji (surrogate pairs in JS)
  const code = ch.codePointAt(0) || 0;
  return (code >= 0x1F300 && code <= 0x1FAFF) || (code >= 0x2600 && code <= 0x27BF) || (code >= 0xFE00 && code <= 0xFE0F);
}

function renderInlineContent(content: string) {
  // Pre-process: if a single line contains multiple bullet markers (•, -, *) split them into separate lines
  const preprocessed = content.split('\n').flatMap((line) => {
    const trimmed = line.trim();
    if (!trimmed) return [line];
    // Check if line has 2+ bullet markers — meaning multiple bullets are jammed on one line
    const bulletMatches = trimmed.match(/[\u2022\-*•]\s/g);
    if (bulletMatches && bulletMatches.length >= 2) {
      // Split on bullet markers but keep the marker with each piece
      return trimmed.split(/(?=[\u2022\-*•]\s)/).filter(Boolean);
    }
    return [line];
  });

  const lines = preprocessed;
  let openerUsed = false;

  return lines.map((line, index) => {
    const trimmed = line.trim();
    if (!trimmed) return <div key={index} className="h-2" />;

    // Bullet point lines (•, -, *, or emoji prefix)
    const firstChar = trimmed.charCodeAt(0);
    const isEmoji = isEmojiChar(trimmed);
    const isBullet = /^[\u2022\-*•]\s/.test(trimmed) || /^[0-9]+[.)]\s/.test(trimmed) || isEmoji;
    const isOpener = !openerUsed && !isBullet && trimmed.length < 80;

    if (isBullet) {
      // Strip leading bullet markers but keep emoji + text
      const displayText = trimmed.replace(/^[\u2022\-*•]\s*/, '').replace(/^[0-9]+[.)]\s*/, '');
      return (
        <div key={index} className="flex items-start gap-2 py-0.5">
          <span className="text-orange-400 shrink-0 mt-0.5 text-xs">&#9656;</span>
          <span className="text-white/90 leading-relaxed text-sm">
            {displayText}
          </span>
        </div>
      );
    }

    if (isOpener) {
      openerUsed = true;
      return (
        <p key={index} className="text-white font-medium text-sm leading-relaxed">
          {trimmed}
        </p>
      );
    }

    return (
      <p key={index} className="text-white/80 text-sm leading-relaxed">
        {trimmed}
      </p>
    );
  });
}

// ── Card Wrapper (avatar + timestamp) ─────────────────────────────

function CardWrapper({
  message,
  isUser,
  children,
}: {
  message: JarvisMessage;
  isUser: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`flex items-end gap-2 px-4 py-2 chat-msg-reveal ${
        isUser ? 'flex-row-reverse' : ''
      }`}
    >
      <MessageAvatar role={message.role} />
      <div className="max-w-[80%]">
        {children}
        <MessageTimestamp timestamp={message.timestamp} isUser={isUser} />
      </div>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────

export function ChatMessage({ message, onRetry, hookActions, sessionState }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const metadata = message.metadata || {};
  const total = sessionState?.totalMessages || 20;

  // System messages — centered, no avatar
  if (isSystem) {
    return <SystemMessage message={message} />;
  }

  // Error messages — show inline error card
  if (message.message_type === 'error') {
    return (
      <CardWrapper message={message} isUser={false}>
        <ErrorMessage message={message} onRetry={onRetry} />
      </CardWrapper>
    );
  }

  // ── Rich Cards (Phase 6) ─────────────────────────────────────

  switch (message.message_type) {
    case 'bill_summary':
      return (
        <CardWrapper message={message} isUser={false}>
          <BillSummaryCard
            metadata={metadata as Record<string, unknown>}
            onProceed={hookActions?.createPayment
              ? () => {
                  const variants = (metadata.variants as { id: string; name?: string; quantity: number; price?: number; features?: string[] }[]) || [];
                  const industry = (metadata.industry as string) || '';
                  hookActions.createPayment?.(variants, industry);
                }
              : undefined}
          />
        </CardWrapper>
      );

    case 'payment_card':
      return (
        <CardWrapper message={message} isUser={false}>
          <PaymentCard
            metadata={metadata as Record<string, unknown>}
            onCreatePayment={hookActions?.createPayment
              ? () => {
                  const variants = (metadata.variants as { id: string; name?: string; quantity: number; price?: number; features?: string[] }[]) || [];
                  const industry = (metadata.industry as string) || '';
                  return hookActions.createPayment?.(variants, industry) || Promise.resolve(null);
                }
              : undefined}
            onPurchaseDemoPack={hookActions?.purchaseDemoPack}
            isDemoPackActive={sessionState?.isDemoPackActive}
          />
        </CardWrapper>
      );

    case 'otp_card':
      return (
        <CardWrapper message={message} isUser={false}>
          <OtpVerificationCard
            onSendOtp={hookActions?.sendOtp || (async () => {})}
            onVerifyOtp={hookActions?.verifyOtp || (async () => false)}
            initialEmail={sessionState?.otpState?.email || (metadata.email as string) || ''}
            onVerified={undefined}
          />
        </CardWrapper>
      );

    case 'handoff_card':
      return (
        <CardWrapper message={message} isUser={false}>
          <HandoffCard
            metadata={metadata as Record<string, unknown>}
            onHandoff={hookActions?.executeHandoff}
            isHandoffComplete={sessionState?.isHandoffComplete}
          />
        </CardWrapper>
      );

    case 'demo_call_card':
      return (
        <CardWrapper message={message} isUser={false}>
          <DemoCallCard
            metadata={metadata as Record<string, unknown>}
            onInitiateCall={hookActions?.initiateDemoCall || (async () => {})}
            callStatus={(sessionState?.demoCallState?.status as 'idle' | 'initiating' | 'calling' | 'completed' | 'failed') || 'idle'}
            callDuration={sessionState?.demoCallState?.duration || 0}
          />
        </CardWrapper>
      );

    case 'action_ticket':
      return (
        <CardWrapper message={message} isUser={false}>
          <ActionTicketCard metadata={metadata as Record<string, unknown>} />
        </CardWrapper>
      );

    case 'call_summary':
      return (
        <CardWrapper message={message} isUser={false}>
          <PostCallSummaryCard metadata={metadata as Record<string, unknown>} />
        </CardWrapper>
      );

    case 'recharge_cta':
      return (
        <CardWrapper message={message} isUser={false}>
          <RechargeCTACard
            metadata={metadata as Record<string, unknown>}
            onRecharge={hookActions?.purchaseDemoPack}
            isProcessing={sessionState?.paymentProcessing}
          />
        </CardWrapper>
      );

    case 'limit_reached':
      return (
        <CardWrapper message={message} isUser={false}>
          <LimitReachedCard
            onUpgrade={hookActions?.purchaseDemoPack || undefined}
          />
        </CardWrapper>
      );

    case 'pack_expired':
      return (
        <CardWrapper message={message} isUser={false}>
          <PackExpiredCard
            onRepurchase={hookActions?.purchaseDemoPack || undefined}
          />
        </CardWrapper>
      );

    // message_counter type — inline counter
    case 'message_counter':
      return (
        <CardWrapper message={message} isUser={false}>
          <MessageCounter
            remaining={sessionState?.remainingToday ?? (metadata.remaining as number) ?? 0}
            total={total}
            isDemoPack={sessionState?.isDemoPackActive}
          />
        </CardWrapper>
      );

    // demo_pack_cta type — upgrade CTA
    case 'demo_pack_cta':
      return (
        <CardWrapper message={message} isUser={false}>
          <DemoPackCTA
            onPurchase={hookActions?.purchaseDemoPack || undefined}
            isProcessing={sessionState?.paymentProcessing}
            isAlreadyActive={sessionState?.isDemoPackActive}
          />
        </CardWrapper>
      );

    // ── Standard text message ─────────────────────────────────
    default:
      return (
        <div
          className={`flex items-end gap-2 px-4 py-2 chat-msg-reveal ${
            isUser ? 'flex-row-reverse' : ''
          }`}
        >
          <MessageAvatar role={message.role} />

          <div className={`max-w-[75%] flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
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
                <div className="space-y-0.5">
                  {renderInlineContent(message.content)}
                </div>
              )}
            </div>

            <MessageTimestamp timestamp={message.timestamp} isUser={isUser} />
          </div>
        </div>
      );
  }
}
