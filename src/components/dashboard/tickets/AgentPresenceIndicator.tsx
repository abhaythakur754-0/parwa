/**
 * PARWA Agent Presence Indicator Component
 *
 * Shows real-time online/offline status for agents.
 * Supports presence badges, status indicators, and typing states.
 *
 * Day 7 — Real-time Updates & Dashboard Integration
 */

'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useSocket } from '@/contexts/SocketContext';

// ── Types ─────────────────────────────────────────────────────────────────

export type PresenceStatus = 'online' | 'away' | 'busy' | 'offline';

export interface AgentPresence {
  agent_id: string;
  agent_name: string;
  avatar_url?: string;
  status: PresenceStatus;
  last_seen_at?: string;
  current_ticket_id?: string;
  is_typing?: boolean;
  typing_ticket_id?: string;
}

interface AgentPresenceIndicatorProps {
  /** Agent ID to show presence for */
  agentId: string;
  /** Agent name for fallback display */
  agentName?: string;
  /** Agent avatar URL */
  avatarUrl?: string;
  /** Size of the indicator */
  size?: 'xs' | 'sm' | 'md' | 'lg';
  /** Show status label text */
  showLabel?: boolean;
  /** Show typing indicator */
  showTyping?: boolean;
  /** Compact mode (just the dot) */
  compact?: boolean;
  /** Additional CSS classes */
  className?: string;
}

interface AgentPresenceListProps {
  /** List of agent IDs to show */
  agentIds?: string[];
  /** Title for the list */
  title?: string;
  /** Maximum agents to show before "+N more" */
  maxVisible?: number;
  /** Show agents currently online only */
  onlineOnly?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Callback when agent is clicked */
  onAgentClick?: (agent: AgentPresence) => void;
}

// ── Presence Context ──────────────────────────────────────────────────────

interface PresenceContextValue {
  presences: Map<string, AgentPresence>;
  updatePresence: (agentId: string, presence: Partial<AgentPresence>) => void;
}

const PresenceContext = React.createContext<PresenceContextValue | null>(null);

// ── Size Config ───────────────────────────────────────────────────────────

const SIZE_CONFIG: Record<
  string,
  { avatar: string; dot: string; dotOffset: string; label: string }
> = {
  xs: { avatar: 'w-5 h-5', dot: 'w-1.5 h-1.5', dotOffset: '-bottom-0 -right-0', label: 'text-[10px]' },
  sm: { avatar: 'w-6 h-6', dot: 'w-2 h-2', dotOffset: '-bottom-0.5 -right-0.5', label: 'text-xs' },
  md: { avatar: 'w-8 h-8', dot: 'w-2.5 h-2.5', dotOffset: '-bottom-0.5 -right-0.5', label: 'text-sm' },
  lg: { avatar: 'w-10 h-10', dot: 'w-3 h-3', dotOffset: '-bottom-1 -right-1', label: 'text-base' },
};

// ── Status Config ─────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<
  PresenceStatus,
  { color: string; bgColor: string; label: string; ringColor?: string }
> = {
  online: {
    color: 'bg-emerald-500',
    bgColor: 'bg-emerald-500/15',
    label: 'Online',
    ringColor: 'ring-emerald-500/30',
  },
  away: {
    color: 'bg-amber-500',
    bgColor: 'bg-amber-500/15',
    label: 'Away',
    ringColor: 'ring-amber-500/30',
  },
  busy: {
    color: 'bg-red-500',
    bgColor: 'bg-red-500/15',
    label: 'Busy',
    ringColor: 'ring-red-500/30',
  },
  offline: {
    color: 'bg-zinc-500',
    bgColor: 'bg-zinc-500/15',
    label: 'Offline',
  },
};

// ── Typing Indicator ──────────────────────────────────────────────────────

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-0.5 ml-1">
      <span className="w-1 h-1 rounded-full bg-current animate-[bounce_1s_infinite_0ms]" />
      <span className="w-1 h-1 rounded-full bg-current animate-[bounce_1s_infinite_150ms]" />
      <span className="w-1 h-1 rounded-full bg-current animate-[bounce_1s_infinite_300ms]" />
    </span>
  );
}

