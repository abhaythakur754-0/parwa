'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { fetchFailoverEvents } from '@/lib/api';
import type { FailoverEvent } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowRight, Clock } from 'lucide-react';

export function FailoverHistory() {
  const [events, setEvents] = useState<FailoverEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchFailoverEvents().then(d => { setEvents(d); setLoading(false); });
  }, []);

  if (loading) {
    return <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Failover History</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4 max-h-80 overflow-y-auto">
          {events.map(event => (
            <div key={event.id} className="relative pl-6 border-l-2 border-border">
              <div className="absolute -left-[7px] top-1 h-3 w-3 rounded-full bg-amber-500 border-2 border-background" />
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-mono">{event.fromProvider}/{event.fromModel}</span>
                  <ArrowRight className="h-3 w-3 text-muted-foreground" />
                  <span className="font-mono">{event.toProvider}/{event.toModel}</span>
                </div>
                <p className="text-xs text-muted-foreground">{event.reason}</p>
                <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {new Date(event.triggeredAt).toLocaleTimeString()}
                  </span>
                  <span>Duration: {Math.floor(event.duration / 60)}m {event.duration % 60}s</span>
                  {event.recoveredAt && (
                    <span className="text-emerald-600 dark:text-emerald-400">Recovered</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
