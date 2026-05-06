'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { fetchPerformanceMetrics } from '@/lib/api';
import type { PerformanceMetrics } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

export function PerformanceMetricsPanel() {
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPerformanceMetrics().then(d => { setMetrics(d); setLoading(false); });
  }, []);

  if (loading || !metrics) {
    return <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>;
  }

  const latencyData = metrics.latencyByVariant.map(v => ({
    variant: v.variant,
    avg: v.avg,
    p95: v.p95,
    p99: v.p99,
  }));

  const techniqueData = metrics.techniqueUsage.slice(0, 8).map(t => ({
    technique: t.technique,
    count: t.count,
  }));

  return (
    <div className="space-y-6">
      {/* Latency by Variant */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Latency by Variant (seconds)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={latencyData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="variant" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  formatter={(v: number) => [`${v}s`]}
                />
                <Bar dataKey="avg" name="Avg" fill="#10b981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="p95" name="P95" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                <Bar dataKey="p99" name="P99" fill="#ef4444" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Technique Usage */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Technique Usage</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={techniqueData} layout="vertical" margin={{ top: 5, right: 10, left: 80, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis dataKey="technique" type="category" tick={{ fontSize: 10 }} width={75} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="count" name="Usage Count" fill="#10b981" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Cost Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Cost Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {metrics.costByVariant.map(v => (
              <div key={v.variant} className="p-4 rounded-lg border border-border text-center">
                <p className="text-xs text-muted-foreground mb-1">{v.variant}</p>
                <p className="text-xl font-bold">${v.totalCost.toFixed(2)}</p>
                <p className="text-[10px] text-muted-foreground">{v.queryCount.toLocaleString()} queries @ ${v.costPerQuery}/q</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
