/**
 * PARWA Onboarding TypingIndicator
 *
 * Animated three-bouncing-dots indicator shown while Jarvis is
 * generating a response. Emerald/parrot green theme.
 */

'use client';

export function TypingIndicator() {
  return (
    <div className="flex items-end gap-2 px-4 py-2 chat-msg-reveal" role="status" aria-label="Jarvis is typing">
      {/* Jarvis avatar (mini) */}
      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-emerald-400/20 to-emerald-600/20 flex items-center justify-center shrink-0">
        <svg className="w-3.5 h-3.5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="11" width="18" height="10" rx="2" />
          <circle cx="12" cy="5" r="2" />
          <path d="M12 7v4" />
        </svg>
      </div>

      {/* Bouncing dots container */}
      <div className="bg-white/[0.05] backdrop-blur-xl rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-1.5 border border-white/[0.06]">
        <span className="typing-dot w-2 h-2 bg-emerald-400 rounded-full inline-block" />
        <span className="typing-dot w-2 h-2 bg-emerald-400 rounded-full inline-block" />
        <span className="typing-dot w-2 h-2 bg-emerald-400 rounded-full inline-block" />
      </div>
    </div>
  );
}
