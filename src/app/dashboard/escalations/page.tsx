'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { getErrorMessage } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import apiClient from '@/lib/api';

// ── Types ───────────────────────────────────────────────────────────────

interface EscalationRecord {
  escalation_id: string;
  company_id: string;
  ticket_id: string;
  trigger: string;
  severity: string;
  channel: string;
  status: string;
  context: Record<string, unknown>;
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  outcome: string | null;
  assigned_to: string | null;
  response_message: string | null;
  cooldown_until: string | null;
  metadata: Record<string, unknown>;
}

interface EscalationStats {
  total_active: number;
  total_resolved_24h: number;
  by_severity: Record<string, number>;
  by_trigger_type: Record<string, number>;
  avg_resolution_time_seconds: number;
  total_escalations: number;
  resolved_escalations: number;
  by_outcome: Record<string, number>;
}

interface PeerReviewItem {
  escalation_id?: string;
  junior_agent_id?: string;
  senior_agent_id?: string;
  ticket_id?: string;
  reason?: string;
  priority?: string;
  status?: string;
  submitted_at?: string;
  [key: string]: unknown;
}

// ── Constants ───────────────────────────────────────────────────────────

const SEVERITY_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  critical: { label: 'Critical', color: 'bg-red-500/15 text-red-400 border-red-500/20', dot: 'bg-red-500' },
  high:     { label: 'High',     color: 'bg-amber-500/15 text-amber-400 border-amber-500/20', dot: 'bg-amber-500' },
  medium:   { label: 'Medium',   color: 'bg-blue-500/15 text-blue-400 border-blue-500/20', dot: 'bg-blue-500' },
  low:      { label: 'Low',      color: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/20', dot: 'bg-zinc-500' },
};

const TRIGGER_LABELS: Record<string, string> = {
  high_frustration: 'High Frustration',
  legal_sensitive: 'Legal / Sensitive',
  multiple_failures: 'Multiple Failures',
  collision_conflict: 'Collision Conflict',
  stale_session: 'Stale Session',
  timeout: 'Timeout',
  confidence_low: 'Low Confidence',
  vip_customer: 'VIP Customer',
  manual_request: 'Manual Request',
  loop_detected: 'Loop Detected',
  capacity_overflow: 'Capacity Overflow',
  partial_failure_critical: 'Partial Failure',
};

// ── Helpers ─────────────────────────────────────────────────────────────

function formatTimestamp(dateStr: string | null): string {
  if (!dateStr) return '\u2014';
  const d = new Date(dateStr);
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function relativeTime(dateStr: string | null): string {
  if (!dateStr) return '';
  const diffSec = Math.round((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

function formatSeconds(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.round((s % 60))}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

function triggerLabel(t: string): string {
  return TRIGGER_LABELS[t] || t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function severityBadge(severity: string) {
  const cfg = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.low;
  return (
    <Badge variant="outline" className={`text-[10px] font-medium ${cfg.color}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot} mr-1.5`} />
      {cfg.label}
    </Badge>
  );
}

function statusBadge(status: string) {
  const styles: Record<string, string> = {
    pending: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
    acknowledged: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
    in_progress: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/20',
    resolved: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  };
  return (
    <Badge variant="outline" className={`text-[10px] font-medium capitalize ${styles[status] || 'bg-zinc-500/10 text-zinc-400 border-zinc-500/15'}`}>
      {status.replace('_', ' ')}
    </Badge>
  );
}

// ── Inline Icons ─────────────────────────────────────────────────────────

const RefreshIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
  </svg>
);

const ChevronDownIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
  </svg>
);

const ChevronUpIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 15.75 7.5-7.5 7.5 7.5" />
  </svg>
);

const AlertTriangleIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
  </svg>
);

const ClockIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
  </svg>
);

const CheckCircleIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
  </svg>
);

const UsersIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" />
  </svg>
);

// ── Skeleton ────────────────────────────────────────────────────────────

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 5 }).map((_, i) => (
        <TableRow key={i} className="hover:bg-transparent">
          <TableCell className="p-3"><Skeleton className="h-5 w-16 rounded-full" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-28" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-40" /></TableCell>
          <TableCell className="p-3 hidden md:table-cell"><Skeleton className="h-4 w-20" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-4 w-24" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-5 w-20 rounded-full" /></TableCell>
          <TableCell className="p-3"><Skeleton className="h-6 w-16" /></TableCell>
        </TableRow>
      ))}
    </>
  );
}

// ════════════════════════════════════════════════════════════════════════
// Main Component
// ════════════════════════════════════════════════════════════════════════

