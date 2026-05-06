'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { fetchTokenBudget } from '@/lib/api';
import type { TokenBudget } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { AlertTriangle } from 'lucide-react';

function formatTokens(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(0)}K`;
  return n.toString();
}

export function CostBudget() {
  const [budget, setBudget] = useState<TokenBudget | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTokenBudget().then(d => { setBudget(d); setLoading(false); });
  }, []);

  if (loading || !budget) {
    return <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>;
  }

  const dailyPct = (budget.daily.used / budget.daily.limit) * 100;
  const monthlyPct = (budget.monthly.used / budget.monthly.limit) * 100;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Token Budget</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Daily Budget */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Daily Budget</span>
            <span className="text-sm text-muted-foreground">
              {formatTokens(budget.daily.used)} / {formatTokens(budget.daily.limit)}
            </span>
          </div>
          <Progress
            value={dailyPct}
            className="h-3"
          />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{dailyPct.toFixed(1)}% used</span>
            <span>{formatTokens(budget.daily.remaining)} remaining</span>
          </div>
        </div>

        {/* Monthly Budget */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Monthly Budget</span>
            <span className="text-sm text-muted-foreground">
              {formatTokens(budget.monthly.used)} / {formatTokens(budget.monthly.limit)}
            </span>
          </div>
          <Progress
            value={monthlyPct}
            className="h-3"
          />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{monthlyPct.toFixed(1)}% used</span>
            <span>{formatTokens(budget.monthly.remaining)} remaining</span>
          </div>
        </div>

        {/* Overage Info */}
        {budget.overageCount > 0 && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            <div className="text-xs">
              <span className="font-medium">{budget.overageCount} overage event(s)</span>
              {budget.lastOverageDate && (
                <span className="ml-1">— last on {new Date(budget.lastOverageDate).toLocaleDateString()}</span>
              )}
            </div>
          </div>
        )}

        {/* Cost Breakdown */}
        <div className="grid grid-cols-3 gap-3 pt-2">
          <div className="text-center p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/20">
            <p className="text-xs text-muted-foreground">Starter</p>
            <p className="text-sm font-bold text-emerald-600 dark:text-emerald-400">$0.003/q</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-amber-50 dark:bg-amber-950/20">
            <p className="text-xs text-muted-foreground">Growth</p>
            <p className="text-sm font-bold text-amber-600 dark:text-amber-400">$0.008/q</p>
          </div>
          <div className="text-center p-3 rounded-lg bg-red-50 dark:bg-red-950/20">
            <p className="text-xs text-muted-foreground">High</p>
            <p className="text-sm font-bold text-red-600 dark:text-red-400">$0.015/q</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
