'use client';

import { useJarvisStatus } from '@/hooks/useJarvisStatus';

interface VariantInfo {
  variant: string;
  status: string;
  current_concurrent: number;
  max_concurrent: number;
}

function variantStatusColor(status: string): string {
  switch (status?.toLowerCase()) {
    case 'active':
    case 'running':
      return 'text-jarvis-green';
    case 'idle':
    case 'standby':
      return 'text-jarvis-cyan';
    case 'busy':
      return 'text-jarvis-yellow';
    case 'error':
    case 'down':
      return 'text-jarvis-red';
    default:
      return 'text-jarvis-muted';
  }
}

function variantStatusBadge(status: string): string {
  switch (status?.toLowerCase()) {
    case 'active':
    case 'running':
      return 'jarvis-badge-green';
    case 'idle':
    case 'standby':
      return 'jarvis-badge-cyan';
    case 'busy':
      return 'jarvis-badge-yellow';
    case 'error':
    case 'down':
      return 'jarvis-badge-red';
    default:
      return 'jarvis-badge';
  }
}

function loadBarColor(ratio: number): string {
  if (ratio >= 0.8) return 'bg-jarvis-red';
  if (ratio >= 0.5) return 'bg-jarvis-yellow';
  return 'bg-jarvis-green';
}

export default function ActiveAgents() {
  const { data: status, isLoading } = useJarvisStatus();

  const agents: VariantInfo[] = status?.load_status || [];

  if (isLoading) {
    return (
      <div className="jarvis-card">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase mb-3">Active Agents</h3>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-16 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (agents.length === 0) {
    return (
      <div className="jarvis-card">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase mb-3">Active Agents</h3>
        <div className="text-center py-6 text-jarvis-muted text-sm">
          No agent data available
        </div>
      </div>
    );
  }

  return (
    <div className="jarvis-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase">Active Agents</h3>
        <span className="text-xs text-jarvis-text">{agents.length} variant{agents.length !== 1 ? 's' : ''}</span>
      </div>
      <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
        {agents.map((agent, idx) => {
          const ratio = agent.max_concurrent > 0 ? agent.current_concurrent / agent.max_concurrent : 0;
          const pct = Math.round(ratio * 100);
          return (
            <div
              key={idx}
              className="bg-jarvis-bg/50 rounded-lg p-3 border border-jarvis-border/50 hover:border-jarvis-green/20 transition-all"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`inline-flex w-2 h-2 rounded-full ${
                    agent.status?.toLowerCase() === 'active' || agent.status?.toLowerCase() === 'running'
                      ? 'bg-jarvis-green animate-pulse'
                      : agent.status?.toLowerCase() === 'idle'
                      ? 'bg-jarvis-cyan'
                      : 'bg-jarvis-yellow'
                  }`} />
                  <span className="text-sm font-medium text-jarvis-text">{agent.variant}</span>
                </div>
                <span className={`jarvis-badge ${variantStatusBadge(agent.status)}`}>
                  {agent.status}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 progress-bar">
                  <div
                    className={`progress-bar-fill ${loadBarColor(ratio)}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="text-[10px] text-jarvis-muted tabular-nums min-w-[3.5rem] text-right">
                  {agent.current_concurrent}/{agent.max_concurrent}
                </span>
              </div>
              <div className="text-[10px] text-jarvis-muted mt-1">
                Load: {pct}%
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}