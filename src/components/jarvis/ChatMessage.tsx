/**
 * PARWA ChatMessage Component — ZAI-style Clean Design
 *
 * Renders chat messages in a clean, modern style:
 * - User messages: Right-aligned gradient bubble
 * - AI messages: Clean open text (no WhatsApp boxes), proper markdown
 * - Cards: Rich interactive cards for specific message types
 * - Error: Inline error with retry
 * - System: Centered muted message
 */

'use client';

import { User, AlertTriangle, Clock, Zap, Bot } from 'lucide-react';
import type { JarvisMessage, MessageType, MessageRole, IntegrationActions, ProviderInfo as ProviderInfoType } from '@/types/jarvis';

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

// Integration Setup card imports
import { ProviderSelectorCard, type ProviderSelectorCardProps } from './ProviderSelectorCard';
import { ApiKeyInputCard } from './ApiKeyInputCard';
import { ConnectionStatusCard } from './ConnectionStatusCard';
import { ConnectionErrorCard } from './ConnectionErrorCard';
import { IntegrationSummaryCard } from './IntegrationSummaryCard';
import { IndustrySuggestionCard } from './IndustrySuggestionCard';

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
    integrationActions?: IntegrationActions;
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
  /** Whether the previous message was from the same role (for grouping) */
  isConsecutive?: boolean;
}

// ── Markdown Processing ──────────────────────────────────────────

function processBold(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const regex = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <strong key={`b-${key++}`} className="font-semibold text-white">
        {match[1]}
      </strong>
    );
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
}

// ── Timestamp ────────────────────────────────────────────────────

function formatRelativeTime(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);

  if (diffSec < 60) return 'now';
  if (diffMin === 1) return '1m ago';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr === 1) return '1h ago';
  if (diffHr < 24) return `${diffHr}h ago`;
  return new Date(timestamp).toLocaleDateString([], { month: 'short', day: 'numeric' });
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
    <div className="rounded-xl p-3 border border-red-500/15 bg-red-500/[0.04] max-w-sm">
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

// ── Inline Content Renderer — Beautiful Markdown ──────────────────

function isEmojiChar(ch: string): boolean {
  const code = ch.codePointAt(0) || 0;
  return (code >= 0x1F300 && code <= 0x1FAFF) || (code >= 0x2600 && code <= 0x27BF) || (code >= 0xFE00 && code <= 0xFE0F);
}

/**
 * Renders AI message content in a beautiful, structured way:
 * - Opening line: Large, bold, eye-catching
 * - Bullet points: With orange chevron markers and proper spacing
 * - Numbered lists: With subtle orange numbers
 * - Emoji lines: Preserved as-is with proper layout
 * - Regular text: Clean and readable
 */
