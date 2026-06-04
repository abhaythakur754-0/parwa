'use client';

import React, { useEffect, useMemo } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  Bot,
  Activity,
  ThumbsUp,
  Ticket,
  Plus,
  Crown,
  ArrowRight,
  Zap,
  Clock,
  TrendingUp,
  AlertCircle,
  Cpu,
} from 'lucide-react';
import {
  useAgentsStore,
  AGENT_TYPE_LABELS,
  AGENT_TYPE_COLORS,
  AGENT_STATUS_COLORS,
  AGENT_STATUS_LABELS,
  type Agent,
  type AgentType,
  type AgentStatus,
} from '@/lib/agents-store';
import { useVariant } from '@/hooks/useVariant';
import { TierBadge } from '@/components/LockedFeature';
import { getTierLabel } from '@/lib/variant-store';

// ── Animation Variants ────────────────────────────────────────────────

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.06 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
};

const cardHover = {
  rest: { scale: 1 },
  hover: { scale: 1.015, transition: { duration: 0.2 } },
};

// ── Tier badge color helper ──────────────────────────────────────────

function tierBadgeStyle(variant: 'light' | 'medium' | 'heavy') {
  switch (variant) {
    case 'light':
      return 'bg-sky-500/10 text-sky-400 border-sky-500/20';
    case 'medium':
      return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
    case 'heavy':
      return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
  }
}

function tierLabel(variant: 'light' | 'medium' | 'heavy') {
  switch (variant) {
    case 'light':
      return 'Mini';
    case 'medium':
      return 'Pro';
    case 'heavy':
      return 'High';
  }
}

// ── Skeleton Card ────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 animate-pulse">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-white/[0.06]" />
          <div className="space-y-2">
            <div className="h-4 w-28 bg-white/[0.06] rounded" />
            <div className="h-3 w-20 bg-white/[0.06] rounded" />
          </div>
        </div>
        <div className="h-5 w-14 bg-white/[0.06] rounded-full" />
      </div>
      <div className="space-y-3 mt-4">
        <div className="flex justify-between">
          <div className="h-3 w-24 bg-white/[0.06] rounded" />
          <div className="h-3 w-16 bg-white/[0.06] rounded" />
        </div>
        <div className="flex justify-between">
          <div className="h-3 w-20 bg-white/[0.06] rounded" />
          <div className="h-3 w-14 bg-white/[0.06] rounded" />
        </div>
        <div className="flex justify-between">
          <div className="h-3 w-24 bg-white/[0.06] rounded" />
          <div className="h-3 w-12 bg-white/[0.06] rounded" />
        </div>
      </div>
      <div className="mt-4 pt-4 border-t border-white/[0.04]">
        <div className="flex justify-between items-center">
          <div className="h-3 w-20 bg-white/[0.06] rounded" />
          <div className="h-3 w-16 bg-white/[0.06] rounded" />
        </div>
      </div>
    </div>
  );
}