// ── Presence Dot Component ────────────────────────────────────────────────

interface PresenceDotProps {
  status: PresenceStatus;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  animate?: boolean;
  className?: string;
}

export function PresenceDot({ status, size = 'sm', animate = true, className }: PresenceDotProps) {
  const config = STATUS_CONFIG[status];
  const sizeConfig = SIZE_CONFIG[size];

  return (
    <span
      className={cn(
        'rounded-full border-2 border-[#1A1A1A]',
        config.color,
        sizeConfig.dot,
        animate && status === 'online' && 'animate-pulse',
        className
      )}
      title={config.label}
    />
  );
}

// ── Agent Presence Indicator ──────────────────────────────────────────────

export function AgentPresenceIndicator({
  agentId,
  agentName,
  avatarUrl,
  size = 'md',
  showLabel = false,
  showTyping = true,
  compact = false,
  className,
}: AgentPresenceIndicatorProps) {
  const { socket, isConnected } = useSocket();
  const [presence, setPresence] = useState<AgentPresence>({
    agent_id: agentId,
    agent_name: agentName || 'Agent',
    avatar_url: avatarUrl,
    status: 'offline',
  });

  // Subscribe to presence updates
  useEffect(() => {
    if (!socket || !isConnected) return;

    // Request presence for this agent
    socket.emit('presence:get', { agent_id: agentId });

    // Listen for presence updates
    const handlePresenceUpdate = (data: AgentPresence) => {
      if (data.agent_id === agentId) {
        setPresence(data);
      }
    };

    socket.on('presence:update', handlePresenceUpdate);

    return () => {
      socket.off('presence:update', handlePresenceUpdate);
    };
  }, [socket, isConnected, agentId]);

  // Update local state when props change
  useEffect(() => {
    setPresence((prev) => ({
      ...prev,
      agent_name: agentName || prev.agent_name,
      avatar_url: avatarUrl || prev.avatar_url,
    }));
  }, [agentName, avatarUrl]);

  const config = STATUS_CONFIG[presence.status];
  const sizeConfig = SIZE_CONFIG[size];

  // Compact mode - just show dot
  if (compact) {
    return (
      <span className={cn('relative inline-flex', className)}>
        <PresenceDot status={presence.status} size={size} />
        {showTyping && presence.is_typing && (
          <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
        )}
      </span>
    );
  }

  // Avatar with presence dot
  return (
    <div className={cn('inline-flex items-center gap-2', className)}>
      <div className="relative">
        <Avatar className={cn(sizeConfig.avatar)}>
          {presence.avatar_url && <AvatarImage src={presence.avatar_url} alt={presence.agent_name} />}
          <AvatarFallback
            className={cn(
              'text-xs font-medium',
              presence.status !== 'offline' && config.bgColor
            )}
          >
            {presence.agent_name
              .split(' ')
              .map((n) => n[0])
              .join('')
              .toUpperCase()
              .slice(0, 2)}
          </AvatarFallback>
        </Avatar>

        {/* Status dot */}
        <span
          className={cn(
            'absolute rounded-full border-2 border-[#1A1A1A]',
            config.color,
            sizeConfig.dot,
            sizeConfig.dotOffset,
            presence.status === 'online' && 'animate-pulse'
          )}
        />

        {/* Typing indicator */}
        {showTyping && presence.is_typing && (
          <span className="absolute -top-1 -right-1 px-1 rounded bg-blue-500 text-[8px] font-bold text-white">
            ...
          </span>
        )}
      </div>

      {/* Name and status */}
      {showLabel && (
        <div className="flex flex-col">
          <span className={cn('font-medium text-zinc-200', sizeConfig.label)}>
            {presence.agent_name}
          </span>
          <span className={cn('text-zinc-500', size === 'lg' ? 'text-xs' : 'text-[10px]')}>
            {presence.is_typing ? (
              <span className="text-blue-400">
                typing<TypingDots />
              </span>
            ) : (
              config.label
            )}
          </span>
        </div>
      )}
    </div>
  );
}