function renderAIContent(content: string) {
  // Pre-process: split lines that have multiple bullet markers jammed together
  const preprocessed = content.split('\n').flatMap((line) => {
    const trimmed = line.trim();
    if (!trimmed) return [line];
    const bulletMatches = trimmed.match(/[\u2022\-*•]\s/g);
    if (bulletMatches && bulletMatches.length >= 2) {
      return trimmed.split(/(?=[\u2022\-*•]\s)/).filter(Boolean);
    }
    return [line];
  });

  const lines = preprocessed;
  let openerUsed = false;
  let inList = false;

  return lines.map((line, index) => {
    const trimmed = line.trim();
    if (!trimmed) {
      // Empty line = spacing between sections
      if (inList) { inList = false; return <div key={index} className="h-1.5" />; }
      return <div key={index} className="h-1" />;
    }

    // Detect line type
    const isEmoji = isEmojiChar(trimmed);
    const isBullet = /^[\u2022\-*•]\s/.test(trimmed);
    const isNumbered = /^[0-9]+[.)]\s/.test(trimmed);
    const isOpener = !openerUsed && !isBullet && !isNumbered && !isEmoji && trimmed.length < 100;

    // ── Opening line: bold, larger, eye-catching ──
    if (isOpener) {
      openerUsed = true;
      return (
        <p key={index} className="text-white font-semibold text-[15px] leading-relaxed mb-0.5">
          {processBold(trimmed)}
        </p>
      );
    }

    // ── Bullet point lines ──
    if (isBullet) {
      inList = true;
      const displayText = trimmed.replace(/^[\u2022\-*•]\s*/, '');
      return (
        <div key={index} className="flex items-start gap-2.5 py-0.5 pl-0.5">
          <span className="text-orange-400/80 shrink-0 mt-[3px] text-[10px]">&#9656;</span>
          <span className="text-white/85 leading-relaxed text-[13.5px]">
            {processBold(displayText)}
          </span>
        </div>
      );
    }

    // ── Numbered list lines ──
    if (isNumbered) {
      inList = true;
      const numMatch = trimmed.match(/^([0-9]+)[.)]\s*(.*)/);
      const num = numMatch ? numMatch[1] : '1';
      const displayText = numMatch ? numMatch[2] : trimmed.replace(/^[0-9]+[.)]\s*/, '');
      return (
        <div key={index} className="flex items-start gap-2.5 py-0.5 pl-0.5">
          <span className="text-orange-400/70 shrink-0 mt-[2px] text-[11px] font-medium min-w-[16px]">{num}.</span>
          <span className="text-white/85 leading-relaxed text-[13.5px]">
            {processBold(displayText)}
          </span>
        </div>
      );
    }

    // ── Emoji-prefixed lines ──
    if (isEmoji) {
      inList = true;
      return (
        <div key={index} className="flex items-start gap-2 py-0.5 pl-0.5">
          <span className="shrink-0 text-[14px] leading-relaxed">{trimmed.charAt(0)}</span>
          <span className="text-white/85 leading-relaxed text-[13.5px]">
            {processBold(trimmed.slice(trimmed.charAt(0).length).trim())}
          </span>
        </div>
      );
    }

    // ── Regular paragraph text ──
    inList = false;
    return (
      <p key={index} className="text-white/75 text-[13.5px] leading-relaxed">
        {processBold(trimmed)}
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
      className={`flex items-end gap-2.5 px-4 py-2 chat-msg-reveal ${
        isUser ? 'flex-row-reverse' : ''
      }`}
    >
      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center shrink-0 text-white font-bold text-xs shadow-sm shadow-orange-500/15">
        J
      </div>
      <div className="max-w-[80%]">
        {children}
        {message.timestamp && (
          <p className="text-[10px] mt-1 px-1 text-white/20">
            {formatRelativeTime(message.timestamp)}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────

export function ChatMessage({ message, onRetry, hookActions, sessionState, isConsecutive }: ChatMessageProps) {
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

    // ── Integration Setup Cards ──────────────────────────────────

    case 'provider_selector': {
      const ia = hookActions?.integrationActions;
      return (
        <CardWrapper message={message} isUser={false}>
          <ProviderSelectorCard
            category={(metadata.category as ProviderSelectorCardProps['category']) || 'email'}
            providers={(metadata.providers as ProviderInfoType[]) || []}
            onSelect={(providerType: string) => {
              ia?.testConnection(providerType, metadata.category || '', {});
            }}
            onSkip={() => ia?.skipIntegration(metadata.category as string || '')}
          />
        </CardWrapper>
      );
    }

    case 'api_key_input': {
      const ia = hookActions?.integrationActions;
      const providerType = metadata.detected_provider?.provider_type || (metadata.provider_type as string);
      const category = metadata.category || '';
      return (
        <CardWrapper message={message} isUser={false}>
          <ApiKeyInputCard
            category={category}
            providerType={providerType}
            onDetect={async (apiKey: string) => {
              const result = await ia!.detectProvider(apiKey);
              return {
                providerType: result.provider_type,
                providerName: result.name,
                icon: undefined,
                confidence: result.confidence,
              };
            }}
            onTest={async (credentials: Record<string, unknown>) => {
              const result = await ia!.testConnection(
                providerType || 'unknown',
                category,
                credentials as Record<string, string>,
              );
              return {
                success: result.success,
                message: result.message,
                details: result.provider_info as Record<string, unknown>,
              };
            }}
            onConnect={(credentials: Record<string, unknown>) => {
              ia?.connectIntegration(
                providerType || 'unknown',
                category,
                credentials as Record<string, string>,
              );
            }}
            onSkip={() => ia?.skipIntegration(category)}
          />
        </CardWrapper>
      );
    }

    case 'connection_status': {
      const ia = hookActions?.integrationActions;
      const conn = metadata.connection;
      return (
        <CardWrapper message={message} isUser={false}>
          <ConnectionStatusCard
            providerName={conn?.provider_name || ''}
            status={conn?.status || 'disconnected'}
            errorMessage={conn?.error_message}
            troubleshootingSteps={metadata.troubleshooting_steps}
            onDisconnect={() => ia?.disconnectIntegration(conn?.id || '')}
            onRetry={() => ia?.testConnection(conn?.provider_type || '', conn?.category || '', {})}
          />
        </CardWrapper>
      );
    }

    case 'connection_error': {
      const ia = hookActions?.integrationActions;
      const conn = metadata.connection;
      return (
        <CardWrapper message={message} isUser={false}>
          <ConnectionErrorCard
            errorMessage={conn?.error_message || message.content}
            commonFixes={metadata.troubleshooting_steps}
            onRetry={() => ia?.testConnection(conn?.provider_type || '', conn?.category || '', {})}
            onSkip={() => ia?.skipIntegration(conn?.category || '')}
          />
        </CardWrapper>
      );
    }

    case 'integration_summary': {
      const ia = hookActions?.integrationActions;
      return (
        <CardWrapper message={message} isUser={false}>
          <IntegrationSummaryCard
            connected={(metadata.connected || []).map((c) => ({
              category: c.category,
              provider: c.provider_name,
              status: c.status,
            }))}
            skipped={(metadata.skipped || []).map((s) => ({
              category: s.category,
            }))}
            industry={metadata.industry || ''}
            onAddMore={() => {}}
            onContinue={() => {}}
          />
        </CardWrapper>
      );
    }

    case 'industry_suggestion': {
      const ia = hookActions?.integrationActions;
      const rawSuggestions = metadata.suggestions || [];
      const flatSuggestions = rawSuggestions.flatMap((group) =>
        (group.providers || []).map((p) => ({
          providerType: p.type,
          providerName: p.name,
          category: group.category,
          icon: p.icon,
        }))
      );
      return (
        <CardWrapper message={message} isUser={false}>
          <IndustrySuggestionCard
            industry={metadata.industry || ''}
            suggestions={flatSuggestions}
            onSelectSuggestion={(providerType: string, category: string) => {
              ia?.testConnection(providerType, category, {});
            }}
            onDismiss={() => ia?.skipIntegration('')}
          />
        </CardWrapper>
      );
    }

    // ── Standard text message — ZAI-STYLE CLEAN DESIGN ─────────
    default: {
      // ── USER MESSAGE: Clean gradient bubble, right-aligned ──
      if (isUser) {
        return (
          <div className="flex justify-end px-4 py-1.5 chat-msg-reveal">
            <div className="max-w-[75%] flex flex-col items-end">
              <div className="rounded-2xl rounded-br-md px-4 py-2.5 bg-gradient-to-br from-orange-500/90 to-orange-600/90 text-white text-[14px] leading-relaxed shadow-md shadow-orange-500/10">
                <p className="whitespace-pre-wrap break-words">{message.content}</p>
              </div>
              {message.timestamp && (
                <p className="text-[10px] mt-0.5 px-1 text-white/20">
                  {formatRelativeTime(message.timestamp)}
                </p>
              )}
            </div>
          </div>
        );
      }

      // ── AI MESSAGE: Clean, open text — no WhatsApp boxes ──
      // Like ZAI: avatar + clean formatted text, no box background
      return (
        <div className="px-4 py-1.5 chat-msg-reveal">
          <div className="flex items-start gap-2.5 max-w-[90%]">
            {/* Avatar — only show for first message in a group */}
            {!isConsecutive ? (
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center shrink-0 text-white font-bold text-[10px] shadow-sm shadow-orange-500/15 mt-0.5">
                J
              </div>
            ) : (
              <div className="w-7 shrink-0" />
            )}

            {/* Content — clean, no box */}
            <div className="flex-1 min-w-0">
              <div className="space-y-0.5">
                {renderAIContent(message.content)}
              </div>
              {message.timestamp && (
                <p className="text-[10px] mt-1 text-white/20">
                  {formatRelativeTime(message.timestamp)}
                </p>
              )}
            </div>
          </div>
        </div>
      );
    }
  }
}
