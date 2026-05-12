/**
 * Jarvis Customer Care Dashboard Page (/dashboard/jarvis)
 *
 * Full Jarvis CC chat interface with awareness feed and command palette.
 */

'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { JarvisCCChat } from '@/components/jarvis-cc/JarvisCCChat';
import { JarvisCommandPalette } from '@/components/jarvis-cc/JarvisCommandPalette';
import { useCommandPalette, useJarvisCCSession, useJarvisCommands } from '@/hooks/useJarvisCC';

export default function JarvisCCPage() {
  const { session, createSession, resumeSession } = useJarvisCCSession();
  const { quickCommands, fetchQuickCommands, executeQuickCommand } = useJarvisCommands(session?.id || null);
  const { isOpen, query, setQuery, open, close } = useCommandPalette();

  const handleSendCommand = useCallback(async (rawInput: string) => {
    // This will be handled by the chat component internally
    // The command palette delegates to the chat input
    const event = new CustomEvent('jarvis-command', { detail: rawInput });
    window.dispatchEvent(event);
    close();
  }, [close]);

  const handleExecuteQuick = useCallback(async (id: string) => {
    await executeQuickCommand(id);
    close();
  }, [executeQuickCommand, close]);

  return (
    <div className="h-[calc(100vh-8rem)]">
      <JarvisCCChat />

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
