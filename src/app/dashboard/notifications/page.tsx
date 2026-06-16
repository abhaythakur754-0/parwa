/**
 * Notifications Page (/dashboard/notifications)
 *
 * PARWA notification center with tab-based views for:
 *  - All notifications
 *  - Escalations (tickets escalated to humans)
 *  - Self-Improvement (auto-adjustments by the self-improvement engine)
 *  - Subgraph Performance (resolution rate changes per subgraph)
 *  - Technique Alerts (technique failures or priority changes)
 */

'use client';

import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import {
  NotificationList,
  type NotificationItem,
  type NotificationTabType,
} from '@/components/notifications/notification-list';
import {
  SubgraphStats,
  type SubgraphStat,
} from '@/components/notifications/subgraph-stats';
import {
  ImprovementLog,
  type ImprovementEntry,
} from '@/components/notifications/improvement-log';

// ── Mock Notification Data ───────────────────────────────────────────

const MOCK_NOTIFICATIONS: NotificationItem[] = [
  {
    id: 'notif-001',
    type: 'escalation',
    title: 'Ticket TK-4521 escalated to human agent',
    message:
      'Refund request for subscription cancellation could not be resolved automatically. Customer requested manager review after 3 AI attempts.',
    timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
    read: false,
    priority: 'high',
    subgraph: 'refund',
  },
  {
    id: 'notif-002',
    type: 'self_improvement',
    title: 'Prompt adjustment applied to refund subgraph',
    message:
      'Added subscription proration rules to refund system prompt after detecting 12 failed resolutions with "subscription" keyword over the past 24h.',
    timestamp: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
    read: false,
    priority: 'medium',
    subgraph: 'refund',
  },
  {
    id: 'notif-003',
    type: 'subgraph_performance',
    title: 'Billing subgraph resolution rate dropped below 80%',
    message:
      'Billing resolution rate fell from 84.2% to 78.6% in the last evaluation window. 6 consecutive tickets failed due to proration calculation errors.',
    timestamp: new Date(Date.now() - 1000 * 60 * 32).toISOString(),
    read: false,
    priority: 'high',
    subgraph: 'billing',
  },
  {
    id: 'notif-004',
    type: 'technique_alert',
    title: 'Chain-of-Thought failing for complex tech tickets',
    message:
      'CoT resolution rate for tech subgraph dropped to 61.3% (down from 78%). Reverse Thinking is being promoted to run alongside CoT for complex complexity tickets.',
    timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
    read: false,
    priority: 'high',
    subgraph: 'tech',
    technique: 'chain_of_thought',
  },
  {
    id: 'notif-005',
    type: 'escalation',
    title: 'Ticket TK-4518 escalated — billing dispute',
    message:
      'Customer disputed a charge that the AI classified as valid. Manual review required for chargeback risk assessment.',
    timestamp: new Date(Date.now() - 1000 * 60 * 67).toISOString(),
    read: true,
    priority: 'medium',
    subgraph: 'billing',
  },
  {
    id: 'notif-006',
    type: 'self_improvement',
    title: 'Technique tuning: Self-Consistency promoted for billing',
    message:
      'Self-Consistency has been promoted in the billing subgraph technique priority list after demonstrating a 15% improvement in resolution rate over the past 48h.',
    timestamp: new Date(Date.now() - 1000 * 60 * 90).toISOString(),
    read: false,
    priority: 'medium',
    subgraph: 'billing',
    technique: 'self_consistency',
  },
  {
    id: 'notif-007',
    type: 'subgraph_performance',
    title: 'General subgraph resolution rate improved to 91.4%',
    message:
      'After the latest prompt adjustment, the general subgraph improved from 87.1% to 91.4%. The FAQ matcher enhancement is working as expected.',
    timestamp: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
    read: true,
    priority: 'low',
    subgraph: 'general',
  },
  {
    id: 'notif-008',
    type: 'technique_alert',
    title: 'ReAct timeout rate exceeds threshold for tech subgraph',
    message:
      'ReAct is timing out on 23% of tech subgraph tickets (threshold: 15%). Consider reducing max iterations or switching to Tree-of-Thoughts for complex tickets.',
    timestamp: new Date(Date.now() - 1000 * 60 * 180).toISOString(),
    read: false,
    priority: 'medium',
    subgraph: 'tech',
    technique: 'react',
  },
  {
    id: 'notif-009',
    type: 'escalation',
    title: 'Ticket TK-4509 escalated — integration failure',
    message:
      'Shopify integration sync failed during ticket resolution. Customer reported data inconsistency. Escalated for manual API verification.',
    timestamp: new Date(Date.now() - 1000 * 60 * 240).toISOString(),
    read: true,
    priority: 'medium',
    subgraph: 'tech',
  },
  {
    id: 'notif-010',
    type: 'self_improvement',
    title: 'Integration troubleshooting steps added to tech prompt',
    message:
      'Pattern learner detected 8 escalation tickets related to "integration" keyword. Added Shopify and Stripe integration troubleshooting rules to tech subgraph prompt.',
    timestamp: new Date(Date.now() - 1000 * 60 * 300).toISOString(),
    read: true,
    priority: 'low',
    subgraph: 'tech',
  },
  {
    id: 'notif-011',
    type: 'subgraph_performance',
    title: 'Refund subgraph resolution rate at 88.7%',
    message:
      'Refund subgraph steady at 88.7% after recent prompt adjustments. Subscription refund handling improved by 4.2%.',
    timestamp: new Date(Date.now() - 1000 * 60 * 360).toISOString(),
    read: true,
    priority: 'low',
    subgraph: 'refund',
  },
  {
    id: 'notif-012',
    type: 'technique_alert',
    title: 'Self-Consistency cap increased for refund subgraph',
    message:
      'Self-Consistency max concurrent executions increased from 2 to 3 for the refund subgraph after confidence scoring validated the improvement.',
    timestamp: new Date(Date.now() - 1000 * 60 * 420).toISOString(),
    read: true,
    priority: 'low',
    subgraph: 'refund',
    technique: 'self_consistency',
  },
  {
    id: 'notif-013',
    type: 'escalation',
    title: 'Ticket TK-4502 escalated — PII detected in response',
    message:
      'Compliance guard flagged a response containing potential PII. Ticket escalated for manual review and response redaction.',
    timestamp: new Date(Date.now() - 1000 * 60 * 500).toISOString(),
    read: true,
    priority: 'critical',
    subgraph: 'general',
  },
  {
    id: 'notif-014',
    type: 'technique_alert',
    title: 'Reverse Thinking demoted for simple billing tickets',
    message:
      'Reverse Thinking was using excessive tokens on simple billing queries. Demoted below CoT for "simple" complexity classification in billing subgraph.',
    timestamp: new Date(Date.now() - 1000 * 60 * 600).toISOString(),
    read: true,
    priority: 'low',
    subgraph: 'billing',
    technique: 'reverse_thinking',
  },
  {
    id: 'notif-015',
    type: 'self_improvement',
    title: 'FAQ matcher enhanced for general subgraph',
    message:
      'Added 5 new FAQ patterns to the general subgraph after pattern learner identified repeated escalation on "how to cancel" and "account deletion" queries.',
    timestamp: new Date(Date.now() - 1000 * 60 * 720).toISOString(),
    read: true,
    priority: 'low',
    subgraph: 'general',
  },
];

