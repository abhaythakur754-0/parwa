/**
 * VariantInstanceCard — Displays variant instance status with real-time metrics
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';

export interface VariantInstanceData {
  id: string;
  name: string;
  tier: 'mini_parwa' | 'parwa' | 'parwa_high';
  status: 'active' | 'idle' | 'error' | 'paused';
  capacity: number;
  activeTickets: number;
  qualityScore: number | null;
  latencyMs: number | null;
}

export interface VariantInstanceCardProps {
  instance: VariantInstanceData;
  onEscalate?: (instanceId: string) => void;
  onRebalance?: (instanceId: string) => void;
  className?: string;
}

const tierColors: Record<string, string> = {
  mini_parwa: 'text-zinc-400 bg-zinc-500/10',
  parwa: 'text-orange-400 bg-orange-500/10',
  parwa_high: 'text-purple-400 bg-purple-500/10',
};

const tierLabels: Record<string, string> = {
  mini_parwa: 'Mini',
  parwa: 'Standard',
  parwa_high: 'High',
};

const statusDots: Record<string, string> = {
  active: 'bg-emerald-400',
  idle: 'bg-zinc-500',
  error: 'bg-red-400',
  paused: 'bg-amber-400',
};

export function VariantInstanceCard({ instance, onEscalate, onRebalance, className }: VariantInstanceCardProps) {
  const utilization = instance.capacity > 0 ? instance.activeTickets / instance.capacity : 0;

  return (
    <div className={cn('rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4 hover:border-white/10 transition-all', className)}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={cn('w-2 h-2 rounded-full', statusDots[instance.status] || 'bg-zinc-500')} />
          <h4 className="text-sm font-semibold text-white">{instance.name}</h4>
        </div>
        <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded-full', tierColors[instance.tier])}>
          {tierLabels[instance.tier]}
        </span>
      </div>

      {/* Utilization bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-xs text-zinc-500 mb-1">
          <span>Utilization</span>
          <span className={cn('font-medium', utilization >= 0.9 ? 'text-red-400' : utilization >= 0.7 ? 'text-amber-400' : 'text-emerald-400')}>
            {Math.round(utilization * 100)}%
          </span>
        </div>
        <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all duration-500',
              utilization >= 0.9 ? 'bg-red-500' : utilization >= 0.7 ? 'bg-amber-500' : 'bg-emerald-500'
            )}
            style={{ width: `${Math.min(utilization * 100, 100)}%` }}
          />
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <span className="text-zinc-600">Tickets</span>
          <p className="text-zinc-300 font-medium">{instance.activeTickets}/{instance.capacity}</p>
        </div>
        <div>
          <span className="text-zinc-600">Quality</span>
          <p className={cn(
            'font-medium',
            instance.qualityScore !== null
              ? instance.qualityScore >= 0.7 ? 'text-emerald-400' : instance.qualityScore >= 0.5 ? 'text-amber-400' : 'text-red-400'
              : 'text-zinc-500'
          )}>
            {instance.qualityScore !== null ? `${Math.round(instance.qualityScore * 100)}%` : '--'}
          </p>
        </div>
        <div>
          <span className="text-zinc-600">Latency</span>
          <p className="text-zinc-300 font-medium">
            {instance.latencyMs !== null ? `${instance.latencyMs}ms` : '--'}
          </p>
        </div>
      </div>

      {/* Actions */}
      {(onEscalate || onRebalance) && (
        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-white/[0.06]">
          {onRebalance && (
            <button
              onClick={() => onRebalance(instance.id)}
              className="text-[10px] px-2.5 py-1 rounded bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Rebalance
            </button>
          )}
          {onEscalate && (
            <button
              onClick={() => onEscalate(instance.id)}
              className="text-[10px] px-2.5 py-1 rounded bg-orange-500/10 hover:bg-orange-500/20 text-orange-400 transition-colors"
            >
              Escalate
            </button>
          )}
        </div>
      )}
    </div>
  );
}
