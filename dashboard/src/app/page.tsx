'use client';

import { useAppStore } from '@/lib/store';
import { AuthPage } from '@/components/auth/auth-page';
import { AppSidebar } from '@/components/layout/app-sidebar';
import { AppHeader } from '@/components/layout/app-header';
import { DashboardPage } from '@/components/dashboard/dashboard-page';
import { VariantsPage } from '@/components/variants/variants-page';
import { MonitoringPage } from '@/components/monitoring/monitoring-page';
import { TicketsPage } from '@/components/tickets/tickets-page';
import { ChannelsPage } from '@/components/channels/channels-page';
import { BillingPage } from '@/components/billing/billing-page';
import { KnowledgeBasePage } from '@/components/knowledge-base/knowledge-base-page';
import { ChatInterface } from '@/components/jarvis/chat-interface';
import { SettingsPage } from '@/components/settings/settings-page';
import { motion, AnimatePresence } from 'framer-motion';
import type { PageId } from '@/lib/types';

function PageRenderer({ page }: { page: PageId }) {
  switch (page) {
    case 'dashboard': return <DashboardPage />;
    case 'variants': return <VariantsPage />;
    case 'monitoring': return <MonitoringPage />;
    case 'tickets': return <TicketsPage />;
    case 'channels': return <ChannelsPage />;
    case 'billing': return <BillingPage />;
    case 'knowledge': return <KnowledgeBasePage />;
    case 'jarvis': return <ChatInterface />;
    case 'settings': return <SettingsPage />;
    default: return <DashboardPage />;
  }
}

export default function Home() {
  const { currentPage, isAuthenticated, sidebarOpen } = useAppStore();

  if (!isAuthenticated || currentPage === 'auth') {
    return <AuthPage />;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <div className="hidden md:flex">
        <AppSidebar />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <AppHeader />
        <main className="flex-1 overflow-y-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentPage}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="p-4 md:p-6 lg:p-8"
            >
              <PageRenderer page={currentPage} />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="fixed inset-0 bg-black/50" onClick={() => useAppStore.getState().setSidebarOpen(false)} />
          <div className="fixed left-0 top-0 bottom-0 w-64 z-50">
            <AppSidebar />
          </div>
        </div>
      )}
    </div>
  );
}
