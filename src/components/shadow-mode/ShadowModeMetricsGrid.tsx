/**
 * ShadowModeMetricsGrid — Key metrics for shadow mode performance
 *
 * Shows win rate, quality delta, latency delta, token savings,
 * human agreement rate, and auto-graduation progress.
 */

'use client';

import React from 'react';
import { MetricCard } from '@/components/jarvis-cc/MetricCard';
import type { ShadowModeStatistics } from '@/types/shadow-mode';

// ── Props ───────────────────────────────────────────────────────────

export interface ShadowModeMetricsGridProps {
  statistics: ShadowModeStatistics | null;
  className?: string;
}

// ── Component ───────────────────────────────────────────────────────

export function ShadowModeMetricsGrid({ statistics, className }: ShadowModeMetricsGridProps) {
  if (!statistics) {
    return (
      <div className={className}>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <MetricCard key={i} label="--" value="--" />
          ))}
        </div>
      </div>
    );
  }

  const winRateVariant = statistics.shadow_win_rate >= 0.7 ? 'success' : statistics.shadow_win_rate >= 0.5 ? 'warning' : 'danger';
  const qualityDeltaVariant = statistics.avg_quality_delta > 0 ? 'success' : statistics.avg_quality_delta < 0 ? 'danger' : 'default';
  const latencyVariant = statistics.avg_latency_delta_ms <= 0 ? 'success' : statistics.avg_latency_delta_ms <= 100 ? 'warning' : 'danger';

  return (
    <div className={className}>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <MetricCard
          label="Win Rate"
          value={`${Math.round(statistics.shadow_win_rate * 100)}%`}
          subtitle={`${statistics.shadow_wins}/${statistics.total_comparisons} wins`}
          variant={winRateVariant}
          trend={statistics.shadow_win_rate >= 0.5 ? 'up' : 'down'}
        />
        <MetricCard
          label="Quality Delta"
          value={`${statistics.avg_quality_delta > 0 ? '+' : ''}${(statistics.avg_quality_delta * 100).toFixed(1)}%`}
          subtitle="shadow vs live"
          variant={qualityDeltaVariant}
          trend={statistics.avg_quality_delta > 0 ? 'up' : statistics.avg_quality_delta < 0 ? 'down' : 'flat'}
        />
        <MetricCard
          label="Latency Delta"
          value={`${statistics.avg_latency_delta_ms > 0 ? '+' : ''}${Math.round(statistics.avg_latency_delta_ms)}ms`}
          subtitle="shadow vs live"
          variant={latencyVariant}
          trend={statistics.avg_latency_delta_ms <= 0 ? 'up' : 'down'}
        />
        <MetricCard
          label="Token Savings"
          value={`${statistics.avg_token_delta < 0 ? '' : '+'}${Math.round(statistics.avg_token_delta)}`}
          subtitle="per comparison"
          variant={statistics.avg_token_delta <= 0 ? 'success' : 'warning'}
        />
        <MetricCard
          label="Human Agreement"
          value={statistics.human_agreement_rate > 0 ? `${Math.round(statistics.human_agreement_rate * 100)}%` : '--'}
          subtitle={`${statistics.human_reviews_total} reviews`}
          variant={statistics.human_agreement_rate >= 0.7 ? 'success' : statistics.human_agreement_rate >= 0.5 ? 'warning' : 'default'}
        />
        <MetricCard
          label="Last 24h"
          value={statistics.comparisons_last_24h}
          subtitle={`last 7d: ${statistics.comparisons_last_7d}`}
          variant="info"
        />
      </div>
    </div>
  );
}
