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
import {
  useJarvisCCSession,
  useJarvisCCChat,
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
    quickCommands,
    fetchQuickCommands,
    executeQuickCommand,
    undoCommand,
  } = useJarvisCommands(session?.id || null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
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
    }
  }, [session?.id, loadHistory, fetchQuickCommands]);

  // ── Auto-send ticket context from URL params (escalation flow) ──
  // When a user clicks "Discuss with Jarvis" on the escalation page,
  // they arrive here with ?ticket_id=X&subject=Y&description=Z.
  // We auto-send a pre-filled message so Jarvis has the full context
  // without the user having to re-type it.
  const autoSentRef = useRef(false);
  useEffect(() => {
    if (!session?.id || autoSentRef.current) return;
    if (typeof window === 'undefined') return;

    const params = new URLSearchParams(window.location.search);
    const ticketId = params.get('ticket_id');
    const ticketNumber = params.get('ticket_number');
    const subject = params.get('subject');
    const description = params.get('description');

    if (!ticketId) return;

    autoSentRef.current = true;

    // Build the message to Jarvis with ticket context
    // This makes Jarvis the bridge between the AI variant and the human.
    // The human sees: which ticket, what the customer asked, and asks Jarvis for help.
    const num = ticketNumber || ticketId.slice(0, 8).toUpperCase();
    const msg = [
      `Ticket ${num} needs my attention.`,
      ``,
      subject ? `**Subject:** ${subject}` : null,
      description ? `**Customer asked:** "${description}"` : null,
      ``,
      `The AI paused on this one and needs my guidance. What should I tell it to do?`,
    ].filter(Boolean).join('\n');

    // Small delay to let the chat UI render before sending
    setTimeout(() => {
      sendMessage(msg);
      // Clean the URL so the message doesn't re-send on refresh
      window.history.replaceState({}, '', '/dashboard/jarvis');
    }, 500);
  }, [session?.id, sendMessage]);

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
        {/* Chat header — clean, ChatGPT-style */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center text-white text-sm font-bold shadow-lg shadow-orange-500/20">
              J
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Jarvis</h2>
              <div className="flex items-center gap-1.5">
                <span className={cn(
                  'w-1.5 h-1.5 rounded-full',
                  session?.pipeline_status === 'running' ? 'bg-emerald-400' : 'bg-zinc-500'
                )} />
                <span className="text-[10px] text-zinc-500">
                  {session?.pipeline_status === 'running' ? 'Active' : 'Ready'}
                </span>
              </div>
            </div>
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
    </div>
  );
}
