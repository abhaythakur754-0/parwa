'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { useSocket } from '@/contexts/SocketContext';
import { getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import { notificationsApi, type Notification, type NotificationPreferences } from '@/lib/notifications-api';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';

// ── Constants ───────────────────────────────────────────────────────────

const PAGE_SIZE = 25;

const TYPE_FILTERS: { value: string; label: string; color?: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'ticket', label: 'Tickets' },
  { value: 'approval', label: 'Approvals' },
  { value: 'system', label: 'System' },
  { value: 'billing', label: 'Billing' },
  { value: 'training', label: 'Training' },
  { value: 'agent', label: 'Agent' },
];

const PRIORITY_STYLES: Record<string, string> = {
  urgent: 'bg-red-500/15 text-red-400 border-red-500/20',
  high: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
  medium: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  low: 'bg-zinc-600/15 text-zinc-500 border-zinc-600/20',
};

const NOTIFICATION_TYPES_FOR_PREFS: string[] = [
  'ticket', 'approval', 'system', 'billing', 'training', 'agent',
];

const TYPE_DISPLAY_NAMES: Record<string, string> = {
  ticket: 'Tickets',
  approval: 'Approvals',
  system: 'System',
  billing: 'Billing',
  training: 'Training',
  agent: 'Agent',
  escalation: 'Escalation',
};

const DIGEST_OPTIONS = [
  { value: 'never', label: 'Never' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
];

// ── Helper: Relative Time ───────────────────────────────────────────────

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  if (diff < 60000) return 'Just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

// ── Helper: Group notifications by time period ──────────────────────────

type TimeGroup = 'Today' | 'Yesterday' | 'This Week' | 'Earlier';

interface GroupedNotifications {
  group: TimeGroup;
  items: Notification[];
}

function groupByTime(notifications: Notification[]): GroupedNotifications[] {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterdayStart = todayStart - 86400000;
  const weekStart = todayStart - 7 * 86400000;

  const groups: Record<TimeGroup, Notification[]> = {
    Today: [],
    Yesterday: [],
    'This Week': [],
    Earlier: [],
  };

  for (const n of notifications) {
    const ts = new Date(n.created_at).getTime();
    if (ts >= todayStart) {
      groups.Today.push(n);
    } else if (ts >= yesterdayStart) {
      groups.Yesterday.push(n);
    } else if (ts >= weekStart) {
      groups['This Week'].push(n);
    } else {
      groups.Earlier.push(n);
    }
  }

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([group, items]) => ({ group: group as TimeGroup, items }));
}

// ── Helper: Simple beep sound via Web Audio API ────────────────────────

function playNotificationBeep() {
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.setValueAtTime(660, ctx.currentTime + 0.1);
    gain.gain.setValueAtTime(0.1, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.3);
  } catch {
    // Audio not supported — ignore
  }
}

// ── Inline SVG Icons ────────────────────────────────────────────────────

const BellIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
  </svg>
);

const CheckDoubleIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
  </svg>
);

const SettingsIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
  </svg>
);

const RefreshIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
  </svg>
);

const SearchIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
  </svg>
);

const VolumeIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75Z" />
  </svg>
);

const VolumeOffIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 9.75 19.5 12m0 0 2.25 2.25M19.5 12l2.25-2.25M19.5 12l-2.25 2.25m-10.5-6 4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75Z" />
  </svg>
);

const EyeIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
  </svg>
);

const CheckIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
  </svg>
);

const XMarkIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
  </svg>
);

const ExternalLinkIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
  </svg>
);

const ChevronDownIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
  </svg>
);

const ShieldIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
  </svg>
);

const GearIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.24-.438.613-.43.992a6.723 6.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
  </svg>
);

const DollarIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
  </svg>
);

const AcademicCapIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5" />
  </svg>
);

const ChatBubbleIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
  </svg>
);

const CheckCircleIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z" />
  </svg>
);

const ArrowUpIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 19.5v-15m0 0-6.75 6.75M12 4.5l6.75 6.75" />
  </svg>
);

const RobotIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75a2.25 2.25 0 0 0-2.25-2.25H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Zm.75-12h9v9h-9v-9Z" />
  </svg>
);

