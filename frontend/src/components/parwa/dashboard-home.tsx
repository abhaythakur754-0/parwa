'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import {
  Ticket, MessageSquare, Bot, TrendingUp, Zap, Clock,
  CheckCircle2, AlertTriangle, ArrowUpRight, Phone,
  OctagonX, Pause, Play, Activity,
} from 'lucide-react';
import {
  getUsage, getConnectedIntegrations, getNotifications,
  getTicketStats, getVariantStatus, pauseAllVariants,
  emergencyStop as emergencyStopApi, resumeAllVariants,
  type VariantType, type TicketStats, type VariantStatusResponse,
} from '@/lib/api';
import { toast } from 'sonner';

interface DashboardHomeProps {
  activeVariants: VariantType[];
  onNavigate: (tab: string) => void;
}

const variantLabels: Record<VariantType, string> = {
  mini: 'PARWA Mini',
  parwa: 'PARWA Standard',
  high: 'PARWA High',
};

const variantColors: Record<VariantType, string> = {
  mini: 'bg-amber-100 text-amber-800',
  parwa: 'bg-[#0A3D2E]/10 text-[#0A3D2E]',
  high: 'bg-purple-100 text-purple-800',
};

export default function DashboardHome({ activeVariants, onNavigate }: DashboardHomeProps) {
  const [usage, setUsage] = useState<Awaited<ReturnType<typeof getUsage>> | null>(null);
  const [integrations, setIntegrations] = useState<Awaited<ReturnType<typeof getConnectedIntegrations>> | null>(null);
  const [notifications, setNotifications] = useState<Awaited<ReturnType<typeof getNotifications>> | null>(null);
  const [ticketStats, setTicketStats] = useState<TicketStats | null>(null);
  const [variantStatus, setVariantStatus] = useState<VariantStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [controlLoading, setControlLoading] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [u, i, n, ts, vs] = await Promise.all([
        getUsage().catch(() => null),
        getConnectedIntegrations().catch(() => null),
        getNotifications().catch(() => null),
        getTicketStats().catch(() => null),
        getVariantStatus().catch(() => null),
      ]);
      setUsage(u);
      setIntegrations(i);
      setNotifications(n);
      setTicketStats(ts);
      setVariantStatus(vs);
      setLoading(false);
    }
    load();
  }, [activeVariants]);

  const unreadCount = notifications?.filter(n => !n.read).length ?? 0;
  const connectedCount = integrations?.length ?? 0;
  const totalUsed = usage?.total_tickets_used ?? 0;

  const handleEmergencyStop = async () => {
    setControlLoading(true);
    try {
      await emergencyStopApi();
      toast.error('EMERGENCY STOP activated — all AI halted');
      const vs = await getVariantStatus().catch(() => null);
      setVariantStatus(vs);
    } catch {
      toast.error('Failed to activate emergency stop');
    }
    setControlLoading(false);
  };

  const handlePauseAll = async () => {
    setControlLoading(true);
    try {
      await pauseAllVariants();
      toast.success('All variants paused');
      const vs = await getVariantStatus().catch(() => null);
      setVariantStatus(vs);
    } catch {
      toast.error('Failed to pause all');
    }
    setControlLoading(false);
  };

  const handleResumeAll = async () => {
    setControlLoading(true);
    try {
      await resumeAllVariants();
      toast.success('All variants resumed');
      const vs = await getVariantStatus().catch(() => null);
      setVariantStatus(vs);
    } catch {
      toast.error('Failed to resume all');
    }
    setControlLoading(false);
  };

  const stats = [
    {
      title: 'Active Variants',
      value: activeVariants.length,
      icon: Zap,
      color: 'text-[#0A3D2E]',
      bgColor: 'bg-[#0A3D2E]/5',
      action: () => onNavigate('variants'),
    },
    {
      title: 'Open Tickets',
      value: ticketStats?.open_tickets ?? totalUsed.toLocaleString(),
      subtitle: ticketStats ? `${ticketStats.total_tickets} total` : 'this month',
      icon: Ticket,
      color: 'text-amber-600',
      bgColor: 'bg-amber-50',
      action: () => onNavigate('tickets'),
    },
    {
      title: 'AI Actions Today',
      value: ticketStats?.ai_actions_today ?? 0,
      subtitle: ticketStats?.pending_approvals ? `${ticketStats.pending_approvals} pending` : undefined,
      icon: Bot,
      color: 'text-[#0A3D2E]',
      bgColor: 'bg-[#0A3D2E]/5',
      action: () => onNavigate('variants'),
    },
    {
      title: 'Avg Quality Score',
      value: ticketStats?.avg_quality_score ?? 0,
      subtitle: ticketStats?.avg_quality_score ? (ticketStats.avg_quality_score >= 80 ? 'Excellent' : ticketStats.avg_quality_score >= 60 ? 'Good' : 'Needs Review') : undefined,
      icon: Activity,
      color: 'text-violet-600',
      bgColor: 'bg-violet-50',
      action: () => onNavigate('tickets'),
    },
    {
      title: 'Unread Alerts',
      value: unreadCount,
      icon: AlertTriangle,
      color: unreadCount > 0 ? 'text-red-600' : 'text-[#0A3D2E]',
      bgColor: unreadCount > 0 ? 'bg-red-50' : 'bg-[#0A3D2E]/5',
      action: () => onNavigate('notifications'),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground">Welcome to PARWA — your AI-powered customer support command center.</p>
      </div>

      {/* Emergency Stop Banner */}
      {variantStatus?.emergency_stop && (
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
              disabled={controlLoading}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              <Play className="h-4 w-4 mr-1.5" />
              Resume All
            </Button>
          </div>
        </motion.div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {stats.map((stat) => (
          <Card
            key={stat.title}
            className="cursor-pointer hover:shadow-md transition-shadow"
            onClick={stat.action}
          >
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{stat.title}</p>
                  {loading ? (
                    <Skeleton className="h-8 w-16 mt-1" />
                  ) : (
                    <div className="flex items-baseline gap-1.5">
                      <p className="text-2xl font-bold">{stat.value}</p>
                      {stat.subtitle && (
                        <span className="text-xs text-muted-foreground">{stat.subtitle}</span>
                      )}
                    </div>
                  )}
                </div>
                <div className={`p-2.5 rounded-xl ${stat.bgColor}`}>
                  <stat.icon className={`h-5 w-5 ${stat.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick Controls */}
      <Card className="border-[#0A3D2E]/10">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Activity className="h-4 w-4 text-[#0A3D2E]" />
            Quick Controls
          </CardTitle>
          <CardDescription>Emergency controls for AI variants</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button
              onClick={handleEmergencyStop}
              disabled={variantStatus?.emergency_stop || controlLoading}
              className="bg-red-600 hover:bg-red-700 text-white"
              size="sm"
            >
              <OctagonX className="h-3.5 w-3.5 mr-1.5" />
              Emergency Stop
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handlePauseAll}
              disabled={variantStatus?.paused_all || variantStatus?.emergency_stop || controlLoading}
              className="border-amber-300 text-amber-700 hover:bg-amber-50"
            >
              <Pause className="h-3.5 w-3.5 mr-1.5" />
              Pause All
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleResumeAll}
              disabled={!variantStatus?.paused_all || variantStatus?.emergency_stop || controlLoading}
              className="border-emerald-300 text-emerald-700 hover:bg-emerald-50"
            >
              <Play className="h-3.5 w-3.5 mr-1.5" />
              Resume All
            </Button>
          </div>
          {/* Variant status indicators */}
          {variantStatus && !loading && (
            <div className="flex items-center gap-4 mt-3">
              {variantStatus.variants.map(v => (
                <div key={v.variant} className="flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-full ${
                    v.status === 'active' ? 'bg-emerald-500' :
                    v.status === 'paused' ? 'bg-amber-500' :
                    'bg-red-500 animate-pulse'
                  }`} />
                  <span className="text-xs text-muted-foreground capitalize">{v.variant}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Variants */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Active Variants</CardTitle>
            <CardDescription>Your current subscription plans</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {loading ? (
              <div className="space-y-3">
                {[1, 2].map(i => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : activeVariants.length === 0 ? (
              <div className="text-center py-8">
                <Zap className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
                <p className="text-muted-foreground text-sm">No variants active yet</p>
                <button
                  onClick={() => onNavigate('variants')}
                  className="text-[#0A3D2E] text-sm font-medium hover:underline mt-1"
                >
                  Choose a plan to get started →
                </button>
              </div>
            ) : (
              activeVariants.map((v) => {
                const variantUsage = usage?.variants.find(uv => uv.variant === v);
                const vs = variantStatus?.variants.find(vs => vs.variant === v);
                const pct = variantUsage ? Math.round((variantUsage.tickets_used / variantUsage.tickets_limit) * 100) : 0;
                return (
                  <div key={v} className="p-4 rounded-lg border">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Badge className={variantColors[v]}>{variantLabels[v]}</Badge>
                        {vs && (
                          <Badge variant="outline" className={`text-xs capitalize ${
                            vs.status === 'active' ? 'border-emerald-300 text-emerald-700' :
                            vs.status === 'paused' ? 'border-amber-300 text-amber-700' :
                            'border-red-300 text-red-700'
                          }`}>
                            {vs.status}
                          </Badge>
                        )}
                        <span className="text-sm text-muted-foreground">
                          {variantUsage ? `${variantUsage.tickets_used.toLocaleString()} / ${variantUsage.tickets_limit.toLocaleString()} tickets` : 'Active'}
                        </span>
                      </div>
                      <ArrowUpRight className="h-4 w-4 text-muted-foreground cursor-pointer hover:text-[#0A3D2E]" onClick={() => onNavigate('variants')} />
                    </div>
                    {variantUsage && (
                      <Progress value={pct} className="h-2" />
                    )}
                    {variantUsage && (
                      <p className="text-xs text-muted-foreground mt-1">{pct}% of monthly limit used</p>
                    )}
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Recent Activity</CardTitle>
            <CardDescription>Latest updates from your support platform</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4].map(i => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : (
              <div className="space-y-3 max-h-80 overflow-y-auto">
                {notifications && notifications.length > 0 ? notifications.slice(0, 5).map((n) => (
                  <div key={n.id} className="flex items-start gap-3 p-3 rounded-lg hover:bg-muted/50 transition-colors">
                    <div className={`mt-0.5 p-1.5 rounded-lg ${
                      n.type === 'success' ? 'bg-[#0A3D2E]/10' :
                      n.type === 'error' ? 'bg-red-100' :
                      n.type === 'warning' ? 'bg-amber-100' :
                      'bg-slate-100'
                    }`}>
                      {n.type === 'success' ? <CheckCircle2 className="h-3.5 w-3.5 text-[#0A3D2E]" /> :
                       n.type === 'error' ? <AlertTriangle className="h-3.5 w-3.5 text-red-600" /> :
                       n.type === 'warning' ? <AlertTriangle className="h-3.5 w-3.5 text-amber-600" /> :
                       <Clock className="h-3.5 w-3.5 text-slate-600" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium">{n.title}</p>
                      <p className="text-xs text-muted-foreground truncate">{n.message}</p>
                    </div>
                    {!n.read && <div className="w-2 h-2 rounded-full bg-[#0A3D2E]/50 mt-2 shrink-0" />}
                  </div>
                )) : (
                  <div className="text-center py-6">
                    <Clock className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">No recent activity</p>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Ticket Stats Overview */}
      {ticketStats && !loading && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Ticket className="h-4 w-4 text-[#0A3D2E]" />
              Ticket Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="p-3 rounded-lg bg-amber-50 text-center">
                <p className="text-2xl font-bold text-amber-700">{ticketStats.open_tickets}</p>
                <p className="text-xs text-amber-600">Open</p>
              </div>
              <div className="p-3 rounded-lg bg-sky-50 text-center">
                <p className="text-2xl font-bold text-sky-700">{ticketStats.in_progress}</p>
                <p className="text-xs text-sky-600">In Progress</p>
              </div>
              <div className="p-3 rounded-lg bg-emerald-50 text-center">
                <p className="text-2xl font-bold text-emerald-700">{ticketStats.resolved}</p>
                <p className="text-xs text-emerald-600">Resolved</p>
              </div>
              <div className="p-3 rounded-lg bg-[#0A3D2E]/5 text-center">
                <p className="text-2xl font-bold text-[#0A3D2E]">{ticketStats.avg_resolution_hours}h</p>
                <p className="text-xs text-[#0A3D2E]/70">Avg Resolution</p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="mt-3 w-full border-[#0A3D2E]/30 hover:bg-[#0A3D2E]/5"
              onClick={() => onNavigate('tickets')}
            >
              View All Tickets
              <ArrowUpRight className="h-3.5 w-3.5 ml-1.5" />
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'View Tickets', icon: Ticket, tab: 'tickets', desc: 'All support tickets' },
              { label: 'Variant Control', icon: Activity, tab: 'variants', desc: 'Manage AI variants' },
              { label: 'Voice Calls', icon: Phone, tab: 'calls', desc: 'Call recordings' },
              { label: 'Integrations', icon: MessageSquare, tab: 'integrations', desc: 'Connect tools' },
            ].map((action) => (
              <button
                key={action.label}
                onClick={() => onNavigate(action.tab)}
                className="p-4 rounded-lg border hover:border-[#0A3D2E]/30 hover:bg-[#0A3D2E]/5/50 transition-all text-left group"
              >
                <action.icon className="h-5 w-5 text-[#0A3D2E] mb-2 group-hover:scale-110 transition-transform" />
                <p className="text-sm font-medium">{action.label}</p>
                <p className="text-xs text-muted-foreground">{action.desc}</p>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
