/**
 * PARWA DashboardHeaderBar — Day 1 (H1)
 *
 * Global header bar shown on every dashboard page.
 * Contains: Logo, Plan Badge, Notification Bell, System Status,
 * Emergency Pause Button, Mode Selector, User Menu.
 */

'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import { useSocket } from '@/contexts/SocketContext';
import { get, post, put } from '@/lib/api';
import toast from 'react-hot-toast';

// ── Types ──────────────────────────────────────────────────────────────

interface SystemHealthResponse {
  status: 'healthy' | 'degraded' | 'down';
  services: Record<string, { status: string; latency_ms?: number }>;
  message?: string;
}

// ── DashboardHeaderBar Component ───────────────────────────────────────

export default function DashboardHeaderBar() {
  const { user, logout } = useAuth();
  const {
    isConnected,
    isReconnecting,
    systemStatus,
    badgeCounts,
    unreadNotificationCount,
    isPaused,
    aiMode,
  } = useSocket();

  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [currentMode, setCurrentMode] = useState(aiMode);
  const [paused, setPaused] = useState(isPaused);
  const [pauseLoading, setPauseLoading] = useState(false);
  const [polledStatus, setPolledStatus] = useState<SystemHealthResponse | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // ── Sync with Socket.io events ───────────────────────────────────────
  useEffect(() => { setPaused(isPaused); }, [isPaused]);
  useEffect(() => { setCurrentMode(aiMode); }, [aiMode]);

  // ── Poll system status every 30s (fallback if Socket.io not connected) ──
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const data = await get<SystemHealthResponse>('/api/system/status');
        setPolledStatus(data);
      } catch {
        // Silent — Socket.io may handle this
      }
    };

    fetchStatus();
    pollIntervalRef.current = setInterval(fetchStatus, 30000);
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  // ── Fetch notifications on open ──────────────────────────────────────
  useEffect(() => {
    if (showNotifications && notifications.length === 0) {
      (async () => {
        try {
          const data = await get<any>('/api/notifications?page=1&page_size=5');
          setNotifications(data.notifications || data.items || data || []);
        } catch {
          // Notifications not available yet
        }
      })();
    }
  }, [showNotifications, notifications.length]);

  // ── Close menus on outside click ─────────────────────────────────────
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setShowNotifications(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ── Emergency Pause ──────────────────────────────────────────────────
  const handleEmergencyPause = useCallback(async () => {
    if (paused) {
      // Resume
      try {
        setPauseLoading(true);
        await post('/api/agents/emergency-resume');
        setPaused(false);
        toast.success('Operations resumed');
      } catch {
        toast.error('Failed to resume operations');
      } finally {
        setPauseLoading(false);
      }
    } else {
      // Confirm before pausing
      if (!window.confirm('This will pause all AI agents. Are you sure?')) return;
      try {
        setPauseLoading(true);
        await post('/api/agents/emergency-pause');
        setPaused(true);
        toast.success('All agents paused');
      } catch {
        toast.error('Failed to pause agents');
      } finally {
        setPauseLoading(false);
      }
    }
  }, [paused]);

  // ── Mode Selector ────────────────────────────────────────────────────
  const handleModeChange = useCallback(async (mode: 'shadow' | 'supervised' | 'graduated') => {
    try {
      await put('/api/system/mode', { mode });
      setCurrentMode(mode);
      toast.success(`Switched to ${mode} mode`);
    } catch {
      toast.error('Failed to change mode');
    }
  }, []);

  // ── Derived values ───────────────────────────────────────────────────
  const effectiveStatus = isConnected ? systemStatus.status : (polledStatus?.status || 'degraded');
  const statusDotColor = effectiveStatus === 'healthy'
    ? 'bg-emerald-400'
    : effectiveStatus === 'degraded'
    ? 'bg-amber-400'
    : 'bg-red-400';

  const modeConfig = {
    shadow: { label: 'Shadow', color: 'bg-orange-500/15 text-orange-400 border-orange-500/20' },
    supervised: { label: 'Supervised', color: 'bg-blue-500/15 text-blue-400 border-blue-500/20' },
    graduated: { label: 'Graduated', color: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' },
  };

  return (
    <header className="h-14 border-b border-white/[0.06] bg-[#111111] flex items-center justify-between px-4 lg:px-6 z-30">
      {/* Left: Logo */}
      <div className="flex items-center gap-3">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center">
          <span className="text-white font-bold text-xs">P</span>
        </div>
        <span className="text-white font-semibold text-sm hidden sm:block">PARWA</span>

        {/* Connection indicator */}
        <div className={cn(
          'flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium',
          isConnected
            ? 'bg-emerald-500/10 text-emerald-400'
            : isReconnecting
            ? 'bg-amber-500/10 text-amber-400'
            : 'bg-red-500/10 text-red-400'
        )}>
          <div className={cn(
            'w-1.5 h-1.5 rounded-full',
            isConnected ? 'bg-emerald-400' : isReconnecting ? 'bg-amber-400 animate-pulse' : 'bg-red-400'
          )} />
          {isConnected ? 'Live' : isReconnecting ? 'Reconnecting...' : 'Offline'}
        </div>
      </div>

      {/* Right: Controls */}
      <div className="flex items-center gap-2 lg:gap-3">
        {/* System Status Indicator */}
        <div className="hidden md:flex items-center gap-1.5 px-2 py-1 rounded-lg hover:bg-white/[0.04] transition-colors cursor-default" title={`System: ${effectiveStatus}`}>
          <div className={cn('w-2 h-2 rounded-full', statusDotColor, effectiveStatus !== 'healthy' && 'animate-pulse')} />
          <span className="text-[11px] text-zinc-500 capitalize">{effectiveStatus}</span>
        </div>

        {/* Mode Selector */}
        <div className="hidden sm:flex items-center gap-0.5 bg-white/[0.03] rounded-lg p-0.5">
          {(Object.keys(modeConfig) as Array<keyof typeof modeConfig>).map(mode => (
            <button
              key={mode}
              onClick={() => handleModeChange(mode)}
              className={cn(
                'px-2 py-1 text-[10px] font-medium rounded-md transition-all duration-150 border',
                currentMode === mode
                  ? modeConfig[mode].color
                  : 'text-zinc-500 hover:text-zinc-400 border-transparent'
              )}
            >
              {modeConfig[mode].label}
            </button>
          ))}
        </div>

        {/* Emergency Pause Button */}
        <button
          onClick={handleEmergencyPause}
          disabled={pauseLoading}
          className={cn(
            'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all duration-200 disabled:opacity-50',
            paused
              ? 'bg-red-500/15 text-red-400 border border-red-500/20 animate-pulse'
              : 'bg-white/[0.04] text-zinc-400 hover:text-red-400 hover:bg-red-500/10 border border-white/[0.06] hover:border-red-500/20'
          )}
          title={paused ? 'Click to resume all agents' : 'Emergency pause all agents'}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            {paused ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 7.5A2.25 2.25 0 0 1 7.5 5.25h9a2.25 2.25 0 0 1 2.25 2.25v9a2.25 2.25 0 0 1-2.25 2.25h-9a2.25 2.25 0 0 1-2.25-2.25v-9Z" />
            )}
          </svg>
          <span className="hidden lg:inline">{paused ? 'PAUSED' : 'Pause'}</span>
        </button>

        {/* Notification Bell */}
        <div ref={notifRef} className="relative">
          <button
            onClick={() => { setShowNotifications(!showNotifications); setShowUserMenu(false); }}
            className="w-9 h-9 rounded-lg flex items-center justify-center text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05] transition-colors relative"
            title="Notifications"
          >
            <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
            </svg>
            {(unreadNotificationCount || badgeCounts.notifications) > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-4.5 h-4.5 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center min-w-[16px] h-[16px]">
                {unreadNotificationCount || badgeCounts.notifications}
              </span>
            )}
          </button>

          {/* Notification Dropdown */}
          {showNotifications && (
            <div className="absolute right-0 top-12 w-80 bg-[#1A1A1A] border border-white/[0.08] rounded-xl shadow-2xl shadow-black/40 overflow-hidden z-50">
              <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
                <span className="text-sm font-semibold text-zinc-200">Notifications</span>
                <span className="text-[10px] text-zinc-500">{notifications.length} recent</span>
              </div>
              <div className="max-h-72 overflow-y-auto scrollbar-thin">
                {notifications.length === 0 ? (
                  <div className="py-8 text-center">
                    <p className="text-sm text-zinc-600">No notifications</p>
                  </div>
                ) : (
                  notifications.slice(0, 5).map((n: any, i: number) => (
                    <div key={i} className="px-4 py-3 border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors">
                      <p className="text-sm text-zinc-300">{n.title || n.message || 'Notification'}</p>
                      <p className="text-[11px] text-zinc-600 mt-0.5">
                        {n.created_at ? new Date(n.created_at).toLocaleString() : ''}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Menu */}
        <div ref={menuRef} className="relative">
          <button
            onClick={() => { setShowUserMenu(!showUserMenu); setShowNotifications(false); }}
            className="flex items-center gap-2 pl-2 pr-1.5 py-1 rounded-lg hover:bg-white/[0.05] transition-colors"
          >
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-emerald-500 to-teal-400 flex items-center justify-center text-white text-xs font-semibold">
              {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
            </div>
            <span className="text-sm text-zinc-300 hidden lg:block max-w-[120px] truncate">
              {user?.full_name || 'User'}
            </span>
            <svg className="w-3.5 h-3.5 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
            </svg>
          </button>

          {/* User Dropdown */}
          {showUserMenu && (
            <div className="absolute right-0 top-12 w-52 bg-[#1A1A1A] border border-white/[0.08] rounded-xl shadow-2xl shadow-black/40 overflow-hidden z-50">
              {/* User info */}
              <div className="px-4 py-3 border-b border-white/[0.06]">
                <p className="text-sm font-medium text-zinc-200">{user?.full_name || 'User'}</p>
                <p className="text-[11px] text-zinc-500 truncate">{user?.email || ''}</p>
              </div>

              {/* Menu items */}
              <div className="py-1">
                <a href="/dashboard/settings" className="flex items-center gap-2.5 px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] transition-colors">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17.982 18.725A7.488 7.488 0 0 0 12 15.75a7.488 7.488 0 0 0-5.982 2.975m11.963 0a9 9 0 1 0-11.963 0m11.963 0A8.966 8.966 0 0 1 12 21a8.966 8.966 0 0 1-5.982-2.275M15 9.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                  </svg>
                  Profile
                </a>
                <a href="/dashboard/settings" className="flex items-center gap-2.5 px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] transition-colors">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                  </svg>
                  Settings
                </a>
                <a href="/dashboard/billing" className="flex items-center gap-2.5 px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] transition-colors">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5A2.25 2.25 0 0 0 4.5 19.5Z" />
                  </svg>
                  Billing
                </a>
              </div>

              {/* Logout */}
              <div className="border-t border-white/[0.06] py-1">
                <button
                  onClick={() => { setShowUserMenu(false); logout(); }}
                  className="flex items-center gap-2.5 px-4 py-2 text-sm text-red-400 hover:bg-red-500/5 transition-colors w-full"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
                  </svg>
                  Log out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