// ── Mock Subgraph Stats ──────────────────────────────────────────────

const MOCK_SUBGRAPH_STATS: SubgraphStat[] = [
  {
    name: 'Refund',
    key: 'refund',
    resolutionRate: 0.887,
    previousRate: 0.845,
    totalTickets: 342,
    resolvedTickets: 303,
    escalatedTickets: 39,
    avgLatencyMs: 1240,
  },
  {
    name: 'Tech Support',
    key: 'tech',
    resolutionRate: 0.764,
    previousRate: 0.781,
    totalTickets: 518,
    resolvedTickets: 396,
    escalatedTickets: 122,
    avgLatencyMs: 2180,
  },
  {
    name: 'Billing',
    key: 'billing',
    resolutionRate: 0.786,
    previousRate: 0.842,
    totalTickets: 287,
    resolvedTickets: 226,
    escalatedTickets: 61,
    avgLatencyMs: 1580,
  },
  {
    name: 'General',
    key: 'general',
    resolutionRate: 0.914,
    previousRate: 0.871,
    totalTickets: 621,
    resolvedTickets: 568,
    escalatedTickets: 53,
    avgLatencyMs: 680,
  },
];

// ── Mock Improvement Log ─────────────────────────────────────────────

const MOCK_IMPROVEMENT_LOG: ImprovementEntry[] = [
  {
    id: 'imp-001',
    type: 'prompt_adjustment',
    subgraph: 'refund',
    title: 'Added subscription proration rules',
    description:
      'Added IMPORTANT rule for subscription refunds: always calculate prorated amount from cancellation date, check if annual or monthly, apply different proration rules.',
    timestamp: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
    status: 'applied',
    confidence: 0.82,
    adjustmentType: 'add_rule',
  },
  {
    id: 'imp-002',
    type: 'prompt_adjustment',
    subgraph: 'tech',
    title: 'Added integration troubleshooting steps',
    description:
      'Added Shopify and Stripe integration troubleshooting rules. Include API status check, webhook verification, and sync conflict resolution steps.',
    timestamp: new Date(Date.now() - 1000 * 60 * 300).toISOString(),
    status: 'verified',
    confidence: 0.91,
    adjustmentType: 'add_rule',
  },
  {
    id: 'imp-003',
    type: 'prompt_adjustment',
    subgraph: 'general',
    title: 'Added cancellation FAQ patterns',
    description:
      'Added 5 new FAQ match patterns for "how to cancel", "account deletion", "subscription cancellation", "remove my data", and "close account" queries.',
    timestamp: new Date(Date.now() - 1000 * 60 * 720).toISOString(),
    status: 'verified',
    confidence: 0.95,
    adjustmentType: 'add_example',
  },
  {
    id: 'imp-004',
    type: 'prompt_adjustment',
    subgraph: 'billing',
    title: 'Added proration calculation examples',
    description:
      'Added worked examples for annual and monthly subscription proration calculations with edge cases for mid-cycle changes.',
    timestamp: new Date(Date.now() - 1000 * 60 * 150).toISOString(),
    status: 'pending',
    confidence: 0.68,
    adjustmentType: 'add_example',
  },
  {
    id: 'imp-005',
    type: 'technique_tuning',
    subgraph: 'billing',
    title: 'Self-Consistency promoted for billing',
    description:
      'Self-Consistency moved from priority 3 to priority 1 in billing subgraph after demonstrating 15% improvement in resolution rate over 48h.',
    timestamp: new Date(Date.now() - 1000 * 60 * 90).toISOString(),
    status: 'applied',
    confidence: 0.87,
    adjustmentType: 'promote',
    technique: 'self_consistency',
  },
  {
    id: 'imp-006',
    type: 'technique_tuning',
    subgraph: 'tech',
    title: 'Reverse Thinking promoted for complex tickets',
    description:
      'Reverse Thinking promoted to run alongside CoT for complex complexity tech tickets after CoT resolution rate dropped to 61.3%.',
    timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
    status: 'applied',
    confidence: 0.74,
    adjustmentType: 'promote',
    technique: 'reverse_thinking',
  },
  {
    id: 'imp-007',
    type: 'technique_tuning',
    subgraph: 'refund',
    title: 'Self-Consistency cap increased to 3',
    description:
      'Self-Consistency max concurrent executions increased from 2 to 3 for refund subgraph. Confidence scoring validated the improvement.',
    timestamp: new Date(Date.now() - 1000 * 60 * 420).toISOString(),
    status: 'verified',
    confidence: 0.89,
    adjustmentType: 'increase_cap',
    technique: 'self_consistency',
  },
  {
    id: 'imp-008',
    type: 'technique_tuning',
    subgraph: 'billing',
    title: 'Reverse Thinking demoted for simple tickets',
    description:
      'Reverse Thinking demoted below CoT for "simple" complexity classification in billing subgraph due to excessive token usage on simple queries.',
    timestamp: new Date(Date.now() - 1000 * 60 * 600).toISOString(),
    status: 'verified',
    confidence: 0.79,
    adjustmentType: 'demote',
    technique: 'reverse_thinking',
  },
  {
    id: 'imp-009',
    type: 'technique_tuning',
    subgraph: 'tech',
    title: 'ReAct max iterations reduced',
    description:
      'ReAct max iterations reduced from 8 to 5 for tech subgraph to address 23% timeout rate. Complex tickets will fall through to Tree-of-Thoughts.',
    timestamp: new Date(Date.now() - 1000 * 60 * 180).toISOString(),
    status: 'pending',
    confidence: 0.62,
    adjustmentType: 'decrease_cap',
    technique: 'react',
  },
];

