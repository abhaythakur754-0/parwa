'use client';

import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';

interface SLATimerProps {
  ticketId: string;
  createdAt: string | Date;
  resolutionTargetAt?: string | Date | null;
  firstResponseTargetAt?: string | Date | null;
  isBreached?: boolean;
  className?: string;
}

export default function SLATimer({
  ticketId,
  createdAt,
  resolutionTargetAt,
  firstResponseTargetAt,
  isBreached = false,
  className,
}: SLATimerProps) {
  const [timeRemaining, setTimeRemaining] = useState<number>(0);
  const [isApproaching, setIsApproaching] = useState(false);
  const [slaType, setSlaType] = useState<'first_response' | 'resolution'>('resolution');

  useEffect(() => {
    const target = firstResponseTargetAt || resolutionTargetAt;
    if (!target) return;

    const targetDate = typeof target === 'string' ? new Date(target) : target;
    const createdDate = typeof createdAt === 'string' ? new Date(createdAt) : createdAt;

    // Determine SLA type
    setSlaType(firstResponseTargetAt ? 'first_response' : 'resolution');

    const updateTime = () => {
      const now = new Date();
      const remaining = targetDate.getTime() - now.getTime();
      setTimeRemaining(remaining);

      // Check if approaching breach (75% threshold)
      const totalTime = targetDate.getTime() - createdDate.getTime();
      const elapsed = now.getTime() - createdDate.getTime();
      const percentageElapsed = (elapsed / totalTime) * 100;
      setIsApproaching(percentageElapsed >= 75 && remaining > 0);
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, [createdAt, resolutionTargetAt, firstResponseTargetAt]);

  const formatTime = (ms: number) => {
    if (ms <= 0) return 'Breached';

    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) {
      return `${days}d ${hours % 24}h`;
    }
    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    }
    if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    }
    return `${seconds}s`;
  };

  const getStatusColor = () => {
    if (isBreached || timeRemaining <= 0) {
      return 'text-red-400 bg-red-500/15 border-red-500/25';
    }
    if (isApproaching) {
      return 'text-yellow-400 bg-yellow-500/15 border-yellow-500/25';
    }
    return 'text-zinc-400 bg-white/[0.04] border-white/[0.08]';
  };

  const getIcon = () => {
    if (isBreached || timeRemaining <= 0) {
      return (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
        </svg>
      );
    }
    if (isApproaching) {
      return (
        <svg className="w-3.5 h-3.5 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
      );
    }
    return (
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      </svg>
    );
  };

  return (
    <div
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-1 rounded-lg border text-xs font-medium transition-colors',
        getStatusColor(),
        className
      )}
      title={`${slaType === 'first_response' ? 'First Response' : 'Resolution'} SLA`}
    >
      {getIcon()}
      <span className="tabular-nums">{formatTime(timeRemaining)}</span>
    </div>
  );
}

// ── SLA Badge Component (Compact) ─────────────────────────────────────

interface SLABadgeProps {
  isBreached?: boolean;
  isApproaching?: boolean;
  hasSLA?: boolean;
  className?: string;
}

export function SLABadge({ isBreached, isApproaching, hasSLA, className }: SLABadgeProps) {
  if (!hasSLA) {
    return (
      <span className={cn('text-[10px] text-zinc-600', className)}>
        No SLA
      </span>
    );
  }

  if (isBreached) {
    return (
      <span className={cn(
        'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium',
        'bg-red-500/15 text-red-400 border border-red-500/25',
        className
      )}>
        <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
        Breached
      </span>
    );
  }

  if (isApproaching) {
    return (
      <span className={cn(
        'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium',
        'bg-yellow-500/15 text-yellow-400 border border-yellow-500/25',
        className
      )}>
        <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
        Due Soon
      </span>
    );
  }

  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium',
      'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25',
      className
    )}>
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
      On Track
    </span>
  );
}

// ── SLA Progress Bar Component ─────────────────────────────────────

interface SLAProgressBarProps {
  createdAt: string | Date;
  targetAt: string | Date;
  isBreached?: boolean;
  className?: string;
}

export function SLAProgressBar({
  createdAt,
  targetAt,
  isBreached = false,
  className,
}: SLAProgressBarProps) {
  const [percentage, setPercentage] = useState(0);

  useEffect(() => {
    const target = typeof targetAt === 'string' ? new Date(targetAt) : targetAt;
    const created = typeof createdAt === 'string' ? new Date(createdAt) : createdAt;

    const updateProgress = () => {
      const now = new Date();
      const total = target.getTime() - created.getTime();
      const elapsed = now.getTime() - created.getTime();
      const pct = Math.min(100, Math.max(0, (elapsed / total) * 100));
      setPercentage(pct);
    };

    updateProgress();
    const interval = setInterval(updateProgress, 60000); // Update every minute
    return () => clearInterval(interval);
  }, [createdAt, targetAt]);

  const getBarColor = () => {
    if (isBreached || percentage >= 100) return 'bg-red-500';
    if (percentage >= 75) return 'bg-yellow-500';
    if (percentage >= 50) return 'bg-orange-500';
    return 'bg-emerald-500';
  };

  const getBgColor = () => {
    if (isBreached || percentage >= 100) return 'bg-red-500/20';
    if (percentage >= 75) return 'bg-yellow-500/20';
    return 'bg-white/[0.04]';
  };

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className={cn('flex-1 h-1.5 rounded-full overflow-hidden', getBgColor())}>
        <div
          className={cn('h-full rounded-full transition-all duration-300', getBarColor())}
          style={{ width: `${Math.min(100, percentage)}%` }}
        />
      </div>
      <span className="text-[10px] text-zinc-500 tabular-nums w-8 text-right">
        {Math.round(percentage)}%
      </span>
    </div>
  );
}
