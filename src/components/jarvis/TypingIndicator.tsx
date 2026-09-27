/**
 * PARWA TypingIndicator Component (Week 6 — Day 3 Phase 5)
 *
 * Animated three-bouncing-dots indicator shown while Jarvis is
 * generating a response. Uses existing .typing-dot CSS animation
 * defined in globals.css.
 */

'use client';

import { Bot } from 'lucide-react';

export function TypingIndicator() {
  return (
    <div className="flex items-end gap-2 px-4 py-2 chat-msg-reveal" role="status" aria-label="Jarvis is typing">
      {/* Jarvis avatar (mini) */}
      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-orange-400/20 to-orange-600/20 flex items-center justify-center shrink-0">
        <Bot className="w-3.5 h-3.5 text-orange-400" />
      </div>

      {/* Bouncing dots container */}
      <div className="glass rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-1.5">
        <span className="typing-dot w-2 h-2 bg-orange-400 rounded-full inline-block" />
        <span className="typing-dot w-2 h-2 bg-orange-400 rounded-full inline-block" />
        <span className="typing-dot w-2 h-2 bg-orange-400 rounded-full inline-block" />
      </div>
    </div>
  );
}
