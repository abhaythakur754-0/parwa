/**
 * JarvisQuickActions — Quick action buttons for common Jarvis operations
 */

'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { QuickCommandItem, CommandIntent } from '@/types/jarvis-cc';

export interface JarvisQuickActionsProps {
  commands: QuickCommandItem[];
  onExecute: (id: string) => void;
  isLoading?: boolean;
  className?: string;
}

const intentColors: Record<string, string> = {
  query: 'text-blue-400 bg-blue-500/10 hover:bg-blue-500/20',
  control: 'text-orange-400 bg-orange-500/10 hover:bg-orange-500/20',
  configure: 'text-purple-400 bg-purple-500/10 hover:bg-purple-500/20',
  report: 'text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20',
  override: 'text-red-400 bg-red-500/10 hover:bg-red-500/20',
};

const intentIcons: Record<string, string> = {
  pause: '⏸️',
  play: '▶️',
  download: '📥',
  'alert-triangle': '⚠️',
  activity: '📊',
  bug: '🐛',
  'x-circle': '❌',
};

export function JarvisQuickActions({ commands, onExecute, isLoading, className }: JarvisQuickActionsProps) {
  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Quick Actions</h3>
        <span className="text-[10px] text-zinc-600">Cmd+K for more</span>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {commands.map(cmd => (
          <button
            key={cmd.id}
            onClick={() => onExecute(cmd.id)}
            disabled={isLoading}
            className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors disabled:opacity-50',
              intentColors[cmd.intent] || 'text-zinc-400 bg-white/5 hover:bg-white/10'
            )}
          >
            <span className="text-sm">{intentIcons[cmd.icon || ''] || '→'}</span>
            <span className="truncate">{cmd.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
