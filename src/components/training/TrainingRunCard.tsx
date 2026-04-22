'use client';

import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  CheckCircle,
  XCircle,
  Clock,
  Play,
  Pause,
  AlertTriangle,
  RefreshCw,
  Zap,
  Loader2,
  DollarSign,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TrainingRun } from '@/lib/training-api';

interface TrainingRunCardProps {
  run: TrainingRun;
  compact?: boolean;
  onUpdate?: () => void;
}

const statusConfig: Record<
  string,
  { label: string; color: string; icon: React.ReactNode; bg: string }
> = {
  queued: {
    label: 'Queued',
    color: 'text-gray-400',
    bg: 'bg-gray-500/15',
    icon: <Clock className="w-4 h-4" />,
  },
  preparing: {
    label: 'Preparing',
    color: 'text-blue-400',
    bg: 'bg-blue-500/15',
    icon: <RefreshCw className="w-4 h-4 animate-spin" />,
  },
  running: {
    label: 'Training',
    color: 'text-orange-400',
    bg: 'bg-orange-500/15',
    icon: <Play className="w-4 h-4" />,
  },
  validating: {
    label: 'Validating',
    color: 'text-purple-400',
    bg: 'bg-purple-500/15',
    icon: <RefreshCw className="w-4 h-4 animate-spin" />,
  },
  completed: {
    label: 'Completed',
    color: 'text-green-400',
    bg: 'bg-green-500/15',
    icon: <CheckCircle className="w-4 h-4" />,
  },
  failed: {
    label: 'Failed',
    color: 'text-red-400',
    bg: 'bg-red-500/15',
    icon: <XCircle className="w-4 h-4" />,
  },
  cancelled: {
    label: 'Cancelled',
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/15',
    icon: <Pause className="w-4 h-4" />,
  },
};

const triggerLabels: Record<string, string> = {
  manual: 'Manual',
  auto_threshold: 'Auto (Threshold)',
  scheduled: 'Scheduled',
  cold_start: 'Cold Start',
};

export function TrainingRunCard({ run, compact, onUpdate }: TrainingRunCardProps) {
  const status = statusConfig[run.status] || statusConfig.queued;
  const isActive = ['queued', 'preparing', 'running', 'validating'].includes(run.status);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (compact) {
    return (
      <Card className="bg-[#1A1A1A] border-white/[0.08] hover:border-white/[0.15] transition-colors">
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center', status.bg)}>
                {status.icon}
              </div>
              <div>
                <p className="text-sm font-medium text-white">
                  {run.name || `Run #${run.id.slice(0, 8)}`}
                </p>
                <p className="text-xs text-gray-400">
                  {triggerLabels[run.trigger] || run.trigger} • {formatDate(run.created_at)}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className={cn('text-sm font-medium', status.color)}>{status.label}</p>
                {run.cost_usd > 0 && (
                  <p className="text-xs text-gray-500">${run.cost_usd.toFixed(2)}</p>
                )}
              </div>
              {run.progress_pct > 0 && run.progress_pct < 100 && (
                <div className="w-16">
                  <Progress value={run.progress_pct} className="h-1.5" />
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-[#1A1A1A] border-white/[0.08] hover:border-white/[0.15] transition-colors">
      <CardContent className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', status.bg, status.color)}>
              {status.icon}
            </div>
            <div>
              <h3 className="text-lg font-medium text-white">
                {run.name || `Training Run #${run.id.slice(0, 8)}`}
              </h3>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="outline" className="text-xs bg-white/5 border-white/10">
                  {triggerLabels[run.trigger] || run.trigger}
                </Badge>
                {run.gpu_type && (
                  <Badge variant="outline" className="text-xs bg-white/5 border-white/10">
                    <Zap className="w-3 h-3 mr-1" />
                    {run.gpu_type}
                  </Badge>
                )}
                {run.provider && (
                  <Badge variant="outline" className="text-xs bg-white/5 border-white/10">
                    {run.provider}
                  </Badge>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge className={cn(status.bg, status.color, 'border-0')}>
              {status.label}
            </Badge>
          </div>
        </div>

        {/* Progress */}
        {isActive && (
          <div className="mb-4">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-gray-400">
                Epoch {run.current_epoch} of {run.total_epochs}
              </span>
              <span className="text-white font-medium">{run.progress_pct.toFixed(1)}%</span>
            </div>
            <Progress value={run.progress_pct} className="h-2" />
          </div>
        )}

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div className="bg-white/[0.03] rounded-lg p-3">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Epochs</p>
            <p className="text-lg font-medium text-white mt-1">
              {run.current_epoch}/{run.total_epochs}
            </p>
          </div>
          <div className="bg-white/[0.03] rounded-lg p-3">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Batch Size</p>
            <p className="text-lg font-medium text-white mt-1">{run.batch_size}</p>
          </div>
          <div className="bg-white/[0.03] rounded-lg p-3">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Learning Rate</p>
            <p className="text-lg font-medium text-white mt-1">
              {run.learning_rate?.toExponential(2) || '-'}
            </p>
          </div>
          <div className="bg-white/[0.03] rounded-lg p-3">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Cost</p>
            <p className="text-lg font-medium text-white mt-1 flex items-center">
              <DollarSign className="w-4 h-4 text-gray-500" />
              {run.cost_usd.toFixed(2)}
            </p>
          </div>
        </div>

        {/* Training Metrics */}
        {run.metrics && Object.keys(run.metrics).length > 0 && (
          <div className="bg-white/[0.03] rounded-lg p-3 mb-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Training Metrics</p>
            <div className="grid grid-cols-3 gap-3">
              {run.metrics.accuracy !== undefined && (
                <div>
                  <p className="text-xs text-gray-400">Accuracy</p>
                  <p className="text-sm font-medium text-green-400">
                    {((run.metrics.accuracy as number) * 100).toFixed(1)}%
                  </p>
                </div>
              )}
              {run.metrics.loss !== undefined && (
                <div>
                  <p className="text-xs text-gray-400">Loss</p>
                  <p className="text-sm font-medium text-blue-400">
                    {(run.metrics.loss as number).toFixed(4)}
                  </p>
                </div>
              )}
              {run.metrics.val_accuracy !== undefined && (
                <div>
                  <p className="text-xs text-gray-400">Val Accuracy</p>
                  <p className="text-sm font-medium text-purple-400">
                    {((run.metrics.val_accuracy as number) * 100).toFixed(1)}%
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Error Message */}
        {run.status === 'failed' && run.error_message && (
          <div className="bg-red-500/10 border border-red-500/25 rounded-lg p-3 mb-4">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-400">Training Failed</p>
                <p className="text-xs text-red-300 mt-1">{run.error_message}</p>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between text-xs text-gray-500">
          <div className="flex items-center gap-4">
            <span>Started: {formatDate(run.started_at || run.created_at)}</span>
            {run.completed_at && <span>Completed: {formatDate(run.completed_at)}</span>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
