'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { fetchVariantInstances } from '@/lib/api';
import type { VariantInstance } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export function WorkloadChart() {
  const [instances, setInstances] = useState<VariantInstance[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchVariantInstances().then(d => { setInstances(d); setLoading(false); });
  }, []);

  if (loading) {
    return <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>;
  }

  const data = instances.map(inst => ({
    name: inst.name,
    current: inst.currentLoad,
    capacity: inst.capacity - inst.currentLoad,
    total: inst.capacity,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Workload Distribution</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ top: 5, right: 10, left: 80, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={75} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
              />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              <Bar dataKey="current" name="Current Load" fill="#10b981" stackId="a" radius={[0, 0, 0, 0]} />
              <Bar dataKey="capacity" name="Available" fill="#e5e7eb" stackId="a" radius={[0, 4, 4, 0]} className="dark:opacity-20" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
