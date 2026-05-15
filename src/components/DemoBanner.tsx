'use client';

import { useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface DemoBannerProps {
  onDismiss?: () => void;
}

export function DemoBanner({ onDismiss }: DemoBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  return (
    <div
      role="alert"
      data-testid="demo-banner"
      className="relative flex items-center justify-center gap-3 px-4 py-2 bg-amber-500/10 border-b border-amber-500/20 text-amber-300"
    >
      <AlertTriangle className="w-4 h-4 shrink-0" />
      <p className="text-sm font-medium">
        <span className="font-semibold">Demo Mode</span> — You are viewing sample data.
        Connect your backend to see live information.
      </p>
      <button
        onClick={() => {
          setDismissed(true);
          onDismiss?.();
        }}
        className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-md hover:bg-amber-500/10 transition-colors"
        aria-label="Dismiss demo banner"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
