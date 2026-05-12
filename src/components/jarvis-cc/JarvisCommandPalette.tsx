/**
 * JarvisCommandPalette — Cmd+K style command palette
 *
 * Quick actions, auto-complete with available commands, command history.
 */

'use client';

import React, { useState, useMemo, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import type { QuickCommandItem, CommandIntent } from '@/types/jarvis-cc';

export interface JarvisCommandPaletteProps {
  isOpen: boolean;
  query: string;
  onQueryChange: (q: string) => void;
  onClose: () => void;
  quickCommands: QuickCommandItem[];
  onExecuteQuick: (id: string) => void;
  onSendCommand: (rawInput: string) => void;
  recentCommands?: Array<{ raw_input: string; intent: CommandIntent; status: string }>;
  className?: string;
}

const intentIcons: Record<string, string> = {
  query: '🔍',
  control: '⚙️',
  configure: '🔧',
  report: '📊',
  override: '🔀',
};

export function JarvisCommandPalette({
  isOpen,
  query,
  onQueryChange,
  onClose,
  quickCommands,
  onExecuteQuick,
  onSendCommand,
  recentCommands = [],
  className,
}: JarvisCommandPaletteProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Filter quick commands by query
  const filteredCommands = useMemo(() => {
    if (!query.trim()) return quickCommands;
    const q = query.toLowerCase();
    return quickCommands.filter(c =>
      c.label.toLowerCase().includes(q) ||
      c.action.toLowerCase().includes(q) ||
      (c.description || '').toLowerCase().includes(q)
    );
  }, [quickCommands, query]);

  // Combine: quick commands + "send as NL command" option
  const allItems = useMemo(() => {
    const items: Array<{ type: 'quick' | 'custom'; id: string; label: string; description: string | null; intent: CommandIntent; icon: string | null }> = filteredCommands.map(c => ({
      type: 'quick' as const,
      id: c.id,
      label: c.label,
      description: c.description,
      intent: c.intent,
      icon: c.icon,
    }));

    if (query.trim()) {
      items.push({
        type: 'custom',
        id: '__custom__',
        label: `Send: "${query.trim()}"`,
        description: 'Send as natural language command',
        intent: 'query' as CommandIntent,
        icon: null,
      });
    }

    return items;
  }, [filteredCommands, query]);

  // Reset selection when items change
  useEffect(() => {
    setSelectedIndex(0);
  }, [allItems.length]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, allItems.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && allItems[selectedIndex]) {
      e.preventDefault();
      const item = allItems[selectedIndex];
      if (item.type === 'quick') {
        onExecuteQuick(item.id);
      } else {
        onSendCommand(query.trim());
      }
      onClose();
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Palette */}
      <div className={cn(
        'relative w-full max-w-lg bg-[#1A1A1A] border border-white/10 rounded-2xl shadow-2xl shadow-black/50 overflow-hidden',
        className
      )}>
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.06]">
          <svg className="w-4 h-4 text-zinc-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or question..."
            className="flex-1 bg-transparent text-sm text-white placeholder-zinc-600 outline-none"
          />
          <kbd className="text-[10px] text-zinc-600 bg-white/5 px-1.5 py-0.5 rounded">ESC</kbd>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-y-auto p-2 scrollbar-premium">
          {allItems.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-zinc-600 text-sm">
              No matching commands
            </div>
          ) : (
            allItems.map((item, index) => (
              <button
                key={`${item.type}-${item.id}`}
                onClick={() => {
                  if (item.type === 'quick') {
                    onExecuteQuick(item.id);
                  } else {
                    onSendCommand(query.trim());
                  }
                  onClose();
                }}
                onMouseEnter={() => setSelectedIndex(index)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors',
                  index === selectedIndex ? 'bg-white/[0.06] text-white' : 'text-zinc-400 hover:text-zinc-200'
                )}
              >
                <span className="text-sm shrink-0">
                  {item.icon || intentIcons[item.intent] || '→'}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.label}</p>
                  {item.description && (
                    <p className="text-[10px] text-zinc-600 truncate">{item.description}</p>
                  )}
                </div>
                <span className="text-[10px] text-zinc-600 capitalize shrink-0">{item.intent}</span>
              </button>
            ))
          )}
        </div>

        {/* Recent Commands Footer */}
        {recentCommands.length > 0 && !query.trim() && (
          <div className="border-t border-white/[0.06] px-4 py-2">
            <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1">Recent</p>
            <div className="space-y-0.5">
              {recentCommands.slice(0, 3).map((cmd, i) => (
                <button
                  key={i}
                  onClick={() => {
                    onSendCommand(cmd.raw_input);
                    onClose();
                  }}
                  className="w-full text-left text-xs text-zinc-500 hover:text-zinc-300 transition-colors py-0.5 truncate"
                >
                  <span className="text-zinc-600 mr-1">{intentIcons[cmd.intent] || '→'}</span>
                  {cmd.raw_input}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Footer hint */}
        <div className="border-t border-white/[0.06] px-4 py-2 flex items-center gap-4 text-[10px] text-zinc-600">
          <span>↑↓ Navigate</span>
          <span>↵ Select</span>
          <span>Esc Close</span>
          <span className="ml-auto">Cmd+K</span>
        </div>
      </div>
    </div>
  );
}
