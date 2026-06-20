'use client';

import DashboardShell from '@/components/DashboardShell';
import ChatPanel from '@/components/ChatPanel';

export default function ChatPage() {
  return (
    <DashboardShell>
      <div className="max-w-4xl mx-auto">
        <ChatPanel />
      </div>
    </DashboardShell>
  );
}