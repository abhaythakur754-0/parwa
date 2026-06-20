'use client';

import { useQuery } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';

import { getCurrentTenantId } from '@/lib/auth-context';

export default function SLAPanel() {
  const { data, isLoading } = useQuery<any>({
    queryKey: ['sla-status', getCurrentTenantId()],
    queryFn: () => jarvisApi.getSLAStatus(getCurrentTenantId()),
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <div className="jarvis-card">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase mb-3">SLA Status</h3>
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-6 rounded" />
          ))}
        </div>
      </div>
    );
  }

  const slaItems: Array<{ name: string; current: number; target: number; unit?: string }> =
    Array.isArray(data) ? data : data?.sla_items || data?.metrics || [];

  const credits = data?.credits_available ?? data?.credits ?? data?.remaining_credits ?? null;
  const totalCredits = data?.total_credits ?? null;

  return (
    <div className="jarvis-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase">SLA Status</h3>
        {credits !== null && (
          <span className="jarvis-badge jarvis-badge-cyan">
            {credits} credit{credits !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {slaItems.length > 0 ? (
        <div className="space-y-3">
          {slaItems.map((item: any, idx: number) => {
            const name = item.name || item.sla_name || item.metric || `SLA ${idx + 1}`;
            const current = item.current ?? item.actual ?? item.value ?? 0;
            const target = item.target ?? item.goal ?? 100;
            const unit = item.unit || '%';
            const met = current >= target;
            const pct = target > 0 ? Math.min((current / target) * 100, 150) : 0;

            return (
              <div key={idx}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] text-jarvis-text capitalize">
                    {name.replace(/_/g, ' ')}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span className={`text-[11px] tabular-nums ${met ? 'text-jarvis-green' : 'text-jarvis-red'}`}>
                      {current}{unit}
                    </span>
                    <span className="text-[10px] text-jarvis-muted">/ {target}{unit}</span>
                    {met ? (
                      <span className="text-jarvis-green text-[10px]">✓</span>
                    ) : (
                      <span className="text-jarvis-red text-[10px]">✗</span>
                    )}
                  </div>
                </div>
                <div className="progress-bar">
                  <div
                    className={`progress-bar-fill ${met ? 'bg-jarvis-green' : 'bg-jarvis-red'}`}
                    style={{ width: `${Math.min(pct, 100)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-6 text-jarvis-muted text-sm">
          {data?.status ? (
            <div>
              <div className="text-lg mb-1">{data.status === 'healthy' ? '✓' : '⚠'}</div>
              <p className="text-jarvis-text">{String(data.status).toUpperCase()}</p>
            </div>
          ) : (
            'No SLA data available'
          )}
        </div>
      )}

      {/* Credits bar */}
      {credits !== null && totalCredits !== null && totalCredits > 0 && (
        <div className="mt-4 pt-3 border-t border-jarvis-border/30">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-jarvis-muted">Credits Used</span>
            <span className="text-[10px] text-jarvis-text tabular-nums">
              {totalCredits - credits} / {totalCredits}
            </span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-bar-fill bg-jarvis-cyan"
              style={{ width: `${((totalCredits - credits) / totalCredits) * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}