'use client';

import { TicketList } from './ticket-list';
import { TicketDetail } from './ticket-detail';
import { TicketAnalytics } from './ticket-analytics';
import { useAppStore } from '@/lib/store';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { List, BarChart3, FileText } from 'lucide-react';

export function TicketsPage() {
  const { selectedTicketId } = useAppStore();

  return (
    <div className="space-y-6">
      <Tabs defaultValue="list">
        <TabsList>
          <TabsTrigger value="list"><List className="h-3 w-3 mr-1" /> All Tickets</TabsTrigger>
          <TabsTrigger value="analytics"><BarChart3 className="h-3 w-3 mr-1" /> Analytics</TabsTrigger>
        </TabsList>
        <TabsContent value="list" className="mt-6">
          <div className={`grid gap-6 ${selectedTicketId ? 'grid-cols-1 lg:grid-cols-3' : 'grid-cols-1'}`}>
            <div className={selectedTicketId ? 'lg:col-span-2' : ''}>
              <TicketList />
            </div>
            {selectedTicketId && (
              <div>
                <TicketDetail />
              </div>
            )}
          </div>
        </TabsContent>
        <TabsContent value="analytics" className="mt-6">
          <TicketAnalytics />
        </TabsContent>
      </Tabs>
    </div>
  );
}
