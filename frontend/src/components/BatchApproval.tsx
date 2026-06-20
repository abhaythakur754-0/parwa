'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';
import { useState } from 'react';

import { getCurrentTenantId } from '@/lib/auth-context';

interface BatchItem {
  key: string;
  batch_key: string;
  description: string;
  confidence_min?: number;
  confidence_max?: number;
  risk_level?: string;
  ticket_count?: number;
  category?: string;
  priority?: string;
  [key: string]: any;
}

function riskColor(risk: string): string {
  switch (risk?.toLowerCase()) {
    case 'low':
      return 'text-jarvis-green';
    case 'medium':
      return 'text-jarvis-yellow';
    case 'high':
    case 'critical':
      return 'text-jarvis-red';
    default:
      return 'text-jarvis-muted';
  }
}

function riskBadge(risk: string): string {
  switch (risk?.toLowerCase()) {
    case 'low':
      return 'jarvis-badge-green';
    case 'medium':
      return 'jarvis-badge-yellow';
    case 'high':
    case 'critical':
      return 'jarvis-badge-red';
    default:
      return 'jarvis-badge';
  }
}

export default function BatchApproval() {
  const queryClient = useQueryClient();
  const [expandedBatch, setExpandedBatch] = useState<string | null>(null);

  const { data, isLoading } = useQuery<any>({
    queryKey: ['approvals', getCurrentTenantId()],
    queryFn: () => jarvisApi.getPendingApprovals(getCurrentTenantId()),
    refetchInterval: 15000,
  });

  const approveMutation = useMutation({
    mutationFn: (batchKey: string) => jarvisApi.approveBatch(getCurrentTenantId(), batchKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (batchKey: string) => jarvisApi.rejectBatch(getCurrentTenantId(), batchKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  const batches: BatchItem[] = Array.isArray(data) ? data : data?.batches || data?.pending || [];

  if (isLoading) {
    return (
      <div className="jarvis-card">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase mb-3">Batch Approvals</h3>
        <div className="space-y-2">
          {[1, 2].map((i) => (
            <div key={i} className="skeleton h-20 rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="jarvis-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase">Batch Approvals</h3>
        <span className="jarvis-badge jarvis-badge-yellow">{batches.length} pending</span>
      </div>

      {batches.length === 0 ? (
        <div className="text-center py-6 text-jarvis-muted text-sm">
          <span className="text-jarvis-green text-lg">✓</span>
          <p className="mt-1">All clear — no pending approvals</p>
        </div>
      ) : (
        <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
          {batches.map((batch: BatchItem, idx: number) => {
            const batchKey = batch.batch_key || batch.key || `batch-${idx}`;
            const isExpanded = expandedBatch === batchKey;
            const isProcessing = approveMutation.isPending || rejectMutation.isPending;

            return (
              <div
                key={batchKey}
                className="bg-jarvis-bg/50 rounded-lg border border-jarvis-border/50 hover:border-jarvis-yellow/20 transition-all"
              >
                <button
                  onClick={() => setExpandedBatch(isExpanded ? null : batchKey)}
                  className="w-full text-left p-3 flex items-start justify-between gap-2"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm text-jarvis-text font-medium truncate">
                        {batch.description || 'Unnamed Batch'}
                      </span>
                      {batch.risk_level && (
                        <span className={`jarvis-badge ${riskBadge(batch.risk_level)}`}>
                          RISK: {batch.risk_level.toUpperCase()}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1.5 text-[10px] text-jarvis-muted">
                      {batch.ticket_count !== undefined && (
                        <span>{batch.ticket_count} tickets</span>
                      )}
                      {batch.confidence_min !== undefined && batch.confidence_max !== undefined && (
                        <span>
                          Confidence: <span className="text-jarvis-text">{batch.confidence_min}%–{batch.confidence_max}%</span>
                        </span>
                      )}
                      {batch.category && (
                        <span className="text-jarvis-cyan">{batch.category.toUpperCase()}</span>
                      )}
                    </div>
                  </div>
                  <span className={`text-jarvis-muted transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
                    ▼
                  </span>
                </button>

                {isExpanded && (
                  <div className="px-3 pb-3 border-t border-jarvis-border/30 pt-2 flex items-center gap-2">
                    <button
                      onClick={() => approveMutation.mutate(batchKey)}
                      disabled={isProcessing}
                      className="jarvis-btn-primary text-xs flex-1 disabled:opacity-30"
                    >
                      ✓ Approve Batch
                    </button>
                    <button
                      onClick={() => rejectMutation.mutate(batchKey)}
                      disabled={isProcessing}
                      className="jarvis-btn-danger text-xs flex-1 disabled:opacity-30"
                    >
                      ✗ Reject Batch
                    </button>
                    <button className="jarvis-btn-secondary text-xs flex-1">
                      ◎ Review
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}