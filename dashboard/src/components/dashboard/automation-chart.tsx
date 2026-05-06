'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { fetchAutomationTrend } from '@/lib/api';
import type { AutomationTrendPoint } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';

export function AutomationChart() {
  const [data, setData] = useState<AutomationTrendPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAutomationTrend().then(d => { setData(d); setLoading(false); });
  }, []);

  if (loading) {
    return <Card><CardHeader><Skeleton className="h-6 w-48" /></CardHeader><CardContent><Skeleton className="h-64 w-full" /></CardContent></Card>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Automation Trend</CardTitle>
        <CardDescription>Automation rate over 30 days (target: 89.5%)</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                className="text-muted-foreground"
              />
              <YAxis
                domain={[82, 92]}
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => `${v}%`}
                className="text-muted-foreground"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                formatter={(value: number) => [`${value}%`, 'Automation Rate']}
              />
              <ReferenceLine y={89.5} stroke="#f59e0b" strokeDasharray="5 5" label={{ value: 'Target 89.5%', position: 'right', fontSize: 11, fill: '#f59e0b' }} />
              <Line
                type="monotone"
                dataKey="automationRate"
                stroke="#10b981"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#10b981' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
