'use client';

import React, { useState, useEffect } from 'react';
import DashboardSidebar from '@/components/dashboard/DashboardSidebar';
import DashboardHeaderBar from '@/components/dashboard/DashboardHeaderBar';
import { SocketProvider } from '@/contexts/SocketContext';

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('parwa_sidebar_collapsed') === 'true';
    }
    return false;
  });

  useEffect(() => {
    localStorage.setItem('parwa_sidebar_collapsed', String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  return (
    <SocketProvider>
      <div className="jarvis-page-body min-h-screen flex">
        {/* Sidebar */}
        <DashboardSidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
        />

        {/* Main Content Area */}
        <div
          className="flex-1 flex flex-col transition-all duration-300"
          style={{ marginLeft: sidebarCollapsed ? '68px' : '260px' }}
        >
          {/* Global Header Bar (Day 1: H1) */}
          <DashboardHeaderBar />

          {/* Page Content */}
          <main className="flex-1 overflow-auto">
            {children}
          </main>
        </div>
      </div>
    </SocketProvider>
  );
}
