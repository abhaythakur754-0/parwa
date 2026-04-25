'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { useVariant } from '@/contexts/VariantContext';

// ── Props ────────────────────────────────────────────────────────────────

interface UsageMetersProps {
  compact?: boolean;
  className?: string;
}

interface UsageMeterProps {
  label: string;
  current: number;
  limit: number;
  icon: React.ReactNode;
  warningThreshold?: number;
  unit?: string;
}

// ── Single Usage Meter ────────────────────────────────────────────────────

function UsageMeter({ 
  label, 
  current, 
  limit, 
  icon,
  warningThreshold = 80,
  unit = ''
}: UsageMeterProps) {
  const percentage = limit > 0 ? Math.round((current / limit) * 100) : 0;
  const isWarning = percentage >= warningThreshold && percentage < 100;
  const isCritical = percentage >= 100;
  
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-zinc-400">{icon}</span>
          <span className="text-sm text-zinc-300">{label}</span>
        </div>
        <span className={cn(
          'text-sm font-medium',
          isCritical ? 'text-red-400' :
          isWarning ? 'text-yellow-400' : 'text-zinc-200'
        )}>
          {current.toLocaleString()}{unit}/{limit.toLocaleString()}{unit}
        </span>
      </div>
      
      {/* Progress Bar */}
      <div className="h-2 bg-white/5 rounded-full overflow-hidden">
        <div 
          className={cn(
            'h-full rounded-full transition-all duration-500',
            isCritical ? 'bg-red-500' :
            isWarning ? 'bg-yellow-500' : 'bg-green-500'
          )}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      
      {/* Warning/Critical Message */}
      {isCritical && (
        <p className="text-xs text-red-400">
          ⚠️ Limit reached. Upgrade to continue.
        </p>
      )}
      {isWarning && !isCritical && (
        <p className="text-xs text-yellow-400">
          ⚠️ Approaching limit ({percentage}% used)
        </p>
      )}
    </div>
  );
}

// ── Usage Meters Grid ─────────────────────────────────────────────────────

export function UsageMeters({ compact = false, className }: UsageMetersProps) {
  const { limits, usage } = useVariant();
  
  const Icons = {
    tickets: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 0 1 0 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 0 1 0-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375Z" />
      </svg>
    ),
    agents: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" />
      </svg>
    ),
    team: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 0 0 3.741-.479 3 3 0 0 0-4.682-2.72m.94 3.198.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0 1 12 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 0 1 6 18.719m12 0a5.971 5.971 0 0 0-.941-3.197m0 0A5.995 5.995 0 0 0 12 12.75a5.995 5.995 0 0 0-5.058 2.772m0 0a3 3 0 0 0-4.681 2.72 8.986 8.986 0 0 0 3.74.477m.94-3.197a5.971 5.971 0 0 0-.94 3.197M15 6.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm6 3a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Zm-13.5 0a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Z" />
      </svg>
    ),
    docs: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
      </svg>
    ),
  };

  if (compact) {
    return (
      <div className={cn('flex items-center gap-4', className)}>
        <UsageMeter
          label="Tickets"
          current={usage.tickets_used}
          limit={limits.monthly_tickets}
          icon={Icons.tickets}
        />
      </div>
    );
  }

  return (
    <div className={cn('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4', className)}>
      <UsageMeter
        label="Monthly Tickets"
        current={usage.tickets_used}
        limit={limits.monthly_tickets}
        icon={Icons.tickets}
      />
      <UsageMeter
        label="AI Agents"
        current={usage.ai_agents_used}
        limit={limits.ai_agents}
        icon={Icons.agents}
      />
      <UsageMeter
        label="Team Members"
        current={usage.team_members_used}
        limit={limits.team_members}
        icon={Icons.team}
      />
      <UsageMeter
        label="Knowledge Base"
        current={usage.kb_docs_used}
        limit={limits.kb_docs}
        icon={Icons.docs}
        unit=" docs"
      />
    </div>
  );
}

// ── Quick Usage Summary for Dashboard ─────────────────────────────────────

export function QuickUsageSummary({ className }: { className?: string }) {
  const { limits, usage, variant } = useVariant();
  const ticketPercentage = limits.monthly_tickets > 0 
    ? Math.round((usage.tickets_used / limits.monthly_tickets) * 100) 
    : 0;
  
  return (
    <div className={cn(
      'flex items-center gap-3 px-3 py-2 rounded-lg',
      'bg-gradient-to-r from-orange-500/5 to-amber-500/5',
      'border border-orange-500/10',
      className
    )}>
      <div className="flex-1">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-zinc-400">
            {variant === 'mini_parwa' ? 'Mini Parwa' : variant === 'parwa' ? 'Parwa' : 'High Parwa'} Usage
          </span>
          <span className={cn(
            'font-medium',
            ticketPercentage >= 100 ? 'text-red-400' :
            ticketPercentage >= 80 ? 'text-yellow-400' : 'text-green-400'
          )}>
            {ticketPercentage}%
          </span>
        </div>
        <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
          <div 
            className={cn(
              'h-full rounded-full transition-all',
              ticketPercentage >= 100 ? 'bg-red-500' :
              ticketPercentage >= 80 ? 'bg-yellow-500' : 'bg-green-500'
            )}
            style={{ width: `${Math.min(ticketPercentage, 100)}%` }}
          />
        </div>
      </div>
      
      <a 
        href="/dashboard/billing" 
        className="text-xs text-orange-400 hover:text-orange-300 whitespace-nowrap"
      >
        View Details →
      </a>
    </div>
  );
}

export default UsageMeters;
