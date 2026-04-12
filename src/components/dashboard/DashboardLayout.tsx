/**
 * PARWA DashboardLayout (Phase 4 — Day 1)
 *
 * Main layout shell for the dashboard.
 * Uses DashboardSidebar component with collapse/expand on desktop,
 * hamburger overlay on mobile.
 */

'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import DashboardSidebar from './DashboardSidebar';
import toast from 'react-hot-toast';

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const { logout } = useAuth();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 1024);
    checkMobile();
    window.addEventListener('resize', checkMobile, { passive: true });
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      localStorage.removeItem('parwa_user');
      localStorage.removeItem('parwa_access_token');
      localStorage.removeItem('parwa_refresh_token');
    }
    toast.success('Logged out');
  };

  // On mobile, we show a hamburger menu + overlay sidebar
  // On desktop, we show the persistent sidebar with collapse toggle
  return (
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
        {/* Top bar (mobile) */}
        <header className="sticky top-0 z-30 h-14 bg-[#1A1A1A]/90 backdrop-blur-xl border-b border-white/[0.06] flex items-center px-4 lg:hidden">
          <button
            onClick={() => setIsMobileOpen(true)}
            className="p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05] transition-colors"
            aria-label="Open menu"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
          <span className="ml-3 text-sm font-semibold text-white">PARWA</span>
        </header>

        {/* Content */}
        <main className="flex-1 p-4 lg:p-6 xl:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