export default function EscalationsPage() {
  const { user } = useAuth();

  // ── State ─────────────────────────────────────────────────────────────
  const [stats, setStats] = useState<EscalationStats | null>(null);
  const [active, setActive] = useState<EscalationRecord[]>([]);
  const [history, setHistory] = useState<EscalationRecord[]>([]);
  const [peerReviews, setPeerReviews] = useState<PeerReviewItem[]>([]);

  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [historyOpen, setHistoryOpen] = useState(false);

  // Manual escalation form
  const [manualTrigger, setManualTrigger] = useState('manual_request');
  const [manualSeverity, setManualSeverity] = useState('medium');
  const [manualDesc, setManualDesc] = useState('');
  const [manualTicketId, setManualTicketId] = useState('');
  const [manualSubmitting, setManualSubmitting] = useState(false);

  // Resolve form
  const [resolveId, setResolveId] = useState<string | null>(null);
  const [resolveOutcome, setResolveOutcome] = useState('resolved');
  const [resolveNote, setResolveNote] = useState('');
  const [resolveSubmitting, setResolveSubmitting] = useState(false);

  // Peer review form
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [reviewDecision, setReviewDecision] = useState('approve');
  const [reviewFeedback, setReviewFeedback] = useState('');
  const [reviewSubmitting, setReviewSubmitting] = useState(false);

  // ── Fetch data ────────────────────────────────────────────────────────

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setStatsLoading(true);
    setError(null);
    try {
      const [statsRes, activeRes, historyRes, peerRes] = await Promise.all([
        apiClient.get('/api/escalation/stats'),
        apiClient.get('/api/escalation/active', { params: { limit: 100 } }),
        apiClient.get('/api/escalation/history', { params: { limit: 50 } }),
        apiClient.get('/api/escalation/peer-review/pending', { params: { limit: 20 } }).catch(() => ({ data: { queue: [], total: 0, pending_count: 0 } })),
      ]);
      setStats(statsRes.data);
      setActive(statsRes.data ? (activeRes.data.items || []) : []);
      setHistory(historyRes.data.items || []);
      setPeerReviews((peerRes.data as any).queue || []);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
      setStatsLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // ── Filtered active list ─────────────────────────────────────────────

  const filteredActive = severityFilter === 'all'
    ? active
    : active.filter(e => e.severity === severityFilter);

  // ── Handlers ──────────────────────────────────────────────────────────

  const handleAcknowledge = async (id: string) => {
    try {
      await apiClient.post(`/api/escalation/${id}/acknowledge`, { note: 'Acknowledged from dashboard' });
      fetchAll();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const handleResolve = async () => {
    if (!resolveId) return;
    setResolveSubmitting(true);
    setError(null);
    try {
      await apiClient.post(`/api/escalation/${resolveId}/resolve`, {
        resolution: resolveNote,
        outcome: resolveOutcome,
      });
      setResolveId(null);
      setResolveNote('');
      fetchAll();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setResolveSubmitting(false);
    }
  };

  const handleManualSubmit = async () => {
    if (!manualDesc.trim()) return;
    setManualSubmitting(true);
    setError(null);
    try {
      await apiClient.post('/api/escalation/manual', {
        trigger_type: manualTrigger,
        severity: manualSeverity,
        description: manualDesc,
        ticket_id: manualTicketId || null,
      });
      setManualDesc('');
      setManualTicketId('');
      fetchAll();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setManualSubmitting(false);
    }
  };

  const handlePeerReviewSubmit = async () => {
    if (!reviewId) return;
    setReviewSubmitting(true);
    setError(null);
    try {
      await apiClient.post(`/api/escalation/peer-review/${reviewId}/review`, {
        decision: reviewDecision,
        feedback: reviewFeedback || null,
      });
      setReviewId(null);
      setReviewFeedback('');
      fetchAll();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setReviewSubmitting(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#0D0D0D] p-4 md:p-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">Escalations</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            {loading ? 'Loading...' : `${filteredActive.length} active escalation${filteredActive.length !== 1 ? 's' : ''}`}
          </p>
        </div>
        <Button
          variant="ghost" size="sm"
          className="text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
          onClick={fetchAll}
        >
          <RefreshIcon /> Refresh
        </Button>
      </div>

      {/* ── Stats Cards ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {/* Active Escalations */}
        <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center text-red-400">
              <AlertTriangleIcon />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Active</p>
              <p className="text-2xl font-semibold text-zinc-100">
                {statsLoading ? <Skeleton className="h-7 w-8 inline-block" /> : (stats?.total_active ?? 0)}
              </p>
              <div className="flex gap-1 mt-1">
                {stats?.by_severity && Object.entries(stats.by_severity).map(([sev, count]) => {
                  const cfg = SEVERITY_CONFIG[sev];
                  if (!cfg || count === 0) return null;
                  return (
                    <span key={sev} className={`text-[9px] font-medium px-1.5 py-0.5 rounded ${cfg.color}`}>
                      {count}
                    </span>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Resolved 24h */}
        <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
              <CheckCircleIcon />
            </div>
            <div className="min-w-0">
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Resolved (24h)</p>
              <p className="text-2xl font-semibold text-zinc-100">
                {statsLoading ? <Skeleton className="h-7 w-8 inline-block" /> : (stats?.total_resolved_24h ?? 0)}
              </p>
            </div>
          </div>
        </div>

        {/* Avg Resolution Time */}
        <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-400">
              <ClockIcon />
            </div>
            <div className="min-w-0">
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Avg Resolution</p>
              <p className="text-2xl font-semibold text-zinc-100">
                {statsLoading ? <Skeleton className="h-7 w-16 inline-block" /> : formatSeconds(stats?.avg_resolution_time_seconds ?? 0)}
              </p>
            </div>
          </div>
        </div>

        {/* Pending Peer Reviews */}
        <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center text-orange-400">
              <UsersIcon />
            </div>
            <div className="min-w-0">
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Peer Reviews</p>
              <p className="text-2xl font-semibold text-zinc-100">
                {statsLoading ? <Skeleton className="h-7 w-8 inline-block" /> : (peerReviews.length ?? 0)}
              </p>
              <p className="text-[11px] text-zinc-600">Pending reviews</p>
            </div>
          </div>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-300 ml-2">&times;</button>
        </div>
      )}

      {/* ── Active Escalations Table ─────────────────────────────────── */}
      <div className="bg-[#111111] border border-white/[0.06] rounded-xl overflow-hidden mb-6">
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
          <h2 className="text-sm font-medium text-zinc-200">Active Escalations</h2>
          <Select value={severityFilter} onValueChange={setSeverityFilter}>
            <SelectTrigger size="sm" className="w-[130px] bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-xs">
              <SelectValue placeholder="All Severities" />
            </SelectTrigger>
            <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
              <SelectItem value="all" className="text-zinc-300">All Severities</SelectItem>
              {Object.entries(SEVERITY_CONFIG).map(([k, v]) => (
                <SelectItem key={k} value={k} className="text-zinc-300">{v.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Table>
          <TableHeader>
            <TableRow className="border-b border-white/[0.06] hover:bg-transparent">
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Severity</TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Trigger</TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Description</TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden md:table-cell">Ticket</TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Created</TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Status</TableHead>
              <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="divide-y divide-white/[0.04]">
            {loading && <SkeletonRows />}
            {!loading && filteredActive.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={7} className="py-12 text-center">
                  <p className="text-sm text-zinc-500">No active escalations</p>
                  <p className="text-xs text-zinc-600 mt-1">Escalations will appear here when triggered by the system or created manually.</p>
                </TableCell>
              </TableRow>
            )}
            {!loading && filteredActive.map((esc) => (
              <TableRow key={esc.escalation_id} className="hover:bg-white/[0.02] transition-colors">
                <TableCell className="p-3">{severityBadge(esc.severity)}</TableCell>
                <TableCell className="p-3 text-sm text-zinc-300">{triggerLabel(esc.trigger)}</TableCell>
                <TableCell className="p-3 text-sm text-zinc-400 max-w-[200px] truncate">
                  {(esc.context as any)?.description || '\u2014'}
                </TableCell>
                <TableCell className="p-3 hidden md:table-cell">
                  <span className="text-sm text-zinc-500 font-mono">{esc.ticket_id || '\u2014'}</span>
                </TableCell>
                <TableCell className="p-3">
                  <div className="flex flex-col">
                    <span className="text-sm text-zinc-200">{formatTimestamp(esc.created_at)}</span>
                    <span className="text-[11px] text-zinc-600">{relativeTime(esc.created_at)}</span>
                  </div>
                </TableCell>
                <TableCell className="p-3">{statusBadge(esc.status)}</TableCell>
                <TableCell className="p-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    {esc.status === 'pending' && (
                      <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
                        onClick={() => handleAcknowledge(esc.escalation_id)}>
                        Ack
                      </Button>
                    )}
                    <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
                      onClick={() => { setResolveId(esc.escalation_id); setResolveOutcome('resolved'); setResolveNote(''); }}>
                      Resolve
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* ── Resolve Modal (inline) ────────────────────────────────────── */}
      {resolveId && (
        <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4 mb-6">
          <h3 className="text-sm font-medium text-zinc-200 mb-3">Resolve Escalation</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Select value={resolveOutcome} onValueChange={setResolveOutcome}>
              <SelectTrigger className="bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                <SelectItem value="resolved" className="text-zinc-300">Resolved</SelectItem>
                <SelectItem value="human_took_over" className="text-zinc-300">Human Took Over</SelectItem>
                <SelectItem value="dismissed" className="text-zinc-300">False Alarm</SelectItem>
                <SelectItem value="escalated_further" className="text-zinc-300">Escalated Further</SelectItem>
              </SelectContent>
            </Select>
            <input
              type="text"
              placeholder="Resolution notes..."
              value={resolveNote}
              onChange={(e) => setResolveNote(e.target.value)}
              className="h-9 px-3 bg-[#1A1A1A] border border-white/[0.06] rounded-lg text-sm text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-[#FF7F11]/50 col-span-1 sm:col-span-1"
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={handleResolve} disabled={resolveSubmitting}
                className="bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 h-9">
                {resolveSubmitting ? 'Resolving...' : 'Confirm'}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setResolveId(null)}
                className="text-zinc-500 hover:text-zinc-300 h-9">Cancel</Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Peer Review Queue ─────────────────────────────────────────── */}
      <div className="bg-[#111111] border border-white/[0.06] rounded-xl overflow-hidden mb-6">
        <div className="px-4 py-3 border-b border-white/[0.06]">
          <h2 className="text-sm font-medium text-zinc-200">Peer Review Queue</h2>
        </div>
        {peerReviews.length === 0 ? (
          <div className="py-10 text-center">
            <p className="text-sm text-zinc-500">No pending peer reviews</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-b border-white/[0.06] hover:bg-transparent">
                <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Agent</TableHead>
                <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Reason</TableHead>
                <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden md:table-cell">Ticket</TableHead>
                <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Priority</TableHead>
                <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="divide-y divide-white/[0.04]">
              {peerReviews.map((pr, idx) => (
                <React.Fragment key={idx}>
                  <TableRow className="hover:bg-white/[0.02]">
                    <TableCell className="p-3 text-sm text-zinc-300">
                      {pr.junior_agent_id ? pr.junior_agent_id.slice(0, 8) + '...' : '\u2014'}
                    </TableCell>
                    <TableCell className="p-3 text-sm text-zinc-400 max-w-[200px] truncate">{pr.reason || '\u2014'}</TableCell>
                    <TableCell className="p-3 hidden md:table-cell text-sm text-zinc-500 font-mono">{pr.ticket_id || '\u2014'}</TableCell>
                    <TableCell className="p-3">
                      <Badge variant="outline" className={`text-[10px] font-medium ${
                        pr.priority === 'high' || pr.priority === 'urgent'
                          ? 'bg-red-500/15 text-red-400 border-red-500/20'
                          : 'bg-zinc-500/10 text-zinc-400 border-zinc-500/15'
                      }`}>
                        {pr.priority || 'normal'}
                      </Badge>
                    </TableCell>
                    <TableCell className="p-3 text-right">
                      {reviewId === (pr.escalation_id || String(idx)) ? (
                        <Button size="sm" variant="ghost" className="text-zinc-500 h-7 text-xs"
                          onClick={() => setReviewId(null)}>Cancel</Button>
                      ) : (
                        <Button size="sm" variant="ghost"
                          className="text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 h-7 text-xs"
                          onClick={() => { setReviewId(pr.escalation_id || String(idx)); setReviewDecision('approve'); setReviewFeedback(''); }}>
                          Review
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                  {reviewId === (pr.escalation_id || String(idx)) && (
                    <TableRow className="bg-white/[0.01]">
                      <TableCell colSpan={5} className="p-4">
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                          <Select value={reviewDecision} onValueChange={setReviewDecision}>
                            <SelectTrigger className="bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-sm">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                              <SelectItem value="approve" className="text-emerald-400">Approve</SelectItem>
                              <SelectItem value="request_changes" className="text-amber-400">Request Changes</SelectItem>
                              <SelectItem value="reject" className="text-red-400">Reject</SelectItem>
                            </SelectContent>
                          </Select>
                          <textarea
                            placeholder="Feedback for the junior agent..."
                            value={reviewFeedback}
                            onChange={(e) => setReviewFeedback(e.target.value)}
                            rows={1}
                            className="h-9 px-3 py-1 bg-[#1A1A1A] border border-white/[0.06] rounded-lg text-sm text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-[#FF7F11]/50 resize-none"
                          />
                          <div className="flex gap-2">
                            <Button size="sm" onClick={handlePeerReviewSubmit} disabled={reviewSubmitting}
                              className={`h-9 ${
                                reviewDecision === 'approve' ? 'bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25'
                                  : reviewDecision === 'reject' ? 'bg-red-500/15 text-red-400 hover:bg-red-500/25'
                                  : 'bg-amber-500/15 text-amber-400 hover:bg-amber-500/25'
                              }`}>
                              {reviewSubmitting ? 'Submitting...' : 'Submit'}
                            </Button>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {/* ── Manual Escalation Form ────────────────────────────────────── */}
      <div className="bg-[#111111] border border-white/[0.06] rounded-xl p-4 mb-6">
        <h2 className="text-sm font-medium text-zinc-200 mb-3">Create Manual Escalation</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <Select value={manualTrigger} onValueChange={setManualTrigger}>
            <SelectTrigger className="bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
              {Object.entries(TRIGGER_LABELS).map(([k, v]) => (
                <SelectItem key={k} value={k} className="text-zinc-300">{v}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={manualSeverity} onValueChange={setManualSeverity}>
            <SelectTrigger className="bg-[#1A1A1A] border-white/[0.06] text-zinc-300 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
              {Object.entries(SEVERITY_CONFIG).map(([k, v]) => (
                <SelectItem key={k} value={k} className="text-zinc-300">{v.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <input
            type="text"
            placeholder="Ticket ID (optional)"
            value={manualTicketId}
            onChange={(e) => setManualTicketId(e.target.value)}
            className="h-9 px-3 bg-[#1A1A1A] border border-white/[0.06] rounded-lg text-sm text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-[#FF7F11]/50"
          />

          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Description *"
              value={manualDesc}
              onChange={(e) => setManualDesc(e.target.value)}
              className="flex-1 h-9 px-3 bg-[#1A1A1A] border border-white/[0.06] rounded-lg text-sm text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-[#FF7F11]/50"
            />
            <Button size="sm" onClick={handleManualSubmit} disabled={manualSubmitting || !manualDesc.trim()}
              className="bg-orange-500/15 text-orange-400 hover:bg-orange-500/25 h-9 whitespace-nowrap">
              {manualSubmitting ? '...' : 'Escalate'}
            </Button>
          </div>
        </div>
      </div>

      {/* ── History (Collapsible) ─────────────────────────────────────── */}
      <div className="bg-[#111111] border border-white/[0.06] rounded-xl overflow-hidden">
        <button
          className="w-full flex items-center justify-between px-4 py-3 border-b border-white/[0.06] hover:bg-white/[0.02] transition-colors"
          onClick={() => setHistoryOpen(!historyOpen)}
        >
          <h2 className="text-sm font-medium text-zinc-200">
            History <span className="text-zinc-600 ml-1">({history.length} resolved)</span>
          </h2>
          {historyOpen ? <ChevronUpIcon /> : <ChevronDownIcon />}
        </button>

        {historyOpen && (
          <Table>
            <TableHeader>
              <TableRow className="border-b border-white/[0.06] hover:bg-transparent">
                <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Severity</TableHead>
                <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Trigger</TableHead>
                <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Description</TableHead>
                <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden md:table-cell">Outcome</TableHead>
                <TableHead className="p-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Resolved</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="divide-y divide-white/[0.04]">
              {history.length === 0 && (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={5} className="py-8 text-center text-sm text-zinc-500">
                    No resolved escalations yet.
                  </TableCell>
                </TableRow>
              )}
              {history.map((esc) => (
                <TableRow key={esc.escalation_id} className="hover:bg-white/[0.02]">
                  <TableCell className="p-3">{severityBadge(esc.severity)}</TableCell>
                  <TableCell className="p-3 text-sm text-zinc-300">{triggerLabel(esc.trigger)}</TableCell>
                  <TableCell className="p-3 text-sm text-zinc-500 max-w-[200px] truncate">
                    {(esc.context as any)?.description || esc.response_message || '\u2014'}
                  </TableCell>
                  <TableCell className="p-3 hidden md:table-cell">
                    <Badge variant="outline" className="text-[10px] font-medium bg-zinc-500/10 text-zinc-400 border-zinc-500/15 capitalize">
                      {(esc.outcome || '\u2014').replace('_', ' ')}
                    </Badge>
                  </TableCell>
                  <TableCell className="p-3 text-sm text-zinc-500">{formatTimestamp(esc.resolved_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
