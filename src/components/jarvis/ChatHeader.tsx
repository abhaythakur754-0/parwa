/**
 * PARWA ChatHeader Component (Week 6 — Day 3 Phase 5)
 *
 * Header bar for the Jarvis chat interface.
 * Displays bot avatar with online status, title, and remaining message count.
 */

'use client';

import { Bot, Zap } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface ChatHeaderProps {
  /** Active Jarvis session (null before init completes) */
  session?: {
    detected_stage?: string;
    remaining_today?: number;
    pack_type?: string;
  } | null;
  /** Whether the session is currently loading */
  isLoading?: boolean;
}

/** Stage display labels mapped from backend enum values */
const STAGE_LABELS: Record<string, string> = {
  welcome: 'Getting Started',
  discovery: 'Understanding Needs',
  demo: 'Demo',
  pricing: 'Pricing',
  bill_review: 'Bill Review',
  verification: 'Verification',
  payment: 'Payment',
  handoff: 'Handoff',
};

export function ChatHeader({ session, isLoading }: ChatHeaderProps) {
  const stageLabel = session?.detected_stage
    ? STAGE_LABELS[session.detected_stage] || session.detected_stage
    : null;

  return (
    <header className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-white/[0.03] backdrop-blur-md shrink-0">
      {/* Left — Avatar + Title */}
      <div className="flex items-center gap-3">
        {/* Bot Avatar */}
        <div className="relative">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Bot className="w-5 h-5 text-white" />
          </div>
          {/* Online indicator dot */}
          <div
            className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#022C22] ${
              isLoading
                ? 'bg-amber-400 animate-pulse'
                : 'bg-emerald-400 animate-pulse'
            }`}
          />
        </div>

        <div className="flex flex-col">
          <h1 className="text-sm font-semibold text-white tracking-tight">
            Jarvis — Your AI Assistant
          </h1>
          <p className="text-[11px] text-emerald-400/60 flex items-center gap-1">
            <Zap className="w-3 h-3" />
            {isLoading ? 'Connecting...' : 'Online • Ready to help'}
          </p>
        </div>
      </div>

      {/* Right — Stage badge + remaining count */}
      <div className="flex items-center gap-2">
        {stageLabel && (
          <Badge
            variant="outline"
            className="hidden sm:flex border-emerald-500/20 text-emerald-300/80 text-[11px] font-normal px-2 py-0.5 bg-emerald-500/5"
          >
            {stageLabel}
          </Badge>
        )}

        {!isLoading && session && (
          <Badge
            variant="outline"
            className={`text-[11px] font-normal px-2 py-0.5 ${
              session.pack_type === 'demo'
                ? 'border-amber-500/30 text-amber-300 bg-amber-500/5'
                : session.remaining_today !== undefined && session.remaining_today <= 5
                  ? 'border-red-500/30 text-red-300 bg-red-500/5'
                  : 'border-emerald-500/30 text-emerald-300 bg-emerald-500/5'
            }`}
          >
            {session.remaining_today} msg left
          </Badge>
        )}
      </div>
    </header>
  );
}
