'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { Ticket, TicketSentiment, GSDState, AITechnique } from '@/types/ticket';
import ConfidenceBar from './ConfidenceBar';
import GSDStateIndicator from './GSDStateIndicator';

interface TicketMetadataProps {
  ticket: Ticket;
  className?: string;
}

const sentimentConfig: Record<TicketSentiment, { label: string; color: string; bg: string; emoji: string }> = {
  positive: { label: 'Positive', color: 'text-emerald-400', bg: 'bg-emerald-500/15', emoji: '😊' },
  neutral: { label: 'Neutral', color: 'text-zinc-400', bg: 'bg-zinc-500/15', emoji: '😐' },
  negative: { label: 'Negative', color: 'text-red-400', bg: 'bg-red-500/15', emoji: '😤' },
  mixed: { label: 'Mixed', color: 'text-amber-400', bg: 'bg-amber-500/15', emoji: '😕' },
};

const techniqueLabels: Record<AITechnique, { label: string; description: string }> = {
  knowledge_base: { label: 'Knowledge Base', description: 'Matched response from KB articles' },
  sentiment_match: { label: 'Sentiment Match', description: 'Adjusted tone based on sentiment analysis' },
  intent_classification: { label: 'Intent Classification', description: 'Classified intent to determine response' },
  entity_extraction: { label: 'Entity Extraction', description: 'Extracted key entities from query' },
  conversation_flow: { label: 'Conversation Flow', description: 'Following guided conversation flow' },
  escalation_trigger: { label: 'Escalation Trigger', description: 'Triggered human escalation rules' },
  template_response: { label: 'Template Response', description: 'Used pre-built response template' },
  fallback: { label: 'Fallback', description: 'Default response when confidence is low' },
};

function formatMinutes(mins: number | null): string {
  if (mins === null) return '—';
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function MetadataItem({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('py-2.5 flex flex-col gap-1', className)}>
      <span className="text-[10px] font-semibold text-zinc-600 uppercase tracking-wider">{label}</span>
      {children}
    </div>
  );
}

export default function TicketMetadata({ ticket, className }: TicketMetadataProps) {
  const sentiment = sentimentConfig[ticket.sentiment];
  const technique = techniqueLabels[ticket.ai_technique];

  return (
    <div className={cn('rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden', className)}>
      <div className="px-4 py-3 border-b border-white/[0.06]">
        <h3 className="text-xs font-semibold text-zinc-300">Ticket Metadata</h3>
      </div>

      <div className="p-4 space-y-0 divide-y divide-white/[0.04]">
        {/* Channel */}
        <MetadataItem label="Channel">
          <span className="text-sm text-zinc-300 capitalize">{ticket.channel}</span>
        </MetadataItem>

        {/* Assigned Agent */}
        <MetadataItem label="Assigned Agent">
          {ticket.assigned_agent ? (
            <div className="flex items-center gap-2">
              <div className={cn(
                'w-5 h-5 rounded-full bg-gradient-to-br from-emerald-500 to-teal-400 flex items-center justify-center text-[9px] font-bold text-white',
              )}>
                {ticket.assigned_agent.name.charAt(0)}
              </div>
              <span className="text-sm text-zinc-300">{ticket.assigned_agent.name}</span>
              <div className={cn(
                'w-1.5 h-1.5 rounded-full',
                ticket.assigned_agent.is_online ? 'bg-emerald-400' : 'bg-zinc-600'
              )} />
            </div>
          ) : (
            <span className="text-sm text-zinc-600">Unassigned</span>
          )}
        </MetadataItem>

        {/* AI Variant */}
        {ticket.variant_name && (
          <MetadataItem label="AI Variant">
            <div className="flex items-center gap-1.5">
              <span className="px-2 py-0.5 rounded-md bg-orange-500/10 text-orange-400 text-[11px] font-medium border border-orange-500/15">
                {ticket.variant_name}
              </span>
            </div>
          </MetadataItem>
        )}

        {/* AI Confidence */}
        <MetadataItem label="AI Confidence">
          <ConfidenceBar value={ticket.ai_confidence} size="md" className="w-full" />
        </MetadataItem>

        {/* Sentiment */}
        <MetadataItem label="Customer Sentiment">
          <div className="flex items-center gap-2">
            <span className="text-lg">{sentiment.emoji}</span>
            <span className={cn('text-sm font-medium', sentiment.color)}>{sentiment.label}</span>
          </div>
        </MetadataItem>

        {/* Resolution Time */}
        <MetadataItem label="Resolution Time">
          <span className="text-sm text-zinc-300">{formatMinutes(ticket.resolution_time_minutes)}</span>
        </MetadataItem>

        {/* First Response */}
        <MetadataItem label="First Response Time">
          <span className="text-sm text-zinc-300">{formatMinutes(ticket.first_response_time_minutes)}</span>
        </MetadataItem>

        {/* GSD State */}
        <MetadataItem label="GSD State">
          <GSDStateIndicator currentState={ticket.gsd_state} />
        </MetadataItem>

        {/* AI Technique */}
        <MetadataItem label="AI Technique">
          <div>
            <span className="text-sm text-zinc-300 block">{technique.label}</span>
            <span className="text-[10px] text-zinc-600">{technique.description}</span>
          </div>
        </MetadataItem>

        {/* SLA */}
        <MetadataItem label="SLA Deadline">
          {ticket.sla_deadline ? (
            <span className="text-sm text-zinc-300">
              {new Date(ticket.sla_deadline).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
            </span>
          ) : (
            <span className="text-sm text-zinc-600">No SLA</span>
          )}
        </MetadataItem>

        {/* AI Resolved */}
        <MetadataItem label="Resolution Method">
          {ticket.is_ai_resolved ? (
            <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 text-[11px] font-medium border border-emerald-500/15">
              AI Auto-Resolved
            </span>
          ) : (
            <span className="text-sm text-zinc-500">Human Agent</span>
          )}
        </MetadataItem>

        {/* Tags */}
        {ticket.tags.length > 0 && (
          <MetadataItem label="Tags">
            <div className="flex flex-wrap gap-1">
              {ticket.tags.map((tag) => (
                <span key={tag} className="px-2 py-0.5 rounded-md bg-white/[0.04] border border-white/[0.06] text-[10px] text-zinc-400">
                  {tag}
                </span>
              ))}
            </div>
          </MetadataItem>
        )}
      </div>
    </div>
  );
}