const InboxIcon = () => (
  <svg className="w-16 h-16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 13.5h3.86a2.25 2.25 0 0 1 2.012 1.244l.256.512a2.25 2.25 0 0 0 2.013 1.244h3.218a2.25 2.25 0 0 0 2.013-1.244l.256-.512a2.25 2.25 0 0 1 2.013-1.244h3.859m-19.5.338V18a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18v-4.162c0-.224-.034-.447-.1-.661L19.24 5.338a2.25 2.25 0 0 0-2.15-1.588H6.911a2.25 2.25 0 0 0-2.15 1.588L2.35 13.177a2.25 2.25 0 0 0-.1.661Z" />
  </svg>
);

const SpinnerIcon = ({ className = 'w-4 h-4' }: { className?: string }) => (
  <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
  </svg>
);

// ── Notification Type Icon Component (N2) ───────────────────────────────

function NotificationTypeIcon({ type, className }: { type: string; className?: string }) {
  const iconClass = className || 'w-9 h-9';

  switch (type) {
    case 'ticket':
      return (
        <div className={cn(iconClass, 'rounded-lg bg-blue-500/15 flex items-center justify-center shrink-0')}>
          <ChatBubbleIcon />
        </div>
      );
    case 'escalation':
      return (
        <div className={cn(iconClass, 'rounded-lg bg-red-500/15 flex items-center justify-center shrink-0')}>
          <ArrowUpIcon />
        </div>
      );
    case 'approval':
      return (
        <div className={cn(iconClass, 'rounded-lg bg-orange-500/15 flex items-center justify-center shrink-0')}>
          <ShieldIcon />
        </div>
      );
    case 'system':
      return (
        <div className={cn(iconClass, 'rounded-lg bg-zinc-500/15 flex items-center justify-center shrink-0')}>
          <GearIcon />
        </div>
      );
    case 'billing':
      return (
        <div className={cn(iconClass, 'rounded-lg bg-purple-500/15 flex items-center justify-center shrink-0')}>
          <DollarIcon />
        </div>
      );
    case 'training':
      return (
        <div className={cn(iconClass, 'rounded-lg bg-cyan-500/15 flex items-center justify-center shrink-0')}>
          <AcademicCapIcon />
        </div>
      );
    case 'agent':
      return (
        <div className={cn(iconClass, 'rounded-lg bg-emerald-500/15 flex items-center justify-center shrink-0')}>
          <RobotIcon />
        </div>
      );
    default:
      return (
        <div className={cn(iconClass, 'rounded-lg bg-zinc-500/15 flex items-center justify-center shrink-0')}>
          <BellIcon />
        </div>
      );
  }
}

// ── Skeleton Loaders ────────────────────────────────────────────────────

function NotificationSkeleton() {
  return (
    <div className="flex items-start gap-3 p-4">
      <Skeleton className="w-9 h-9 rounded-lg shrink-0" />
      <div className="flex-1 min-w-0 space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-20" />
      </div>
      <Skeleton className="w-2 h-2 rounded-full shrink-0 mt-2" />
    </div>
  );
}

function NotificationListSkeleton() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <NotificationSkeleton key={i} />
      ))}
    </>
  );
}

// ── Preferences Panel ───────────────────────────────────────────────────

