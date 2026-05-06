'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { fetchTickets } from '@/lib/api';
import type { Ticket, TicketStatus, VariantType, ChannelType } from '@/lib/types';
import { useAppStore } from '@/lib/store';
import { Skeleton } from '@/components/ui/skeleton';
import { Search, Filter, ChevronLeft, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

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

export function TicketList() {
  const { ticketFilters, setTicketFilter, resetTicketFilters, selectedTicketId, setSelectedTicketId } = useAppStore();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchTickets(ticketFilters).then(d => {
      if (!cancelled) { setTickets(d); setLoading(false); }
    });
    return () => { cancelled = true; };
  }, [ticketFilters]);

  return (
    <div className="space-y-4">
      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search tickets..."
            value={ticketFilters.search}
            onChange={e => setTicketFilter('search', e.target.value)}
            className="pl-10"
          />
        </div>
        <Button variant="outline" onClick={() => setShowFilters(!showFilters)}>
          <Filter className="h-4 w-4 mr-2" /> Filters
        </Button>
      </div>

      {/* Filters */}
      <AnimatePresence>
        {showFilters && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <Card>
              <CardContent className="p-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <Select value={ticketFilters.status} onValueChange={v => setTicketFilter('status', v)}>
                    <SelectTrigger><SelectValue placeholder="Status" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Status</SelectItem>
                      <SelectItem value="open">Open</SelectItem>
                      <SelectItem value="in_progress">In Progress</SelectItem>
                      <SelectItem value="resolved">Resolved</SelectItem>
                      <SelectItem value="closed">Closed</SelectItem>
                      <SelectItem value="escalated">Escalated</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={ticketFilters.variant} onValueChange={v => setTicketFilter('variant', v)}>
                    <SelectTrigger><SelectValue placeholder="Variant" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Variants</SelectItem>
                      <SelectItem value="mini_parwa">Starter</SelectItem>
                      <SelectItem value="parwa">Growth</SelectItem>
                      <SelectItem value="parwa_high">High</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={ticketFilters.channel} onValueChange={v => setTicketFilter('channel', v)}>
                    <SelectTrigger><SelectValue placeholder="Channel" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Channels</SelectItem>
                      <SelectItem value="chat">Chat</SelectItem>
                      <SelectItem value="email">Email</SelectItem>
                      <SelectItem value="sms">SMS</SelectItem>
                      <SelectItem value="voice">Voice</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={ticketFilters.priority} onValueChange={v => setTicketFilter('priority', v)}>
                    <SelectTrigger><SelectValue placeholder="Priority" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Priority</SelectItem>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="urgent">Urgent</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button variant="ghost" size="sm" className="mt-3" onClick={resetTicketFilters}>
                  Reset Filters
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Ticket Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6"><Skeleton className="h-64 w-full" /></div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/30">
                    <th className="text-left font-medium text-muted-foreground p-4">ID</th>
                    <th className="text-left font-medium text-muted-foreground p-4">Subject</th>
                    <th className="text-left font-medium text-muted-foreground p-4">Customer</th>
                    <th className="text-left font-medium text-muted-foreground p-4">Status</th>
                    <th className="text-left font-medium text-muted-foreground p-4">Priority</th>
                    <th className="text-left font-medium text-muted-foreground p-4">Variant</th>
                    <th className="text-left font-medium text-muted-foreground p-4">Channel</th>
                    <th className="text-right font-medium text-muted-foreground p-4">Quality</th>
                    <th className="text-left font-medium text-muted-foreground p-4">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {tickets.map(ticket => (
                    <tr
                      key={ticket.id}
                      className={`border-b border-border/50 hover:bg-muted/50 cursor-pointer transition-colors ${
                        selectedTicketId === ticket.id ? 'bg-emerald-50/50 dark:bg-emerald-950/20' : ''
                      }`}
                      onClick={() => setSelectedTicketId(selectedTicketId === ticket.id ? null : ticket.id)}
                    >
                      <td className="p-4 font-mono text-xs">{ticket.id}</td>
                      <td className="p-4 max-w-[200px] truncate">{ticket.subject}</td>
                      <td className="p-4 text-xs">{ticket.customerName}</td>
                      <td className="p-4">
                        <Badge variant="outline" className={`text-[10px] px-1.5 py-0 border-0 ${statusColors[ticket.status]}`}>
                          {ticket.status.replace('_', ' ')}
                        </Badge>
                      </td>
                      <td className="p-4">
                        <Badge variant="outline" className={`text-[10px] px-1.5 py-0 border-0 ${priorityColors[ticket.priority]}`}>
                          {ticket.priority}
                        </Badge>
                      </td>
                      <td className="p-4 font-mono text-xs">{ticket.variant}</td>
                      <td className="p-4 capitalize text-xs">{ticket.channel}</td>
                      <td className="p-4 text-right font-mono text-xs">{ticket.qualityScore}%</td>
                      <td className="p-4 text-xs text-muted-foreground">
                        {new Date(ticket.createdAt).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
