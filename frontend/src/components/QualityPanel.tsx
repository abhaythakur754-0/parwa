'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';

import { getCurrentTenantId } from '@/lib/auth-context';

function scoreBarColor(score: number): string {
  if (score >= 90) return 'bg-jarvis-green';
  if (score >= 75) return 'bg-jarvis-cyan';
  if (score >= 60) return 'bg-jarvis-yellow';
  return 'bg-jarvis-red';
}

export default function QualityPanel() {
  const queryClient = useQueryClient();

  const { data: scores, isLoading: scoresLoading } = useQuery<any>({
    queryKey: ['quality-scores', getCurrentTenantId()],
    queryFn: () => jarvisApi.getQualityScores(getCurrentTenantId(), 7),
    refetchInterval: 30000,
  });

  const { data: alerts } = useQuery<any>({
    queryKey: ['quality-alerts', getCurrentTenantId()],
    queryFn: () => jarvisApi.getQualityAlerts(getCurrentTenantId()),
    refetchInterval: 20000,
  });

  const driftMutation = useMutation({
    mutationFn: () => jarvisApi.runDriftCheck(getCurrentTenantId()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quality-scores'] });
      queryClient.invalidateQueries({ queryKey: ['health-score'] });
    },
  });

  const scoreItems: Array<{ name: string; score: number }> = Array.isArray(scores)
    ? scores
    : scores?.scores || scores?.metrics || [];

  const alertList: any[] = Array.isArray(alerts)
    ? alerts
    : alerts?.alerts || alerts?.items || [];

  return (
    <div className="jarvis-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase">Quality Monitor</h3>
        <button
          onClick={() => driftMutation.mutate()}
          disabled={driftMutation.isPending}
          className="jarvis-btn-secondary text-[10px] disabled:opacity-30"
        >
          {driftMutation.isPending ? 'CHECKING...' : 'RUN DRIFT CHECK'}
        </button>
      </div>

      {/* Scores */}
      {scoresLoading ? (
        <div className="space-y-2 mb-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-6 rounded" />
          ))}
        </div>
      ) : (
        <div className="space-y-2 mb-4">
          {scoreItems.length > 0 ? scoreItems.map((item: any, idx: number) => {
            const name = item.name || item.category || item.metric || `Score ${idx + 1}`;
            const score = item.score ?? item.value ?? 0;
            return (
              <div key={idx} className="flex items-center gap-3">
                <span className="text-[11px] text-jarvis-muted min-w-[7rem] truncate capitalize">
                  {name.replace(/_/g, ' ')}
                </span>
                <div className="flex-1 progress-bar">
                  <div
                    className={`progress-bar-fill ${scoreBarColor(score)}`}
                    style={{ width: `${Math.min(score, 100)}%` }}
                  />
                </div>
                <span className="text-[11px] text-jarvis-text tabular-nums min-w-[2.5rem] text-right">
                  {Math.round(score)}%
                </span>
              </div>
            );
          }) : (
            <p className="text-xs text-jarvis-muted">No score data available</p>
          )}
        </div>
      )}

      {/* Alerts */}
      {alertList.length > 0 && (
        <div className="border-t border-jarvis-border/30 pt-3">
          <div className="text-[10px] text-jarvis-yellow tracking-widest uppercase mb-2">
            ⚠ {alertList.length} Alert{alertList.length !== 1 ? 's' : ''}
          </div>
          <div className="space-y-1.5 max-h-32 overflow-y-auto">
            {alertList.map((alert: any, idx: number) => (
              <div
                key={idx}
                className={`text-[11px] px-2 py-1 rounded ${
                  alert.severity?.toLowerCase() === 'high'
                    ? 'bg-red-950/20 text-jarvis-red'
                    : alert.severity?.toLowerCase() === 'medium'
                    ? 'bg-yellow-950/20 text-jarvis-yellow'
                    : 'bg-jarvis-bg/50 text-jarvis-muted'
                }`}
              >
                {alert.message || alert.description || alert.title || 'Unknown alert'}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Drift result */}
      {driftMutation.isSuccess && (
        <div className="mt-3 pt-3 border-t border-jarvis-border/30 fade-in">
          <div className="text-[10px] text-jarvis-green">
            ✓ Drift check completed: {JSON.stringify(driftMutation.data)}
          </div>
        </div>
      )}
    </div>
  );
}