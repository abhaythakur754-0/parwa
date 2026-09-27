/**
 * JarvisAwarenessFeed — Real-time feed of proactive alerts
 *
 * Shows color-coded alerts with severity, action buttons, and filtering.
 */

'use client';

import React, { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { AlertCard } from './AlertCard';
import type { ProactiveAlert, AlertSeverity, AlertCategory } from '@/types/jarvis-cc';

export interface JarvisAwarenessFeedProps {
  alerts: ProactiveAlert[];
  onAcknowledge?: (alertId: string) => void;
  onDismiss?: (alertId: string) => void;
  onResolve?: (alertId: string) => void;
  className?: string;
}

const SEVERITY_FILTERS: Array<{ value: AlertSeverity | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'emergency', label: 'Emergency' },
  { value: 'critical', label: 'Critical' },
  { value: 'warning', label: 'Warning' },
  { value: 'info', label: 'Info' },
];

const CATEGORY_FILTERS: Array<{ value: AlertCategory | 'all'; label: string }> = [
  { value: 'all', label: 'All Categories' },
  { value: 'system_health', label: 'System' },
  { value: 'ticket_volume', label: 'Volume' },
  { value: 'agent_pool', label: 'Agents' },
  { value: 'quality', label: 'Quality' },
  { value: 'drift', label: 'Drift' },
  { value: 'billing', label: 'Billing' },
  { value: 'security', label: 'Security' },
];

export function JarvisAwarenessFeed({ alerts, onAcknowledge, onDismiss, onResolve, className }: JarvisAwarenessFeedProps) {
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | 'all'>('all');
  const [categoryFilter, setCategoryFilter] = useState<AlertCategory | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<'active' | 'all'>('active');

  const filteredAlerts = useMemo(() => {
    return alerts.filter(a => {
      if (severityFilter !== 'all' && a.severity !== severityFilter) return false;
      if (categoryFilter !== 'all' && a.category !== categoryFilter) return false;
      if (statusFilter === 'active' && a.status !== 'active' && a.status !== 'acknowledged') return false;
      return true;
    });
  }, [alerts, severityFilter, categoryFilter, statusFilter]);

  const activeCount = alerts.filter(a => a.status === 'active').length;
  const criticalCount = alerts.filter(a => a.severity === 'critical' || a.severity === 'emergency').length;

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-1 mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-white">Awareness Feed</h3>
          {activeCount > 0 && (
            <span className={cn(
              'text-[10px] font-bold px-1.5 py-0.5 rounded-full',
              criticalCount > 0 ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400'
            )}>
              {activeCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setStatusFilter(statusFilter === 'active' ? 'all' : 'active')}
            className={cn(
              'text-[10px] px-2 py-0.5 rounded transition-colors',
              statusFilter === 'active' ? 'bg-orange-500/20 text-orange-400' : 'bg-white/5 text-zinc-500'
            )}
          >
            {statusFilter === 'active' ? 'Active' : 'All'}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-1 mb-3 overflow-x-auto pb-1 scrollbar-none">
        {SEVERITY_FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => setSeverityFilter(f.value)}
            className={cn(
              'text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap transition-colors shrink-0',
              severityFilter === f.value
                ? 'bg-white/10 text-white'
                : 'text-zinc-500 hover:text-zinc-300'
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Alert list */}
      <div className="flex-1 overflow-y-auto space-y-2 scrollbar-premium">
        {filteredAlerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-zinc-600">
            <svg className="w-8 h-8 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
            <p className="text-xs">No active alerts</p>
            <p className="text-[10px] text-zinc-700">System is running smoothly</p>
          </div>
        ) : (
          filteredAlerts.map(alert => (
            <AlertCard
              key={alert.id}
              alert={alert}
              onAcknowledge={onAcknowledge}
              onDismiss={onDismiss}
              onResolve={onResolve}
              compact
            />
          ))
        )}
      </div>
    </div>
  );
}