function PreferencesPanel({
  preferences,
  loading,
  onPreferenceChange,
  onDigestChange,
  onDisableAll,
  onEnableAll,
  onClose,
}: {
  preferences: NotificationPreferences | null;
  loading: boolean;
  onPreferenceChange: (typeKey: string, channel: 'email' | 'push' | 'in_app', value: boolean) => void;
  onDigestChange: (frequency: string) => void;
  onDisableAll: () => void;
  onEnableAll: () => void;
  onClose: () => void;
}) {
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="bg-[#111111] border border-white/[0.06] max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-white">Notification Preferences</DialogTitle>
          <DialogDescription className="text-zinc-500">
            Control how and when you receive notifications.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="space-y-4 py-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full rounded-lg" />
            ))}
          </div>
        ) : preferences ? (
          <div className="space-y-6">
            {/* Master Toggles */}
            <div className="flex items-center gap-3">
              <button
                onClick={onDisableAll}
                className="px-4 py-2 text-xs font-medium text-zinc-400 border border-white/[0.06] rounded-lg hover:bg-white/[0.04] hover:text-zinc-200 transition-colors"
              >
                Disable All
              </button>
              <button
                onClick={onEnableAll}
                className="px-4 py-2 text-xs font-medium text-zinc-400 border border-white/[0.06] rounded-lg hover:bg-white/[0.04] hover:text-zinc-200 transition-colors"
              >
                Enable All
              </button>
            </div>

            {/* Digest Settings */}
            <div className="bg-[#1A1A1A] rounded-xl p-4 border border-white/[0.06]">
              <h4 className="text-sm font-medium text-white mb-3">Digest Mode</h4>
              <div className="flex items-center gap-2">
                {DIGEST_OPTIONS.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => onDigestChange(opt.value)}
                    className={cn(
                      'px-4 py-2 text-xs font-medium rounded-lg transition-colors border',
                      preferences.digest_frequency === opt.value
                        ? 'bg-[#FF7F11]/15 text-[#FF7F11] border-[#FF7F11]/20'
                        : 'text-zinc-500 border-white/[0.06] hover:bg-white/[0.04] hover:text-zinc-300'
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Per-Type Preferences */}
            <div className="bg-[#1A1A1A] rounded-xl border border-white/[0.06] overflow-hidden">
              <div className="grid grid-cols-[1fr,80px,80px,80px] gap-0 text-xs font-medium text-zinc-500 uppercase tracking-wider p-3 border-b border-white/[0.06]">
                <span>Category</span>
                <span className="text-center">Email</span>
                <span className="text-center">Push</span>
                <span className="text-center">In-App</span>
              </div>
              {NOTIFICATION_TYPES_FOR_PREFS.map(typeKey => {
                const pref = preferences.type_preferences?.[typeKey] || { email: true, push: true, in_app: true };
                return (
                  <div
                    key={typeKey}
                    className="grid grid-cols-[1fr,80px,80px,80px] gap-0 items-center p-3 border-b border-white/[0.04] last:border-b-0"
                  >
                    <span className="text-sm text-zinc-300">{TYPE_DISPLAY_NAMES[typeKey] || typeKey}</span>
                    {(['email', 'push', 'in_app'] as const).map(channel => (
                      <div key={channel} className="flex justify-center">
                        <button
                          onClick={() => onPreferenceChange(typeKey, channel, !pref[channel])}
                          className={cn(
                            'w-10 h-5 rounded-full transition-colors relative',
                            pref[channel] ? 'bg-[#FF7F11]' : 'bg-zinc-700'
                          )}
                        >
                          <span
                            className={cn(
                              'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform',
                              pref[channel] ? 'left-5.5 translate-x-0' : 'left-0.5'
                            )}
                            style={{ left: pref[channel] ? '22px' : '2px' }}
                          />
                        </button>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>

            {/* Quiet Hours */}
            <div className="pt-4 border-t border-white/[0.06]">
              <h4 className="text-sm font-semibold text-zinc-300 mb-3">Quiet Hours</h4>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-sm text-zinc-400">Mute notifications during quiet hours</p>
                  <p className="text-xs text-zinc-500">No notifications will be sent during this time window</p>
                </div>
                <button
                  onClick={() => onPreferenceChange('__quiet_hours__', 'in_app', !preferences?.quiet_hours_enabled)}
                  className={cn(
                    'relative w-11 h-6 rounded-full transition-colors duration-300',
                    preferences?.quiet_hours_enabled ? 'bg-orange-500' : 'bg-white/[0.1]'
                  )}
                >
                  <span className={cn(
                    'absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-300',
                    preferences?.quiet_hours_enabled ? 'translate-x-5' : 'translate-x-0'
                  )} />
                </button>
              </div>
              {preferences?.quiet_hours_enabled && (
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-zinc-500">From</span>
                    <input
                      type="time"
                      value={preferences.quiet_hours_start || '22:00'}
                      onChange={(e) => onPreferenceChange('__quiet_hours_start__', 'in_app', e.target.value as any)}
                      className="bg-[#1A1A1A] border border-white/[0.06] rounded-lg px-3 py-1.5 text-sm text-white"
                    />
                  </div>
                  <span className="text-zinc-600">to</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-zinc-500">To</span>
                    <input
                      type="time"
                      value={preferences.quiet_hours_end || '08:00'}
                      onChange={(e) => onPreferenceChange('__quiet_hours_end__', 'in_app', e.target.value as any)}
                      className="bg-[#1A1A1A] border border-white/[0.06] rounded-lg px-3 py-1.5 text-sm text-white"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : null}

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
          >
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Main Component ──────────────────────────────────────────────────────

export default function NotificationsPage() {
  const router = useRouter();
  const { socket, unreadNotificationCount: socketUnreadCount } = useSocket();

  // ── Data State ────────────────────────────────────────────────────────
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);

  // ── Filter State ──────────────────────────────────────────────────────
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');

  // ── Preferences State ─────────────────────────────────────────────────
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(null);
  const [showPreferences, setShowPreferences] = useState(false);
  const [prefsLoading, setPrefsLoading] = useState(false);
  const [prefChanges, setPrefChanges] = useState<Partial<NotificationPreferences> | null>(null);

  // ── Sound Toggle ──────────────────────────────────────────────────────
  const [soundEnabled, setSoundEnabled] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('parwa_notif_sound') !== 'false';
    }
    return true;
  });

  // ── Expanded Notification ─────────────────────────────────────────────
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // ── Mark All Loading ──────────────────────────────────────────────────
  const [markingAll, setMarkingAll] = useState(false);

  // ── Grouped Notifications (N1) ────────────────────────────────────────
  const groupedNotifications = useMemo(() => groupByTime(notifications), [notifications]);

  // ── Fetch Notifications ───────────────────────────────────────────────

  const fetchNotifications = useCallback(async (pageNum: number, append: boolean = false) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
      setError(null);
      setIsConnecting(false);
    }

    try {
      const params: { page?: number; pageSize?: number; type?: string; unreadOnly?: boolean } = {
        page: pageNum,
        pageSize: PAGE_SIZE,
      };
      if (typeFilter !== 'all') params.type = typeFilter;
      if (unreadOnly) params.unreadOnly = true;

      const data = await notificationsApi.list(params);

      if (append) {
        setNotifications(prev => [...prev, ...data.notifications]);
      } else {
        setNotifications(data.notifications);
      }

      setTotal(data.total);
      setUnreadCount(data.unread_count);
      setHasMore(data.notifications.length === PAGE_SIZE && data.page * data.page_size < data.total);
    } catch (err: any) {
      const msg = getErrorMessage(err);
      if (err?.response?.status === 404 || msg.includes('404')) {
        setIsConnecting(true);
        setNotifications([]);
        setTotal(0);
        setUnreadCount(0);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [typeFilter, unreadOnly]);

  // ── Fetch Unread Count ────────────────────────────────────────────────

  const fetchUnreadCount = useCallback(async () => {
    try {
      const data = await notificationsApi.getUnreadCount();
      setUnreadCount(data.count);
    } catch {
      // Silent fail
    }
  }, []);

  // ── Initial Load ──────────────────────────────────────────────────────

  useEffect(() => {
    fetchNotifications(1);
  }, [fetchNotifications]);

  useEffect(() => {
    fetchUnreadCount();
    // Poll every 30s
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  // ── Debounced Search ──────────────────────────────────────────────────

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // ── Apply search filter to notifications ──────────────────────────────

  const filteredGroups = useMemo(() => {
    if (!search.trim()) return groupedNotifications;
    const q = search.toLowerCase();
    return groupedNotifications.map(group => ({
      ...group,
      items: group.items.filter(
        n => n.title.toLowerCase().includes(q) || n.message.toLowerCase().includes(q)
      ),
    })).filter(group => group.items.length > 0);
  }, [groupedNotifications, search]);

  // ── Real-time Socket Updates (N6) ─────────────────────────────────────

  useEffect(() => {
    if (!socket) return;

    const handleNewNotification = (data: any) => {
      const notification: Notification = {
        id: data.id || data.notification_id || String(Date.now()),
        user_id: data.user_id || '',
        type: data.type || 'system',
        priority: data.priority || 'medium',
        title: data.title || 'New Notification',
        message: data.message || '',
        link: data.link || null,
        is_read: false,
        action_data: data.action_data || null,
        created_at: data.created_at || new Date().toISOString(),
        read_at: null,
      };

      // Prepend to list with animation
      setNotifications(prev => [notification, ...prev]);
      setUnreadCount(prev => prev + 1);

      // Show toast for high-priority
      if (notification.priority === 'urgent' || notification.priority === 'high') {
        toast.error(notification.title, {
          duration: 5000,
          style: {
            background: '#1A1A1A',
            color: '#fff',
            border: '1px solid rgba(255,255,255,0.06)',
          },
          iconTheme: {
            primary: '#FF7F11',
            secondary: '#fff',
          },
        });
      }

      // Play sound
      if (soundEnabled) {
        playNotificationBeep();
      }
    };

    socket.on('notification:new', handleNewNotification);
    return () => {
      socket.off('notification:new', handleNewNotification);
    };
  }, [socket, soundEnabled]);

  // ── Mark as Read Handlers (N3) ────────────────────────────────────────

  const handleMarkRead = useCallback(async (notificationId: string) => {
    try {
      await notificationsApi.markRead({ notification_ids: [notificationId] });
      setNotifications(prev =>
        prev.map(n => n.id === notificationId ? { ...n, is_read: true, read_at: new Date().toISOString() } : n)
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch {
      // Silent fail
    }
  }, []);

  const handleMarkAllRead = useCallback(async () => {
    setMarkingAll(true);
    try {
      await notificationsApi.markRead({ mark_all: true });
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true, read_at: n.read_at || new Date().toISOString() })));
      setUnreadCount(0);
      toast.success('All notifications marked as read');
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setMarkingAll(false);
    }
  }, []);

  // ── Click Notification ────────────────────────────────────────────────

  const handleNotificationClick = useCallback(async (notification: Notification) => {
    if (!notification.is_read) {
      await handleMarkRead(notification.id);
    }

    if (notification.link) {
      router.push(notification.link);
    } else {
      setExpandedId(prev => prev === notification.id ? null : notification.id);
    }
  }, [handleMarkRead, router]);

  // ── Preferences Handlers (N5) ─────────────────────────────────────────

  const handleOpenPreferences = useCallback(async () => {
    setShowPreferences(true);
    setPrefsLoading(true);
    setPrefChanges(null);
    try {
      const prefs = await notificationsApi.getPreferences();
      setPreferences(prefs);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setPrefsLoading(false);
    }
  }, []);

  const handlePrefToggle = useCallback(async (typeKey: string, channel: 'email' | 'push' | 'in_app', value: boolean) => {
    setPreferences(prev => {
      if (!prev) return prev;
      const updatedTypePrefs = { ...prev.type_preferences };
      const current = updatedTypePrefs[typeKey] || { email: true, push: true, in_app: true };
      updatedTypePrefs[typeKey] = { ...current, [channel]: value };
      return { ...prev, type_preferences: updatedTypePrefs };
    });
    // Persist to backend
    try {
      await notificationsApi.updatePreferences({
        type_preferences: { [typeKey]: { ...({ email: true, push: true, in_app: true } as any), [channel]: value } } as any,
      });
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }, []);

  const handleDigestChange = useCallback((frequency: string) => {
    setPreferences(prev => prev ? { ...prev, digest_frequency: frequency as any } : prev);
  }, []);

  const handleSavePreferences = useCallback(async () => {
    if (!preferences) return;
    try {
      await notificationsApi.updatePreferences(preferences);
      toast.success('Preferences saved');
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }, [preferences]);

  const handleSetDigest = useCallback(async (frequency: string) => {
    handleDigestChange(frequency);
    try {
      await notificationsApi.setDigest({ frequency });
      toast.success('Digest setting updated');
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }, [handleDigestChange]);

  const handleDisableAll = useCallback(async () => {
    try {
      const updated = await notificationsApi.disableAll();
      setPreferences(updated);
      toast.success('All notifications disabled');
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }, []);

  const handleEnableAll = useCallback(async () => {
    try {
      const updated = await notificationsApi.enableAll();
      setPreferences(updated);
      toast.success('All notifications enabled');
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }, []);

  const handleClosePreferences = useCallback(async () => {
    if (preferences && prefChanges) {
      await handleSavePreferences();
    }
    setShowPreferences(false);
    setPrefChanges(null);
  }, [preferences, prefChanges, handleSavePreferences]);

  // ── Quick Action Handlers (N7) ────────────────────────────────────────

  const handleApproveAction = useCallback(async (approvalId: string) => {
    try {
      // Use the dashboard API for approvals
      const { dashboardApi } = await import('@/lib/dashboard-api');
      await dashboardApi.approveResponse(approvalId, {});
      toast.success('Approved successfully');
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }, []);

  const handleRejectAction = useCallback(async (approvalId: string) => {
    try {
      const { dashboardApi } = await import('@/lib/dashboard-api');
      await dashboardApi.rejectResponse(approvalId, {});
      toast.success('Rejected successfully');
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }, []);

  // ── Load More ─────────────────────────────────────────────────────────

  const handleLoadMore = useCallback(() => {
    const nextPage = page + 1;
    setPage(nextPage);
    fetchNotifications(nextPage, true);
  }, [page, fetchNotifications]);

  // ── Sound Toggle Handler ──────────────────────────────────────────────

  const toggleSound = useCallback(() => {
    setSoundEnabled(prev => {
      const next = !prev;
      localStorage.setItem('parwa_notif_sound', String(next));
      return next;
    });
  }, []);

  // ── Clear Filters ─────────────────────────────────────────────────────

  const clearFilters = () => {
    setTypeFilter('all');
    setUnreadOnly(false);
    setSearchInput('');
    setSearch('');
    setPage(1);
  };

  const hasActiveFilters = typeFilter !== 'all' || unreadOnly || search;

  // ── Type Count Map ────────────────────────────────────────────────────

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const n of notifications) {
      counts[n.type] = (counts[n.type] || 0) + 1;
    }
    return counts;
  }, [notifications]);

  // ── Render ────────────────────────────────────────────────────────────

  const displayUnreadCount = unreadCount > 0 ? unreadCount : socketUnreadCount || 0;

  return (
    <div className="min-h-screen jarvis-page-body">
      <div className="p-4 md:p-6 max-w-4xl mx-auto">
        {/* ── Page Header (N1) ─────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-white flex items-center gap-2.5">
              <BellIcon />
              Notifications
              {displayUnreadCount > 0 && (
                <span className="ml-1 inline-flex items-center justify-center min-w-[22px] h-[22px] text-xs font-bold bg-[#FF7F11] text-white rounded-full px-1.5">
                  {displayUnreadCount > 99 ? '99+' : displayUnreadCount}
                </span>
              )}
            </h1>
            <p className="text-sm text-zinc-500 mt-0.5">
              {loading ? 'Loading...' : `${total} notification${total !== 1 ? 's' : ''}${displayUnreadCount > 0 ? ` · ${displayUnreadCount} unread` : ''}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* Sound Toggle */}
            <button
              onClick={toggleSound}
              className={cn(
                'h-8 w-8 rounded-lg flex items-center justify-center transition-colors',
                soundEnabled ? 'text-[#FF7F11] bg-[#FF7F11]/10' : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04]'
              )}
              title={soundEnabled ? 'Sound on' : 'Sound off'}
            >
              {soundEnabled ? <VolumeIcon /> : <VolumeOffIcon />}
            </button>

            {/* Mark All Read */}
            {displayUnreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                disabled={markingAll}
                className="h-8 px-3 rounded-lg flex items-center gap-1.5 text-xs font-medium text-zinc-400 border border-white/[0.06] hover:bg-white/[0.04] hover:text-zinc-200 transition-colors disabled:opacity-50"
              >
                {markingAll ? <SpinnerIcon /> : <CheckDoubleIcon />}
                Mark All Read
              </button>
            )}

            {/* Refresh */}
            <button
              onClick={() => fetchNotifications(1)}
              className="h-8 w-8 rounded-lg flex items-center justify-center text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] transition-colors"
              title="Refresh"
            >
              <RefreshIcon />
            </button>

            {/* Preferences */}
            <button
              onClick={handleOpenPreferences}
              className="h-8 w-8 rounded-lg flex items-center justify-center text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] transition-colors"
              title="Preferences"
            >
              <SettingsIcon />
            </button>
          </div>
        </div>

        {/* ── Type Filter Tabs (N4) ─────────────────────────────────────── */}
        <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-3 mb-4">
          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            {/* Type Tabs */}
            <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0 flex-1">
              {TYPE_FILTERS.map(tab => (
                <button
                  key={tab.value}
                  onClick={() => { setTypeFilter(tab.value); setPage(1); }}
                  className={cn(
                    'whitespace-nowrap px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5',
                    typeFilter === tab.value
                      ? 'bg-[#FF7F11]/15 text-[#FF7F11]'
                      : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04]'
                  )}
                >
                  {tab.label}
                  {tab.value !== 'all' && typeCounts[tab.value] > 0 && (
                    <span className="text-[10px] opacity-70">({typeCounts[tab.value]})</span>
                  )}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {/* Unread Only Toggle */}
              <button
                onClick={() => { setUnreadOnly(prev => !prev); setPage(1); }}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 border',
                  unreadOnly
                    ? 'bg-[#FF7F11]/15 text-[#FF7F11] border-[#FF7F11]/20'
                    : 'text-zinc-500 border-white/[0.06] hover:text-zinc-300 hover:bg-white/[0.04]'
                )}
              >
                <EyeIcon />
                Unread Only
              </button>

              {/* Search */}
              <div className="relative">
                <div className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500">
                  <SearchIcon />
                </div>
                <input
                  type="text"
                  placeholder="Search..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className="w-[140px] sm:w-[180px] pl-8 pr-3 py-1.5 bg-[#1A1A1A] border border-white/[0.06] rounded-lg text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[#FF7F11]/50 transition-colors"
                />
              </div>

              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
          </div>
        </div>

        {/* ── Notification List (N1) ────────────────────────────────────── */}
        <div className="bg-[#111111] border border-white/[0.06] rounded-xl overflow-hidden">
          {/* Loading State */}
          {loading && <NotificationListSkeleton />}

          {/* Connecting State (404) */}
          {!loading && isConnecting && (
            <div className="py-16 text-center">
              <div className="flex flex-col items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-orange-500/10 flex items-center justify-center">
                  <SpinnerIcon className="w-6 h-6 text-orange-400" />
                </div>
                <p className="text-sm text-orange-400 font-medium">Notification service connecting...</p>
                <p className="text-xs text-zinc-600 max-w-xs">
                  The notification system is being initialized. This page will update automatically.
                </p>
              </div>
            </div>
          )}

          {/* Error State */}
          {!loading && !isConnecting && error && (
            <div className="py-16 text-center">
              <div className="flex flex-col items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center text-red-400">
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                  </svg>
                </div>
                <p className="text-sm text-red-400">{error}</p>
                <button
                  onClick={() => fetchNotifications(1)}
                  className="h-8 px-3 rounded-lg flex items-center gap-1.5 text-xs font-medium text-zinc-400 border border-white/[0.06] hover:bg-white/[0.04] hover:text-zinc-200 transition-colors"
                >
                  <RefreshIcon /> Retry
                </button>
              </div>
            </div>
          )}

          {/* Empty State */}
          {!loading && !isConnecting && !error && filteredGroups.length === 0 && (
            <div className="py-16 text-center">
              <div className="flex flex-col items-center gap-3">
                <div className="w-20 h-20 rounded-2xl bg-emerald-500/10 flex items-center justify-center text-emerald-500/40">
                  <InboxIcon />
                </div>
                <p className="text-sm text-zinc-300 font-medium">
                  {unreadOnly ? 'All caught up!' : 'No notifications'}
                </p>
                <p className="text-xs text-zinc-600 max-w-xs">
                  {unreadOnly
                    ? 'You have no unread notifications. Great job!'
                    : hasActiveFilters
                      ? 'Try adjusting your filters to find notifications.'
                      : 'When you receive notifications, they\'ll appear here.'}
                </p>
                {hasActiveFilters && (
                  <button
                    onClick={clearFilters}
                    className="h-8 px-3 rounded-lg flex items-center gap-1.5 text-xs font-medium text-zinc-400 border border-white/[0.06] hover:bg-white/[0.04] hover:text-zinc-200 transition-colors"
                  >
                    Clear Filters
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Grouped Notification List */}
          {!loading && !isConnecting && !error && filteredGroups.map(group => (
            <div key={group.group}>
              {/* Group Header */}
              <div className="sticky top-0 z-10 bg-[#0D0D0D]/95 backdrop-blur-sm border-b border-white/[0.06] px-4 py-2">
                <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
                  {group.group}
                </span>
              </div>

              {/* Notification Items */}
              <div className="divide-y divide-white/[0.04]">
                {group.items.map(notification => {
                  const isExpanded = expandedId === notification.id;
                  const isHovered = hoveredId === notification.id;
                  const showActions = isExpanded || isHovered;

                  return (
                    <div
                      key={notification.id}
                      className={cn(
                        'relative cursor-pointer transition-all group',
                        notification.is_read
                          ? 'opacity-70 hover:opacity-100'
                          : 'bg-white/[0.02]',
                        notification.priority === 'urgent' && !notification.is_read && 'border-l-2 border-l-red-500',
                      )}
                      onClick={() => handleNotificationClick(notification)}
                      onMouseEnter={() => setHoveredId(notification.id)}
                      onMouseLeave={() => setHoveredId(null)}
                    >
                      <div className="flex items-start gap-3 p-4">
                        {/* Type Icon (N2) */}
                        <NotificationTypeIcon type={notification.type} />

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              {/* Title + Priority Badge */}
                              <div className="flex items-center gap-2 mb-0.5">
                                <h3 className={cn(
                                  'text-sm truncate',
                                  notification.is_read ? 'text-zinc-400 font-normal' : 'text-white font-semibold'
                                )}>
                                  {notification.title}
                                </h3>
                                {notification.priority !== 'low' && notification.priority !== 'medium' && (
                                  <span className={cn(
                                    'text-[9px] font-medium px-1.5 py-0.5 rounded-full border whitespace-nowrap',
                                    PRIORITY_STYLES[notification.priority]
                                  )}>
                                    {notification.priority}
                                  </span>
                                )}
                              </div>

                              {/* Message */}
                              <p className={cn(
                                'text-xs text-zinc-500 line-clamp-2 mt-0.5',
                                isExpanded && 'line-clamp-none'
                              )}>
                                {notification.message}
                              </p>

                              {/* Timestamp */}
                              <p className="text-[10px] text-zinc-600 mt-1.5">
                                {timeAgo(notification.created_at)}
                              </p>
                            </div>

                            {/* Unread Dot */}
                            {!notification.is_read && (
                              <div className="w-2 h-2 rounded-full bg-[#FF7F11] shrink-0 mt-1.5" />
                            )}
                          </div>

                          {/* Quick Actions (N7) — shown on hover or expand */}
                          {showActions && (
                            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-white/[0.04] animate-in fade-in-0 duration-200">
                              {/* Ticket actions */}
                              {notification.type === 'ticket' && notification.action_data?.ticket_id && (
                                <Link
                                  href={`/dashboard/tickets/${notification.action_data.ticket_id}`}
                                  onClick={(e) => e.stopPropagation()}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium text-blue-400 bg-blue-500/10 rounded-md hover:bg-blue-500/20 transition-colors"
                                >
                                  <EyeIcon /> View Ticket
                                </Link>
                              )}

                              {/* Approval actions */}
                              {notification.type === 'approval' && notification.action_data?.approval_id && (
                                <>
                                  <button
                                    onClick={(e) => { e.stopPropagation(); handleApproveAction(notification.action_data?.approval_id); }}
                                    className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 rounded-md hover:bg-emerald-500/20 transition-colors"
                                  >
                                    <CheckIcon /> Approve
                                  </button>
                                  <button
                                    onClick={(e) => { e.stopPropagation(); handleRejectAction(notification.action_data?.approval_id); }}
                                    className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium text-red-400 bg-red-500/10 rounded-md hover:bg-red-500/20 transition-colors"
                                  >
                                    <XMarkIcon /> Reject
                                  </button>
                                </>
                              )}

                              {/* System notifications — View Details */}
                              {notification.type === 'system' && notification.link && (
                                <Link
                                  href={notification.link}
                                  onClick={(e) => e.stopPropagation()}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium text-zinc-400 bg-white/[0.04] rounded-md hover:bg-white/[0.08] transition-colors"
                                >
                                  <ExternalLinkIcon /> View Details
                                </Link>
                              )}

                              {/* Link action for any notification with a link */}
                              {notification.link && notification.type !== 'system' && notification.type !== 'ticket' && (
                                <Link
                                  href={notification.link}
                                  onClick={(e) => e.stopPropagation()}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium text-[#FF7F11] bg-[#FF7F11]/10 rounded-md hover:bg-[#FF7F11]/20 transition-colors"
                                >
                                  <ExternalLinkIcon /> Open
                                </Link>
                              )}

                              {/* Mark as Read (if unread) */}
                              {!notification.is_read && (
                                <button
                                  onClick={(e) => { e.stopPropagation(); handleMarkRead(notification.id); }}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium text-zinc-500 bg-white/[0.04] rounded-md hover:bg-white/[0.08] hover:text-zinc-300 transition-colors ml-auto"
                                >
                                  <CheckCircleIcon /> Mark Read
                                </button>
                              )}

                              {/* Expand/Collapse toggle */}
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setExpandedId(prev => prev === notification.id ? null : notification.id);
                                }}
                                className="inline-flex items-center justify-center w-6 h-6 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04] transition-colors ml-auto"
                              >
                                <ChevronDownIcon />
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {/* Load More */}
          {!loading && !isConnecting && !error && hasMore && (
            <div className="p-4 border-t border-white/[0.06]">
              <button
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="w-full h-9 rounded-lg flex items-center justify-center gap-2 text-xs font-medium text-zinc-400 border border-white/[0.06] hover:bg-white/[0.04] hover:text-zinc-200 transition-colors disabled:opacity-50"
              >
                {loadingMore ? (
                  <>
                    <SpinnerIcon />
                    Loading...
                  </>
                ) : (
                  <>
                    <ChevronDownIcon />
                    Load More ({total - notifications.length} remaining)
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── Preferences Modal (N5) ─────────────────────────────────────── */}
      <PreferencesPanel
        preferences={preferences}
        loading={prefsLoading}
        onPreferenceChange={handlePrefToggle}
        onDigestChange={handleSetDigest}
        onDisableAll={handleDisableAll}
        onEnableAll={handleEnableAll}
        onClose={handleClosePreferences}
      />
    </div>
  );
}
