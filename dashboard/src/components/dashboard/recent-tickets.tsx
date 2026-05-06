'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { fetchTickets } from '@/lib/api';
import type { Ticket } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import { useAppStore } from '@/lib/store';

const statusColors: Record<string, string> = {
  open: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  in_progress: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  resolved: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400',
  closed: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-500',
  escalated: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

const priorityColors: Record<string, string> = {
  low: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  medium: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  high: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  urgent: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

export function RecentTickets() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const { setCurrentPage, setSelectedTicketId } = useAppStore();

  useEffect(() => {
    fetchTickets().then(d => { setTickets(d.slice(0, 10)); setLoading(false); });
  }, []);

  if (loading) {
    return (
      <Card>
        <CardHeader><Skeleton className="h-6 w-48" /></CardHeader>
        <CardContent><Skeleton className="h-64 w-full" /></CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">Recent Tickets</CardTitle>
        <button
          onClick={() => setCurrentPage('tickets')}
          className="text-xs text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 font-medium"
        >
          View All →
        </button>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left font-medium text-muted-foreground pb-3 pr-4">ID</th>
                <th className="text-left font-medium text-muted-foreground pb-3 pr-4">Subject</th>
                <th className="text-left font-medium text-muted-foreground pb-3 pr-4">Status</th>
                <th className="text-left font-medium text-muted-foreground pb-3 pr-4">Variant</th>
                <th className="text-left font-medium text-muted-foreground pb-3 pr-4">Channel</th>
                <th className="text-left font-medium text-muted-foreground pb-3 pr-4">Priority</th>
                <th className="text-right font-medium text-muted-foreground pb-3">Quality</th>
              </tr>
            </thead>
            <tbody>
              {tickets.map((ticket) => (
                <tr
                  key={ticket.id}
                  className="border-b border-border/50 hover:bg-muted/50 cursor-pointer transition-colors"
                  onClick={() => { setSelectedTicketId(ticket.id); setCurrentPage('tickets'); }}
                >
                  <td className="py-3 pr-4 font-mono text-xs">{ticket.id}</td>
                  <td className="py-3 pr-4 max-w-[200px] truncate">{ticket.subject}</td>
                  <td className="py-3 pr-4">
                    <Badge variant="outline" className={`text-[10px] px-1.5 py-0 border-0 ${statusColors[ticket.status]}`}>
                      {ticket.status.replace('_', ' ')}
                    </Badge>
                  </td>
                  <td className="py-3 pr-4 text-xs font-mono">{ticket.variant}</td>
                  <td className="py-3 pr-4 capitalize text-xs">{ticket.channel}</td>
                  <td className="py-3 pr-4">
                    <Badge variant="outline" className={`text-[10px] px-1.5 py-0 border-0 ${priorityColors[ticket.priority]}`}>
                      {ticket.priority}
                    </Badge>
                  </td>
                  <td className="py-3 text-right font-mono text-xs">{ticket.qualityScore}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
