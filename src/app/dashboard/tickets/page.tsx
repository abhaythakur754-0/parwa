'use client';

import React from 'react';
import { TicketList } from '@/components/dashboard/tickets';

export default function TicketsPage() {
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="pb-6 border-b border-white/[0.06]">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white">Tickets</h1>
            <p className="text-sm text-zinc-500 mt-0.5">
              Manage and monitor all support tickets. View conversations, assign agents, and track resolution.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
              <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50 animate-pulse" />
              <span className="text-[11px] font-medium text-emerald-400">Live</span>
            </div>
          </div>
        </div>
      </div>

      {/* Ticket List */}
      <TicketList />
    </div>
  );
}
