/**
 * PARWA DashboardLayout
 *
 * Main layout shell for the dashboard.
 * Uses DashboardSidebar component with collapse/expand on desktop,
 * hamburger overlay on mobile.
 *
 * Day 4: Added SocketProvider, NotificationBell, RealtimeToast,
 * SystemHealthMonitor, ConnectionStatus.
 */

'use client';

import { useState, useEffect, Component } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import DashboardSidebar from './DashboardSidebar';
import NotificationBell from '@/components/notifications/NotificationBell';
import RealtimeToast from '@/components/notifications/RealtimeToast';
import UsageWarningModal from '@/components/notifications/UsageWarningModal';
import ConnectionStatus from '@/components/ConnectionStatus';
import { TrialBanner } from './TrialBanner';
import { SocketProvider } from '@/providers/SocketProvider';
import { useNotificationStore } from '@/lib/notification-store';
import { useApprovalStore } from '@/lib/approval-store';
import toast from 'react-hot-toast';

// ── Error Boundary for SocketProvider ────────────────────────────────

class SocketErrorBoundary extends Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    console.warn('[SocketErrorBoundary] Caught error:', error.message);
  }

  render() {
    if (this.state.hasError) {
      // Render children without the socket provider on error
      return this.props.children;
    }
    return this.props.children;
  }
}

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const router = useRouter();
  const { logout, isAuthenticated, isInitialized, isLoading } = useAuth();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  // Max-loading flag: if auth takes longer than 5 seconds, stop blocking
  // the dashboard. The user can still see the UI; if auth later resolves
  // to "not authenticated", the auth guard useEffect will redirect them.
  const [maxLoadExceeded, setMaxLoadExceeded] = useState(false);

  // Onboarding gate — DISABLED for testing
  // User can access dashboard without completing onboarding.
  const [onboardingCheckState, setOnboardingCheckState] = useState<
    'checking' | 'completed' | 'incomplete' | 'unknown'
  >('completed'); // Set to 'completed' to skip onboarding gate

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

  // ── Max loading timeout ────────────────────────────────────────────
  useEffect(() => {
    if (isInitialized && !isLoading) return;
    const timer = setTimeout(() => setMaxLoadExceeded(true), 5000);
    return () => clearTimeout(timer);
  }, [isInitialized, isLoading]);

  // ── Auth Guard ───────────────────────────────────────────────────────
  useEffect(() => {
    if (isInitialized && !isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isInitialized, isLoading, isAuthenticated, router]);

  // ── Onboarding Gate — DISABLED for testing ─────────────────────────
  // Users can access dashboard without completing onboarding wizard.
  // Original logic commented out - re-enable when ready for production.
  /*
  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;

    async function checkOnboarding() {
      try {
        const res = await fetch('/api/onboarding/state', {
          credentials: 'include',
          signal: AbortSignal.timeout(8000),
        });
        if (cancelled) return;

        if (!res.ok) {
          setOnboardingCheckState('unknown');
          return;
        }

        const data = await res.json().catch(() => null);
        if (cancelled || !data) {
          setOnboardingCheckState('unknown');
          return;
        }

        const finished =
          data.first_victory_completed === true ||
          (data.status === 'completed' && data.current_step >= 4);

        if (finished) {
          setOnboardingCheckState('completed');
        } else {
          setOnboardingCheckState('incomplete');
          setTimeout(() => {
            if (!cancelled) router.replace('/onboarding');
          }, 50);
        }
      } catch {
        if (!cancelled) setOnboardingCheckState('unknown');
      }
    }

    checkOnboarding();
    return () => { cancelled = true; };
  }, [isAuthenticated, router]);
  */

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      localStorage.removeItem('parwa_user');
      localStorage.removeItem('parwa_access_token');
      localStorage.removeItem('parwa_refresh_token');
    }
    toast.success('Logged out');
    router.push('/');
  };

  // Show loading state while auth is initializing — BUT only up to 5 seconds.
  // After 5 seconds, fall through and render the dashboard shell so the user
  // sees something instead of an infinite spinner.
  if ((!isInitialized || isLoading) && !maxLoadExceeded) {
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
  // (unless we hit the max-load timeout — then render anyway so the user
  // isn't stuck on a blank page; the auth guard will redirect if needed)
  if (!isAuthenticated && !maxLoadExceeded) {
    return null;
  }

  // Onboarding gate — show loading screen while checking onboarding state,
  // and prevent rendering the dashboard if the user hasn't finished
  // onboarding (they'll be redirected to /onboarding).
  // 'unknown' = backend was unreachable; let them through to avoid a hard
  // block during cold starts.
  if (onboardingCheckState === 'checking' || onboardingCheckState === 'incomplete') {
    return (
      <div className="min-h-screen bg-[#1A1A1A] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-zinc-500">
            {onboardingCheckState === 'incomplete'
              ? 'Redirecting to onboarding...'
              : 'Checking onboarding...'}
          </p>
        </div>
      </div>
    );
  }

  // Get approval pending count for the sidebar badge (safe access)
  let approvalPendingCount = 0;
  try {
    approvalPendingCount = useApprovalStore.getState()?.pendingCount ?? 0;
  } catch {
    // Store not ready — default to 0
  }

  // On mobile, we show a hamburger menu + overlay sidebar
  // On desktop, we show the persistent sidebar with collapse toggle
  return (
    <SocketErrorBoundary>
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
          {/* Trial Banner — only renders for trial users */}
          <TrialBanner />

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
          </div>
        </div>

        {/* Realtime Toast Overlay */}
        <RealtimeToast />

        {/* Usage Warning Modal (80% plan limit + renewal reminders) */}
        <UsageWarningModal />
        </div>
      </SocketProvider>
    </SocketErrorBoundary>
  );
}
