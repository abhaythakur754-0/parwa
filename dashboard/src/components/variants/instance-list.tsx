'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { fetchVariantInstances } from '@/lib/api';
import type { VariantInstance } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { MoreVertical } from 'lucide-react';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

const statusColors: Record<string, string> = {
  active: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  inactive: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  maintenance: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  error: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

const variantColors: Record<string, string> = {
  mini_parwa: 'text-emerald-600 dark:text-emerald-400',
  parwa: 'text-amber-600 dark:text-amber-400',
  parwa_high: 'text-red-600 dark:text-red-400',
};

export function InstanceList() {
  const [instances, setInstances] = useState<VariantInstance[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchVariantInstances().then(d => { setInstances(d); setLoading(false); });
  }, []);

  if (loading) {
    return <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>;
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">Variant Instances</CardTitle>
        <Badge variant="outline" className="border-0 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400">
          {instances.length} instances
        </Badge>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left font-medium text-muted-foreground pb-3 pr-4">Name</th>
                <th className="text-left font-medium text-muted-foreground pb-3 pr-4">Type</th>
                <th className="text-left font-medium text-muted-foreground pb-3 pr-4">Status</th>
                <th className="text-left font-medium text-muted-foreground pb-3 pr-4">Channel</th>
                <th className="text-left font-medium text-muted-foreground pb-3 pr-4">Load</th>
                <th className="text-right font-medium text-muted-foreground pb-3 pr-4">Accuracy</th>
                <th className="text-right font-medium text-muted-foreground pb-3 pr-4">Latency</th>
                <th className="text-right font-medium text-muted-foreground pb-3">Cost</th>
              </tr>
            </thead>
            <tbody>
              {instances.map((inst) => (
                <tr key={inst.id} className="border-b border-border/50 hover:bg-muted/50 transition-colors">
                  <td className="py-3 pr-4 font-medium">{inst.name}</td>
                  <td className="py-3 pr-4">
                    <span className={`font-mono text-xs ${variantColors[inst.type]}`}>{inst.type}</span>
                  </td>
                  <td className="py-3 pr-4">
                    <Badge variant="outline" className={`text-[10px] px-1.5 py-0 border-0 ${statusColors[inst.status]}`}>
                      {inst.status}
                    </Badge>
                  </td>
                  <td className="py-3 pr-4 capitalize text-xs">{inst.channel}</td>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2 min-w-[100px]">
                      <Progress value={(inst.currentLoad / inst.capacity) * 100} className="h-2" />
                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                        {inst.currentLoad}/{inst.capacity}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 pr-4 text-right font-mono text-xs">{inst.accuracyRate}%</td>
                  <td className="py-3 pr-4 text-right font-mono text-xs">{inst.avgLatency}s</td>
                  <td className="py-3 text-right font-mono text-xs">${inst.costPerQuery}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
