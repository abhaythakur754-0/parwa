'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle, CheckCircle, Zap, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ThresholdStatus, MistakeStats } from '@/lib/training-api';

interface MistakeThresholdProgressProps {
  agentId: string;
  status?: ThresholdStatus;
  stats?: MistakeStats;
  compact?: boolean;
}

export function MistakeThresholdProgress({
  agentId,
  status,
  stats,
  compact,
}: MistakeThresholdProgressProps) {
  const current = status?.current_count || 0;
  const threshold = status?.threshold || 50; // LOCKED at 50 per BC-007
  const percentage = status?.percentage || (current / threshold) * 100;
  const remaining = status?.remaining || Math.max(0, threshold - current);
  const triggered = status?.triggered || current >= threshold;

  // Determine status color
  const getStatusColor = () => {
    if (triggered) return 'text-orange-400';
    if (percentage >= 80) return 'text-yellow-400';
    if (percentage >= 50) return 'text-blue-400';
    return 'text-green-400';
  };

  const getProgressColor = () => {
    if (triggered) return 'bg-orange-500';
    if (percentage >= 80) return 'bg-yellow-500';
    if (percentage >= 50) return 'bg-blue-500';
    return 'bg-green-500';
  };

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <div className="flex-1">
          <Progress
            value={Math.min(percentage, 100)}
            className="h-2"
          />
        </div>
        <span className={cn('text-sm font-medium', getStatusColor())}>
          {current}/{threshold}
        </span>
      </div>
    );
  }

  return (
    <Card className="bg-[#1A1A1A] border-white/[0.08]">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base text-white flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-400" />
            Mistake Threshold
          </CardTitle>
          {triggered ? (
            <Badge className="bg-orange-500/15 text-orange-400 border-orange-500/25">
              Training Triggered
            </Badge>
          ) : (
            <Badge className="bg-green-500/15 text-green-400 border-green-500/25">
              Below Threshold
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Progress Bar */}
        <div>
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-gray-400">Mistakes toward training</span>
            <span className={cn('font-medium', getStatusColor())}>
              {current} / {threshold}
            </span>
          </div>
          <div className="relative h-3 bg-white/5 rounded-full overflow-hidden">
            <div
              className={cn(
                'absolute inset-y-0 left-0 rounded-full transition-all duration-500',
                getProgressColor()
              )}
              style={{ width: `${Math.min(percentage, 100)}%` }}
            />
            {/* Threshold marker */}
            <div
              className="absolute inset-y-0 w-0.5 bg-white/30"
              style={{ left: '100%' }}
            />
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white/[0.03] rounded-lg p-3">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-orange-400" />
              <span className="text-xs text-gray-500 uppercase">Remaining</span>
            </div>
            <p className={cn('text-xl font-bold mt-1', getStatusColor())}>
              {remaining}
            </p>
            <p className="text-xs text-gray-500">until training</p>
          </div>

          <div className="bg-white/[0.03] rounded-lg p-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-blue-400" />
              <span className="text-xs text-gray-500 uppercase">Progress</span>
            </div>
            <p className="text-xl font-bold text-white mt-1">
              {percentage.toFixed(0)}%
            </p>
            <p className="text-xs text-gray-500">to threshold</p>
          </div>
        </div>

        {/* Mistake Breakdown */}
        {stats && (
          <div className="bg-white/[0.03] rounded-lg p-3">
            <p className="text-xs text-gray-500 uppercase mb-2">By Type</p>
            <div className="space-y-1">
              {Object.entries(stats.by_type).slice(0, 4).map(([type, count]) => (
                <div key={type} className="flex items-center justify-between text-sm">
                  <span className="text-gray-400 capitalize">{type.replace(/_/g, ' ')}</span>
                  <span className="text-white font-medium">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Info Box */}
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3">
          <p className="text-xs text-blue-300">
            <strong>BC-007:</strong> The threshold is locked at 50 mistakes and cannot be changed.
            When reached, automatic training is triggered for continuous improvement.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
