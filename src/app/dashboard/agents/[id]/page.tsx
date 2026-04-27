'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  agentsApi,
  type Agent,
  type AgentCardData,
  type AgentMetrics,
  type AgentMistake,
} from '@/lib/agents-api';
import { ticketsApi } from '@/lib/tickets-api';
import { getErrorMessage } from '@/lib/api';
import { useSocket } from '@/contexts/SocketContext';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import ConfidenceTrend from '@/components/dashboard/ConfidenceTrend';
import AdaptationTracker from '@/components/dashboard/AdaptationTracker';

// ── Helpers ────────────────────────────────────────────────────────────

function formatSpecialty(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function statusBadgeStyle(status: string): string {
  const map: Record<string, string> = {
    active: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    paused: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    error: 'bg-red-500/10 text-red-400 border-red-500/20',
    initializing: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    training: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
    deprovisioned: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
  };
  return map[status] || 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20';
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '\u2014';
  return new Date(dateStr).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '\u2014';
  const d = new Date(dateStr);
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return '\u2014';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function confidenceColor(c: number): string {
  if (c >= 75) return 'text-emerald-400';
  if (c >= 50) return 'text-amber-400';
  return 'text-red-400';
}

function channelIcon(channel: string): string {
  const map: Record<string, string> = { email: 'E', chat: 'C', sms: 'S', voice: 'V', slack: 'Sl' };
  return map[channel] || channel.charAt(0).toUpperCase();
}

// ── Inline SVG Icons ──────────────────────────────────────────────────

const ArrowLeftIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
  </svg>
);

const BotIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
  </svg>
);

const ActivityIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
  </svg>
);

const SettingsIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
  </svg>
);

const TrainIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5" />
  </svg>
);

const TicketIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 0 1 0 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 0 1 0-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375Z" />
  </svg>
);

// ── KPI Card Component (A7) ───────────────────────────────────────────

function KpiCard({ label, value, sublabel, icon, variant }: {
  label: string;
  value: string | number;
  sublabel?: string;
  icon: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger';
}) {
  const variantStyles = {
    default: 'border-white/[0.06]',
    success: 'border-emerald-500/20 bg-emerald-500/[0.03]',
    warning: 'border-amber-500/20 bg-amber-500/[0.03]',
    danger: 'border-red-500/20 bg-red-500/[0.03]',
  };
  return (
    <div className={`rounded-lg border p-3 space-y-1 ${variantStyles[variant || 'default']}`}>
      <div className="flex items-center gap-2">
        <span className="text-zinc-500">{icon}</span>
        <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-lg font-bold text-zinc-100">{value}</p>
      {sublabel && <p className="text-[10px] text-zinc-500">{sublabel}</p>}
    </div>
  );
}

// ── Live Activity Panel (A8) ───────────────────────────────────────────

interface LiveActivity {
  ticket_id: string;
  ticket_subject: string | null;
  customer: string | null;
  channel: string;
  confidence: number | null;
  time_spent: number;
  status: string;
}

