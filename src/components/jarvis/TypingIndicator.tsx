/**
 * PARWA TypingIndicator Component — ZAI-style Clean Design
 *
 * Animated three-bouncing-dots indicator shown while Jarvis is
 * generating a response. Clean minimal design matching ZAI style.
 */

'use client';

export function TypingIndicator() {
  return (
    <div className="px-4 py-2 chat-msg-reveal" role="status" aria-label="Jarvis is typing">
      <div className="flex items-start gap-3">
        {/* Mini Jarvis avatar */}
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center shrink-0 text-white font-bold text-[11px] shadow-md shadow-orange-500/20 mt-0.5">
          J
        </div>

        {/* Bouncing dots — clean, no box */}
        <div className="flex items-center gap-1.5 py-2">
          <span className="typing-dot w-2 h-2 bg-orange-400/60 rounded-full inline-block" />
          <span className="typing-dot w-2 h-2 bg-orange-400/60 rounded-full inline-block" />
          <span className="typing-dot w-2 h-2 bg-orange-400/60 rounded-full inline-block" />
        </div>
      </div>
    </div>
  );
}
