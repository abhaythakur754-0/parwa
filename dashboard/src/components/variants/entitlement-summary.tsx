'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { fetchEntitlements } from '@/lib/api';
import type { Entitlement } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { ArrowUpRight } from 'lucide-react';

export function EntitlementSummary() {
  const [entitlements, setEntitlements] = useState<Entitlement[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEntitlements().then(d => { setEntitlements(d); setLoading(false); });
  }, []);

  if (loading) {
    return <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>;
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">Entitlement Summary</CardTitle>
            <CardDescription>Current plan: Growth</CardDescription>
          </div>
          <Button variant="outline" size="sm" className="text-emerald-600 border-emerald-200 dark:border-emerald-800">
            <ArrowUpRight className="h-3 w-3 mr-1" /> Upgrade
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left font-medium text-muted-foreground pb-3 pr-4">Feature</th>
                <th className="text-center font-medium text-muted-foreground pb-3 px-3">
                  <span className="text-emerald-600 dark:text-emerald-400">Starter</span>
                </th>
                <th className="text-center font-medium text-muted-foreground pb-3 px-3 bg-emerald-50/50 dark:bg-emerald-950/10">
                  <span className="text-amber-600 dark:text-amber-400 font-semibold">Growth ✓</span>
                </th>
                <th className="text-center font-medium text-muted-foreground pb-3 px-3">
                  <span className="text-red-600 dark:text-red-400">High</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {entitlements.map(ent => (
                <tr key={ent.id} className="border-b border-border/30 hover:bg-muted/30 transition-colors">
                  <td className="py-2.5 pr-4">{ent.name}</td>
                  <td className="py-2.5 text-center px-3 text-xs text-muted-foreground">{ent.mini_parwa}</td>
                  <td className="py-2.5 text-center px-3 text-xs font-medium bg-emerald-50/50 dark:bg-emerald-950/10">
                    {ent.parwa}{ent.unit ? ` ${ent.unit}` : ''}
                  </td>
                  <td className="py-2.5 text-center px-3 text-xs text-muted-foreground">
                    {ent.parwa_high}{ent.unit ? ` ${ent.unit}` : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
