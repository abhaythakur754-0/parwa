/**
 * PARWA DashboardLayout
 *
 * Main layout shell for the dashboard.
 * Uses DashboardSidebar component with collapse/expand on desktop,
 * hamburger overlay on mobile.
 *
 * Day 4: Added SocketProvider, NotificationBell, RealtimeToast,
 * ApprovalWatcher, SystemHealthMonitor, ConnectionStatus.
 */

'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useAppStore } from '@/lib/store';
import DashboardSidebar from './DashboardSidebar';
import NotificationBell from '@/components/notifications/NotificationBell';
import RealtimeToast from '@/components/notifications/RealtimeToast';
import ApprovalWatcher from '@/components/approvals/ApprovalWatcher';
import SystemHealthMonitor from '@/components/dashboard/SystemHealthMonitor';
import ConnectionStatus from '@/components/ConnectionStatus';
import { SocketProvider } from '@/providers/SocketProvider';
import { useNotificationStore } from '@/lib/notification-store';
import { useApprovalStore } from '@/lib/approval-store';
import toast from 'react-hot-toast';

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const navigate = useAppStore((s) => s.navigate);
  const setAuth = useAppStore((s) => s.setAuth);
  const { logout, isAuthenticated, isInitialized, isLoading } = useAuth();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // Fetch initial notifications and approvals
  const fetchNotifications = useNotificationStore((s) => s.fetchNotifications);
  const fetchApprovals = useApprovalStore((s) => s.fetchApprovals);

  useEffect(() => {
    if (isAuthenticated) {
      fetchNotifications();
      fetchApprovals();
    }
  }, [isAuthenticated, fetchNotifications, fetchApprovals]);

  // ── Mobile detection — must be before early returns ─────────────────
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 1024);
    checkMobile();
    window.addEventListener('resize', checkMobile, { passive: true });
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // ── Auth Guard ───────────────────────────────────────────────────────
  useEffect(() => {
    if (isInitialized && !isLoading && !isAuthenticated) {
      navigate('login');
    }
  }, [isInitialized, isLoading, isAuthenticated, navigate]);

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      localStorage.removeItem('parwa_user');
      localStorage.removeItem('parwa_access_token');
      localStorage.removeItem('parwa_refresh_token');
    }
    setAuth(false);
    toast.success('Logged out');
    navigate('landing');
  };

  // Show loading state while auth is initializing
  if (!isInitialized || isLoading) {
    return (
      <div className="min-h-screen bg-[#1A1A1A] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-zinc-500">Loading...</p>
        </div>
      </div>
    );
  }

  // Don't render dashboard content if not authenticated
  if (!isAuthenticated) {
    return null;
  }

  // Get approval pending count for the sidebar badge
  const approvalPendingCount = useApprovalStore.getState().pendingCount;

  // On mobile, we show a hamburger menu + overlay sidebar
  // On desktop, we show the persistent sidebar with collapse toggle
  return (
    <SocketProvider>
      <div className="min-h-screen bg-[#1A1A1A] flex">
        {/* Mobile overlay */}
        {isMobileOpen && (
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 lg:hidden"
            onClick={() => setIsMobileOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* Sidebar — desktop: sticky with collapse; mobile: fixed overlay */}
        {isMobile ? (
          <div
            className={`fixed lg:hidden z-50 transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] ${
              isMobileOpen ? 'translate-x-0' : '-translate-x-full'
            }`}
          >
            <DashboardSidebar collapsed={false} onToggle={() => setIsMobileOpen(false)} />
          </div>
        ) : (
          <DashboardSidebar
            collapsed={sidebarCollapsed}
            onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
          />
        )}

        {/* Main Content */}
        <div
          className="flex-1 flex flex-col min-w-0 transition-all duration-300"
          style={{ marginLeft: isMobile ? 0 : sidebarCollapsed ? '68px' : '260px' }}
        >
          {/* Top bar */}
          <header className="sticky top-0 z-30 h-14 bg-[#1A1A1A]/90 backdrop-blur-xl border-b border-white/[0.06] flex items-center px-4 lg:px-6 gap-3">
            {/* Mobile hamburger */}
            {isMobile && (
              <button
                onClick={() => setIsMobileOpen(true)}
                className="p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05] transition-colors"
                aria-label="Open menu"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                </svg>
              </button>
            )}

            {/* Mobile brand */}
            {isMobile && (
              <span className="text-sm font-semibold text-white">PARWA</span>
            )}

            {/* Spacer */}
            <div className="flex-1" />

            {/* Connection Status */}
            <ConnectionStatus />

            {/* Approval Badge */}
            {approvalPendingCount > 0 && (
              <button
                className="relative p-2 rounded-lg text-amber-400 hover:bg-amber-400/10 transition-colors"
                title={`${approvalPendingCount} pending approval(s)`}
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
                </svg>
                <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 rounded-full bg-amber-500 text-white text-[9px] font-bold flex items-center justify-center px-0.5">
                  {approvalPendingCount > 9 ? '9+' : approvalPendingCount}
                </span>
              </button>
            )}

            {/* Notification Bell */}
            <NotificationBell />
          </header>

          {/* Content + Right Sidebar */}
          <div className="flex-1 flex">
            {/* Main content */}
            <main className="flex-1 p-4 lg:p-6 xl:p-8 min-w-0">
              {children}
            </main>

            {/* Right sidebar — Approval Watcher + System Health (desktop only) */}
            {!isMobile && (
              <aside className="w-[320px] shrink-0 p-4 space-y-4 border-l border-white/[0.04] overflow-y-auto scrollbar-premium hidden xl:block">
                <ApprovalWatcher />
                <SystemHealthMonitor />
              </aside>
            )}
          </div>
        </div>

        {/* Realtime Toast Overlay */}
        <RealtimeToast />
      </div>
    </SocketProvider>
  );
}
