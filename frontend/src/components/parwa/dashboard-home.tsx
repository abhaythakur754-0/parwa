'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import {
  Ticket, MessageSquare, Bot, TrendingUp, Zap, Clock,
  CheckCircle2, AlertTriangle, ArrowUpRight,
} from 'lucide-react';
import { getUsage, getConnectedIntegrations, getNotifications, type VariantType } from '@/lib/api';

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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [u, i, n] = await Promise.all([
        getUsage().catch(() => null),
        getConnectedIntegrations().catch(() => null),
        getNotifications().catch(() => null),
      ]);
      setUsage(u);
      setIntegrations(i);
      setNotifications(n);
      setLoading(false);
    }
    load();
  }, [activeVariants]);

  const unreadCount = notifications?.filter(n => !n.read).length ?? 0;
  const connectedCount = integrations?.length ?? 0;
  const totalUsed = usage?.total_tickets_used ?? 0;

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
      title: 'Tickets Used',
      value: totalUsed.toLocaleString(),
      subtitle: 'this month',
      icon: Ticket,
      color: 'text-amber-600',
      bgColor: 'bg-amber-50',
      action: () => onNavigate('billing'),
    },
    {
      title: 'Integrations',
      value: connectedCount,
      subtitle: 'connected',
      icon: MessageSquare,
      color: 'text-sky-600',
      bgColor: 'bg-sky-50',
      action: () => onNavigate('integrations'),
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
        <p className="text-muted-foreground">Welcome to PARWA — your AI-powered customer support platform.</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
                const pct = variantUsage ? Math.round((variantUsage.tickets_used / variantUsage.tickets_limit) * 100) : 0;
                return (
                  <div key={v} className="p-4 rounded-lg border">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Badge className={variantColors[v]}>{variantLabels[v]}</Badge>
                        <span className="text-sm text-muted-foreground">
                          {variantUsage ? `${variantUsage.tickets_used.toLocaleString()} / ${variantUsage.tickets_limit.toLocaleString()} tickets` : 'Active'}
                        </span>
                      </div>
                      <ArrowUpRight className="h-4 w-4 text-muted-foreground cursor-pointer hover:text-[#0A3D2E]" onClick={() => onNavigate('billing')} />
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

      {/* Quick Actions */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Add Variant', icon: Zap, tab: 'variants', desc: 'Upgrade or add plans' },
              { label: 'Payment Setup', icon: TrendingUp, tab: 'billing', desc: 'Configure gateways' },
              { label: 'Integrations', icon: MessageSquare, tab: 'integrations', desc: 'Connect tools' },
              { label: 'Knowledge Base', icon: Bot, tab: 'knowledge', desc: 'Train your AI' },
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
