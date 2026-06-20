'use client';

import { useQuery } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';
import { useState } from 'react';

import { getCurrentTenantId } from '@/lib/auth-context';

export default function WeeklyWinsBanner() {
  const [expanded, setExpanded] = useState(false);

  const { data, isLoading } = useQuery<any>({
    queryKey: ['weekly-report', getCurrentTenantId()],
    queryFn: () => jarvisApi.getWeeklyReport(getCurrentTenantId(), 7),
    refetchInterval: 60000,
  });

  if (isLoading) {
    return (
      <div className="jarvis-card border-jarvis-green/10">
        <div className="skeleton h-8 rounded" />
      </div>
    );
  }

  const skillsLearned = data?.new_skills_learned ?? data?.skills_learned ?? data?.total_tasks ?? 0;
  const reviewDown = data?.review_time_reduction_pct ?? data?.time_saved_pct ?? 0;
  const autoResolved = data?.auto_resolved ?? data?.total_auto ?? 0;
  const totalTasks = data?.total_tasks ?? data?.tasks_processed ?? 0;
  const accuracy = data?.accuracy_score ?? data?.avg_accuracy ?? 0;

  return (
    <div className="jarvis-card border-jarvis-green/15 bg-green-950/5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left flex items-center justify-between"
      >
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-jarvis-green text-sm">🏆</span>
          <p className="text-sm text-jarvis-green font-medium">
            AI learned <span className="glow-green font-bold">{skillsLearned}</span> new skill{skillsLearned !== 1 ? 's' : ''} this week.
            {reviewDown > 0 && (
              <> Review time down <span className="glow-green font-bold">{Math.round(reviewDown)}%</span>.</>
            )}
          </p>
        </div>
        <span className={`text-jarvis-muted text-xs transition-transform ${expanded ? 'rotate-180' : ''}`}>
          ▼
        </span>
      </button>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-jarvis-border/30 grid grid-cols-2 sm:grid-cols-4 gap-3 fade-in">
          <div className="text-center">
            <div className="text-xl font-bold text-jarvis-green glow-green tabular-nums">{totalTasks}</div>
            <div className="text-[10px] text-jarvis-muted mt-0.5">Tasks Processed</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold text-jarvis-cyan tabular-nums">{autoResolved}</div>
            <div className="text-[10px] text-jarvis-muted mt-0.5">Auto-Resolved</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold text-jarvis-green tabular-nums">{Math.round(accuracy * 100)}%</div>
            <div className="text-[10px] text-jarvis-muted mt-0.5">Accuracy</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold text-jarvis-yellow tabular-nums">{skillsLearned}</div>
            <div className="text-[10px] text-jarvis-muted mt-0.5">New Skills</div>
          </div>

          {data?.top_categories && (
            <div className="col-span-2 sm:col-span-4 mt-1">
              <div className="text-[10px] text-jarvis-muted mb-1">Top Categories</div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(data.top_categories).slice(0, 5).map(([cat, count]: [string, any]) => (
                  <span key={cat} className="jarvis-badge jarvis-badge-cyan">
                    {cat}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}