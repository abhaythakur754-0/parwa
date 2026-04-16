/**
 * PARWA DashboardHeaderBar — Day 1
 *
 * Global top bar for the dashboard with:
 * - Connection status indicator (Socket.io)
 * - System status badge (healthy/degraded/down)
 * - Notification bell with unread count
 * - Emergency Pause toggle (kills AI auto-respond)
 * - Mode selector (Live / Simulation / Training)
 * - User menu with plan badge & logout
 *
 * Uses real API calls and Socket.io events (not mock data).
 */

'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useSocket } from '@/lib/socket';
import { get, post } from '@/lib/api';
import toast from 'react-hot-toast';

// ── Types ──────────────────────────────────────────────────────────────

interface PlanInfo {
  plan_name: string;
  current_period_end?: string;
}

interface SystemHealth {
  status: 'healthy' | 'degraded' | 'down';
  message?: string;
}

type AIOperatingMode = 'live' | 'simulation' | 'training';

// ── Component ──────────────────────────────────────────────────────────

export default function DashboardHeaderBar() {
  const { user, logout } = useAuth();
  const { isConnected, badgeCounts, notifications, systemStatus, markNotificationRead } = useSocket();

  const [planInfo, setPlanInfo] = useState<PlanInfo | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [currentMode, setCurrentMode] = useState<AIOperatingMode>('live');
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [isTogglingPause, setIsTogglingPause] = useState(false);

  const notifRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // ── Fetch plan info on mount ─────────────────────────────────────
  useEffect(() => {
    get<PlanInfo>('/api/billing/plan')
      .then(setPlanInfo)
      .catch(() => {
        // Plan endpoint may not exist yet — use localStorage fallback
        const stored = localStorage.getItem('parwa_plan');
        if (stored) {
          try { setPlanInfo(JSON.parse(stored)); } catch { /* ignore */ }
        }
      });
  }, []);

  // ── Persist & restore mode ───────────────────────────────────────
  useEffect(() => {
    const stored = localStorage.getItem('parwa_ai_mode') as AIOperatingMode | null;
    if (stored && ['live', 'simulation', 'training'].includes(stored)) {
      setCurrentMode(stored);
    }
  }, []);

  const handleModeChange = useCallback((mode: AIOperatingMode) => {
    setCurrentMode(mode);
    localStorage.setItem('parwa_ai_mode', mode);
    toast.success(`Mode switched to ${mode}`);
  }, []);

  // ── Emergency Pause Toggle ───────────────────────────────────────
  const handleEmergencyPause = useCallback(async () => {
    try {
      setIsTogglingPause(true);
      const newState = !isPaused;
      await post('/api/dashboard/emergency-pause', { enabled: newState });
      setIsPaused(newState);
      toast.success(newState ? 'AI auto-respond PAUSED' : 'AI auto-respond RESUMED');
    } catch {
      toast.error('Failed to toggle pause');
    } finally {
      setIsTogglingPause(false);
    }
  }, [isPaused]);

  // ── Close dropdowns on outside click ─────────────────────────────
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setShowNotifications(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // ── Connection status color ──────────────────────────────────────
  const connColor = isConnected
    ? 'bg-emerald-400 shadow-emerald-400/50'
    : 'bg-red-400 shadow-red-400/50';

  // ── System status badge ──────────────────────────────────────────
  const statusConfig = systemStatus || { status: 'healthy' as const };
  const statusColor = {
    healthy: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    degraded: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    down: 'bg-red-500/10 text-red-400 border-red-500/20',
  }[statusConfig.status];

  // ── Plan badge color ─────────────────────────────────────────────
  const planColor = {
    free: 'bg-zinc-500/10 text-zinc-400',
    starter: 'bg-blue-500/10 text-blue-400',
    growth: 'bg-violet-500/10 text-violet-400',
    pro: 'bg-orange-500/10 text-orange-400',
    enterprise: 'bg-amber-500/10 text-amber-400',
  }[planInfo?.plan_name?.toLowerCase() || 'free'] || 'bg-zinc-500/10 text-zinc-400';

  return (
    <header className="sticky top-0 z-50 h-14 bg-[#111111]/95 backdrop-blur-xl border-b border-white/[0.06] flex items-center justify-between px-4 lg:px-6">
      {/* Left: Connection + System Status */}
      <div className="flex items-center gap-3">
        {/* Connection indicator */}
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full shadow-sm ${connColor}`} />
          <span className="text-xs text-zinc-500 hidden sm:inline">
            {isConnected ? 'Connected' : 'Offline'}
          </span>
        </div>

        {/* System status badge */}
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${statusColor}`}>
          {statusConfig.status.charAt(0).toUpperCase() + statusConfig.status.slice(1)}
        </span>

        {/* Emergency Pause */}
        <button
          onClick={handleEmergencyPause}
          disabled={isTogglingPause}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
            isPaused
              ? 'bg-red-500/15 text-red-400 border border-red-500/25 hover:bg-red-500/25'
              : 'bg-white/[0.04] text-zinc-400 border border-white/[0.06] hover:bg-white/[0.08]'
          } disabled:opacity-50`}
          title={isPaused ? 'Resume AI auto-respond' : 'Emergency pause AI'}
        >
          {isPaused ? (
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          )}
          <span className="hidden sm:inline">{isPaused ? 'PAUSED' : 'Pause'}</span>
        </button>
      </div>

      {/* Right: Mode Selector + Notifications + User */}
      <div className="flex items-center gap-2">
        {/* Mode Selector */}
        <div className="flex items-center rounded-lg border border-white/[0.06] bg-white/[0.03] p-0.5">
          {(['live', 'simulation', 'training'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => handleModeChange(mode)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                currentMode === mode
                  ? mode === 'live'
                    ? 'bg-emerald-500/15 text-emerald-400'
                    : mode === 'simulation'
                      ? 'bg-blue-500/15 text-blue-400'
                      : 'bg-amber-500/15 text-amber-400'
                  : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              {mode.charAt(0).toUpperCase() + mode.slice(1)}
            </button>
          ))}
        </div>

        {/* Notifications Bell */}
        <div ref={notifRef} className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative w-9 h-9 rounded-lg flex items-center justify-center text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05] transition-all"
            title="Notifications"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
            </svg>
            {badgeCounts.notifications > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-4.5 h-4.5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center min-w-[18px] h-[18px]">
                {badgeCounts.notifications > 99 ? '99+' : badgeCounts.notifications}
              </span>
            )}
          </button>

          {/* Notification Dropdown */}
          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 bg-[#1A1A1A] border border-white/[0.08] rounded-xl shadow-2xl shadow-black/40 overflow-hidden">
              <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
                <span className="text-sm font-semibold text-white">Notifications</span>
                <button
                  onClick={() => markNotificationRead('all')}
                  className="text-xs text-zinc-500 hover:text-zinc-300"
                >
                  Mark all read
                </button>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="px-4 py-8 text-center text-sm text-zinc-500">
                    No notifications
                  </div>
                ) : (
                  notifications.slice(0, 10).map((notif) => (
                    <div
                      key={notif.id}
                      onClick={() => markNotificationRead(notif.id)}
                      className={`px-4 py-3 border-b border-white/[0.04] cursor-pointer hover:bg-white/[0.03] transition-colors ${
                        !notif.read ? 'bg-white/[0.02]' : ''
                      }`}
                    >
                      <p className="text-sm text-zinc-200">{notif.title}</p>
                      <p className="text-xs text-zinc-500 mt-0.5">{notif.message}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Menu */}
        <div ref={userMenuRef} className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 pl-3 pr-2 py-1.5 rounded-lg hover:bg-white/[0.05] transition-all"
          >
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center text-white text-xs font-bold">
              {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
            </div>
            <span className="text-sm text-zinc-300 hidden sm:inline max-w-[100px] truncate">
              {user?.full_name || 'User'}
            </span>
            <svg className="w-4 h-4 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
            </svg>
          </button>

          {showUserMenu && (
            <div className="absolute right-0 mt-2 w-56 bg-[#1A1A1A] border border-white/[0.08] rounded-xl shadow-2xl shadow-black/40 overflow-hidden">
              {/* Plan Badge */}
              <div className="px-4 py-3 border-b border-white/[0.06]">
                <p className="text-xs text-zinc-500">Current Plan</p>
                <span className={`inline-block mt-1 px-2 py-0.5 rounded-md text-xs font-semibold ${planColor}`}>
                  {planInfo?.plan_name || 'Free'}
                </span>
              </div>

              <div className="py-1">
                <button
                  onClick={() => {
                    setShowUserMenu(false);
                  }}
                  className="w-full text-left px-4 py-2 text-sm text-zinc-300 hover:bg-white/[0.05] transition-colors"
                >
                  Settings
                </button>
                <button
                  onClick={async () => {
                    setShowUserMenu(false);
                    try {
                      await logout();
                    } catch {
                      localStorage.removeItem('parwa_user');
                      localStorage.removeItem('parwa_access_token');
                      localStorage.removeItem('parwa_refresh_token');
                    }
                  }}
                  className="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                >
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
