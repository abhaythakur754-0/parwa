/**
 * Jarvis Customer Care Dashboard Page (/dashboard/jarvis)
 *
 * Full Jarvis CC chat interface with awareness feed, command palette,
 * and Shadow Mode integration.
 */

'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { JarvisCCChat } from '@/components/jarvis-cc/JarvisCCChat';
import { JarvisCommandPalette } from '@/components/jarvis-cc/JarvisCommandPalette';
import { useCommandPalette, useJarvisCCSession, useJarvisCommands } from '@/hooks/useJarvisCC';
import { useShadowMode } from '@/hooks/useShadowMode';
import { toast } from 'sonner';

export default function JarvisCCPage() {
  const { session, createSession, resumeSession } = useJarvisCCSession();
  const { quickCommands, fetchQuickCommands, executeQuickCommand } = useJarvisCommands(session?.id || null);
  const { isOpen, query, setQuery, open, close } = useCommandPalette();
  const { status: shadowStatus, enableShadowMode, disableShadowMode, promoteShadowMode } = useShadowMode(30000);
  const [showShadowPanel, setShowShadowPanel] = useState(false);

  const handleSendCommand = useCallback(async (rawInput: string) => {
    const event = new CustomEvent('jarvis-command', { detail: rawInput });
    window.dispatchEvent(event);
    close();
  }, [close]);

  const handleExecuteQuick = useCallback(async (id: string) => {
    await executeQuickCommand(id);
    close();
  }, [executeQuickCommand, close]);

  const isShadowActive = shadowStatus?.active ?? false;
  const shadowPhase = shadowStatus?.status || 'disabled';

  // Handle shadow mode quick actions from Jarvis
  const handleShadowQuickAction = useCallback(async (action: string) => {
    switch (action) {
      case 'enable_shadow':
        try {
          const success = await enableShadowMode({
            live_variant: 'mini_parwa',
            shadow_variant: 'parwa',
            sample_rate: 1.0,
          });
          if (success) toast.success('Shadow Mode enabled via Jarvis');
        } catch {
          toast.error('Failed to enable Shadow Mode');
        }
        break;
      case 'promote_shadow':
        try {
          const success = await promoteShadowMode();
          if (success) toast.success('Shadow Mode promoted via Jarvis');
        } catch {
          toast.error('Failed to promote Shadow Mode');
        }
        break;
      case 'disable_shadow':
        try {
          const success = await disableShadowMode('Disabled via Jarvis CC');
          if (success) toast.success('Shadow Mode disabled via Jarvis');
        } catch {
          toast.error('Failed to disable Shadow Mode');
        }
        break;
      case 'view_shadow_mode':
        window.open('/dashboard/shadow-mode', '_self');
        break;
    }
  }, [enableShadowMode, promoteShadowMode, disableShadowMode]);

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      {/* Shadow Mode Quick Access Bar */}
      <div className="mb-3 flex items-center gap-3">
        <button
          onClick={() => setShowShadowPanel(!showShadowPanel)}
          className={cn(
            'flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg transition-colors',
            isShadowActive
              ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
              : 'bg-white/5 text-zinc-500 border border-white/[0.06] hover:text-zinc-300'
          )}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09Z" />
          </svg>
          <span className="font-medium">
            {isShadowActive ? `Shadow: ${shadowPhase.toUpperCase()}` : 'Shadow Mode'}
          </span>
          {isShadowActive && (
            <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />
          )}
        </button>

        {isShadowActive && (
          <>
            <button
              onClick={() => handleShadowQuickAction('promote_shadow')}
              className="text-xs px-2.5 py-1 rounded bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors"
            >
              Promote
            </button>
            <button
              onClick={() => handleShadowQuickAction('disable_shadow')}
              className="text-xs px-2.5 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
            >
              Disable
            </button>
          </>
        )}

        {!isShadowActive && (
          <button
            onClick={() => handleShadowQuickAction('enable_shadow')}
            className="text-xs px-2.5 py-1 rounded bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 transition-colors"
          >
            Enable
          </button>
        )}

        <Link
          href="/dashboard/shadow-mode"
          className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors ml-auto"
        >
          Open Dashboard →
        </Link>
      </div>

      {/* Shadow Mode Panel (collapsible) */}
      {showShadowPanel && (
        <div className="mb-3 rounded-xl border border-purple-500/20 bg-purple-500/5 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-purple-400">Shadow Mode Status</h3>
            <button
              onClick={() => setShowShadowPanel(false)}
              className="text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {isShadowActive && shadowStatus ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Phase</p>
                <p className={cn(
                  'text-sm font-bold capitalize',
                  shadowPhase === 'shadow' ? 'text-purple-400' :
                  shadowPhase === 'supervised' ? 'text-amber-400' :
                  'text-emerald-400'
                )}>
                  {shadowPhase}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Live</p>
                <p className="text-sm font-medium text-white">{shadowStatus.live_variant}</p>
              </div>
              <div>
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Shadow</p>
                <p className="text-sm font-medium text-purple-400">{shadowStatus.shadow_variant}</p>
              </div>
              <div>
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider">Win Rate</p>
                <p className="text-sm font-medium text-white">{Math.round(shadowStatus.shadow_win_rate * 100)}%</p>
              </div>
            </div>
          ) : (
            <div className="text-center py-2">
              <p className="text-xs text-zinc-500">Shadow Mode is not active.</p>
              <p className="text-[10px] text-zinc-600 mt-1">Enable it to test new variants safely alongside your live variant.</p>
            </div>
          )}
        </div>
      )}

      {/* Chat + Command Palette */}
      <div className="flex-1 min-h-0">
        <JarvisCCChat />
      </div>

      <JarvisCommandPalette
        isOpen={isOpen}
        query={query}
        onQueryChange={setQuery}
        onClose={close}
        quickCommands={quickCommands}
        onExecuteQuick={handleExecuteQuick}
        onSendCommand={handleSendCommand}
      />
    </div>
  );
}
