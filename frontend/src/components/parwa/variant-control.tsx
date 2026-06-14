'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';
import {
  Zap, Pause, Play, OctagonX, Loader2, Activity, AlertTriangle,
  CheckCircle2, XCircle, RotateCcw, StickyNote, ThumbsUp, ThumbsDown,
  Shield, Crown, Rocket, RefreshCw, Clock, Bot,
} from 'lucide-react';
import {
  getVariantStatus, pauseVariant, resumeVariant, pauseAllVariants,
  emergencyStop as emergencyStopApi, resumeAllVariants, getVariantActivity,
  getPendingApprovals, approveAction, denyAction, undoAction, addNoteToAction,
  type VariantStatusResponse, type ActivityEntry, type VariantType,
} from '@/lib/api';
import { toast } from 'sonner';

interface VariantControlProps {
  activeVariants: VariantType[];
}

const variantIcons: Record<string, React.ElementType> = {
  mini: Zap,
  parwa: Rocket,
  high: Crown,
};

const variantLabels: Record<string, string> = {
  mini: 'PARWA Mini',
  parwa: 'PARWA Standard',
  high: 'PARWA High',
};

function variantStatusColor(status: string): string {
  switch (status) {
    case 'active': return 'bg-emerald-500';
    case 'paused': return 'bg-amber-500';
    case 'stopped': return 'bg-red-500';
    default: return 'bg-slate-400';
  }
}

function variantStatusBg(status: string): string {
  switch (status) {
    case 'active': return 'border-emerald-200 bg-gradient-to-br from-emerald-50 to-white';
    case 'paused': return 'border-amber-200 bg-gradient-to-br from-amber-50 to-white';
    case 'stopped': return 'border-red-200 bg-gradient-to-br from-red-50 to-white';
    default: return '';
  }
}

function actionStatusBadge(status: string): string {
  switch (status) {
    case 'executed': return 'bg-[#0A3D2E]/10 text-[#0A3D2E]';
    case 'pending': return 'bg-amber-100 text-amber-800';
    case 'undone': return 'bg-slate-100 text-slate-600';
    case 'denied': return 'bg-red-100 text-red-800';
    default: return 'bg-slate-100 text-slate-600';
  }
}

