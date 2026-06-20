'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { useJarvisStatus } from '@/hooks/useJarvisStatus';

const navItems = [
  { href: '/', label: 'Dashboard', icon: '◉' },
  { href: '/chat', label: 'Chat', icon: '◈' },
  { href: '/onboarding', label: 'Setup', icon: '◎' },
];

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function StatusColor(status: string): string {
  switch (status?.toUpperCase()) {
    case 'OPTIMAL':
      return 'text-jarvis-green';
    case 'DEGRADED':
      return 'text-jarvis-yellow';
    case 'CRITICAL':
      return 'text-jarvis-red';
    default:
      return 'text-jarvis-muted';
  }
}

function ModeColor(mode: string): string {
  switch (mode?.toUpperCase()) {
    case 'SHADOW':
      return 'jarvis-badge-cyan';
    case 'SUPERVISED':
      return 'jarvis-badge-yellow';
    case 'GRADUATED':
      return 'jarvis-badge-green';
    default:
      return 'jarvis-badge';
  }
}

export default function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { tenantName, adminEmail, tier, logout } = useAuth();
  const { data: status, isLoading } = useJarvisStatus();

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-jarvis-card/95 backdrop-blur border-b border-jarvis-border px-4 py-2.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            className="lg:hidden text-jarvis-muted hover:text-jarvis-text transition-colors p-1"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Toggle sidebar"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="5" x2="17" y2="5" />
              <line x1="3" y1="10" x2="17" y2="10" />
              <line x1="3" y1="15" x2="17" y2="15" />
            </svg>
          </button>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-jarvis-green/10 border border-jarvis-green/30 flex items-center justify-center">
              <span className="text-jarvis-green font-bold text-sm glow-green">J</span>
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-wider text-jarvis-text">
                JARVIS<span className="text-jarvis-green">.</span>OS
              </h1>
              <p className="text-[10px] text-jarvis-muted tracking-widest uppercase">AI Operating System</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {isLoading ? (
            <div className="skeleton h-5 w-40 rounded" />
          ) : status ? (
            <>
              <span className={`jarvis-badge ${ModeColor(status.mode || '')}`}>
                {status.mode || 'SHADOW'}
              </span>
              <div className="hidden sm:flex items-center gap-1.5 text-xs">
                <span className={`font-semibold ${StatusColor(status.system_status)}`}>
                  {(status.system_status || 'OPTIMAL').toUpperCase()}
                </span>
                <span className="text-jarvis-muted">|</span>
                <span className="text-jarvis-muted">UP</span>
                <span className="text-jarvis-text font-mono tabular-nums">
                  {formatUptime(status.uptime_seconds || 0)}
                </span>
              </div>
            </>
          ) : (
            <span className="text-xs text-jarvis-red">OFFLINE</span>
          )}
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside
          className={`
            fixed lg:static inset-y-0 left-0 z-40 w-52 bg-jarvis-card border-r border-jarvis-border
            transform transition-transform duration-200 ease-in-out lg:transform-none
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          `}
        >
          <nav className="flex flex-col gap-1 p-3 mt-14 lg:mt-0" role="navigation" aria-label="Main navigation">
            {navItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={`
                    flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-200
                    ${isActive
                      ? 'bg-jarvis-green/10 text-jarvis-green border border-jarvis-green/20'
                      : 'text-jarvis-muted hover:text-jarvis-text hover:bg-jarvis-border/30 border border-transparent'
                    }
                  `}
                >
                  <span className="text-base">{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          {/* Sidebar Footer */}
          <div className="absolute bottom-0 left-0 right-0 p-3 border-t border-jarvis-border space-y-3">
            <div className="text-[10px] text-jarvis-muted space-y-1">
              <div className="flex justify-between">
                <span>VERSION</span>
                <span className="text-jarvis-text">PHASE-9</span>
              </div>
              <div className="flex justify-between">
                <span>TENANT</span>
                <span className="text-jarvis-cyan">{tenantName || 'default'}</span>
              </div>
              <div className="flex justify-between">
                <span>EMAIL</span>
                <span className="text-jarvis-muted truncate max-w-[100px]" title={adminEmail}>
                  {adminEmail || 'admin'}
                </span>
              </div>
              {tier && (
                <div className="flex justify-between">
                  <span>TIER</span>
                  <span className="jarvis-badge-green text-[9px]">{tier.toUpperCase()}</span>
                </div>
              )}
            </div>

            {/* Sign out */}
            <button
              onClick={() => {
                logout();
                window.location.href = '/';
              }}
              className="w-full jarvis-btn-ghost text-[10px] text-jarvis-red/70 hover:text-jarvis-red hover:border-jarvis-red/30"
            >
              SIGN OUT
            </button>
          </div>
        </aside>

        {/* Sidebar overlay for mobile */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/50 lg:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
