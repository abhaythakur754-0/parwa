'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import type { AnomalyAlert, AnomalySeverity } from '@/types/analytics';

// ── Props ─────────────────────────────────────────────────────────────

interface DashboardAlertsProps {
  /** Alert data from dashboard home /anomalies */
  alerts: AnomalyAlert[];
  /** Optional callback when an alert is dismissed */
  onDismiss?: (alertIndex: number) => void;
  className?: string;
}

// ── Severity Config ───────────────────────────────────────────────────

const SEVERITY_CONFIG: Record<AnomalySeverity, {
  bg: string;
  border: string;
  iconBg: string;
  iconColor: string;
  textColor: string;
  badgeBg: string;
  badgeText: string;
}> = {
  high: {
    bg: 'bg-red-500/[0.06]',
    border: 'border-red-500/20',
    iconBg: 'bg-red-500/15',
    iconColor: 'text-red-400',
    textColor: 'text-red-300',
    badgeBg: 'bg-red-500/20',
    badgeText: 'text-red-400',
  },
  medium: {
    bg: 'bg-amber-500/[0.06]',
    border: 'border-amber-500/20',
    iconBg: 'bg-amber-500/15',
    iconColor: 'text-amber-400',
    textColor: 'text-amber-300',
    badgeBg: 'bg-amber-500/20',
    badgeText: 'text-amber-400',
  },
  low: {
    bg: 'bg-sky-500/[0.06]',
    border: 'border-sky-500/20',
    iconBg: 'bg-sky-500/15',
    iconColor: 'text-sky-400',
    textColor: 'text-sky-300',
    badgeBg: 'bg-sky-500/20',
    badgeText: 'text-sky-400',
  },
};

// ── Alert Type Icons ──────────────────────────────────────────────────

function AlertIcon({ type, color }: { type: string; color: string }) {
  switch (type) {
    case 'volume_spike':
      return (
        <svg className={cn('w-4 h-4', color)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />
        </svg>
      );
    case 'sla_breach_cluster':
      return (
        <svg className={cn('w-4 h-4', color)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
        </svg>
      );
    case 'resolution_drop':
      return (
        <svg className={cn('w-4 h-4', color)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6 9 12.75l4.286-4.286a11.948 11.948 0 0 1 4.306 6.43l.776 2.898m0 0 3.182-5.511m-3.182 5.51-5.511-3.181" />
        </svg>
      );
    case 'csat_decline':
      return (
        <svg className={cn('w-4 h-4', color)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" />
        </svg>
      );
    default:
      return (
        <svg className={cn('w-4 h-4', color)} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
        </svg>
      );
  }
}

// ── Time Formatting ───────────────────────────────────────────────────

function formatAlertTime(isoString: string): string {
  if (!isoString) return '';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);

  if (diffMins < 5) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// ── Single Alert Banner ───────────────────────────────────────────────

function AlertBanner({
  alert,
  onDismiss,
}: {
  alert: AnomalyAlert;
  onDismiss?: () => void;
}) {
  const [isDismissed, setIsDismissed] = useState(false);
  const config = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.medium;

  if (isDismissed) return null;

  return (
    <div
      className={cn(
        'flex items-start gap-3 px-4 py-3 rounded-xl border transition-all duration-300 animate-in slide-in-from-top-2 fade-in',
        config.bg,
        config.border
      )}
    >
      {/* Icon */}
      <div className={cn(
        'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5',
        config.iconBg
      )}>
        <AlertIcon type={alert.type} color={config.iconColor} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className={cn(
            'text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded',
            config.badgeBg,
            config.badgeText
          )}>
            {alert.severity}
          </span>
          <span className="text-[11px] text-zinc-600">
            {formatAlertTime(alert.detected_at)}
          </span>
        </div>
        <p className={cn('text-sm font-medium leading-snug', config.textColor)}>
          {alert.message}
        </p>
      </div>

      {/* Dismiss */}
      {onDismiss && (
        <button
          onClick={() => {
            setIsDismissed(true);
            onDismiss();
          }}
          className="w-6 h-6 rounded-md flex items-center justify-center text-zinc-600 hover:text-zinc-400 hover:bg-white/[0.05] transition-colors shrink-0 mt-0.5"
          title="Dismiss alert"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  );
}

// ── DashboardAlerts Component ─────────────────────────────────────────

export default function DashboardAlerts({
  alerts,
  onDismiss,
  className,
}: DashboardAlertsProps) {
  const [dismissedIndices, setDismissedIndices] = useState<Set<number>>(new Set());

  if (alerts.length === 0) return null;

  const visibleAlerts = alerts.filter((_, i) => !dismissedIndices.has(i));

  if (visibleAlerts.length === 0) return null;

  return (
    <div className={cn('space-y-2', className)} role="list" aria-label="Dashboard alerts">
      {/* Alert count header */}
      {visibleAlerts.length > 1 && (
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              <div className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
              <span className="text-xs font-medium text-zinc-400">
                {visibleAlerts.length} active alert{visibleAlerts.length > 1 ? 's' : ''}
              </span>
            </div>
          </div>
          <button
            onClick={() => setDismissedIndices(new Set(alerts.map((_, i) => i)))}
            aria-label="Dismiss all alerts"
            className="text-[11px] text-zinc-600 hover:text-zinc-400 transition-colors"
          >
            Dismiss all
          </button>
        </div>
      )}

      {/* Alert banners */}
      {visibleAlerts.map((alert, idx) => {
        const originalIndex = alerts.indexOf(alert);
        return (
          <AlertBanner
            key={`${alert.type}-${alert.detected_at}-${originalIndex}`}
            alert={alert}
            onDismiss={() => {
              setDismissedIndices(prev => new Set(prev).add(originalIndex));
              onDismiss?.(originalIndex);
            }}
          />
        );
      })}
    </div>
  );
}
