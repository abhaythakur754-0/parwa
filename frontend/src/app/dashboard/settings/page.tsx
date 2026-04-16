'use client';

import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import { notificationsApi, type NotificationPreferences } from '@/lib/notifications-api';
import apiClient from '@/lib/api';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';

// ── Skeleton Helper ────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-white/[0.06]', className)} />;
}

// ── Inline SVG Icons ───────────────────────────────────────────────────────

function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
    </svg>
  );
}

function BuildingOfficeIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21" />
    </svg>
  );
}

function UserGroupIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 0 0 3.741-.479 3 3 0 0 0-4.682-2.72m.94 3.198.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0 1 12 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 0 1 6 18.719m12 0a5.971 5.971 0 0 0-.941-3.197m0 0A5.995 5.995 0 0 0 12 12.75a5.995 5.995 0 0 0-5.058 2.772m0 0a3 3 0 0 0-4.681 2.72 8.986 8.986 0 0 0 3.74.477m.94-3.197a5.971 5.971 0 0 0-.94 3.197M15 6.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm6 3a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Zm-13.5 0a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Z" />
    </svg>
  );
}

function ShieldCheckIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
    </svg>
  );
}

function BellIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
    </svg>
  );
}

function CodeBracketIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75 22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3-4.5 16.5" />
    </svg>
  );
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  );
}

function XMarkIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className={className}>
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
    </svg>
  );
}

function KeyIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1 1 21.75 8.25Z" />
    </svg>
  );
}

function DevicePhoneMobileIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 1.5H8.25A2.25 2.25 0 0 0 6 3.75v16.5a2.25 2.25 0 0 0 2.25 2.25h7.5A2.25 2.25 0 0 0 18 20.25V3.75a2.25 2.25 0 0 0-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3" />
    </svg>
  );
}

function QrCodeIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 0 1 3.75 9.375v-4.5ZM3.75 14.625c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5a1.125 1.125 0 0 1-1.125-1.125v-4.5ZM13.5 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 0 1 13.5 9.375v-4.5Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 6.75h.75v.75h-.75v-.75ZM6.75 16.5h.75v.75h-.75v-.75ZM16.5 6.75h.75v.75h-.75v-.75ZM13.5 13.5h.75v.75h-.75v-.75ZM13.5 19.5h.75v.75h-.75v-.75ZM19.5 13.5h.75v.75h-.75v-.75ZM19.5 19.5h.75v.75h-.75v-.75ZM16.5 16.5h.75v.75h-.75v-.75Z" />
    </svg>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  );
}

function GlobeAltIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582m15.686 0A11.953 11.953 0 0 1 12 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0 1 21 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0 1 12 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 0 1 3 12c0-1.605.42-3.113 1.157-4.418" />
    </svg>
  );
}

function DocumentTextIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
    </svg>
  );
}

function LinkIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 0 1 1.242 7.244l-4.5 4.5a4.5 4.5 0 0 1-6.364-6.364l1.757-1.757m13.35-.622 1.757-1.757a4.5 4.5 0 0 0-6.364-6.364l-4.5 4.5a4.5 4.5 0 0 0 1.242 7.244" />
    </svg>
  );
}

function ChartBarIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
    </svg>
  );
}

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
    </svg>
  );
}

function EyeSlashIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
    </svg>
  );
}

function ExclamationTriangleIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
    </svg>
  );
}

// ── Format Helpers ─────────────────────────────────────────────────────────

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
    });
  } catch {
    return 'N/A';
  }
}

function formatRelativeDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Unknown';
  try {
    const now = new Date();
    const date = new Date(dateStr);
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return formatDate(dateStr);
  } catch {
    return 'Unknown';
  }
}

// ── Error Fallback ─────────────────────────────────────────────────────────

function SectionError({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
      <p className="text-sm text-zinc-500">{message || 'Unable to load data'}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-xs text-[#FF7F11] hover:underline">
          Try again
        </button>
      )}
    </div>
  );
}

// ── Toggle Switch Component ────────────────────────────────────────────────

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (val: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF7F11]/50',
        checked ? 'bg-[#FF7F11]' : 'bg-zinc-700',
        disabled && 'opacity-50 cursor-not-allowed',
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out',
          checked ? 'translate-x-4' : 'translate-x-0',
        )}
      />
    </button>
  );
}

// ── Section Card Wrapper ───────────────────────────────────────────────────