// ── Stat Card ────────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  subtitle,
  variant,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  subtitle?: string;
  variant?: 'default' | 'success' | 'warning' | 'danger';
}) {
  const borderMap = {
    default: 'border-white/[0.06] hover:border-white/[0.1]',
    success: 'border-emerald-500/20 hover:border-emerald-500/30',
    warning: 'border-amber-500/20 hover:border-amber-500/30',
    danger: 'border-red-500/20 hover:border-red-500/30',
  };
  const iconBgMap = {
    default: 'bg-white/[0.05]',
    success: 'bg-emerald-500/10',
    warning: 'bg-amber-500/10',
    danger: 'bg-red-500/10',
  };
  const iconTextMap = {
    default: 'text-zinc-400',
    success: 'text-emerald-400',
    warning: 'text-amber-400',
    danger: 'text-red-400',
  };

  const v = variant || 'default';

  return (
    <motion.div
      variants={itemVariants}
      className={`rounded-xl bg-[#1A1A1A] border p-5 transition-all duration-300 ${borderMap[v]}`}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold text-white tabular-nums">{value}</p>
          {subtitle && <p className="text-xs text-zinc-500">{subtitle}</p>}
        </div>
        <div
          className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${iconBgMap[v]}`}
        >
          <span className={iconTextMap[v]}>{icon}</span>
        </div>
      </div>
    </motion.div>
  );
}

// ── Agent Card ───────────────────────────────────────────────────────

function AgentCard({ agent, index }: { agent: Agent; index: number }) {
  const typeGradient = AGENT_TYPE_COLORS[agent.type] || 'from-zinc-500 to-zinc-400';
  const statusDot = AGENT_STATUS_COLORS[agent.status] || 'bg-zinc-400';
  const statusLabel = AGENT_STATUS_LABELS[agent.status] || 'Unknown';
  const typeLabel = AGENT_TYPE_LABELS[agent.type] || agent.type;

  return (
    <motion.div
      variants={itemVariants}
      whileHover="hover"
      initial="rest"
      animate="rest"
    >
      <motion.div
        variants={cardHover}
        className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 hover:border-white/[0.1] transition-colors duration-300 h-full flex flex-col"
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div
              className={`w-9 h-9 rounded-lg bg-gradient-to-br ${typeGradient} flex items-center justify-center shrink-0`}
            >
              <Bot className="w-4.5 h-4.5 text-white" />
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-white truncate">{agent.name}</h3>
              <p className="text-xs text-zinc-500 mt-0.5">{agent.model}</p>
            </div>
          </div>
          <span
            className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${tierBadgeStyle(agent.variant)}`}
          >
            {tierLabel(agent.variant)}
          </span>
        </div>

        {/* Type badge + Status */}
        <div className="flex items-center gap-2 mb-4">
          <span
            className={`text-[10px] font-medium px-2.5 py-1 rounded-full bg-gradient-to-r ${typeGradient} text-white`}
          >
            {typeLabel}
          </span>
          <div className="flex items-center gap-1.5 ml-auto">
            <span className={`w-2 h-2 rounded-full ${statusDot} ${agent.status === 'active' ? 'animate-pulse' : ''}`} />
            <span className="text-[11px] text-zinc-400">{statusLabel}</span>
          </div>
        </div>

        {/* Metrics */}
        <div className="space-y-2.5 flex-1">
          <div className="flex items-center justify-between text-sm">
            <span className="text-zinc-500 flex items-center gap-1.5">
              <Ticket className="w-3.5 h-3.5" />
              Tickets
            </span>
            <span className="text-zinc-300 font-medium tabular-nums">
              {agent.metrics.ticketsHandled.toLocaleString()}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-zinc-500 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" />
              Avg Response
            </span>
            <span className="text-zinc-300 font-medium tabular-nums">
              {agent.metrics.avgResponseTime > 0
                ? `${agent.metrics.avgResponseTime.toFixed(1)}s`
                : '—'}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-zinc-500 flex items-center gap-1.5">
              <ThumbsUp className="w-3.5 h-3.5" />
              Satisfaction
            </span>
            <span className="text-orange-400 font-semibold tabular-nums">
              {agent.metrics.satisfactionScore > 0
                ? `${agent.metrics.satisfactionScore}%`
                : '—'}
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-4 pt-3 border-t border-white/[0.04] flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Cpu className="w-3 h-3 text-zinc-500" />
            <span className="text-[11px] text-zinc-500">{agent.domain}</span>
          </div>
          {agent.lastActiveAt && (
            <span className="text-[10px] text-zinc-600">
              {formatLastActive(agent.lastActiveAt)}
            </span>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────

function formatLastActive(dateStr: string): string {
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch {
    return '';
  }
}

// ── Empty State ──────────────────────────────────────────────────────

function EmptyState() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col items-center justify-center py-20 text-center"
    >
      <div className="w-16 h-16 rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center mb-5">
        <Bot className="w-8 h-8 text-zinc-600" />
      </div>
      <h3 className="text-base font-semibold text-zinc-300 mb-1.5">No agents yet</h3>
      <p className="text-sm text-zinc-500 max-w-sm mb-6">
        Create your first AI agent to start automating customer support. Each agent specializes in a specific task like FAQs, refunds, or technical issues.
      </p>
      <Link
        href="/dashboard/agents/new"
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200"
      >
        <Plus className="w-4 h-4" />
        Create Agent
      </Link>
    </motion.div>
  );
}

// ── Tier Limit Banner ────────────────────────────────────────────────

function TierLimitBanner({ used, limit }: { used: number; limit: number }) {
  if (limit <= 0 || used < limit) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 flex flex-col sm:flex-row items-start sm:items-center gap-3"
    >
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <div className="w-9 h-9 rounded-lg bg-amber-500/10 flex items-center justify-center shrink-0">
          <AlertCircle className="w-4.5 h-4.5 text-amber-400" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-amber-300">Agent limit reached</p>
          <p className="text-xs text-zinc-400 mt-0.5">
            You&apos;re using {used} of {limit} agents on your current plan.
          </p>
        </div>
      </div>
      <Link
        href="/dashboard/billing"
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200 shrink-0"
      >
        <Crown className="w-3.5 h-3.5" />
        Upgrade to add more agents
        <ArrowRight className="w-3 h-3" />
      </Link>
    </motion.div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────

export default function AgentsPage() {
  const { agents, isLoading, fetchAgents, getActiveAgentCount, getTotalMetrics } =
    useAgentsStore();
  const { features, usage, tier, tierLabel, isAtLimit } = useVariant();

  // Fetch agents on mount
  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  // Derived values
  const maxAgents = features.maxAgents;
  const agentsUsed = usage.agentsUsed || agents.length;
  const atAgentLimit = isAtLimit('agents') || agentsUsed >= maxAgents;

  const activeCount = getActiveAgentCount();
  const totalMetrics = getTotalMetrics();
  const avgSatisfaction =
    agents.length > 0
      ? Math.round(totalMetrics.satisfactionScore / agents.length)
      : 0;
  const ticketsToday = totalMetrics.ticketsHandled;

  // ── Loading State ────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="space-y-6">
        {/* Header skeleton */}
        <div className="animate-pulse">
          <div className="flex items-center gap-3">
            <div className="h-8 w-36 bg-white/[0.06] rounded" />
            <div className="h-6 w-16 bg-white/[0.06] rounded-full" />
          </div>
          <div className="h-4 w-72 bg-white/[0.06] rounded mt-2" />
        </div>

        {/* Stats skeleton */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5 animate-pulse">
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <div className="h-3 w-20 bg-white/[0.06] rounded" />
                  <div className="h-7 w-24 bg-white/[0.06] rounded" />
                </div>
                <div className="w-10 h-10 rounded-lg bg-white/[0.06]" />
              </div>
            </div>
          ))}
        </div>

        {/* Cards skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  // ── Render ───────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* ── Page Header ──────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white">AI Agents</h1>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-white/[0.05] border border-white/[0.06] text-zinc-300">
              <Bot className="w-3 h-3" />
              {agentsUsed} / {maxAgents === -1 ? '∞' : maxAgents} agents
            </span>
          </div>
          <div className="flex items-center gap-3">
            {/* Tier progress bar */}
            {maxAgents > 0 && (
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-32 h-2 rounded-full bg-white/[0.06] overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      atAgentLimit
                        ? 'bg-amber-500'
                        : 'bg-gradient-to-r from-orange-500 to-amber-400'
                    }`}
                    style={{
                      width: `${Math.min((agentsUsed / maxAgents) * 100, 100)}%`,
                    }}
                  />
                </div>
                <span className="text-xs text-zinc-500 tabular-nums whitespace-nowrap">
                  {agentsUsed}/{maxAgents}
                </span>
              </div>
            )}
            <Link
              href="/dashboard/agents/new"
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200 shrink-0 ${
                atAgentLimit
                  ? 'bg-white/[0.05] text-zinc-500 cursor-not-allowed pointer-events-none'
                  : 'bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5'
              }`}
              aria-disabled={atAgentLimit}
              onClick={(e) => { if (atAgentLimit) e.preventDefault(); }}
            >
              <Plus className="w-4 h-4" />
              New Agent
            </Link>
          </div>
        </div>
        <p className="text-sm text-zinc-500 mt-1.5">
          Monitor and configure your AI agent workforce
          {tierLabel && (
            <span className="text-zinc-600"> &middot; {tierLabel}</span>
          )}
        </p>
      </motion.div>

      {/* ── Tier Limit Banner ────────────────────────────────────── */}
      {maxAgents > 0 && atAgentLimit && (
        <TierLimitBanner used={agentsUsed} limit={maxAgents} />
      )}

      {/* ── Agent Stats Bar ──────────────────────────────────────── */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="grid grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <StatCard
          icon={<Bot className="w-5 h-5" />}
          label="Total Agents"
          value={agents.length}
          subtitle={`of ${maxAgents === -1 ? '∞' : maxAgents} allowed`}
        />
        <StatCard
          icon={<Activity className="w-5 h-5" />}
          label="Active Agents"
          value={activeCount}
          subtitle={agents.length > 0 ? `${Math.round((activeCount / agents.length) * 100)}% online` : undefined}
          variant="success"
        />
        <StatCard
          icon={<ThumbsUp className="w-5 h-5" />}
          label="Avg Satisfaction"
          value={avgSatisfaction > 0 ? `${avgSatisfaction}%` : '—'}
          subtitle="across all agents"
          variant={avgSatisfaction >= 80 ? 'success' : avgSatisfaction >= 60 ? 'warning' : 'default'}
        />
        <StatCard
          icon={<Ticket className="w-5 h-5" />}
          label="Tickets Handled"
          value={ticketsToday > 0 ? ticketsToday.toLocaleString() : '—'}
          subtitle="total resolved"
        />
      </motion.div>

      {/* ── Agent Grid / Empty State ──────────────────────────────── */}
      {agents.length === 0 ? (
        <EmptyState />
      ) : (
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
        >
          {agents.map((agent, i) => (
            <AgentCard key={agent.id} agent={agent} index={i} />
          ))}
        </motion.div>
      )}

      {/* ── Bottom info when agents exist ──────────────────────────── */}
      {agents.length > 0 && agents.length < 3 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-4 flex items-center gap-3"
        >
          <div className="w-8 h-8 rounded-lg bg-orange-500/10 flex items-center justify-center shrink-0">
            <Zap className="w-4 h-4 text-orange-400" />
          </div>
          <div className="min-w-0">
            <p className="text-sm text-zinc-300">
              Add more agents to cover different support categories
            </p>
            <p className="text-xs text-zinc-500 mt-0.5">
              You still have {maxAgents === -1 ? 'unlimited' : maxAgents - agentsUsed} agent{maxAgents !== -1 && maxAgents - agentsUsed !== 1 ? 's' : ''} available on your plan.
            </p>
          </div>
          {!atAgentLimit && (
            <Link
              href="/dashboard/agents/new"
              className="ml-auto text-xs font-medium text-orange-400 hover:text-orange-300 transition-colors shrink-0 flex items-center gap-1"
            >
              Add agent <ArrowRight className="w-3 h-3" />
            </Link>
          )}
        </motion.div>
      )}
    </div>
  );
}