function LiveActivityPanel({
  agentId,
  isConnected,
}: {
  agentId: string;
  isConnected: boolean;
}) {
  const [activity, setActivity] = useState<LiveActivity | null>(null);
  const { socket } = useSocket();

  useEffect(() => {
    if (!socket || !isConnected) return;

    const handler = (data: any) => {
      if (data.agent_id === agentId) {
        setActivity({
          ticket_id: data.ticket_id || '',
          ticket_subject: data.ticket_subject || null,
          customer: data.customer || null,
          channel: data.channel || 'chat',
          confidence: data.confidence ?? null,
          time_spent: data.time_spent ?? 0,
          status: data.status || 'in_progress',
        });
      }
    };

    socket.on('agent:status_changed', handler);
    return () => {
      socket.off('agent:status_changed', handler);
    };
  }, [socket, isConnected, agentId]);

  return (
    <div className="bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-[#FF7F11]/10 flex items-center justify-center">
            <ActivityIcon />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">Live Activity</h3>
            <p className="text-[10px] text-zinc-500">Real-time agent status</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-600'}`} />
          <span className="text-[10px] text-zinc-500">{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>
      <div className="p-4">
        {activity ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Badge variant="outline" className="text-[10px] bg-blue-500/10 text-blue-400 border-blue-500/20">
                Handling Ticket
              </Badge>
              <span className="text-[10px] text-zinc-500">Time: {formatDuration(activity.time_spent)}</span>
            </div>
            <div>
              <Link
                href={`/dashboard/tickets/${activity.ticket_id}`}
                className="text-sm font-medium text-[#FF7F11] hover:underline"
              >
                #{activity.ticket_id.slice(0, 8)}
              </Link>
              {activity.ticket_subject && (
                <p className="text-xs text-zinc-400 mt-0.5">{activity.ticket_subject}</p>
              )}
            </div>
            <div className="flex items-center gap-4 text-xs text-zinc-500">
              {activity.customer && <span>Customer: {activity.customer}</span>}
              <span className="capitalize">{activity.channel}</span>
              {activity.confidence !== null && (
                <span className={confidenceColor(activity.confidence)}>
                  Confidence: {activity.confidence}%
                </span>
              )}
            </div>
          </div>
        ) : (
          <div className="text-center py-6">
            <div className="w-10 h-10 rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mx-auto mb-2">
              <ActivityIcon />
            </div>
            <p className="text-xs text-zinc-500">No active ticket being handled</p>
            <p className="text-[10px] text-zinc-600 mt-0.5">
              {isConnected ? 'Waiting for agent updates…' : 'Connect to see live updates'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Mistake Log (A11) ──────────────────────────────────────────────────

function MistakeLog({ agentId }: { agentId: string }) {
  const [mistakes, setMistakes] = useState<AgentMistake[]>([]);
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);

  useEffect(() => {
    const fn = async () => {
      setLoading(true);
      try {
        // Fetch from agent metrics or tickets endpoint
        const metrics = await agentsApi.getAgentMetrics(agentId).catch(() => null);
        // For demo, use empty array if no endpoint
        setMistakes((metrics as any)?.recent_mistakes || []);
      } catch {
        setMistakes([]);
      } finally {
        setLoading(false);
      }
    };
    fn();
  }, [agentId]);

  const handleTrainFromErrors = async () => {
    setTraining(true);
    try {
      // TODO(placeholder): This is a stub retraining flow.
      // Pauses the agent, simulates retraining, then resumes.
      // Replace with actual retraining API when available.
      await agentsApi.pauseAgent(agentId);
      // Simulate retraining trigger
      await new Promise(r => setTimeout(r, 1500));
      await agentsApi.resumeAgent(agentId);
    } catch {
      // Silent fail
    } finally {
      setTraining(false);
    }
  };

  return (
    <div className="bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-red-500/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">Mistake Log</h3>
            <p className="text-[10px] text-zinc-500">Recent errors and corrections</p>
          </div>
        </div>
        <Button
          size="sm"
          variant="ghost"
          disabled={training || mistakes.length === 0}
          onClick={handleTrainFromErrors}
          className="text-xs h-7 text-red-400 hover:bg-red-500/10 hover:text-red-300"
        >
          <TrainIcon />
          {training ? 'Retraining...' : 'Train from Errors'}
        </Button>
      </div>
      <div className="max-h-64 overflow-y-auto">
        {loading ? (
          <div className="p-4 space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full rounded-lg bg-white/[0.04]" />
            ))}
          </div>
        ) : mistakes.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-xs text-zinc-500">No recent mistakes recorded</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/[0.04]">
                <th className="px-4 py-2 text-left text-[10px] font-medium text-zinc-500 uppercase">Time</th>
                <th className="px-4 py-2 text-left text-[10px] font-medium text-zinc-500 uppercase">Ticket</th>
                <th className="px-4 py-2 text-left text-[10px] font-medium text-zinc-500 uppercase">Type</th>
                <th className="px-4 py-2 text-left text-[10px] font-medium text-zinc-500 uppercase">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {mistakes.map(m => (
                <tr key={m.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-4 py-2.5 text-xs text-zinc-500">{formatDateTime(m.timestamp)}</td>
                  <td className="px-4 py-2.5">
                    <Link href={`/dashboard/tickets/${m.ticket_id}`} className="text-xs text-[#FF7F11] hover:underline">
                      #{m.ticket_id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge variant="outline" className="text-[10px] bg-red-500/10 text-red-400 border-red-500/20">
                      {m.error_type}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-zinc-400 max-w-[200px] truncate">{m.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ── Agent Config Panel (A12) ───────────────────────────────────────────

function AgentConfigPanel({ agent, onRefresh }: { agent: Agent; onRefresh: () => void }) {
  const [editOpen, setEditOpen] = useState(false);
  const [name, setName] = useState(agent.name);
  const [description, setDescription] = useState(agent.description || '');
  const [specialty, setSpecialty] = useState(agent.specialty);
  const [saving, setSaving] = useState(false);

  const activeChannels = Object.entries(agent.channels || {})
    .filter(([, v]) => v === true || v === 1)
    .map(([k]) => k);

  const permissionLevel = (agent.permissions as any)?.level || 'standard';
  const requiresApproval = (agent.permissions as any)?.requires_approval || false;

  const handleSave = async () => {
    setSaving(true);
    try {
      // TODO(placeholder): Replace with actual backend PUT endpoint when available.
      // Currently simulates a save with a delay.
      console.warn('handleSave is a stub — backend PUT /api/agents/:id not yet implemented');
      await new Promise(r => setTimeout(r, 800));
      onRefresh();
      setEditOpen(false);
    } catch {
      // Silent fail
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-violet-500/10 flex items-center justify-center">
              <SettingsIcon />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-zinc-200">Configuration</h3>
              <p className="text-[10px] text-zinc-500">Agent settings and permissions</p>
            </div>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setEditOpen(true)}
            className="text-xs h-7 text-zinc-400 hover:text-[#FF7F11] hover:bg-[#FF7F11]/10"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
            </svg>
            Edit
          </Button>
        </div>
        <div className="p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Name</p>
              <p className="text-sm text-zinc-200">{agent.name}</p>
            </div>
            <div>
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Specialty</p>
              <Badge variant="outline" className="text-[10px] bg-violet-500/10 text-violet-400 border-violet-500/20">
                {formatSpecialty(agent.specialty)}
              </Badge>
            </div>
          </div>
          <div>
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Description</p>
            <p className="text-xs text-zinc-400">{agent.description || 'No description set'}</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Base Model</p>
              <p className="text-xs text-zinc-300">{agent.base_model || 'Default'}</p>
            </div>
            <div>
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Permission Level</p>
              <p className="text-xs text-zinc-300 capitalize">{permissionLevel}</p>
            </div>
          </div>
          <div>
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Channels</p>
            <div className="flex gap-1.5">
              {activeChannels.length > 0 ? activeChannels.map(ch => (
                <span key={ch} className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                  {channelIcon(ch)} {ch}
                </span>
              )) : <span className="text-xs text-zinc-600">No channels configured</span>}
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs text-zinc-500">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-zinc-500 uppercase">Requires Approval:</span>
              <span className={requiresApproval ? 'text-amber-400' : 'text-zinc-600'}>
                {requiresApproval ? 'Yes' : 'No'}
              </span>
            </div>
            <span className="text-zinc-700">|</span>
            <span>Created: {formatDate(agent.created_at)}</span>
            <span className="text-zinc-700">|</span>
            <span>Activated: {formatDate(agent.activated_at)}</span>
          </div>
        </div>
      </div>

      {/* Edit Config Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="bg-[#1A1A1A] border-white/[0.06] max-w-md">
          <DialogHeader>
            <DialogTitle className="text-zinc-200">Edit Agent Configuration</DialogTitle>
            <DialogDescription className="text-zinc-500">
              Update agent settings. Some changes may require retraining.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs text-zinc-400">Agent Name</Label>
              <Input
                value={name}
                onChange={e => setName(e.target.value)}
                className="bg-[#0F0F0F] border-white/[0.06] text-zinc-200 text-sm focus-visible:border-[#FF7F11]/50"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-zinc-400">Specialty</Label>
              <Select value={specialty} onValueChange={setSpecialty}>
                <SelectTrigger className="bg-[#0F0F0F] border-white/[0.06] text-zinc-200 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#1A1A1A] border-white/[0.06]">
                  {[
                    'billing_specialist', 'returns_specialist', 'technical_support',
                    'general_support', 'sales_assistant', 'onboarding_guide',
                    'vip_concierge', 'feedback_collector', 'custom',
                  ].map(v => (
                    <SelectItem key={v} value={v} className="text-zinc-300">
                      {formatSpecialty(v)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-zinc-400">Description</Label>
              <Textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                rows={3}
                className="bg-[#0F0F0F] border-white/[0.06] text-zinc-200 text-sm focus-visible:border-[#FF7F11]/50 resize-none"
              />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-xs text-zinc-400">Requires Human Approval</Label>
              <Switch checked={requiresApproval} disabled />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditOpen(false)} className="text-zinc-400 text-xs">
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={saving || !name.trim()}
              className="bg-[#FF7F11] text-white hover:bg-[#FF7F11]/90 text-xs"
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ── Main Agent Detail Page ─────────────────────────────────────────────

export default function AgentDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const { isConnected } = useSocket();

  const [agent, setAgent] = useState<Agent | null>(null);
  const [cardData, setCardData] = useState<AgentCardData | null>(null);
  const [metrics, setMetrics] = useState<AgentMetrics | null>(null);
  const [tickets, setTickets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── Fetch Data ───────────────────────────────────────────────────

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [agentData, cardRes, metricsRes] = await Promise.all([
        agentsApi.getAgent(id).catch(() => null),
        agentsApi.getAgentCardDetail(id).catch(() => null),
        agentsApi.getAgentMetrics(id).catch(() => null),
      ]);

      if (!agentData) {
        setError('Agent not found');
        setLoading(false);
        return;
      }

      setAgent(agentData);
      setCardData(cardRes);
      setMetrics(metricsRes);

      // Fetch tickets assigned to this agent
      try {
        const ticketsRes = await ticketsApi.list({
          assigned_to: id,
          page_size: 20,
        });
        setTickets(ticketsRes.items || []);
      } catch {
        setTickets([]);
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    const fn = async () => { await fetchData(); };
    fn();
  }, [fetchData]);

  // ── Loading State ────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0F0F0F] p-4 md:p-6">
        <div className="flex items-center gap-3 mb-6">
          <Skeleton className="h-8 w-8 rounded" />
          <Skeleton className="h-6 w-48" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl bg-white/[0.04]" />
          ))}
        </div>
        <Skeleton className="h-64 rounded-xl bg-white/[0.04]" />
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="min-h-screen bg-[#0F0F0F] p-4 md:p-6">
        <Link href="/dashboard/agents" className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-300 mb-6 transition-colors">
          <ArrowLeftIcon /> Back to Agents
        </Link>
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="w-16 h-16 rounded-2xl bg-red-500/10 flex items-center justify-center">
            <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
            </svg>
          </div>
          <p className="text-sm text-red-400">{error || 'Agent not found'}</p>
          <Link href="/dashboard/agents" className="text-sm text-[#FF7F11] hover:underline">
            Return to agents list
          </Link>
        </div>
      </div>
    );
  }

  // ── Computed ─────────────────────────────────────────────────────

  const m = metrics || {
    tickets_handled_7d: 0,
    resolution_rate_7d: 0,
    csat_avg_7d: 0,
    avg_response_time_7d: 0,
    confidence_avg_7d: 0,
    mistakes_7d: 0,
  };

  return (
    <div className="min-h-screen bg-[#0F0F0F]">
      {/* Header */}
      <div className="border-b border-white/[0.04] bg-[#0F0F0F]/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-screen-2xl mx-auto px-4 md:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/dashboard/agents" className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-300 transition-colors">
              <ArrowLeftIcon /> Agents
            </Link>
            <Separator orientation="vertical" className="h-4 bg-white/[0.06]" />
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-[#FF7F11]/10 flex items-center justify-center">
                <BotIcon />
              </div>
              <span className="text-sm font-semibold text-zinc-200">{agent.name}</span>
              <Badge variant="outline" className={`text-[10px] ${statusBadgeStyle(agent.status)}`}>
                {agent.status}
              </Badge>
              <Badge variant="outline" className="text-[10px] bg-violet-500/10 text-violet-400 border-violet-500/20">
                {formatSpecialty(agent.specialty)}
              </Badge>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-screen-2xl mx-auto px-4 md:px-6 py-5 space-y-5">
        {/* KPI Cards (A7) */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <KpiCard
            label="Tickets (7d)"
            value={m.tickets_handled_7d}
            icon={<TicketIcon />}
          />
          <KpiCard
            label="Resolution Rate"
            value={`${(m.resolution_rate_7d * 100).toFixed(1)}%`}
            variant={m.resolution_rate_7d >= 0.8 ? 'success' : m.resolution_rate_7d >= 0.6 ? 'warning' : 'danger'}
            icon={<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" /></svg>}
          />
          <KpiCard
            label="CSAT Avg"
            value={`${m.csat_avg_7d.toFixed(1)}/5`}
            variant={m.csat_avg_7d >= 4 ? 'success' : m.csat_avg_7d >= 3 ? 'default' : 'warning'}
            icon={<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" /></svg>}
          />
          <KpiCard
            label="Avg Response"
            value={m.avg_response_time_7d > 0 ? formatDuration(m.avg_response_time_7d) : '\u2014'}
            icon={<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" /></svg>}
          />
          <KpiCard
            label="Confidence"
            value={`${(m.confidence_avg_7d * 100).toFixed(1)}%`}
            variant={m.confidence_avg_7d >= 0.75 ? 'success' : m.confidence_avg_7d >= 0.5 ? 'warning' : 'danger'}
            icon={<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" /></svg>}
          />
          <KpiCard
            label="Mistakes"
            value={m.mistakes_7d}
            variant={m.mistakes_7d > 5 ? 'danger' : m.mistakes_7d > 2 ? 'warning' : 'default'}
            icon={<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" /></svg>}
          />
        </div>

        {/* Main Content: Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Left Column: Charts, Conversations, Tickets */}
          <div className="lg:col-span-2 space-y-5">
            {/* Performance Charts (A10) */}
            <div className="space-y-5">
              <ConfidenceTrend className="w-full" />
              <AdaptationTracker className="w-full" />
            </div>

            {/* Tabs: Conversations + Tickets */}
            <Tabs defaultValue="conversations">
              <TabsList className="bg-[#1A1A1A] border border-white/[0.06] p-1 h-9">
                <TabsTrigger value="conversations" className="text-xs flex-1 data-[state=active]:bg-[#FF7F11]/10 data-[state=active]:text-[#FF7F11]">
                  Conversations
                </TabsTrigger>
                <TabsTrigger value="tickets" className="text-xs flex-1 data-[state=active]:bg-[#FF7F11]/10 data-[state=active]:text-[#FF7F11]">
                  Tickets ({tickets.length})
                </TabsTrigger>
              </TabsList>

              {/* Conversation Records (A9) */}
              <TabsContent value="conversations" className="mt-4">
                <div className="bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden">
                  {tickets.length === 0 ? (
                    <div className="text-center py-12">
                      <p className="text-sm text-zinc-500">No conversations handled by this agent yet</p>
                    </div>
                  ) : (
                    <div className="max-h-96 overflow-y-auto">
                      <table className="w-full">
                        <thead className="sticky top-0 bg-[#1A1A1A]">
                          <tr className="border-b border-white/[0.04]">
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-500 uppercase">Ticket</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-500 uppercase">Customer</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-500 uppercase">Channel</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-500 uppercase">Status</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-500 uppercase">Confidence</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-500 uppercase">Duration</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-500 uppercase">Created</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.04]">
                          {tickets.map(t => (
                            <tr key={t.id} className="hover:bg-white/[0.02] transition-colors">
                              <td className="px-4 py-2.5">
                                <Link href={`/dashboard/tickets/${t.id}`} className="text-xs text-[#FF7F11] hover:underline">
                                  #{t.id.slice(0, 8)}
                                </Link>
                              </td>
                              <td className="px-4 py-2.5 text-xs text-zinc-400">
                                {(t as any).customer_name || '\u2014'}
                              </td>
                              <td className="px-4 py-2.5">
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 capitalize">
                                  {t.channel || '\u2014'}
                                </span>
                              </td>
                              <td className="px-4 py-2.5">
                                <Badge variant="outline" className={`text-[10px] ${statusBadgeStyle(t.status)}`}>
                                  {t.status.replace(/_/g, ' ')}
                                </Badge>
                              </td>
                              <td className="px-4 py-2.5 text-xs text-zinc-400">
                                {(t as any).ai_confidence != null
                                  ? <span className={confidenceColor((t as any).ai_confidence)}>{(t as any).ai_confidence}%</span>
                                  : '\u2014'}
                              </td>
                              <td className="px-4 py-2.5 text-xs text-zinc-500">
                                {formatDuration((t as any).resolution_time_seconds)}
                              </td>
                              <td className="px-4 py-2.5 text-xs text-zinc-500">
                                {formatDateTime(t.created_at)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </TabsContent>

              {/* Agent Ticket List (A13) */}
              <TabsContent value="tickets" className="mt-4">
                <div className="bg-[#1A1A1A] border border-white/[0.06] rounded-xl overflow-hidden">
                  {tickets.length === 0 ? (
                    <div className="text-center py-12">
                      <p className="text-sm text-zinc-500">No tickets assigned to this agent</p>
                    </div>
                  ) : (
                    <div className="max-h-96 overflow-y-auto">
                      <table className="w-full">
                        <thead className="sticky top-0 bg-[#1A1A1A]">
                          <tr className="border-b border-white/[0.04]">
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-500 uppercase">Ticket</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-500 uppercase">Subject</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-500 uppercase">Priority</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-500 uppercase">Status</th>
                            <th className="px-4 py-2.5 text-left text-[10px] font-medium text-zinc-500 uppercase">Created</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.04]">
                          {tickets.map(t => (
                            <tr key={t.id} className="hover:bg-white/[0.02] transition-colors">
                              <td className="px-4 py-2.5">
                                <Link href={`/dashboard/tickets/${t.id}`} className="text-xs text-[#FF7F11] hover:underline">
                                  #{t.id.slice(0, 8)}
                                </Link>
                              </td>
                              <td className="px-4 py-2.5 text-xs text-zinc-300 max-w-[200px] truncate">
                                {t.subject || '\u2014'}
                              </td>
                              <td className="px-4 py-2.5">
                                <Badge variant="outline" className={`text-[10px] uppercase ${
                                  t.priority === 'critical' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                                  t.priority === 'high' ? 'bg-orange-500/10 text-orange-400 border-orange-500/20' :
                                  t.priority === 'medium' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                                  'bg-zinc-600/10 text-zinc-400 border-zinc-600/20'
                                }`}>
                                  {t.priority}
                                </Badge>
                              </td>
                              <td className="px-4 py-2.5">
                                <Badge variant="outline" className={`text-[10px] ${statusBadgeStyle(t.status)}`}>
                                  {t.status.replace(/_/g, ' ')}
                                </Badge>
                              </td>
                              <td className="px-4 py-2.5 text-xs text-zinc-500">
                                {formatDateTime(t.created_at)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          </div>

          {/* Right Column: Live Activity, Config, Mistakes */}
          <div className="space-y-5">
            {/* Live Activity (A8) */}
            <LiveActivityPanel agentId={id} isConnected={isConnected} />

            {/* Agent Configuration (A12) */}
            <AgentConfigPanel agent={agent} onRefresh={fetchData} />

            {/* Mistake Log (A11) */}
            <MistakeLog agentId={id} />
          </div>
        </div>
      </div>
    </div>
  );
}
