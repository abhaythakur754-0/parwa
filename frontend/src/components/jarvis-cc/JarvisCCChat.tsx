/**
 * JarvisCCChat — Main chat container for Jarvis Customer Care
 *
 * Combines chat messages, input, awareness feed sidebar, and quick actions.
 * Manages session lifecycle and real-time awareness polling.
 */

'use client';

import React, { useEffect, useRef, useCallback, useState } from 'react';
import { cn } from '@/lib/utils';
import { CCChatMessage } from './CCChatMessage';
import { CCChatInput } from './CCChatInput';
import { JarvisAwarenessFeed } from './JarvisAwarenessFeed';
import { JarvisQuickActions } from './JarvisQuickActions';
import {
  useJarvisCCSession,
  useJarvisCCChat,
  useJarvisAwareness,
  useJarvisCommands,
} from '@/hooks/useJarvisCC';
import type { CommandResponse } from '@/types/jarvis-cc';

export interface JarvisCCChatProps {
  className?: string;
}

export function JarvisCCChat({ className }: JarvisCCChatProps) {
  const { session, state: sessionState, createSession, resumeSession } = useJarvisCCSession();
  const {
    messages,
    isLoading: chatLoading,
    error: chatError,
    loadHistory,
    sendMessage,
    sendCommand,
  } = useJarvisCCChat(session?.id || null);
  const {
    snapshot,
    alerts,
    triggerTick,
    handleAlertAction,
    startPolling,
    stopPolling,
  } = useJarvisAwareness(session?.id || null);
  const {
    quickCommands,
    fetchQuickCommands,
    executeQuickCommand,
    undoCommand,
  } = useJarvisCommands(session?.id || null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [showSidebar, setShowSidebar] = useState(true);
  const [commandResults, setCommandResults] = useState<CommandResponse[]>([]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Initialize session on mount
  useEffect(() => {
    const init = async () => {
      // Try to resume existing session from localStorage
      const savedSessionId = typeof window !== 'undefined' ? localStorage.getItem('jarvis_cc_session_id') : null;
      if (savedSessionId) {
        const result = await resumeSession(savedSessionId);
        if (!result) {
          await createSession();
        }
      } else {
        await createSession();
      }
    };
    init();
  }, [createSession, resumeSession]);

  // Save session ID and load data when session changes
  useEffect(() => {
    if (session?.id) {
      localStorage.setItem('jarvis_cc_session_id', session.id);
      loadHistory();
      fetchQuickCommands();
      startPolling();
    }
    return () => stopPolling();
  }, [session?.id, loadHistory, fetchQuickCommands, startPolling, stopPolling]);

  const handleSendMessage = useCallback(async (content: string) => {
    await sendMessage(content);
  }, [sendMessage]);

  const handleSendCommand = useCallback(async (rawInput: string) => {
    const result = await sendCommand(rawInput);
    if (result) {
      setCommandResults(prev => [result, ...prev.slice(0, 9)]);
    }
  }, [sendCommand]);

  const handleQuickCommand = useCallback(async (id: string) => {
    const result = await executeQuickCommand(id);
    if (result) {
      // Add as message
      const cmdMessage = {
        id: `qc-${result.command_id}`,
        session_id: session?.id || '',
        role: 'jarvis' as const,
        content: result.error
          ? `Quick command failed: ${result.error}`
          : result.suggestion || `Quick command executed successfully.`,
        message_type: 'command_response' as const,
        metadata: { command_id: result.command_id, undo_available: result.undo_available, result: result.result },
        timestamp: new Date().toISOString(),
      };
      setCommandResults(prev => [result, ...prev.slice(0, 9)]);
    }
  }, [executeQuickCommand, session?.id]);

  const handleUndoCommand = useCallback(async (commandId: string) => {
    const result = await undoCommand(commandId);
    if (result) {
      // Could add undo result as a message
    }
  }, [undoCommand]);

  // Loading state
  if (sessionState.status === 'loading' && !session) {
    return (
      <div className={cn('flex items-center justify-center h-full', className)}>
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center animate-pulse shadow-lg shadow-orange-500/20">
            <span className="text-white font-bold text-sm">J</span>
          </div>
          <p className="text-sm text-zinc-500">Starting Jarvis...</p>
        </div>
      </div>
    );
  }

  // Error state with retry
  if (sessionState.status === 'error' && !session) {
    return (
      <div className={cn('flex items-center justify-center h-full', className)}>
        <div className="flex flex-col items-center gap-3 text-center max-w-sm">
          <svg className="w-10 h-10 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
          </svg>
          <p className="text-sm text-zinc-400">{sessionState.error}</p>
          <button
            onClick={() => createSession()}
            className="text-xs text-orange-400 hover:underline"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('flex h-full bg-[#111111]', className)}>
      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Chat header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center text-white text-xs font-bold shadow-lg shadow-orange-500/20">
              J
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Jarvis Customer Care</h2>
              <div className="flex items-center gap-2">
                <span className={cn(
                  'w-1.5 h-1.5 rounded-full',
                  session?.pipeline_status === 'running' ? 'bg-emerald-400' : session?.pipeline_status === 'paused' ? 'bg-amber-400' : 'bg-zinc-500'
                )} />
                <span className="text-[10px] text-zinc-500 capitalize">
                  {session?.pipeline_status || 'idle'}
                </span>
                {session?.variant_tier && (
                  <span className="text-[10px] text-zinc-600">| {session.variant_tier.replace('_', ' ')}</span>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => triggerTick('manual')}
              className="text-[10px] px-2.5 py-1 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.06] transition-colors"
              title="Refresh awareness data"
            >
              Refresh
            </button>
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className={cn(
                'text-[10px] px-2.5 py-1 rounded-lg transition-colors',
                showSidebar ? 'bg-orange-500/10 text-orange-400' : 'bg-white/[0.04] text-zinc-400'
              )}
            >
              {showSidebar ? 'Hide Feed' : 'Show Feed'}
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scrollbar-premium">
          {/* Welcome message */}
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center gap-4 py-12">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center text-white text-2xl font-bold shadow-2xl shadow-orange-500/20">
                J
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white mb-1">Jarvis is ready</h3>
                <p className="text-sm text-zinc-500 max-w-md">
                  I can help you manage tickets, check system health, control channels, and more.
                  Type a message or use <kbd className="text-[10px] bg-white/5 px-1.5 py-0.5 rounded">/</kbd> for commands.
                </p>
              </div>
              {/* Quick action suggestions */}
              {quickCommands.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  {quickCommands.slice(0, 4).map(cmd => (
                    <button
                      key={cmd.id}
                      onClick={() => handleQuickCommand(cmd.id)}
                      className="text-xs px-3 py-1.5 rounded-full bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors"
                    >
                      {cmd.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Message list */}
          {messages.map(msg => (
            <CCChatMessage
              key={msg.id}
              message={msg}
              onUndoCommand={handleUndoCommand}
            />
          ))}

          {/* Typing indicator */}
          {chatLoading && messages.length > 0 && messages[messages.length - 1].role === 'user' && (
            <div className="flex gap-2.5">
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center text-white text-[10px] font-bold shrink-0">
                J
              </div>
              <div className="bg-[#222222] rounded-2xl rounded-tl-md px-4 py-3">
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Chat error */}
        {chatError && (
          <div className="px-4 py-2 bg-red-500/10 border-t border-red-500/20">
            <p className="text-xs text-red-400">{chatError}</p>
          </div>
        )}

        {/* Input */}
        <CCChatInput
          onSendMessage={handleSendMessage}
          onSendCommand={handleSendCommand}
          disabled={!session?.is_active || chatLoading}
          remainingToday={session?.remaining_today}
        />
      </div>

      {/* Right sidebar: Awareness Feed */}
      {showSidebar && (
        <div className="w-80 border-l border-white/[0.06] bg-[#0D0D0D] flex flex-col shrink-0 hidden lg:flex">
          {/* Awareness overview */}
          {snapshot?.state && (
            <div className="p-4 border-b border-white/[0.06]">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider">System Status</h3>
                <span className={cn(
                  'w-2 h-2 rounded-full',
                  snapshot.state.system_health === 'healthy' ? 'bg-emerald-400' :
                  snapshot.state.system_health === 'degraded' ? 'bg-amber-400' : 'bg-red-400'
                )} />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="text-xs">
                  <span className="text-zinc-600">Quality</span>
                  <p className={cn(
                    'font-semibold',
                    snapshot.state.quality_score >= 0.7 ? 'text-emerald-400' :
                    snapshot.state.quality_score >= 0.5 ? 'text-amber-400' : 'text-red-400'
                  )}>
                    {Math.round(snapshot.state.quality_score * 100)}%
                  </p>
                </div>
                <div className="text-xs">
                  <span className="text-zinc-600">Tickets</span>
                  <p className="text-zinc-300 font-semibold">{snapshot.state.ticket_volume_today}</p>
                </div>
                <div className="text-xs">
                  <span className="text-zinc-600">Utilization</span>
                  <p className={cn(
                    'font-semibold',
                    snapshot.state.agent_pool_utilization >= 0.9 ? 'text-red-400' :
                    snapshot.state.agent_pool_utilization >= 0.7 ? 'text-amber-400' : 'text-emerald-400'
                  )}>
                    {Math.round(snapshot.state.agent_pool_utilization * 100)}%
                  </p>
                </div>
                <div className="text-xs">
                  <span className="text-zinc-600">Drift</span>
                  <p className={cn(
                    'font-semibold',
                    snapshot.state.drift_score > 0.3 ? 'text-amber-400' : 'text-emerald-400'
                  )}>
                    {Math.round(snapshot.state.drift_score * 100)}%
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Alerts feed */}
          <div className="flex-1 p-4 overflow-y-auto">
            <JarvisAwarenessFeed
              alerts={alerts}
              onAcknowledge={(id) => handleAlertAction(id, 'acknowledge')}
              onDismiss={(id) => handleAlertAction(id, 'dismiss')}
              onResolve={(id) => handleAlertAction(id, 'resolve')}
            />
          </div>

          {/* Quick actions */}
          {quickCommands.length > 0 && (
            <div className="p-4 border-t border-white/[0.06]">
              <JarvisQuickActions
                commands={quickCommands}
                onExecute={handleQuickCommand}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
