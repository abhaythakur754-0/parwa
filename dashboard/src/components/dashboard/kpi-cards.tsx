'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { fetchKPIs } from '@/lib/api';
import type { KPICard as KPICardType } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import {
  TicketCheck, Cpu, Award, Clock, Bot, Zap,
  TrendingUp, TrendingDown, Minus,
} from 'lucide-react';
import { motion } from 'framer-motion';

const iconMap: Record<string, React.ElementType> = {
  TicketCheck, Cpu, Award, Clock, Bot, Zap,
};

export function KPICards() {
  const [kpiCards, setKpiCards] = useState<KPICardType[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchKPIs().then(data => { setKpiCards(data); setLoading(false); });
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i}><CardContent className="p-6"><Skeleton className="h-24 w-full" /></CardContent></Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {kpiCards.map((kpi, index) => {
        const Icon = iconMap[kpi.icon] || TicketCheck;
        return (
          <motion.div
            key={kpi.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
          >
            <Card className="hover:shadow-md transition-shadow">
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-muted-foreground">{kpi.title}</p>
                    <p className="text-2xl font-bold">{kpi.value}</p>
                    <div className="flex items-center gap-1 text-xs">
                      {kpi.trend === 'up' && <TrendingUp className="h-3 w-3 text-emerald-600" />}
                      {kpi.trend === 'down' && <TrendingDown className="h-3 w-3 text-red-500" />}
                      {kpi.trend === 'neutral' && <Minus className="h-3 w-3 text-muted-foreground" />}
                      <span className={
                        kpi.trend === 'up' ? 'text-emerald-600' :
                        kpi.trend === 'down' ? 'text-red-500' :
                        'text-muted-foreground'
                      }>
                        {kpi.change > 0 ? '+' : ''}{kpi.change}%
                      </span>
                      <span className="text-muted-foreground">{kpi.changeLabel}</span>
                    </div>
                  </div>
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 dark:bg-emerald-950/30">
                    <Icon className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        );
      })}
    </div>
  );
}