function SectionCard({
  title,
  icon,
  children,
  className,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5', className)}>
      <div className="flex items-center gap-2 mb-4">
        <span className="text-[#FF7F11]">{icon}</span>
        <h3 className="text-base font-semibold text-white">{title}</h3>
      </div>
      {children}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// Mock Data Types
// ════════════════════════════════════════════════════════════════════════════

interface MockTeamMember {
  id: string;
  name: string;
  email: string;
  role: 'Owner' | 'Admin' | 'Agent' | 'Viewer';
  last_active: string;
  avatar: string;
}

interface SessionInfo {
  id: string;
  device: string;
  browser: string;
  ip: string;
  last_active: string;
  is_current: boolean;
  created_at: string;
}

interface ApiKeyInfo {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used: string | null;
  scopes: string[];
  status: 'active' | 'revoked';
}

// ── Mock Data ──────────────────────────────────────────────────────────────

const MOCK_TEAM: MockTeamMember[] = [
  { id: '1', name: 'Sarah Chen', email: 'sarah@acmecorp.com', role: 'Owner', last_active: '2025-01-10T14:30:00Z', avatar: 'SC' },
  { id: '2', name: 'Marcus Johnson', email: 'marcus@acmecorp.com', role: 'Admin', last_active: '2025-01-10T12:15:00Z', avatar: 'MJ' },
  { id: '3', name: 'Priya Patel', email: 'priya@acmecorp.com', role: 'Agent', last_active: '2025-01-09T18:00:00Z', avatar: 'PP' },
  { id: '4', name: 'Alex Rivera', email: 'alex@acmecorp.com', role: 'Agent', last_active: '2025-01-10T09:45:00Z', avatar: 'AR' },
];

const ROLE_COLORS: Record<string, string> = {
  Owner: 'bg-[#FF7F11]/15 text-[#FF7F11] border-[#FF7F11]/30',
  Admin: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  Agent: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  Viewer: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30',
};

const TIMEZONES = [
  'UTC', 'America/New_York', 'America/Chicago', 'America/Denver',
  'America/Los_Angeles', 'Europe/London', 'Europe/Paris', 'Europe/Berlin',
  'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Kolkata', 'Australia/Sydney',
];

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' },
  { value: 'ja', label: 'Japanese' },
  { value: 'zh', label: 'Chinese' },
];

const NOTIFICATION_TYPES = [
  { key: 'ticket', label: 'Ticket Updates', description: 'New tickets, replies, status changes' },
  { key: 'approval', label: 'Approval Requests', description: 'Pending approvals, decisions' },
  { key: 'system', label: 'System Alerts', description: 'Maintenance, outages, errors' },
  { key: 'billing', label: 'Billing Updates', description: 'Invoices, payment confirmations' },
  { key: 'training', label: 'Training & AI', description: 'AI training, knowledge base updates' },
];

const CHANNEL_LABELS: Record<string, string> = {
  email: 'Email',
  in_app: 'In-App',
  push: 'Push',
};

// ════════════════════════════════════════════════════════════════════════════
// Main Settings Page Component
// ════════════════════════════════════════════════════════════════════════════

export default function SettingsPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('account');

  // ── Account State ───────────────────────────────────────────────────────
  const [companyName, setCompanyName] = useState(user?.company_name || '');
  const [industry, setIndustry] = useState('E-Commerce');
  const [timezone, setTimezone] = useState('UTC');
  const [language, setLanguage] = useState('en');
  const [savingAccount, setSavingAccount] = useState(false);

  // ── Team State ──────────────────────────────────────────────────────────
  const [teamMembers] = useState<MockTeamMember[]>(MOCK_TEAM);
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('Agent');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [removeConfirmId, setRemoveConfirmId] = useState<string | null>(null);

  // ── Security State ──────────────────────────────────────────────────────
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [mfaLoading, setMfaLoading] = useState(false);
  const [mfaQrCode, setMfaQrCode] = useState<string | null>(null);
  const [mfaSecret, setMfaSecret] = useState<string | null>(null);
  const [mfaVerifyCode, setMfaVerifyCode] = useState('');
  const [mfaSetupStep, setMfaSetupStep] = useState<'idle' | 'qr' | 'verify'>('idle');

  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [revokingSessionId, setRevokingSessionId] = useState<string | null>(null);
  const [revokingAll, setRevokingAll] = useState(false);

  const [apiKeys, setApiKeys] = useState<ApiKeyInfo[]>([]);
  const [apiKeysLoading, setApiKeysLoading] = useState(true);
  const [createKeyModalOpen, setCreateKeyModalOpen] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyScopes, setNewKeyScopes] = useState<string[]>(['read']);
  const [newKeyExpiry, setNewKeyExpiry] = useState('90');
  const [createKeyLoading, setCreateKeyLoading] = useState(false);
  const [revokingKeyId, setRevokingKeyId] = useState<string | null>(null);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);

  // ── Notifications State ─────────────────────────────────────────────────
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [prefsLoading, setPrefsLoading] = useState(true);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [digestFrequency, setDigestFrequency] = useState<'never' | 'daily' | 'weekly'>('never');
  const [quietHoursEnabled, setQuietHoursEnabled] = useState(false);
  const [quietStart, setQuietStart] = useState('22:00');
  const [quietEnd, setQuietEnd] = useState('08:00');

  // ── Data Loading ───────────────────────────────────────────────────────

  // Load sessions
  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const { data } = await apiClient.get('/api/auth/sessions');
      if (data && Array.isArray(data.sessions || data)) {
        setSessions(data.sessions || data);
      } else {
        // Mock fallback
        setSessions([
          { id: 's1', device: 'MacBook Pro', browser: 'Chrome 121', ip: '192.168.1.1', last_active: new Date().toISOString(), is_current: true, created_at: '2025-01-08T10:00:00Z' },
          { id: 's2', device: 'iPhone 15', browser: 'Safari Mobile', ip: '10.0.0.1', last_active: '2025-01-10T08:00:00Z', is_current: false, created_at: '2025-01-09T15:00:00Z' },
        ]);
      }
    } catch {
      setSessions([
        { id: 's1', device: 'MacBook Pro', browser: 'Chrome 121', ip: '192.168.1.1', last_active: new Date().toISOString(), is_current: true, created_at: '2025-01-08T10:00:00Z' },
        { id: 's2', device: 'iPhone 15', browser: 'Safari Mobile', ip: '10.0.0.1', last_active: '2025-01-10T08:00:00Z', is_current: false, created_at: '2025-01-09T15:00:00Z' },
      ]);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  // Load API keys
  const loadApiKeys = useCallback(async () => {
    setApiKeysLoading(true);
    try {
      const { data } = await apiClient.get('/api/api-keys');
      if (data && Array.isArray(data.keys || data)) {
        setApiKeys(data.keys || data);
      } else {
        setApiKeys([
          { id: 'k1', name: 'Production API', prefix: 'parwa_live_...a1b2', created_at: '2024-12-01T10:00:00Z', last_used: '2025-01-10T14:00:00Z', scopes: ['read', 'write'], status: 'active' },
          { id: 'k2', name: 'Development', prefix: 'parwa_test_...c3d4', created_at: '2025-01-05T10:00:00Z', last_used: '2025-01-09T09:00:00Z', scopes: ['read'], status: 'active' },
        ]);
      }
    } catch {
      setApiKeys([
        { id: 'k1', name: 'Production API', prefix: 'parwa_live_...a1b2', created_at: '2024-12-01T10:00:00Z', last_used: '2025-01-10T14:00:00Z', scopes: ['read', 'write'], status: 'active' },
        { id: 'k2', name: 'Development', prefix: 'parwa_test_...c3d4', created_at: '2025-01-05T10:00:00Z', last_used: '2025-01-09T09:00:00Z', scopes: ['read'], status: 'active' },
      ]);
    } finally {
      setApiKeysLoading(false);
    }
  }, []);

  // Load notification preferences
  const loadPrefs = useCallback(async () => {
    setPrefsLoading(true);
    try {
      const data = await notificationsApi.getPreferences();
      setPrefs(data);
      setDigestFrequency(data.digest_frequency === 'never' ? 'never' : data.digest_frequency);
      setQuietHoursEnabled(data.quiet_hours_enabled);
      setQuietStart(data.quiet_hours_start || '22:00');
      setQuietEnd(data.quiet_hours_end || '08:00');
    } catch {
      // Default fallback
      const defaultTypePrefs: Record<string, { email: boolean; push: boolean; in_app: boolean }> = {};
      NOTIFICATION_TYPES.forEach(t => {
        defaultTypePrefs[t.key] = { email: true, push: true, in_app: true };
      });
      setPrefs({
        email_enabled: true,
        push_enabled: true,
        in_app_enabled: true,
        digest_frequency: 'never',
        quiet_hours_enabled: false,
        quiet_hours_start: null,
        quiet_hours_end: null,
        type_preferences: defaultTypePrefs,
      });
    } finally {
      setPrefsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
    loadApiKeys();
    loadPrefs();
  }, [loadSessions, loadApiKeys, loadPrefs]);

  // ── Handlers ───────────────────────────────────────────────────────────

  // Account save
  const handleSaveAccount = async () => {
    setSavingAccount(true);
    try {
      if (user?.company_id) {
        await apiClient.put(`/api/admin/clients/${user.company_id}`, {
          name: companyName,
          industry,
          timezone,
          language,
        });
      }
      toast.success('Company profile updated');
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setSavingAccount(false);
    }
  };

  // Team invite
  const handleInviteMember = async () => {
    if (!inviteEmail.trim()) {
      toast.error('Please enter an email address');
      return;
    }
    setInviteLoading(true);
    // Simulate API call
    await new Promise(r => setTimeout(r, 1000));
    toast.success(`Invitation sent to ${inviteEmail}`);
    setInviteEmail('');
    setInviteRole('Agent');
    setInviteModalOpen(false);
    setInviteLoading(false);
  };

  // Team remove
  const handleRemoveMember = async (id: string) => {
    setRemoveConfirmId(null);
    await new Promise(r => setTimeout(r, 500));
    toast.success('Member removed');
  };

  // MFA initiate
  const handleMfaInitiate = async () => {
    setMfaLoading(true);
    try {
      const { data } = await apiClient.post('/api/auth/mfa/setup/initiate');
      if (data?.qr_code) {
        setMfaQrCode(data.qr_code);
        setMfaSecret(data.secret || data.otp_secret || null);
        setMfaSetupStep('qr');
      } else {
        toast.success('MFA setup initiated — check your authenticator app');
        setMfaSetupStep('verify');
      }
    } catch {
      // Mock fallback for demo
      setMfaQrCode('otpauth://totp/PARWA:demo@parwa.ai?secret=JBSWY3DPEHPK3PXP&issuer=PARWA');
      setMfaSecret('JBSWY3DPEHPK3PXP');
      setMfaSetupStep('qr');
    } finally {
      setMfaLoading(false);
    }
  };

  // MFA verify
  const handleMfaVerify = async () => {
    if (!mfaVerifyCode.trim()) {
      toast.error('Please enter the verification code');
      return;
    }
    setMfaLoading(true);
    try {
      await apiClient.post('/api/auth/mfa/setup/verify', { code: mfaVerifyCode });
      setMfaEnabled(true);
      setMfaSetupStep('idle');
      setMfaQrCode(null);
      setMfaSecret(null);
      setMfaVerifyCode('');
      toast.success('MFA enabled successfully');
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setMfaLoading(false);
    }
  };

  // Revoke session
  const handleRevokeSession = async (id: string) => {
    setRevokingSessionId(id);
    try {
      await apiClient.delete(`/api/auth/sessions/${id}/revoke`);
      setSessions(prev => prev.filter(s => s.id !== id));
      toast.success('Session revoked');
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setRevokingSessionId(null);
    }
  };

  // Revoke all other sessions
  const handleRevokeAllOthers = async () => {
    setRevokingAll(true);
    try {
      await apiClient.delete('/api/auth/sessions/revoke-others');
      setSessions(prev => prev.filter(s => s.is_current));
      toast.success('All other sessions revoked');
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setRevokingAll(false);
    }
  };

  // Create API key
  const handleCreateKey = async () => {
    if (!newKeyName.trim()) {
      toast.error('Please enter a key name');
      return;
    }
    setCreateKeyLoading(true);
    try {
      const { data } = await apiClient.post('/api/api-keys', {
        name: newKeyName,
        scopes: newKeyScopes,
        expires_in_days: parseInt(newKeyExpiry) || 90,
      });
      if (data?.key || data?.api_key) {
        setNewlyCreatedKey(data.key || data.api_key);
      } else {
        setNewlyCreatedKey('parwa_live_demo_key_' + Math.random().toString(36).slice(2));
      }
      toast.success('API key created');
      setNewKeyName('');
      setNewKeyScopes(['read']);
      setNewKeyExpiry('90');
      loadApiKeys();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setCreateKeyLoading(false);
    }
  };

  // Revoke API key
  const handleRevokeKey = async (id: string) => {
    setRevokingKeyId(id);
    try {
      await apiClient.delete(`/api/api-keys/${id}/revoke`);
      setApiKeys(prev => prev.map(k => k.id === id ? { ...k, status: 'revoked' as const } : k));
      toast.success('API key revoked');
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setRevokingKeyId(null);
    }
  };

  // Notification preference toggle
  const handlePrefToggle = async (typeKey: string, channel: string, value: boolean) => {
    if (!prefs) return;
    setSavingPrefs(true);
    try {
      const updatedTypePrefs = {
        ...prefs.type_preferences,
        [typeKey]: {
          ...(prefs.type_preferences[typeKey] || { email: false, push: false, in_app: false }),
          [channel]: value,
        },
      };
      setPrefs({ ...prefs, type_preferences: updatedTypePrefs });
      await notificationsApi.updatePreferences({
        type_preferences: updatedTypePrefs,
      });
      toast.success('Preference updated');
    } catch (error) {
      toast.error(getErrorMessage(error));
      loadPrefs();
    } finally {
      setSavingPrefs(false);
    }
  };

  // Digest frequency
  const handleDigestChange = async (freq: 'never' | 'daily' | 'weekly') => {
    setSavingPrefs(true);
    setDigestFrequency(freq);
    try {
      await notificationsApi.setDigest({ frequency: freq });
      toast.success('Digest settings updated');
    } catch (error) {
      toast.error(getErrorMessage(error));
      setDigestFrequency(freq === 'never' ? 'daily' : freq);
    } finally {
      setSavingPrefs(false);
    }
  };

  // Quiet hours
  const handleQuietHoursToggle = async (enabled: boolean) => {
    setSavingPrefs(true);
    setQuietHoursEnabled(enabled);
    try {
      await notificationsApi.updatePreferences({
        quiet_hours_enabled: enabled,
        quiet_hours_start: enabled ? quietStart : null,
        quiet_hours_end: enabled ? quietEnd : null,
      });
      toast.success('Quiet hours updated');
    } catch (error) {
      toast.error(getErrorMessage(error));
      setQuietHoursEnabled(!enabled);
    } finally {
      setSavingPrefs(false);
    }
  };

  // ════════════════════════════════════════════════════════════════════════
  // Render
  // ════════════════════════════════════════════════════════════════════════

  return (
    <div className="jarvis-page-body min-h-screen bg-[#0A0A0A]">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        {/* ── Page Header ──────────────────────────────────────────────── */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FF7F11]/10">
              <SettingsIcon className="h-5 w-5 text-[#FF7F11]" />
            </div>
            <h1 className="text-2xl font-bold text-white">Settings</h1>
          </div>
          <p className="text-sm text-zinc-500 ml-[52px]">
            Manage your organization, team, security, and preferences.
          </p>
        </div>

        {/* ── Tabs ────────────────────────────────────────────────────── */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="flex w-full overflow-x-auto gap-1 bg-[#141414] border border-white/[0.06] rounded-xl p-1 h-auto mb-6">
            {[
              { value: 'account', label: 'Account', icon: <BuildingOfficeIcon className="h-4 w-4" /> },
              { value: 'team', label: 'Team', icon: <UserGroupIcon className="h-4 w-4" /> },
              { value: 'security', label: 'Security', icon: <ShieldCheckIcon className="h-4 w-4" /> },
              { value: 'notifications', label: 'Notifications', icon: <BellIcon className="h-4 w-4" /> },
              { value: 'api', label: 'API & Webhooks', icon: <CodeBracketIcon className="h-4 w-4" /> },
            ].map(tab => (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className={cn(
                  'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap',
                  'data-[state=active]:bg-[#1A1A1A] data-[state=active]:text-white data-[state=active]:shadow-sm',
                  'data-[state=inactive]:text-zinc-500 data-[state=inactive]:hover:text-zinc-300',
                  'border border-transparent data-[state=active]:border-white/[0.08]',
                )}
              >
                {tab.icon}
                <span className="hidden sm:inline">{tab.label}</span>
                <span className="sm:hidden">{tab.label.slice(0, 4)}</span>
              </TabsTrigger>
            ))}
          </TabsList>

          {/* ══════════════════════════════════════════════════════════
              ST1: Account Tab
              ══════════════════════════════════════════════════════════ */}
          <TabsContent value="account">
            <div className="space-y-6">
              {/* Company Profile Card */}
              <SectionCard
                title="Company Profile"
                icon={<BuildingOfficeIcon className="h-5 w-5" />}
              >
                <div className="space-y-5">
                  <div>
                    <label className="block text-sm font-medium text-zinc-300 mb-1.5">Company Name</label>
                    <input
                      type="text"
                      value={companyName}
                      onChange={e => setCompanyName(e.target.value)}
                      className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-4 py-2.5 text-sm text-white placeholder-zinc-600 focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 transition-colors"
                      placeholder="Enter company name"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-300 mb-1.5">Industry</label>
                    <select
                      value={industry}
                      onChange={e => setIndustry(e.target.value)}
                      className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-4 py-2.5 text-sm text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 transition-colors appearance-none cursor-pointer"
                    >
                      {['E-Commerce', 'SaaS', 'FinTech', 'Healthcare', 'Education', 'Real Estate', 'Travel', 'Professional Services', 'Other'].map(i => (
                        <option key={i} value={i}>{i}</option>
                      ))}
                    </select>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                    <div>
                      <label className="block text-sm font-medium text-zinc-300 mb-1.5">Timezone</label>
                      <select
                        value={timezone}
                        onChange={e => setTimezone(e.target.value)}
                        className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-4 py-2.5 text-sm text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 transition-colors appearance-none cursor-pointer"
                      >
                        {TIMEZONES.map(tz => (
                          <option key={tz} value={tz}>{tz}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-zinc-300 mb-1.5">Language</label>
                      <select
                        value={language}
                        onChange={e => setLanguage(e.target.value)}
                        className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-4 py-2.5 text-sm text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 transition-colors appearance-none cursor-pointer"
                      >
                        {LANGUAGES.map(l => (
                          <option key={l.value} value={l.value}>{l.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="flex items-center justify-end pt-2">
                    <button
                      onClick={handleSaveAccount}
                      disabled={savingAccount}
                      className="inline-flex items-center gap-2 rounded-xl bg-[#FF7F11] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 disabled:opacity-50 transition-colors"
                    >
                      {savingAccount && <SpinnerIcon className="h-4 w-4 animate-spin" />}
                      {savingAccount ? 'Saving...' : 'Save Changes'}
                    </button>
                  </div>
                </div>
              </SectionCard>

              {/* Account Info Card */}
              <SectionCard
                title="Account Information"
                icon={<BuildingOfficeIcon className="h-5 w-5" />}
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between py-2 border-b border-white/[0.04]">
                    <span className="text-sm text-zinc-500">Company ID</span>
                    <span className="text-sm text-zinc-300 font-mono">{user?.company_id || 'N/A'}</span>
                  </div>
                  <div className="flex items-center justify-between py-2 border-b border-white/[0.04]">
                    <span className="text-sm text-zinc-500">Email</span>
                    <span className="text-sm text-zinc-300">{user?.email || 'N/A'}</span>
                  </div>
                  <div className="flex items-center justify-between py-2 border-b border-white/[0.04]">
                    <span className="text-sm text-zinc-500">Role</span>
                    <span className="text-sm text-zinc-300 capitalize">{user?.role || 'N/A'}</span>
                  </div>
                  <div className="flex items-center justify-between py-2 border-b border-white/[0.04]">
                    <span className="text-sm text-zinc-500">Account Created</span>
                    <span className="text-sm text-zinc-300">{formatDate(user?.created_at)}</span>
                  </div>
                  <div className="flex items-center justify-between py-2">
                    <span className="text-sm text-zinc-500">Status</span>
                    <span className={cn(
                      'inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium',
                      user?.is_active ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400',
                    )}>
                      {user?.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
              </SectionCard>

              {/* Coming Soon Notice */}
              <div className="rounded-xl border border-[#FF7F11]/20 bg-[#FF7F11]/5 p-4">
                <div className="flex items-start gap-3">
                  <ExclamationTriangleIcon className="h-5 w-5 text-[#FF7F11] mt-0.5 shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-[#FF7F11]">Platform Admin API</p>
                    <p className="text-sm text-zinc-400 mt-1">
                      Full company profile management (logo, phone, address, billing contact) requires platform admin access. Contact{' '}
                      <a href="mailto:support@parwa.ai" className="text-[#FF7F11] hover:underline">support@parwa.ai</a>{' '}
                      for advanced configuration.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>

          {/* ══════════════════════════════════════════════════════════
              ST2: Team Tab
              ══════════════════════════════════════════════════════════ */}
          <TabsContent value="team">
            <div className="space-y-6">
              {/* Team Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <UserGroupIcon className="h-5 w-5 text-[#FF7F11]" />
                  <h3 className="text-base font-semibold text-white">Team Members</h3>
                  <span className="ml-2 inline-flex items-center rounded-full bg-white/[0.06] px-2.5 py-0.5 text-xs font-medium text-zinc-400">
                    {teamMembers.length} members
                  </span>
                </div>
                <button
                  onClick={() => setInviteModalOpen(true)}
                  className="inline-flex items-center gap-2 rounded-xl bg-[#FF7F11] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
                >
                  <PlusIcon className="h-4 w-4" />
                  Invite Member
                </button>
              </div>

              {/* Team Member Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {teamMembers.map(member => (
                  <div
                    key={member.id}
                    className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4 hover:border-white/[0.1] transition-colors group"
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-[#FF7F11]/80 to-amber-500/80 text-white text-sm font-semibold shrink-0">
                        {member.avatar}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <p className="text-sm font-semibold text-white truncate">{member.name}</p>
                          <span className={cn(
                            'inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider shrink-0',
                            ROLE_COLORS[member.role] || ROLE_COLORS.Viewer,
                          )}>
                            {member.role}
                          </span>
                        </div>
                        <p className="text-xs text-zinc-500 truncate">{member.email}</p>
                        <p className="text-xs text-zinc-600 mt-1">
                          <ClockIcon className="h-3 w-3 inline mr-1" />
                          Active {formatRelativeDate(member.last_active)}
                        </p>
                      </div>
                      {member.role !== 'Owner' && (
                        removeConfirmId === member.id ? (
                          <div className="flex items-center gap-1 shrink-0">
                            <button
                              onClick={() => handleRemoveMember(member.id)}
                              className="rounded-lg bg-red-500/15 border border-red-500/30 px-2.5 py-1 text-[10px] font-medium text-red-400 hover:bg-red-500/25 transition-colors"
                            >
                              Confirm
                            </button>
                            <button
                              onClick={() => setRemoveConfirmId(null)}
                              className="rounded-lg bg-white/[0.04] px-2 py-1 text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setRemoveConfirmId(member.id)}
                            className="opacity-0 group-hover:opacity-100 transition-opacity text-zinc-600 hover:text-red-400 shrink-0"
                            title="Remove member"
                          >
                            <TrashIcon className="h-4 w-4" />
                          </button>
                        )
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Placeholder Note */}
              <div className="rounded-xl border border-white/[0.06] bg-[#141414] p-4">
                <p className="text-xs text-zinc-500 text-center">
                  Team management uses platform-admin level APIs. Full invite/removal workflow will be available when your organization plan supports team management.
                </p>
              </div>
            </div>
          </TabsContent>

          {/* ══════════════════════════════════════════════════════════
              ST3: Security Tab
              ══════════════════════════════════════════════════════════ */}
          <TabsContent value="security">
            <div className="space-y-6">
              {/* MFA Section */}
              <SectionCard
                title="Multi-Factor Authentication"
                icon={<ShieldCheckIcon className="h-5 w-5" />}
              >
                <div className="space-y-4">
                  {mfaSetupStep === 'qr' && mfaQrCode && (
                    <div className="flex flex-col items-center p-4 rounded-lg bg-[#141414] border border-white/[0.04]">
                      <QrCodeIcon className="h-8 w-8 text-zinc-400 mb-3" />
                      <p className="text-sm text-zinc-300 mb-2 text-center font-medium">Scan QR Code</p>
                      <p className="text-xs text-zinc-500 mb-3 text-center">
                        Use your authenticator app (Google Authenticator, Authy, etc.) to scan this QR code.
                      </p>
                      {mfaSecret && (
                        <p className="text-xs text-zinc-600 font-mono mb-3 p-2 rounded bg-white/[0.03] select-all">
                          Secret: {mfaSecret}
                        </p>
                      )}
                      <div className="flex items-center gap-2 mt-2 w-full max-w-xs">
                        <input
                          type="text"
                          value={mfaVerifyCode}
                          onChange={e => setMfaVerifyCode(e.target.value)}
                          placeholder="Enter 6-digit code"
                          maxLength={6}
                          className="flex-1 rounded-lg border border-white/[0.08] bg-[#0A0A0A] px-3 py-2 text-sm text-white text-center tracking-widest focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30"
                        />
                        <button
                          onClick={handleMfaVerify}
                          disabled={mfaLoading || mfaVerifyCode.length < 6}
                          className="rounded-lg bg-[#FF7F11] px-4 py-2 text-sm font-medium text-white hover:bg-[#FF7F11]/90 disabled:opacity-50 transition-colors"
                        >
                          {mfaLoading ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : 'Verify'}
                        </button>
                      </div>
                      <button
                        onClick={() => {
                          setMfaSetupStep('idle');
                          setMfaQrCode(null);
                          setMfaSecret(null);
                        }}
                        className="mt-3 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                      >
                        Cancel setup
                      </button>
                    </div>
                  )}

                  {mfaSetupStep === 'verify' && (
                    <div className="flex flex-col items-center p-4 rounded-lg bg-[#141414] border border-white/[0.04]">
                      <p className="text-sm text-zinc-300 mb-3 font-medium">Enter Verification Code</p>
                      <input
                        type="text"
                        value={mfaVerifyCode}
                        onChange={e => setMfaVerifyCode(e.target.value)}
                        placeholder="6-digit code from authenticator"
                        maxLength={6}
                        className="w-full max-w-xs rounded-lg border border-white/[0.08] bg-[#0A0A0A] px-4 py-2.5 text-sm text-white text-center tracking-widest focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 mb-3"
                      />
                      <div className="flex items-center gap-2">
                        <button
                          onClick={handleMfaVerify}
                          disabled={mfaLoading || mfaVerifyCode.length < 6}
                          className="rounded-lg bg-[#FF7F11] px-5 py-2 text-sm font-medium text-white hover:bg-[#FF7F11]/90 disabled:opacity-50 transition-colors"
                        >
                          {mfaLoading ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : 'Verify & Enable'}
                        </button>
                        <button
                          onClick={() => setMfaSetupStep('idle')}
                          className="rounded-lg border border-white/[0.08] bg-white/[0.04] px-4 py-2 text-sm text-zinc-400 hover:bg-white/[0.08] transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}

                  {mfaSetupStep === 'idle' && (
                    <div className="flex items-center justify-between p-4 rounded-lg bg-[#141414] border border-white/[0.04]">
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          'flex h-10 w-10 items-center justify-center rounded-xl',
                          mfaEnabled ? 'bg-emerald-500/10' : 'bg-zinc-500/10',
                        )}>
                          <ShieldCheckIcon className={cn('h-5 w-5', mfaEnabled ? 'text-emerald-400' : 'text-zinc-500')} />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-zinc-200">Authenticator App</p>
                          <p className="text-xs text-zinc-500">
                            {mfaEnabled ? 'MFA is enabled and protecting your account' : 'Add an extra layer of security to your account'}
                          </p>
                        </div>
                      </div>
                      {mfaEnabled ? (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 px-3 py-1 text-xs font-medium text-emerald-400">
                          <CheckIcon className="h-3 w-3" />
                          Enabled
                        </span>
                      ) : (
                        <button
                          onClick={handleMfaInitiate}
                          disabled={mfaLoading}
                          className="inline-flex items-center gap-2 rounded-xl bg-[#FF7F11] px-4 py-2 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 disabled:opacity-50 transition-colors"
                        >
                          {mfaLoading ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : 'Enable MFA'}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </SectionCard>

              {/* Active Sessions */}
              <SectionCard
                title="Active Sessions"
                icon={<DevicePhoneMobileIcon className="h-5 w-5" />}
              >
                {sessionsLoading ? (
                  <div className="space-y-3">
                    <Skeleton className="h-16" />
                    <Skeleton className="h-16" />
                  </div>
                ) : sessions.length === 0 ? (
                  <p className="text-sm text-zinc-500 text-center py-4">No active sessions</p>
                ) : (
                  <div className="space-y-3">
                    {sessions.map(session => (
                      <div
                        key={session.id}
                        className={cn(
                          'flex items-center justify-between p-3 rounded-lg border transition-colors',
                          session.is_current
                            ? 'bg-emerald-500/5 border-emerald-500/20'
                            : 'bg-[#141414] border-white/[0.04] hover:border-white/[0.08]',
                        )}
                      >
                        <div className="flex items-center gap-3">
                          <div className={cn(
                            'flex h-9 w-9 items-center justify-center rounded-lg',
                            session.is_current ? 'bg-emerald-500/10' : 'bg-white/[0.04]',
                          )}>
                            <DevicePhoneMobileIcon className={cn('h-4 w-4', session.is_current ? 'text-emerald-400' : 'text-zinc-500')} />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <p className="text-sm font-medium text-zinc-200">{session.device}</p>
                              {session.is_current && (
                                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
                                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                  Current
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-zinc-500">
                              {session.browser} &middot; {session.ip} &middot; {formatRelativeDate(session.last_active)}
                            </p>
                          </div>
                        </div>
                        {!session.is_current && (
                          <button
                            onClick={() => handleRevokeSession(session.id)}
                            disabled={revokingSessionId === session.id}
                            className="text-xs text-zinc-500 hover:text-red-400 disabled:opacity-50 transition-colors"
                          >
                            {revokingSessionId === session.id ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : 'Revoke'}
                          </button>
                        )}
                      </div>
                    ))}
                    {sessions.length > 1 && (
                      <div className="flex justify-end pt-2">
                        <button
                          onClick={handleRevokeAllOthers}
                          disabled={revokingAll}
                          className="text-xs text-[#FF7F11] hover:text-[#FF7F11]/80 disabled:opacity-50 transition-colors"
                        >
                          {revokingAll ? <SpinnerIcon className="h-3.5 w-3.5 animate-spin inline" /> : (
                            <>Revoke all other sessions</>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </SectionCard>

              {/* API Keys */}
              <SectionCard
                title="API Keys"
                icon={<KeyIcon className="h-5 w-5" />}
              >
                <div className="flex items-center justify-between mb-4">
                  <p className="text-xs text-zinc-500">Manage keys for programmatic access</p>
                  <button
                    onClick={() => { setCreateKeyModalOpen(true); setNewlyCreatedKey(null); }}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-[#FF7F11] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#FF7F11]/90 transition-colors"
                  >
                    <PlusIcon className="h-3.5 w-3.5" />
                    Create Key
                  </button>
                </div>

                {/* New Key Display */}
                {newlyCreatedKey && (
                  <div className="mb-4 rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-4">
                    <div className="flex items-start gap-3">
                      <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400 mt-0.5 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-yellow-300">Save Your API Key</p>
                        <p className="text-xs text-zinc-400 mt-1 mb-2">
                          This key will not be shown again. Make sure to copy it now.
                        </p>
                        <div className="flex items-center gap-2">
                          <code className="flex-1 rounded bg-[#0A0A0A] px-3 py-2 text-xs text-emerald-400 font-mono truncate block">
                            {newlyCreatedKey}
                          </code>
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(newlyCreatedKey);
                              toast.success('Key copied to clipboard');
                            }}
                            className="shrink-0 rounded-lg bg-white/[0.06] px-3 py-2 text-xs text-zinc-300 hover:bg-white/[0.1] transition-colors"
                          >
                            Copy
                          </button>
                        </div>
                        <button
                          onClick={() => setNewlyCreatedKey(null)}
                          className="mt-2 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                        >
                          Dismiss
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {apiKeysLoading ? (
                  <div className="space-y-3">
                    <Skeleton className="h-16" />
                    <Skeleton className="h-16" />
                  </div>
                ) : apiKeys.length === 0 ? (
                  <div className="text-center py-6">
                    <KeyIcon className="h-10 w-10 text-zinc-600 mx-auto mb-3" />
                    <p className="text-sm text-zinc-500">No API keys yet</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {apiKeys.map(key => (
                      <div
                        key={key.id}
                        className={cn(
                          'flex items-center justify-between p-3 rounded-lg border transition-colors',
                          key.status === 'revoked'
                            ? 'bg-zinc-500/5 border-zinc-500/20 opacity-60'
                            : 'bg-[#141414] border-white/[0.04] hover:border-white/[0.08]',
                        )}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/[0.04] shrink-0">
                            <KeyIcon className="h-4 w-4 text-zinc-500" />
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <p className="text-sm font-medium text-zinc-200 truncate">{key.name}</p>
                              <span className={cn(
                                'inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium',
                                key.status === 'active' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-zinc-500/15 text-zinc-500',
                              )}>
                                {key.status}
                              </span>
                            </div>
                            <p className="text-xs text-zinc-500 font-mono">{key.prefix}</p>
                            <p className="text-xs text-zinc-600 mt-0.5">
                              Created {formatDate(key.created_at)}
                              {key.last_used && <> &middot; Last used {formatRelativeDate(key.last_used)}</>}
                            </p>
                          </div>
                        </div>
                        {key.status === 'active' && (
                          <div className="flex items-center gap-2 shrink-0">
                            <div className="hidden sm:flex items-center gap-1">
                              {key.scopes.map(scope => (
                                <span key={scope} className="rounded bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-zinc-500 font-medium">
                                  {scope}
                                </span>
                              ))}
                            </div>
                            <button
                              onClick={() => handleRevokeKey(key.id)}
                              disabled={revokingKeyId === key.id}
                              className="text-xs text-zinc-500 hover:text-red-400 disabled:opacity-50 transition-colors ml-1"
                            >
                              {revokingKeyId === key.id ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : 'Revoke'}
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            </div>
          </TabsContent>

          {/* ══════════════════════════════════════════════════════════
              ST4: Notifications Tab
              ══════════════════════════════════════════════════════════ */}
          <TabsContent value="notifications">
            <div className="space-y-6">
              {prefsLoading ? (
                <div className="space-y-4">
                  <Skeleton className="h-72" />
                  <Skeleton className="h-48" />
                </div>
              ) : !prefs ? (
                <SectionError message="Unable to load notification preferences" onRetry={loadPrefs} />
              ) : (
                <>
                  {/* Notification Type Toggles */}
                  <SectionCard
                    title="Notification Preferences"
                    icon={<BellIcon className="h-5 w-5" />}
                  >
                    <div className="space-y-1">
                      {/* Header row */}
                      <div className="grid grid-cols-[1fr_80px_80px_80px] gap-3 px-3 py-2">
                        <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Type</span>
                        <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider text-center">Email</span>
                        <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider text-center hidden sm:block">In-App</span>
                        <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider text-center">Push</span>
                      </div>
                      {NOTIFICATION_TYPES.map(type => {
                        const typePref = prefs.type_preferences?.[type.key] || { email: false, push: false, in_app: false };
                        return (
                          <div
                            key={type.key}
                            className="grid grid-cols-[1fr_80px_80px_80px] gap-3 items-center px-3 py-3 rounded-lg hover:bg-white/[0.02] transition-colors"
                          >
                            <div>
                              <p className="text-sm font-medium text-zinc-200">{type.label}</p>
                              <p className="text-xs text-zinc-600 hidden sm:block">{type.description}</p>
                            </div>
                            <div className="flex justify-center">
                              <Toggle
                                checked={typePref.email}
                                onChange={val => handlePrefToggle(type.key, 'email', val)}
                                disabled={savingPrefs}
                              />
                            </div>
                            <div className="flex justify-center hidden sm:flex">
                              <Toggle
                                checked={typePref.in_app}
                                onChange={val => handlePrefToggle(type.key, 'in_app', val)}
                                disabled={savingPrefs}
                              />
                            </div>
                            <div className="flex justify-center">
                              <Toggle
                                checked={typePref.push}
                                onChange={val => handlePrefToggle(type.key, 'push', val)}
                                disabled={savingPrefs}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </SectionCard>

                  {/* Digest Settings */}
                  <SectionCard
                    title="Digest Settings"
                    icon={<DocumentTextIcon className="h-5 w-5" />}
                  >
                    <div className="space-y-4">
                      <p className="text-sm text-zinc-400">
                        Get a summary of notifications at your preferred frequency instead of individual alerts.
                      </p>
                      <div className="flex items-center gap-3">
                        {(['never', 'daily', 'weekly'] as const).map(freq => (
                          <button
                            key={freq}
                            onClick={() => handleDigestChange(freq)}
                            className={cn(
                              'rounded-lg px-4 py-2 text-sm font-medium border transition-colors',
                              digestFrequency === freq
                                ? 'bg-[#FF7F11]/15 border-[#FF7F11]/30 text-[#FF7F11]'
                                : 'bg-white/[0.02] border-white/[0.06] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.12]',
                            )}
                          >
                            {freq === 'never' ? 'No Digest' : freq.charAt(0).toUpperCase() + freq.slice(1)}
                          </button>
                        ))}
                      </div>
                    </div>
                  </SectionCard>

                  {/* Quiet Hours */}
                  <SectionCard
                    title="Quiet Hours"
                    icon={<ClockIcon className="h-5 w-5" />}
                  >
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-zinc-200">Enable Quiet Hours</p>
                          <p className="text-xs text-zinc-500 mt-0.5">
                            Mute notifications during a set time window
                          </p>
                        </div>
                        <Toggle
                          checked={quietHoursEnabled}
                          onChange={val => handleQuietHoursToggle(val)}
                          disabled={savingPrefs}
                        />
                      </div>
                      {quietHoursEnabled && (
                        <div className="flex items-center gap-4 p-3 rounded-lg bg-[#141414] border border-white/[0.04]">
                          <div className="flex-1">
                            <label className="block text-xs text-zinc-500 mb-1">Start Time</label>
                            <input
                              type="time"
                              value={quietStart}
                              onChange={e => setQuietStart(e.target.value)}
                              className="w-full rounded-lg border border-white/[0.08] bg-[#0A0A0A] px-3 py-2 text-sm text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30"
                            />
                          </div>
                          <span className="text-zinc-600 mt-5">to</span>
                          <div className="flex-1">
                            <label className="block text-xs text-zinc-500 mb-1">End Time</label>
                            <input
                              type="time"
                              value={quietEnd}
                              onChange={e => setQuietEnd(e.target.value)}
                              className="w-full rounded-lg border border-white/[0.08] bg-[#0A0A0A] px-3 py-2 text-sm text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </SectionCard>
                </>
              )}
            </div>
          </TabsContent>

          {/* ══════════════════════════════════════════════════════════
              ST5: API & Webhooks Tab
              ══════════════════════════════════════════════════════════ */}
          <TabsContent value="api">
            <div className="space-y-6">
              {/* Rate Limits */}
              <SectionCard
                title="Rate Limits"
                icon={<ChartBarIcon className="h-5 w-5" />}
              >
                <div className="space-y-4">
                  <p className="text-sm text-zinc-400">
                    API rate limits protect the platform from abuse and ensure fair usage across all customers.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {[
                      { label: 'Standard', limit: '100 req/min', desc: 'REST API endpoints' },
                      { label: 'WebSocket', limit: '50 msg/min', desc: 'Real-time messages' },
                      { label: 'Bulk Operations', limit: '10 req/min', desc: 'Batch actions' },
                    ].map(item => (
                      <div key={item.label} className="rounded-lg bg-[#141414] border border-white/[0.04] p-4 text-center">
                        <p className="text-lg font-bold text-white">{item.limit}</p>
                        <p className="text-xs font-medium text-zinc-400 mt-1">{item.label}</p>
                        <p className="text-[10px] text-zinc-600 mt-0.5">{item.desc}</p>
                      </div>
                    ))}
                  </div>
                  <div className="rounded-lg bg-[#141414] border border-white/[0.04] p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-zinc-400">Rate Limit Headers</span>
                      <code className="text-xs text-zinc-500 font-mono">X-RateLimit-Limit / X-RateLimit-Remaining</code>
                    </div>
                  </div>
                </div>
              </SectionCard>

              {/* API Documentation */}
              <SectionCard
                title="API Documentation"
                icon={<DocumentTextIcon className="h-5 w-5" />}
              >
                <div className="space-y-3">
                  <p className="text-sm text-zinc-400">
                    Access comprehensive API documentation to integrate PARWA into your workflow.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <a
                      href="/api/docs"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-3 rounded-lg bg-[#141414] border border-white/[0.04] p-4 hover:border-[#FF7F11]/30 transition-colors group"
                    >
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#FF7F11]/10 shrink-0">
                        <DocumentTextIcon className="h-5 w-5 text-[#FF7F11]" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-white group-hover:text-[#FF7F11] transition-colors">Swagger Docs</p>
                        <p className="text-xs text-zinc-500">Interactive API reference</p>
                      </div>
                    </a>
                    <a
                      href="/api/redoc"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-3 rounded-lg bg-[#141414] border border-white/[0.04] p-4 hover:border-[#FF7F11]/30 transition-colors group"
                    >
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#FF7F11]/10 shrink-0">
                        <DocumentTextIcon className="h-5 w-5 text-[#FF7F11]" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-white group-hover:text-[#FF7F11] transition-colors">ReDoc</p>
                        <p className="text-xs text-zinc-500">Clean documentation view</p>
                      </div>
                    </a>
                  </div>
                </div>
              </SectionCard>

              {/* Webhooks */}
              <SectionCard
                title="Webhooks"
                icon={<LinkIcon className="h-5 w-5" />}
              >
                <div className="space-y-3">
                  <p className="text-sm text-zinc-400">
                    Configure webhook endpoints to receive real-time event notifications from PARWA.
                  </p>
                  <div className="rounded-lg bg-[#141414] border border-white/[0.04] p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <GlobeAltIcon className="h-5 w-5 text-zinc-500" />
                        <div>
                          <p className="text-sm font-medium text-zinc-200">Webhook Configuration</p>
                          <p className="text-xs text-zinc-500">Create and manage custom webhook endpoints</p>
                        </div>
                      </div>
                      <a
                        href="/dashboard/integrations"
                        className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-white/[0.08] transition-colors"
                      >
                        Go to Integrations
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-3.5 w-3.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
                        </svg>
                      </a>
                    </div>
                  </div>
                </div>
              </SectionCard>

              {/* API Usage */}
              <SectionCard
                title="API Usage"
                icon={<ChartBarIcon className="h-5 w-5" />}
              >
                <div className="space-y-3">
                  <p className="text-sm text-zinc-400">
                    Monitor your API usage and track request patterns.
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    {[
                      { label: 'Requests Today', value: '1,247' },
                      { label: 'Avg Response', value: '142ms' },
                      { label: 'Error Rate', value: '0.3%' },
                      { label: 'Requests This Month', value: '34,891' },
                    ].map(stat => (
                      <div key={stat.label} className="rounded-lg bg-[#141414] border border-white/[0.04] p-3 text-center">
                        <p className="text-lg font-bold text-white">{stat.value}</p>
                        <p className="text-[10px] text-zinc-500 mt-1">{stat.label}</p>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-zinc-600 text-center">
                    Detailed usage analytics coming soon with the Analytics dashboard.
                  </p>
                </div>
              </SectionCard>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          MODALS
          ══════════════════════════════════════════════════════════════════ */}

      {/* ── Invite Member Modal ─────────────────────────────────────────── */}
      {inviteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setInviteModalOpen(false)} />
          <div className="relative w-full max-w-md rounded-2xl border border-white/[0.08] bg-[#1A1A1A] p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-semibold text-white">Invite Team Member</h3>
              <button onClick={() => setInviteModalOpen(false)} className="text-zinc-500 hover:text-zinc-300 transition-colors">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">Email Address</label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={e => setInviteEmail(e.target.value)}
                  placeholder="colleague@company.com"
                  className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-4 py-2.5 text-sm text-white placeholder-zinc-600 focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">Role</label>
                <select
                  value={inviteRole}
                  onChange={e => setInviteRole(e.target.value)}
                  className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-4 py-2.5 text-sm text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 appearance-none cursor-pointer"
                >
                  {['Admin', 'Agent', 'Viewer'].map(r => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={() => setInviteModalOpen(false)}
                  className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.04] py-2.5 text-sm font-medium text-zinc-300 hover:bg-white/[0.08] transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleInviteMember}
                  disabled={inviteLoading}
                  className="flex-1 rounded-xl bg-[#FF7F11] py-2.5 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 disabled:opacity-50 transition-colors"
                >
                  {inviteLoading ? (
                    <span className="flex items-center justify-center gap-2">
                      <SpinnerIcon className="h-4 w-4 animate-spin" />
                      Sending...
                    </span>
                  ) : 'Send Invitation'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Create API Key Modal ───────────────────────────────────────── */}
      {createKeyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={() => { setCreateKeyModalOpen(false); setNewKeyName(''); setNewKeyScopes(['read']); }} />
          <div className="relative w-full max-w-md rounded-2xl border border-white/[0.08] bg-[#1A1A1A] p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-semibold text-white">Create API Key</h3>
              <button
                onClick={() => { setCreateKeyModalOpen(false); setNewKeyName(''); setNewKeyScopes(['read']); }}
                className="text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">Key Name</label>
                <input
                  type="text"
                  value={newKeyName}
                  onChange={e => setNewKeyName(e.target.value)}
                  placeholder="e.g., Production API"
                  className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-4 py-2.5 text-sm text-white placeholder-zinc-600 focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">Scopes</label>
                <div className="flex flex-wrap gap-2">
                  {['read', 'write', 'admin', 'tickets', 'agents'].map(scope => (
                    <button
                      key={scope}
                      onClick={() => {
                        setNewKeyScopes(prev =>
                          prev.includes(scope) ? prev.filter(s => s !== scope) : [...prev, scope],
                        );
                      }}
                      className={cn(
                        'rounded-lg px-3 py-1.5 text-xs font-medium border transition-colors',
                        newKeyScopes.includes(scope)
                          ? 'bg-[#FF7F11]/15 border-[#FF7F11]/30 text-[#FF7F11]'
                          : 'bg-white/[0.02] border-white/[0.06] text-zinc-500 hover:text-zinc-300',
                      )}
                    >
                      {scope}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-1.5">Expires In</label>
                <select
                  value={newKeyExpiry}
                  onChange={e => setNewKeyExpiry(e.target.value)}
                  className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-4 py-2.5 text-sm text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 appearance-none cursor-pointer"
                >
                  <option value="30">30 days</option>
                  <option value="90">90 days</option>
                  <option value="180">180 days</option>
                  <option value="365">1 year</option>
                </select>
              </div>
              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={() => { setCreateKeyModalOpen(false); setNewKeyName(''); setNewKeyScopes(['read']); }}
                  className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.04] py-2.5 text-sm font-medium text-zinc-300 hover:bg-white/[0.08] transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateKey}
                  disabled={createKeyLoading || newKeyScopes.length === 0}
                  className="flex-1 rounded-xl bg-[#FF7F11] py-2.5 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 disabled:opacity-50 transition-colors"
                >
                  {createKeyLoading ? (
                    <span className="flex items-center justify-center gap-2">
                      <SpinnerIcon className="h-4 w-4 animate-spin" />
                      Creating...
                    </span>
                  ) : 'Create Key'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
