'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Brain,
  Activity,
  AlertTriangle,
  Target,
  Loader2,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Snowflake,
  CalendarClock,
  TrendingUp,
  TrendingDown,
  Minus,
  Clock,
  CheckCircle,
  XCircle,
  Play,
} from 'lucide-react';

import {
  getTrainingStats,
  listTrainingRuns,
  getAgentsDueForRetraining,
  getAgentsNeedingColdStart,
  getRetrainingSchedule,
  getTrainingEffectiveness,
  scheduleAllRetraining,
  initializeAllColdStart,
  type TrainingStats,
  type TrainingRun,
  type ColdStartStatus,
  type RetrainingSchedule,
} from '@/lib/training-api';

// ═══════════════════════════════════════════════════════════════════════════════
// API Helpers
// ═══════════════════════════════════════════════════════════════════════════════

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ═══════════════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════════════

interface EffectivenessData {
  runs: TrainingRun[];
  avg_accuracy: number;
  avg_loss: number;
  improvement_trend: 'improving' | 'stable' | 'declining';
}

interface RetrainingDueAgent {
  agent_id: string;
  agent_name: string;
  last_training: string;
  days_since_training: number;
  is_due_for_retraining: boolean;
  current_mistakes?: number;
  threshold?: number;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Status Config
// ═══════════════════════════════════════════════════════════════════════════════

const RUN_STATUS_CONFIG: Record<string, { label: string; dot: string; text: string }> = {
  running: { label: 'Running', dot: 'bg-blue-500', text: 'text-blue-400' },
  queued: { label: 'Queued', dot: 'bg-blue-400', text: 'text-blue-300' },
  preparing: { label: 'Preparing', dot: 'bg-blue-400', text: 'text-blue-300' },
  validating: { label: 'Validating', dot: 'bg-purple-400', text: 'text-purple-400' },
  completed: { label: 'Completed', dot: 'bg-emerald-500', text: 'text-emerald-400' },
  failed: { label: 'Failed', dot: 'bg-red-500', text: 'text-red-400' },
  cancelled: { label: 'Cancelled', dot: 'bg-zinc-500', text: 'text-zinc-400' },
};

const COLD_STATUS_CONFIG: Record<string, { label: string; dot: string; text: string }> = {
  cold_start_needed: { label: 'Needed', dot: 'bg-amber-500', text: 'text-amber-400' },
  initializing: { label: 'Initializing', dot: 'bg-blue-400', text: 'text-blue-400' },
  initialized: { label: 'Ready', dot: 'bg-emerald-500', text: 'text-emerald-400' },
  training: { label: 'Training', dot: 'bg-orange-400', text: 'text-orange-400' },
  ready: { label: 'Ready', dot: 'bg-emerald-500', text: 'text-emerald-400' },
};

const TRIGGER_LABELS: Record<string, string> = {
  manual: 'Manual',
  auto_threshold: 'Auto (50 mistakes)',
  scheduled: 'Scheduled',
  cold_start: 'Cold Start',
};

// ═══════════════════════════════════════════════════════════════════════════════
// Utility
// ═══════════════════════════════════════════════════════════════════════════════

function fmtDate(d?: string) {
  if (!d) return '—';
  return new Date(d).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function fmtDuration(start?: string, end?: string) {
  if (!start) return '—';
  const ms = (end ? new Date(end) : new Date()).getTime() - new Date(start).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m`;
}

function agentShort(id: string) {
  return id.length > 12 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Component
// ═══════════════════════════════════════════════════════════════════════════════

export default function TrainingDashboardPage() {
  // ── State ──────────────────────────────────────────────────────────────────
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<TrainingStats | null>(null);
  const [runs, setRuns] = useState<TrainingRun[]>([]);
  const [retrainingDue, setRetrainingDue] = useState<RetrainingDueAgent[]>([]);
  const [coldStartAgents, setColdStartAgents] = useState<ColdStartStatus[]>([]);
  const [schedule, setSchedule] = useState<RetrainingSchedule | null>(null);
  const [effectiveness, setEffectiveness] = useState<EffectivenessData | null>(null);
  const [expandedRun, setExpandedRun] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // ── Data Loading ───────────────────────────────────────────────────────────
  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [s, r, rd, cs, sch, eff] = await Promise.allSettled([
        getTrainingStats(),
        listTrainingRuns({ limit: 20 }),
        getAgentsDueForRetraining(true),
        getAgentsNeedingColdStart(),
        getRetrainingSchedule(30),
        getTrainingEffectiveness(undefined, 10),
      ]);
      if (s.status === 'fulfilled') setStats(s.value);
      if (r.status === 'fulfilled') setRuns(r.value.runs);
      if (rd.status === 'fulfilled') setRetrainingDue(rd.value.agents);
      if (cs.status === 'fulfilled') setColdStartAgents(cs.value.agents);
      if (sch.status === 'fulfilled') setSchedule(sch.value);
      if (eff.status === 'fulfilled') setEffectiveness(eff.value as EffectivenessData);
      const firstErr = [s, r, rd, cs, sch, eff].find((x) => x.status === 'rejected');
      if (firstErr && firstErr.status === 'rejected') {
        setError('Some data could not be loaded. Partial results shown.');
      }
    } catch {
      setError('Failed to load training data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // ── Actions ───────────────────────────────────────────────────────────────
  const handleScheduleAll = async () => {
    setActionLoading('schedule');
    try {
      await scheduleAllRetraining();
      await loadAll();
    } catch (e) {
      console.error('Schedule all failed:', e);
    } finally {
      setActionLoading(null);
    }
  };

  const handleInitializeAll = async () => {
    setActionLoading('coldstart');
    try {
      await initializeAllColdStart();
      await loadAll();
    } catch (e) {
      console.error('Init all failed:', e);
    } finally {
      setActionLoading(null);
    }
  };

  // ── Derived ───────────────────────────────────────────────────────────────
  const activeRuns = runs.filter((r) =>
    ['queued', 'preparing', 'running', 'validating'].includes(r.status)
  );
  const mistakesCount = stats?.failed ?? 0; // best available proxy; real count from mistake stats
  const avgEff = effectiveness?.avg_accuracy
    ? Math.round((effectiveness.avg_accuracy) * 100)
    : null;

  // ═══════════════════════════════════════════════════════════════════════════
  // Loading Skeleton
  // ═══════════════════════════════════════════════════════════════════════════
  if (loading) {
    return (
      <div className="min-h-screen bg-[#0D0D0D] p-6">
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <Skeleton className="h-8 w-56 bg-white/[0.06] rounded" />
              <Skeleton className="h-4 w-80 bg-white/[0.04] rounded mt-2" />
            </div>
            <Skeleton className="h-10 w-32 bg-white/[0.06] rounded-lg" />
          </div>
          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="bg-[#111111] border border-white/[0.06] rounded-xl p-6">
                <div className="flex items-center gap-4">
                  <Skeleton className="w-12 h-12 rounded-xl bg-white/[0.06]" />
                  <div className="space-y-2">
                    <Skeleton className="h-7 w-16 bg-white/[0.06]" />
                    <Skeleton className="h-3 w-24 bg-white/[0.04]" />
                  </div>
                </div>
              </div>
            ))}
          </div>
          {/* Table skeleton */}
          <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-6 space-y-4">
            <Skeleton className="h-6 w-40 bg-white/[0.06]" />
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 py-3 border-b border-white/[0.04]">
                <Skeleton className="h-4 w-24 bg-white/[0.04]" />
                <Skeleton className="h-5 w-20 bg-white/[0.06] rounded-full" />
                <Skeleton className="h-4 w-28 bg-white/[0.04]" />
                <Skeleton className="h-4 w-12 bg-white/[0.04]" />
                <Skeleton className="h-4 w-16 bg-white/[0.04]" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Render
  // ═══════════════════════════════════════════════════════════════════════════
  return (
    <div className="min-h-screen bg-[#0D0D0D] p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* ── Header ──────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Training Metrics</h1>
            <p className="text-sm text-zinc-400 mt-1">
              Monitor training runs, mistake thresholds, retraining &amp; cold start status
            </p>
          </div>
          <button
            onClick={loadAll}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/[0.06] border border-white/[0.08] text-sm text-zinc-300 hover:text-white hover:bg-white/[0.1] transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* ═════════════════════════════════════════════════════════════════ */}
        {/* 1. STATS CARDS                                               */}
        {/* ═════════════════════════════════════════════════════════════════ */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Total Runs */}
          <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center">
                <Brain className="w-6 h-6 text-blue-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{stats?.total_runs ?? 0}</p>
                <p className="text-xs text-zinc-400">Total Training Runs</p>
              </div>
            </div>
          </div>
          {/* Active Runs */}
          <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-orange-500/10 flex items-center justify-center">
                <Activity className="w-6 h-6 text-orange-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{activeRuns.length}</p>
                <p className="text-xs text-zinc-400">Active Runs</p>
              </div>
            </div>
          </div>
          {/* Mistakes Reported */}
          <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-red-500/10 flex items-center justify-center">
                <AlertTriangle className="w-6 h-6 text-red-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">
                  {(retrainingDue.reduce((sum, a) => sum + (a.current_mistakes ?? 0), 0) || (stats?.failed ?? 0))}
                </p>
                <p className="text-xs text-zinc-400">Mistakes Reported</p>
              </div>
            </div>
          </div>
          {/* Avg Effectiveness */}
          <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                <Target className="w-6 h-6 text-emerald-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">
                  {avgEff !== null ? `${avgEff}%` : '—'}
                </p>
                <p className="text-xs text-zinc-400">Avg Effectiveness</p>
              </div>
            </div>
          </div>
        </div>

        {/* ═════════════════════════════════════════════════════════════════ */}
        {/* 2. TRAINING RUNS TABLE                                      */}
        {/* ═════════════════════════════════════════════════════════════════ */}
        <SectionCard title="Training Runs" icon={<Brain className="w-5 h-5 text-blue-400" />}>
          {runs.length === 0 ? (
            <EmptyState
              icon={<Play className="w-8 h-8 text-zinc-600" />}
              message="No training runs yet"
              sub="Start a new training run to see it here."
            />
          ) : (
            <div className="overflow-x-auto">
              {/* Header row */}
              <div className="grid grid-cols-12 gap-4 px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider border-b border-white/[0.06]">
                <div className="col-span-3">Agent / Run</div>
                <div className="col-span-2">Status</div>
                <div className="col-span-3">Started At</div>
                <div className="col-span-2">Duration</div>
                <div className="col-span-2 text-right">Best Score</div>
              </div>
              {/* Rows */}
              {runs.map((run) => {
                const sc = RUN_STATUS_CONFIG[run.status] ?? RUN_STATUS_CONFIG.queued;
                const isExpanded = expandedRun === run.id;
                const bestAcc = run.metrics?.accuracy as number | undefined;
                const bestValAcc = run.metrics?.val_accuracy as number | undefined;
                const bestScore = bestValAcc ?? bestAcc;

                return (
                  <div key={run.id} className="border-b border-white/[0.04] last:border-0">
                    <button
                      className="grid grid-cols-12 gap-4 px-4 py-3 w-full text-left hover:bg-white/[0.02] transition-colors"
                      onClick={() => setExpandedRun(isExpanded ? null : run.id)}
                    >
                      <div className="col-span-3 flex items-center gap-2 min-w-0">
                        <div className={`w-2 h-2 rounded-full shrink-0 ${sc.dot}`} />
                        <span className="text-sm text-zinc-200 truncate">
                          {run.name || agentShort(run.agent_id)}
                        </span>
                      </div>
                      <div className="col-span-2 flex items-center">
                        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${sc.text} bg-white/[0.04]`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${sc.dot}`} />
                          {sc.label}
                        </span>
                      </div>
                      <div className="col-span-3 text-sm text-zinc-400">{fmtDate(run.started_at)}</div>
                      <div className="col-span-2 text-sm text-zinc-400">{fmtDuration(run.started_at, run.completed_at)}</div>
                      <div className="col-span-2 text-right text-sm text-zinc-200 font-medium">
                        {bestScore != null ? `${(bestScore * 100).toFixed(1)}%` : '—'}
                      </div>
                    </button>
                    {/* Expanded Details */}
                    {isExpanded && (
                      <div className="px-4 pb-4 pt-1 bg-white/[0.015] border-t border-white/[0.04]">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
                          <DetailPill label="Trigger" value={TRIGGER_LABELS[run.trigger] ?? run.trigger} />
                          <DetailPill label="Epochs" value={`${run.current_epoch} / ${run.total_epochs}`} />
                          <DetailPill label="Batch Size" value={String(run.batch_size)} />
                          <DetailPill label="Cost" value={`$${run.cost_usd.toFixed(2)}`} />
                          <DetailPill label="Learning Rate" value={run.learning_rate?.toExponential(1) ?? '—'} />
                          <DetailPill label="Provider" value={run.provider ?? '—'} />
                          <DetailPill label="GPU" value={run.gpu_type ?? '—'} />
                          <DetailPill label="Created" value={fmtDate(run.created_at)} />
                        </div>
                        {/* Metrics */}
                        {run.metrics && Object.keys(run.metrics).length > 0 && (
                          <div className="mt-3 p-3 rounded-lg bg-white/[0.03]">
                            <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Metrics</p>
                            <div className="flex flex-wrap gap-4 text-sm">
                              {run.metrics.accuracy != null && (
                                <span className="text-emerald-400">
                                  Accuracy: {((run.metrics.accuracy as number) * 100).toFixed(1)}%
                                </span>
                              )}
                              {run.metrics.loss != null && (
                                <span className="text-blue-400">
                                  Loss: {(run.metrics.loss as number).toFixed(4)}
                                </span>
                              )}
                              {run.metrics.val_accuracy != null && (
                                <span className="text-purple-400">
                                  Val Acc: {((run.metrics.val_accuracy as number) * 100).toFixed(1)}%
                                </span>
                              )}
                              {run.metrics.val_loss != null && (
                                <span className="text-amber-400">
                                  Val Loss: {(run.metrics.val_loss as number).toFixed(4)}
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                        {/* Progress bar for active runs */}
                        {['queued', 'preparing', 'running', 'validating'].includes(run.status) && (
                          <div className="mt-3">
                            <div className="flex justify-between text-xs text-zinc-400 mb-1">
                              <span>Progress</span>
                              <span>{run.progress_pct.toFixed(0)}%</span>
                            </div>
                            <div className="h-2 rounded-full bg-white/[0.06] overflow-hidden">
                              <div
                                className="h-full rounded-full bg-gradient-to-r from-orange-500 to-orange-400 transition-all duration-500"
                                style={{ width: `${run.progress_pct}%` }}
                              />
                            </div>
                          </div>
                        )}
                        {/* Error */}
                        {run.status === 'failed' && run.error_message && (
                          <div className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">
                            {run.error_message}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </SectionCard>

        {/* ── Two-column layout for sections 3-6 ────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ═════════════════════════════════════════════════════════════════ */}
          {/* 3. MISTAKE TRACKER (F-101)                                   */}
          {/* ═════════════════════════════════════════════════════════════════ */}
          <SectionCard title="Mistake Tracker" icon={<AlertTriangle className="w-5 h-5 text-amber-400" />}>
            {retrainingDue.length === 0 ? (
              <EmptyState
                icon={<CheckCircle className="w-8 h-8 text-zinc-600" />}
                message="All clear"
                sub="No agents approaching the 50-mistake threshold."
              />
            ) : (
              <div className="space-y-3">
                {retrainingDue.map((agent) => {
                  const mistakes = agent.current_mistakes ?? 0;
                  const threshold = agent.threshold ?? 50;
                  const pct = Math.min((mistakes / threshold) * 100, 100);
                  const isWarning = mistakes > 35;
                  const isCritical = mistakes >= threshold;

                  return (
                    <div key={agent.agent_id} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-zinc-200">{agent.agent_name || agentShort(agent.agent_id)}</span>
                          {isCritical && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-red-500/20 text-red-400">
                              TRAINING TRIGGERED
                            </span>
                          )}
                          {isWarning && !isCritical && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-400">
                              WARNING
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-zinc-500">{mistakes} / {threshold}</span>
                      </div>
                      <div className="h-2 rounded-full bg-white/[0.06] overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            isCritical
                              ? 'bg-red-500'
                              : isWarning
                              ? 'bg-amber-500'
                              : 'bg-emerald-500'
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between mt-1.5">
                        <span className="text-[10px] text-zinc-500">
                          {threshold - mistakes} mistakes until threshold
                        </span>
                        <span className="text-[10px] text-zinc-500">
                          {pct.toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </SectionCard>

          {/* ═════════════════════════════════════════════════════════════════ */}
          {/* 6. EFFECTIVENESS CHART                                        */}
          {/* ═════════════════════════════════════════════════════════════════ */}
          <SectionCard title="Retraining Effectiveness" icon={<Target className="w-5 h-5 text-emerald-400" />}>
            {!effectiveness || effectiveness.runs.length === 0 ? (
              <EmptyState
                icon={<TrendingUp className="w-8 h-8 text-zinc-600" />}
                message="No data yet"
                sub="Complete a few training runs to see effectiveness metrics."
              />
            ) : (
              <div className="space-y-4">
                {/* Summary row */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 rounded-lg bg-white/[0.03] text-center">
                    <p className="text-lg font-bold text-white">
                      {effectiveness.avg_accuracy != null
                        ? `${(effectiveness.avg_accuracy * 100).toFixed(1)}%`
                        : '—'}
                    </p>
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider mt-1">Avg Accuracy</p>
                  </div>
                  <div className="p-3 rounded-lg bg-white/[0.03] text-center">
                    <p className="text-lg font-bold text-white">
                      {effectiveness.avg_loss != null ? effectiveness.avg_loss.toFixed(4) : '—'}
                    </p>
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider mt-1">Avg Loss</p>
                  </div>
                  <div className="p-3 rounded-lg bg-white/[0.03] text-center">
                    <div className="flex items-center justify-center gap-1">
                      {effectiveness.improvement_trend === 'improving' && (
                        <TrendingUp className="w-4 h-4 text-emerald-400" />
                      )}
                      {effectiveness.improvement_trend === 'declining' && (
                        <TrendingDown className="w-4 h-4 text-red-400" />
                      )}
                      {effectiveness.improvement_trend === 'stable' && (
                        <Minus className="w-4 h-4 text-zinc-400" />
                      )}
                      <span className={`text-lg font-bold capitalize ${
                        effectiveness.improvement_trend === 'improving'
                          ? 'text-emerald-400'
                          : effectiveness.improvement_trend === 'declining'
                          ? 'text-red-400'
                          : 'text-zinc-300'
                      }`}>
                        {effectiveness.improvement_trend}
                      </span>
                    </div>
                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider mt-1">Trend</p>
                  </div>
                </div>
                {/* Per-run bars */}
                <div className="space-y-2">
                  {effectiveness.runs.map((run, idx) => {
                    const acc = (run.metrics?.accuracy as number) ?? 0;
                    return (
                      <div key={run.id} className="flex items-center gap-3">
                        <span className="text-[10px] text-zinc-500 w-4 text-right shrink-0">{idx + 1}</span>
                        <div className="flex-1 h-3 rounded-full bg-white/[0.04] overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              acc >= 0.9 ? 'bg-emerald-500' : acc >= 0.7 ? 'bg-amber-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${acc * 100}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-zinc-400 w-10 text-right shrink-0">
                          {(acc * 100).toFixed(0)}%
                        </span>
                      </div>
                    );
                  })}
                </div>
                <p className="text-[10px] text-zinc-600 text-center">Per-run accuracy (most recent first)</p>
              </div>
            )}
          </SectionCard>

          {/* ═════════════════════════════════════════════════════════════════ */}
          {/* 4. RETRAINING SCHEDULE (F-106)                               */}
          {/* ═════════════════════════════════════════════════════════════════ */}
          <SectionCard
            title="Retraining Schedule"
            icon={<CalendarClock className="w-5 h-5 text-purple-400" />}
            action={
              <button
                onClick={handleScheduleAll}
                disabled={actionLoading === 'schedule'}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-purple-500/15 text-purple-400 hover:bg-purple-500/25 transition-colors disabled:opacity-50"
              >
                {actionLoading === 'schedule' ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="w-3.5 h-3.5" />
                )}
                Schedule All Due
              </button>
            }
          >
            {!schedule || schedule.schedule.length === 0 ? (
              <EmptyState
                icon={<CalendarClock className="w-8 h-8 text-zinc-600" />}
                message="No upcoming schedule"
                sub="Retraining schedule will appear here."
              />
            ) : (
              <div className="space-y-2">
                {/* Summary */}
                <div className="flex items-center gap-4 mb-3 px-1">
                  <span className="text-xs text-zinc-500">
                    <span className="text-zinc-200 font-medium">{schedule.total_agents}</span> agents tracked
                  </span>
                  {schedule.due_count > 0 && (
                    <span className="text-xs text-zinc-500">
                      <span className="text-amber-400 font-medium">{schedule.due_count}</span> due now
                    </span>
                  )}
                </div>
                {schedule.schedule.map((item) => {
                  const isOverdue = item.is_due;
                  return (
                    <div
                      key={item.agent_id}
                      className={`flex items-center justify-between p-3 rounded-lg border ${
                        isOverdue
                          ? 'bg-amber-500/[0.04] border-amber-500/20'
                          : 'bg-white/[0.02] border-white/[0.04]'
                      }`}
                    >
                      <div>
                        <p className="text-sm font-medium text-zinc-200">
                          {item.agent_name || agentShort(item.agent_id)}
                        </p>
                        <p className="text-xs text-zinc-500 mt-0.5">
                          {fmtDate(item.next_retraining)}
                        </p>
                      </div>
                      <div className="text-right">
                        <span
                          className={`text-xs font-medium ${
                            isOverdue ? 'text-amber-400' : 'text-zinc-500'
                          }`}
                        >
                          {isOverdue ? 'Due' : `${item.days_until_due}d`}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </SectionCard>

          {/* ═════════════════════════════════════════════════════════════════ */}
          {/* 5. COLD START STATUS (F-107)                                */}
          {/* ═════════════════════════════════════════════════════════════════ */}
          <SectionCard
            title="Cold Start Status"
            icon={<Snowflake className="w-5 h-5 text-cyan-400" />}
            action={
              coldStartAgents.length > 0 ? (
                <button
                  onClick={handleInitializeAll}
                  disabled={actionLoading === 'coldstart'}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-cyan-500/15 text-cyan-400 hover:bg-cyan-500/25 transition-colors disabled:opacity-50"
                >
                  {actionLoading === 'coldstart' ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Snowflake className="w-3.5 h-3.5" />
                  )}
                  Initialize All
                </button>
              ) : undefined
            }
          >
            {coldStartAgents.length === 0 ? (
              <EmptyState
                icon={<CheckCircle className="w-8 h-8 text-zinc-600" />}
                message="All agents initialized"
                sub="No agents need cold start."
              />
            ) : (
              <div className="space-y-2">
                {coldStartAgents.map((agent) => {
                  const cs = COLD_STATUS_CONFIG[agent.status] ?? COLD_STATUS_CONFIG.cold_start_needed;
                  return (
                    <div
                      key={agent.agent_id}
                      className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-2 h-2 rounded-full ${cs.dot}`} />
                        <div>
                          <p className="text-sm font-medium text-zinc-200">
                            {agentShort(agent.agent_id)}
                          </p>
                          <p className="text-xs text-zinc-500">
                            {agent.suggested_industry || 'No industry set'} &middot; {agent.training_run_count} prior runs
                          </p>
                        </div>
                      </div>
                      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${cs.text} bg-white/[0.04]`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${cs.dot}`} />
                        {cs.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Sub-components
// ═══════════════════════════════════════════════════════════════════════════════

function SectionCard({
  title,
  icon,
  action,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-[#111111] border border-white/[0.06] rounded-xl">
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="text-sm font-semibold text-white">{title}</h2>
        </div>
        {action}
      </div>
      <div className="p-6">{children}</div>
    </div>
  );
}

function EmptyState({
  icon,
  message,
  sub,
}: {
  icon: React.ReactNode;
  message: string;
  sub: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="w-14 h-14 rounded-full bg-white/[0.03] flex items-center justify-center mb-3">
        {icon}
      </div>
      <p className="text-sm font-medium text-zinc-300">{message}</p>
      <p className="text-xs text-zinc-500 mt-1">{sub}</p>
    </div>
  );
}

function DetailPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white/[0.03] rounded-lg px-3 py-2">
      <p className="text-[10px] text-zinc-500 uppercase tracking-wider">{label}</p>
      <p className="text-xs text-zinc-200 font-medium mt-0.5">{value}</p>
    </div>
  );
}
