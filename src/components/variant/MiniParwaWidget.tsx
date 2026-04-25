'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { useVariant } from '@/contexts/VariantContext';
import { VariantBadge, UsageMeters, LimitWarningBanner } from './index';

// ── Mini Parwa Widget ─────────────────────────────────────────────────────

interface MiniParwaWidgetProps {
  /** Show compact version for sidebar */
  compact?: boolean;
  /** Show detailed version for settings/billing */
  detailed?: boolean;
  className?: string;
}

/**
 * MiniParwaWidget
 * 
 * A comprehensive dashboard widget for Mini Parwa users showing:
 * - Current plan badge
 * - Usage meters with limits
 * - Limit warnings
 * - Model tier (Light only for Mini Parwa)
 * - Technique tier (Tier 1 only)
 * - Upgrade CTA
 */
export function MiniParwaWidget({ 
  compact = false, 
  detailed = false,
  className 
}: MiniParwaWidgetProps) {
  const { 
    variant, 
    limits, 
    usage, 
    isFeatureBlocked,
    getUpgradePrompt,
    canCreateTicket,
    getTicketWarning,
  } = useVariant();

  // Only show for mini_parwa variant
  if (variant !== 'mini_parwa') {
    return null;
  }

  const ticketWarning = getTicketWarning();

  // Compact version for sidebar
  if (compact) {
    return (
      <div className={cn(
        'rounded-lg border p-3',
        'bg-gradient-to-r from-orange-500/5 to-amber-500/5',
        'border-orange-500/20',
        className
      )}>
        <div className="flex items-center justify-between mb-2">
          <VariantBadge size="sm" showIcon={true} />
          <span className={cn(
            'text-xs font-medium',
            usage.utilization_pct >= 100 ? 'text-red-400' :
            usage.utilization_pct >= 80 ? 'text-yellow-400' : 'text-green-400'
          )}>
            {usage.utilization_pct}%
          </span>
        </div>
        
        {/* Ticket Progress */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-zinc-500">
            <span>Tickets</span>
            <span>{usage.tickets_used.toLocaleString()}/{limits.monthly_tickets.toLocaleString()}</span>
          </div>
          <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
            <div 
              className={cn(
                'h-full rounded-full transition-all',
                usage.utilization_pct >= 100 ? 'bg-red-500' :
                usage.utilization_pct >= 80 ? 'bg-yellow-500' : 'bg-green-500'
              )}
              style={{ width: `${Math.min(usage.utilization_pct, 100)}%` }}
            />
          </div>
        </div>

        {ticketWarning.show && (
          <p className={cn(
            'text-[10px] mt-2',
            ticketWarning.severity === 'critical' ? 'text-red-400' : 'text-yellow-400'
          )}>
            {ticketWarning.severity === 'critical' ? '⚠️ Limit reached' : '⚡ Approaching limit'}
          </p>
        )}
      </div>
    );
  }

  // Detailed version for billing/settings
  if (detailed) {
    return (
      <div className={cn(
        'rounded-xl border p-6',
        'bg-gradient-to-br from-orange-500/5 via-transparent to-amber-500/5',
        'border-orange-500/20',
        className
      )}>
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center">
              <span className="text-xl">🚀</span>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">Mini Parwa</h3>
              <p className="text-xs text-zinc-500">Your current plan</p>
            </div>
          </div>
          <a
            href="/dashboard/billing"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-orange-500/10 border border-orange-500/20 text-orange-400 text-sm font-medium rounded-lg hover:bg-orange-500/20 transition-colors"
          >
            Upgrade
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 15.75 7.5-7.5 7.5 7.5" />
            </svg>
          </a>
        </div>

        {/* Usage Meters */}
        <UsageMeters className="mb-6" />

        {/* Plan Limits */}
        <div className="grid grid-cols-2 gap-3 mb-6">
          <PlanLimitItem 
            label="AI Model" 
            value="Light Only"
            icon="🤖"
          />
          <PlanLimitItem 
            label="Techniques" 
            value="Tier 1 (CLARA, CRP, GSD)"
            icon="⚡"
          />
          <PlanLimitItem 
            label="API Access" 
            value="Read Only"
            icon="🔑"
          />
          <PlanLimitItem 
            label="Channels" 
            value="Email + Chat"
            icon="📧"
          />
        </div>

        {/* Limit Warning */}
        <LimitWarningBanner type="all" className="mb-4" />

        {/* What's Included */}
        <div className="pt-4 border-t border-white/[0.06]">
          <h4 className="text-sm font-medium text-zinc-300 mb-3">What's Included</h4>
          <div className="grid grid-cols-2 gap-2">
            {[
              '2000 tickets/month',
              '1 AI Agent',
              '3 Team Members',
              '100 KB Documents',
              'Email Channel',
              'Chat Widget',
              'Shadow Mode',
              'Basic Analytics',
              'Light AI Model',
              'Tier 1 Techniques',
            ].map((feature, idx) => (
              <div key={idx} className="flex items-center gap-2 text-xs text-zinc-400">
                <svg className="w-3.5 h-3.5 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                </svg>
                {feature}
              </div>
            ))}
          </div>
        </div>

        {/* Upgrade Benefits */}
        <div className="mt-6 pt-4 border-t border-white/[0.06]">
          <h4 className="text-sm font-medium text-zinc-300 mb-3">Upgrade to Unlock</h4>
          <div className="grid grid-cols-2 gap-2">
            {[
              { feature: 'SMS Channel', tier: 'Parwa' },
              { feature: 'Medium AI Model', tier: 'Parwa' },
              { feature: 'Tier 2 Techniques', tier: 'Parwa' },
              { feature: 'Voice AI', tier: 'High Parwa' },
              { feature: 'Heavy AI Model', tier: 'High Parwa' },
              { feature: 'Custom Integrations', tier: 'Parwa' },
            ].map((item, idx) => (
              <div key={idx} className="flex items-center gap-2 text-xs text-zinc-500">
                <svg className="w-3.5 h-3.5 text-orange-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
                </svg>
                <span className="text-zinc-500">{item.feature}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400">{item.tier}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Default dashboard widget
  return (
    <div className={cn('space-y-4', className)}>
      {/* Header with badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <VariantBadge showIcon={true} showLimits={false} />
          <span className="text-sm text-zinc-500">Plan Overview</span>
        </div>
        <a
          href="/dashboard/billing"
          className="text-sm text-orange-400 hover:text-orange-300 transition-colors flex items-center gap-1"
        >
          Manage
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
          </svg>
        </a>
      </div>

      {/* Limit Warning Banner */}
      {ticketWarning.show && (
        <LimitWarningBanner type="tickets" />
      )}

      {/* Quick Usage Summary */}
      <div className="grid grid-cols-4 gap-3">
        <QuickUsageCard
          label="Tickets"
          current={usage.tickets_used}
          limit={limits.monthly_tickets}
          icon="🎫"
        />
        <QuickUsageCard
          label="AI Agents"
          current={usage.ai_agents_used}
          limit={limits.ai_agents}
          icon="🤖"
        />
        <QuickUsageCard
          label="Team"
          current={usage.team_members_used}
          limit={limits.team_members}
          icon="👥"
        />
        <QuickUsageCard
          label="KB Docs"
          current={usage.kb_docs_used}
          limit={limits.kb_docs}
          icon="📚"
        />
      </div>

      {/* Model & Technique Info */}
      <div className="flex gap-3">
        <div className="flex-1 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
          <div className="flex items-center gap-2">
            <span className="text-sm">🧠</span>
            <div>
              <p className="text-xs text-zinc-500">AI Model</p>
              <p className="text-sm font-medium text-zinc-300">Light Only</p>
            </div>
          </div>
        </div>
        <div className="flex-1 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
          <div className="flex items-center gap-2">
            <span className="text-sm">⚡</span>
            <div>
              <p className="text-xs text-zinc-500">Techniques</p>
              <p className="text-sm font-medium text-zinc-300">Tier 1 (CLARA, CRP, GSD)</p>
            </div>
          </div>
        </div>
      </div>

      {/* Upgrade CTA */}
      <div className="flex items-center justify-between p-3 rounded-lg bg-gradient-to-r from-orange-500/10 to-amber-500/10 border border-orange-500/20">
        <div className="flex items-center gap-2">
          <span className="text-orange-400">💡</span>
          <span className="text-sm text-zinc-300">Get SMS channel & Medium AI</span>
        </div>
        <a
          href="/dashboard/billing"
          className="text-sm font-medium text-orange-400 hover:text-orange-300 transition-colors"
        >
          Upgrade to Parwa →
        </a>
      </div>
    </div>
  );
}

// ── Helper Components ─────────────────────────────────────────────────────

function QuickUsageCard({ 
  label, 
  current, 
  limit, 
  icon 
}: { 
  label: string; 
  current: number; 
  limit: number; 
  icon: string;
}) {
  const percentage = limit > 0 ? Math.round((current / limit) * 100) : 0;
  const isCritical = percentage >= 100;
  const isWarning = percentage >= 80 && !isCritical;

  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm">{icon}</span>
        <span className={cn(
          'text-xs font-medium',
          isCritical ? 'text-red-400' : isWarning ? 'text-yellow-400' : 'text-zinc-400'
        )}>
          {percentage}%
        </span>
      </div>
      <p className="text-xs text-zinc-500 mb-1">{label}</p>
      <p className={cn(
        'text-sm font-medium',
        isCritical ? 'text-red-400' : 'text-zinc-300'
      )}>
        {current.toLocaleString()}/{limit.toLocaleString()}
      </p>
      <div className="h-1 bg-white/5 rounded-full overflow-hidden mt-2">
        <div 
          className={cn(
            'h-full rounded-full transition-all',
            isCritical ? 'bg-red-500' : isWarning ? 'bg-yellow-500' : 'bg-green-500'
          )}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
    </div>
  );
}

function PlanLimitItem({ 
  label, 
  value, 
  icon 
}: { 
  label: string; 
  value: string; 
  icon: string;
}) {
  return (
    <div className="flex items-center gap-2 p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
      <span className="text-sm">{icon}</span>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-zinc-500 truncate">{label}</p>
        <p className="text-sm font-medium text-zinc-300 truncate">{value}</p>
      </div>
    </div>
  );
}

// ── Restricted Features Banner ─────────────────────────────────────────────

export function RestrictedFeaturesBanner({ className }: { className?: string }) {
  const { variant, isFeatureBlocked } = useVariant();

  if (variant !== 'mini_parwa') return null;

  const restrictedFeatures = [
    { key: 'sms_channel', label: 'SMS Channel', icon: '📱' },
    { key: 'voice_ai_channel', label: 'Voice AI', icon: '📞' },
    { key: 'ai_model_medium', label: 'Medium AI', icon: '🧠' },
    { key: 'custom_integrations', label: 'Custom Integrations', icon: '🔗' },
  ];

  const blocked = restrictedFeatures.filter(f => isFeatureBlocked(f.key));

  if (blocked.length === 0) return null;

  return (
    <div className={cn(
      'rounded-xl border p-4',
      'bg-gradient-to-r from-zinc-900 to-zinc-900/50',
      'border-white/[0.06]',
      className
    )}>
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-medium text-zinc-300">
          🔒 Upgrade to Unlock
        </h4>
        <a
          href="/dashboard/billing"
          className="text-xs text-orange-400 hover:text-orange-300"
        >
          View Plans →
        </a>
      </div>
      <div className="flex flex-wrap gap-2">
        {blocked.map((feature, idx) => (
          <span 
            key={idx}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.03] border border-white/[0.06] text-xs text-zinc-500"
          >
            <span>{feature.icon}</span>
            {feature.label}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Feature Lock Banner for Pages ───────────────────────────────────────────

export function FeatureLockBanner({ 
  feature,
  className 
}: { 
  feature: string;
  className?: string;
}) {
  const { getUpgradePrompt, variant } = useVariant();
  
  if (variant !== 'mini_parwa') return null;
  
  const prompt = getUpgradePrompt(feature);
  if (!prompt) return null;

  return (
    <div className={cn(
      'rounded-xl border p-4',
      'bg-gradient-to-r from-orange-500/10 to-amber-500/10',
      'border-orange-500/20',
      className
    )}>
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-orange-500/20 flex items-center justify-center shrink-0">
          <span className="text-xl">🔒</span>
        </div>
        <div className="flex-1">
          <h4 className="text-sm font-medium text-zinc-200 mb-1">
            {feature} is not available on Mini Parwa
          </h4>
          <p className="text-sm text-zinc-400">
            {prompt}
          </p>
          <a
            href="/dashboard/billing"
            className="inline-flex items-center gap-2 mt-3 px-4 py-2 bg-orange-500 text-white text-sm font-medium rounded-lg hover:bg-orange-600 transition-colors"
          >
            Upgrade Plan
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 15.75 7.5-7.5 7.5 7.5" />
            </svg>
          </a>
        </div>
      </div>
    </div>
  );
}

export default MiniParwaWidget;