// ── Agent Presence List ───────────────────────────────────────────────────

export function AgentPresenceList({
  agentIds,
  title = 'Team',
  maxVisible = 5,
  onlineOnly = false,
  className,
  onAgentClick,
}: AgentPresenceListProps) {
  const { socket, isConnected } = useSocket();
  const [presences, setPresences] = useState<Map<string, AgentPresence>>(new Map());

  // Subscribe to presence updates
  useEffect(() => {
    if (!socket || !isConnected || !agentIds?.length) return;

    // Request presence for all agents
    socket.emit('presence:get_batch', { agent_ids: agentIds });

    // Listen for presence updates
    const handlePresenceUpdate = (data: AgentPresence) => {
      setPresences((prev) => {
        const next = new Map(prev);
        next.set(data.agent_id, data);
        return next;
      });
    };

    const handleBatchUpdate = (data: { presences: AgentPresence[] }) => {
      setPresences((prev) => {
        const next = new Map(prev);
        data.presences.forEach((p) => next.set(p.agent_id, p));
        return next;
      });
    };

    socket.on('presence:update', handlePresenceUpdate);
    socket.on('presence:batch', handleBatchUpdate);

    return () => {
      socket.off('presence:update', handlePresenceUpdate);
      socket.off('presence:batch', handleBatchUpdate);
    };
  }, [socket, isConnected, agentIds]);

  // Convert to array and filter
  const agentsList = useMemo(() => {
    const list = Array.from(presences.values());
    if (onlineOnly) {
      return list.filter((p) => p.status !== 'offline');
    }
    return list;
  }, [presences, onlineOnly]);

  // Count by status
  const statusCounts = useMemo(
    () => ({
      online: agentsList.filter((a) => a.status === 'online').length,
      away: agentsList.filter((a) => a.status === 'away').length,
      busy: agentsList.filter((a) => a.status === 'busy').length,
      offline: agentsList.filter((a) => a.status === 'offline').length,
    }),
    [agentsList]
  );

  // Split visible and hidden
  const visibleAgents = agentsList.slice(0, maxVisible);
  const hiddenCount = agentsList.length - maxVisible;

  return (
    <div className={cn('bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>

        {/* Status counts */}
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-xs text-zinc-500">{statusCounts.online}</span>
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="text-xs text-zinc-500">{statusCounts.away}</span>
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500" />
            <span className="text-xs text-zinc-500">{statusCounts.busy}</span>
          </span>
        </div>
      </div>

      {/* Agent List */}
      <div className="divide-y divide-white/[0.04]">
        {visibleAgents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8">
            <span className="text-xs text-zinc-600">No agents available</span>
          </div>
        ) : (
          visibleAgents.map((agent) => (
            <button
              key={agent.agent_id}
              onClick={() => onAgentClick?.(agent)}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-white/[0.02] transition-colors text-left"
            >
              <AgentPresenceIndicator
                agentId={agent.agent_id}
                agentName={agent.agent_name}
                avatarUrl={agent.avatar_url}
                size="sm"
                showLabel
              />

              {agent.current_ticket_id && (
                <span className="ml-auto text-[10px] text-zinc-600 truncate max-w-[100px]">
                  Working on #{agent.current_ticket_id.slice(0, 6)}
                </span>
              )}
            </button>
          ))
        )}

        {/* More indicator */}
        {hiddenCount > 0 && (
          <div className="px-4 py-2.5 text-xs text-zinc-500 text-center">
            +{hiddenCount} more {hiddenCount === 1 ? 'agent' : 'agents'}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Exports ───────────────────────────────────────────────────────────────

export default AgentPresenceIndicator;
