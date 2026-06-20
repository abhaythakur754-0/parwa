/**
 * Jarvis Dashboard Page (/dashboard/jarvis)
 *
 * Full Jarvis interface with tabs for:
 *  - Chat: JarvisCC + Shadow Mode + Command Palette (existing)
 *  - Quality: Scores, drift, health, alerts, weekly report
 *  - SLA: Status, credits
 *  - Approvals: Pending approvals with batch actions
 *  - Notifications: System notifications with batch resolve
 *  - Wave 8: Agent provisioning, copilot, skills, corrections
 *  - Audit: Audit log viewer
 */

'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { JarvisCCChat } from '@/components/jarvis-cc/JarvisCCChat';
import { JarvisCommandPalette } from '@/components/jarvis-cc/JarvisCommandPalette';
import { useCommandPalette, useJarvisCCSession, useJarvisCommands } from '@/hooks/useJarvisCC';
import { useShadowMode } from '@/hooks/useShadowMode';
import {
  useJarvisQuality,
  useJarvisSLA,
  useJarvisApprovals,
  useJarvisNotifications,
  useJarvisWave8,
  useJarvisAudit,
  useJarvisPipelineStatus,
  useJarvisFlags,
  useJarvisCommandControl,
} from '@/hooks/useJarvisPipeline';
import { toast } from 'sonner';

// ── Tab Types ─────────────────────────────────────────────────────

type TabId = 'chat' | 'quality' | 'sla' | 'approvals' | 'notifications' | 'wave8' | 'audit';

interface TabItem {
  id: TabId;
  label: string;
  shortLabel: string;
}

const TABS: TabItem[] = [
  { id: 'chat', label: 'Chat', shortLabel: 'Chat' },
  { id: 'quality', label: 'Quality', shortLabel: 'Quality' },
  { id: 'sla', label: 'SLA', shortLabel: 'SLA' },
  { id: 'approvals', label: 'Approvals', shortLabel: 'Approvals' },
  { id: 'notifications', label: 'Notifications', shortLabel: 'Notifs' },
  { id: 'wave8', label: 'Wave 8', shortLabel: 'W8' },
  { id: 'audit', label: 'Audit', shortLabel: 'Audit' },
];

// ── Skeleton Card ─────────────────────────────────────────────────

function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn('rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4 animate-pulse', className)}>
      <div className="h-3 w-20 bg-white/[0.06] rounded mb-3" />
      <div className="h-6 w-16 bg-white/[0.06] rounded" />
    </div>
  );
}

// ── Stat Card ───────────────────────────────────────────────────

function StatCard({ label, value, sub, color, icon }: { label: string; value: string | number; sub?: string; color?: string; icon?: React.ReactNode }) {
  return (
    <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">{label}</span>
        {icon && <span className="text-zinc-600">{icon}</span>}
      </div>
      <p className={cn('text-xl font-bold', color || 'text-white')}>{value}</p>
      {sub && <p className="text-[10px] text-zinc-600 mt-1">{sub}</p>}
    </div>
  );
}

// ── Quality Tab ───────────────────────────────────────────────────

