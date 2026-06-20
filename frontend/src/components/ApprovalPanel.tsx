'use client';

import { useQuery } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';

import { getCurrentTenantId } from '@/lib/auth-context';

export default function ApprovalPanel() {
  const { data, isLoading } = useQuery<any>({
    queryKey: ['approvals-list', getCurrentTenantId()],
    queryFn: () => jarvisApi.getPendingApprovals(getCurrentTenantId()),
    refetchInterval: 15000,
  });

  const items: any[] = Array.isArray(data)
    ? data
    : data?.approvals || data?.pending || data?.items || [];

  if (isLoading) {
    return (
      <div className="jarvis-card">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase mb-3">Pending Approvals</h3>
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-14 rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="jarvis-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase">Pending Approvals</h3>
        <span className={`jarvis-badge ${items.length > 0 ? 'jarvis-badge-yellow' : 'jarvis-badge-green'}`}>
          {items.length}
        </span>
      </div>

      {items.length === 0 ? (
        <div className="text-center py-6 text-jarvis-muted text-sm">
          <span className="text-jarvis-green">✓</span>
          <p className="mt-1">No pending approvals</p>
        </div>
      ) : (
        <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
          {items.map((item: any, idx: number) => {
            const key = item.key || item.id || `item-${idx}`;
            const confidence = item.confidence ?? item.confidence_score ?? null;
            const priority = item.priority || item.risk_level || 'medium';

            return (
              <div
                key={key}
                className="bg-jarvis-bg/50 rounded-lg p-2.5 border border-jarvis-border/30 hover:border-jarvis-yellow/20 transition-all"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-jarvis-text font-medium truncate">
                      {item.title || item.description || item.name || `Approval #${idx + 1}`}
                    </p>
                    {item.category && (
                      <span className="text-[9px] text-jarvis-cyan tracking-wider mt-0.5 block">
                        {String(item.category).toUpperCase()}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    {confidence !== null && (
                      <span className={`text-[11px] tabular-nums ${
                        confidence >= 80 ? 'text-jarvis-green' : confidence >= 60 ? 'text-jarvis-yellow' : 'text-jarvis-red'
                      }`}>
                        {Math.round(confidence)}%
                      </span>
                    )}
                    <span className={`jarvis-badge text-[9px] ${
                      priority === 'high' || priority === 'critical' ? 'jarvis-badge-red'
                      : priority === 'medium' ? 'jarvis-badge-yellow'
                      : 'jarvis-badge-green'
                    }`}>
                      {String(priority).toUpperCase()}
                    </span>
                  </div>
                </div>
                {item.requested_by && (
                  <div className="mt-1.5 text-[10px] text-jarvis-muted">
                    By: {item.requested_by}
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