'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Bell, CheckCircle2, AlertTriangle, AlertCircle, Info,
  Eye, Loader2, Filter,
} from 'lucide-react';
import { getNotifications, markNotificationRead, type Notification } from '@/lib/api';
import { toast } from 'sonner';

const severityConfig = {
  success: { icon: CheckCircle2, color: 'text-[#0A3D2E]', bg: 'bg-[#0A3D2E]/10', badge: 'bg-[#0A3D2E]/10 text-[#0A3D2E]' },
  warning: { icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-100', badge: 'bg-amber-100 text-amber-800' },
  error: { icon: AlertCircle, color: 'text-red-600', bg: 'bg-red-100', badge: 'bg-red-100 text-red-800' },
  info: { icon: Info, color: 'text-sky-600', bg: 'bg-sky-100', badge: 'bg-sky-100 text-sky-800' },
};

export default function Notifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'unread'>('all');
  const [markingId, setMarkingId] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const data = await getNotifications().catch(() => []);
      setNotifications(data);
      setLoading(false);
    }
    load();
  }, []);

  const handleMarkRead = async (id: string) => {
    setMarkingId(id);
    try {
      await markNotificationRead(id);
      setNotifications(notifications.map(n => n.id === id ? { ...n, read: true } : n));
      toast.success('Notification marked as read');
    } catch {
      setNotifications(notifications.map(n => n.id === id ? { ...n, read: true } : n));
    }
    setMarkingId(null);
  };

  const handleMarkAllRead = async () => {
    const unread = notifications.filter(n => !n.read);
    for (const n of unread) {
      await markNotificationRead(n.id).catch(() => {});
    }
    setNotifications(notifications.map(n => ({ ...n, read: true })));
    toast.success('All notifications marked as read');
  };

  const filtered = filter === 'unread' ? notifications.filter(n => !n.read) : notifications;
  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Notifications</h2>
          <p className="text-muted-foreground">Stay informed about your PARWA instance.</p>
        </div>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <>
              <Badge className="bg-[#0A3D2E]/10 text-[#0A3D2E]">{unreadCount} unread</Badge>
              <Button
                size="sm"
                variant="outline"
                onClick={handleMarkAllRead}
                className="border-[#0A3D2E]/30 hover:bg-[#0A3D2E]/5"
              >
                <Eye className="h-3.5 w-3.5 mr-1" />
                Mark all read
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-muted-foreground" />
        <Button
          size="sm"
          variant={filter === 'all' ? 'default' : 'outline'}
          onClick={() => setFilter('all')}
          className={filter === 'all' ? 'bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]' : ''}
        >
          All ({notifications.length})
        </Button>
        <Button
          size="sm"
          variant={filter === 'unread' ? 'default' : 'outline'}
          onClick={() => setFilter('unread')}
          className={filter === 'unread' ? 'bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]' : ''}
        >
          Unread ({unreadCount})
        </Button>
      </div>

      {/* Notification List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map(i => <Skeleton key={i} className="h-20 w-full" />)}
        </div>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Bell className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="font-medium">
              {filter === 'unread' ? 'No unread notifications' : 'No notifications yet'}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              {filter === 'unread' ? 'You\'re all caught up!' : 'Notifications will appear here when there\'s activity.'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3 max-h-[calc(100vh-300px)] overflow-y-auto">
          {filtered.map((n) => {
            const config = severityConfig[n.type];
            const Icon = config.icon;
            return (
              <Card
                key={n.id}
                className={`transition-all ${!n.read ? 'border-l-4 border-l-text-[#0A3D2E] bg-[#0A3D2E]/5/30' : ''}`}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <div className={`p-2 rounded-lg ${config.bg} shrink-0 mt-0.5`}>
                      <Icon className={`h-4 w-4 ${config.color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className={`text-sm ${!n.read ? 'font-semibold' : 'font-medium'}`}>{n.title}</h4>
                        <Badge className={`${config.badge} text-xs`}>{n.type}</Badge>
                        {!n.read && <div className="w-2 h-2 rounded-full bg-[#0A3D2E]/50 shrink-0" />}
                      </div>
                      <p className="text-sm text-muted-foreground">{n.message}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {new Date(n.created_at).toLocaleString()}
                      </p>
                    </div>
                    {!n.read && (
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={markingId === n.id}
                        onClick={() => handleMarkRead(n.id)}
                        className="shrink-0 text-[#0A3D2E] hover:text-[#0A3D2E] hover:bg-[#0A3D2E]/5"
                      >
                        {markingId === n.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Eye className="h-3.5 w-3.5" />}
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
