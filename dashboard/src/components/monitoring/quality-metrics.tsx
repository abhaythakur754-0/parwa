'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { fetchQualityMetrics } from '@/lib/api';
import type { QualityMetrics } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { Shield, Eye, Brain, Lock } from 'lucide-react';

export function QualityMetricsPanel() {
  const [metrics, setMetrics] = useState<QualityMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchQualityMetrics().then(d => { setMetrics(d); setLoading(false); });
  }, []);

  if (loading || !metrics) {
    return <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>;
  }

  const items = [
    { label: 'Avg Confidence Score', value: metrics.avgConfidenceScore, display: `${(metrics.avgConfidenceScore * 100).toFixed(1)}%`, icon: Brain, color: 'emerald' },
    { label: 'Guardrail Pass Rate', value: metrics.guardrailPassRate / 100, display: `${metrics.guardrailPassRate}%`, icon: Shield, color: 'emerald' },
    { label: 'Hallucination Rate', value: metrics.hallucinationRate / 100, display: `${metrics.hallucinationRate}%`, icon: Eye, color: 'amber' },
    { label: 'PII Detection Rate', value: metrics.piiDetectionRate / 100, display: `${metrics.piiDetectionRate}%`, icon: Lock, color: 'emerald' },
    { label: 'Sentiment Accuracy', value: metrics.sentimentAccuracy / 100, display: `${metrics.sentimentAccuracy}%`, icon: Brain, color: 'emerald' },
    { label: 'Intent Classification', value: metrics.intentClassificationAccuracy / 100, display: `${metrics.intentClassificationAccuracy}%`, icon: Brain, color: 'emerald' },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Quality Metrics</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {items.map(item => {
            const Icon = item.icon;
            return (
              <div key={item.label} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">{item.label}</span>
                  </div>
                  <span className="text-sm font-bold">{item.display}</span>
                </div>
                <Progress value={item.value * 100} className="h-1.5" />
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
