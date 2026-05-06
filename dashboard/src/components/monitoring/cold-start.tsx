'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { fetchColdStartStatus, triggerWarmup } from '@/lib/api';
import type { ColdStartStatus } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/badge';
import { Flame, Play } from 'lucide-react';

const stateColors: Record<string, string> = {
  cold: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  warming: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  warm: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  hot: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

export function ColdStartStatusPanel() {
  const [tenants, setTenants] = useState<ColdStartStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchColdStartStatus().then(d => { setTenants(d); setLoading(false); });
  }, []);

  const handleWarmup = async (tenantId: string) => {
    await triggerWarmup(tenantId);
    setTenants(prev => prev.map(t =>
      t.tenantId === tenantId ? { ...t, warmupState: 'warming', warmupProgress: 10 } : t
    ));
  };

  if (loading) {
    return <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Flame className="h-4 w-4" /> Cold Start Status
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {tenants.map(tenant => (
            <div key={tenant.tenantId} className="flex items-center justify-between p-3 rounded-lg border border-border">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{tenant.tenantName}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${stateColors[tenant.warmupState]}`}>
                    {tenant.warmupState}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-24 bg-muted rounded-full h-1.5">
                    <div
                      className="h-1.5 rounded-full bg-emerald-500 transition-all"
                      style={{ width: `${tenant.warmupProgress}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-muted-foreground">{tenant.warmupProgress}%</span>
                </div>
                <p className="text-[10px] text-muted-foreground">
                  Last accessed: {new Date(tenant.lastAccessed).toLocaleString()}
                </p>
              </div>
              {tenant.warmupState === 'cold' && (
                <Button size="sm" variant="outline" onClick={() => handleWarmup(tenant.tenantId)}>
                  <Play className="h-3 w-3 mr-1" /> Warmup
                </Button>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