// ── Tab Configuration ────────────────────────────────────────────────

interface TabConfig {
  value: NotificationTabType;
  label: string;
  icon: React.ReactNode;
  count: number;
}

// ── Page Component ───────────────────────────────────────────────────

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<NotificationItem[]>(
    MOCK_NOTIFICATIONS
  );
  const [activeTab, setActiveTab] = useState<NotificationTabType>('all');

  const handleMarkRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  }, []);

  const handleMarkAllRead = useCallback(() => {
    const filtered =
      activeTab === 'all'
        ? notifications
        : notifications.filter((n) => n.type === activeTab);
    const filteredIds = new Set(filtered.filter((n) => !n.read).map((n) => n.id));
    setNotifications((prev) =>
      prev.map((n) => (filteredIds.has(n.id) ? { ...n, read: true } : n))
    );
  }, [activeTab, notifications]);

  // Compute tab counts
  const tabs: TabConfig[] = [
    {
      value: 'all',
      label: 'All',
      icon: (
        <svg
          className="w-3.5 h-3.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"
          />
        </svg>
      ),
      count: notifications.filter((n) => !n.read).length,
    },
    {
      value: 'escalation',
      label: 'Escalations',
      icon: (
        <svg
          className="w-3.5 h-3.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
          />
        </svg>
      ),
      count: notifications.filter((n) => n.type === 'escalation' && !n.read)
        .length,
    },
    {
      value: 'self_improvement',
      label: 'Self-Improvement',
      icon: (
        <svg
          className="w-3.5 h-3.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"
          />
        </svg>
      ),
      count: notifications.filter(
        (n) => n.type === 'self_improvement' && !n.read
      ).length,
    },
    {
      value: 'subgraph_performance',
      label: 'Subgraph',
      icon: (
        <svg
          className="w-3.5 h-3.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
          />
        </svg>
      ),
      count: notifications.filter(
        (n) => n.type === 'subgraph_performance' && !n.read
      ).length,
    },
    {
      value: 'technique_alert',
      label: 'Technique Alerts',
      icon: (
        <svg
          className="w-3.5 h-3.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
          />
        </svg>
      ),
      count: notifications.filter(
        (n) => n.type === 'technique_alert' && !n.read
      ).length,
    },
  ];

  const totalUnread = notifications.filter((n) => !n.read).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <svg
              className="w-6 h-6 text-orange-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"
              />
            </svg>
            Notifications
            {totalUnread > 0 && (
              <Badge className="bg-orange-500/15 text-orange-400 border-orange-500/20 text-[10px] px-2">
                {totalUnread} unread
              </Badge>
            )}
          </h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Self-improvement alerts, escalations, and subgraph performance
          </p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as NotificationTabType)}
      >
        <TabsList className="bg-[#1A1A1A] border border-white/[0.06] rounded-lg w-full overflow-x-auto sm:w-auto flex-nowrap">
          {tabs.map((tab) => (
            <TabsTrigger
              key={tab.value}
              value={tab.value}
              className="text-xs gap-1.5 data-[state=active]:bg-white/10 data-[state=active]:text-white data-[state=active]:shadow-none text-zinc-500 hover:text-zinc-300 shrink-0"
            >
              {tab.icon}
              <span className="hidden sm:inline">{tab.label}</span>
              <span className="sm:hidden">
                {tab.label.split(' ')[0].slice(0, 6)}
              </span>
              {tab.count > 0 && (
                <span className="min-w-[16px] h-4 rounded-full bg-orange-500/20 text-orange-400 text-[9px] font-bold flex items-center justify-center px-1">
                  {tab.count}
                </span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Tab Content */}
        <div className="mt-4">
          {/* All notifications tab — shows list + side panels */}
          <TabsContent value="all" className="space-y-4">
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              {/* Main list */}
              <div className="xl:col-span-2">
                <NotificationList
                  notifications={notifications}
                  activeTab="all"
                  onMarkRead={handleMarkRead}
                  onMarkAllRead={handleMarkAllRead}
                />
              </div>
              {/* Side panel */}
              <div className="space-y-4">
                <SubgraphStats stats={MOCK_SUBGRAPH_STATS} />
              </div>
            </div>
            {/* Improvement log below */}
            <ImprovementLog entries={MOCK_IMPROVEMENT_LOG} />
          </TabsContent>

          {/* Escalations tab */}
          <TabsContent value="escalation" className="space-y-4">
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              <div className="xl:col-span-2">
                <NotificationList
                  notifications={notifications}
                  activeTab="escalation"
                  onMarkRead={handleMarkRead}
                  onMarkAllRead={handleMarkAllRead}
                />
              </div>
              <div>
                {/* Escalation summary card */}
                <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
                  <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
                    Escalation Summary
                  </h3>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-zinc-400">Total escalations</span>
                      <span className="text-sm font-bold text-white">
                        {notifications.filter((n) => n.type === 'escalation').length}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-zinc-400">Unread</span>
                      <span className="text-sm font-bold text-amber-400">
                        {notifications.filter((n) => n.type === 'escalation' && !n.read).length}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-zinc-400">Critical</span>
                      <span className="text-sm font-bold text-red-400">
                        {notifications.filter((n) => n.type === 'escalation' && n.priority === 'critical').length}
                      </span>
                    </div>
                    {(() => {
                      const bySubgraph: Record<string, number> = {};
                      notifications
                        .filter((n) => n.type === 'escalation')
                        .forEach((n) => {
                          const sg = n.subgraph || 'unknown';
                          bySubgraph[sg] = (bySubgraph[sg] || 0) + 1;
                        });
                      return Object.entries(bySubgraph).map(([sg, count]) => (
                        <div key={sg} className="flex items-center justify-between">
                          <span className="text-xs text-zinc-400 capitalize">
                            {sg}
                          </span>
                          <span className="text-sm font-medium text-white">
                            {count}
                          </span>
                        </div>
                      ));
                    })()}
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Self-Improvement tab */}
          <TabsContent value="self_improvement" className="space-y-4">
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              <div className="xl:col-span-2">
                <NotificationList
                  notifications={notifications}
                  activeTab="self_improvement"
                  onMarkRead={handleMarkRead}
                  onMarkAllRead={handleMarkAllRead}
                />
              </div>
              <div>
                <ImprovementLog entries={MOCK_IMPROVEMENT_LOG} />
              </div>
            </div>
          </TabsContent>

          {/* Subgraph Performance tab */}
          <TabsContent value="subgraph_performance" className="space-y-4">
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              <div className="xl:col-span-2">
                <NotificationList
                  notifications={notifications}
                  activeTab="subgraph_performance"
                  onMarkRead={handleMarkRead}
                  onMarkAllRead={handleMarkAllRead}
                />
              </div>
              <div>
                <SubgraphStats stats={MOCK_SUBGRAPH_STATS} />
              </div>
            </div>
          </TabsContent>

          {/* Technique Alerts tab */}
          <TabsContent value="technique_alert" className="space-y-4">
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              <div className="xl:col-span-2">
                <NotificationList
                  notifications={notifications}
                  activeTab="technique_alert"
                  onMarkRead={handleMarkRead}
                  onMarkAllRead={handleMarkAllRead}
                />
              </div>
              <div>
                {/* Technique summary card */}
                <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-4">
                  <h3 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3">
                    Technique Alert Summary
                  </h3>
                  <div className="space-y-3">
                    {(() => {
                      const byTechnique: Record<string, number> = {};
                      notifications
                        .filter((n) => n.type === 'technique_alert')
                        .forEach((n) => {
                          const tech = n.technique || 'unknown';
                          byTechnique[tech] = (byTechnique[tech] || 0) + 1;
                        });
                      return Object.entries(byTechnique).length > 0 ? (
                        Object.entries(byTechnique).map(([tech, count]) => (
                          <div key={tech} className="flex items-center justify-between">
                            <span className="text-xs text-zinc-400">
                              {tech.replace(/_/g, ' ')}
                            </span>
                            <span className="text-sm font-medium text-white">
                              {count} alert{count > 1 ? 's' : ''}
                            </span>
                          </div>
                        ))
                      ) : (
                        <p className="text-xs text-zinc-600">No technique alerts</p>
                      );
                    })()}
                    <div className="border-t border-white/[0.06] pt-3 mt-3">
                      <p className="text-[10px] text-zinc-600">
                        Technique alerts are triggered when a technique&apos;s failure rate
                        exceeds its threshold or when the self-improvement engine
                        adjusts technique priorities.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Improvement log with only technique entries */}
                <div className="mt-4">
                  <ImprovementLog
                    entries={MOCK_IMPROVEMENT_LOG.filter(
                      (e) => e.type === 'technique_tuning'
                    )}
                  />
                </div>
              </div>
            </div>
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