function QualityTab() {
  const quality = useJarvisQuality();
  const flags = useJarvisFlags();
  const control = useJarvisCommandControl();

  useEffect(() => { quality.refreshAll(); flags.fetchFlags(); }, []);
  useEffect(() => { const t = setInterval(() => quality.refreshAll(), 60000); return () => clearInterval(t); }, [quality]);

  const healthData = quality.healthScore.data as Record<string, unknown> | null;
  const driftData = quality.driftCheck.data as Record<string, unknown> | null;
  const scoresData = quality.scores.data as Record<string, unknown> | null;
  const alertsData = quality.alerts.data as Record<string, unknown> | null;
  const alertsList = (alertsData?.alerts as unknown[]) || [];

  return (
    <div className="space-y-4">
      {/* Action bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={() => quality.fetchReport()} className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors">
          Weekly Report
        </button>
        <button onClick={() => quality.fetchRecommendations()} className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors">
          Recommendations
        </button>
        <button onClick={() => control.pause('Manual quality review')} disabled={control.isLoading} className="text-xs px-3 py-1.5 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 transition-colors disabled:opacity-50">
          {control.isLoading ? 'Pausing...' : 'Pause Pipeline'}
        </button>
        <button onClick={() => control.resume('Quality review done')} disabled={control.isLoading} className="text-xs px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-50">
          {control.isLoading ? 'Resuming...' : 'Resume Pipeline'}
        </button>
      </div>

      {/* Score cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {quality.healthScore.status === 'loading' ? (
          <>
            <SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard />
          </>
        ) : (
          <>
            <StatCard
              label="Health Score"
              value={typeof healthData?.health_score === 'number' ? `${Math.round((healthData.health_score as number) * 100)}%` : '--'}
              sub="Overall system health"
              color={(healthData?.health_score as number) >= 0.7 ? 'text-emerald-400' : (healthData?.health_score as number) >= 0.4 ? 'text-amber-400' : 'text-red-400'}
            />
            <StatCard
              label="Drift"
              value={typeof driftData?.drift_detected === 'boolean' ? (driftData.drift_detected ? 'YES' : 'No') : '--'}
              sub={driftData?.severity || 'Stable'}
              color={driftData?.drift_detected ? 'text-amber-400' : 'text-emerald-400'}
            />
            <StatCard
              label="Quality Avg"
              value={typeof scoresData?.avg_score === 'number' ? `${Math.round((scoresData.avg_score as number) * 100)}%` : '--'}
              sub="Across all tickets"
              color={(scoresData?.avg_score as number) >= 0.7 ? 'text-emerald-400' : 'text-amber-400'}
            />
            <StatCard
              label="Alerts"
              value={alertsList.length}
              sub="Active quality alerts"
              color={alertsList.length > 5 ? 'text-red-400' : alertsList.length > 0 ? 'text-amber-400' : 'text-emerald-400'}
            />
          </>
        )}
      </div>

      {/* Weekly report preview */}
      {quality.report.data && (
        <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
          <h3 className="text-sm font-semibold text-white mb-3">Weekly Report Preview</h3>
          <pre className="text-xs text-zinc-400 whitespace-pre-wrap max-h-48 overflow-y-auto">{JSON.stringify(quality.report.data, null, 2)}</pre>
        </div>
      )}

      {/* Quality alerts */}
      {alertsList.length > 0 && (
        <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
          <h3 className="text-sm font-semibold text-white mb-3">Quality Alerts</h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {alertsList.map((alert, i) => {
              const a = alert as Record<string, unknown>;
              return (
                <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                  <div>
                    <p className="text-xs text-zinc-300">{String(a.message || a.alert_type || 'Alert')}</p>
                    <p className="text-[10px] text-zinc-600">{String(a.timestamp || '')}</p>
                  </div>
                  <button
                    onClick={() => quality.resolveAlert(String(a.id || i)).then(() => quality.fetchAlerts())}
                    className="text-[10px] px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                  >
                    Resolve
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Active flags */}
      {flags.flags.data && Array.isArray(flags.flags.data?.active_flags) && (flags.flags.data.active_flags as unknown[]).length > 0 && (
        <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
          <h3 className="text-sm font-semibold text-white mb-3">Active Flags</h3>
          <div className="space-y-2">
            {(flags.flags.data.active_flags as unknown[]).map((flag, i) => {
              const f = flag as Record<string, unknown>;
              return (
                <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-amber-500/5 border border-amber-500/10">
                  <div>
                    <p className="text-xs text-amber-400 font-medium">{String(f.flag_key || 'Flag')}</p>
                    <p className="text-[10px] text-zinc-600">{String(f.reason || '')}</p>
                  </div>
                  <button
                    onClick={() => flags.revokeFlag(String(f.id || i)).then(() => flags.fetchFlags())}
                    className="text-[10px] px-2 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20"
                  >
                    Revoke
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── SLA Tab ─────────────────────────────────────────────────────

function SlaTab() {
  const sla = useJarvisSLA();

  useEffect(() => { sla.refreshAll(); }, []);

  const statusData = sla.slaStatus.data as Record<string, unknown> | null;
  const creditsData = sla.credits.data as Record<string, unknown> | null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {sla.slaStatus.status === 'loading' ? (
          <><SkeletonCard className="h-32" /><SkeletonCard className="h-32" /></>
        ) : (
          <>
            <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5">
              <h3 className="text-sm font-semibold text-white mb-4">SLA Status</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-xs text-zinc-500">Status</span>
                  <span className={cn('text-xs font-semibold', statusData?.status === 'healthy' ? 'text-emerald-400' : 'text-amber-400')}>
                    {String(statusData?.status || 'Unknown')}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-zinc-500">Current Response Time</span>
                  <span className="text-xs font-medium text-white">{String(statusData?.avg_response_time || '--')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-zinc-500">Breach Count</span>
                  <span className={cn('text-xs font-medium', (statusData?.breach_count as number) > 0 ? 'text-red-400' : 'text-emerald-400')}>
                    {String(statusData?.breach_count || 0)}
                  </span>
                </div>
              </div>
            </div>
            <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5">
              <h3 className="text-sm font-semibold text-white mb-4">SLA Credits</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-xs text-zinc-500">Available Credits</span>
                  <span className="text-xs font-bold text-white">{String(creditsData?.available_credits || '--')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-zinc-500">Used Credits</span>
                  <span className="text-xs font-medium text-zinc-300">{String(creditsData?.used_credits || 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-zinc-500">Total Earned</span>
                  <span className="text-xs font-medium text-zinc-300">{String(creditsData?.total_earned || 0)}</span>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Approvals Tab ────────────────────────────────────────────────

function ApprovalsTab() {
  const approvals = useJarvisApprovals();

  useEffect(() => { approvals.fetchPending(); }, []);

  const pendingData = approvals.pending.data as Record<string, unknown> | null;
  const pendingList = (pendingData?.pending as unknown[]) || [];

  const handleBatchApprove = async () => {
    try {
      await approvals.batchApprove();
      toast.success('All pending approvals approved');
      approvals.fetchPending();
    } catch { toast.error('Failed to batch approve'); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={handleBatchApprove} disabled={pendingList.length === 0} className="text-xs px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-40">
          Approve All ({pendingList.length})
        </button>
        <button onClick={() => approvals.fetchPending()} className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors">
          Refresh
        </button>
      </div>

      {approvals.pending.status === 'loading' ? (
        <div className="space-y-2"><SkeletonCard /><SkeletonCard /><SkeletonCard /></div>
      ) : pendingList.length === 0 ? (
        <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-8 text-center">
          <p className="text-sm text-zinc-500">No pending approvals</p>
        </div>
      ) : (
        <div className="space-y-2">
          {pendingList.map((item, i) => {
            const a = item as Record<string, unknown>;
            return (
              <div key={i} className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-white">{String(a.command_type || a.action || 'Approval')}</p>
                  <p className="text-[10px] text-zinc-600 mt-0.5">{String(a.reason || a.description || '')}</p>
                  <p className="text-[10px] text-zinc-600">{String(a.created_at || '')}</p>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 font-medium">
                  Pending
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Notifications Tab ────────────────────────────────────────────

function NotificationsTab() {
  const notifs = useJarvisNotifications();

  useEffect(() => { notifs.fetchNotifications(); }, []);

  const notifsData = notifs.notifications.data as Record<string, unknown> | null;
  const notifsList = (notifsData?.notifications as unknown[]) || [];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={() => notifs.fetchNotifications(true)} className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors">
          Include Resolved
        </button>
        <button onClick={async () => { try { await notifs.batchApprove(); toast.success('All notifications approved'); notifs.fetchNotifications(); } catch { toast.error('Failed'); }}} className="text-xs px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors">
          Approve All
        </button>
        <button onClick={async () => { try { await notifs.batchReject(); toast.success('All notifications rejected'); notifs.fetchNotifications(); } catch { toast.error('Failed'); }}} className="text-xs px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors">
          Reject All
        </button>
        <button onClick={() => notifs.fetchNotifications()} className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors">
          Refresh
        </button>
      </div>

      {notifs.notifications.status === 'loading' ? (
        <div className="space-y-2"><SkeletonCard /><SkeletonCard /><SkeletonCard /></div>
      ) : notifsList.length === 0 ? (
        <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-8 text-center">
          <p className="text-sm text-zinc-500">No notifications</p>
        </div>
      ) : (
        <div className="space-y-2">
          {notifsList.map((notif, i) => {
            const n = notif as Record<string, unknown>;
            const severity = String(n.severity || 'info');
            const severityColor = severity === 'emergency' || severity === 'critical' ? 'border-red-500/20 bg-red-500/5' :
              severity === 'warning' ? 'border-amber-500/20 bg-amber-500/5' : 'border-blue-500/20 bg-blue-500/5';
            return (
              <div key={i} className={cn('rounded-xl border p-4 flex items-center justify-between', severityColor)}>
                <div>
                  <p className="text-xs font-medium text-white">{String(n.title || n.type || 'Notification')}</p>
                  <p className="text-[10px] text-zinc-500 mt-0.5">{String(n.message || n.body || '')}</p>
                  <p className="text-[10px] text-zinc-600">{String(n.created_at || '')}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => notifs.resolveNotification(String(n.key || n.id || i)).then(() => notifs.fetchNotifications())}
                    className="text-[10px] px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                  >
                    Resolve
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Wave 8 Tab ───────────────────────────────────────────────────

function Wave8Tab() {
  const wave8 = useJarvisWave8();
  const [draftTicketId, setDraftTicketId] = useState('');
  const [draftQuery, setDraftQuery] = useState('');
  const [teachAgent, setTeachAgent] = useState('');
  const [teachSkill, setTeachSkill] = useState('');
  const [teachContent, setTeachContent] = useState('');

  useEffect(() => { wave8.fetchAgents(); wave8.fetchSkills(); }, []);

  const agentsData = wave8.agents.data as Record<string, unknown> | null;
  const agentsList = (agentsData?.agents as unknown[]) || [];
  const skillsData = wave8.skills.data as Record<string, unknown> | null;
  const skillsList = (skillsData?.skills as unknown[]) || [];

  return (
    <div className="space-y-4">
      {/* Agents list */}
      <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-white">Provisioned Agents</h3>
          <button onClick={() => wave8.fetchAgents()} className="text-[10px] text-zinc-500 hover:text-zinc-300">Refresh</button>
        </div>
        {agentsList.length === 0 ? (
          <p className="text-xs text-zinc-600">No agents provisioned yet</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {agentsList.map((agent, i) => {
              const a = agent as Record<string, unknown>;
              return (
                <div key={i} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-medium text-white">{String(a.name || a.agent_name || `Agent ${i}`)}</p>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400">{String(a.status || 'active')}</span>
                  </div>
                  <p className="text-[10px] text-zinc-600 mt-1">{String(a.type || a.agent_type || '')} {Array.isArray(a.capabilities) ? `| ${(a.capabilities as string[]).join(', ')}` : ''}</p>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Copilot Draft */}
      <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
        <h3 className="text-sm font-semibold text-white mb-3">Copilot — Draft Response</h3>
        <div className="space-y-2">
          <input
            value={draftTicketId}
            onChange={e => setDraftTicketId(e.target.value)}
            placeholder="Ticket ID"
            className="w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.06] text-xs text-white placeholder-zinc-600 focus:outline-none focus:border-orange-500/30"
          />
          <textarea
            value={draftQuery}
            onChange={e => setDraftQuery(e.target.value)}
            placeholder="Customer query or issue description..."
            rows={3}
            className="w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.06] text-xs text-white placeholder-zinc-600 focus:outline-none focus:border-orange-500/30 resize-none"
          />
          <button
            onClick={() => wave8.copilotDraft(draftTicketId, draftQuery)}
            disabled={wave8.isLoading || !draftQuery}
            className="text-xs px-3 py-1.5 rounded-lg bg-gradient-to-r from-orange-500 to-amber-400 text-white font-medium hover:shadow-lg hover:shadow-orange-500/20 transition-all disabled:opacity-40"
          >
            {wave8.isLoading ? 'Generating...' : 'Generate Draft'}
          </button>
        </div>
        {wave8.copilotResult && (
          <div className="mt-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
            <p className="text-[10px] text-zinc-600 mb-1">Generated Draft:</p>
            <p className="text-xs text-zinc-300 whitespace-pre-wrap">{String((wave8.copilotResult as Record<string, unknown>)?.draft_text || JSON.stringify(wave8.copilotResult))}</p>
          </div>
        )}
      </div>

      {/* Teach Skill */}
      <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
        <h3 className="text-sm font-semibold text-white mb-3">Teach New Skill</h3>
        <div className="space-y-2">
          <input value={teachAgent} onChange={e => setTeachAgent(e.target.value)} placeholder="Agent name" className="w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.06] text-xs text-white placeholder-zinc-600 focus:outline-none focus:border-orange-500/30" />
          <input value={teachSkill} onChange={e => setTeachSkill(e.target.value)} placeholder="Skill name (e.g. refund_policy)" className="w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.06] text-xs text-white placeholder-zinc-600 focus:outline-none focus:border-orange-500/30" />
          <textarea value={teachContent} onChange={e => setTeachContent(e.target.value)} placeholder="Skill content / instructions..." rows={3} className="w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.06] text-xs text-white placeholder-zinc-600 focus:outline-none focus:border-orange-500/30 resize-none" />
          <button onClick={() => { wave8.teach(teachAgent, teachSkill, teachContent).then(() => { toast.success('Skill taught'); setTeachAgent(''); setTeachSkill(''); setTeachContent(''); }).catch(() => toast.error('Failed to teach skill')); }} disabled={wave8.isLoading || !teachAgent || !teachSkill} className="text-xs px-3 py-1.5 rounded-lg bg-orange-500/10 text-orange-400 hover:bg-orange-500/20 transition-colors disabled:opacity-40">
            {wave8.isLoading ? 'Teaching...' : 'Teach Skill'}
          </button>
        </div>
      </div>

      {/* Skills list */}
      {skillsList.length > 0 && (
        <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
          <h3 className="text-sm font-semibold text-white mb-3">Known Skills</h3>
          <div className="flex flex-wrap gap-2">
            {skillsList.map((skill, i) => {
              const s = skill as Record<string, unknown>;
              return (
                <span key={i} className="text-[10px] px-2.5 py-1 rounded-full bg-white/[0.04] text-zinc-400 border border-white/[0.06]">
                  {String(s.name || s.skill_name || `Skill ${i}`)}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Provisioning Logs */}
      <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-white">Provisioning Logs</h3>
          <button onClick={() => wave8.fetchLogs()} className="text-[10px] text-zinc-500 hover:text-zinc-300">Refresh</button>
        </div>
        <div className="max-h-48 overflow-y-auto space-y-1">
          {wave8.logs.data && Array.isArray((wave8.logs.data as Record<string, unknown>)?.logs) ? (
            ((wave8.logs.data as Record<string, unknown>).logs as unknown[]).map((log, i) => {
              const l = log as Record<string, unknown>;
              return (
                <div key={i} className="text-[10px] text-zinc-600 py-1 border-b border-white/[0.03]">
                  <span className="text-zinc-400">{String(l.timestamp || '')}</span> — {String(l.action || l.event || '')}
                </div>
              );
            })
          ) : (
            <p className="text-[10px] text-zinc-600">No logs yet</p>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Audit Tab ─────────────────────────────────────────────────────

function AuditTab() {
  const audit = useJarvisAudit();

  useEffect(() => { audit.fetchAudit(100); }, []);

  const auditData = audit.audit.data as Record<string, unknown> | null;
  const auditList = (auditData?.entries || auditData?.audit || []) as unknown[];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button onClick={() => audit.fetchAudit(100)} className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors">
          Refresh
        </button>
      </div>

      {audit.audit.status === 'loading' ? (
        <div className="space-y-2"><SkeletonCard /><SkeletonCard /><SkeletonCard /></div>
      ) : auditList.length === 0 ? (
        <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-8 text-center">
          <p className="text-sm text-zinc-500">No audit entries</p>
        </div>
      ) : (
        <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden">
          <div className="max-h-[60vh] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-[#1A1A1A] border-b border-white/[0.06]">
                <tr>
                  <th className="text-left px-4 py-2 text-zinc-500 font-medium">Timestamp</th>
                  <th className="text-left px-4 py-2 text-zinc-500 font-medium">Action</th>
                  <th className="text-left px-4 py-2 text-zinc-500 font-medium">Actor</th>
                  <th className="text-left px-4 py-2 text-zinc-500 font-medium">Details</th>
                </tr>
              </thead>
              <tbody>
                {auditList.map((entry, i) => {
                  const e = entry as Record<string, unknown>;
                  return (
                    <tr key={i} className="border-b border-white/[0.03] hover:bg-white/[0.02]">
                      <td className="px-4 py-2 text-zinc-500 whitespace-nowrap">{String(e.timestamp || e.created_at || '')}</td>
                      <td className="px-4 py-2 text-zinc-300 font-medium">{String(e.action || e.type || '')}</td>
                      <td className="px-4 py-2 text-zinc-400">{String(e.actor_email || e.actor || '')}</td>
                      <td className="px-4 py-2 text-zinc-600 max-w-xs truncate">{String(e.target_type || e.details || '')}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Page Component ─────────────────────────────────────────

export default function JarvisCCPage() {
  const [activeTab, setActiveTab] = useState<TabId>('chat');

  // Existing chat/hooks
  const { session, createSession, resumeSession } = useJarvisCCSession();
  const { quickCommands, fetchQuickCommands, executeQuickCommand } = useJarvisCommands(session?.id || null);
  const { isOpen, query, setQuery, open, close } = useCommandPalette();
  const { status: shadowStatus, enableShadowMode, disableShadowMode, promoteShadowMode } = useShadowMode(30000);
  const [showShadowPanel, setShowShadowPanel] = useState(false);

  const handleSendCommand = useCallback(async (rawInput: string) => {
    const event = new CustomEvent('jarvis-command', { detail: rawInput });
    window.dispatchEvent(event);
    close();
  }, [close]);

  const handleExecuteQuick = useCallback(async (id: string) => {
    await executeQuickCommand(id);
    close();
  }, [executeQuickCommand, close]);

  const isShadowActive = shadowStatus?.active ?? false;
  const shadowPhase = shadowStatus?.status || 'disabled';

  const handleShadowQuickAction = useCallback(async (action: string) => {
    switch (action) {
      case 'enable_shadow':
        try { const success = await enableShadowMode({ live_variant: 'mini_parwa', shadow_variant: 'parwa', sample_rate: 1.0 }); if (success) toast.success('Shadow Mode enabled via Jarvis'); } catch { toast.error('Failed to enable Shadow Mode'); }
        break;
      case 'promote_shadow':
        try { const success = await promoteShadowMode(); if (success) toast.success('Shadow Mode promoted via Jarvis'); } catch { toast.error('Failed to promote Shadow Mode'); }
        break;
      case 'disable_shadow':
        try { const success = await disableShadowMode('Disabled via Jarvis CC'); if (success) toast.success('Shadow Mode disabled via Jarvis'); } catch { toast.error('Failed to disable Shadow Mode'); }
        break;
      case 'view_shadow_mode':
        window.open('/dashboard/shadow-mode', '_self');
        break;
    }
  }, [enableShadowMode, promoteShadowMode, disableShadowMode]);

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col">
      {/* Tab Bar */}
      <div className="flex items-center gap-1 mb-3 overflow-x-auto scrollbar-none pb-1">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200 whitespace-nowrap',
              activeTab === tab.id
                ? 'bg-orange-500/10 text-orange-400 border border-orange-500/20 shadow-sm shadow-orange-500/5'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04] border border-transparent'
            )}
          >
            {tab.label}
            {tab.id === 'approvals' && <PendingDot />}
          </button>
        ))}

        {/* Shadow Mode toggle (always visible) */}
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setShowShadowPanel(!showShadowPanel)}
            className={cn(
              'flex items-center gap-1.5 text-[10px] px-2.5 py-1.5 rounded-lg transition-colors',
              isShadowActive ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' : 'bg-white/[0.04] text-zinc-500 border border-white/[0.06] hover:text-zinc-300'
            )}
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09Z" />
            </svg>
            <span className="font-medium">{isShadowActive ? `Shadow: ${shadowPhase.toUpperCase()}` : 'Shadow'}</span>
            {isShadowActive && <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />}
          </button>
          <Link href="/dashboard/shadow-mode" className="text-[10px] text-zinc-600 hover:text-zinc-400 transition-colors">
            Dashboard
          </Link>
        </div>
      </div>

      {/* Shadow Mode Panel */}
      {showShadowPanel && (
        <div className="mb-3 rounded-xl border border-purple-500/20 bg-purple-500/5 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-semibold text-purple-400">Shadow Mode Status</h3>
            <button onClick={() => setShowShadowPanel(false)} className="text-zinc-500 hover:text-zinc-300 transition-colors">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          {isShadowActive && shadowStatus ? (
            <div className="flex items-center gap-3 flex-wrap">
              <button onClick={() => handleShadowQuickAction('promote_shadow')} className="text-[10px] px-2.5 py-1 rounded bg-amber-500/10 text-amber-400 hover:bg-amber-500/20">Promote</button>
              <button onClick={() => handleShadowQuickAction('disable_shadow')} className="text-[10px] px-2.5 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20">Disable</button>
              <span className="text-[10px] text-zinc-600 ml-auto">Win Rate: {Math.round(shadowStatus.shadow_win_rate * 100)}%</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button onClick={() => handleShadowQuickAction('enable_shadow')} className="text-[10px] px-2.5 py-1 rounded bg-purple-500/10 text-purple-400 hover:bg-purple-500/20">Enable Shadow Mode</button>
              <p className="text-[10px] text-zinc-600">Test new variants safely alongside your live variant.</p>
            </div>
          )}
        </div>
      )}

      {/* Tab Content */}
      <div className="flex-1 min-h-0 overflow-y-auto scrollbar-premium">
        {activeTab === 'chat' && <ChatContent />}
        {activeTab === 'quality' && <QualityTab />}
        {activeTab === 'sla' && <SlaTab />}
        {activeTab === 'approvals' && <ApprovalsTab />}
        {activeTab === 'notifications' && <NotificationsTab />}
        {activeTab === 'wave8' && <Wave8Tab />}
        {activeTab === 'audit' && <AuditTab />}
      </div>

      {/* Command Palette (always available) */}
      <JarvisCommandPalette
        isOpen={isOpen}
        query={query}
        onQueryChange={setQuery}
        onClose={close}
        quickCommands={quickCommands}
        onExecuteQuick={handleExecuteQuick}
        onSendCommand={handleSendCommand}
      />
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────

function PendingDot() {
  return <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />;
}

function ChatContent() {
  const { session, createSession, resumeSession } = useJarvisCCSession();
  const { quickCommands, fetchQuickCommands, executeQuickCommand } = useJarvisCommands(session?.id || null);
  const { isOpen, query, setQuery, open, close } = useCommandPalette();

  const handleSendCommand = useCallback(async (rawInput: string) => {
    const event = new CustomEvent('jarvis-command', { detail: rawInput });
    window.dispatchEvent(event);
    close();
  }, [close]);

  const handleExecuteQuick = useCallback(async (id: string) => {
    await executeQuickCommand(id);
    close();
  }, [executeQuickCommand, close]);

  return (
    <>
      <div className="flex-1 min-h-0">
        <JarvisCCChat />
      </div>
    </>
  );
}