export default function VariantControl({ activeVariants }: VariantControlProps) {
  const [status, setStatus] = useState<VariantStatusResponse | null>(null);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Emergency stop confirmation
  const [emergencyDialogOpen, setEmergencyDialogOpen] = useState(false);
  const [emergencyLoading, setEmergencyLoading] = useState(false);

  // Activity filter
  const [activityVariant, setActivityVariant] = useState<string>('all');
  const [activityStatus, setActivityStatus] = useState<string>('all');

  // Note dialog
  const [noteActionId, setNoteActionId] = useState<string | null>(null);
  const [noteText, setNoteText] = useState('');
  const [noteLoading, setNoteLoading] = useState(false);

  // Load data
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [statusRes, activityRes] = await Promise.all([
          getVariantStatus(),
          getVariantActivity('all', { per_page: 50 }),
        ]);
        if (!cancelled) {
          setStatus(statusRes);
          setActivity(activityRes.entries);
        }
      } catch {
        // fallback data from api.ts
      }
      if (!cancelled) setLoading(false);
    }
    load();
    return () => { cancelled = true; };
  }, []);

  // Manual reload function (called from button clicks)
  const loadData = useCallback(async () => {
    try {
      const [statusRes, activityRes] = await Promise.all([
        getVariantStatus(),
        getVariantActivity('all', { per_page: 50 }),
      ]);
      setStatus(statusRes);
      setActivity(activityRes.entries);
    } catch {
      // fallback data from api.ts
    }
    setLoading(false);
  }, []);

  // Reload activity with filters
  useEffect(() => {
    if (loading) return;
    let cancelled = false;
    async function load() {
      try {
        const params: Record<string, string | number> = { per_page: 50 };
        if (activityStatus !== 'all') params.status = activityStatus;
        const res = await getVariantActivity(activityVariant, params);
        if (!cancelled) setActivity(res.entries);
      } catch {
        // fallback
      }
    }
    load();
    return () => { cancelled = true; };
  }, [activityVariant, activityStatus, loading]);

  // Actions
  const handlePause = async (variantId: string) => {
    setActionLoading(variantId);
    try {
      await pauseVariant(variantId);
      toast.success(`${variantLabels[variantId]} paused`);
      loadData();
    } catch {
      toast.error('Failed to pause variant');
    }
    setActionLoading(null);
  };

  const handleResume = async (variantId: string) => {
    setActionLoading(variantId);
    try {
      await resumeVariant(variantId);
      toast.success(`${variantLabels[variantId]} resumed`);
      loadData();
    } catch {
      toast.error('Failed to resume variant');
    }
    setActionLoading(null);
  };

  const handlePauseAll = async () => {
    setActionLoading('all');
    try {
      await pauseAllVariants();
      toast.success('All variants paused');
      loadData();
    } catch {
      toast.error('Failed to pause all variants');
    }
    setActionLoading(null);
  };

  const handleResumeAll = async () => {
    setActionLoading('all');
    try {
      await resumeAllVariants();
      toast.success('All variants resumed');
      loadData();
    } catch {
      toast.error('Failed to resume all variants');
    }
    setActionLoading(null);
  };

  const handleEmergencyStop = async () => {
    setEmergencyLoading(true);
    try {
      await emergencyStopApi();
      toast.error('EMERGENCY STOP activated — all AI halted');
      loadData();
    } catch {
      toast.error('Failed to activate emergency stop');
    }
    setEmergencyLoading(false);
    setEmergencyDialogOpen(false);
  };

  const handleApprove = async (actionId: string) => {
    try {
      await approveAction(actionId);
      toast.success('Action approved');
      loadData();
    } catch {
      toast.error('Failed to approve');
    }
  };

  const handleDeny = async (actionId: string) => {
    try {
      await denyAction(actionId);
      toast.success('Action denied');
      loadData();
    } catch {
      toast.error('Failed to deny');
    }
  };

  const handleUndo = async (actionId: string) => {
    try {
      await undoAction(actionId);
      toast.success('Action undone');
      loadData();
    } catch {
      toast.error('Failed to undo');
    }
  };

  const handleAddNote = async () => {
    if (!noteActionId || !noteText.trim()) return;
    setNoteLoading(true);
    try {
      await addNoteToAction(noteActionId, noteText.trim());
      toast.success('Note added');
      setNoteActionId(null);
      setNoteText('');
      loadData();
    } catch {
      toast.error('Failed to add note');
    }
    setNoteLoading(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Variant Control</h2>
          <p className="text-muted-foreground">Monitor, pause, resume, and manage AI variants in real-time.</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={loadData}
          className="border-[#0A3D2E]/30 hover:bg-[#0A3D2E]/5"
        >
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
          Refresh
        </Button>
      </div>

      {/* Emergency Stop Banner */}
      {status?.emergency_stop && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="p-4 rounded-xl bg-red-50 border-2 border-red-300"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <motion.div
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              >
                <OctagonX className="h-6 w-6 text-red-600" />
              </motion.div>
              <div>
                <p className="font-bold text-red-800">EMERGENCY STOP ACTIVE</p>
                <p className="text-sm text-red-700">All AI processing halted. New tickets route to human agents.</p>
              </div>
            </div>
            <Button
              onClick={handleResumeAll}
              disabled={actionLoading !== null}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              <Play className="h-4 w-4 mr-1.5" />
              Resume All
            </Button>
          </div>
        </motion.div>
      )}

      {/* Control Buttons */}
      <div className="flex flex-wrap gap-3">
        <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
          <Button
            onClick={() => setEmergencyDialogOpen(true)}
            className="bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-200"
            disabled={status?.emergency_stop}
          >
            <OctagonX className="h-4 w-4 mr-1.5" />
            EMERGENCY STOP
          </Button>
        </motion.div>
        <Button
          variant="outline"
          onClick={handlePauseAll}
          disabled={status?.paused_all || status?.emergency_stop || actionLoading !== null}
          className="border-amber-300 text-amber-700 hover:bg-amber-50"
        >
          {actionLoading === 'all' ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : <Pause className="h-4 w-4 mr-1.5" />}
          Pause All
        </Button>
        <Button
          variant="outline"
          onClick={handleResumeAll}
          disabled={!status?.paused_all || status?.emergency_stop || actionLoading !== null}
          className="border-emerald-300 text-emerald-700 hover:bg-emerald-50"
        >
          <Play className="h-4 w-4 mr-1.5" />
          Resume All
        </Button>
      </div>

      {/* Variant Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {loading ? (
          [1, 2, 3].map(i => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-40 w-full" />
              </CardContent>
            </Card>
          ))
        ) : status ? (
          status.variants.map((v) => {
            const Icon = variantIcons[v.variant] || Zap;
            const isActive = v.status === 'active';
            const isPaused = v.status === 'paused';
            const isStopped = v.status === 'stopped';
            const usagePct = v.tickets_limit > 0 ? Math.round((v.tickets_used / v.tickets_limit) * 100) : 0;

            return (
              <motion.div
                key={v.variant}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <Card className={`border-2 ${variantStatusBg(v.status)} overflow-hidden`}>
                  <CardContent className="p-5">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2.5">
                        <div className={`p-2 rounded-xl ${
                          isActive ? 'bg-[#0A3D2E]' :
                          isPaused ? 'bg-amber-500' :
                          'bg-red-500'
                        }`}>
                          <Icon className="h-5 w-5 text-white" />
                        </div>
                        <div>
                          <p className="font-semibold">{variantLabels[v.variant]}</p>
                          <div className="flex items-center gap-1.5">
                            <div className={`w-2 h-2 rounded-full ${variantStatusColor(v.status)} ${
                              isStopped ? 'animate-pulse' : ''
                            }`} />
                            <span className={`text-xs capitalize font-medium ${
                              isActive ? 'text-emerald-700' :
                              isPaused ? 'text-amber-700' :
                              'text-red-700'
                            }`}>
                              {v.status}
                            </span>
                          </div>
                        </div>
                      </div>
                      {/* Pause/Resume Button */}
                      {isActive ? (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 text-xs border-amber-300 text-amber-700 hover:bg-amber-50"
                          onClick={() => handlePause(v.variant)}
                          disabled={actionLoading !== null || status.emergency_stop}
                        >
                          {actionLoading === v.variant ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Pause className="h-3 w-3 mr-1" />}
                          Pause
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 text-xs border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                          onClick={() => handleResume(v.variant)}
                          disabled={actionLoading !== null || status.emergency_stop}
                        >
                          {actionLoading === v.variant ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Play className="h-3 w-3 mr-1" />}
                          Resume
                        </Button>
                      )}
                    </div>

                    {/* Stats */}
                    <div className="space-y-3">
                      <div>
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="text-muted-foreground">Tickets Used</span>
                          <span className="font-medium">
                            {v.tickets_used.toLocaleString()} / {v.tickets_limit === 0 ? '∞' : v.tickets_limit.toLocaleString()}
                          </span>
                        </div>
                        {v.tickets_limit > 0 && (
                          <Progress value={usagePct} className="h-1.5" />
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div className="p-2 rounded-lg bg-white/50 text-center">
                          <p className="text-lg font-bold text-[#0A3D2E]">{v.actions_today}</p>
                          <p className="text-xs text-muted-foreground">Actions Today</p>
                        </div>
                        <div className="p-2 rounded-lg bg-white/50 text-center">
                          <p className={`text-lg font-bold ${v.pending_approvals > 0 ? 'text-amber-600' : 'text-[#0A3D2E]'}`}>
                            {v.pending_approvals}
                          </p>
                          <p className="text-xs text-muted-foreground">Pending</p>
                        </div>
                      </div>

                      {v.last_action && (
                        <div className="p-2 rounded-lg bg-white/50">
                          <p className="text-xs text-muted-foreground mb-0.5">Last Action</p>
                          <p className="text-xs font-medium truncate">{v.last_action}</p>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })
        ) : null}
      </div>

      <Separator />

      {/* Activity Log */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Activity className="h-5 w-5 text-[#0A3D2E]" />
              Activity Log
            </h3>
            <p className="text-sm text-muted-foreground">Track all AI actions across variants</p>
          </div>
          <div className="flex gap-2">
            <Select value={activityVariant} onValueChange={setActivityVariant}>
              <SelectTrigger className="w-[130px] h-8 text-xs">
                <SelectValue placeholder="Variant" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Variants</SelectItem>
                <SelectItem value="mini">Mini</SelectItem>
                <SelectItem value="parwa">Standard</SelectItem>
                <SelectItem value="high">High</SelectItem>
              </SelectContent>
            </Select>
            <Select value={activityStatus} onValueChange={setActivityStatus}>
              <SelectTrigger className="w-[130px] h-8 text-xs">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="executed">Executed</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="undone">Undone</SelectItem>
                <SelectItem value="denied">Denied</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <Card>
          <CardContent className="p-0">
            {activity.length === 0 ? (
              <div className="text-center py-12">
                <Activity className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
                <p className="text-muted-foreground">No activity recorded yet</p>
              </div>
            ) : (
              <div className="divide-y max-h-96 overflow-y-auto">
                {activity.map((entry) => (
                  <div key={entry.id} className="p-4 hover:bg-[#0A3D2E]/5 transition-colors">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <Badge className={`text-xs ${actionStatusBadge(entry.status)}`}>
                            {entry.status}
                          </Badge>
                          <Badge variant="outline" className="text-xs capitalize">
                            {entry.action_type.replace(/_/g, ' ')}
                          </Badge>
                          <Badge variant="secondary" className="text-xs capitalize">
                            {entry.variant}
                          </Badge>
                          {entry.ticket_id && (
                            <span className="text-xs text-muted-foreground font-mono">
                              {entry.ticket_id}
                            </span>
                          )}
                        </div>
                        <p className="text-sm font-medium">{entry.description}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <Clock className="h-3 w-3 text-muted-foreground" />
                          <span className="text-xs text-muted-foreground">
                            {new Date(entry.timestamp).toLocaleString()}
                          </span>
                          {entry.customer_id && (
                            <span className="text-xs text-muted-foreground">
                              • Customer: {entry.customer_id}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex items-center gap-1 shrink-0">
                        {entry.can_approve && entry.status === 'pending' && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 text-xs border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                              onClick={() => handleApprove(entry.id)}
                            >
                              <ThumbsUp className="h-3 w-3 mr-1" />
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 text-xs border-red-300 text-red-700 hover:bg-red-50"
                              onClick={() => handleDeny(entry.id)}
                            >
                              <ThumbsDown className="h-3 w-3 mr-1" />
                              Deny
                            </Button>
                          </>
                        )}
                        {entry.can_undo && entry.status === 'executed' && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs border-amber-300 text-amber-700 hover:bg-amber-50"
                            onClick={() => handleUndo(entry.id)}
                          >
                            <RotateCcw className="h-3 w-3 mr-1" />
                            Undo
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 text-xs"
                          onClick={() => { setNoteActionId(entry.id); setNoteText(''); }}
                        >
                          <StickyNote className="h-3 w-3 mr-1" />
                          Note
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Emergency Stop Confirmation Dialog */}
      <Dialog open={emergencyDialogOpen} onOpenChange={setEmergencyDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-700">
              <OctagonX className="h-6 w-6" />
              EMERGENCY STOP
            </DialogTitle>
            <DialogDescription>
              This will immediately halt ALL AI processing. New tickets will be routed to human agents only. This affects all variants across your entire account.
            </DialogDescription>
          </DialogHeader>
          <div className="p-4 rounded-lg bg-red-50 border border-red-200">
            <p className="text-sm font-medium text-red-800 mb-2">This action will:</p>
            <ul className="text-sm text-red-700 space-y-1 list-disc list-inside">
              <li>Stop all AI from processing tickets</li>
              <li>Route all new tickets to human agents</li>
              <li>Cancel any pending AI actions</li>
              <li>Require manual &quot;Resume All&quot; to restart</li>
            </ul>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEmergencyDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleEmergencyStop}
              disabled={emergencyLoading}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {emergencyLoading ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : <OctagonX className="h-4 w-4 mr-1.5" />}
              Confirm Emergency Stop
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Note Dialog */}
      <Dialog open={noteActionId !== null} onOpenChange={() => { setNoteActionId(null); setNoteText(''); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add Note to Action</DialogTitle>
            <DialogDescription>Provide a correction or instruction for this AI action.</DialogDescription>
          </DialogHeader>
          <textarea
            className="w-full h-32 rounded-lg border p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[#0A3D2E]/30"
            placeholder="Enter your note..."
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => { setNoteActionId(null); setNoteText(''); }}>
              Cancel
            </Button>
            <Button
              onClick={handleAddNote}
              disabled={noteLoading || !noteText.trim()}
              className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A]"
            >
              {noteLoading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              Add Note
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
