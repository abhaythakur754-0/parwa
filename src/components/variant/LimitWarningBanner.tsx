'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { useVariant } from '@/contexts/VariantContext';

// ── Props ────────────────────────────────────────────────────────────────

interface LimitWarningBannerProps {
  type?: 'tickets' | 'agents' | 'team' | 'kb_docs' | 'all';
  className?: string;
  dismissible?: boolean;
  onDismiss?: () => void;
}

// ── Component ────────────────────────────────────────────────────────────

export function LimitWarningBanner({ 
  type = 'tickets',
  className,
  dismissible = true,
  onDismiss,
}: LimitWarningBannerProps) {
  const { limits, usage, variant } = useVariant();
  const [dismissed, setDismissed] = React.useState(false);
  
  // Check limits based on type
  const checkLimits = () => {
    const warnings: { resource: string; current: number; limit: number; severity: 'warning' | 'critical' }[] = [];
    
    if (type === 'tickets' || type === 'all') {
      const ticketPct = Math.round((usage.tickets_used / limits.monthly_tickets) * 100);
      if (ticketPct >= 100) {
        warnings.push({ resource: 'tickets', current: usage.tickets_used, limit: limits.monthly_tickets, severity: 'critical' });
      } else if (ticketPct >= 80) {
        warnings.push({ resource: 'tickets', current: usage.tickets_used, limit: limits.monthly_tickets, severity: 'warning' });
      }
    }
    
    if (type === 'agents' || type === 'all') {
      if (usage.ai_agents_used >= limits.ai_agents) {
        warnings.push({ resource: 'AI agents', current: usage.ai_agents_used, limit: limits.ai_agents, severity: 'critical' });
      }
    }
    
    if (type === 'team' || type === 'all') {
      if (usage.team_members_used >= limits.team_members) {
        warnings.push({ resource: 'team members', current: usage.team_members_used, limit: limits.team_members, severity: 'critical' });
      }
    }
    
    if (type === 'kb_docs' || type === 'all') {
      if (usage.kb_docs_used >= limits.kb_docs) {
        warnings.push({ resource: 'knowledge base documents', current: usage.kb_docs_used, limit: limits.kb_docs, severity: 'critical' });
      } else if (usage.kb_docs_used >= limits.kb_docs * 0.8) {
        warnings.push({ resource: 'knowledge base documents', current: usage.kb_docs_used, limit: limits.kb_docs, severity: 'warning' });
      }
    }
    
    return warnings;
  };
  
  const warnings = checkLimits();
  
  // Don't show if no warnings or dismissed
  if (warnings.length === 0 || dismissed) return null;
  
  const criticalWarnings = warnings.filter(w => w.severity === 'critical');
  const hasCritical = criticalWarnings.length > 0;
  
  const handleDismiss = () => {
    setDismissed(true);
    onDismiss?.();
  };
  
  // Generate message
  const getMessage = () => {
    if (hasCritical) {
      const resources = criticalWarnings.map(w => w.resource).join(', ');
      return `You've reached your ${resources} limit. Upgrade your plan to continue.`;
    }
    
    const warning = warnings[0];
    const pct = Math.round((warning.current / warning.limit) * 100);
    return `You've used ${pct}% of your ${warning.resource} limit. Consider upgrading soon.`;
  };
  
  return (
    <div className={cn(
      'flex items-start gap-3 p-4 rounded-xl border',
      hasCritical 
        ? 'bg-red-500/10 border-red-500/20' 
        : 'bg-yellow-500/10 border-yellow-500/20',
      className
    )}>
      {/* Icon */}
      <div className={cn(
        'shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
        hasCritical ? 'bg-red-500/20' : 'bg-yellow-500/20'
      )}>
        {hasCritical ? (
          <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
        ) : (
          <svg className="w-4 h-4 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
          </svg>
        )}
      </div>
      
      {/* Content */}
      <div className="flex-1 min-w-0">
        <h4 className={cn(
          'text-sm font-medium',
          hasCritical ? 'text-red-400' : 'text-yellow-400'
        )}>
          {hasCritical ? 'Limit Reached' : 'Approaching Limit'}
        </h4>
        <p className="text-sm text-zinc-400 mt-0.5">
          {getMessage()}
        </p>
        
        {/* Usage Details */}
        <div className="flex flex-wrap gap-3 mt-2">
          {warnings.map((w, idx) => (
            <span key={idx} className="text-xs bg-black/20 px-2 py-1 rounded">
              {w.resource}: {w.current.toLocaleString()}/{w.limit.toLocaleString()}
            </span>
          ))}
        </div>
        
        {/* CTA */}
        {variant !== 'high_parwa' && (
          <a 
            href="/dashboard/billing"
            className={cn(
              'inline-flex items-center gap-1.5 mt-3 text-sm font-medium',
              hasCritical ? 'text-red-400 hover:text-red-300' : 'text-yellow-400 hover:text-yellow-300'
            )}
          >
            Upgrade Plan →
          </a>
        )}
      </div>
      
      {/* Dismiss Button */}
      {dismissible && (
        <button 
          onClick={handleDismiss}
          className="shrink-0 p-1 rounded hover:bg-white/5 transition-colors"
        >
          <svg className="w-4 h-4 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  );
}

// ── Inline Warning for Forms ──────────────────────────────────────────────

export function InlineLimitWarning({ 
  type,
  className 
}: { 
  type: 'tickets' | 'agents' | 'team' | 'kb_docs';
  className?: string;
}) {
  const { limits, usage } = useVariant();
  
  const checkLimit = () => {
    switch (type) {
      case 'tickets':
        return { 
          current: usage.tickets_used, 
          limit: limits.monthly_tickets, 
          label: 'tickets' 
        };
      case 'agents':
        return { 
          current: usage.ai_agents_used, 
          limit: limits.ai_agents, 
          label: 'AI agents' 
        };
      case 'team':
        return { 
          current: usage.team_members_used, 
          limit: limits.team_members, 
          label: 'team members' 
        };
      case 'kb_docs':
        return { 
          current: usage.kb_docs_used, 
          limit: limits.kb_docs, 
          label: 'documents' 
        };
    }
  };
  
  const { current, limit, label } = checkLimit();
  const isAtLimit = current >= limit;
  
  if (!isAtLimit) return null;
  
  return (
    <div className={cn(
      'flex items-center gap-2 px-3 py-2 rounded-lg text-sm',
      'bg-red-500/10 border border-red-500/20 text-red-400',
      className
    )}>
      <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
      </svg>
      <span>You've reached your {label} limit ({limit}). Upgrade to add more.</span>
      <a href="/dashboard/billing" className="underline ml-1">Upgrade →</a>
    </div>
  );
}

export default LimitWarningBanner;
