/**
 * CCChatMessage — Message bubble for Jarvis CC chat
 *
 * Supports customer care message types: text, command_response, proactive_alert, variant_pipeline, error
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { JarvisCCMessage, CCMessageType, PipelineMetadata } from '@/types/jarvis-cc';

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
  return (
    <div className="mt-2 pt-2 border-t border-white/[0.04] grid grid-cols-2 gap-x-3 gap-y-1 text-[10px]">
      {metadata.technique_used && (
        <div><span className="text-zinc-600">Technique:</span> <span className="text-zinc-400">{metadata.technique_used}</span></div>
      )}
      {metadata.quality_score !== undefined && metadata.quality_score !== null && (
        <div><span className="text-zinc-600">Quality:</span> <span className={metadata.quality_score >= 0.7 ? 'text-emerald-400' : 'text-amber-400'}>{Math.round(metadata.quality_score * 100)}%</span></div>
      )}
      {metadata.latency_ms !== undefined && metadata.latency_ms !== null && (
        <div><span className="text-zinc-600">Latency:</span> <span className="text-zinc-400">{metadata.latency_ms}ms</span></div>
      )}
      {metadata.variant_tier && (
        <div><span className="text-zinc-600">Tier:</span> <span className="text-zinc-400 capitalize">{metadata.variant_tier.replace('_', ' ')}</span></div>
      )}
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
