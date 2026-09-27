/**
 * CCChatMessage — Message bubble for Jarvis CC chat
 *
 * Supports customer care message types: text, command_response, proactive_alert, variant_pipeline, error
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { JarvisCCMessage, CCMessageType, PipelineMetadata } from '@/types/jarvis-cc';

/**
 * Map backend variant tier identifiers to user-facing display labels.
 * Legacy "mini_parwa" / "mini" values auto-upgrade to "PARWA" display
 * (Mini PARWA was removed on 2026-07-26 — only 2 tiers remain).
 */
function formatTierLabel(tier: string): string {
  const t = (tier || '').toLowerCase().trim();
  if (t === 'parwa_high' || t === 'high' || t === 'high-parwa') return 'PARWA High';
  if (t === 'parwa' || t === 'mini_parwa' || t === 'mini' || t === 'starter' || t === 'growth') return 'PARWA';
  return tier.replace('_', ' ');
}

export interface CCChatMessageProps {
  message: JarvisCCMessage;
  onUndoCommand?: (commandId: string) => void;
  className?: string;
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function renderContent(content: string): React.ReactNode {
  // Handle bullet points
  const lines = content.split('\n');
  return (
    <>
      {lines.map((line, i) => {
        const trimmed = line.trim();
        if (trimmed.startsWith('• ') || trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          return (
            <div key={i} className="flex gap-1.5 ml-1">
              <span className="text-zinc-600 shrink-0">•</span>
              <span>{renderInline(trimmed.slice(2))}</span>
            </div>
          );
        }
        if (trimmed === '') return <br key={i} />;
        return <div key={i}>{renderInline(trimmed)}</div>;
      })}
    </>
  );
}

function renderInline(text: string): React.ReactNode {
  // Bold: **text**
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

function MessageTypeBadge({ type }: { type: CCMessageType }) {
  const styles: Record<string, string> = {
    command_response: 'text-orange-400 bg-orange-500/10',
    proactive_alert: 'text-red-400 bg-red-500/10',
    variant_pipeline: 'text-purple-400 bg-purple-500/10',
    ai_generated: 'text-emerald-400 bg-emerald-500/10',
    error: 'text-red-400 bg-red-500/10',
    direct_ai: 'text-blue-400 bg-blue-500/10',
  };

  const labels: Record<string, string> = {
    command_response: 'Command',
    proactive_alert: 'Alert',
    variant_pipeline: 'Pipeline',
    ai_generated: 'AI',
    error: 'Error',
    direct_ai: 'Direct AI',
  };

  if (type === 'text') return null;

  return (
    <span className={cn('text-[9px] font-medium px-1.5 py-0.5 rounded-full', styles[type] || 'text-zinc-500 bg-zinc-500/10')}>
      {labels[type] || type}
    </span>
  );
}

function PipelineInfo({ metadata }: { metadata: PipelineMetadata }) {
  const qualityPct = metadata.quality_score !== undefined && metadata.quality_score !== null
    ? Math.round(metadata.quality_score * 100)
    : null;
  const qualityColor = qualityPct !== null
    ? (qualityPct >= 80 ? 'text-emerald-400' : qualityPct >= 60 ? 'text-amber-400' : 'text-rose-400')
    : '';
  const qualityBarColor = qualityPct !== null
    ? (qualityPct >= 80 ? 'bg-emerald-500' : qualityPct >= 60 ? 'bg-amber-500' : 'bg-rose-500')
    : '';

  return (
    <div className="mt-2.5 pt-2.5 border-t border-white/[0.06]">
      <div className="flex items-center gap-1.5 mb-2">
        <svg className="w-3 h-3 text-violet-400/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c.251.023.501.05.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6.23-.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0 1 12 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
        </svg>
        <span className="text-[9px] font-semibold uppercase tracking-wider text-zinc-500">Pipeline Metrics</span>
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[10px]">
        {metadata.technique_used && (
          <div className="flex items-center gap-1">
            <span className="text-zinc-600">Technique:</span>
            <span className="text-zinc-300 font-medium">{metadata.technique_used}</span>
          </div>
        )}
        {qualityPct !== null && (
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-1">
              <span className="text-zinc-600">Quality:</span>
              <span className={cn('font-semibold', qualityColor)}>{qualityPct}%</span>
            </div>
            <div className="h-1 rounded-full bg-white/[0.06] overflow-hidden">
              <div className={cn('h-full rounded-full transition-all', qualityBarColor)} style={{ width: `${qualityPct}%` }} />
            </div>
          </div>
        )}
        {metadata.latency_ms !== undefined && metadata.latency_ms !== null && (
          <div className="flex items-center gap-1">
            <span className="text-zinc-600">Latency:</span>
            <span className="text-zinc-300 font-medium">{metadata.latency_ms}ms</span>
          </div>
        )}
        {metadata.variant_tier && (
          <div className="flex items-center gap-1">
            <span className="text-zinc-600">Tier:</span>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-violet-500/10 border border-violet-500/20 text-violet-300 font-semibold text-[9px]">
              {formatTierLabel(metadata.variant_tier)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export function CCChatMessage({ message, onUndoCommand, className }: CCChatMessageProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const isCommandResponse = message.message_type === 'command_response';
  const isAlert = message.message_type === 'proactive_alert';
  const commandId = message.metadata?.command_id as string | undefined;
  const undoAvailable = message.metadata?.undo_available as boolean | undefined;
  const pipelineMeta = message.pipeline_metadata;

  return (
    <div className={cn('flex gap-2.5 group', isUser ? 'flex-row-reverse' : '', className)}>
      {/* Avatar */}
      {!isUser && (
        <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center text-white text-[10px] font-bold shadow-lg shadow-orange-500/20 mt-0.5">
          J
        </div>
      )}

      {/* Message bubble */}
      <div className={cn(
        'max-w-[80%] rounded-2xl px-3.5 py-2.5',
        isUser
          ? 'bg-orange-500 text-white rounded-tr-md'
          : isAlert
          ? 'bg-red-500/10 border border-red-500/20 text-zinc-300 rounded-tl-md'
          : 'bg-[#222222] text-zinc-300 rounded-tl-md'
      )}>
        {/* Type badge + timestamp */}
        <div className={cn('flex items-center gap-2 mb-1', isUser && 'justify-end')}>
          <MessageTypeBadge type={message.message_type} />
          <span className="text-[10px] text-zinc-600">{formatTimestamp(message.timestamp)}</span>
        </div>

        {/* Content */}
        <div className={cn('text-sm leading-relaxed', isUser ? 'text-white' : '')}>
          {renderContent(message.content)}
        </div>

        {/* Pipeline metadata */}
        {pipelineMeta && <PipelineInfo metadata={pipelineMeta} />}

        {/* Command actions */}
        {isCommandResponse && undoAvailable && commandId && onUndoCommand && (
          <div className="mt-2 pt-1 border-t border-white/[0.06]">
            <button
              onClick={() => onUndoCommand(commandId)}
              className="text-[10px] text-zinc-500 hover:text-orange-400 transition-colors"
            >
              ↩ Undo
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
