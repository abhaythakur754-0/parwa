'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { fetchProviderHealth } from '@/lib/api';
import type { ProviderHealth } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import { Activity, Server } from 'lucide-react';

const statusColors: Record<string, string> = {
  healthy: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  degraded: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  down: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

const cbColors: Record<string, string> = {
  closed: 'text-emerald-600 dark:text-emerald-400',
  open: 'text-red-600 dark:text-red-400',
  half_open: 'text-amber-600 dark:text-amber-400',
};

export function RouterStatus() {
  const [providers, setProviders] = useState<ProviderHealth[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProviderHealth().then(d => { setProviders(d); setLoading(false); });
  }, []);

  if (loading) {
    return <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Server className="h-4 w-4" /> Smart Router Status
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {providers.map(provider => (
            <div key={provider.provider} className="p-4 rounded-lg border border-border">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Activity className={`h-3 w-3 ${
                    provider.status === 'healthy' ? 'text-emerald-500' :
                    provider.status === 'degraded' ? 'text-amber-500' : 'text-red-500'
                  }`} />
                  <span className="font-medium">{provider.provider}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className={`text-[10px] px-1.5 py-0 border-0 ${statusColors[provider.status]}`}>
                    {provider.status}
                  </Badge>
                  <span className="text-[10px] text-muted-foreground">
                    Circuit: <span className={cbColors[provider.circuitBreakerState]}>{provider.circuitBreakerState.replace('_', ' ')}</span>
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div>
                  <span className="text-muted-foreground">Latency</span>
                  <p className="font-mono font-medium">{provider.latency}ms</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Uptime</span>
                  <p className="font-mono font-medium">{provider.uptime}%</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Models</span>
                  <p className="font-medium">{provider.models.length} available</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {provider.models.map(model => (
                  <Badge key={model.name} variant="secondary" className="text-[10px]">
                    {model.name} {model.available ? '✓' : '✗'} ({model.latency}ms)
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
