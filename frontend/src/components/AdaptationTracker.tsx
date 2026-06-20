'use client';

import { useQuery } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';

import { getCurrentTenantId } from '@/lib/auth-context';

const MILESTONES = [
  { day: 5, label: 'Baseline Set', icon: '◎' },
  { day: 10, label: 'Patterns Learned', icon: '◈' },
  { day: 15, label: 'Auto-Optimize', icon: '◉' },
  { day: 20, label: 'Drift Check Pass', icon: '◉' },
  { day: 25, label: 'Threshold Met', icon: '◉' },
  { day: 30, label: 'Graduation Ready', icon: '★' },
];

export default function AdaptationTracker() {
  const { data, isLoading } = useQuery<any>({
    queryKey: ['customer-health', getCurrentTenantId()],
    queryFn: () => jarvisApi.getCustomerHealth(getCurrentTenantId()),
    refetchInterval: 60000,
  });

  const currentDay = data?.day_in_cycle ?? data?.current_day ?? data?.progress_day ?? 0;
  const totalDays = data?.total_days ?? 30;
  const adaptationScore = data?.adaptation_score ?? data?.score ?? data?.health_score ?? 0;
  const coachMessage = data?.coach_message ?? data?.message ?? data?.recommendation ?? 'Keep monitoring progress. System is adapting well.';

  const progress = totalDays > 0 ? Math.min((currentDay / totalDays) * 100, 100) : 0;

  if (isLoading) {
    return (
      <div className="jarvis-card">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase mb-3">Adaptation Tracker</h3>
        <div className="space-y-3">
          <div className="skeleton h-3 w-full rounded" />
          <div className="skeleton h-16 rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className="jarvis-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase">Adaptation Tracker</h3>
        <span className="text-sm font-bold text-jarvis-cyan tabular-nums">
          Day {currentDay} / {totalDays}
        </span>
      </div>

      {/* Progress bar */}
      <div className="mb-4">
        <div className="progress-bar h-3">
          <div
            className="progress-bar-fill bg-gradient-to-r from-jarvis-cyan to-jarvis-green"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-[10px] text-jarvis-muted">0</span>
          <span className="text-[10px] text-jarvis-text">{Math.round(progress)}% complete</span>
          <span className="text-[10px] text-jarvis-muted">{totalDays}</span>
        </div>
      </div>

      {/* Milestones */}
      <div className="space-y-1.5 mb-4">
        {MILESTONES.map((ms) => {
          const achieved = currentDay >= ms.day;
          return (
            <div
              key={ms.day}
              className={`flex items-center gap-2 text-[11px] transition-colors ${
                achieved ? 'text-jarvis-green' : 'text-jarvis-muted'
              }`}
            >
              <span className={`text-sm ${achieved ? 'glow-green' : 'opacity-40'}`}>
                {achieved ? '✓' : ms.icon}
              </span>
              <span className="flex-1">{ms.label}</span>
              <span className="text-[9px] tabular-nums">Day {ms.day}</span>
            </div>
          );
        })}
      </div>

      {/* Coach Message */}
      <div className="bg-jarvis-bg/50 rounded-lg p-2.5 border border-jarvis-cyan/10">
        <div className="text-[9px] text-jarvis-cyan tracking-widest uppercase mb-1">Success Coach</div>
        <p className="text-[11px] text-jarvis-text/80 leading-relaxed">{coachMessage}</p>
      </div>

      {/* Adaptation Score */}
      {adaptationScore > 0 && (
        <div className="mt-3 flex items-center justify-between text-[11px]">
          <span className="text-jarvis-muted">Adaptation Score</span>
          <span className="text-jarvis-green font-bold tabular-nums">{Math.round(adaptationScore * 100)}%</span>
        </div>
      )}
    </div>
  );
}