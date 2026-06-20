'use client';

import { useQuery } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';
import { useState } from 'react';

import { getCurrentTenantId } from '@/lib/auth-context';

function gradeFromScore(score: number): { grade: string; color: string; bgColor: string } {
  if (score >= 90) return { grade: 'A', color: 'text-jarvis-green', bgColor: 'bg-jarvis-green' };
  if (score >= 80) return { grade: 'B', color: 'text-jarvis-cyan', bgColor: 'bg-jarvis-cyan' };
  if (score >= 70) return { grade: 'C', color: 'text-jarvis-yellow', bgColor: 'bg-jarvis-yellow' };
  if (score >= 60) return { grade: 'D', color: 'text-orange-400', bgColor: 'bg-orange-400' };
  return { grade: 'F', color: 'text-jarvis-red', bgColor: 'bg-jarvis-red' };
}

function scoreColor(score: number): string {
  if (score >= 90) return '#00ff88';
  if (score >= 80) return '#06b6d4';
  if (score >= 70) return '#f59e0b';
  if (score >= 60) return '#f97316';
  return '#ef4444';
}

export default function HealthCard() {
  const [showDetails, setShowDetails] = useState(false);

  const { data, isLoading } = useQuery<any>({
    queryKey: ['health-score', getCurrentTenantId()],
    queryFn: () => jarvisApi.getHealthScore(getCurrentTenantId()),
    refetchInterval: 30000,
  });

  const score = data?.health_score ?? data?.score ?? data?.overall_score ?? 0;
  const trend = data?.trend ?? data?.trend_days ?? [];
  const { grade, color, bgColor } = gradeFromScore(score);
  const sc = scoreColor(score);
  const circumference = 2 * Math.PI * 36;
  const offset = circumference - (score / 100) * circumference;

  if (isLoading) {
    return (
      <div className="jarvis-card">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase mb-3">System Health</h3>
        <div className="flex items-center justify-center">
          <div className="skeleton w-28 h-28 rounded-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="jarvis-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase">System Health</h3>
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="text-[10px] text-jarvis-cyan hover:text-jarvis-text transition-colors"
        >
          {showDetails ? 'HIDE' : 'DETAILS'}
        </button>
      </div>

      <div className="flex flex-col items-center">
        {/* Score Circle */}
        <div className="relative w-28 h-28 mb-3">
          <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
            <circle cx="40" cy="40" r="36" fill="none" stroke="#1f2937" strokeWidth="4" />
            <circle
              cx="40"
              cy="40"
              r="36"
              fill="none"
              stroke={sc}
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              className="transition-all duration-1000"
              style={{ filter: `drop-shadow(0 0 6px ${sc}40)` }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-2xl font-bold ${color}`}>{score}</span>
            <span className={`text-xs font-bold ${color}`}>{grade}</span>
          </div>
        </div>

        {/* 7-day Trend Sparkline */}
        {trend.length > 0 && (
          <div className="w-full mb-2">
            <div className="text-[10px] text-jarvis-muted mb-1">7-Day Trend</div>
            <div className="flex items-end gap-[2px] h-8">
              {trend.slice(-7).map((val: any, idx: number) => {
                const v = typeof val === 'object' ? (val.score ?? val.value ?? 0) : Number(val) || 0;
                const h = Math.max(4, (v / 100) * 32);
                const c = scoreColor(v);
                return (
                  <div key={idx} className="flex-1 flex flex-col items-center gap-0.5">
                    <div
                      className="w-full rounded-t transition-all duration-500"
                      style={{ height: `${h}px`, backgroundColor: c, opacity: 0.7 }}
                    />
                    <span className="text-[7px] text-jarvis-muted">{v}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Expanded Details */}
      {showDetails && (
        <div className="mt-3 pt-3 border-t border-jarvis-border/30 space-y-1.5 fade-in">
          {data?.drift_detected !== undefined && (
            <div className="flex justify-between text-[11px]">
              <span className="text-jarvis-muted">Drift Detected</span>
              <span className={data.drift_detected ? 'text-jarvis-red' : 'text-jarvis-green'}>
                {data.drift_detected ? 'YES' : 'NONE'}
              </span>
            </div>
          )}
          {data?.last_check && (
            <div className="flex justify-between text-[11px]">
              <span className="text-jarvis-muted">Last Check</span>
              <span className="text-jarvis-text">{new Date(data.last_check).toLocaleString()}</span>
            </div>
          )}
          {data?.components && Object.entries(data.components).map(([name, val]: [string, any]) => (
            <div key={name} className="flex justify-between text-[11px]">
              <span className="text-jarvis-muted capitalize">{name.replace(/_/g, ' ')}</span>
              <span className="text-jarvis-text tabular-nums">{typeof val === 'number' ? `${val}%` : val}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}