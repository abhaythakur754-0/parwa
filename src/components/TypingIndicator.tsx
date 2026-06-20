'use client';

import { useTypingStore } from '@/lib/typing-store';

interface TypingIndicatorProps {
  ticketId: string;
}

export function TypingIndicator({ ticketId }: TypingIndicatorProps) {
  // Use primitive selectors to avoid infinite loop with useSyncExternalStore
  // (getTypingUsers returns a new array reference each time)
  const typingCount = useTypingStore((s) => s.typingUsers.get(ticketId)?.length || 0);
  const typingNames = useTypingStore((s) =>
    (s.typingUsers.get(ticketId) || []).map(u => u.userName).join(',')
  );

  if (typingCount === 0) return null;

  const names = typingNames.split(',').filter(Boolean);
  let text: string;

  if (names.length === 1) {
    text = `${names[0]} is typing`;
  } else if (names.length === 2) {
    text = `${names[0]} and ${names[1]} are typing`;
  } else {
    text = `${names[0]} and ${names.length - 1} others are typing`;
  }

  return (
    <div
      data-testid="typing-indicator"
      className="flex items-center gap-2 px-3 py-1.5 text-xs text-zinc-400"
      role="status"
      aria-live="polite"
    >
      <span className="flex gap-0.5">
        <span className="w-1 h-1 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-1 h-1 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="w-1 h-1 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '300ms' }} />
      </span>
      <span>{text}</span>
    </div>
  );
}
