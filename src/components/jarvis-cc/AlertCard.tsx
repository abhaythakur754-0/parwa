/**
 * AlertCard — Displays a single proactive alert with severity styling and action buttons
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { ProactiveAlert, AlertSeverity } from '@/types/jarvis-cc';
import { severityColor, severityIcon } from '@/hooks/useJarvisCC';

export interface AlertCardProps {
  alert: ProactiveAlert;
  onAcknowledge?: (alertId: string) => void;
  onDismiss?: (alertId: string) => void;
  onResolve?: (alertId: string) => void;
  compact?: boolean;
  className?: string;
}

export function AlertCard({ alert, onAcknowledge, onDismiss, onResolve, compact = false, className }: AlertCardProps) {
  const sevClass = severityColor(alert.severity);
  const icon = severityIcon(alert.severity);

  const formatTime = (ts: string) => {
    try {
      const d = new Date(ts);
      const now = new Date();
      const diff = now.getTime() - d.getTime();
      if (diff < 60000) return 'Just now';
      if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
      if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
      return d.toLocaleDateString();
    } catch {
      return ts;
    }
  };

  return (
    <div
      className={cn(
        'rounded-lg border p-3 transition-all duration-200',
        sevClass,
        compact ? 'p-2' : 'p-3',
        alert.status === 'acknowledged' && 'opacity-70',
        alert.status === 'resolved' && 'opacity-50',
        className
      )}
    >
      <div className="flex items-start gap-2">
        <span className="text-sm shrink-0 mt-0.5">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h4 className={cn('font-semibold text-sm truncate', compact ? 'text-xs' : 'text-sm')}>
              {alert.title}
            </h4>
            <span className="text-[10px] text-zinc-500 shrink-0">{formatTime(alert.created_at)}</span>
          </div>
          {!compact && (
            <p className="text-xs text-zinc-400 mt-0.5 line-clamp-2">{alert.message}</p>
          )}
          {alert.action_required && alert.status === 'active' && (
            <div className="flex items-center gap-1.5 mt-2">
              {onAcknowledge && (
                <button
                  onClick={() => onAcknowledge(alert.id)}
                  className="text-[10px] px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 transition-colors"
                >
                  Ack
                </button>
              )}
              {onDismiss && (
                <button
                  onClick={() => onDismiss(alert.id)}
                  className="text-[10px] px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 transition-colors"
                >
                  Dismiss
                </button>
              )}
              {onResolve && (
                <button
                  onClick={() => onResolve(alert.id)}
                  className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 transition-colors"
                >
                  Resolve
                </button>
              )}
            </div>
          )}
          {alert.status !== 'active' && (
            <span className="text-[10px] text-zinc-600 mt-1 inline-block capitalize">{alert.status}</span>
          )}
        </div>
      </div>
    </div>
  );
}
