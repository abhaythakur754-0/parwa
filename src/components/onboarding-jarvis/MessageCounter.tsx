/**
 * PARWA Onboarding Jarvis — Message Counter
 *
 * Displays remaining message count for the onboarding chat session.
 */

'use client';

interface MessageCounterProps {
  remaining: number;
  total: number;
}

export function MessageCounter({ remaining, total }: MessageCounterProps) {
  const pct = total > 0 ? (remaining / total) * 100 : 0;
  const isLow = remaining <= 5 && remaining > 0;
  const isExhausted = remaining <= 0;

  return (
    <div className="px-4 py-2 flex items-center gap-3">
      <div className="flex-1 h-1.5 rounded-full bg-gray-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            isExhausted
              ? 'bg-red-500'
              : isLow
                ? 'bg-amber-500'
                : 'bg-emerald-500'
          }`}
          style={{ width: `${Math.max(pct, 0)}%` }}
        />
      </div>
      <span
        className={`text-xs tabular-nums whitespace-nowrap ${
          isExhausted
            ? 'text-red-400'
            : isLow
              ? 'text-amber-400'
              : 'text-gray-400'
        }`}
      >
        {remaining}/{total} messages
      </span>
    </div>
  );
}
