'use client';

import { usePresenceStore } from '@/lib/presence-store';
import type { AgentStatus } from '@/lib/presence-store';

interface AgentPresenceBadgeProps {
  agentId: string;
  showName?: boolean;
  size?: 'sm' | 'md';
}

const statusColors: Record<AgentStatus, string> = {
  available: 'bg-emerald-400',
  busy: 'bg-amber-400',
  away: 'bg-zinc-400',
  offline: 'bg-zinc-600',
};

const statusLabels: Record<AgentStatus, string> = {
  available: 'Available',
  busy: 'Busy',
  away: 'Away',
  offline: 'Offline',
};

export function AgentPresenceBadge({ agentId, showName = true, size = 'md' }: AgentPresenceBadgeProps) {
  const agent = usePresenceStore((s) => s.agents.get(agentId));
  const isOnline = usePresenceStore((s) => s.isOnline(agentId));

  const status: AgentStatus = agent?.status || 'offline';
  const dotSize = size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2';
  const textSize = size === 'sm' ? 'text-[10px]' : 'text-xs';

  return (
    <div className="flex items-center gap-1.5" data-testid={`presence-${agentId}`}>
      <span className="relative flex">
        <span
          className={`${dotSize} rounded-full ${statusColors[status]} ${isOnline ? 'animate-pulse' : ''}`}
          title={statusLabels[status]}
        />
        {isOnline && (
          <span className={`absolute inline-flex h-full w-full rounded-full ${statusColors[status]} opacity-30 animate-ping`} />
        )}
      </span>
      {showName && agent && (
        <span className={`${textSize} text-zinc-400`}>{agent.name}</span>
      )}
    </div>
  );
}
